"""
Fetcher for Kalimati's own daily-prices API.

Kalimati publishes clean JSON in English and Nepali:
    https://kalimatimarket.gov.np/api/daily-prices/en
    https://kalimatimarket.gov.np/api/daily-prices/np

BUT: the site sits behind a JS anti-bot interstitial ("Please wait while
your request is being verified..."). Confirmed (via debug_kalimati.py
screenshots) that this is NOT a timing issue — the page reloads itself
every 5s and shows the SAME challenge every time, meaning its detection
script is actively and correctly identifying our browser as automated
on every attempt, not just failing to finish rendering in time.

Reading the page's own (deliberately obfuscated, but readable once
de-minified) detection script, it runs these checks and treats ANY of
them being true as "this is a bot":

  1. webdriverCheck        — `navigator.webdriver` is true
  2. userAgentCheck        — UA string contains "headless"/"bytespider"
  3. appVersionCheck       — appVersion string contains "headless"
  4. pluginArraySpoofing   — navigator.plugins/PluginArray prototype
                              mismatch (headless Chromium's plugins
                              array is empty/inconsistent)
  5. mimeTypeArraySpoofing — same idea for navigator.mimeTypes
  6. noLanguage            — navigator.languages is empty
  7. zeroOuterDimensions   — window.outerWidth/outerHeight are both 0
                              (true for headless Chromium, since there's
                              no real window chrome)

(1)-(3) and (6) are straightforward to fix with a custom user agent and
a small JS override injected before any page script runs. (4)-(5) are
fixed the same way, faking a plausible plugins/mimeTypes array. (7) is
structural to headless mode itself — there's no real "outer window" to
report a size for — so the only honest fix is to NOT run headless.

On a machine with a real display (your laptop), `headless=False` just
works. On a GitHub Actions runner (no display), the workflow uses
`xvfb-run` to provide a virtual display so "headed" mode still works
without an actual screen — this is a standard, well-supported pattern,
not exotic infrastructure (see .github/workflows/daily-scrape.yml).
"""

from __future__ import annotations

import json
import os
import re

from playwright.sync_api import sync_playwright

from name_map import UNIT_NAME_MAP

# Set KALIMATI_HEADLESS=1 in your environment (or GitHub Actions env) to
# run headless. Defaults to headed (False) because Kalimati's bot-detection
# script checks window.outerWidth/outerHeight, which are always 0 in true
# headless mode — a dead giveaway. In GitHub Actions, use xvfb-run in
# your workflow step instead of flipping this flag:
#
#   - run: xvfb-run --auto-servernum python src/main.py
#
# Only set KALIMATI_HEADLESS=1 if you've confirmed the challenge page is
# no longer checking outerDimensions, or if you're on a newer Chromium
# that fakes them correctly in headless mode.
HEADLESS: bool = os.environ.get("KALIMATI_HEADLESS", "0") == "1"

EN_URL = "https://kalimatimarket.gov.np/api/daily-prices/en"
NP_URL = "https://kalimatimarket.gov.np/api/daily-prices/np"

# How long to give the challenge page to self-resolve after a real,
# stealthed browser loads it. The page reloads itself every 5s; one
# extra cycle of margin is plenty once detection is actually passing.
CHALLENGE_WAIT_MS = 7_000

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Injected before any page script runs (Playwright's add_init_script
# fires on every navigation/reload in this context, which matters since
# the challenge page reloads itself). Patches exactly the signals the
# site's own detection script checks for.
STEALTH_INIT_SCRIPT = """
Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => undefined });

Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

Object.defineProperty(navigator, 'plugins', {
  get: () => {
    const fakePlugin = Object.create(Plugin.prototype);
    const arr = Object.create(PluginArray.prototype);
    Object.defineProperty(arr, 'length', { value: 1 });
    arr[0] = fakePlugin;
    return arr;
  }
});

Object.defineProperty(navigator, 'mimeTypes', {
  get: () => {
    const fakeMime = Object.create(MimeType.prototype);
    const arr = Object.create(MimeTypeArray.prototype);
    Object.defineProperty(arr, 'length', { value: 1 });
    arr[0] = fakeMime;
    return arr;
  }
});
"""


class ChallengeNotResolvedError(RuntimeError):
    """Raised when the bot-challenge page never resolved to real JSON."""


def _looks_like_challenge(text: str) -> bool:
    return "Please wait while your request is being verified" in text


def _extract_json_from_page(raw_text: str) -> dict:
    """
    A JSON API endpoint loaded in a browser is normally wrapped by the
    browser's own JSON viewer (Chrome/Chromium renders it inside a
    <pre> tag). Playwright's `page.content()` returns the full
    documentElement HTML, so pull the actual JSON text out of it.
    """
    match = re.search(r'<pre[^>]*>(.*)</pre>', raw_text, re.DOTALL)
    candidate = match.group(1) if match else raw_text

    candidate = (
        candidate.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )

    return json.loads(candidate)


def _fetch_one(playwright, url: str, *, timeout_ms: int = 30_000) -> dict:
    # Uses the HEADLESS flag defined at module level — see its comment for
    # when to flip it. --disable-blink-features=AutomationControlled removes
    # Chromium automation tells at the engine level on top of the JS overrides.
    browser = playwright.chromium.launch(
        headless=HEADLESS,
        args=["--disable-blink-features=AutomationControlled"],
    )
    try:
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )
        context.add_init_script(STEALTH_INIT_SCRIPT)
        page = context.new_page()
        page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

        content = page.content()
        if _looks_like_challenge(content):
            page.wait_for_timeout(CHALLENGE_WAIT_MS)
            content = page.content()

        if _looks_like_challenge(content):
            raise ChallengeNotResolvedError(
                f"Challenge page never resolved for {url} "
                f"(stealth overrides didn't satisfy the site's detection "
                f"script — see debug_kalimati.py to inspect further)"
            )

        return _extract_json_from_page(content)
    finally:
        browser.close()


