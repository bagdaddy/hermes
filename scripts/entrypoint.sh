#!/bin/bash
set -euo pipefail

echo "[entrypoint] Starting hermes-cro-agent..."

: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY is required. Copy .env.example to .env and fill it in.}"
: "${WEBHOOK_SECRET:?WEBHOOK_SECRET is required.}"
: "${CRAWL_OUTPUT_DIR:?CRAWL_OUTPUT_DIR is required.}"

WEBHOOK_PORT="${WEBHOOK_PORT:-8644}"
HERMES_INTERNAL_PORT="${HERMES_INTERNAL_PORT:-8645}"
export HERMES_INTERNAL_PORT

mkdir -p "${CRAWL_OUTPUT_DIR}"
mkdir -p /root/.hermes

# The `execute_code` sandbox doesn't see container env vars, so agents often
# fall back to writing to /tmp/crawls/. Symlink onto the real crawl dir so
# their output lands on the host-mounted volume.
rm -rf /tmp/crawls
ln -sfn "${CRAWL_OUTPUT_DIR}" /tmp/crawls

cat > /root/.hermes/.env <<ENVEOF
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
WEBHOOK_ENABLED=true
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=${HERMES_INTERNAL_PORT}
WEBHOOK_SECRET=${WEBHOOK_SECRET}
CRAWL_OUTPUT_DIR=${CRAWL_OUTPUT_DIR}
GATEWAY_ALLOW_ALL_USERS=true
# Contract caps total browser_* actions at 20 per skill. With the dispatcher
# orchestrating crawler + analyst, ~150 turns is a comfortable ceiling.
HERMES_MAX_ITERATIONS=150
ENVEOF

echo "[entrypoint] Credentials written."

# --- crawl webhook → funnel-crawler only (for isolated testing) ---
echo "[entrypoint] Registering crawl webhook subscription..."
hermes webhook subscribe crawl \
  --secret "${WEBHOOK_SECRET}" \
  --prompt "A funnel crawl has been requested (crawler only, no analyst).

run_id: {run_id}
url: {url}
callback_url: {callback_url}

Load the funnel-crawler skill and execute it exactly as written. Do not
deviate from the contract in funnel-crawler.md. Work in
\${CRAWL_OUTPUT_DIR}/{run_id}. If callback_url is empty, do not POST." \
  --events "crawl_requested" \
  --skills "funnel-crawler" \
  --description "Run the funnel-crawler skill in isolation (no analysis stage)" \
  2>&1 || echo "[entrypoint] crawl: already registered"

# --- audit webhook → audit-dispatcher → funnel-crawler + cro-analyst ---
echo "[entrypoint] Registering audit webhook subscription..."
hermes webhook subscribe audit \
  --secret "${WEBHOOK_SECRET}" \
  --prompt "A CRO audit has been requested.

run_id: {run_id}
url: {url}
callback_url: {callback_url}

Load the audit-dispatcher skill and execute it exactly as written. Do not
deviate from the contract in audit-dispatcher.md. Work in
\${CRAWL_OUTPUT_DIR}/{run_id}." \
  --events "audit_requested" \
  --skills "audit-dispatcher,funnel-crawler,cro-analyst" \
  --description "Run the full CRO audit pipeline: crawl funnel + analyze + POST report" \
  2>&1 || echo "[entrypoint] audit: already registered"

# --- feedback webhook → feedback-processor ---
echo "[entrypoint] Registering feedback webhook subscription..."
hermes webhook subscribe feedback \
  --secret "${WEBHOOK_SECRET}" \
  --prompt "Test feedback has been received.

run_id: {run_id}
liked_test_ids: {liked_test_ids}
callback_url: {callback_url}

Load the feedback-processor skill and execute it exactly as written.
Generate implementation briefs for the liked tests and POST to
{callback_url}." \
  --events "feedback_received" \
  --skills "feedback-processor" \
  --description "Generate implementation briefs for tests the user liked" \
  2>&1 || echo "[entrypoint] feedback: already registered"

# Hermes' `hermes webhook subscribe --secret` is silently ignored — the CLI
# auto-generates a fresh HMAC secret per subscription. Patch the stored
# subscriptions file so each route uses the shared WEBHOOK_SECRET.
python3 - <<PY
import json, os
path = "/root/.hermes/webhook_subscriptions.json"
secret = os.environ["WEBHOOK_SECRET"]
with open(path) as f:
    subs = json.load(f)
for name in subs:
    subs[name]["secret"] = secret
with open(path, "w") as f:
    json.dump(subs, f, indent=2)
print(f"[entrypoint] Patched {len(subs)} subscription secret(s) to WEBHOOK_SECRET.")
PY

echo "[entrypoint] Starting Hermes gateway on 127.0.0.1:${HERMES_INTERNAL_PORT} (internal)..."
hermes gateway run &
HERMES_PID=$!

trap "kill -TERM ${HERMES_PID} 2>/dev/null; exit 0" SIGTERM SIGINT

echo "[entrypoint] Starting /api proxy on 0.0.0.0:${WEBHOOK_PORT}..."
exec python3 /proxy.py
