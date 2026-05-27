---
name: funnel-crawler
description: Walk a website funnel to signup or purchase. Screenshot every distinct step. Write crawl.json.
tags: [browser, screenshots, funnel, contract]
---

# Funnel Crawler

> Contract file. Do not edit from inside a run. Navigation tactics in `/workspace/patterns.md`.

## Goal

Walk the user journey from `{url}` to the first **signup or purchase completion** screen you can reach. Screenshot every distinct step along the way.

You are looking for two terminal destinations in priority order:
1. **Purchase** — payment form, plan selection, checkout, order confirmation
2. **Signup** — account creation form, email+password, registration confirmation

Stop when you reach one. If neither is reachable (auth wall, bot block, out of budget), stop and write what you have.

## Before you start

Read `/workspace/patterns.md`. The navigation fixes are there — do not rediscover them.

## How to navigate

- `browser_snapshot` + `browser_click` for all navigation. Never `browser_vision` for navigation.
- Accept cookie banner before anything else.
- At every choice, pick the most common/default option and keep moving. Don't explore branches.
- Stuck? Check `patterns.md` before trying anything else.
- Budget: ≤ 80 `browser_navigate` + `browser_click` + `browser_type` combined. If exhausted, write what you have and stop.

**Defaults for any form fields:**
- Age: 30-39
- Goal: Lose weight / most prominent option
- Body type: middle option
- Activity: Desk job / sedentary
- Height: 5ft6 / 168cm
- Weight: 165lbs / 75kg
- Target weight: 140lbs / 63kg
- Numeric age: 35
- Email: `qa+123@kilo.health` (fallback: `qa123@kilo.health` if + rejected)
- Name: Auditor
- Password: Auditor123!

## Screenshots

Take a screenshot after **every distinct screen** — a screen is distinct when the URL or main heading changes.

Run the `[[readiness-gate]]` from patterns.md before each screenshot. If not ready after one retry, screenshot anyway.

Filename: `{N:02d}-{heading-slug}.png` where N is 1-based and the slug is the main heading lowercased with spaces replaced by hyphens. If no heading, use the URL path segment.

Copy each screenshot immediately: `cp {screenshot_path} "${CRAWL_OUTPUT_DIR}/{run_id}/{filename}"`

## Output schema

Write `${CRAWL_OUTPUT_DIR}/{run_id}/crawl.json` using `write_file`:

```json
{
  "run_id": "",
  "url": "",
  "crawled_at": "",
  "funnel_type": "purchase | signup | unknown",
  "funnel_steps": [
    {
      "step": 1,
      "name": "heading-slug",
      "url": "",
      "screenshot": "01-heading-slug.png"
    }
  ],
  "terminal": {
    "reached": true,
    "type": "purchase | signup | none",
    "url": "",
    "screenshot": ""
  },
  "checkout": {
    "reached": true,
    "plans": [{"name": "", "original_price": "", "sale_price": "", "per_day_price": "", "billing_period": "", "badge": ""}],
    "urgency_tactics": [],
    "trust_signals": [],
    "cta_text": "",
    "fine_print": ""
  }
}
```

**This file is mandatory.** Write it even on failure with whatever steps completed. Set `terminal.reached = false` and `checkout.reached = false` if not reached.

If `{callback_url}` is non-empty, POST the file after writing.

## After the run

Append any new navigation patterns to `/workspace/patterns.md`. Only cross-site tactics — nothing site-specific.

## Inputs

- `{url}` — entry URL
- `{run_id}` — output dir key
- `{callback_url}` — POST crawl.json here (may be empty)
