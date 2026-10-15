# Colorado Open Food Web — Schema (DRAFT v0.1)

> Draft for maintainer review. Follows [`CHARTER.md`](CHARTER.md).
> Canonical form is plain CSV tables; JSON, GeoJSON and SQLite are built from them.
> A Frictionless `datapackage.json` will be generated from this spec once it is agreed.

## Model in one picture

```
producer 1 ──< producer_location >── 1 location ── county (FIPS)
   │                          │
   ├──< market_vendor >── 1 market ───┤ (each market has one location)
   ├──< outlet_supplier >── 1 outlet ─┘ (each outlet has one location)
                                      access_point ─┘ (each food access point has one location)
   ├──< service_area (derived from producer locations, markets and outlets, or set by hand)
   └──< source_link / field_source (for producers, markets and outlets)
```

- **producer**: one record per producer. This is the unit behind a producer homepage.
- **market**: a recurring multi-vendor gathering. Not a producer: it is its own record type, tied
  to one location, with its own hours, season and programs.
- **outlet**: a restaurant, caterer, food truck, cafe, bar, grocer, farm store, garden center or other
  business that sells or serves local food. Not a producer: its own record type, tied to one location,
  kept deliberately thin. What it is comes from its `kind`.
- **outlet_supplier**: a sourced claim that a producer supplies an outlet. One linked table serves
  every kind of outlet.
- **location**: a physical location with coordinates (a farm, a stand, a market site, an outlet).
- **access_point**: a place where people can get food without buying it: a community fridge now, pantries and meal sites later. Not a producer or an outlet: its own record type, tied to one location, kept thin. Apps show it as type "food access".
- **producer_location**: the link between a producer and a location, with the role (home base, farm stand, CSA drop-off, pickup), days and hours.
- **market_vendor**: a producer selling at a market in a given year.
- **service_area**: counties where a producer can be found. Derived from producer locations and market
  participation, or set by hand for producers who deliver or ship.
- **source_link / field_source**: where each record and each field came from, and when it was checked.

A producer with no location at all (online or wholesale only) is valid. A producer whose only
connections are four markets is valid.

## Field classes

Every field has a class that decides whether it appears in the public release.

| Class | Meaning | In public release |
|---|---|---|
| `fact` | A checkable fact (name, address, phone, coordinates) | Yes |
| `controlled` | Value from a project vocabulary (categories, products, kinds) | Yes |
| `owned` | Text written by the project, or submitted by the producer under the contributor statement | Yes |
| `source_prose` | Descriptive text copied from a source | **No.** Link only (see `source_link`) |
| `personal` | Could identify a person rather than a business (home address the producer hides, personal social profile) | **No**, unless the business itself publishes it for customers |

## Identifiers

- IDs are stable, never reused, and namespaced: `co-p-000123` (producer), `co-m-000789` (market), `co-o-000321` (outlet),
  `co-loc-000456` (location).
- Slugs (`aspen-moon-farm`, with `-2` on collisions) are separate from IDs and may change; the ID may not.
- Merged duplicates keep a redirect in `id_aliases` so old IDs still resolve.

## Table: `producers`

