---
name: cro-analyst
description: Read crawl.json + screenshots, write report.json with exactly 5 A/B test hypotheses.
tags: [analysis, cro, contract]
---

# CRO Analyst

> **This file is the contract. Do not edit it from inside a run.**

## Contract (immutable)

1. **Input:** `${CRAWL_OUTPUT_DIR}/{run_id}/crawl.json` + the screenshots
   it references in the same directory (variable count, 1..25).
2. **Output:** `${CRAWL_OUTPUT_DIR}/{run_id}/report.json` — schema below,
   fixed.
3. **Exactly 5 tests**, ids `test-001` through `test-005`. Not 4, not 6.
4. **Status starts as `awaiting_feedback`**.
5. Always write `report.json` and POST to `{callback_url}` — even if a
   screenshot is missing or `checkout.reached=false`. Note gaps in the
   report rather than failing silently.

## Inputs

- `{run_id}` — directory key under `${CRAWL_OUTPUT_DIR}`
- `{callback_url}` — POST `report.json` here when finished

## Output schema — `${CRAWL_OUTPUT_DIR}/{run_id}/report.json`

```json
{
  "run_id": "",
  "url": "",
  "crawled_at": "",
  "status": "awaiting_feedback",
  "funnel_summary": {
    "step_count": 0,
    "email_gate_present": true,
    "pricing_tiers": 0,
    "urgency_present": true,
    "guarantee_present": true,
    "post_purchase_upsell": false,
    "annual_plan_option": false,
    "checkout_reached": true
  },
  "pricing_analysis": {
    "current_plans": [],
    "recommended_change": ""
  },
  "tests": [
    {
      "id": "test-001",
      "priority": "P0",
      "page_location": "",
      "hypothesis": "",
      "control": "",
      "variant": "",
      "primary_metric": "",
      "secondary_metric": "",
      "effort": "low",
      "expected_impact": "",
      "implementation_notes": ""
    }
  ],
  "screenshots": []
}
```

Fields are fixed. `priority` ∈ {P0, P1, P2}. `effort` ∈ {low, medium, high}.

## Procedure

1. Read `${CRAWL_OUTPUT_DIR}/{run_id}/crawl.json`.
2. For each entry in `funnel_steps`, open its `screenshot` file (use the
   vision-enabled file reader, not `browser_vision`). Build a mental
   model of the funnel from these.
3. Identify the four landmark steps by **name** in `funnel_steps`:
   - `landing`
   - `email-gate` (may be absent — set `email_gate_present` accordingly)
   - `plan-reveal`
   - `checkout`
   Everything between landing → email-gate is the quiz; between
   email-gate → plan-reveal is the results/summary section.
4. Derive `funnel_summary`:
   - `step_count` = `len(funnel_steps)`.
   - `email_gate_present` = any step has `name == "email-gate"` with a
     non-empty `screenshot`.
   - `pricing_tiers` = `len(checkout.plans)`.
   - `urgency_present` = `checkout.urgency_tactics` non-empty.
   - `guarantee_present` = any `checkout.trust_signals` mentions
     refund / guarantee / money-back.
   - `checkout_reached` = `checkout.reached`.
   - `post_purchase_upsell` / `annual_plan_option` — inferred from
     screenshots; default `false` if unclear.
5. Build `pricing_analysis.current_plans` from `checkout.plans`. Write a
   one-sentence `recommended_change`.
6. Produce **exactly 5 tests** covering distinct surfaces — e.g. hero
   CTA, quiz friction, email gate, pricing layout, checkout urgency.
   Assign ids `test-001` .. `test-005`. Each test must have every field
   populated; empty strings only where a value genuinely doesn't apply.
7. Populate `screenshots` with ALL screenshot filenames from
   `crawl.json.funnel_steps` (no path prefix; same dir as report.json).
8. Write `report.json`.
9. `POST {callback_url}` with the body of `report.json`.

## On missing inputs

- Missing `crawl.json`: write a minimal `report.json` with
  `status="awaiting_feedback"`, empty `tests` array of 5 stubs, and POST.
- Missing screenshots: proceed with what you can see; note the gap in
  affected test `implementation_notes`.
- Never block on missing inputs. Always emit a report.

## After the run

Do **not** edit this skill file, `funnel-crawler.md`, or
`audit-dispatcher.md`. Insights about CRO patterns can go in a new
section of `/workspace/patterns.md` if (and only if) they will help
**navigation** in future crawls.
