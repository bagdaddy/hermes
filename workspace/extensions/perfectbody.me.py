"""
Extension: perfectbody.me
Archetype: quiz-funnel

Only overrides what actually differs from the generic loop.
Generated after first manual crawl. Update when the site changes.
"""

import sys, time, json
sys.path.insert(0, "/workspace/archetypes")

from quiz_funnel import QuizFunnelCrawler, EMAIL_FB
from selenium.webdriver.common.by import By


class PerfectBodyCrawler(QuizFunnelCrawler):

    def classify(self, dom):
        # Ingredients page: has checkboxes but Continue is not disabled
        # — base would call it unknown. Override to catch it.
        if "ingredient" in dom["url"].lower() or "ingredient" in dom["text"].lower():
            return "ingredients"
        return None  # fall through to base classify

    def act(self, stype):
        if stype == "email-gate":
            # perfectbody rejects + in email addresses
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='email']")
            if inputs:
                self._fill(inputs[0], EMAIL_FB)
            self._check_any_checkbox()
            self._advance()
            return True

        if stype == "ingredients":
            # "Select everything" checkbox at top
            self._js("document.querySelector('input[type=checkbox]')?.click()")
            self._advance()
            return True

        return False  # everything else handled by base


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--url",        required=True)
    ap.add_argument("--run_id",     required=True)
    ap.add_argument("--output_dir", required=True)
    args = ap.parse_args()
    PerfectBodyCrawler(args.url, args.run_id, args.output_dir).run()
