"""
Daily run entry point.

For each market in `markets.py`:
  1. Scrape its AMPIS page.
  2. Translate each Nepali commodity name to English via `name_map.py`.
  3. Write data/<slug>.json (bilingual records) for that market.

Also writes data/kalimati_kathmandu.json from Kalimati's own API,
data/_index.json listing all markets + last-updated timestamp,
data/market_prices_latest.json — a single combined file in the shape
the Laravel app actually consumes (one HTTP request instead of N) —
and data/history/<slug>.csv per market: one row per commodity per day,
accumulated over time for later analysis/price-prediction use. Running
main.py twice in the same day replaces that day's rows for a market
rather than duplicating them.

For AMPIS commodity names not found in name_map.py, a second lookup is
attempted against Kalimati's live bilingual data (commodity_np ->
commodity_en). If that also misses, the raw Nepali name is used as-is
so the Laravel app always gets a displayable string.

Unmapped commodity names (Nepali names resolved by neither name_map.py
nor Kalimati's live data) are collected across all markets and written to
data/unmapped_commodities.txt so they're easy to spot and fix.

Designed to run once per day via GitHub Actions
(see .github/workflows/daily-scrape.yml). Safe to re-run: every run
overwrites that day's files; nothing is appended.
"""

from __future__ import annotations

import csv
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

from ampis_scraper import scrape_market, rows_to_dicts
from kalimati_fetcher import fetch_kalimati
from markets import MARKETS
from name_map import COMMODITY_NAME_MAP, UNIT_NAME_MAP

