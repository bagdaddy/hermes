"""
Extension: perfectbody.me
Archetype: quiz-funnel

Overrides only the steps that differ from the base.
Generated after first manual crawl. Update when the site changes.
"""

import sys, time, json
sys.path.insert(0, "/workspace/archetypes")

from quiz_funnel import QuizFunnelCrawler
from selenium.webdriver.common.by import By


class PerfectBodyCrawler(QuizFunnelCrawler):

    # perfectbody rejects + in email addresses
    EMAIL = "qa123@kilo.health"

    def step_entry(self):
        # Photo card buttons — click Female card directly
        self._click_text(["Female"])

    def step_target_areas(self):
        # Multi-select body diagram — DOM-direct click on first checkbox then advance
        self._js("document.querySelectorAll('input[type=checkbox]')[0]?.click()")
        self._continue()

    def step_habits(self):
        # Inner checkbox DOM click required — wrapper click doesn't register in React
        self._js("document.querySelectorAll('input[type=checkbox]')[0]?.click()")
        self._continue()

    def step_ingredients(self):
        # "Select everything" toggle at top of ingredient list
        self._click_text(["Select everything"])
        self._continue()

    def step_email_gate(self):
        self.screenshot("email-gate")
        self._fill_email(self.EMAIL)
        self._js("document.querySelector('input[type=checkbox]')?.click()")
        self._continue()

    def step_plan_reveal(self):
        # Two informational inserts appear before the actual plan reveal
        for _ in range(3):
            url_before = self.driver.current_url
            self._continue()
            time.sleep(0.3)
        self.screenshot("plan-reveal")
        self._continue()

    def step_checkout(self):
        self.screenshot("checkout")
        # Extract plan data while we're here
        try:
            plans_raw = self._js("""
                return Array.from(document.querySelectorAll('[class*="plan" i],[class*="Plan"]'))
                    .map(el => el.innerText.trim())
                    .filter(t => t.length > 5)
                    .slice(0, 6)
            """)
            if plans_raw:
                self._write_checkout_plans(plans_raw)
        except Exception:
            pass

    def _write_checkout_plans(self, raw):
        import re
        out_path = self.out / "crawl.json"
        if not out_path.exists():
            return
        data = json.loads(out_path.read_text())
        # Store raw text — the analyst will parse it
        data["checkout"]["plans_raw"] = raw
        out_path.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--url",        required=True)
    ap.add_argument("--run_id",     required=True)
    ap.add_argument("--output_dir", required=True)
    args = ap.parse_args()
    PerfectBodyCrawler(args.url, args.run_id, args.output_dir).run()
