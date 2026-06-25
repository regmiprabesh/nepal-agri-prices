# nepal-agri-prices

Daily scrape of Nepali wholesale agricultural prices from **Kalimati
Tarkari Bazar** (Kathmandu's main wholesale fruit & vegetable market)
and **AMPIS** (the government's market-price portal covering 11 other
regional markets). Publishes one combined JSON file for the SmartKishan
backend to fetch, plus an accumulating CSV history per market for later
price-trend analysis or prediction.

---

## Quick start

```bash
pip install -r requirements.txt
playwright install chromium

cd src
python3 main.py
```

On a headless Linux server/SSH session with no display, wrap the run
with Xvfb instead (explained in detail below):

```bash
sudo apt-get install xvfb   # one-time
xvfb-run --auto-servernum -- python3 main.py
```

Check the console output for `[fetch]`/`[scrape]` lines, then look at
`data/market_prices_latest.json`.

---

## Why Kalimati needs a real (headed) browser, not a simple API call

Kalimati Tarkari Bazar — officially the **Kalimati Fruit and Vegetable
Market Development Committee**, Nepal's largest wholesale agricultural
market, established in 1987 — publishes a clean, structured JSON feed
at:

```
https://kalimatimarket.gov.np/api/daily-prices/en
https://kalimatimarket.gov.np/api/daily-prices/np
```

This looks like it should be a one-line `requests.get()`. It isn't,
and here's exactly why, worked out by actually debugging it rather
than assuming:

### What goes wrong with a plain HTTP request

A plain HTTP client (`requests`, `curl`, Laravel's `Http::get()`, etc.)
gets back a **200 OK** — so it looks successful — but the response body
isn't JSON. It's an HTML page titled "One moment, please..." with a
spinner and the text "Please wait while your request is being
verified...", plus a heavily obfuscated JavaScript payload.

### It's not a timing issue — it's real bot detection

The obfuscated script does a `setTimeout(..., 5000)` that reloads the
page every 5 seconds. The natural assumption is "just wait a bit
longer for it to finish loading." **That assumption was tested and
disproven**: a debug run that waited through multiple reload cycles
still got served the exact same challenge page every time. That only
happens if the page's detection check is actively and correctly
identifying the client as a bot on every single attempt — not failing
to finish rendering.

Reading through the de-obfuscated script, it runs these checks and
treats *any* of them being true as "this is a bot":

| Check | What it tests |
|---|---|
| `webdriverCheck` | `navigator.webdriver` is `true` |
| `userAgentCheck` | UA string contains "headless"/"bytespider" |
| `appVersionCheck` | `navigator.appVersion` contains "headless" |
| `pluginArraySpoofing` | `navigator.plugins` is empty/inconsistent |
| `mimeTypeArraySpoofing` | `navigator.mimeTypes` is empty/inconsistent |
| `noLanguage` | `navigator.languages` is empty |
| `zeroOuterDimensions` | `window.outerWidth` AND `outerHeight` are both `0` |

A plain HTTP client never executes this JavaScript at all, so it can
never produce a passing answer to any of these checks — it just gets
served the static challenge HTML forever. **This is why no amount of
retrying, waiting, or "trying again" on the Laravel/PHP side ever
fixed it** — the problem was never about retry logic, it was that
nothing was ever running the page's JS in the first place.

### Why a *headless* browser doesn't fully fix it either

The natural next step is "drive a real browser with Playwright/Puppeteer
instead." That gets further — a headless browser does execute the
JS — but headless Chromium still **fails two of the checks above by
default**:

- `navigator.webdriver` is `true` in automation contexts unless
  explicitly patched.
- Headless Chromium has no real window chrome, so
  `outerWidth`/`outerHeight` are genuinely `0` — there's no window to
  measure. This one can't be safely faked from inside the page (timing
  attacks and prototype-chain checks exist precisely to catch that kind
  of patch on more sophisticated anti-bot systems).

### The actual fix, confirmed working against the live site

`src/kalimati_fetcher.py` launches Chromium **headed** (`headless=False`)
with `--disable-blink-features=AutomationControlled`, plus a small
script injected into the page before any of its own JS runs, patching:

- `navigator.webdriver` → `undefined` (on `Navigator.prototype`, matching
  how a real browser defines it — not just the instance)
- `navigator.languages` → `['en-US', 'en']`
- `navigator.plugins` / `navigator.mimeTypes` → non-empty fake arrays

Headed mode resolves the `outerWidth`/`outerHeight` check structurally,
since a real (even if invisible-to-you) browser window has real
dimensions. **This combination was tested against the live site and
confirmed to work.**

### "Headed" doesn't mean you need a monitor

On a normal desktop, `headless=False` just opens a visible browser
window briefly. On a server with no display (like a GitHub Actions
runner), the same headed browser runs perfectly fine under **Xvfb** — a
virtual framebuffer that gives Chromium a "screen" to report real
dimensions to, without any actual monitor attached. This is a standard,
well-supported pattern (see `.github/workflows/daily-scrape.yml`), not
exotic infrastructure — it's one `apt-get install xvfb` and prefixing
the command with `xvfb-run --auto-servernum --`.

### Debugging it yourself

```bash
cd src
python3 debug_kalimati.py
```

This runs the exact same stealth logic as the real fetcher (imported,
not copy-pasted, so they can't drift apart) and saves a screenshot +
raw HTML at each stage to `../debug_output/`. If you ever see the
challenge page again after a future Kalimati change, this is the first
thing to run — it'll show you directly whether the patches are still
working rather than leaving you to guess from an error message.

---

## What's in this repo

```
nepal-agri-prices/
├── src/
│   ├── main.py               — entry point, run this
│   ├── kalimati_fetcher.py   — Kalimati's own API (headed Playwright, see above)
│   ├── ampis_scraper.py      — AMPIS market pages (static fetch, Playwright fallback)
│   ├── debug_kalimati.py     — standalone diagnostic tool for Kalimati
│   ├── markets.py            — registry of the 11 AMPIS markets + their UUIDs
│   └── name_map.py           — Nepali<->English commodity + unit translation dicts
├── .github/workflows/
│   └── daily-scrape.yml      — runs main.py daily at 1:07 AM Nepal time
├── data/                     — output, committed to the repo each run
│   ├── market_prices_latest.json   — combined file, what Laravel fetches
│   ├── <market_slug>.json          — one raw record per market
│   ├── unmapped_commodities.txt    — any Nepali names missing from name_map.py
│   └── history/<market_slug>.csv   — accumulating daily price history
├── test_main_smoke.py        — mocked end-to-end test, no network needed
└── requirements.txt
```

### Markets covered

Kalimati (Kathmandu) via its own API, plus 11 AMPIS markets:

| Market | Slug |
|---|---|
| Kalimati, Kathmandu | `kalimati_kathmandu` |
| Birtamod, Jhapa | `birtamod_jhapa` |
| Dharan, Sunsari | `dharan_sunsari` |
| Dhalkebar, Dhanusha | `dhalkebar_dhanusha` |
| Kamalamai, Sindhuli | `kamalamai_sindhuli` |
| Kawasoti, Nawalpur | `kawasoti_nawalpur` |
| Pokhara, Kaski | `pokhara_kaski` |
| Butwal, Rupandehi | `butwal_rupandehi` |
| Kohalpur, Banke | `kohalpur_banke` |
| Birendranagar, Surkhet | `birendranagar_surkhet` |
| Attariya, Kailali | `attariya_kailali` |
| Lalbandi, Sarlahi | `lalbandi_sarlahi` |

---

## How AMPIS scraping works

`ampis_scraper.py` tries a cheap plain HTTP fetch of each market's page
first. If that doesn't contain a recognizable price table (the page has
date/category dropdowns, so the table may require JS/AJAX to populate),
it automatically falls back to a Playwright-rendered fetch. Table
parsing is done by matching column headers by name (कृषि उपज / ईकाइ /
न्यूनतम / अधिकतम / औसत) rather than fixed positions, so it tolerates
minor markup changes. If *both* attempts yield zero tables, it raises
loudly (`AmpisScrapeError`) instead of silently writing empty data —
that's a real signal worth investigating, not something to paper over.

AMPIS gives commodity names in **Nepali only**. `name_map.py`'s
`COMMODITY_NAME_MAP` bridges this — built from AMPIS's commodity list,
cross-checked against Kalimati's English names. Any AMPIS commodity not
yet in the map is still included in the output (no real price data is
ever silently dropped) with `name.en: null`, and logged to
`data/unmapped_commodities.txt` so it's easy to find and fix.

---

## Why units needed their own translation map

Kalimati's API gives bilingual **commodity names** out of the box, but
its **units** come back English-only, with inconsistent casing across
rows: `KG`, `Kg`, `Doz`, `1 Pc`, `Per Dozen`, etc. Rather than scraping
a second source just for units, `name_map.py`'s `UNIT_NAME_MAP` handles
this with a small hand-maintained lookup — the unit vocabulary is
closed and tiny (weight/count/volume units), unlike commodity names,
which are open-ended and need a scrape-and-grow approach.

Lookups are normalized (lowercased, whitespace-collapsed), so `"KG"`,
`"Kg"`, `"  kg "` all resolve to the same entry. Units not yet in the
map are left English-only (`{"en": "...", "ne": null}`) and logged as
a warning — never guessed at:

```
[warn] 1 unit string(s) had no Nepali mapping: ['Sack'] -> add them to UNIT_NAME_MAP in name_map.py.
```

Add new ones using the same lowercase-key convention as the existing
entries, e.g.:

```python
"sack": {"en": "Sack", "ne": "बोरा"},
```

---

## Price history for prediction work

Every successful run appends to `data/history/<market_slug>.csv` — one
row per commodity per day:

```
date, commodity_en, commodity_ne, unit_en, unit_ne, min, max, avg
```

- Re-running on the same day **replaces** that day's rows for a market
  rather than duplicating them, so it's safe to re-run repeatedly while
  testing without polluting the dataset.
- A failed/skipped market writes nothing for that day — a gap in the
  dates means "no data," not "price was zero."
- These accumulate in the repo over time. Once you've got a useful
  stretch of history, load directly into pandas:

```python
import pandas as pd
df = pd.read_csv("data/history/kalimati_kathmandu.csv", parse_dates=["date"])
```

---

## Output shape

`data/market_prices_latest.json` — the file Laravel actually fetches:

```json
{
  "generated_at_utc": "...",
  "markets": [
    {
      "key": "kalimati_kathmandu",
      "name": {"en": "Kalimati, Kathmandu", "ne": "कालीमाटी, काठमाडौं"},
      "date": "...",
      "status": "ok",
      "commodities": [
        {
          "name": {"en": "Tomato Big (Nepali)", "ne": "गोलभेंडा ठुलो (नेपाली)"},
          "unit": {"en": "Kg", "ne": "के.जी."},
          "min": 50.0,
          "max": 60.0,
          "avg": 55.0
        }
      ]
    }
  ]
}
```

Only markets with `status: "ok"` and at least one commodity are
included — a failed or skipped market never ships an empty/misleading
entry. `name.en` can be `null` for an AMPIS commodity not yet in
`COMMODITY_NAME_MAP`; handle that in the app by falling back to the
Nepali name.

---

## Testing

```bash
python3 test_main_smoke.py
```

Mocks every network call (Kalimati, AMPIS) and exercises the full data
pipeline: commodity/unit translation, the combined-output shape,
skip-on-missing-data handling, and history CSV writing including
same-day de-duplication. No internet required, runs in under a second,
safe to run after any edit to `name_map.py` or `markets.py`.

---

## Deploying on a schedule (GitHub Actions)

1. Push this repo to **[github.com/regmiprabesh/nepal-agri-prices](https://github.com/regmiprabesh/nepal-agri-prices)** — public means
   free, no-auth access to `raw.githubusercontent.com`.
2. No secrets needed. `permissions: contents: write` in the workflow
   is enough for it to commit results back using the automatically
   provided `GITHUB_TOKEN`.
3. Go to **Actions → Daily market price scrape → Run workflow** to
   test the whole pipeline manually (including the Chromium + Xvfb
   install) before trusting the 1:07 AM Nepal-time schedule.

The workflow installs Playwright's Chromium, installs Xvfb, then runs
`xvfb-run --auto-servernum -- python3 main.py` — exactly mirroring the
headed-browser approach described above, just on a runner with no
physical display.

---

## Consuming the data

Once a run has succeeded at least once, the combined JSON file is
publicly available at:

```
https://raw.githubusercontent.com/regmiprabesh/nepal-agri-prices/main/data/market_prices_latest.json
```

No authentication, no bot-walls, no cookies. Fetch it from anywhere:

**JavaScript / Node.js**
```js
const res = await fetch(
  'https://raw.githubusercontent.com/regmiprabesh/nepal-agri-prices/main/data/market_prices_latest.json'
);
const data = await res.json();
```

**Python**
```python
import requests
data = requests.get(
    'https://raw.githubusercontent.com/regmiprabesh/nepal-agri-prices/main/data/market_prices_latest.json',
    timeout=10,
).json()
```

**curl**
```bash
curl -s https://raw.githubusercontent.com/regmiprabesh/nepal-agri-prices/main/data/market_prices_latest.json \
  | python3 -m json.tool
```

**PHP**
```php
$data = json_decode(file_get_contents(
    'https://raw.githubusercontent.com/regmiprabesh/nepal-agri-prices/main/data/market_prices_latest.json'
), true);
```

All the scraping complexity lives here in this repo, run once a day on
infrastructure built for exactly this kind of job — your client just
does a single, plain HTTP GET.