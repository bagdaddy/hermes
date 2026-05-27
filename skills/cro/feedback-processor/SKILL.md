---
name: feedback-processor
description: Generate implementation briefs for tests the user marked as liked.
tags: [feedback, cro, contract]
---

# Feedback Processor

> **This file is the contract. Do not edit it from inside a run.**

## Contract (immutable)

1. **Input:** `{run_id}` + `{liked_test_ids}` (array of ids from
   `report.json`, e.g. `["test-001", "test-003"]`).
2. **Output:** `${CRAWL_OUTPUT_DIR}/{run_id}/briefs.json` — schema fixed.
3. **One brief per liked test.** Order matches input order.
4. Always write `briefs.json` and POST to `{callback_url}` — even if some
   tests couldn't be processed. Mark gaps inline.

## Inputs

- `{run_id}` — directory key under `${CRAWL_OUTPUT_DIR}`
- `{liked_test_ids}` — JSON array of test ids
- `{callback_url}` — POST `briefs.json` here when finished

## Output schema — `${CRAWL_OUTPUT_DIR}/{run_id}/briefs.json`

```json
{
  "run_id": "",
  "generated_at": "",
  "briefs": [
    {
      "test_id": "",
      "title": "",
      "summary": "",
      "implementation_steps": [],
      "code_pointers": [],
      "acceptance_criteria": [],
      "tracking_events": [],
      "rollout_plan": "",
      "estimated_effort_hours": 0
    }
  ]
}
```

Fields are fixed. `estimated_effort_hours` is an integer.

## Procedure

1. Read `${CRAWL_OUTPUT_DIR}/{run_id}/report.json`.
2. For each id in `{liked_test_ids}`:
   - Find the test in `report.json.tests`.
   - If not found: emit a brief with that `test_id`, empty fields, and
     `summary="test id not found in report"`.
   - Otherwise: generate `implementation_steps`, `code_pointers`,
     `acceptance_criteria`, `tracking_events`, `rollout_plan`, and an
     integer `estimated_effort_hours` from the test's `control`,
     `variant`, `implementation_notes`, and `effort` fields.
3. Write `briefs.json` in the order of `{liked_test_ids}`.
4. `POST {callback_url}` with the body of `briefs.json`.

## On missing inputs

- Missing `report.json`: write a `briefs.json` with one empty brief per
  liked id and `summary="no report.json found for this run"`. POST anyway.

## After the run

Do **not** edit this skill file or anything under `skills/cro/`.