| Field | Type | Class | Notes |
|---|---|---|---|
| `producer_id` | string | fact | Required. Primary key |
| `slug` | string | fact | Homepage path |
| `name` | string | fact | Required. Business name |
| `kind` | enum | controlled | How the business labels itself: `farm`, `ranch`, `orchard`, `maker`, `winery`. A vegetable farm and a cattle ranch are different things to a shopper, so they are not merged. Markets are not producers (see `markets`). Food hubs, retailers and organizations are not decided yet (see open questions) |
| `categories` | list | controlled | From the category vocabulary below. Primary first |
| `products` | list | controlled | From the product vocabulary |
| `product_groups` | list | controlled | The short list people search by: `veggies`, `fruit`, `beef-meat`, `poultry-eggs`, `dairy`, `honey`, `flowers`, `garlic-herbs`, `mushrooms`, `baked-goods`, `drinks`. Found from the products text, categories and name, plus what the business itself ticked (`inputs/producer_kinds.csv`). `products` keeps the source's own words |
| `dropin_visits` | bool/null | fact | Can a customer just show up? Set by a person (`inputs/producer_kinds.csv`); a stated farm stand or u-pick also counts as yes in the export. Null = not confirmed, never assumed |
| `farm_pickup` | bool/null | fact | Can a customer collect an order at the farm, by arrangement? A different question from `dropin_visits`: a ranch can refuse drop-ins and still hand over pre-ordered beef at its annex |
| `visit_note` | string | owned | One plain sentence about visiting or pickup, written by us or the business |
| `seasonal_months` | list | fact | Months operating, 1–12. Empty if unknown |
| `hours_structured` | list | fact | `{days, open, close, season_start, season_end}` entries. See `hours_text` |
| `hours_text` | string | fact | Fallback when hours cannot be structured. Verbatim and short |
| `website` | url | fact | The business's own site |
| `phone` | string | fact | Public business phone |
| `email` | string | fact/personal | Only if the business publishes it for customers |
| `facebook`, `instagram` | url | fact/personal | Business pages only |
| `sales_channels` | list | controlled | How the public can buy from this producer; check any that apply. `farm_stand` (on-farm sales: a stand, store or open hours at the farm), `u_pick`, `csa`, `farmers_market`, `pickup` (off-farm pickup points), `delivery`, `online`, `wholesale`, `retail_partners`. Blank = not yet confirmed, never assumed none. A producer is mapped at its home base only when `farm_stand` or `u_pick` is checked |
| `certified_organic` | bool/null | fact | Null = unknown, never assumed false |
| `accepts_snap` | bool/null | fact | |
| `ada_accessible` | bool/null | fact | |
| `call_first` | bool/null | fact | |
| `description` | string | owned | Only text we wrote or the producer submitted. Never copied |
| `status` | enum | fact | `active`, `seasonal_closed`, `closed`, `unverified`, `removed` |
| `claimed` | bool | fact | Producer has confirmed their record |
| `opted_out_fields` | list | fact | Fields the producer asked to have removed |
| `first_seen`, `last_verified` | date | fact | |

## Table: `locations`

| Field | Type | Class | Notes |
|---|---|---|---|
| `location_id` | string | fact | Required |
| `name` | string | fact | Location name if different from the producer |
| `kind` | enum | controlled | What the spot is: `farm`, `market_site`, `outlet_site`, `access_site`, `public_venue` (a parking lot, church or park used by several producers), `other`. What a producer does there is the role on `producer_locations` |
| `address`, `city`, `zip` | string | fact/personal | Honors `hide_address` |
| `hide_address` | bool | fact | When true, public release keeps city and county only, and coordinates are rounded to the town |
| `state` | string | fact | `CO`. A field, not a constant |
| `county_fips` | string | fact | 5-digit FIPS (e.g. `08117`). County name is derived |
| `lat`, `lon` | number | fact | Null if not known |
| `geo_source` | enum | fact | `source`, `geocoder`, `manual` |
| `google_place_id` | string | fact | Stored for link-outs and live photo thumbnails. No photos or photo URLs stored |
| `photo_url`, `photo_credit`, `photo_license` | string | owned | Only when the producer submitted the photo with an open license |

## Table: `producer_locations`

A producer can have several locations (a farm plus three pickup points). Each is one row here; the physical spot is a row in `locations`, which other records can share. `role` says what the producer does at the location; `sales_channels` on the producer says how it sells overall. `farm_stand` and `pickup` appear in both on purpose: the channel is the how, the role is the where.

| Field | Type | Class | Notes |
|---|---|---|---|
| `producer_location_id` | string | fact | Primary key |
| `producer_id` | string | fact | FK |
| `location_id` | string | fact | FK |
| `role` | enum | controlled | `home_base`, `farm_stand`, `csa_dropoff`, `pickup`. Markets are in `market_vendors` and stores or restaurants in `outlet_suppliers`, not here |
| `days`, `hours_text` | list/string | fact | When they are at that location |
| `season_start`, `season_end` | date/month | fact | Months or dates |
| `status` | enum | fact | `confirmed`, `listed`, `unverified` |

## Table: `markets`

A recurring gathering where several vendors sell at a fixed location. A market has exactly one location;
a market that moves between sites is one record per site, linked by `network_name`.

| Field | Type | Class | Notes |
|---|---|---|---|
| `market_id` | string | fact | Required. Primary key |
| `slug` | string | fact | Page path |
| `name` | string | fact | Required |
| `location_id` | string | fact | FK. Required |
| `operator` | string | fact | Organization that runs it |
| `network_name` | string | fact | For markets run as a series at several sites |
| `days`, `season_start`, `season_end` | list/date | fact | When it runs |
| `hours_structured`, `hours_text` | list/string | fact | As for producers |
| `website`, `phone`, `email`, `facebook`, `instagram` | string | fact/personal | Public contact for the market |
| `accepts_snap`, `double_up`, `accepts_wic`, `ada_accessible` | bool/null | fact | Null = unknown |
| `status` | enum | fact | `active`, `seasonal_closed`, `closed`, `unverified` |
| `first_seen`, `last_verified` | date | fact | |

