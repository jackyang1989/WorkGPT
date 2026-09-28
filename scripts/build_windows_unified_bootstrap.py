#!/usr/bin/env python3
"""Build the outer Windows unified installer around a Tauri NSIS payload."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import prepare_windows_unified_installer as candidate


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nsis_quote(path: Path) -> str:
    value = str(path.resolve()).replace("/", "\\")
    if any(ch in value for ch in ('"', "$", "\r", "\n")):
        raise ValueError("NSIS path contains unsupported characters")
    return f'"{value}"'


def render(candidate_dir: Path, inner_installer: Path, output: Path, platform: str) -> str:
    manifest, files = candidate.validate_candidate(candidate_dir, platform)
    inner = inner_installer.resolve(strict=True)
    if inner.read_bytes()[:2] != b"MZ":
        raise ValueError("inner Tauri installer is not a Windows executable")
    target = "x86_64" if platform == "win32-x64" else "aarch64"
    lines = [
        'Unicode true',
        '!include "LogicLib.nsh"',
        '!include "FileFunc.nsh"',
        '!include "WinMessages.nsh"',
        '!include "StrFunc.nsh"',
        '${Using:StrFunc} StrStr',
        'Name "WorkGPT Unified Installer"',
        f'OutFile {nsis_quote(output)}',
        'RequestExecutionLevel user',
        'InstallDir "$LOCALAPPDATA\\WorkGPT Desktop"',
        'Var WorkGPTInstallDir',
        'Var WorkGPTEnvironmentDir',
        'Var WorkGPTExisting',
        'Var WorkGPTCandidate',
        'Var WorkGPTTrustedCLI',
        'Var WorkGPTOldDesktop',
        'Var WorkGPTUpgradePrepared',
        '',
        'Function .onInit',
        '  SetRegView 64',
        '  StrCpy $WorkGPTEnvironmentDir ""',
        '  ${GetParameters} $R0',
        '  ClearErrors',
        '  ${GetOptions} $R0 "/ENVIRONMENTDIR=" $WorkGPTEnvironmentDir',
        '  ${If} ${Errors}',
        '    StrCpy $WorkGPTEnvironmentDir ""',
        '  ${EndIf}',
        '  ReadRegStr $WorkGPTInstallDir HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\WorkGPT Desktop" "InstallLocation"',
        '  ${If} $WorkGPTInstallDir == ""',
        '    StrCpy $WorkGPTInstallDir "$LOCALAPPDATA\\WorkGPT Desktop"',
        '  ${Else}',
        '    StrCpy $0 $WorkGPTInstallDir 1',
        '    ${If} $0 == \'"\'',
        '      StrCpy $WorkGPTInstallDir $WorkGPTInstallDir -1 1',
        '    ${EndIf}',
        '  ${EndIf}',
        'FunctionEnd',
        '',
        'Section "-WorkGPTUnifiedBootstrap"',
        '  StrCpy $WorkGPTExisting 0',
        '  ReadRegStr $R3 HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\WorkGPT Desktop" "InstallLocation"',
        '  ${If} $R3 != ""',
        '    StrCpy $WorkGPTExisting 1',
        '  ${EndIf}',
        '  ${If} ${FileExists} "$WorkGPTInstallDir\\WorkGPT.exe"',
        '  ${OrIf} ${FileExists} "$WorkGPTInstallDir\\workgpt-runtime\\workgpt.exe"',
        '    StrCpy $WorkGPTExisting 1',
        '  ${EndIf}',
        '  SetRegView 64',
        '  StrCpy $R1 0',
        'workgpt_service_scan:',
        '  EnumRegKey $R0 HKLM "SYSTEM\\CurrentControlSet\\Services" $R1',
        '  ${If} $R0 == ""',
        '    Goto workgpt_services_checked',
        '  ${EndIf}',
        '  StrCpy $R2 $R0 8',
        '  ${If} $R2 == "WorkGPT"',
        '    StrCpy $WorkGPTExisting 1',
        '  ${EndIf}',
        '  IntOp $R1 $R1 + 1',
        '  Goto workgpt_service_scan',
        'workgpt_services_checked:',
        '  InitPluginsDir',
        '  StrCpy $WorkGPTCandidate "$PLUGINSDIR\\WorkGPTUpgradeCandidate"',
        '  SetOutPath "$WorkGPTCandidate"',
        f'  File /oname=source-manifest.json {nsis_quote(candidate_dir / "source-manifest.json")}',
        f'  File /oname=SHA256SUMS {nsis_quote(candidate_dir / "SHA256SUMS")}',
        '  SetOutPath "$WorkGPTCandidate\\artifacts\\bin"',
    ]
    for name in candidate.BINARIES:
        lines.append(f'  File /oname={name}.exe {nsis_quote(files[name])}')
    lines.extend([
        f'  ExecWait \'"$WINDIR\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -NonInteractive -Command "$h=(Get-FileHash -Algorithm SHA256 -LiteralPath $args[0]).Hash.ToLowerInvariant(); if($h -ne {manifest["artifacts"]["workgpt"]["sha256"]}){{exit 1}}" "$WorkGPTCandidate\\artifacts\\bin\\workgpt.exe"\' $0',
        '  ${If} $0 != 0',
        '    MessageBox MB_ICONSTOP "WorkGPT candidate CLI failed its manifest-bound SHA-256 check."',
        '    SetErrorLevel 1',
        '    Abort',
        '  ${EndIf}',
        '  StrCpy $WorkGPTTrustedCLI "$WorkGPTCandidate\\artifacts\\bin\\workgpt.exe"',
        '  ${If} $WorkGPTExisting == 1',
        '    ${If} ${FileExists} "$WorkGPTInstallDir\\workgpt-runtime\\workgpt.exe"',
        '      StrCpy $WorkGPTTrustedCLI "$WorkGPTInstallDir\\workgpt-runtime\\workgpt.exe"',
        '    ${EndIf}',
        '  ${EndIf}',
        '  ${If} $WorkGPTExisting == 1',
        '    ExecWait \'"$WorkGPTTrustedCLI" environment installer-verify-same --candidate-dir "$WorkGPTCandidate" --expected-runtime-dir "$WorkGPTInstallDir\\workgpt-runtime" --json\' $0',
        '    ${If} $0 == 0',
        '      Goto workgpt_bootstrap_done',
        '    ${EndIf}',
        '  ${EndIf}',
        '  ${If} $WorkGPTEnvironmentDir == ""',
        '    ExecWait \'"$WorkGPTTrustedCLI" environment upgrade-preflight --candidate-dir "$WorkGPTCandidate" --json\' $0',
        '  ${Else}',
        '    ExecWait \'"$WorkGPTTrustedCLI" environment upgrade-preflight --candidate-dir "$WorkGPTCandidate" --environment-dir "$WorkGPTEnvironmentDir" --json\' $0',
        '  ${EndIf}',
        '  ${If} $0 != 0',
        '    MessageBox MB_ICONSTOP "WorkGPT upgrade preflight rejected this installer."',
        '    SetErrorLevel 1',
        '    Abort',
        '  ${EndIf}',
        '  StrCpy $WorkGPTUpgradePrepared 1',
        '  ${If} $WorkGPTEnvironmentDir == ""',
        '    ExecWait \'"$WorkGPTTrustedCLI" environment upgrade-prepare --candidate-dir "$WorkGPTCandidate" --json\' $0',
        '  ${Else}',
        '    ExecWait \'"$WorkGPTTrustedCLI" environment upgrade-prepare --candidate-dir "$WorkGPTCandidate" --environment-dir "$WorkGPTEnvironmentDir" --json\' $0',
        '  ${EndIf}',
        '  ${If} $0 != 0',
        '    Call WorkGPTRollback',
        '    MessageBox MB_ICONSTOP "WorkGPT could not prepare the upgrade; installation was stopped."',
        '    SetErrorLevel 1',
        '    Abort',
        '  ${EndIf}',
        '  ${If} $WorkGPTExisting == 1',
        '    ${If} $WorkGPTEnvironmentDir == ""',
        '      ExecWait \'"$WorkGPTTrustedCLI" environment installer-verify --candidate-dir "$WorkGPTCandidate" --expected-runtime-dir "$WorkGPTInstallDir\\workgpt-runtime" --json\' $0',
        '    ${Else}',
        '      ExecWait \'"$WorkGPTTrustedCLI" environment installer-verify --candidate-dir "$WorkGPTCandidate" --expected-runtime-dir "$WorkGPTInstallDir\\workgpt-runtime" --environment-dir "$WorkGPTEnvironmentDir" --json\' $0',
        '    ${EndIf}',
        '    ${If} $0 != 0',
        '      Call WorkGPTRollback',
        '      MessageBox MB_ICONSTOP "Prepared owner receipt or runtime target does not match this installation. No files were replaced."',
        '      SetErrorLevel 1',
        '      Abort',
        '    ${EndIf}',
        '  ${EndIf}',
        '  ${If} ${FileExists} "$WorkGPTInstallDir\\WorkGPT.exe"',
        '    StrCpy $WorkGPTOldDesktop "$PLUGINSDIR\\WorkGPTDesktop.backup.exe"',
        '    CopyFiles /SILENT "$WorkGPTInstallDir\\WorkGPT.exe" "$WorkGPTOldDesktop"',
        '  ${EndIf}',
        '  SetOutPath "$PLUGINSDIR"',
        f'  File /oname=WorkGPTTauriPayload.exe {nsis_quote(inner)}',
        '  ExecWait \'"$PLUGINSDIR\\WorkGPTTauriPayload.exe" /S /UPDATE /D=$WorkGPTInstallDir\' $0',
        '  ${If} $0 != 0',
        '    Call WorkGPTRollback',
        '    MessageBox MB_ICONSTOP "WorkGPT installation failed; the previous environment was restored."',
        '    SetErrorLevel 1',
        '    Abort',
        '  ${EndIf}',
        '  ${If} $WorkGPTEnvironmentDir == ""',
        '    ExecWait \'"$WorkGPTInstallDir\\workgpt-runtime\\workgpt.exe" environment upgrade-finish --json\' $0',
        '  ${Else}',
        '    ExecWait \'"$WorkGPTInstallDir\\workgpt-runtime\\workgpt.exe" environment upgrade-finish --environment-dir "$WorkGPTEnvironmentDir" --json\' $0',
        '  ${EndIf}',
        '  ${If} $0 != 0',
        '    Call WorkGPTRollback',
        '    MessageBox MB_ICONSTOP "WorkGPT could not verify the installed upgrade; rollback was requested."',
        '    SetErrorLevel 1',
        '    Abort',
        '  ${EndIf}',
        '  ReadRegStr $0 HKCU "Environment" "Path"',
        '  StrCpy $1 "$WorkGPTInstallDir\\workgpt-runtime"',
        '  ${StrStr} $2 "$0" "$1"',
        '  ${If} $2 == ""',
        '    ${If} $0 == ""',
        '      WriteRegStr HKCU "Environment" "Path" "$1"',
        '    ${Else}',
        '      WriteRegStr HKCU "Environment" "Path" "$1;$0"',
        '    ${EndIf}',
        '  ${EndIf}',
        '  SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=5000',
        '  StrCpy $WorkGPTUpgradePrepared 0',
        'workgpt_bootstrap_done:',
        'SectionEnd',
        '',
        'Function WorkGPTRollback',
        '  ${If} $WorkGPTUpgradePrepared == 1',
        '    ${If} $WorkGPTEnvironmentDir == ""',
        '      ExecWait \'"$WorkGPTTrustedCLI" environment upgrade-rollback --json\' $0',
        '    ${Else}',
        '      ExecWait \'"$WorkGPTTrustedCLI" environment upgrade-rollback --environment-dir "$WorkGPTEnvironmentDir" --json\' $0',
        '    ${EndIf}',
        '    ${If} ${FileExists} "$WorkGPTOldDesktop"',
        '      CopyFiles /SILENT "$WorkGPTOldDesktop" "$WorkGPTInstallDir\\WorkGPT.exe"',
        '    ${EndIf}',
        '    ${If} $0 != 0',
        '      MessageBox MB_ICONSTOP "WorkGPT rollback failed; the previous program backup remains available."',
        '    ${EndIf}',
        '  ${EndIf}',
        '  StrCpy $WorkGPTUpgradePrepared 0',
        'FunctionEnd',
        '',
        'Function .onInstFailed',
        '  Call WorkGPTRollback',
        'FunctionEnd',
        'Function .onUserAbort',
        '  Call WorkGPTRollback',
        'FunctionEnd',
        '',
    ])
    return "\n".join(lines)


def build(args: argparse.Namespace) -> dict:
    if args.output.exists():
        raise ValueError(f"output already exists: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source = render(args.candidate_dir, args.inner_installer, args.output, args.platform)
    script = args.output.with_suffix(".nsi")
    script.write_text(source, encoding="utf-8", newline="\n")
    compiler = args.makensis or shutil.which("makensis")
    if not compiler:
        raise ValueError("makensis is required to build the Windows bootstrap installer")
    result = subprocess.run([compiler, "/V3", str(script)], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180)
    if result.returncode:
        args.output.unlink(missing_ok=True)
        raise ValueError("makensis failed to compile the outer Windows installer")
    manifest = json.loads((args.candidate_dir / "source-manifest.json").read_text(encoding="utf-8"))
    provenance = {
        "schema_version": 1,
        "platform": args.platform,
        "version": manifest["version"],
        "source_sha": manifest["source_sha"],
        "workflow_run_id": manifest["source_workflow_run_id"],
        "workflow_ref": manifest["source_workflow_ref"],
        "candidate_manifest_sha256": sha256(args.candidate_dir / "source-manifest.json"),
        "inner_installer_sha256": sha256(args.inner_installer),
        "installer_sha256": sha256(args.output),
    }
    sidecar = args.output.with_suffix(args.output.suffix + ".provenance.json")
    sidecar.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--inner-installer", type=Path, required=True)
    parser.add_argument("--platform", choices=tuple(candidate.TARGETS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--makensis")
    args = parser.parse_args()
    try:
        print(json.dumps(build(args), sort_keys=True))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"Windows unified bootstrap build failed: {exc}") from exc
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