# Reverse lookup: Nepali unit string -> {"en": ..., "ne": ...}
# Built once at import time from UNIT_NAME_MAP (which is keyed by English).
# Used to resolve AMPIS unit strings, which come back Nepali-only.
_UNIT_NE_TO_BILINGUAL: dict[str, dict[str, str]] = {
    v["ne"]: v
    for v in UNIT_NAME_MAP.values()
    if v.get("ne")
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_DIR = DATA_DIR / "history"
REQUEST_DELAY_SECONDS = 2  # be polite to a small gov't server between markets

HISTORY_FIELDNAMES = [
    "date",
    "commodity_en",
    "commodity_ne",
    "unit_en",
    "unit_ne",
    "min",
    "max",
    "avg",
]


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def translate(
    commodity_np: str,
    unmapped: set[str],
    kalimati_np_to_en: dict[str, str],
) -> tuple[str, str]:
    """
    Returns (english_name, source) where source is one of:
      "static_map"       — found in COMMODITY_NAME_MAP (name_map.py)
      "kalimati_derived" — not in static map, but matched via Kalimati's
                           live bilingual data (commodity_np -> commodity_en)
      "unmapped"         — not found anywhere; raw Nepali name used as-is
                           so the app always gets a displayable string

    Unmapped names are added to `unmapped` for logging to
    data/unmapped_commodities.txt at the end of the run.
    """
    english = COMMODITY_NAME_MAP.get(commodity_np)
    if english:
        return english, "static_map"

    english = kalimati_np_to_en.get(commodity_np)
    if english:
        return english, "kalimati_derived"

    unmapped.add(commodity_np)
    return commodity_np, "unmapped"  # raw Nepali as fallback — never None


def build_market_record(
    market,
    unmapped: set[str],
    kalimati_np_to_en: dict[str, str],
) -> dict:
    print(f"[scrape] {market.slug} ({market.name_en})")

    if market.uuid.startswith("PUT-UUID"):
        print(f"  -> skipped: no UUID configured for {market.slug}")
        return {
            "market_slug": market.slug,
            "market_name_en": market.name_en,
            "market_name_np": market.name_np,
            "status": "skipped_no_uuid",
            "fetched_at_utc": None,
            "prices": [],
        }

    try:
        rows = scrape_market(market.uuid)
    except Exception as exc:  # noqa: BLE001 - log and continue other markets
        print(f"  -> FAILED: {exc}")
        return {
            "market_slug": market.slug,
            "market_name_en": market.name_en,
            "market_name_np": market.name_np,
            "status": f"error: {exc}",
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "prices": [],
        }

    prices = []
    for row in rows_to_dicts(rows):
        english_name, name_source = translate(
            row["commodity_np"], unmapped, kalimati_np_to_en
        )
        unit_np = row["unit_np"]
        # If the Nepali unit string is in the map, we get a proper bilingual
        # result. If not, use the Nepali string for both sides so the app
        # always has something displayable rather than en=None.
        unit_bilingual = _UNIT_NE_TO_BILINGUAL.get(
            unit_np, {"en": unit_np or None, "ne": unit_np or None}
        )
        prices.append(
            {
                "category_np": row["category_np"],
                "name": {"en": english_name, "ne": row["commodity_np"]},
                "name_source": name_source,  # "static_map" | "kalimati_derived" | "unmapped"
                "unit": unit_bilingual,
                "min": row["min_price"],
                "max": row["max_price"],
                "avg": row["avg_price"],
            }
        )

    print(f"  -> {len(prices)} commodities scraped")
    return {
        "market_slug": market.slug,
        "market_name_en": market.name_en,
        "market_name_np": market.name_np,
        "status": "ok",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "prices": prices,
    }


def build_kalimati_record() -> tuple[list[dict], dict]:
    """
    Returns (raw_items, shaped_record).

    raw_items is the list straight from fetch_kalimati() — held onto by
    main() to build the kalimati_np_to_en lookup for AMPIS fallback
    resolution, without a second network call.
    """
    print("[fetch] kalimati_kathmandu (Kalimati, Kathmandu)")
    try:
        items = fetch_kalimati()
    except Exception as exc:  # noqa: BLE001
        print(f"  -> FAILED: {exc}")
        return [], {
            "market_slug": "kalimati_kathmandu",
            "market_name_en": "Kalimati, Kathmandu",
            "market_name_np": "कालीमाटी, काठमाडौं",
            "status": f"error: {exc}",
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "prices": [],
        }

    prices = [
        {
            "category_np": "",
            "name": {"en": item["commodity_en"] or None, "ne": item["commodity_np"] or None},
            "name_source": "kalimati_api",  # Kalimati's own API gives English directly
            "unit": item["unit"],  # already {"en": ..., "ne": ...} from fetch_kalimati()
            "min": item["min_price"],
            "max": item["max_price"],
            "avg": item["avg_price"],
        }
        for item in items
    ]
    print(f"  -> {len(prices)} commodities fetched")
    return items, {
        "market_slug": "kalimati_kathmandu",
        "market_name_en": "Kalimati, Kathmandu",
        "market_name_np": "कालीमाटी, काठमाडौं",
        "status": "ok",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "prices": prices,
    }


def build_combined_record(record: dict) -> dict:
    """
    Reshape one market's internal record into the flat shape Laravel's
    MarketPriceService expects per market:

        { "key": "...", "name": {"en":..,"ne":..}, "date": "...",
          "commodities": [ {"name":{...}, "unit":{...}, "min","max","avg"} ] }
    """
    return {
        "key": record["market_slug"],
        "name": {"en": record["market_name_en"], "ne": record["market_name_np"]},
        "date": record["fetched_at_utc"],
        "status": record["status"],
        "commodities": [
            {
                "name": p["name"],
                "unit": p["unit"],
                "min": p["min"],
                "max": p["max"],
                "avg": p["avg"],
            }
            for p in record["prices"]
        ],
    }


def write_combined_output(records: list[dict]) -> None:
    """
    Writes data/market_prices_latest.json — the single file the Laravel
    app actually fetches (one HTTP request instead of N). Only markets
    with status "ok" and at least one commodity are included, so a
    failed/skipped market doesn't ship an empty entry to the app.
    """
    markets = [
        build_combined_record(r)
        for r in records
        if r["status"] == "ok" and r["prices"]
    ]
    write_json(
        DATA_DIR / "market_prices_latest.json",
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "markets": markets,
        },
    )


def _read_existing_history_rows(csv_path: Path) -> list[dict]:
    """Returns existing rows as plain dicts, or [] if the file doesn't
    exist yet. Tolerant of a missing/corrupt file — history is a nice-to
    -have, not something that should ever crash the daily run."""
    if not csv_path.exists():
        return []
    try:
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except (csv.Error, OSError) as exc:
        print(f"  [warn] could not read existing history at {csv_path}: {exc}")
        return []


