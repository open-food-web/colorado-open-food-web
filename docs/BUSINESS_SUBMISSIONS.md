> Moved from the Colorado Farm Trail repo on 2026-10-15. File paths in this document may still use the old layout (`source-data/`, `data-compiled/`); the raw material now lives in the private sources repo, and inputs, snapshots and tables in this repo.

# Business submissions — "Add my business to the map"

> Status: **live.** The Apps Script has been run, the form and its linked
> response sheet exist, and the home-page buttons point at the published form
> URL (<https://forms.gle/NFoVsEQURggzTBSX9>). Submissions still go through
> manual maintainer review before appearing on the map.

The map is **pull-only**: records come from the Colorado Proud Farm Fresh
Directory (see [DATA.md](DATA.md)). A farm or market that isn't in that directory
— or a brand-new one — has no way onto the map. This is the intake path that
fixes that: a free public form, a maintainer review, and a manual add to the CSV.

This is deliberately **not** the paid "Featured listings" idea in
[MONETIZATION.md](MONETIZATION.md). This is free, neutral inclusion. Keep the two
separate.

## The flow (end to end)

1. Visitor clicks **➕ Add my business to the map** on the home page (`index.html`).
2. A **Google Form** collects the submission (fields below).
3. Responses land in a **linked Google Sheet**.
4. Maintainer reviews for legitimacy and de-duplication (see
   [DEDUP_STANDARDS.md](DEDUP_STANDARDS.md)).
5. Maintainer adds a row to `data-compiled/farm_fresh_directory_mymaps.csv`.
6. Run `python scripts/build_map_data.py` to regenerate `data/markets.json`.
7. Commit the regenerated JSON per [GIT_WORKFLOW.md](GIT_WORKFLOW.md); GitHub
   Pages redeploys and the pin appears.

There is no backend and no automation on this path by design — a human vets every
submission before it reaches the map.

## Building the form (one-time)

The form is defined in code at
[`scripts/apps-script/create_business_form.gs`](../scripts/apps-script/create_business_form.gs)
so its structure is version-controlled.

**Live form URL (published):** <https://forms.gle/NFoVsEQURggzTBSX9> — this is the
link the home-page button points at.

To (re)create the live form from the script:

- [x] Open [script.google.com](https://script.google.com) → **New project**.
- [x] Delete the starter code, paste in the whole `.gs` file.
- [x] **Run** → `createBusinessForm` and authorize the requested scopes.
- [x] Open **View → Logs** (or **Executions**) and copy the two URLs it prints.
- [x] Paste the **PUBLISHED URL** into the button `href` in `index.html`. *(Live: <https://forms.gle/NFoVsEQURggzTBSX9>.)*
- [ ] Paste the **EDIT URL** here for future edits: `EDIT_URL_TODO`
- [ ] Note the **responses Sheet URL** here: `SHEET_URL_TODO`

Re-running `createBusinessForm()` makes a **new** form + Sheet each time. To
tweak the live form later, use its EDIT URL instead of re-running the script.

Owner note: ideally the form is owned by the brand Gmail, which is still a parked
TODO in [BRANDING.md](BRANDING.md). If created under a personal account for now,
plan to migrate ownership later.

## Field spec

Question titles mirror the CSV columns so a response row copies almost straight
into `data-compiled/farm_fresh_directory_mymaps.csv`.

| Form question | CSV column | Type | Required | Notes |
|---|---|---|---|---|
| Business Name | `Business Name` | Short text | ✅ | Name as shown on the map. |
| Category | `Category` | Checkboxes (multi) | ✅ | Check all that apply — a producer can appear under several categories. Listed options match the `CATS` set in `index.html`, **plus a native "Other:" option with a free-text box** for anything unlisted. See [Multiple categories](#multiple-categories). |
| Address | `Address` | Short text | ✅ | Street address or nearest cross-street. |
| City | `City` | Short text | | |
| County | `County` | Short text | | |
| Zip | `Zip` | Short text | | 5-digit ZIP. |
| Google Maps link | *(none — see below)* | Short text | | Submitter searches on Google Maps and pastes the share link; maintainer reads `Latitude`/`Longitude` from it. |
| Phone | `Phone` | Short text | | |
| Call first? | `Call first?` | Yes/No | | Call ahead before visiting? |
| Website | `Website` | Short text | | Full URL. |
| Email | `Email` | Short text | | Public contact email. |
| Facebook | `Facebook` | Short text | | Full URL. |
| Instagram | `Instagram` | Short text | | URL or @handle. |
| Hours | `Hours` | Paragraph | | Free text. |
| Months Open | `Months Open` | Checkboxes | | Jan–Dec. |
| Products | `Products` | Paragraph | | Comma-separated. |
| Certified Organic | `Certified Organic` | Yes/No | | |
| Accepts SNAP / EBT | `SNAP` | Yes/No | | |
| ADA Accessible | `ADA Accessible` | Yes/No | | |
| Where to Get It | `Where to Get It` | Paragraph | | Wholesale growers: stores/markets/restaurants carrying their products, one per line. Maintainer joins lines with `; `. |
| Notes | `Notes` | Paragraph | | One-line description works well. |

**Not asked of submitters:** `State` (always `CO`), `Latitude`, `Longitude`.
Google Forms has no live address autocomplete, so the **Google Maps link** field
is how submitters "search" their location — they find the spot on Google Maps and
paste the share link. The maintainer reads precise `Latitude`/`Longitude` from
that link (or geocodes the typed address if no link was given);
`build_map_data.py` drops rows outside the Colorado bounding box, so bad
coordinates won't reach the map.

## Multiple categories

A producer can belong to **several** categories at once — e.g. an on-farm store
that is also a U-Pick and offers agritourism. The form's Category question is a
**checkbox** list so submitters can check every one that fits.

Design for handling this end to end:

- **Primary category drives the pin.** A map marker can only be one color/emoji,
  so the **first** category listed is the *primary* and defines the pin's look
  (via the `CATS` map in `index.html`). The maintainer orders the CSV cell so the
  main activity comes first.
- **Storage.** The single `Category` CSV column holds a **comma-separated** list,
  primary first (e.g. `On-Farm / Ranch Sales, U-Pick, Agritourism`). No category
  label itself contains a comma, so comma is a safe delimiter.
- **Build output.** `build_map_data.py` splits `Category` into a `categories`
  array and keeps `category` = the first entry (primary) for backward-compatible
  pin styling.
- **Filtering.** The single-select type filter in `index.html` matches a record
  if the chosen type is **any** of its `categories` (not just the primary), so a
  multi-category producer shows up under each of its filters.
- **"Other" free text.** The Category question has a native **"Other:"** option
  with a free-text box (`.showOtherOption(true)` in the `.gs`). When a submitter
  uses it, the typed value lands in the response as their category. The maintainer
  reads it and either maps it to an existing `CATS` category or records it as
  `Other` in the CSV — the map has no styling for arbitrary custom labels, so
  free-text values must be bucketed on ingest, never passed straight through.

> ⏸ **Not built yet.** The form + this doc are updated. The CSV/`build_map_data.py`/
> `index.html` changes touch the live map and are held until the branch is free —
> see the plan file. Until then, multi-category submissions degrade gracefully:
> the maintainer records the extra categories and picks a primary manually.

## The button

The map-first redesign has landed: the home page is now the full-bleed Leaflet
map (`index.html`), and the standalone `map.html` was retired. The "Add your
business" entry point goes in **two** places within the new UI (per decision):

1. **Sidebar/filter footer** — a small secondary control near the `Reset filters`
   button / data-credit line; always visible while exploring.
2. **About & Share sheet** — an entry alongside the share actions in the overlay
   sheet, for discoverability.

Both point at the live form (<https://forms.gle/NFoVsEQURggzTBSX9>) and open in a
new tab (`target="_blank" rel="noopener"`).

> ✅ **Done:** the `index.html` entry points are wired to the live PUBLISHED URL
> (<https://forms.gle/NFoVsEQURggzTBSX9>) on the `feat/add-business-cta` branch.

- [x] Add the entry points and wire them to the live PUBLISHED URL. *(Sidebar
      footer, About & Share sheet, plus a floating corner action on the map.)*
- [x] Add an `add_business_click` GA4 event mirroring `open_map` — see
      [ANALYTICS.md](ANALYTICS.md). *(UTM tagging still optional/parked.)*

## Backlog / parked

- Brand Gmail as the form/Sheet owner ([BRANDING.md](BRANDING.md) TODO).
- Optional submit-notification email to the maintainer — already stubbed behind
  the `ENABLE_SUBMIT_NOTIFICATIONS` flag in the `.gs`.
- Map-side "add your business" entry point after the redesign ships.
- Semi-automate CSV row-building from the responses Sheet (currently manual).
