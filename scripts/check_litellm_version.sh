#!/usr/bin/env bash
# check_litellm_version.sh — Compare the running LiteLLM image digest against
# the pinned digest in docker-compose.yml.
#
# Usage:
#   ./scripts/check_litellm_version.sh
#
# Exits 0 if up to date, 1 if outdated or image not pulled.

set -euo pipefail

COMPOSE_FILE="$(dirname "$0")/../docker-compose.yml"

# Extract the pinned digest from docker-compose.yml
PINNED=$(grep -o 'sha256:[a-f0-9]*' "$COMPOSE_FILE" | head -1)

if [[ -z "$PINNED" ]]; then
  echo "ERROR: Could not find a pinned digest in docker-compose.yml" >&2
  echo "  Expected a line like: image: ghcr.io/berriai/litellm@sha256:..." >&2
  exit 1
fi

# Get the digest of the locally pulled main-latest
CURRENT=$(podman inspect ghcr.io/berriai/litellm:main-latest --format '{{.Digest}}' 2>/dev/null || echo "none")

if [[ "$CURRENT" == "none" ]]; then
  echo "⚠️  Latest image not pulled locally."
  echo "   Run: podman pull ghcr.io/berriai/litellm:main-latest"
  exit 1
fi

echo "Pinned:  $PINNED"
echo "Current: $CURRENT"
echo ""

if [[ "$CURRENT" == "$PINNED" ]]; then
  echo "✅ LiteLLM image is up to date."
else
  echo "⚠️  A newer image is available."
  echo ""
  echo "To upgrade:"
  echo "  1. Test the new image manually if needed"
  echo "  2. Update the digest in docker-compose.yml:"
  echo "       image: ghcr.io/berriai/litellm@$CURRENT"
  echo "  3. Restart the stack:"
  echo "       podman-compose down && podman-compose up -d"
  echo "  4. Verify everything works, then commit:"
  echo "       git add docker-compose.yml"
  echo "       git commit -m 'chore: upgrade LiteLLM image digest'"
  exit 1
fi
