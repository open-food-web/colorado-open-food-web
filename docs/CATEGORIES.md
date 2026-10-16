> Moved from the Colorado Farm Trail repo on 2026-10-15. File paths in this document may still use the old layout (`source-data/`, `data-compiled/`); the raw material now lives in the private sources repo, and inputs, snapshots and tables in this repo.

# Categories

The data set covers the local food system: anything that produces, makes, distributes,
sells or serves food, or supplies the people who do. No entity is too large or too small
if a category fits it, and if none fits we add one. What a *public* application shows is
a separate decision (see "Data versus display" below).

Rules live in `scripts/scrape/categories.py` (data label -> filter group) and are enforced
by `scripts/tests/test_categories.py`. A record can carry several labels, primary first.

## Labels

| Role | Label | Use for |
|---|---|---|
| Grow | On-Farm / Ranch Sales, Farm Products (online), Roadside Market, U-Pick, CSA Farm, Agritourism, Wholesale Grower | existing |
| Grow | **Flower Farm** *(new)* | cut-flower and other flower growers |
| Grow | **Plant Nursery** *(new)* | nurseries, native-plant growers, greenhouses selling plants (retail garden centers keep `Garden Center / Greenhouse`) |
| Grow | **Seed Company** *(new)* | seed growers and sellers |
| Make | Food Maker, Bakery, Winery, Meat Producer & Packer | existing |
| Make | **Cottage Food** *(new)* | home-based licensed food makers (jams, baking, dips, ferments) |
| Make | **Food Processor** *(new)* | custom processors, mills, dairies and plants that process others' product |
| Make | **Brewery / Distillery** *(new)* | breweries, distilleries, cideries |
| Distribute | Food Hub, Community Food Hub | existing |
| Distribute | **Distributor / Aggregator** *(new)* | wholesalers, distributors, resellers and aggregators of local product |
| Distribute | **Market Vendor** *(new)* | verified producers who sell through farmers markets and have no separate sales location |
| Sell / serve | Farmers' Market, Farm Store, Grocery Store, Restaurant, Caterer | existing |
| Sell / serve | **Apothecary** *(new)* | herb and apothecary shops that sell herbs, honey, seeds and the like (Copper Kettle Apothecary). An outlet, filed under Shops & Grocers |
| Sell / serve | **Food Truck**, **Cafe / Coffee Shop** *(new)* | mobile and counter-service food businesses |
| Support | **Agricultural Education** *(new)* | sites whose main work is teaching about farming and ranching: learning centers, working-farm schools, demonstration farms (Hutchinson Homestead & Learning Center). A record may also sell, and then carries its sales channels |
| Support | Food Bank, Organization | existing |
| Support | **Ag Input Supplier** *(new)* | feed, soil, compost, worm castings, equipment |

Not yet categories (add when records need them): institutional buyers (schools,
hospitals), livestock merchants, hay and forage, cideries separate from breweries.

## Suggested mapping for Colorado Proud business types
Today the Colorado Proud importer only keeps the types in `TYPE_CATEGORIES`. These
currently unmapped types now have a home (counts from `category_counts.csv`):

| Colorado Proud type | New label |
|---|---|
| Food Manufacturer (243), Manufacturer (105) | Food Maker / Food Processor |
| Wholesaler (95), Distributor (33), Merchant / Merchandiser (19), Wholesale Market (13), Buyer | Distributor / Aggregator |
| Food Truck (64), Mobile Food Stand / Cart (27) | Food Truck |
| Coffee Shop (34) | Cafe / Coffee Shop |
| Brewery (21), Distillery (19), Beer | Brewery / Distillery |
| Ag Input Supplier (20) | Ag Input Supplier |
| Retailer (101) | needs a look (retail of what?) |

Importing these is a separate step: it would add several hundred records.

## Data versus display
The data set may hold every location; applications filter. A public map shows only
places that advertise a sales channel. New labels are in the data but a group only appears
on the live map once `index.html` styles it (unstyled groups are skipped), so adding a
category never changes the public map by itself.

### Display flags (raw export)
Carried on curated records and written to `co_farmers_markets_all_raw.csv` only (the My Maps CSV
keeps its 23 columns):

| Column | Values | Meaning |
|---|---|---|
| Public Listing | yes / no / unknown | The business advertises a sales channel, so a public app may show it |
| Local Sales Channel | yes / no / unknown | It has a local channel (farm stand, market, CSA pickup, local delivery, local retail). Online-only national sellers are `no` |
| Sales Channels | list | `on_farm`, `farm_stand`, `farmers_market`, `csa`, `delivery`, `wholesale`, `retail_partners`, `online` |
| Sales Locations | text | Where it sells: markets, pickup points |
| Hide Address | yes / blank | Keep the full address and coordinates in the raw data; omit them from the public output (no map pin) |

`scripts/scrape/categories.py` also lists `PUBLIC_GROUPS`: the filter groups the public map
shows. Records whose only groups are newer ones (flowers, plants and seeds; processors;
breweries and distilleries; farm inputs; market vendors) are in the data but not on the public
map until the maintainer enables the group.
