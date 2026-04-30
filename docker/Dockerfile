FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# slim-bookworm already has ca-certificates; we don't need build-essential because
# every runtime dep ships manylinux wheels for amd64+py3.12, and the healthcheck
# uses python -c urllib.request, not curl.

# uv for fast deps install
COPY --from=ghcr.io/astral-sh/uv:0.5.13 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN uv pip install --system --no-cache-dir -e .

# Non-root user for runtime
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

ENV PYTHONPATH=/app/src

CMD ["uvicorn", "jarvis.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
