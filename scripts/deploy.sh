#!/bin/bash
set -euo pipefail

REMOTE="${1:?Usage: ./scripts/deploy.sh user@host}"
REMOTE_DIR="/opt/hermes-cro-agent"

echo "Deploying to ${REMOTE}:${REMOTE_DIR}..."

rsync -az --delete \
  --exclude='.env' \
  --exclude='crawls/' \
  --exclude='.git/' \
  . "${REMOTE}:${REMOTE_DIR}"

scp .env "${REMOTE}:${REMOTE_DIR}/.env"

ssh "${REMOTE}" bash <<'ENDSSH'
set -euo pipefail
cd /opt/hermes-cro-agent

if ! command -v docker &>/dev/null; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | bash
  usermod -aG docker $USER || true
fi

if ! docker compose version &>/dev/null 2>&1; then
  apt-get install -y docker-compose-plugin
fi

docker compose build
docker compose up -d

sleep 8
curl -sf http://localhost:${WEBHOOK_PORT:-8644}/health \
  && echo " ✓ Gateway is up" \
  || echo " ✗ Not ready — check: docker compose logs"
ENDSSH
