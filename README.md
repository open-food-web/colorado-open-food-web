# Colorado Open Food Web

A free, open, community-maintained dataset of how Colorado's food connects: the people who produce
it, and the markets, restaurants and stores where it is sold or served.

The name has two meanings. A food web maps who feeds whom. And the dataset is built by gathering
what is already published on the web, linking it together, and showing it in new ways.

> **Status: draft, pre-release.** The charter and schema are being settled. No data has been
> published yet. See [docs/CHARTER.md](docs/CHARTER.md).

## Why

Information about Colorado's local food is scattered across state programs, federal directories,
market associations, county nonprofits and individual websites. Each holds a piece, none agrees
with the others, and each goes stale on its own schedule. Every app that wants to help someone
find local food rebuilds the same list. This project builds it once, keeps it accurate in the
open, and shares it.

## What is in it

One record per **producer**, linked to the **locations** they operate from, the **markets** they sell
at, and the **outlets** (restaurants, grocers, farm stores) that carry their food. Counties
served are derived from those links, so a county filter finds producers who come in as well as
those who grow there. Every field records where it came from and when it was last checked.

| Record | What it is |
|---|---|
| Producer | A farm, ranch, orchard, maker, bakery or winery (its producer type). One record, one stable page |
| Market | A recurring multi-vendor gathering at one location |
| Outlet | A restaurant, caterer, food truck, cafe, bar, grocer, farm store or garden center, with a `kind` |
| Location | A physical location with an address and coordinates |

Full field list: [docs/SCHEMA.md](docs/SCHEMA.md).

## How a producer is described

A producer is described by four separate answers, so a listing never has to squeeze several ideas into one
label. Counts are producers in the Oct 2026 statewide tables (1,209). Details and the reasoning:
[docs/PROPOSAL_PRODUCER_TYPE.md](docs/PROPOSAL_PRODUCER_TYPE.md) and [docs/SCHEMA.md](docs/SCHEMA.md).

| Question | Field | Shape |
|---|---|---|
| What is this business? | `producer_type` | One value, from the list below |
| How can the public buy from it? | `sales_channels` | Any that apply |
| What does it make or grow? | `product_groups` | Any that apply |
| What can a visitor do there? | `visits` | Any that apply (farm stand, tour, u-pick, volunteer, by appointment) |

### Producer types

One required value per producer. It sets the label and pin on a map. Set by hand in
`inputs/producer_types.csv`, otherwise derived from the source labels (`producer_type()` in
`scripts/build_tables.py`).

| Producer type | What it means | Producers |
|---|---|---|
| `farm` | A farm that grows vegetables, fruit, flowers, herbs, mushrooms or mixed crops, and the default when nothing more specific applies. Includes farms that also host visits (agritourism) or sell through a CSA or farm stand | 664 |
| `ranch` | A working ranch that raises livestock for meat, eggs or dairy, including businesses labeled Meat Producer & Packer | 221 |
| `maker` | A business that turns ingredients into food or drink for sale: preserves, sauces, cheese, honey syrups and similar. Not a bakery or winery | 157 |
| `bakery` | A business whose only label is Bakery or Bakery plus Food Maker: bread, pastry, baked goods. A bakery that also sells from a farm stays a `farm` | 126 |
| `winery` | Wineries and vineyards | 39 |
| `orchard` | A tree-fruit orchard. Set by hand; no source label implies it | 1 |
| `education` | A site whose main work is teaching about farming and ranching. It may also sell | 1 |

Markets, outlets (restaurants, grocers, farm stores, garden centers) and food access points are
different record types with their own `kind`; they do not have a producer type.

### Sales channels

How the public can buy. Check any that apply; blank means not yet confirmed, and `none` means confirmed no
public sales.