def append_to_history(record: dict, today: str) -> None:
    """
    Appends today's prices for one market to data/history/<slug>.csv,
    one row per commodity. If this market already has a row for
    `today` (e.g. main.py was run twice in one day — once manually,
    once via the scheduled job), those rows are replaced rather than
    duplicated, so the history stays one-row-per-commodity-per-day and
    is safe to reuse directly for later analysis/prediction work.

    Markets with no usable data (skipped/error/zero commodities) are
    left untouched — we don't want a blank or error day silently
    appearing as a real (empty) data point in the history.
    """
    if record["status"] != "ok" or not record["prices"]:
        return

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = HISTORY_DIR / f"{record['market_slug']}.csv"

    existing_rows = _read_existing_history_rows(csv_path)
    kept_rows = [row for row in existing_rows if row.get("date") != today]

    new_rows = [
        {
            "date": today,
            "commodity_en": p["name"]["en"] or "",
            "commodity_ne": p["name"]["ne"] or "",
            "unit_en": p["unit"]["en"] or "",
            "unit_ne": p["unit"]["ne"] or "",
            "min": p["min"],
            "max": p["max"],
            "avg": p["avg"],
        }
        for p in record["prices"]
    ]

    all_rows = kept_rows + new_rows
    all_rows.sort(key=lambda r: (r["date"], r["commodity_en"], r["commodity_ne"]))

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    replaced_note = " (replaced existing rows for today)" if len(existing_rows) != len(kept_rows) else ""
    print(f"  -> history: {len(new_rows)} rows written to {csv_path.name}{replaced_note}")



def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    unmapped: set[str] = set()
    index_entries = []
    all_records = []
    had_error = False
    today = date.today().isoformat()  # one consistent date for this whole run

    # Kalimati first — it already has clean bilingual data from its own API.
    # raw_kalimati_items is kept to build the AMPIS fallback lookup below.
    raw_kalimati_items, kalimati_record = build_kalimati_record()
    write_json(DATA_DIR / f"{kalimati_record['market_slug']}.json", kalimati_record)
    append_to_history(kalimati_record, today)
    all_records.append(kalimati_record)
    index_entries.append(
        {
            "slug": kalimati_record["market_slug"],
            "name_en": kalimati_record["market_name_en"],
            "name_np": kalimati_record["market_name_np"],
            "status": kalimati_record["status"],
            "file": f"{kalimati_record['market_slug']}.json",
        }
    )
    if kalimati_record["status"] != "ok":
        had_error = True

    # Build a Nepali -> English lookup from Kalimati's live bilingual data.
    # Used as a fallback in translate() for AMPIS commodity names not yet
    # in COMMODITY_NAME_MAP — no extra network call needed since we already
    # have the raw items from the Kalimati fetch above.
    kalimati_np_to_en: dict[str, str] = {
        item["commodity_np"]: item["commodity_en"]
        for item in raw_kalimati_items
        if item.get("commodity_np") and item.get("commodity_en")
    }

    for i, market in enumerate(MARKETS):
        record = build_market_record(market, unmapped, kalimati_np_to_en)
        write_json(DATA_DIR / f"{market.slug}.json", record)
        append_to_history(record, today)
        all_records.append(record)
        index_entries.append(
            {
                "slug": market.slug,
                "name_en": market.name_en,
                "name_np": market.name_np,
                "status": record["status"],
                "file": f"{market.slug}.json",
            }
        )
        if record["status"].startswith("error"):
            had_error = True

        if i < len(MARKETS) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)

    write_json(
        DATA_DIR / "_index.json",
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "markets": index_entries,
        },
    )

    write_combined_output(all_records)

    if unmapped:
        unmapped_path = DATA_DIR / "unmapped_commodities.txt"
        unmapped_path.write_text("\n".join(sorted(unmapped)) + "\n", encoding="utf-8")
        print(
            f"\n[warn] {len(unmapped)} commodity name(s) had no English mapping. "
            f"See {unmapped_path} -> add them to src/name_map.py."
        )
    else:
        stale = DATA_DIR / "unmapped_commodities.txt"
        if stale.exists():
            stale.unlink()

    print("\nDone.")
    return 1 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main())