"""
Standalone debug tool for the Kalimati challenge page.

Run this directly (not via main.py) when fetch_kalimati() is still
failing after the stealth patches in kalimati_fetcher.py. It uses the
EXACT SAME launch args / context options / init script as the real
fetcher (imported, not copy-pasted, so the two can't drift apart) and
saves a screenshot + raw HTML at each stage.

Usage:
    cd src
    python3 debug_kalimati.py

Output (written to ../debug_output/):
    01_initial_load.png / .html   — right after page.goto()
    02_after_wait.png / .html     — after waiting out the challenge's
                                     own self-reload timer

Read these in order:
  - If 01 already shows real JSON: the stealth patches worked, no
    challenge appeared at all on this run.
  - If 01 shows the challenge but 02 shows real JSON: the patches
    worked, you just needed to wait out one reload cycle (this is the
    expected, "working correctly" case).
  - If BOTH still show the challenge: the stealth patches in
    kalimati_fetcher.py aren't enough yet. Open 02_after_wait.html in
    a text editor — if the obfuscated detection script LOOKS different
    from the one you saw in your original Laravel logs, the site
    changed its anti-bot mechanism; if it looks the same, one of the
    checks (webdriver/plugins/mimeTypes/languages) is still slipping
    through and needs a closer look.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))

from kalimati_fetcher import (  # noqa: E402
    CHALLENGE_WAIT_MS,
    STEALTH_INIT_SCRIPT,
    USER_AGENT,
    _looks_like_challenge,
)

URL = "https://kalimatimarket.gov.np/api/daily-prices/en"
OUT_DIR = Path(__file__).resolve().parent.parent / "debug_output"


def save(page, stage: str) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    page.screenshot(path=str(OUT_DIR / f"{stage}.png"), full_page=True)
    (OUT_DIR / f"{stage}.html").write_text(page.content(), encoding="utf-8")
    print(f"  saved {stage}.png and {stage}.html")


def main() -> None:
    with sync_playwright() as p:
        # headless=False to match kalimati_fetcher.py exactly. If this
        # crashes with something like "Missing X server" or similar,
        # you're on a machine/session with no display — run this over
        # a real desktop session, or wrap with xvfb-run (Linux):
        #   xvfb-run --auto-servernum -- python3 debug_kalimati.py
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            slow_mo=150,
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )
        context.add_init_script(STEALTH_INIT_SCRIPT)
        page = context.new_page()

        print(f"Navigating to {URL} ...")
        page.goto(URL, timeout=30_000, wait_until="domcontentloaded")
        print("Initial load done.")
        save(page, "01_initial_load")

        is_challenge = _looks_like_challenge(page.content())
        print(f"Looks like challenge page? {is_challenge}")

        if is_challenge:
            print(f"Waiting {CHALLENGE_WAIT_MS / 1000:.0f}s for the page's own auto-reload...")
            page.wait_for_timeout(CHALLENGE_WAIT_MS)
            save(page, "02_after_wait")

            still_challenge = _looks_like_challenge(page.content())
            print(f"Still challenge after wait? {still_challenge}")

        print(f"\nFinal page title: {page.title()}")
        print(f"Final URL: {page.url}")
        print(f"\nAll output saved under: {OUT_DIR}")

        browser.close()


if __name__ == "__main__":
    main()
