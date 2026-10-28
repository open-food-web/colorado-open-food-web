# Proposal: producer type simplification (one answer to "what is this business?")

> Status: **implemented in the same PR** (single cutover, export `format_version` 2). See `reports/2026-10-28-producer-type-simplification.md` for the before/after.
> Follows [`SCHEMA.md`](SCHEMA.md) and [`CATEGORIES.md`](CATEGORIES.md).

## Problem

A producer carries two fields that try to answer the same question, and the second one also answers two other questions:

- `kind` (one value, now renamed `producer_type`): `farm`, `ranch`, `orchard`, `maker`, `winery`, `agritourism`, `education`. (`agritourism` was dropped as a type before release: it is a sales channel.)
- `categories` (a list): the directory labels from the source data.

Counts from the Oct 2026 tables (1,235 producers):

| Primary category | Producers | `producer_type` it ends up with |
|---|---|---|
| On-Farm / Ranch Sales | 480 | 359 farm, 118 ranch, 3 other |
| Food Maker | 155 | 153 maker, 2 farm |
| Agritourism | 139 | 120 farm, 16 ranch, 3 other |
| Bakery | 125 | 122 maker, 3 bakery |
| Meat Producer & Packer | 82 | 81 ranch, 1 maker |
| CSA Farm | 81 | 78 farm, 3 ranch |
| Roadside Market | 64 | 55 farm, 6 maker, 3 other |
| Winery | 37 | 37 winery |
| Wholesale Grower | 25 | 25 farm |

Three things are wrong with this:

1. **`producer_type` is mostly derived from `categories`.** `producer_type()` in `scripts/build_tables.py` guesses it from the
   category and the name unless `inputs/producer_types.csv` sets it. Two fields, one idea.
2. **`categories` mixes three different questions.** *What is the business* (Food Maker, Winery, Bakery, Meat Producer &
   Packer), *how does it sell* (CSA Farm, Roadside Market, U-Pick, Farm Products (online), Wholesale Grower, On-Farm / Ranch
   Sales) and *what else does it do* (Agritourism, Agricultural Education). The second group duplicates `sales_channels`
   (`csa`, `farm_stand`, `u_pick`, `online`, `wholesale`), which the schema already has.
3. **Nobody can answer it in a form.** A producer asked to pick "categories" has to choose between "On-Farm / Ranch
   Sales" and "Roadside Market", which describe the same stand. Corrections end up as overrides (Scanga, Alpenglow).

## Proposal

Keep three separate questions, each with one home:

| Question | Field | Shape |
|---|---|---|
| What is this business? | `producer_type` | One required value from a defined list |
| How can the public buy from it? | `sales_channels` | Checklist (already exists) |
| What does it make or grow? | `product_groups`, `products` | Controlled lists (already exist) |
| What else can a visitor do there? | `visits` | `type\|detail` entries (already exist): `tour`, `volunteer`, `u_pick`, `farm_stand`, `by_appointment` |

and retire `categories` as a stored, edited field on producers.

### The producer types

`farm`, `ranch`, `orchard`, `maker` (food maker, including bakery sub-type), `bakery`, `winery`, `brewery_distillery`,
`processor`, `nursery`, `education`. Agritourism is a sales channel, not a type.
Wording and the exact list are for the maintainer; the point is one defined list with one value per producer.
Markets, outlets and access points keep their own `kind`.

### Mapping from today's categories

