# syntax=docker/dockerfile:1.6

# --- Stage 1: build the React UI ---------------------------------------------
FROM node:20-alpine AS ui-build
WORKDIR /ui

COPY ui/package.json ui/package-lock.json ./
# node:20-alpine ships npm 10.8.2, which rejects this lockfile's
# platform-specific optional deps ("Missing: @emnapi/core from lock file").
# Pin npm to the version used to regenerate the lockfile so rebuilds are
# reproducible — bumping npm here means also regenerating package-lock.json.
RUN npm install -g npm@11.12.1 && npm ci --no-audit --no-fund

COPY ui/ ./
RUN npm run build


# --- Stage 2: runtime (FastAPI + built UI) -----------------------------------
FROM python:3.11-slim AS runtime

ARG SDF_VERSION=dev
ARG SDF_GIT_SHA=unknown

LABEL org.opencontainers.image.title="SDF" \
      org.opencontainers.image.description="Smart Data Frameworks - web-based data migration tool" \
      org.opencontainers.image.source="https://github.com/smart-associates/sdf" \
      org.opencontainers.image.url="https://hub.docker.com/r/smartassociates/sdf" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${SDF_VERSION}" \
      org.opencontainers.image.revision="${SDF_GIT_SHA}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SDF_VERSION=${SDF_VERSION} \
    SDF_GIT_SHA=${SDF_GIT_SHA}

WORKDIR /app

# libpq5 + curl: runtime deps (psycopg2-binary, HEALTHCHECK). postgresql:
# bundled server for the embedded-Postgres fallback when no external DATABASE_URL
# is configured (docker-entrypoint.py spins it up on a unix socket). All Python
# deps ship manylinux/musllinux wheels for amd64+arm64, so no compiler needed.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 curl postgresql \
 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./
COPY --from=ui-build /ui/dist /app/ui_dist

RUN chmod +x /app/docker-entrypoint.py \
 && useradd -u 10001 -m -s /bin/false sdf \
 && chown -R sdf:sdf /app

USER sdf

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.py"]
