"""
Registry of AMPIS markets.

Each market detail page on https://ampis.gov.np/market-price/<uuid> shows
that market's daily wholesale price tables. The UUID is the only stable
identifier — the homepage dropdown menu lists current markets, but UUIDs
must be picked out by hand once (they don't follow a guessable pattern).

If AMPIS adds a market, grab its UUID from the "बजार" dropdown on
https://ampis.gov.np/ (right-click -> inspect the <option> value, or watch
the network tab when the page filters) and add an entry below.

`slug` is used purely for naming output files (ASCII, filesystem-safe).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    slug: str           # output filename stem, e.g. "attariya_kailali"
    name_en: str         # English display name
    name_np: str         # Nepali display name
    uuid: str            # AMPIS market-price page UUID


MARKETS: list[Market] = [
    Market("birtamod_jhapa", "Birtamod, Jhapa", "बिर्तामोड, झापा", "e05705d2-e9b5-4947-9cd0-a9619fd18b14"),
    Market("dharan_sunsari", "Dharan, Sunsari", "धरान, सुनसरी", "6116a0f3-3f3a-46e2-9f02-6647fab7366e"),
    Market("dhalkebar_dhanusha", "Dhalkebar, Dhanusha", "ढल्केवर, धनुषा", "a9e5c705-82d0-47ed-9f48-e549b383a08c"),
    Market("kamalamai_sindhuli", "Kamalamai, Sindhuli", "कमलामाई, सिन्धुली", "2598da44-a65d-43f6-8ee2-10da417f6e32"),
    Market("kawasoti_nawalpur", "Kawasoti, Nawalpur", "कावासोती, नवलपुर", "26418ca3-a6ef-4a15-9a4e-a12d00ebff5b"),
    Market("pokhara_kaski", "Pokhara, Kaski", "पोखरा, कास्की", "0628dce3-da29-4384-9544-e73f58842189"),
    Market("butwal_rupandehi", "Butwal, Rupandehi", "बुटवल, रुपन्देही", "75b5ebdb-f20e-4cc8-a7dd-cb20f1e84b6c"),
    Market("kohalpur_banke", "Kohalpur, Banke", "कोहलपुर, बाँके", "edb979a3-883e-4e50-96dd-8347c2c8b4b9"),
    Market("birendranagar_surkhet", "Birendranagar, Surkhet", "बिरेन्द्रनगर, सुर्खेत", "20237f47-6aef-4ccb-94ef-2f31fad26c9e"),
    Market("attariya_kailali", "Attariya, Kailali", "अत्तरिया, कैलाली", "e5cb4842-5d11-439d-8673-1608758b06fe"),
    Market("lalbandi_sarlahi", "Lalbandi, Sarlahi", "लालबन्दी, सर्लाही", "17b8872d-7860-41d3-a802-ddbec99182fe"),
    # Kalimati is already covered by its own dedicated API
    # (https://kalimatimarket.gov.np/api/daily-prices/en) — included here
    # too only if you also want it captured via AMPIS for consistency.
    # Market("kalimati_kathmandu", "Kalimati, Kathmandu", "कालीमाटी, काठमाडौं", "PUT-UUID-HERE"),
]
