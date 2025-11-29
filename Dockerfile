# syntax=docker/dockerfile:1

# Multi-stage Docker build optimized for uv
# Based on: https://docs.astral.sh/uv/guides/integration/docker/

# Stage 1: Builder - Install dependencies and compile bytecode
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Install git for submodule cloning
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Enable bytecode compilation and copy mode for cache mounts
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first (separate layer for caching)
# This layer will only rebuild when pyproject.toml or uv.lock changes
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Copy the entire project (including .git for submodule initialization)
COPY . /app

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Clone private submodule using GitHub token
RUN --mount=type=secret,id=gh_token \
    git config --global url."https://$(cat /run/secrets/gh_token)@github.com/".insteadOf "https://github.com/" && \
    git submodule update --init --recursive

# Stage 2: Runtime - Minimal final image without uv
FROM python:3.12-slim-bookworm

# Install runtime dependencies for Pillow and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    libjpeg62-turbo \
    libfreetype6 \
    libopenjp2-7 \
    libtiff6 \
    libwebp7 \
    liblcms2-2 \
    libfribidi0 \
    libharfbuzz0b \
    && rm -rf /var/lib/apt/lists/*

# Copy the application and virtual environment from builder
COPY --from=builder --chown=app:app /app /app

# Place virtual environment executables at front of PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Default command (override in docker-compose.yml)
CMD ["python", "-OO", "run.py"]
