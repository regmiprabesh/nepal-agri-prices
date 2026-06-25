"""
Scraper for a single AMPIS market page.

AMPIS (https://ampis.gov.np) is a Drupal site. Each market's daily
wholesale price page (https://ampis.gov.np/market-price/<uuid>) renders
one HTML <table> per commodity category (तरकारी, फलफूल, मसला बाली, ...),
each preceded by a heading/emphasis element naming the category.

This module is defensive about exact markup: rather than hard-coding
Drupal CSS classes (which can change between releases), it finds every
<table> on the page and walks backwards through preceding siblings to
find the nearest heading-like element for the category name. Row parsing
is done by column position, matching the column headers AMPIS uses today:

    कृषि उपज | ईकाइ | न्यूनतम | अधिकतम | [औसत]

The "औसत" (average) column isn't present on every page; if missing, it
is computed as (min + max) / 2 instead of being left blank.

IMPORTANT — verify this before relying on it:
The market page has date / category / commodity dropdowns. It is not
yet confirmed whether the static HTML (a plain GET, no JS) already
contains today's price table, or whether the table is only injected
after the page's own JS runs a Drupal AJAX call in response to a form
selection. To handle both possibilities without guessing wrong:

  1. `scrape_market()` first tries a plain `requests.get()` (cheap, fast,
     no browser needed).
  2. If that yields zero recognizable price tables, it automatically
     retries using Playwright (a real headless browser), which will
     execute any JS/AJAX the page needs.

If BOTH attempts yield zero tables, that's a real signal worth
investigating by hand (site structure changed, or genuinely no data for
today) rather than something to paper over — see AmpisScrapeError.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

BASE_URL = "https://ampis.gov.np/market-price/{uuid}"

# Headers we expect, in Nepali, used to confirm we've found a real price
# table (as opposed to some other unrelated table on the page).
EXPECTED_HEADER_TOKENS = ("कृषि उपज", "ईकाइ", "न्यूनतम", "अधिकतम")

HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "em", "strong", "b")


class AmpisScrapeError(RuntimeError):
    """Raised when a market page yields zero recognizable price tables
    after BOTH the static-HTML and rendered-browser attempts. This means
    either AMPIS changed its markup, or something else is genuinely
    wrong — not a transient blip to silently swallow."""


@dataclass
class PriceRow:
    category_np: str
    commodity_np: str
    unit_np: str
    min_price: float
    max_price: float
    avg_price: float


def fetch_market_html_static(uuid: str, *, retries: int = 3, timeout: int = 30) -> str:
    """Fetch the raw HTML for one market page via a plain GET, retrying
    transient failures. This is the cheap path — no browser needed."""
    url = BASE_URL.format(uuid=uuid)
    last_exc: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:  # noqa: PERF203
            last_exc = exc
            if attempt < retries:
                time.sleep(2 * attempt)  # simple backoff
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts") from last_exc


def fetch_market_html_rendered(uuid: str, *, timeout_ms: int = 30_000) -> str:
    """Fetch the page via a real headless browser, letting any client-side
    JS/AJAX run before reading the final DOM. Used only as a fallback when
    the static fetch doesn't yield a recognizable price table."""
    url = BASE_URL.format(uuid=uuid)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()
            page.goto(url, timeout=timeout_ms, wait_until="networkidle")
            return page.content()
        finally:
            browser.close()


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_number(text: str) -> float | None:
    text = _clean(text).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _find_category_heading(table) -> str:
    """Walk backwards from a <table> to the nearest heading-like text."""
    node = table.find_previous(HEADING_TAGS)
    if node:
        text = _clean(node.get_text())
        if text:
            return text
    return "अन्य"  # "other" — fallback if no heading is found


def _looks_like_price_table(header_cells: list[str]) -> bool:
    joined = " ".join(header_cells)
    return all(token in joined for token in EXPECTED_HEADER_TOKENS)


def parse_market_html(html: str) -> list[PriceRow]:
    """Parse every commodity price table on a market page."""
    soup = BeautifulSoup(html, "lxml")
    rows: list[PriceRow] = []

    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if header_row is None:
            continue
        header_cells = [_clean(c.get_text()) for c in header_row.find_all(["th", "td"])]
        if not _looks_like_price_table(header_cells):
            continue

        # Map header text -> column index so we're not relying on fixed
        # positions (AMPIS has been seen both with and without "औसत").
        col_index = {name: i for i, name in enumerate(header_cells)}
        category = _find_category_heading(table)

        for tr in table.find_all("tr")[1:]:  # skip header row
            cells = [_clean(c.get_text()) for c in tr.find_all(["td", "th"])]
            if not cells or len(cells) < 4:
                continue

            commodity = cells[col_index.get("कृषि उपज", 0)]
            unit = cells[col_index.get("ईकाइ", 1)]
            min_price = _parse_number(cells[col_index.get("न्यूनतम", 2)])
            max_price = _parse_number(cells[col_index.get("अधिकतम", 3)])

            if not commodity or min_price is None or max_price is None:
                continue

            if "औसत" in col_index and col_index["औसत"] < len(cells):
                avg_price = _parse_number(cells[col_index["औसत"]])
            else:
                avg_price = None
            if avg_price is None:
                avg_price = round((min_price + max_price) / 2, 2)

            rows.append(
                PriceRow(
                    category_np=category,
                    commodity_np=commodity,
                    unit_np=unit,
                    min_price=min_price,
                    max_price=max_price,
                    avg_price=avg_price,
                )
            )

    return rows


def scrape_market(uuid: str) -> list[PriceRow]:
    """Try the cheap static fetch first; fall back to a rendered browser
    fetch only if the static HTML didn't contain a usable price table."""
    static_html = fetch_market_html_static(uuid)
    rows = parse_market_html(static_html)
    if rows:
        return rows

    rendered_html = fetch_market_html_rendered(uuid)
    rows = parse_market_html(rendered_html)
    if rows:
        return rows

    raise AmpisScrapeError(
        f"No price tables found for market {uuid} after both static and "
        f"rendered fetch attempts. Check the page manually — AMPIS may "
        f"have changed its markup, or the table may require selecting a "
        f"date/category in the form before it renders."
    )


def rows_to_dicts(rows: list[PriceRow]) -> list[dict]:
    return [asdict(r) for r in rows]
