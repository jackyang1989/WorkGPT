# Download page source

This directory is the source for the release-manifest-driven static download page. `manifest.json` is generated for a specific published release and is intentionally not tracked here, so opening `index.html` directly from a checkout shows an unavailable-manifest state.

To build a usable page locally, download the manifest for a published release and render it:

```sh
release_tag=v1.2.3
mkdir -p /tmp/workgpt-release
gh release download "$release_tag" --repo jackyang1989/WorkGPT --pattern manifest.json --dir /tmp/workgpt-release
python3 scripts/build_download_page.py \
  --manifest /tmp/workgpt-release/manifest.json \
  --output-dir /tmp/workgpt-download-page
```

The [download-page workflow](https://github.com/jackyang1989/WorkGPT/actions/workflows/download-page.yml) performs the same build after a release is published, or on a manual run with a tag. It uploads the result as the `download-page-<tag>` GitHub Actions artifact. The workflow does not publish or deploy that artifact as a website; published release downloads remain available from [GitHub Releases](https://github.com/jackyang1989/WorkGPT/releases).
