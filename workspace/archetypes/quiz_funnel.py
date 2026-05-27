"""
quiz-funnel archetype base crawler.

Generic loop — classify each screen, act, repeat.
No hardcoded steps. No site-specific knowledge.
That lives in patterns.md and extensions.

Usage:
  python /workspace/archetypes/quiz_funnel.py \
    --url https://example.com \
    --run_id abc123 \
    --output_dir /crawls/abc123
"""

import argparse, json, time, re
from datetime import datetime, timezone
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


EMAIL    = "qa+123@kilo.health"
EMAIL_FB = "qa123@kilo.health"

# Landmark screen names — when we see one, we take a screenshot
LANDMARKS = {"landing", "email-gate", "plan-reveal", "checkout", "upsell"}


class QuizFunnelCrawler:
    """
    Crawls a quiz-style funnel by classifying each screen and acting.
    No hardcoded step sequence. Discovers the funnel at runtime.

    Subclasses may override:
      - classify(dom)     → return screen type or None to use base logic
      - act(screen_type)  → return False to fall back to base action
      - is_done()         → return True to stop early (e.g. reached checkout)
    """

    BUDGET   = 80     # max selenium actions
    MAX_SAME = 5      # stop if URL unchanged after this many consecutive advances

    def __init__(self, url, run_id, output_dir):
        self.url        = url
        self.run_id     = run_id
        self.out        = Path(output_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.steps      = []
        self.actions    = 0
        self.driver     = None
        self._t_start   = None
        self._t_step    = None
        self._seen_urls = []   # recent URL history for stuck detection

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self):
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1280,800")
        self.driver  = webdriver.Chrome(options=opts)
        self._t_start = time.monotonic()
        try:
            self._crawl()
        except _BudgetExhausted:
            print(f"[crawler] budget exhausted after {self.actions} actions")
        except _StuckDetected:
            print(f"[crawler] stuck — URL unchanged {self.MAX_SAME} times, stopping")
        except Exception as e:
            print(f"[crawler] error: {e}")
        finally:
            self._write_output()
            self.driver.quit()

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    def _crawl(self):
        self._goto(self.url)
        self._accept_cookies()
        self._screenshot_if_landmark("landing")

        while not self._is_terminal():
            dom   = self._dom_signals()
            stype = self.classify(dom) or self._base_classify(dom)
            acted = self.act(stype) if stype else False
            if not acted:
                self._base_act(stype, dom)
            self._screenshot_if_landmark(stype)
            self._check_stuck()

    # ------------------------------------------------------------------
    # Classification — what kind of screen is this?
    # Subclasses override classify() to intercept before base logic.
    # ------------------------------------------------------------------

    def classify(self, dom):
        """Override to return a screen type string, or None to use base."""
        return None

    def _base_classify(self, dom):
        text = dom["text"].lower()
        url  = dom["url"].lower()

        if any(x in url for x in ["/checkout", "/pricing", "/plans", "/order"]):
            return "checkout"
        if any(x in url for x in ["/upsell", "/upgrade", "/offer"]):
            return "upsell"
        if dom["has_email_input"]:
            return "email-gate"
        if dom["has_payment_input"]:
            return "payment-form"
        if any(x in text for x in ["your plan", "your weight", "you will reach", "by ", "lbs by", "kg by"]):
            return "plan-reveal"
        if dom["has_numeric_inputs"] and not dom["has_text_inputs"]:
            return "numeric-input"
        if dom["has_checkboxes"] and dom["continue_disabled"]:
            return "multi-select"
        if dom["has_photo_cards"]:
            return "photo-card-select"
        if dom["has_radio_or_option_list"] and not dom["has_checkboxes"]:
            return "single-select"
        if dom["has_continue"] and not dom["has_inputs"]:
            return "informational"
        if dom["has_name_input"]:
            return "name-input"
        return "unknown"

    # ------------------------------------------------------------------
    # Actions — what to do for each screen type
    # Subclasses override act() to intercept before base logic.
    # ------------------------------------------------------------------

    def act(self, stype):
        """Override to handle a screen type. Return True if handled, False to fall back."""
        return False

    def _base_act(self, stype, dom):
        if stype == "photo-card-select":
            # Click the first card — sensible default for gender/age/body-type
            self._click_first_card()

        elif stype == "single-select":
            # Click the first option
            self._click_first_option()

        elif stype == "multi-select":
            # Select first checkbox then advance
            self._js("document.querySelectorAll('input[type=checkbox]')[0]?.click()")
            self._advance()

        elif stype == "numeric-input":
            self._fill_numeric_defaults(dom)
            self._advance()

        elif stype == "email-gate":
            self._fill_email()
            self._check_any_checkbox()
            self._advance()

        elif stype == "name-input":
            inputs = self.driver.find_elements(By.CSS_SELECTOR,
                "input[name='name'],input[placeholder*='name' i]")
            if inputs:
                self._fill(inputs[0], "Auditor")
            self._advance()

        elif stype in ("informational", "plan-reveal"):
            self._advance()

        elif stype == "checkout":
            pass  # terminal — stop looping

        elif stype == "payment-form":
            pass  # terminal

        else:
            # Unknown — try advancing and see what happens
            self._advance()

    # ------------------------------------------------------------------
    # Terminal condition
    # ------------------------------------------------------------------

    def _is_terminal(self):
        if self.is_done():
            return True
        url = self.driver.current_url.lower()
        return any(x in url for x in ["/checkout", "/payment", "/upsell", "/order", "/plans"])

    def is_done(self):
        """Override to add custom terminal conditions."""
        return False

    # ------------------------------------------------------------------
    # Landmark screenshots
    # ------------------------------------------------------------------

    def _screenshot_if_landmark(self, stype):
        if stype not in LANDMARKS:
            return
        # Don't double-screenshot the same landmark
        if any(s["name"] == stype for s in self.steps):
            return
        self._screenshot(stype)

    def _screenshot(self, name):
        now  = time.monotonic()
        elapsed  = round(now - self._t_start, 2)
        step_took = round(now - self._t_step, 2) if self._t_step else elapsed
        self._t_step = now

        n     = len(self.steps) + 1
        fname = f"{n:02d}-{name}.png"
        self.driver.save_screenshot(str(self.out / fname))
        self.steps.append({
            "step":        n,
            "name":        name,
            "url":         self.driver.current_url,
            "screenshot":  fname,
            "elapsed_s":   elapsed,
            "step_took_s": step_took,
            "actions_so_far": self.actions,
        })
        print(f"  [{n:02d}] {name} | +{step_took}s | total {elapsed}s | {self.actions} actions")

    # ------------------------------------------------------------------
    # DOM signals — cheap signals for classification
    # ------------------------------------------------------------------

    def _dom_signals(self):
        url  = self.driver.current_url
        text = self.driver.find_element(By.TAG_NAME, "body").text
        return {
            "url":                  url,
            "text":                 text[:2000],
            "has_email_input":      bool(self.driver.find_elements(By.CSS_SELECTOR, "input[type='email']")),
            "has_payment_input":    bool(self.driver.find_elements(By.CSS_SELECTOR, "input[name*='card'],input[name*='number'],iframe[name*='stripe']")),
            "has_name_input":       bool(self.driver.find_elements(By.CSS_SELECTOR, "input[name='name'],input[placeholder*='name' i]")),
            "has_numeric_inputs":   bool(self.driver.find_elements(By.CSS_SELECTOR, "input[type='number'],[role='spinbutton']")),
            "has_text_inputs":      bool(self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'],input[type='email']")),
            "has_inputs":           bool(self.driver.find_elements(By.CSS_SELECTOR, "input,select,textarea")),
            "has_checkboxes":       bool(self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")),
            "has_photo_cards":      self._has_photo_cards(),
            "has_radio_or_option_list": bool(self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio'],[role='radio'],[role='listitem'] button")),
            "has_continue":         bool(self._find_continue()),
            "continue_disabled":    self._continue_is_disabled(),
        }

    def _has_photo_cards(self):
        # Cards with images and clickable wrappers — typical quiz photo-card pattern
        cards = self.driver.find_elements(By.CSS_SELECTOR, "button img, [role='button'] img, li img")
        return len(cards) >= 2

    def _find_continue(self):
        try:
            return self.driver.find_element(By.XPATH,
                "//button[normalize-space()='Continue' or normalize-space()='Next' or normalize-space()='Continue →']")
        except Exception:
            return None

    def _continue_is_disabled(self):
        btn = self._find_continue()
        if not btn:
            return False
        return btn.get_attribute("disabled") is not None

    # ------------------------------------------------------------------
    # Low-level actions
    # ------------------------------------------------------------------

    def _accept_cookies(self):
        self._js("""
            (function(){
                var sel = 'button[id*=accept i],button[class*=accept i],button[aria-label*=accept i]';
                var btn = document.querySelector(sel);
                if(btn){ btn.click(); return 'accepted'; }
                return 'none';
            })()
        """)
        time.sleep(0.3)

    def _advance(self):
        """Try to click Continue/Next. Escalate to MouseEvent if plain click fails."""
        self._budget()
        result = self._js("""
            (function(){
                var b = Array.from(document.querySelectorAll('button'))
                    .find(b => ['Continue','Next','Continue →'].includes(b.textContent.trim()) && !b.disabled);
                if(!b) return 'not-found';
                b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
                return 'dispatched';
            })()
        """)
        self.actions += 1
        time.sleep(0.4)
        return result

    def _click_first_card(self):
        self._budget()
        cards = self.driver.find_elements(By.CSS_SELECTOR, "button img, [role='button'] img")
        if cards:
            try:
                cards[0].find_element(By.XPATH, "./..").click()
            except Exception:
                self._js("arguments[0].click()", cards[0])
            self.actions += 1
            time.sleep(0.3)

    def _click_first_option(self):
        self._budget()
        # Try list item buttons first, then radio inputs
        for sel in ["[role='listitem'] button", "input[type='radio']", "label"]:
            els = self.driver.find_elements(By.CSS_SELECTOR, sel)
            if els:
                try:
                    els[0].click()
                    self.actions += 1
                    time.sleep(0.3)
                    return
                except Exception:
                    continue

    def _fill_numeric_defaults(self, dom):
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='number'],[role='spinbutton']")
        defaults = ["5", "6", "165", "140", "35"]
        for i, inp in enumerate(inputs[:len(defaults)]):
            self._fill(inp, defaults[i])

    def _fill_email(self):
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='email'],input[name='email']")
        if inputs:
            self._fill(inputs[0], EMAIL)
            return True
        return False

    def _check_any_checkbox(self):
        self._js("document.querySelector('input[type=checkbox]')?.click()")

    def _fill(self, el, value):
        self._budget()
        el.clear()
        el.send_keys(value)
        self.actions += 1

    def _goto(self, url):
        self._budget()
        self.driver.get(url)
        self.actions += 1
        time.sleep(0.8)

    def _js(self, script, *args):
        try:
            return self.driver.execute_script(script, *args)
        except Exception:
            return None

    def _budget(self):
        if self.actions >= self.BUDGET:
            raise _BudgetExhausted()

    def _check_stuck(self):
        url = self.driver.current_url
        self._seen_urls.append(url)
        if len(self._seen_urls) > self.MAX_SAME:
            self._seen_urls.pop(0)
        if len(self._seen_urls) == self.MAX_SAME and len(set(self._seen_urls)) == 1:
            raise _StuckDetected()

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _write_output(self):
        total_s = round(time.monotonic() - self._t_start, 2)
        checkout_reached = any(
            "checkout" in s["url"] or s["name"] in ("checkout", "payment-form")
            for s in self.steps
        )
        timing = [
            {"step": s["step"], "name": s["name"],
             "elapsed_s": s["elapsed_s"], "step_took_s": s["step_took_s"],
             "actions": s["actions_so_far"]}
            for s in self.steps
        ]
        slowest = max(timing, key=lambda s: s["step_took_s"]) if timing else {}

        data = {
            "run_id":     self.run_id,
            "url":        self.url,
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "archetype":  self.__class__.__name__,

            "timing": {
                "total_s":          total_s,
                "total_actions":    self.actions,
                "budget":           self.BUDGET,
                "budget_used_pct":  round(self.actions / self.BUDGET * 100, 1),
                "slowest_step":     slowest.get("name"),
                "slowest_step_s":   slowest.get("step_took_s", 0),
                "steps":            timing,
            },

            "funnel_steps": [
                {k: v for k, v in s.items()
                 if k not in ("elapsed_s", "step_took_s", "actions_so_far")}
                for s in self.steps
            ],

            "checkout": {
                "reached":         checkout_reached,
                "plans":           [],
                "urgency_tactics": [],
                "trust_signals":   [],
                "cta_text":        "",
                "fine_print":      "",
            },
        }

        path = self.out / "crawl.json"
        path.write_text(json.dumps(data, indent=2))

        print(f"\n{'─'*52}")
        print(f"  run_id       {self.run_id}")
        print(f"  url          {self.url}")
        print(f"  total time   {total_s}s")
        print(f"  actions      {self.actions}/{self.BUDGET} ({data['timing']['budget_used_pct']}%)")
        print(f"  landmarks    {len(self.steps)}")
        print(f"  slowest      {slowest.get('name')} ({slowest.get('step_took_s',0)}s)")
        print(f"  checkout     {'✓' if checkout_reached else '✗'}")
        print(f"  output       {path}")
        print(f"{'─'*52}\n")


class _BudgetExhausted(Exception):
    pass

class _StuckDetected(Exception):
    pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url",        required=True)
    ap.add_argument("--run_id",     required=True)
    ap.add_argument("--output_dir", required=True)
    args = ap.parse_args()
    QuizFunnelCrawler(args.url, args.run_id, args.output_dir).run()
