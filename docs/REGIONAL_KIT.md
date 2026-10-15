# The regional producer map kit

> Status: **plan, nothing built yet.** It builds on what already exists: the app export (`EXPORTS.md`), the
> Chaffee Provides site, and the Gunnison Valley prototype.

## The idea

A local food organization (a county nonprofit, an extension office, a tourism board, a food council) gets a
current, trustworthy map and directory of its region's producers without building or maintaining one. The
Food Web supplies and maintains the data; a ready-made site template shows it; the organization reviews and
corrects. Chaffee Provides (Guidestone Colorado) is the first region; Gunnison Valley is the second.

```
sources ──> Food Web (statewide tables) ──> region export ──> region site ──> the organization's web address
 (monthly)        │                              │ diff                │
                  └──── corrections, claims <────┴─── partner review ──┘
```

## What already exists

| Piece | Where | State |
|---|---|---|
| Export format v1, with the release rules applied once (hidden addresses, opt-outs, closed records) | `docs/EXPORTS.md`, `scripts/export_app.py` | Built, one county |
| Chaffee Provides site: find-food map with filters, provider page, about, list-your-business, food assistance, stories | prototype repo, hosted copy | Draft, for review |
| Gunnison Valley prototype: same design system, same JavaScript and map code, different copy and data | Farm Trail repo, `gunnison-valley/` | Prototype |
| Source pipeline, schedules, change reports | this repo | Built |
| Partner list intake (`data/partner-additions/`), correction forms | this repo | Convention and forms only |
| Corrections and claims flow, partner moderation | `FEEDBACK.md` | Design only |

The two sites differ by roughly 15 changed lines in the map and provider pages and by wording elsewhere.
That is the evidence a template is realistic.

## What a new region needs

### 1. A region definition
One small file per region, `regions/<slug>.json`:

- name, the organization, and who the contacts are;
- the counties (FIPS codes) and any extra sources to include (for example a partner's own list);
- which record types are shown (producers, markets, food access points; restaurants on or off);
- map centre and zoom, the product and category vocabulary to show, and the cities used as filters;
- the web address, and when the data was last approved.

### 2. A region export
`export_app.py` takes a region file instead of one county, and produces `exports/<slug>.json` in format v1. A second
step compares two exports and writes the **change report** (new, changed, removed), which is what the partner
reviews each month.

### 3. A site template
The common core of the two prototypes, driven by `site.config.json`: brand name and colors, navigation, which pages
exist, copy blocks, banner text, contact details and form target. It reads the export directly (no per-region data
script). Pages: find-food map with search and filters, provider page, about, list-your-business. Optional: a food
assistance schedule. Stories and blogs are out of scope (Guidestone dropped theirs).

### 4. A build and publish routine
One command builds a region's static site from the template, the config and the export. A workflow runs it, checks
the export (known format version, counts match), and publishes to GitHub Pages. The result is plain files the
partner could host anywhere.

### 5. The update loop
1. The Food Web refreshes its sources on schedule.
2. Each month it rebuilds the region export and the change report.
3. The partner's reviewer approves or corrects (a pull request, or a short form that becomes one).
4. The site republishes. A bad update is reverted by one commit.

### 6. Partner onboarding
Take in the partner's own list, match it against the statewide data, return a **gaps report** (what each side is
missing or has stale), apply their corrections, agree the hide-address and opt-out rules, and decide who moderates
and how fast. Producers can see, correct or remove their record.

### 7. Hosting, domain and handoff
Decide who owns the repository and the domain (the partner's, so they can leave with it), who pays the roughly $20 a
year for the domain, and write down the exit path. Because the site is static and the data is open, a partner is
never locked in; that is part of the trust.

### 8. Launch checks
Coverage against the partner's list, duplicates, hidden addresses, link health, accessibility, phone layout, and
search engines blocked until the partner approves.

### 9. An engagement package
What the partner gets for a fee: setup, monthly checks and change report, corrections handled, one launch social
push, and a handoff plan. The Guidestone discussion is the reference point (about $500 a year, with $1,000 a year
in view). The Food Web data itself stays free and open (CC BY 4.0); the service is the maintenance and the site.

## Proposed steps

| # | Step | Size | Notes |
|---|---|---|---|
| 0 | Ship Chaffee Provides on the work already done; generalize afterwards | | The October 31 relaunch is the acceptance test. Do not delay it to build the kit |
| 1 | Statewide canonical tables (today only Chaffee County) | M | Prerequisite for every region |
| 2 | Region file, `export_app.py --region`, change report | S to M | The county flag becomes a region |
| 3 | Extract the template from the two sites; switch it to read the export; make it config-driven | M | Gunnison is the check that it is truly reusable |
| 4 | Build and publish workflow, with export checks | S to M | One region first |
| 5 | Onboarding path: partner list in, gaps report out; corrections to pull request | M | Uses the feedback design |
| 6 | Move Gunnison onto the kit | S | Second region proves it |
| 7 | Engagement package and handoff checklist | S | Also the pitch for the next regions |

Sizes are relative (S under a day, M a few days). Steps 1 to 3 are the real work; 0 comes first.

## Decisions needed

1. **Ownership.** Does each region's repository and domain belong to the partner, to you, or to a Food Web
   organization?
2. **Pricing.** One flat annual fee, or setup plus annual? Whether a grant-funded region pays differently.
3. **Restaurants.** Off by default for regions (as Guidestone asked); the farm-to-table guide is its own product.
4. **Photos.** The Chaffee draft hotlinks Guidestone's own photos. Decide the policy: producer-supplied and
   licensed, or a placeholder.
5. **Naming.** Regions can carry their own brand (Chaffee Provides) with a standard "Data from the Colorado Open
   Food Web" credit.
