"""
quiz-funnel archetype base crawler.
Uses Selenium + the already-installed chromium-driver (no extra deps).
Domain extensions import this and override only what differs.

Usage:
  python /workspace/archetypes/quiz_funnel.py \
    --url https://example.com \
    --run_id abc123 \
    --output_dir /crawls/abc123
"""

import argparse, json, os, time
from datetime import datetime, timezone
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


EMAIL    = "qa+123@kilo.health"
EMAIL_FB = "qa123@kilo.health"   # fallback if + is rejected


class QuizFunnelCrawler:
    """
    Base class for quiz-style funnels (personalisation quiz → plan → checkout).
    Override individual step_* methods in a domain extension — nothing else.
    """

    BUDGET = 80   # max selenium actions (clicks + types + navigates)

    def __init__(self, url, run_id, output_dir):
        self.url        = url
        self.run_id     = run_id
        self.out        = Path(output_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.steps      = []      # {step, name, url, screenshot}
        self.actions    = 0
        self.driver     = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self):
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1280,800")
        self.driver = webdriver.Chrome(options=opts)
        try:
            self._crawl()
        except _BudgetExhausted:
            print(f"[{self.__class__.__name__}] budget exhausted at step {len(self.steps)}")
        except Exception as e:
            print(f"[{self.__class__.__name__}] error: {e}")
        finally:
            self._write_output()
            self.driver.quit()

    # ------------------------------------------------------------------
    # Crawl flow — override individual steps, not this method
    # ------------------------------------------------------------------

    def _crawl(self):
        self._goto(self.url)
        self.screenshot("landing")
        self.accept_cookies()
        self.step_entry()
        self.step_age()
        self.step_goal()
        self.step_body_type()
        self.step_target_areas()
        self.step_lifestyle()
        self.step_height()
        self.step_weight()
        self.step_target_weight()
        self.step_age_numeric()
        self.step_informational_inserts()
        self.step_habits()
        self.step_sleep()
        self.step_water()
        self.step_diet()
        self.step_ingredients()
        self.step_email_gate()
        self.step_name()
        self.step_plan_reveal()
        self.step_checkout()

    # ------------------------------------------------------------------
    # Steps — override in extensions as needed
    # ------------------------------------------------------------------

    def accept_cookies(self):
        self._js("document.querySelector('button[id*=accept i],button[class*=accept i]')?.click()")
        time.sleep(0.3)

    def step_entry(self):
        self._click_text(["Female", "Woman", "Get started"])

    def step_age(self):
        self._click_text(["30-39", "30–39"])
        self.screenshot("quiz-age")

    def step_goal(self):
        self._click_text(["Lose weight", "Weight loss"])

    def step_body_type(self):
        self._click_text(["Plump", "Average", "Regular"])

    def step_target_areas(self):
        self._continue()

    def step_lifestyle(self):
        self._click_text(["Desk job", "Sedentary"])

    def step_height(self):
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "[role='spinbutton'], input[type='number']")
        if len(inputs) >= 2:
            self._fill(inputs[0], "5"); self._fill(inputs[1], "6")
        elif inputs:
            self._fill(inputs[0], "168")   # cm fallback
        self._continue()

    def step_weight(self):
        self._fill_spinbutton("165")
        self._continue()

    def step_target_weight(self):
        self._fill_spinbutton("140")
        self._continue()

    def step_age_numeric(self):
        self._fill_spinbutton("35")
        self._continue()

    def step_informational_inserts(self):
        for _ in range(4):
            url_before = self.driver.current_url
            self._continue()
            if self.driver.current_url == url_before:
                break   # didn't advance — probably not an insert screen

    def step_habits(self):
        self._js("document.querySelectorAll('input[type=checkbox]')[0]?.click()")
        self._continue()

    def step_sleep(self):
        self._click_text(["7-8 hours", "7–8 hours"])

    def step_water(self):
        self._click_text(["16 oz - 48 oz", "2 - 6 glasses"])

    def step_diet(self):
        self._click_text(["No, I don", "None", "I don"])
        if not self._try_continue():
            self._js("document.querySelectorAll('input[type=checkbox]')[0]?.click()")
            self._continue()

    def step_ingredients(self):
        self._js("document.querySelector('input[type=checkbox]')?.click()")
        self._continue()

    def step_email_gate(self):
        self.screenshot("email-gate")
        done = self._fill_email(EMAIL)
        if not done:
            self._fill_email(EMAIL_FB)
        self._js("document.querySelector('input[type=checkbox]')?.click()")
        self._continue()

    def step_name(self):
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[name='name'],input[placeholder*='name' i]")
        if inputs:
            self._fill(inputs[0], "Auditor")
            self._continue()

    def step_plan_reveal(self):
        self.screenshot("plan-reveal")
        self._continue()

    def step_checkout(self):
        self.screenshot("checkout")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def screenshot(self, name):
        n = len(self.steps) + 1
        fname = f"{n:02d}-{name}.png"
        self.driver.save_screenshot(str(self.out / fname))
        self.steps.append({"step": n, "name": name, "url": self.driver.current_url, "screenshot": fname})
        print(f"  [{n:02d}] {name} → {fname}")

    def _goto(self, url):
        self._budget()
        self.driver.get(url)
        self.actions += 1
        time.sleep(0.5)

    def _click_text(self, candidates):
        self._budget()
        for text in candidates:
            try:
                el = self.driver.find_element(By.XPATH, f"//*[normalize-space()='{text}']")
                el.click()
                self.actions += 1
                time.sleep(0.3)
                return True
            except Exception:
                continue
        return False

    def _continue(self):
        self._budget()
        self._js(
            "(function(){"
            "var b=Array.from(document.querySelectorAll('button'))"
            ".find(b=>b.textContent.trim()==='Continue'&&!b.disabled);"
            "if(b){b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));return 'ok';}"
            "return 'noop';})()"
        )
        self.actions += 1
        time.sleep(0.4)

    def _try_continue(self):
        url_before = self.driver.current_url
        self._continue()
        return self.driver.current_url != url_before

    def _fill(self, el, value):
        self._budget()
        el.clear(); el.send_keys(value)
        self.actions += 1

    def _fill_spinbutton(self, value):
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "[role='spinbutton'], input[type='number']")
        if inputs:
            self._fill(inputs[0], value)

    def _fill_email(self, email):
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='email'],input[name='email']")
        if inputs:
            self._fill(inputs[0], email)
            return True
        return False

    def _js(self, script):
        try:
            return self.driver.execute_script(script)
        except Exception:
            return None

    def _budget(self):
        if self.actions >= self.BUDGET:
            raise _BudgetExhausted()

    def _write_output(self):
        checkout_reached = any("checkout" in s["url"] or "checkout" in s["name"] for s in self.steps)
        data = {
            "run_id":      self.run_id,
            "url":         self.url,
            "crawled_at":  datetime.now(timezone.utc).isoformat(),
            "archetype":   "quiz-funnel",
            "action_count": self.actions,
            "funnel_steps": self.steps,
            "checkout": {
                "reached":         checkout_reached,
                "plans":           [],
                "urgency_tactics": [],
                "trust_signals":   [],
                "cta_text":        "",
                "fine_print":      "",
            },
        }
        (self.out / "crawl.json").write_text(json.dumps(data, indent=2))
        print(f"  crawl.json → {self.out / 'crawl.json'} ({self.actions} actions)")


class _BudgetExhausted(Exception):
    pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url",        required=True)
    ap.add_argument("--run_id",     required=True)
    ap.add_argument("--output_dir", required=True)
    args = ap.parse_args()
    QuizFunnelCrawler(args.url, args.run_id, args.output_dir).run()
