# Colorado Open Food Web — Project Charter (DRAFT)

> Name: Colorado Open Food Web (chosen 2026-10-14; domain and trademark not yet checked).
> Status: draft for maintainer review. Nothing here is published.
> Licensing and partner agreements are deliberately deferred (see "Not yet").

## What it is

**Colorado Open Food Web** is a free, open, community-maintained dataset of how Colorado's food
connects: the people who produce it, the markets, restaurants and stores where it is sold or served,
and the places and counties in between.

The core unit is the **producer**: one producer, one record, one stable page. Markets and outlets
(restaurants, grocers, farm stores) are their own record types. Locations, and the links between all
of them, are what make it a web rather than a list.

### Why "food web"

Two meanings, both intended:

- **The ecological one.** A food web maps who feeds whom. The dataset does the same for a local
  food system: producers supply markets and outlets, markets and outlets reach counties.
- **The internet one.** It is built mainly by gathering what is already published on the web
  (state and federal directories, market and association sites, producers' own pages), linking it
  together, and showing it in new ways. Records point back to those sources rather than copying
  them.

## Why it exists

Information about Colorado's local food is scattered across state programs, federal
directories, market associations, county nonprofits, and individual websites. Each holds a
piece, none agrees with the others, and each goes stale on its own schedule. Every app that
wants to help someone find local food has to rebuild the same list from scratch.

The Food Web exists so that list is built once, kept accurate in the open, and shared.

## What it seeks to create

1. **One trustworthy record per Colorado producer**, merged from many sources, with every
   field traceable to where it came from and when it was last checked.
2. **A shared picture of where food is available**: where a producer grows, where they sell,
   and which counties they serve, including producers with no public location (online-only,
   market-only, wholesale).
3. **A neutral foundation others can build on**: maps, guides, trip planners, school and
   food-assistance tools, research. Free to use, with stable IDs and a versioned schema so
   builders aren't broken by changes.
4. **A maintenance model that doesn't depend on one person**: agencies, nonprofits, market
   managers, and producers themselves can confirm and correct their own information.

## Principles

- **Open by default.** Free to use, free to reuse, open to inspect. Code and process are public.
- **Producer-centered.** Producers can see, claim, correct, or remove their record.
- **Provenance over volume.** A field is filled only when a source states it. Nothing is
  guessed. Every field carries its source and verification date.
- **Neutral and unbranded.** The Food Web is infrastructure, not a consumer brand. It does not
  rank, promote, or editorialize.
- **Separate from the apps.** The data is maintained independently of any product built on it.
- **Clean content.** The Food Web contains no copyrighted text and no personal information
  beyond what a business has itself made public for customers (see "Release design").
- **Partners over scraping.** Where a source can become a partner, it should.

## What it is not

- Not a consumer app or a map. (The Colorado Farm Trail is one app built on it.)
- Not a marketplace, review site, or ranking.
- Not a certification or endorsement of any producer.
- Not limited to farms: markets, ranches, orchards, food hubs and similar producers all belong.

## What it produces

| Output | Description |
|---|---|
| **Producer records** | One per producer: name, categories, products, contact, sales channels, verification status. Facts only (see "Release design") |
| **Locations** | Physical spots with coordinates: farms, stands, markets, stores |
| **Producer locations** | How a producer relates to a location: home base, sells at market (season/days), stocked at store |
| **Service areas** | Counties a producer can be found in, derived from producer locations or set by hand |
| **Versioned releases** | Dated JSON/CSV exports plus a published schema |
| **A public change log** | What changed, from which source, when |

## Release design: facts only, sourced, linked

The public Food Web publishes **facts, not other people's prose**.

- **Published core:** name, location (address, coordinates, county), contact (phone, email,
  website, social links), categories, products and seasons as structured values, stable IDs,
  and sources.
- **Kept out:** descriptions, blurbs and "about" text copied from a directory or a producer's
  website. The record links to the original instead. Text the project writes itself, or text a
  producer submits to the Food Web, may be included.
- **Attribution:** every field records its source in the provenance data, and each release
  lists its sources.
- **Apps may pull from the links:** every record carries links to its original sources (the
  producer's own site, the directory listing). An app such as the Farm Trail may fetch and
  display content from those links, with attribution, if it wishes. That is the app's decision
  and responsibility under the source's terms, not the Food Web's.

**Personal information.** Many producers are sole proprietors whose farm is also their home.
The Food Web publishes only contact details the business itself makes public for customers: its website,
public phone, public address, and public email. For email this is checked, not assumed. An address is kept
only if it appears on the business's own website (found by a passive check of its home and contact pages,
re-checked twice a year). One that cannot be confirmed is not stored in the repository, only as a hash so it
is not checked again. The Food Web does not publish home addresses a producer has chosen to hide (a source's
"hide address" flag is honored and carried through), personal social profiles, names of individuals beyond
the business name, or anything gathered from sources that were not offered to the public. Any producer can
ask for a field or the whole record to be removed. Removal requests are honored and logged by ID only.

This keeps the open release low-risk while the source relationships are still being built, and
it holds up as sources are added: a source with unclear terms contributes facts and a link,
never a copied paragraph.

## Photos

The Food Web holds **no third-party photos**. For a location it stores only the `google_place_id`
(which Google permits) and, where a producer submits their own photo, the image link with
`photo_credit` and `photo_license`.

Apps may show Google Maps photos as live thumbnails by asking the Places API at view time, with
Google's required attribution and within its current display terms. Nothing is downloaded or
stored. The Farm Trail plans to do this on producer pages only, falling back to a placeholder
and a "See photos on Google Maps" link. Photo references from the API are temporary, so the data
never stores photo URLs.

**Launch plan:** the Farm Trail launches with the placeholder, the "See photos on Google Maps"
link and the stored Place ID. Live thumbnails come later, on producer pages only and loaded on
demand, behind a hard spending cap and budget alert in Google Cloud. Places API photos are billed
per request, so cost grows with page views.

## Relationship to the Colorado Farm Trail

The Farm Trail is the first and reference consumer. It reads the Food Web and adds the
experience layer: the map, producer homepages, county pages, Google Maps directions, the food
guide, the CSA finder. Anything about *what is true of a producer* lives in the Food Web;
anything about *how it is shown or used* lives in the app.

## Who it serves

- **App builders** (Farm Trail, Chaffee Provides, and anyone else) who need accurate producer data.
- **Agencies and nonprofits** who maintain parts of the picture and want it shared and kept current.
- **Market managers** who know their vendors best.
- **Producers**, who get one location to be correct once and appear everywhere.
- **Researchers and planners** studying Colorado's local food system.

## Scope: Colorado first, a base model for the rest

The Food Web covers **Colorado only**. A statewide dataset is the right size to get accurate,
and it lets us prove the model with real partners before anyone asks for more.

If it works, the national step is a **spin-off, not an expansion**: a separate, state-agnostic
**Open Food Web** (working name) that uses the Colorado Open Food Web as its
base model. Colorado stays its own dataset with its own partners and maintainers; other states
would run their own on the same model.

What this asks of the design now, at almost no cost:

- **Nothing hard-codes Colorado in the structure.** State is a field; counties use standard
  FIPS codes; IDs are namespaced (for example `co-` plus a number) so records from different
  registries never collide.
- **The schema is published as a standalone, versioned spec**, separate from the Colorado data,
  so another state can adopt it unchanged.
- **Colorado-specific things stay labeled as such** (for example Colorado Proud membership is a
  state-program attribute, not a core field).
- **The tooling is reusable**: the merge pipeline reads source definitions, so a new state is new
  source configs, not new code.

We do not build any multi-state features until the Colorado Open Food Web is working.

## License

**Data: CC BY 4.0. Code: MIT.**

- CC BY asks only for credit, which agencies and nonprofits accept readily and which keeps
  partners and sources visible. Share-alike licenses (ODbL, CC BY-SA) would add friction for
  the partners and app builders we most want.
- It is compatible with upstream CC BY data (the USDA farmers market directory is listed under
  CC BY). CC0 would not be, since CC BY material cannot be relicensed as CC0.
- Version 4.0 covers database rights, so no separate database license is needed.
- The license covers only what the Food Web contributes. Third-party content keeps its own
  terms, which is why the release is facts only.
- Contributors agree at the point of contribution: "By contributing, you confirm the facts are
  yours to share and agree they are released under CC BY 4.0, with credit to you as a named
  source." Producers and partners see this before they sign up, not after.

Files: `LICENSE` (data), `LICENSE-CODE` (MIT), `LICENSING.md` (this reasoning, plus the source
terms table).

## Prior art

A first search (October 2026, from search summaries, not a full review) found no open,
community-maintained, producer-level dataset with partner-maintained, per-field provenance.

- **Federal:** USDA AMS Local Food Directories (farmers markets, CSAs, on-farm markets, food
  hubs, agritourism), with an API and a CC BY listing on data.gov. Self-reported, goes stale,
  has gaps and duplicates. USDA FAME is an open analytical mapper.
- **Commercial and nonprofit directories that own their data:** LocalHarvest (2000, member-
  maintained; a 2009 study found it counted far fewer CSAs than the Census), Eat Wild, Eat Well
  Guide, MarketMaker.
- **State and regional directories, closed to bulk use:** Maine Farm and Seafood Products
  Directory (operator cannot share in bulk because of its sign-up terms), Vermont Food System
  Atlas and NOFA-VT directory, Wisconsin Farm Fresh Atlas (annual refresh, statewide since
  2023), OregonTaste.
- **Open source, adjacent:** Open Food Network (marketplace software), Data Food Consortium
  (data standards, a "digital commons" for short supply chains), LocalCrop and other viewers on
  USDA data, Open Food Facts (packaged products, the proof that a community-maintained open food
  database works), OpenStreetMap `shop=farm`.

What this suggests: the recurring problem is stale self-reported data, so per-field verification
dates and producer and partner confirmation are the point. Closed regional directories are the
likely partners, and their sign-up language is the barrier, which our contributor statement
addresses. The Data Food Consortium and USDA are worth contacting about standards and
distribution. To be verified before relying on any detail here.

## Near-term scope

1. Settle the name and this charter.
2. Define the producer / location / producer-location / service-area schema.
3. Migrate the existing Phase 2 data into that schema.
4. Rebuild the Farm Trail on top of it (producer pages, areas of operation in county filters).
5. Stand up the public home for the dataset (organization, repo, site).

## Not yet

Deliberately postponed until the foundation is set:

- Source-by-source terms review. A first pass found no stated data license on most upstream
  sources (Colorado Proud, CFMA/MarketWurks, Chaffee Provides); USDA's data.gov listing is CC BY
  but its API terms are unverified. The facts-only release design limits the exposure meanwhile.
- Partner outreach (Colorado Proud, USDA, CFMA, Guidestone and others).
- Governance details, producer claim flow, opt-out process, funding.

## Open questions

- Where does the organization live (GitHub org name, domain)?
