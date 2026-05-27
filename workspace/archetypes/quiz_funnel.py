"""
quiz-funnel archetype base crawler.

Generic loop — classify each screen, act, screenshot every distinct screen.
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


EMAIL    = "qa+123@kilo.health"
EMAIL_FB = "qa123@kilo.health"


class QuizFunnelCrawler:
    """
    Crawls a quiz-style funnel by classifying each screen and acting.
    Screenshots every distinct screen — URL change or heading change.
    No hardcoded step sequence. Discovers the funnel at runtime.

    Subclasses may override:
      - classify(dom)   → return screen type string, or None for base logic
      - act(stype, dom) → return True if handled, False to fall back
      - is_done()       → return True to stop early
    """

    BUDGET   = 80
    MAX_SAME = 5   # stop if URL+heading unchanged this many consecutive loops

    def __init__(self, url, run_id, output_dir):
        self.url          = url
        self.run_id       = run_id
        self.out          = Path(output_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.steps        = []
        self.actions      = 0
        self.driver       = None
        self._t_start     = None
        self._t_prev      = None
        self._prev_sig    = None   # (url, heading) — detect distinct screens
        self._same_count  = 0

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
            print(f"[crawler] stuck — no progress after {self.MAX_SAME} loops")
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
        self._maybe_screenshot()   # landing

        while not self._is_terminal():
            dom   = self._dom_signals()
            stype = self.classify(dom) or self._base_classify(dom)
            handled = self.act(stype, dom)
            if not handled:
                self._base_act(stype, dom)
            self._check_stuck(dom)
            self._maybe_screenshot()   # screenshot if page changed

    # ------------------------------------------------------------------
    # Screenshot every distinct screen
    # ------------------------------------------------------------------

    def _screen_sig(self):
        """Fingerprint for the current screen — URL + visible heading."""
        url = self.driver.current_url
        heading = self._js(
            "return (document.querySelector('h1,h2,h3,h4,h5,h6,legend') || {}).innerText || ''"
        ) or ""
        return (url, heading.strip()[:120])

    def _maybe_screenshot(self):
        """Take a screenshot if this screen is distinct from the last one."""
        sig = self._screen_sig()
        if sig == self._prev_sig:
            return
        self._prev_sig = sig
        url, heading = sig
        name = self._screen_name(url, heading)
        self._screenshot(name)

    def _screen_name(self, url, heading):
        """Derive a slug for the screenshot filename from the heading or URL."""
        if heading:
            slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")[:40]
            return slug or "screen"
        # Fall back to last URL path segment
        path = url.rstrip("/").split("/")[-1].split("?")[0]
        return re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")[:40] or "screen"

    def _screenshot(self, name):
        now       = time.monotonic()
        elapsed   = round(now - self._t_start, 2)
        step_took = round(now - self._t_prev, 2) if self._t_prev else elapsed
        self._t_prev = now

        n     = len(self.steps) + 1
        fname = f"{n:02d}-{name}.png"
        self.driver.save_screenshot(str(self.out / fname))
        self.steps.append({
            "step":           n,
            "name":           name,
            "url":            self.driver.current_url,
            "screenshot":     fname,
            "elapsed_s":      elapsed,
            "step_took_s":    step_took,
            "actions_so_far": self.actions,
        })
        print(f"  [{n:02d}] {name} | +{step_took}s | total {elapsed}s | {self.actions} actions")

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify(self, dom):
        """Override to intercept classification. Return string or None."""
        return None

    def _base_classify(self, dom):
        text = dom["text"].lower()
        url  = dom["url"].lower()

        if any(x in url for x in ["/checkout", "/pricing", "/plans", "/order"]):
            return "checkout"
        if any(x in url for x in ["/upsell", "/upgrade", "/offer"]):
            return "upsell"
        if dom["has_payment_input"]:
            return "payment-form"
        if dom["has_email_input"]:
            return "email-gate"
        if any(x in text for x in ["your plan", "you will reach", "lbs by", "kg by", "by july", "by august"]):
            return "plan-reveal"
        if dom["has_name_input"]:
            return "name-input"
        if dom["has_numeric_inputs"] and not dom["has_text_inputs"]:
            return "numeric-input"
        if dom["has_checkboxes"] and dom["continue_disabled"]:
            return "multi-select"
        if dom["has_photo_cards"]:
            return "photo-card-select"
        if dom["has_option_list"]:
            return "single-select"
        if dom["has_continue"] and not dom["has_inputs"]:
            return "informational"
        return "unknown"

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def act(self, stype, dom):
        """Override to intercept actions. Return True if handled, False to fall back."""
        return False

    def _base_act(self, stype, dom):
        if stype == "photo-card-select":
            self._click_first_card()

        elif stype == "single-select":
            self._click_first_option()

        elif stype == "multi-select":
            self._js("document.querySelectorAll('input[type=checkbox]')[0]?.click()")
            self._advance()

        elif stype == "numeric-input":
            self._fill_numeric_defaults(dom)
            self._advance()

        elif stype == "email-gate":
            self._fill_email(EMAIL)
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

        elif stype in ("checkout", "payment-form", "upsell"):
            pass   # terminal — stop advancing

        else:
            self._advance()

    # ------------------------------------------------------------------
    # Terminal condition
    # ------------------------------------------------------------------

    def _is_terminal(self):
        if self.is_done():
            return True
        url = self.driver.current_url.lower()
        return any(x in url for x in ["/checkout", "/payment", "/order", "/upsell"])

    def is_done(self):
        return False

    # ------------------------------------------------------------------
    # DOM signals
    # ------------------------------------------------------------------

    def _dom_signals(self):
        url  = self.driver.current_url
        text = self.driver.find_element(By.TAG_NAME, "body").text
        return {
            "url":               url,
            "text":              text[:2000],
            "has_email_input":   bool(self.driver.find_elements(By.CSS_SELECTOR, "input[type='email']")),
            "has_payment_input": bool(self.driver.find_elements(By.CSS_SELECTOR,
                "input[name*='card'],input[name*='number'],iframe[name*='stripe'],iframe[name*='braintree']")),
            "has_name_input":    bool(self.driver.find_elements(By.CSS_SELECTOR,
                "input[name='name'],input[placeholder*='name' i]")),
            "has_numeric_inputs": bool(self.driver.find_elements(By.CSS_SELECTOR,
                "input[type='number'],[role='spinbutton']")),
            "has_text_inputs":   bool(self.driver.find_elements(By.CSS_SELECTOR,
                "input[type='text'],input[type='email']")),
            "has_inputs":        bool(self.driver.find_elements(By.CSS_SELECTOR, "input,select,textarea")),
            "has_checkboxes":    bool(self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")),
            "has_photo_cards":   self._has_photo_cards(),
            "has_option_list":   bool(self.driver.find_elements(By.CSS_SELECTOR,
                "input[type='radio'],[role='radio'],[role='listitem'] button,[role='option']")),
            "has_continue":      bool(self._find_continue()),
            "continue_disabled": self._continue_is_disabled(),
        }

    def _has_photo_cards(self):
        cards = self.driver.find_elements(By.CSS_SELECTOR,
            "button img,[role='button'] img,li img,[class*='card'] img")
        return len(cards) >= 2

    def _find_continue(self):
        try:
            return self.driver.find_element(By.XPATH,
                "//button[normalize-space()='Continue' or normalize-space()='Next'"
                " or normalize-space()='Continue →' or normalize-space()='Get started']")
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
            var sel='button[id*=accept i],button[class*=accept i],button[aria-label*=accept i]';
            var b=document.querySelector(sel);
            if(b) b.click();
        """)
        time.sleep(0.3)

    def _advance(self):
        self._budget()
        self._js("""
            (function(){
                var b=Array.from(document.querySelectorAll('button'))
                    .find(b=>['Continue','Next','Continue →','Get started']
                        .includes(b.textContent.trim())&&!b.disabled);
                if(b) b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
            })()
        """)
        self.actions += 1
        time.sleep(0.4)

    def _click_first_card(self):
        self._budget()
        cards = self.driver.find_elements(By.CSS_SELECTOR,
            "button img,[role='button'] img,[class*='card'] img")
        if cards:
            try:
                cards[0].find_element(By.XPATH, "./..").click()
            except Exception:
                self._js("arguments[0].click()", cards[0])
            self.actions += 1
            time.sleep(0.3)

    def _click_first_option(self):
        self._budget()
        for sel in ["[role='listitem'] button,[role='option']",
                    "input[type='radio']", "label"]:
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
        inputs = self.driver.find_elements(By.CSS_SELECTOR,
            "input[type='number'],[role='spinbutton']")
        defaults = ["5", "6", "165", "140", "35"]
        for i, inp in enumerate(inputs[:len(defaults)]):
            self._fill(inp, defaults[i])

    def _fill_email(self, email):
        inputs = self.driver.find_elements(By.CSS_SELECTOR,
            "input[type='email'],input[name='email']")
        if inputs:
            self._fill(inputs[0], email)
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

    def _check_stuck(self, dom):
        sig = (dom["url"], dom["text"][:100])
        if not hasattr(self, "_last_stuck_sig"):
            self._last_stuck_sig = None
            self._same_count = 0
        if sig == self._last_stuck_sig:
            self._same_count += 1
            if self._same_count >= self.MAX_SAME:
                raise _StuckDetected()
        else:
            self._last_stuck_sig = sig
            self._same_count = 0

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
                "total_s":         total_s,
                "total_actions":   self.actions,
                "budget":          self.BUDGET,
                "budget_used_pct": round(self.actions / self.BUDGET * 100, 1),
                "slowest_step":    slowest.get("name"),
                "slowest_step_s":  slowest.get("step_took_s", 0),
                "steps":           timing,
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
        print(f"  screenshots  {len(self.steps)}")
        print(f"  actions      {self.actions}/{self.BUDGET} ({data['timing']['budget_used_pct']}%)")
        print(f"  slowest      {slowest.get('name')} ({slowest.get('step_took_s', 0)}s)")
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
