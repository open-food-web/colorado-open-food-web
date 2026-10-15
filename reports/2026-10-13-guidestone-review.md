# Guidestone review, Oct 13, 2026: what changed in the data

**Source:** Alycen Quattrocchi's review of the Chaffee Provides producer list (her edited sheet and the Oct 13 call, with Emma Lietz Bilecky). This is the first round of partner feedback applied through the normal process: feedback → entries in `inputs/` → a rebuild → this report → a pull request. A maintainer merging the PR is the approval step.

Everything below is reproducible: `inputs/overrides.csv`, `inputs/curated_records.csv` and `inputs/locations.csv` hold Alycen's changes, each credited `partner:guidestone` with the date. Re-running the build keeps them.

## What Alycen told us, and what we did

| Her note | What changed | Where |
|---|---|---|
| Meadows Edge Farm is not in business (red) | Removed | `inputs/overrides.csv` |
| Moonstone Farm: no reply, not public-facing anymore (red) | Removed | `inputs/overrides.csv` |
| Guidestone: list one farm, the Community and School Farm at 1455 Holman Ave, with a Tuesday 4-6 farm stand. Leave the Hutchinson homestead off for now | Old "Guidestone Colorado" record removed; new record added with the farm stand | overrides, `inputs/curated_records.csv` |
| Badger Creek Ranch: no CSA, no visitors at the ranch. Pickups are Tuesday evenings at the Salida Safeway lot (4:45-5:00) and Valley Fellowship Church in Buena Vista (6:00-6:15), plus the farmers market. Use the Coaldale annex address | Address set to the Coaldale annex, ranch address hidden, three pickup places plus the Salida Farmers Market added, channels set (pickup, delivery, farmers market, online) | overrides, `inputs/locations.csv` |
| Rocky Mountain Garlic: the public farm stand is the pin; it also sells at the Salida market and the winter market | Farm stand and Salida Farmers Market pickup recorded; channels set | `inputs/locations.csv` |
| Copper Kettle Apothecary: keep the first address; phone and Facebook correct | Phone set to (719) 530-7111; address left as is | overrides |
| Everett Ranch Beef: phone confirmed | Phone set to (719) 530-1597 | overrides |
| Sweet Pea Farm's Wildflower Honey, The Grainery, Caring & Sharing: Facebook pages are accurate | Facebook set for each | overrides |
| Chaffee Community Resource Center: Tuesday/Thursday 10-1 | Hours set | overrides |
| Cottonwood Spirit Ranch: mostly an Airbnb (orange) | **Kept in the data**, left off the Chaffee Provides site (Guidestone's scope choice) | `exports/chaffee-provides.config.json` |
| Eddyline, The Asian Palate, other caterers: set restaurants aside (orange) | No data change; restaurants and caterers are outlets and are not exported to the site | (existing behavior) |
| Free Community Fridges, Salida and Buena Vista (green) | Already in, as food access points (PR #1) | `data/partner-additions/` |

Every field Alycen confirmed is recorded as **partner-verified** with the date, so a later automatic check can flag a conflict but cannot overwrite it.

## Resulting changes in the Chaffee data

### Counts

| | Before | After |
|---|---|---|
| Producers | 29 | 28 |
| Locations | 37 | 39 |
| Markets | 2 | 2 |
| Food access points | 2 | 2 |
| Producers on the Chaffee Provides site | 29 | 27 |
| Map pins on the Chaffee Provides site | 31 | 33 |

### Added

- **Guidestone Colorado Community and School Farm** (farm). home base: 1455 Holman Ave, Salida — Tue: 4:00pm - 6:00pm
- **Who Knows? Farms** (farm). home base: 19235 US Highway 285, Nathrop — Tue-Sun: 8:00am - 6:00pm

### Removed

- **Guidestone Colorado**
- **Meadows Edge Farm**
- **Moonstone Farm**

### Changed

- **Badger Creek Ranch**
  - address: 5795 County Road 2 → 364 County Road 40
  - city: Cañon City → Coaldale
  - zip: 81212 → 81222
  - sales channels: (blank) → delivery;farmers_market;online;pickup
  - new place to buy — home base: 364 County Road 40, Coaldale (hidden address)
  - new place to buy — pickup: Safeway parking lot (Salida) — Tue: 4:45pm - 5:00pm
  - new place to buy — pickup: Valley Fellowship Church (Buena Vista) — Tue: 6:00pm - 6:15pm
  - new place to buy — pickup: Ranch Annex (Coaldale) — Pickup by arrangement
  - new place to buy — pickup: Salida Farmers Market — Sat: 8:00am - 12:00pm (through Oct 24); winter market Nov 14 - Dec 19
  - no longer listed — home base: 5795 County Road 2, Cañon City
- **Copper Kettle Apothecary**
  - phone: (719) 221-3158 → (719) 530-7111
- **Everett Ranch Beef**
  - phone: (blank) → (719) 530-1597
- **Rocky Mountain Garlic**
  - sales channels: csa;farm_stand → csa;farm_stand;farmers_market;online
  - new place to buy — pickup: Salida Farmers Market — Sat: 8:00am - 12:00pm (through Oct 24); winter market Nov 14 - Dec 19
- **Sweet Pea Farm’s Wildflower Honey**
  - facebook: (blank) → https://www.facebook.com/SweetPeaFarmHoney


## Still waiting (not applied)

| Item | Waiting on |
|---|---|
| The Farm Stand on South Main, Buena Vista (Headwater Farms, Arrowpoint, Buck & Bloom, Eldest Daughter) | Street address and hours (Emma) |
| The stand outside Buena Vista that sells salmon | Emma has the details. A possible match is an "Arnold farm stand" off Crossman, open Saturdays: unconfirmed |
| Pastures of Liberty (replaces Salida Quality Dairy) | Guidestone's decision: it is based in Avondale and members-only (a farm visit is required), and the "drops at MLS" note is unclear |
| Greg's Gourmet Greens, Alpine Valley Mushrooms, Westcliffe Honey Co., Microgreen Creations, Rasin Rye | Alycen's list to cross-reference; the first two have websites, the others need a contact |
| Red marks on Market on Main St (Triangle Oasis), The Ark Angel, Vino Salida; yellow marks on PIFCA, Poncha Creek Gardens, Trout Creek Farm | What she meant by them. (Vino Salida's website has expired.) |
| Chaffee Cares (not food access), Colorado Mountain Lavender (online only) | Alycen is following up with both |
| Emma's map flag: "Market on Main St" drawn in Buena Vista where Josh's Market is, and Josh's Market missing | Check on the new map |
| Caring & Sharing, The Grainery and the Resource Center are food banks | Their confirmed fields are saved but they stay out of the site until food banks join the food access list |
| Sales channels for most producers | 21 of 27 producers on the site still have none confirmed; their home-base pins are marked unconfirmed |

## How this was produced

```
python scripts/scrape/build.py
python scripts/build_tables.py --raw .cache/build/co_farmers_markets_all_raw.csv --county Chaffee \
    --out data/chaffee-county --additions data/partner-additions/guidestone_2026-10-13.csv \
    --locations inputs/locations.csv --overrides inputs/overrides.csv
python scripts/export_app.py --tables data/chaffee-county --out exports/chaffee-provides.json \
    --release 2026-10 --county-fips 08015 --include-source chaffee_provides \
    --config exports/chaffee-provides.config.json
python scripts/change_report.py --before <tables built from main> --after data/chaffee-county
```

## Follow-up, Oct 16: red means closed

The maintainer confirmed that red on Alycen's sheet means the business is closed. Vino Salida Wine Cellars (website expired) and The Ark Angel were marked red but still listed, so both are now removed. Market on Main St (The Triangle Oasis) is also red but its own site still lists it, so it is being checked with Alycen. Colorado Mountain Lavender is red but sells online; the maintainer decided to keep it listed as online-only.
