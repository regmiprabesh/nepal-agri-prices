"""
Local smoke test — mocks every network call so we can exercise main.py's
full data-flow logic (shape consistency between AMPIS + Kalimati records,
translate(), the combined-output writer, the unmapped-commodities file,
and the per-market history CSV including same-day de-duplication)
WITHOUT touching the real internet. This catches structural bugs
(KeyError, shape mismatches) fast, before a real GitHub Actions run.

It does NOT verify:
  - that fetch_market_html_static/_rendered actually returns AMPIS's
    real table HTML (no network access from this sandbox to confirm)
  - that the Kalimati Playwright challenge-bypass actually works against
    the live, real anti-bot page (same reason)

Run with: python3 test_main_smoke.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from unittest import mock

SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

# Sample AMPIS-shaped HTML: one category table with two commodities,
# one of which (स्कूस) IS in name_map.py, plus a deliberately-unmapped
# fake commodity to test the unmapped-tracking path.
FAKE_AMPIS_HTML = """
<html><body>
<h3>तरकारी</h3>
<table>
  <tr><th>कृषि उपज</th><th>ईकाइ</th><th>न्यूनतम</th><th>अधिकतम</th><th>औसत</th></tr>
  <tr><td>स्कूस</td><td>के.जी.</td><td>40</td><td>50</td><td>45</td></tr>
  <tr><td>नयाँ तरकारी</td><td>के.जी.</td><td>10</td><td>20</td><td>15</td></tr>