| Channel | What it means | Producers |
|---|---|---|
| `farmers_market` | Sells at one or more farmers markets | 233 |
| `agritourism` | Visits, lodging, events or classes at the farm. Not a way to buy food | 192 |
| `farm_stand` | On-farm sales: a stand, store or open hours at the farm | 119 |
| `csa` | Sells subscription shares (community supported agriculture) | 106 |
| `online` | Takes orders through its own website or shop | 60 |
| `wholesale` | Sells to restaurants, shops or other businesses | 43 |
| `u_pick` | Customers pick their own | 22 |
| `delivery` | Delivers to customers | 14 |
| `retail_partners` | Sold in other businesses' stores | 13 |
| `pickup` | Off-farm pickup points | 4 |
| `none` | Confirmed: no public sales | 1 |

### Product groups

The short list people search by. Found from the products text and what the business ticked; the producer's
own wording stays in `products`.

| Group | What it covers | Producers |
|---|---|---|
| `veggies` | Vegetables, greens, produce, microgreens, pumpkins | 295 |
| `beef-meat` | Beef, pork, lamb, bison, sausage, jerky | 287 |
| `baked-goods` | Bread, pastry, cookies, pies | 241 |
| `poultry-eggs` | Chicken, turkey, duck, eggs | 188 |
| `garlic-herbs` | Garlic, herbs, spices | 158 |
| `fruit` | Tree and berry fruit, melons, grapes | 149 |
| `honey` | Honey, beeswax, bee products | 144 |
| `flowers` | Cut flowers, bouquets, lavender | 117 |
| `drinks` | Wine, cider, beer, juice, coffee, tea, kombucha | 111 |
| `dairy` | Milk, cheese, yogurt, ice cream, butter | 70 |
| `mushrooms` | Culinary mushrooms and growing supplies | 60 |
| `seeds-plants` | Seeds, seedlings, plant starts, nursery plants | 33 |

### Source category labels

The labels the source directories (Colorado Proud, USDA, CFMA, county programs) give a business. They are kept
as `source_categories` for provenance and to decide the record type, and they feed the producer type and sales
channels above. Apps should use the fields above, not these.

| Source label | What it says | Becomes | Producers |
|---|---|---|---|
| On-Farm / Ranch Sales | Sells directly at the farm or ranch | Type `farm` or `ranch` by name and products. Not turned into a channel | 575 |
| Food Maker | Makes prepared food or drink | `maker` (unless the business also has farm sales) | 217 |
| Agritourism | Visitors, lodging, events | `agritourism` channel; the type stays `farm` or `ranch` | 192 |
| Bakery | Bakery | `bakery` (unless the business also has farm sales) | 132 |
| Meat Producer & Packer | Raises, processes or packs meat | `ranch`; `beef-meat` product group | 115 |
| Roadside Market | A roadside stand or farm market | `farm_stand` channel | 104 |
| CSA Farm | Offers CSA shares | `csa` channel | 101 |
| Winery | Makes wine | `winery` | 39 |
| Wholesale Grower | Grows for wholesale buyers | `wholesale` channel; type `farm` | 33 |
| Farm Products (online) | Sells farm products online | `online` channel | 31 |
| U-Pick | Customers pick their own | `u_pick` channel | 22 |
| Agricultural Education | Teaching farm or ranch | `education` | 1 |

Other labels in [docs/CATEGORIES.md](docs/CATEGORIES.md) (Flower Farm, Plant Nursery, Brewery / Distillery and so on)
are recognized in the sources but are not yet producer types.

## Principles

- **Open.** Data under CC BY 4.0, code under MIT.
- **Facts only.** No copied descriptions or other third-party text. Records link to their sources instead.
- **Provenance over volume.** A field is filled only when a source states it.
- **Producer-centered.** Producers can claim, correct or remove their record.
- **Colorado first.** Built so other states could adopt the same model later.

## Built on it

- **[Colorado Farm Trail](https://coloradofarmtrail.com)**: a map-first guide to local food.
- **CSA finder**: in development.

## Contributing and partners

Not open for contributions yet. If you run a regional food project, directory or market and want
to share data or help keep it accurate, open an issue or get in touch once the repo is public.

## Licensing

See [LICENSING.md](LICENSING.md). Third-party sources keep their own terms; this project publishes
facts and links, not their content.
