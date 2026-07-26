# rustfava server - web interface for rustledger
# Build: docker build -t rustfava .
# Multi-arch: docker buildx build --platform linux/amd64,linux/arm64 -t rustfava .
# Run:   docker run -p 5000:5000 -v /path/to/ledger:/data rustfava /data/main.beancount

# Build the frontend once, natively on the build host ($BUILDPLATFORM). The
# output is architecture-independent JS/CSS, and bun's JIT is unreliable under
# QEMU user emulation, so cross-builds must never run it on the target arch.
FROM --platform=$BUILDPLATFORM oven/bun:1-slim AS frontend

WORKDIR /build
COPY frontend/ frontend/
# build.ts emits into ../src/rustfava/static relative to frontend/
RUN mkdir -p src/rustfava/static \
    && cd frontend \
    && bun install --frozen-lockfile \
    && bun run build

# Runtime image, built per target platform. Everything here is either pure
# Python or a dependency with prebuilt wheels for amd64 and arm64, so no
# compilers, bun, or arch-specific downloads are needed.
FROM python:3.13-slim

WORKDIR /app

# Copy source and frontend sources (the build backend stats them to decide
# whether a frontend rebuild is needed)
COPY pyproject.toml MANIFEST.in _build_backend.py ./
COPY src/ src/
COPY frontend/ frontend/

# Overlay the prebuilt frontend and mark it fresh so the build backend skips
# the bun build entirely (bun is not installed in this stage).
COPY --from=frontend /build/src/rustfava/static/ src/rustfava/static/
RUN touch src/rustfava/static/*

# Install rustfava (set version since no .git in container)
ARG VERSION=0.1.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}
RUN pip install --no-cache-dir .

# Pre-fetch the rustledger component wasm (architecture-independent) into the
# installed package so containers work offline and the first request does not
# stall on a download.
RUN python -c "\
from rustfava.rustledger.component_engine import _default_wasm_path, _download_component_wasm; \
path = _default_wasm_path(); \
_download_component_wasm(path); \
assert path.exists(), 'component wasm download failed'"

# Sources are installed into site-packages; drop them from the image
RUN rm -rf /app/frontend /app/src

# Create data directory for mounting ledger files
RUN mkdir -p /data

EXPOSE 5000

# Listen on all interfaces, dual-stack: Docker also forwards published ports
# over IPv6, and browsers resolve localhost to ::1 first, so an IPv4-only
# (0.0.0.0) bind makes http://localhost:<port> fail on many hosts.
ENV RUSTFAVA_HOST=::
ENV RUSTFAVA_PORT=5000

ENTRYPOINT ["rustfava"]
# User provides the beancount file path as argument, e.g.:
# docker run -p 5000:5000 -v ~/ledger:/data rustfava /data/main.beancount
