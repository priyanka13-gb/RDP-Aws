# Supported Debian Trixie/Python 3.12 base, pinned for reviewable updates.
ARG PYTHON_BASE=python:3.12-slim@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54
FROM ${PYTHON_BASE} AS base

# Apply available stable security updates to both build and runtime stages.
# Do not mix Debian unstable packages into the supported runtime.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Fix the inherited pip 25.0.1 advisories without changing application libraries.
RUN python -m pip install --no-cache-dir --upgrade pip==26.2

FROM base AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml README.md ./
COPY app/ ./app/
RUN python -m pip wheel --wheel-dir /wheels .

FROM base AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels aws-resilient-delivery-platform \
    && python -m pip uninstall -y pip \
    && rm -rf /wheels
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
