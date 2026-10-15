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
| Producer | A farm, ranch, orchard, maker or winery. One record, one stable page |
| Market | A recurring multi-vendor gathering at one location |
| Outlet | A restaurant, caterer, food truck, cafe, bar, grocer, farm store or garden center, with a `kind` |
| Location | A physical location with an address and coordinates |

Full field list: [docs/SCHEMA.md](docs/SCHEMA.md).

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
