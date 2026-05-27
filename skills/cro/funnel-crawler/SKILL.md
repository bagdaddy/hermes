---
name: funnel-crawler
description: Crawl a website funnel and screenshot every step of the user journey.
tags: [browser, screenshots, funnel]
---

# Funnel Crawler

Crawl `{url}` and screenshot every step of the user journey toward signup or purchase.

1. Navigate to `{url}`
2. Accept any cookie banner first
3. Follow the path a real user would take to sign up or make a purchase
4. Take a `browser_vision` screenshot after every single action — every click, every type, every page load. No exceptions.
5. Save every screenshot to `${CRAWL_OUTPUT_DIR}/{run_id}/` numbered sequentially: `01-...png`, `02-...png`, etc.
6. Keep going until you hit a payment form, order confirmation, or account creation screen

Read `/workspace/patterns.md` before starting — it has fixes for common navigation problems.

Defaults for any form: age 30-39, email `qa+123@kilo.health` (fallback `qa123@kilo.health`), name Auditor, height 5ft6, weight 165lbs.
