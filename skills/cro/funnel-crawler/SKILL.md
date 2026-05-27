---

## name: funnel-crawler description: Walk a funnel entry → checkout. One screenshot per visually distinct step. Write crawl.json. Tactics live in /workspace/patterns.md. tags: \[browser, screenshots, funnel, contract\]

# Funnel Crawler

> **Contract file. Do not edit it from inside a run.** Tactics evolve in `/workspace/patterns.md` (agent-writable). Heuristic scripts live in `/workspace/archetypes/` and `/workspace/extensions/` (agent-writable).

## Step 0 — pick your execution path

Extract `{domain}` from `{url}` (hostname only, e.g. `perfectbody.me`).

Check in order — use the **first** that applies:

### A. Domain extension exists (fastest)
```bash
ls /workspace/extensions/{domain}.py
```
If found:
```bash
python /workspace/extensions/{domain}.py \
  --url "{url}" --run_id "{run_id}" --output_dir "${CRAWL_OUTPUT_DIR}/{run_id}"
```
Verify `crawl.json` was written. If yes → jump to **Always emit crawl.json**. If the script errored → fall through to B.

### B. Known archetype match (fast)
Check `/workspace/patterns.md` archetypes section. Take one `browser_snapshot` of the landing page to confirm the fingerprint. If a match with confidence > 0 is found:
```bash
python /workspace/archetypes/{archetype}.py \
  --url "{url}" --run_id "{run_id}" --output_dir "${CRAWL_OUTPUT_DIR}/{run_id}"
```
Watch for steps that fail. Handle them manually, then **write a domain extension** capturing the delta before finishing.

### C. Full manual crawl (slow — only when A and B don't apply)

Read `/workspace/patterns.md` end-to-end before the first browser action.

1. `mkdir -p "${CRAWL_OUTPUT_DIR}/{run_id}"`
2. `browser_navigate` to `{url}`
3. Accept cookie banner (always first — see `cookie-banner-blocks-interaction`)
4. Follow the primary path to checkout. Defaults:
   - Age 30-39 · Goal: Lose weight · Body: Plump · Activity: Desk job
   - Height 5ft6 · Weight 165lbs · Target 140lbs · Numeric age 35
   - Email `qa+123@kilo.health` (fallback `qa123@kilo.health` if + rejected)
   - Name `Auditor`
5. Navigation only: `browser_snapshot` + `browser_click`. Never `browser_vision` for navigation.
6. Stuck? Check `patterns.md` first — the fix is probably already there.
7. Budget: ≤ 80 `browser_navigate`/`browser_click`/`browser_type` actions total.

Screenshots (use `browser_vision` + run `[[readiness-gate]]` from patterns.md first):

| Landmark | Filename |
|----------|----------|
| Landing page | `01-landing.png` |
| First quiz/entry screen | `02-quiz-entry.png` |
| Email gate | `03-email-gate.png` |
| Plan reveal / forecast | `04-plan-reveal.png` |
| Checkout / pricing | `05-checkout.png` |
| Post-purchase upsell (if present) | `06-upsell.png` |

`cp {screenshot_path} "${CRAWL_OUTPUT_DIR}/{run_id}/{filename}"` after each `browser_vision`.

After a successful manual crawl, **always write a domain extension**:
```
/workspace/extensions/{domain}.py
```
Import the closest archetype base class. Override only the steps that differed. Keep it under 100 lines.

## What you're producing

Capturing up to 50 unique user-journey defining screenshots from a given URL. Produce:

- `crawl.json` describing the walk (schema below).
- Screenshots of each page

Both land in `${CRAWL_OUTPUT_DIR}/{run_id}/`.

## Budget

| Resource | Limit |
| --- | --- |
| `browser_vision` | one per visually distinct step — no upper cap |
| `browser_navigate` + `browser_click` + `browser_type` | ≤ 80 combined |
| `browser_snapshot`, `browser_console` | unbounded |
| Wall-clock target | < 5 min |

If you exhaust the navigate/click/type budget or the wall-clock target, write whatever `crawl.json` you have and stop.

## Screenshot Definition of Done

A screenshot is a defect unless ALL of these hold:

- Full page, not viewport-only.
- All images loaded and decoded (no placeholders / LQIPs / broken icons).
- No skeleton loaders, spinners, or "loading…" text visible.
- No mid-flight animations (carousels mid-rotate, count-ups mid-tick).
- Layout stable — no further reflow.

