#!/usr/bin/env bash
#
# Build and publish ghcr.io/smart-associates/sdf to GitHub Container Registry
# as a multi-arch image.
#
# Usage:
#   scripts/publish.sh              # tags :latest and :<git-sha>
#   scripts/publish.sh 1.2.0        # additionally tags :1.2.0
#
# Prerequisites:
#   * docker login ghcr.io (credentials for the smart-associates org, e.g. a
#     PAT with write:packages)
#   * docker buildx       (bundled with recent Docker Desktop / docker-buildx-plugin)
#   * QEMU for cross-build (auto-installed by Docker Desktop; on Linux:
#     `docker run --rm --privileged tonistiigi/binfmt --install all`)
#
set -euo pipefail

REPO="ghcr.io/smart-associates/sdf"
VERSION="${1:-}"
BUILDER="sdf-builder"

cd "$(dirname "$0")/.."

GIT_SHA="$(git rev-parse --short HEAD)"
DIRTY=""
if ! git diff --quiet || ! git diff --cached --quiet; then
  DIRTY="-dirty"
  echo "warning: working tree is dirty; git sha tag will be ${GIT_SHA}${DIRTY}" >&2
fi

# Confirm GHCR login (config stores "auths" entries post-login).
if ! grep -q '"ghcr.io"' "${DOCKER_CONFIG:-$HOME/.docker}/config.json" 2>/dev/null; then
  echo "error: not logged into ghcr.io. Run 'docker login ghcr.io' first." >&2
  exit 1
fi

# Ensure a multi-arch builder exists and is selected.
if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
  docker buildx create --name "$BUILDER" --driver docker-container --use
else
  docker buildx use "$BUILDER"
fi
docker buildx inspect --bootstrap >/dev/null

TAGS=(-t "$REPO:latest" -t "$REPO:${GIT_SHA}${DIRTY}")
if [ -n "$VERSION" ]; then
  TAGS+=(-t "$REPO:$VERSION")
fi

echo "Publishing ${REPO} (linux/amd64, linux/arm64) with tags:"
printf '  %s\n' "${TAGS[@]}" | sed 's/^  -t /  /'

docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg SDF_VERSION="${VERSION:-$GIT_SHA}" \
  --build-arg SDF_GIT_SHA="$GIT_SHA" \
  "${TAGS[@]}" \
  --push \
  .

echo
echo "Pushed. Verify with:"
echo "  docker buildx imagetools inspect ${REPO}:${VERSION:-latest}"
