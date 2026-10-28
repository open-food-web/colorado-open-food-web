# Producer type simplification: before and after

Date: 2026-10-28. Branch `producer-type-simplification`, rebased onto `main` at `4383dae` (it includes the Oct 20 check-in changes, #72). Compares the tables built from `main` with the tables built from this branch (same inputs; the only input edits are the `producer_type` values for Hutchinson Ranch, Mountain Goat Lodge and Old Elm Farm, below). Method: `data/colorado/producers.csv` joined on `producer_id`; the Chaffee slice is the statewide export with the site's scope applied (old scope on the old export, new scope on the new export).

## Summary

- Same **1209 producers** before and after. None added, removed or renamed.
- `product_groups`, `status`, `name` and `slug` are **identical for every producer** (0 differences). `sales_channels` are identical except that the new `agritourism` channel is added (192 producers); every other channel is unchanged (0 differences).
- `categories` is renamed `source_categories`; the values are identical for all 1209 producers (1209 match).
- The producer field `kind` is renamed `producer_type`; outlets, markets and access points keep `kind`.
- **Agritourism is a sales channel, not a producer type.** A farm that hosts visits is a farm. The type list is `farm`, `ranch`, `orchard`, `maker`, `bakery`, `winery`, `education`.
- **126 producers change producer type** (123 bakery moves, 3 one-offs). The Chaffee Provides slice keeps the same **27 producers, 3 markets, 4 outlets, 2 access points and 38 pins**; one producer type changes there (Hutchinson Ranch, see decisions).

## Producer type counts

| Producer type | Before | After |
|---|---|---|
| farm | 663 | 664 |
| ranch | 219 | 221 |
| orchard | 1 | 1 |
| maker | 281 | 157 |
| bakery | 3 | 126 |
| winery | 39 | 39 |
| agritourism | 2 | 0 |
| education | 1 | 1 |
| **Total** | 1209 | 1209 |

(`agritourism` was a type on `main` for 2 producers; it no longer exists.)

## Producer type changes

| From | To | Producers | Why |
|---|---|---|---|
| maker | bakery | 123 | Bakery-only labels (no On-Farm / Ranch Sales or Meat Producer) are now `bakery`, not `maker` |
| maker | ranch | 1 | Has the Meat Producer & Packer label; that rule now comes before maker (FARMER GAVIN) |
| agritourism | ranch | 1 | Hutchinson Ranch: set by hand to match Guidestone's Oct 20 note (see decisions) |
| agritourism | farm | 1 | Old Elm Farm: the hand-set type `agritourism` no longer exists; it is a farm (see decisions) |

<details><summary>maker to bakery (123)</summary>

A Kitchen Mouse, Anita's Pantry & Produce / Palisade Pies, Aqua Duck Farms L.L.C., Aspen Baking Company, Azula home bakery, B sweet cupcakes, BakeOff LLC, Baklava Unlimited, Baklava Unlimited, Because I Love You Dog Treats, Bessemer Bread Co. LLC, Biscotti Hound Dog Biscuit Bakery, Black Forest Brownies, Blossom Bakery LLC, Blossom.Baking, Bly Ranch, Bollinger Breads, Books on Main, Bougie Tailz, Bread In The Box LLC, Bread Truck Bakery, Bully Boy Baking, Busy Green Bee, Buttah Bakehouse, Camille's Yum Bites, LLC, CastleDough, Chalk and Flour, Colorado Stroopwafels LLC, Confections by Charlee LLC, Crafton's Summit Sourdough, Crusty Batch Sourdough, Daily Grains, Dianes's Delights, Dot's Pizzelle Cookies, Ever Risen Bakery, Fig & Olive Bakery, Filomena's Fresh Forno, Furry Feet Bakery, Gammy's Baklava, Great Harvest Bread Co & Yogurt Shack, Greek Delicious & Monica's Chocolate Creations, Happy Hippie Breads, Hearth and Crunch LLC, Hey, Good Lukken!, Homemade by Hammett, HooRayRay's, Jewels' Edible Gems, Jon-a-thins, Lazar Family Bakehouse, Little Finch, Little Spouse Bread House, Lunch Wired, Maggie’s Bread and Butter LLC, Marketplace Bakery, Miette et Chocolat, Milk and Honey Coffee, Mill Haus Coffee, Mimi's Place Cottage Bakery, Mountain Oven Organic Bakery, Mountainside Bakery, Moxie Bread Co, Nathy’s Cake Shop, NoCo Gluten Free Bakeshop, Northern Cowgirl & Company, OVER THE MOON EMPORIUM, Olive & Finch - Uptown, Outside the Breadbox, Oven Spring, Home Kitchen, Paula's Cozy Kitchen LLC, Pauline's Bonafide Baking, Peak & Petal, Peak and Crumb Bakery LLC, Purebread Doughs, Queen Bee Sweets & Treats LLC, Rampart Bakehouse, Real Deal Baked Goods, Renee the Baker, Rocky Mountain Barkery, Romero Mexican Wedding Cookies, Rudi's Bakery, SauerDough Bakes, Scratch Dough Co, Slavinka Food, Something Cute Co., Sourdough by Tori, Stretch and Fold Sourdough Co., Styria Bakery II, SugarBee Cookie Company, Sun Mountain Bakery, Sunflower Cottage Foods, Sunflower Sourdough Ltd., Superior Sweets, Susan Cochran, Sweet Chaos LLC, Sweet Diplomacy, Sweet P's Bakery LLC, Sweet Street, LLC, Sweet and Savory, Sweetened Patisserie, THE PERUVIAN COOKIE COMPANY LLC, Tart and Soul Bakery, Teal Velvet Bakery, The Baked Cottage Bakery, The Bread Chic, The Cookie Coven, The Crumb Keeper, The Daily Knead, The Dyna, The Mill Bakery LLC, The Sweetest Bean, This is a test, Inc., Three Cubs Bakehouse, Three Little Pigs Bakery, Tumbleweed Bread, Venezuela dulce LLC, Vollmer's Bakery, Wilde Cookie Compant, Wildflower & Wheat LLC, XLVII's Bakery/ 47 Bakery, Yampa Valley Made, Your Peak Energy, colorado kolache company, izzio artisan bakery

</details>

<details><summary>maker to ranch (1)</summary>

FARMER GAVIN

</details>

<details><summary>agritourism to ranch (1)</summary>

Hutchinson Ranch

</details>

<details><summary>agritourism to farm (1)</summary>

Old Elm Farm

</details>

## Decisions made in this change

- **Agritourism becomes a sales channel** (`agritourism`: visits, lodging, events, classes). All 192 producers carrying the Agritourism source label get it, including the multi-label farms that only had it in `source_categories`. It is not a way to buy food, so it is ignored when deciding whether a producer's sales channels are known (home pins, readiness).
- **Hutchinson Ranch: `agritourism` to `ranch`.** Guidestone's Oct 20 check-in notes ask for it to be a ranch ("At the Ranch"). It stays on the Chaffee map. The Oct 15 override row that calls it "not a working ranch" is left in place as history.
- **Old Elm Farm: `agritourism` to `farm`** (it was hand-set to `agritourism`, a type that no longer exists).
- **Mountain Goat Lodge: type `farm`.** It is excluded from Chaffee Provides by an `exclude_slugs` entry in the site's `scope.json` (Guidestone does not want agritourism there), not by its type.

## Chaffee Provides slice

Statewide export (format 2) with `scripts/scope.json` applied (`exclude_producer_types` bakery; `exclude_only_channels` wholesale; `exclude_slugs` includes Mountain Goat Lodge; the old `include_categories` allowlist is gone). The slice includes the Oct 20 changes already on `main` (Winter Farmers Market, Scanga as a grocery, the closures).

| | Before | After |
|---|---|---|
| Producers | 27 | 27 |
| Markets | 3 | 3 |
| Outlets | 4 | 4 |
| Access points | 2 | 2 |
| Pins | 38 | 38 |

Same producers; every field other than the producer type (and the new agritourism channel on a few farms) is identical; the only type change is Hutchinson Ranch (agritourism to ranch).

## Other changes in the PR

- `scripts/build_tables.py`: new `producer_type()` rules, `source_categories` column, `PRODUCER_TYPES`, field renamed from `kind` to `producer_type`, `--producer-types`, the `agritourism` channel.
- `inputs/producer_kinds.csv` is now `inputs/producer_types.csv` (column `producer_type`).
- `scripts/export_app.py`: `format_version` 2; `categories` dropped from producers; the producer `kind` field is now `producer_type` and `vocab.kinds` is now `vocab.producer_types` (outlets, markets and access points keep `kind`); config keys `include_producer_types` / `exclude_producer_types` / `exclude_only_channels` / `exclude_only_source_categories` replace `include_categories` / `exclude_categories`.
- `scripts/readiness.py`, `scripts/change_report.py`, `scripts/make_release.py`: follow the rename.
- `tests/test_producer_type.py`: every producer label lands in a producer type or a channel; sample types; agritourism is a channel; the tables have only valid producer types and no `categories` column.
- `docs/SCHEMA.md`, `EXPORTS.md`, `CATEGORIES.md`, `PROPOSAL_PRODUCER_TYPE.md` and the README (new section "How a producer is described") updated; `exports/open-food-web.config.json` scoped by producer type and channel.

## The Food Web project site

`site/` (the statewide map and directory, #50) reads the same export, so it moves to format 2 in this PR (`site/assets/app.js`: `supportedFormat` 2, reads `producer_type`, no `categories`). Its scope file, `exports/open-food-web.config.json`, now says `exclude_producer_types: [bakery]` and `exclude_only_source_categories: [Agritourism]` (a provenance-based rule: a producer is left out only when Agritourism is the only directory label the sources gave, as before). Result on the statewide map: every producer the old rule excluded is still excluded, and **18 more are excluded** because they are now typed `bakery` (they carried Bakery plus Food Maker labels and were `maker` before).

## Not changed

- `directory.csv` still carries the source `Category` column (built from the raw rows), so the Farm Trail's 23-column layout is unchanged.
- **On-Farm / Ranch Sales is not turned into a `farm_stand` channel.** The proposal first said it would be; the build never did that, and doing it would pin hundreds of farm addresses (many are homes). It only informs the type (farm or ranch).
- The extra labels in `CATEGORIES.md` (Flower Farm, Plant Nursery, Brewery / Distillery and so on) are still not producer labels in the build; they are mapped in the proposal for when they are.
- The Meat Producer & Packer split (ranch versus processor) is not done; all of them still map to `ranch`.