Crawler should capture the loaders and other stuff as insight (what happened after I clicked X, etc.).

How you verify these is up to you. `/workspace/patterns.md` has a known-working readiness gate (\[\[readiness-gate\]\]) you can use or improve.

## Tools at your disposal

You have the full Hermes toolset. The ones that matter here, and when:

| Tool | When to reach for it |
| --- | --- |
| `browser_snapshot` | Read the page DOM. Cheap; use freely. Refs from a snapshot go stale after any DOM-mutating action — re-snapshot before each interaction. |
| `browser_click` / `browser_type` | Single interactions. |
| `browser_console` | Run JS — readiness gate, content extraction, force-clicks (DOM-direct, `MouseEvent` dispatch). |
| `browser_scroll` | Built-in scroll. Prefer over `window.scrollTo` JS where possible. |
| `browser_get_images` | Inventory page images without DIY JS. |
| `browser_vision` | Screenshots **only**. Each call also spends a hidden LLM turn on visual analysis you don't need — keep it for screenshot moments. |
| `delegate_task` | Up to 3 parallel subagents. Useful for splitting independent work; rarely helpful for a single linear funnel walk. |
| `execute_code` | **Does NOT expose** `browser_*` **tools.** Sandbox allow-list is `web_search`, `web_extract`, `read_file`, `write_file`, `search_files`, `patch`, `terminal`. 300s sandbox timeout. Use it for post-walk processing — e.g. assembling `crawl.json` from a list of step records, or batch-extracting plan data from saved HTML. Don't use it to walk the funnel. |
| `write_file` | The way crawl.json reaches disk. Calling it is mandatory. Don't paste JSON into chat as a substitute. |
| `terminal` | Run heuristic scripts: `python /workspace/extensions/{domain}.py ...` or `python /workspace/archetypes/{archetype}.py ...` |

**Try to be as fast as possible. Look for ways to advance in the user journey and find all terminal pages (register/login/payments/signup forms). Ideally we find all, but if not, signup + payments is good enough for most ecommerce websites.**

## Test credentials

Email gates: use `qa+123@kilo.health`. Fallback `qa123@kilo.health` if the funnel rejects `+`. Never use placeholder addresses.

## Output schema — `${CRAWL_OUTPUT_DIR}/{run_id}/crawl.json`

```json
{
  "run_id": "",
  "url": "",
  "crawled_at": "",
  "funnel_steps": [
    {"step": 1, "name": "landing",         "screenshot": "01-landing.png"},
    {"step": 2, "name": "quiz-q1-goals",   "screenshot": "02-quiz-q1-goals.png"},
    {"step": 3, "name": "quiz-q2-veggies", "screenshot": "03-quiz-q2-veggies.png"}
  ],
  "checkout": {
    "reached": true,
    "plans": [{"name":"","original_price":"","sale_price":"","per_day_price":"","billing_period":"","badge":""}],
    "urgency_tactics": [],
    "trust_signals": [],
    "cta_text": "",
    "fine_print": ""
  }
}
```

Field names are fixed. `funnel_steps` is variable length — one entry per visually distinct step the crawler encountered. Step number is the 1-based index; screenshot filename uses the same 2-digit prefix (`01-`, `02-`, …) + the step's `name`.

## Always emit crawl.json

This is mandatory — the run is a failure if `crawl.json` isn't on disk.

- Use the `write_file` tool. Path: `${CRAWL_OUTPUT_DIR}/{run_id}/crawl.json`. Pasting the JSON into a chat message is **not** writing the file.
- Write it even on timeout, budget exhaustion, or any failure — with whatever steps you completed. Set `checkout.reached = false` if you didn't get there.
- Reserve budget for this. Plan to call `write_file` while you still have headroom; don't let it slip behind a wall of last-minute clicks.
- If `{callback_url}` is non-empty, POST the file body to it after writing. Otherwise skip the POST.

## After the run

Read `/workspace/patterns.md` first. Append new transferable patterns after. Confirm existing entries that helped (bump confidence). The patterns.md preamble has the rules on what belongs and what doesn't.

Never edit this file or anything under `skills/cro/`.

## Inputs

- `{url}` — entry URL
- `{run_id}` — output dir key
- `{callback_url}` — POST `crawl.json` here (may be empty)
