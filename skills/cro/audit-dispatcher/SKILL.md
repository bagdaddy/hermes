---
name: audit-dispatcher
description: Orchestrate a full CRO audit — run funnel-crawler, then cro-analyst, then POST final report.
tags: [orchestration, contract]
---

# Audit Dispatcher

> **This file is the contract. Do not edit it from inside a run.**

## Contract (immutable)

1. **Run order:** `funnel-crawler` → `cro-analyst`. Always both. Always in
   that order. Never one without the other.
2. **Each downstream skill is invoked exactly once per audit run.** No
   retries from this orchestrator — the downstream skills handle their
   own partial-success outputs.
3. **Always POST to `{callback_url}` at the end**, even if the crawler
   timed out or the analyst couldn't read screenshots. The POST body is
   the contents of `report.json` (the final, schema-conformant output).
4. **Do not touch `crawl.json` or `report.json` directly.** Each
   downstream skill writes its own file. Dispatcher only reads.

## Inputs

- `{run_id}` — directory key under `${CRAWL_OUTPUT_DIR}`
- `{url}` — entry URL for the audit
- `{callback_url}` — final POST target

## Procedure

1. `mkdir -p ${CRAWL_OUTPUT_DIR}/{run_id}`.
2. Invoke the `funnel-crawler` skill with `{url}`, `{run_id}`,
   `callback_url=""` (suppress crawler's own POST — dispatcher owns the
   external callback).
3. Wait for `${CRAWL_OUTPUT_DIR}/{run_id}/crawl.json` to exist.
4. Invoke the `cro-analyst` skill with `{run_id}`, `callback_url=""`.
5. Wait for `${CRAWL_OUTPUT_DIR}/{run_id}/report.json` to exist.
6. `POST {callback_url}` with the body of `report.json`.

## On downstream failure

- `crawl.json` never appears (crawler hung / killed): write a stub
  `crawl.json` with `checkout.reached=false` and empty `funnel_steps`,
  then continue to step 4 so the analyst still produces a report.
- `report.json` never appears: write a minimal `report.json` with
  `status="awaiting_feedback"` and 5 placeholder tests, then POST.
- Time budget for the full pipeline: **5 minutes**. If exceeded, POST
  whatever exists.

## After the run

Do **not** edit this skill file or anything under `skills/cro/`.