</table>
</body></html>
"""

FAKE_KALIMATI_RESULTS = [
    {
        "commodity_en": "Tomato Big (Nepali)",
        "commodity_np": "गोलभेंडा ठुलो (नेपाली)",
        "unit": {"en": "Kg", "ne": "के.जी."},  # mapped unit, common case
        "min_price": 50.0,
        "max_price": 60.0,
        "avg_price": 55.0,
    },
    {
        "commodity_en": "Banana (Malbhog)",
        "commodity_np": "केरा (मालभोग)",
        "unit": {"en": "Doz", "ne": "दर्जन"},  # mapped count-based unit
        "min_price": 80.0,
        "max_price": 100.0,
        "avg_price": 90.0,
    },
    {
        "commodity_en": "Mystery Item",
        "commodity_np": "रहस्य वस्तु",
        "unit": {"en": "Sack", "ne": None},  # deliberately UNMAPPED unit
        "min_price": 200.0,
        "max_price": 250.0,
        "avg_price": 225.0,
    },
]


def run_smoke_test() -> None:
    import ampis_scraper
    import kalimati_fetcher
    import markets as markets_module
    import main

    # Give one market a real-looking UUID so it's not skipped, and make
    # sure exactly one stays "PUT-UUID-HERE" so we test the skip path too.
    test_markets = [
        markets_module.Market(
            "attariya_kailali", "Attariya, Kailali", "अत्तरिया, कैलाली",
            "e5cb4842-5d11-439d-8673-1608758b06fe",
        ),
        markets_module.Market(
            "birtamod_jhapa", "Birtamod, Jhapa", "बिर्तामोड, झापा",
            "PUT-UUID-HERE",
        ),
    ]

    with mock.patch.object(main, "MARKETS", test_markets), \
         mock.patch.object(
             ampis_scraper, "fetch_market_html_static", return_value=FAKE_AMPIS_HTML
         ), \
         mock.patch.object(
             kalimati_fetcher, "fetch_kalimati", return_value=FAKE_KALIMATI_RESULTS
         ), \
         mock.patch.object(main, "fetch_kalimati", kalimati_fetcher.fetch_kalimati), \
         mock.patch.object(main, "scrape_market", ampis_scraper.scrape_market), \
         mock.patch.object(main, "REQUEST_DELAY_SECONDS", 0):

        test_data_dir = SRC_DIR.parent / "data"
        if test_data_dir.exists():
            shutil.rmtree(test_data_dir)

        exit_code = main.main()

    print(f"\n--- main() returned exit code: {exit_code} ---")

    # Assertions on what got written
    combined = test_data_dir / "market_prices_latest.json"
    assert combined.exists(), "market_prices_latest.json was not written"

    import json
    payload = json.loads(combined.read_text(encoding="utf-8"))
    market_keys = {m["key"] for m in payload["markets"]}
    print(f"Combined file markets: {market_keys}")

    assert "kalimati_kathmandu" in market_keys, "Kalimati missing from combined output"
    assert "attariya_kailali" in market_keys, "Attariya missing from combined output"
    assert "birtamod_jhapa" not in market_keys, (
        "Skipped market (no UUID) should NOT appear in combined output"
    )

    attariya = next(m for m in payload["markets"] if m["key"] == "attariya_kailali")
    assert len(attariya["commodities"]) == 2, "Expected 2 commodities for Attariya"

    mapped = next(c for c in attariya["commodities"] if c["name"]["ne"] == "स्कूस")
    assert mapped["name"]["en"] == "Christophine", f"Mapping failed: {mapped}"

    unmapped_commodity = next(
        c for c in attariya["commodities"] if c["name"]["ne"] == "नयाँ तरकारी"
    )
    assert unmapped_commodity["name"]["en"] is None, (
        "Unmapped commodity should have name.en == None, not a guessed value"
    )

    unmapped_file = test_data_dir / "unmapped_commodities.txt"
    assert unmapped_file.exists(), "unmapped_commodities.txt should exist"
    assert "नयाँ तरकारी" in unmapped_file.read_text(encoding="utf-8")

    kalimati = next(m for m in payload["markets"] if m["key"] == "kalimati_kathmandu")
    assert kalimati["commodities"][0]["name"]["en"] == "Tomato Big (Nepali)"
    assert kalimati["commodities"][0]["unit"] == {"en": "Kg", "ne": "के.जी."}, (
        f"Mapped unit shape wrong: {kalimati['commodities'][0]['unit']}"
    )

    banana = next(c for c in kalimati["commodities"] if c["name"]["en"] == "Banana (Malbhog)")
    assert banana["unit"] == {"en": "Doz", "ne": "दर्जन"}, f"Doz unit mapping failed: {banana['unit']}"

    mystery = next(c for c in kalimati["commodities"] if c["name"]["en"] == "Mystery Item")
    assert mystery["unit"] == {"en": "Sack", "ne": None}, (
        f"Unmapped unit should pass through as {{'en': 'Sack', 'ne': None}}, got {mystery['unit']}"
    )

    # --- History CSV checks ---
    import csv as csv_module

    history_dir = test_data_dir / "history"
    attariya_csv = history_dir / "attariya_kailali.csv"
    kalimati_csv = history_dir / "kalimati_kathmandu.csv"
    birtamod_csv = history_dir / "birtamod_jhapa.csv"

    assert attariya_csv.exists(), "attariya_kailali.csv history file was not written"
    assert kalimati_csv.exists(), "kalimati_kathmandu.csv history file was not written"
    assert not birtamod_csv.exists(), (
        "Skipped market (no UUID) should NOT get a history file"
    )

    with attariya_csv.open(encoding="utf-8") as f:
        rows_after_first_run = list(csv_module.DictReader(f))
    assert len(rows_after_first_run) == 2, (
        f"Expected 2 history rows after first run, got {len(rows_after_first_run)}"
    )
    print(f"\nHistory after 1st run: {len(rows_after_first_run)} row(s) in attariya_kailali.csv")

    # Re-run main() the SAME day to verify de-duplication: rows for
    # today should be REPLACED, not duplicated, per Anthony's choice.
    with mock.patch.object(main, "MARKETS", test_markets), \
         mock.patch.object(
             ampis_scraper, "fetch_market_html_static", return_value=FAKE_AMPIS_HTML
         ), \
         mock.patch.object(
             kalimati_fetcher, "fetch_kalimati", return_value=FAKE_KALIMATI_RESULTS
         ), \
         mock.patch.object(main, "fetch_kalimati", kalimati_fetcher.fetch_kalimati), \
         mock.patch.object(main, "scrape_market", ampis_scraper.scrape_market), \
         mock.patch.object(main, "REQUEST_DELAY_SECONDS", 0):
        main.main()

    with attariya_csv.open(encoding="utf-8") as f:
        rows_after_second_run = list(csv_module.DictReader(f))
    assert len(rows_after_second_run) == 2, (
        f"Expected STILL 2 rows after same-day re-run (de-dup should replace, "
        f"not duplicate), got {len(rows_after_second_run)}"
    )
    print(f"History after 2nd run (same day): {len(rows_after_second_run)} row(s) "
          f"— de-duplication working correctly")

    print("\n✅ ALL SMOKE TEST ASSERTIONS PASSED")
    print(f"   (exit code {exit_code} is expected to be 0 here, since no real "
          f"errors occurred — only an intentional skip)")


if __name__ == "__main__":
    run_smoke_test()
