# Google Places lookup and display rules

> **Status: on hold (2026-10-14).** Nothing here is set up yet. No Google Cloud project, key or
> script exists. This records the plan and the rules we settled so we can pick it up later.

## Why

Two questions come up for almost every record, and a Google Places lookup helps answer both:

1. Does the business **publicize a location**? (decides `hide_address` and where a pin goes)
2. Is the record **a real, open business** with a public listing? (decides how much to trust it)

It does not replace the business's own site. Addresses, hours and products still come from the
business's own pages, as in [SCHEMA.md](SCHEMA.md).

## Rules we settled

**Scope is the whole food system.** Any food production, making, distribution or consumption can be
in the data, including cottage food, flower farms, nurseries, seed companies, processors, resellers
and aggregators. No entity is too large or too small if a category can be made for it. If no
category fits, add one.

**The data set is broad; applications filter.** The data is not meant for a public audience as-is.
It is a backend that applications filter. Locations of every farm can be held (for example to study
how far produce travels), but a public map or "where to buy" list shows only places that advertise a
sales channel. Farm locations are provided for research on request and are not published for farms
that have not asked to be listed or advertised direct sales.

**Three questions per record, kept separate:**

| Question | Yes when |
|---|---|
| In the data? | It is part of the Colorado food system |
| Shown publicly? | It advertises a sales channel to customers |
| On a map and counted as a local producer? | It has a **local** sales channel: farm stand, market, CSA pickup, local delivery or local retail |

A business that only sells online and ships nationally, with no local channel, still gets a record
and a page, but it is tied to no area and does not count as a local producer.

**Sales locations are not the home base.** Where a business sells (pickup points, markets, farm
stands) is public by design. Where it is based is only shown if the business publishes it.
Example: a beef ranch whose online shop lists pickup at a fairgrounds in Norwood and a parking lot in
Telluride has two sales locations and no published home address. Model these as `presences`
(`farm_stand`, `csa_dropoff`, and so on) and leave the home base off the public map.

## What the Places lookup would do

For each business, search by name and town and record only:

- `google_place_id` (Google permits storing this)
- `publishes_address`: whether a public listing shows a street address (yes / no)
- `listing_status`: operational, temporarily closed, permanently closed, not found
- `lookup_date`

**It must not store** Google's addresses, phone numbers, hours, ratings, reviews, photos or
coordinates. Those come from the business's own pages or other open sources. Google's terms limit
caching and redistributing Places content, so check the current terms and pricing before relying on
any of this. The charter's rule for photos is the same: store `google_place_id` only, and show
thumbnails live at view time (see [CHARTER.md](CHARTER.md)).

## Proposed schema additions (not applied)

| Field | Table | Values | Purpose |
|---|---|---|---|
| `public_listing` | producers / outlets | yes, no | May apps show it publicly |
| `local_sales_channel` | producers | yes, no, unknown | Map placement and "local producer" counts |
| `publishes_address` | places | yes, no, unknown | Default for `hide_address` |
| `listing_status` | places | see above | Trust signal; closes stale records |

`sales_channels` already exists. `local_sales_channel` can be derived from it (any of `on_farm`,
`farm_stand`, `farmers_market`, `csa`, `delivery`, `retail_partners`) once those values are
filled in for each record.

## Setup (when we pick this up)

1. **Project.** In the Google Cloud console create a project, for example
   `open-food-web-places`.
2. **Billing.** Link a billing account. Maps Platform APIs need one.
3. **API.** Enable **Places API (New)**, not the older "Places API".
4. **Key.** Create an API key. Restrict it to Places API (New) only. Add an application or IP
   restriction if the machine's IP is stable.
5. **Hard limit.** Lower the daily request quota for Places API (New) so a runaway loop cannot spend
   much. A budget alone only sends email; a quota blocks requests.
6. **Budget alerts.** Create a monthly budget with alerts at 50%, 90% and 100%.
7. **Store the key** in the git-ignored `.env` as `GOOGLE_MAPS_API_KEY`. Never commit it or paste it
   into chat or an issue.
8. **Field mask.** Request the fewest fields possible; the price tier depends on the fields.

## Script design

- Reads the key from `.env`; stops cleanly if it is missing.
- Works from a list of records (name, town), in small slow batches, and stops on the first error
  or when the daily quota is hit.
- Caches by record so a record is never looked up twice (re-check on a schedule, for example
  yearly).
- Writes only the fields above, with a source and date, into the provenance table.
- First run on a small, already-verified sample, checked by hand against what a person finds on
  Google, before any wider run.

## What we learned while preparing this

- Automated searches miss small producers that a person finds on the first Google result. In one
  review, 3 of 3 vendors the maintainer looked up by hand had been missed by an automated search.
- Guessing a website from a business name works about half the time and returns false matches
  (wrong state, unrelated company, parked domains) the rest of the time. Every guess needs a
  read-through before it is kept.
- A Google search run through the maintainer's own browser returns the "Local results" panels and
  business pages that automated search does not. That is a manual-assist route if the API stays on
  hold.
- Facebook cannot be checked by script, and Instagram can only confirm a profile that exists, not
  one that does not.

## Open questions

- Which Google terms apply to storing a `publishes_address` yes/no derived from a lookup? Confirm
  before the first run.
- Where does the spending cap live for a project owned by the organization, not an individual?
- Do we run lookups for every record, or only for records without a business-published address?
- Who owns the Google Cloud project: the organization, or the maintainer?
