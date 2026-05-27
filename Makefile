IMAGE   = hermes-cro-agent
COMPOSE = docker compose

.PHONY: help build up down logs logs-session shell crawl audit clean

help:
	@echo ""
	@echo "  make build         Build the Docker image"
	@echo "  make up            Start the container (detached)"
	@echo "  make down          Stop and remove the container"
	@echo "  make logs          Tail container logs"
	@echo "  make shell         Open a shell inside the running container"
	@echo "  make crawl URL=... Fire a crawl request (default: perfectbody.me/v2)"
	@echo "  make clean         Remove image + crawl output"
	@echo ""

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d
	@echo "Gateway starting at http://localhost:$${WEBHOOK_PORT:-8644}"
	@sleep 5
	@curl -sf http://localhost:$${WEBHOOK_PORT:-8644}/health && echo " ✓ Gateway is up" || echo " ✗ Not ready yet — try: make logs"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

# Dump the most recent agent session as a readable timeline of tool calls.
logs-session:
	@python3 scripts/dump-session.py

shell:
	$(COMPOSE) exec hermes-cro /bin/bash

# Fire crawler-only run (no analyst). Use for isolated crawler testing.
crawl:
	@RUN_ID=$$(openssl rand -hex 8); \
	URL=$${URL:-https://perfectbody.me/v2}; \
	CALLBACK_URL=$${CALLBACK_URL:-}; \
	PORT=$${WEBHOOK_PORT:-8644}; \
	SECRET=$$(grep WEBHOOK_SECRET .env | cut -d= -f2); \
	PAYLOAD="{\"event_type\":\"crawl_requested\",\"run_id\":\"$$RUN_ID\",\"url\":\"$$URL\",\"callback_url\":\"$$CALLBACK_URL\"}"; \
	SIG=$$(printf '%s' "$$PAYLOAD" | openssl dgst -sha256 -hmac "$$SECRET" | sed 's/.*= //'); \
	echo "Sending crawl — run_id=$$RUN_ID url=$$URL callback=$$CALLBACK_URL"; \
	curl -s -X POST "http://localhost:$$PORT/api/crawl" \
	  -H "Content-Type: application/json" \
	  -H "X-Webhook-Signature: $$SIG" \
	  -d "$$PAYLOAD"; \
	echo ""; \
	echo "run_id=$$RUN_ID — results will land in ./crawls/$$RUN_ID/"

# Fire full CRO audit (crawler → analyst). Sends final report.json to CALLBACK_URL.
audit:
	@RUN_ID=$$(openssl rand -hex 8); \
	URL=$${URL:-https://perfectbody.me/v2}; \
	CALLBACK_URL=$${CALLBACK_URL:-}; \
	PORT=$${WEBHOOK_PORT:-8644}; \
	SECRET=$$(grep WEBHOOK_SECRET .env | cut -d= -f2); \
	PAYLOAD="{\"event_type\":\"audit_requested\",\"run_id\":\"$$RUN_ID\",\"url\":\"$$URL\",\"callback_url\":\"$$CALLBACK_URL\"}"; \
	SIG=$$(printf '%s' "$$PAYLOAD" | openssl dgst -sha256 -hmac "$$SECRET" | sed 's/.*= //'); \
	echo "Sending audit — run_id=$$RUN_ID url=$$URL callback=$$CALLBACK_URL"; \
	curl -s -X POST "http://localhost:$$PORT/api/audit" \
	  -H "Content-Type: application/json" \
	  -H "X-Webhook-Signature: $$SIG" \
	  -d "$$PAYLOAD"; \
	echo ""; \
	echo "run_id=$$RUN_ID — results will land in ./crawls/$$RUN_ID/"

clean:
	$(COMPOSE) down --rmi local
	rm -rf crawls/*
