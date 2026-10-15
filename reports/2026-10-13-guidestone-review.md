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

## Resulting changes

The tables are now statewide, so the counts below are for all of Colorado; the Chaffee Provides site lines are the app export for Chaffee County.

### Counts

| | Before | After |
|---|---|---|
| Producers | 1228 | 1227 |
| Locations | 1491 | 1493 |
| Markets | 153 | 153 |
| Food access points | 2 | 2 |
| Producers on the Chaffee Provides site | 36 | 34 |
| Map pins on the Chaffee Provides site | 37 | 39 |

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
| **Question for Emma and Alycen:** should businesses that grow or operate outside Chaffee County, but sell here (so far at the Salida Farmers Market), get their own listing? Today they do, with no pin of their own. Palisade Peach Shack (Palisade, with a farm tour that is not in the county) is the clearest case; the others are Alpine Valley Mushrooms (Saguache), Feedsack Flowers (Center), Miss Penn's Mountain Seeds and Westcliffe Honey Company (Westcliffe), Raisin' Rye (Del Norte) and Bristlecone Bakeshop (Alma) | Guidestone's decision. If not, they could appear only on the market's vendor list, or be left off |
| Sales channels for most producers | 27 of 34 producers on the site still have none confirmed; their home-base pins are marked unconfirmed |

## How this was produced

```
python scripts/scrape/build.py
python scripts/build_tables.py --raw .cache/build/co_farmers_markets_all_raw.csv --out data/colorado     --additions data/partner-additions/guidestone_2026-10-13.csv     --locations inputs/locations.csv --overrides inputs/overrides.csv
python scripts/export_app.py --tables data/colorado --out exports/chaffee-provides.json     --release 2026-10 --county-fips 08015 --include-source chaffee_provides     --config exports/chaffee-provides.config.json
python scripts/change_report.py --before <tables built from main> --after data/colorado     --export-before <export built from main> --export-after exports/chaffee-provides.json
```

## Follow-up, Oct 16: red means closed

The maintainer confirmed that red on Alycen's sheet means the business is closed. Vino Salida Wine Cellars (website expired) and The Ark Angel were marked red but still listed, so both are now removed. Market on Main St (The Triangle Oasis) is also red but its own site still lists it, so it is being checked with Alycen. Colorado Mountain Lavender is red but sells online; the maintainer decided to keep it listed as online-only.

## Changes driven by the maintainer (David), not by Alycen's sheet

These came out of the maintainer's own review of the draft site and the Oct 8 / Oct 13 calls. They belong to this round, so they are listed here rather than in separate pull requests.

| Change | Why |
|---|---|
| Farms and ranches are separate categories (by how the business labels itself); product groups (veggies, fruit, beef and meat, poultry and eggs, dairy, honey, flowers, garlic and herbs, mushrooms, baked goods, seeds and plants, drinks) | People search by what they want to buy; sales channels are detail on each producer's page, not search filters |
| `confirmed_by` credits in the export | The site credits the partner (Guidestone), or the business's own website or Facebook page, for each confirmed detail |
| Two visit flags, drop-in visits and pickup at the farm, inferred from the listing (farm stand, u-pick, tours, listed as a pickup spot) unless a person has answered; drop-in hours are listed, and "by appointment" is not | Visitors need to know whether they can just show up |
| Vino Salida Wine Cellars and The Ark Angel removed | Red on Alycen's sheet means closed |
| Colorado Mountain Lavender kept, online only | Maintainer decision |
| Sweet Pea Farm: honey, meat chickens, eggs and pork, from its own Facebook page (not beef) | Corrects an earlier claim |
| Seven vendors at the Salida Farmers Market added (Greg's Gourmet Greens, Miss Penn's Mountain Seeds, Alpine Valley Mushrooms, Foxtown Farm, Feedsack Flowers, Westcliffe Honey Company, Palisade Peach Shack) | A business that sells in the county belongs on the county's map wherever it is based; each has no pin of its own, only the market's |
| Microgreen Creations LLC added: grows in Buena Vista, sells at the Salida Farmers Market and the Breckenridge Sunday Market | Same rule. No pin in Buena Vista, because a pin marks a place to buy |
| Bakeries are their own category (Banyan Breads, Raisin' Rye, Bristlecone Bakeshop). Raisin' Rye is a Del Norte bakery that sells at the Salida Farmers Market | Whether the category is in the first launch is for Emma and Alycen; `exclude_kinds: ["bakery"]` in the export config leaves it out |
| A place outside the county gets no pin on the county's map | Raisin' Rye's Del Norte shop is not on the Chaffee map; only its Salida market stall is |
| Colorado Mountain Lavender also offers herbs (product group "Garlic & herbs"); a leading `+` in `inputs/producer_kinds.csv` adds a group to what the products text shows | Maintainer decision |
| Farms that welcome neither drop-in visits nor farm pickup (Colorado Mountain Lavender, Alpine Valley Mushrooms) show one "Not open to visitors" message and no farm under "places to find them"; the town is shown as "Based in" | Maintainer decision; this is done in the site, not the data |