## Table: `market_vendors`

| Field | Type | Class | Notes |
|---|---|---|---|
| `market_id` | string | fact | FK |
| `producer_id` | string | fact | FK |
| `year` | integer | fact | Vendor lists change yearly. Required |
| `days`, `season_start`, `season_end` | list/date | fact | If narrower than the market's own |
| `status` | enum | fact | `confirmed`, `listed`, `unverified` |
| `list_source` | string | fact | Which vendor list said so |

## Table: `outlets`

Any business that sells or serves local food: a restaurant, caterer, food truck, cafe, bar, grocer,
farm store, garden center or other retailer. One table, with a `kind` saying which. Thin on purpose:
identity, location and a link to where the business describes itself. The Food Web holds no menus,
prices or descriptions. One record per location; chains share a `brand`.

| Field | Type | Class | Notes |
|---|---|---|---|
| `outlet_id` | string | fact | Required. Primary key |
| `slug` | string | fact | Page path |
| `name` | string | fact | Required |
| `kind` | enum | controlled | Dining: `restaurant`, `caterer`, `food_truck`, `cafe`, `bar_or_taproom`, `other_dining`. Retail: `grocery`, `farm_store`, `garden_center`, `other_retail` |
| `brand` | string | fact | Chain or group name, for multi-location businesses |
| `location_id` | string | fact | FK. Required |
| `website`, `phone` | string | fact | Public business contact |
| `facebook`, `instagram` | url | fact/personal | Business pages only |
| `status` | enum | fact | `active`, `seasonal_closed`, `closed`, `unverified` |
| `first_seen`, `last_verified` | date | fact | Restaurants close often; `last_verified` matters |

Apps can group kinds as needed: the dining kinds answer "where to eat", the retail kinds "where to buy". The grouping is derived from `kind`, not stored.

## Table: `outlet_suppliers`

The most perishable data in the Food Web: who buys from whom changes with menus and seasons.

| Field | Type | Class | Notes |
|---|---|---|---|
| `outlet_id` | string | fact | FK |
| `producer_id` | string | fact | FK |
| `featured_item` | string | fact | The item the source names (a dish, drink or product), kept short and factual. Optional |
| `basis` | enum | fact | `outlet_says`, `producer_says`, `both`, `third_party` |
| `source_url` | url | fact | Page that states it (menu, supplier list, producer page) |
| `source_dated` | date | fact | The date on the page, if it shows one. Optional |
| `observed_on` | date | fact | When the claim was seen. Required |
| `status` | enum | fact | `current`, `unverified`, `ended` |

## Table: `access_points`

A place to get food that is not a sale. Version 1 holds community fridges; pantries, meal sites and food boxes use the same table when they are added. Thin on purpose: identity, location, hours and public contact.

| Field | Type | Class | Notes |
|---|---|---|---|
| `access_point_id` | string | fact | Required. Primary key (`co-ap-000001`) |
| `slug` | string | fact | Page path |
| `name` | string | fact | Required |
| `kind` | enum | controlled | `community_fridge`; later `pantry`, `meal_site`, `food_box`, `other` |
| `location_id` | string | fact | FK. Required |
| `hours_text` | string | fact | For example "Open 24/7" |
| `website`, `phone`, `email`, `facebook`, `instagram` | string | fact/personal | Public contact for the access point |
| `status` | enum | fact | `active`, `seasonal_closed`, `closed`, `unverified` |
| `first_seen`, `last_verified` | date | fact | |

## Table: `service_areas`