| Today's category | Becomes |
|---|---|
| On-Farm / Ranch Sales | `producer_type` from the name/products (farm or ranch). **Not turned into a channel**: deriving `farm_stand` from this label would pin hundreds of farm addresses (many are homes) |
| Roadside Market | `sales_channels` += `farm_stand` |
| U-Pick | `sales_channels` += `u_pick`; `visits` += `u_pick` |
| CSA Farm | `sales_channels` += `csa` |
| Farm Products (online) | `sales_channels` += `online` |
| Wholesale Grower | `sales_channels` += `wholesale`; `producer_type` farm |
| Meat Producer & Packer | `producer_type` ranch (or `processor` when it processes others' product); `product_groups` += `beef-meat` |
| Food Maker | `producer_type` maker |
| Bakery | `producer_type` bakery |
| Winery | `producer_type` winery |
| Agritourism | `sales_channels` += `agritourism` (visits, lodging, events, classes); the type stays farm or ranch |
| Agricultural Education | `producer_type` education |
| Flower Farm, Plant Nursery, Seed Company, Cottage Food, Food Processor, Brewery / Distillery (new labels in `CATEGORIES.md`) | `producer_type` farm + `product_groups` flowers; `nursery`; `farm`; `maker`; `processor`; `brewery_distillery` |

Most rows are a straight rename, which is the evidence for the change: the information is already in `sales_channels`,
`product_groups` and `producer_type`.

### What happens to `categories`

- **Inside the pipeline** the source labels stay as `source_categories` (what Colorado Proud, USDA and CFMA called the
  business), because the importers need them. They are provenance, not something people edit.
- **In `producers.csv`** the column is renamed `source_categories` (provenance only; readiness and the drop-in inference still
  read it). **In the export** `categories` is removed outright. No app is live yet, so there is no reason to carry it for a
  deprecation period.
- **`directory.csv`** may keep a `Category` column derived from the new fields if the Farm Trail still wants the old
  23-column layout; that is the Farm Trail's decision, not a constraint on the model.

## Why it matters for maintenance

- A submission form asks **"What best describes your business?"** (one choice, `producer_type`), **"How do you sell?"**
  (checkboxes, `sales_channels`) and **"What do you make or grow?"** (`product_groups`). Each answer maps to exactly
  one field, so a form submission becomes a single clear row in `inputs/`.
- Partners such as Guidestone no longer have to choose among overlapping labels, and the map's single label and
  pin stay unambiguous.
- Scope rules in apps move from category allowlists to something people can reason about (for example "producer types farm,
  ranch, orchard, maker, winery, bakery with any sales channel").

## What has to change

| Area | Change |
|---|---|
| `scripts/build_tables.py` | Replace `PRODUCER_CATS` and `producer_type()` with the mapping above; read the new `producer_type` from `inputs/producer_types.csv` first |
| `scripts/scrape/categories.py`, `docs/CATEGORIES.md` | Keep as source-label vocabulary; add the mapping table |
| `scripts/export_app.py`, `docs/EXPORTS.md` | `include_categories`/`exclude_categories` become `include_producer_types`/`exclude_producer_types` plus channel filters; format version bump |
| `scripts/make_release.py` | Derive the `directory.csv` `Category` column |
| `scripts/tests/test_categories.py` | Test the mapping is total: every existing category lands somewhere |
| Apps (Chaffee Provides, Farm Trail) | Neither is live, so both move in the same change window. Chaffee's `scripts/scope.json` uses `include_categories` and moves to producer types; its pin and label code reads the producer type (the site code is renamed from `kind` in the same change). The Farm Trail moves to the new export or keeps a derived `Category` column |

## Rollout

Because no app is live, this is one cutover, not a staged migration:

1. **Food Web:** one PR adds the mapping, the new `producer_type` values and derived channel fields, drops `categories` from the
   tables and export, bumps the export `format_version`, and updates `SCHEMA.md`, `CATEGORIES.md` and `EXPORTS.md`.
   A test checks the mapping is total (every existing category lands somewhere) and that no producer loses a sales
   channel or product group.
2. **Review of the data:** the PR includes a before/after report of how many producers change `producer_type` (expected to be
   few, since `producer_type` is already set for most), and a list of the records that need a human decision (see
   Meat Producer & Packer below).
3. **Apps:** a release with the new format is cut, then Chaffee Provides and the Farm Trail each take one PR to
   read it. Chaffee Provides is the first consumer and tests the new scope rules.

## Risks and open questions

- **Businesses with two identities** (a bakery that is also a farm; a ranch with a farm store). The proposal keeps one
  `producer_type`, plus `sales_channels` and `visits` for the rest. If one value is too tight, allow an optional second type.
- **Meat Producer & Packer** covers ranches that sell beef and plants that process others' meat. Splitting them needs a
  review of the 82 records.
- **Format version.** Removing a field from the export is a breaking change, and the version bump makes apps refuse the
  new file until they are updated (the sync script already does this). That is acceptable now and would not be once an
  app is live, which is the reason to do it now.
- **Vocabulary ownership.** Who may add a `producer_type` value? Suggest the maintainer, via a PR to this document.
- **Outlets and markets** are unchanged: they already use `producer_type` and have no `categories`.
