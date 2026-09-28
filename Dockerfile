# syntax=docker/dockerfile:1

FROM rust:bookworm AS builder

WORKDIR /src

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        perl \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# The server image also contains the workgpt CLI so server-side pairing and
# administration can be run with `docker compose exec workgpt workgpt ...`.
# workgpt-runner is intentionally not built into this image. Git metadata is
# supplied as build args because .git is intentionally outside the build context.
ARG WORKGPT_GIT_COMMIT
ARG WORKGPT_GIT_DIRTY
ARG WORKGPT_BUILT_AT
RUN WORKGPT_GIT_COMMIT="$WORKGPT_GIT_COMMIT" \
    WORKGPT_GIT_DIRTY="$WORKGPT_GIT_DIRTY" \
    WORKGPT_BUILT_AT="$WORKGPT_BUILT_AT" \
    cargo build --locked --release --bins -p workgpt -p workgpt-cli

FROM debian:bookworm-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libgcc-s1 \
        libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 workgpt \
    && useradd --system --uid 10001 --gid workgpt \
        --home-dir /var/lib/workgpt workgpt \
    && install -d -o workgpt -g workgpt -m 0700 /var/lib/workgpt

COPY --from=builder /src/target/release/workgpt-server /usr/local/bin/workgpt-server
COPY --from=builder /src/target/release/workgpt /usr/local/bin/workgpt

ENV WORKGPT_ADDR=0.0.0.0:8080 \
    WORKGPT_DATA=/var/lib/workgpt \
    RUST_LOG=info

USER workgpt:workgpt
WORKDIR /var/lib/workgpt

EXPOSE 8080
VOLUME ["/var/lib/workgpt"]

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8080/healthz >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/workgpt-server"]