| Field | Type | Class | Notes |
|---|---|---|---|
| `producer_id` | string | fact | FK |
| `county_fips` | string | fact | |
| `basis` | enum | fact | `home_base`, `pickup`, `market`, `store`, `delivery`, `manual` (`pickup` comes from a producer's pickup points; `market` comes from `market_vendors` through the market's location, `store` from `outlet_suppliers` through the outlet's location) |
| `derived` | bool | fact | True when computed from producer locations. Rebuilt on every release |

A county filter matches a producer when any `service_areas` row for that county exists.
Apps may label `home_base` as "Grows here" and the other bases as "Sells here".

## Table: `source_links`

Per producer, market or outlet, links to the original listings. Apps may pull display content from these links.

| Field | Type | Class | Notes |
|---|---|---|---|
| `record_type` | enum | fact | `producer`, `market`, `outlet`, `access_point` |
| `record_id` | string | fact | FK |
| `source` | string | fact | `producer_site`, `usda_lfd`, `colorado_proud`, `cfma`, `chaffee_provides`, … |
| `url` | url | fact | The listing page |
| `source_record_id` | string | fact | Stable ID at the source, for change detection |
| `last_seen` | date | fact | Last time the link worked |
| `link_status` | enum | fact | `ok`, `redirect`, `dead`, `unchecked` |

## Table: `field_sources`

Provenance for each populated field. Attribution for the public release is built from this table.

| Field | Type | Notes |
|---|---|---|
| `record_type` | enum | `producer`, `market`, `outlet`, `access_point`, `location`, `producer_location`, `market_vendor`, `outlet_supplier` |
| `record_id` | string | |
| `field` | string | e.g. `phone` |
| `source` | string | Source name |
| `source_url` | url | |
| `verified_by` | string | Source, partner or `producer` |
| `verified_on` | date | |

## Vocabularies

- **Categories** follow the existing labels (Farmers' Market, On-Farm / Ranch Sales, Meat Producer &
  Packer, Farm Products (online), Agritourism, CSA Farm, Roadside Market, U-Pick, Garden Center /
  Greenhouse, Winery, Grocery Store, Farm Store, Bakery, Food Maker, Restaurant, Caterer, Wholesale
  Grower, Food Hub, Food Bank, Community Food Hub, Organization), plus the badge "Sells to Schools".
  The Farm Trail's map groups are an app concern and stay in the app.
- **Products** reuse the normalized product list from the Farm Trail data.
- Colorado-specific attributes (for example Colorado Proud membership) go in a separate
  `state_attributes` table, never in the core tables.

## What a producer homepage reads

One producer row, its locations via producer locations (home base pin), its markets via `market_vendors`
(market pins), its outlets via `outlet_suppliers` ("where to buy" and "where to eat"), service areas for
the county list, `source_links` for the "More from the source" links, and `google_place_id` for
the Maps directions link and optional live photos.

## Public release rules

Public export drops `source_prose` and `personal` fields, applies `hide_address` and
`opted_out_fields`, and writes the sources into the release notes. Removed producers appear
as ID only.

## Mapping from today's data

| Today (Phase 2 raw CSV) | Becomes |
|---|---|
| Business Name, Category, Phone, Website, Email, Facebook, Instagram, Hours, Months Open, Products, Certified Organic, SNAP, ADA Accessible, Call first? | `producers` |
| Address, City, Zip, County, Latitude, Longitude, Geo Source | `locations` (kind `farm`, or `market_site` for a market's location) |
| Records categorized "Farmers' Market" | `markets` (not `producers`), each with its `location_id` |
| Where to Get It | `outlet_suppliers`, once each named store or restaurant is resolved to an `outlets` record |
| Records categorized Grocery Store, Farm Store, Garden Center / Greenhouse, Restaurant, Caterer, Food Truck, Cafe / Coffee Shop | `outlets` (not `producers`), each with its `location_id` and a `kind`. A record that is also a producer (a bakery with a cafe) becomes one `producers` row and one `outlets` row |
| Market vendor lists (Phase 3 prospects) | `market_vendors` (with `year`) |
| Notes | Dropped from the public release; the link goes in `source_links` |
| Source, Source ID, Source Updated, Provenance | `source_links`, `field_sources` |
| Possible Dup Of, dedup decisions | Merge decisions and `id_aliases` |

## Open questions

1. **Hubs, food banks and organizations.** Producers, markets, outlets and food access points (fridges first) are in v1. Food hubs and
   support organizations are not producers or outlets. Plan: an `organizations` table in v2, designed
   together with the supply-network graph in the food guide. Pantries and meal sites can move into `access_points` whenever wanted.
2. **Hours:** how much of the existing free-text hours can be structured automatically versus
   left in `hours_text`?
3. **Producer-submitted fields:** which ones can a claimed producer edit directly (description,
   photo, hours) versus only propose changes to?
4. **Multiple home bases:** a producer with two farms gets two `home_base` producer locations. Is that fine, or
   should one be primary?
5. **Merged duplicates:** define an `id_aliases` table (`old_id`, `new_id`, `merged_on`) and the
   convention for multi-value fields in CSV (`;`-separated, with hours in their own table).
6. **Producer that is also an outlet.** A bakery with a café is one `producers` row plus one `outlets`
   row sharing a location. Is linking them with an optional `producer_id` on the outlet enough?
7. **Outlet claims at scale.** `outlet_suppliers` rows need a source and date. Should the public release
   hide rows older than a set age (for example 18 months) unless re-observed? Dining kinds probably
   need a shorter limit than retail kinds.
8. **Institutions** (schools, hospitals) that buy local food fit neither dining nor retail kinds. Plan:
   decide with the `organizations` table in v2.