def _translate_unit(raw_unit: str, unmapped_units: set[str]) -> dict:
    """
    Kalimati's API returns unit strings in English only, with
    inconsistent casing/spacing across rows (observed: "KG", "Kg",
    "Doz", "1 Pc", "Per Dozen", ...). Normalize (lowercase, collapse
    whitespace) and look up in UNIT_NAME_MAP for a bilingual result.

    Unmapped units are tracked (not guessed at) so they surface the
    same way unmapped commodity names do, rather than silently showing
    English-only or a wrong translation.
    """
    raw_unit = (raw_unit or "").strip()
    normalized = re.sub(r"\s+", " ", raw_unit).strip().lower()

    mapped = UNIT_NAME_MAP.get(normalized)
    if mapped is not None:
        return {"en": mapped["en"], "ne": mapped["ne"]}

    if raw_unit:
        unmapped_units.add(raw_unit)
    # Use the raw string for both sides so the app always has something
    # displayable — same principle as commodity name passthrough.
    fallback = raw_unit or None
    return {"en": fallback, "ne": fallback}


def fetch_kalimati() -> list[dict]:
    """
    Returns a list of dicts, one per commodity, each with both english and
    nepali names where available, and a bilingual unit:

        {
          "commodity_en": "Tomato Big(Nepali)",
          "commodity_np": "गोलभेंडा ठुलो (नेपाली)",   # "" if unavailable
          "unit": {"en": "Kg", "ne": "के.जी."},
          "min_price": 60.0,
          "max_price": 70.0,
          "avg_price": 63.75,
        }

    Any unit string not found in name_map.UNIT_NAME_MAP is left as
    English-only ({"en": <raw value>, "ne": None}) and printed as a
    warning at the end of this function, rather than guessed at —
    mirroring how unmapped commodity names are handled in main.py.
    """
    with sync_playwright() as p:
        en_data = _fetch_one(p, EN_URL)

        if "prices" not in en_data:
            raise RuntimeError(
                "Kalimati English feed loaded but has no 'prices' key "
                "— response shape may have changed."
            )

        try:
            np_data = _fetch_one(p, NP_URL)
            np_prices = np_data.get("prices", [])
        except (ChallengeNotResolvedError, json.JSONDecodeError, RuntimeError):
            # Don't fail the whole run if only the Nepali variant breaks —
            # English data alone is still useful output.
            np_prices = []

    np_names = [item.get("commodityname", "") for item in np_prices]
    same_length = len(np_names) == len(en_data["prices"])

    unmapped_units: set[str] = set()
    results = []
    for i, item in enumerate(en_data["prices"]):
        results.append(
            {
                "commodity_en": item.get("commodityname", ""),
                "commodity_np": np_names[i] if same_length else "",
                "unit": _translate_unit(item.get("commodityunit", ""), unmapped_units),
                "min_price": float(item.get("minprice", 0) or 0),
                "max_price": float(item.get("maxprice", 0) or 0),
                "avg_price": float(item.get("avgprice", 0) or 0),
            }
        )

    if unmapped_units:
        print(
            f"  [warn] {len(unmapped_units)} unit string(s) had no Nepali "
            f"mapping: {sorted(unmapped_units)} -> add them to "
            f"UNIT_NAME_MAP in name_map.py."
        )

    return results