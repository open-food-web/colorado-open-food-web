> Moved from the Colorado Farm Trail repo on 2026-10-15. File paths in this document may still use the old layout (`source-data/`, `data-compiled/`); the raw material now lives in the private sources repo, and inputs, snapshots and tables in this repo.

# Deduplication Standards

How we decide whether two records are the **same market** (merge) or **distinct
markets** (keep both). These rules were set while reconciling the merged
`colorado_proud` + `usda` farmers-market data in
`data/co_farmers_markets_all_raw.csv`, where near-duplicates are flagged in the
**`Possible Dup Of`** column.

## First principle: location is key

**We are producing a map.** A record earns a pin because it puts real food at a
real place. So the decisive question is always:

> **Is this the same market happening at the same physical location?**

- **Same location → same pin → merge.** Two records that resolve to the same spot
  are one map marker, no matter how many names, seasons, or source feeds they came
  in under.
- **Different location → different pin → keep separate.** If a customer would drive
  to a different address, it's a distinct market on the map — even if the same
  organization runs both.

Everything below serves that principle.

## Seasonality: merge same-location summer/winter markets

If a **winter** and **summer** (or holiday, or any seasonal) market operate at the
**same location**, **merge them into one record** and make the seasonality explicit
in the data:

- **`Hours`** — spell out each season's days/times.
- **`Months Open`** — list all months across both seasons.
- **`Notes`** — describe the seasonal split in plain language
  (e.g. "Outdoor market May–Oct; moves indoors Nov–Apr at the same site").

One location = one pin, with the full-year story captured in the fields. A visitor
looking at that spot on the map should see it runs year-round, not two competing
markers.

If the seasonal editions are at **different addresses**, keep them **separate** —
they're different pins (see the Backyard Market example below).

## Proximity: close markets are candidate duplicates

Real markets rarely operate **within ~10 miles of each other** — the customer base
overlaps too much. So when two records sit that close together, treat it as a
**duplicate flag** and investigate:

- **Close + same market day** → very likely the **same market** (one record has a
  stale/second address, or the two feeds geocoded it slightly differently). Merge.
- **Close + different market days** → this is the usual exception. It can be one
  operator running two market days at two nearby sites, or two genuinely distinct
  markets. Confirm with location + web before deciding.

Caveat: this is a **prior, not a law**. Dense metro areas (Denver, Colorado Springs)
legitimately pack many distinct markets within 10 miles — the heuristic is
strongest in rural and suburban areas where a second nearby market is unusual.

## Liveness: dead links are a red flag

**Markets that are actively running have easy-to-find, working information** — a live
website, a current-season social feed, a listing that resolves. So a **dead link is
a strong red flag** about the record itself:

- A dead domain often means the market **folded, moved, or was consolidated** into
  another — not merely that a URL went stale. Chase down where it went before
  assuming the market still runs as listed.
- When a dead-domain record and a live-domain record describe the same location, the
  **live one is usually the surviving identity**; re-point the record to it.
- If *no* working information can be found for a market at all, treat its continued
  existence as **unverified** and flag it rather than pinning it as active.

(Example: `highlandssquarefarmersmarket.com` going dead was the tell that the
Highlands Square market had been folded into The Highlands Farmers Market — see the
edge-case notes below.)

## Signals that they are the SAME (merge)

Strongest first:

1. **Same physical location** (same address, or coordinates within ~a block).
   The controlling signal.
2. **Same website domain.** The most decisive *contact* signal when addresses
   differ.
3. **Same email + same social accounts** (Facebook page/group, Instagram handle).
4. **Address change explained by a move.** Different addresses are fine to merge
   *if* a record's notes or the web confirm the market relocated. Treat the old
   address as stale, keep the current one.
5. **Same operator at the same site under different names** (e.g. a market renamed,
   or a neighborhood-org name vs. a market name for the same event).
6. **Within ~10 miles and running the same market day** (see Proximity, above).

## Signals that they are DISTINCT (keep separate)

1. **Different physical locations** with no evidence of a move — especially
   different neighborhoods. Different pins.
2. **Different website domains** and **different operator orgs / emails / socials**.
3. **A shared phone number is weak on its own.** Market managers and booking
   agents run multiple markets off one line. Do not merge on phone alone — confirm
   with location + web.
4. **Name overlap on a generic word** ("Urban", "Highland", "Fork", "Four Seasons")
   is a false-positive trap, not evidence of sameness.

## Ambiguous — verify on the web before deciding

- Same phone but different website **and** different address.
- Same operator listed at different locations (satellite / pop-up vs. main site) —
  decide per the location principle: different address → separate pins.
- Suspect a record has **cross-contaminated data** (e.g. a name from one market
  glued to an address/website from another). Verify each field against the source
  before merging or dropping.

## Choosing the canonical record when merging

Keep the record with the **current, correct location** and the **richest data**
(hours, products, socials, notes) — usually the `colorado_proud` row. Drop the
sparse or stale one (usually the bare `usda` row). Carry over any unique field from
the dropped record before removing it.

## Worked decisions (2026 all-CO farmers-market reconciliation)

12 flagged pairs, resolved under these rules. **Merged** = one dropped; **Separate**
= both kept.

| Pair | Call | Reason |
|---|---|---|
| The Backyard Market in Black Forest / **- Winter** | Merge | Winter is the same 6845 Shoup Rd address, off-season → fold into hours/months |
| The Backyard Market in Black Forest / **- Holiday** | **Separate** | Dec-only pop-up at a *different* address (13710 Black Forest Rd) → own pin |
| Delta FM / Delta FM & Bazaar | Merge | Same site/phone/email; market relocated to 2195 Southgate Ln (web-confirmed) |
| Evergreen FM / Evergreen FM THE ORIGINAL | Merge | Same operator (Colorado Outdoor Markets), moved Bergen Pkwy → Meadow Dr |
| Fort Morgan at The Block / Fort Morgan FM | Merge | Same site/email/socials, both "at The Block" |
| Aspen Grove FM / Aspen Grove Lifestyle Center FM | Merge | Same location; old denverfarmersmarket operator now closed, abmarketcolorado active |
| Highland FM / Highland United Neighbors FM | Merge | Same NW-Denver market/org (denverhighland.org); the S. Pearl address on the dup was cross-contaminated junk data |
| Feed Denver / Urban Market | Separate | Different entities (urban-farm nonprofit vs. Union Station arts market); name collision on "Urban" |
| Fort Collins FM / FC Winter FM | Separate | Different orgs, domains, **and locations** |
| Greeley FM / Greeley Winter FM | Separate | Same operator but **different addresses** → different pins |
| City of Rifle FM / Rifle FM | Separate | Different domains, phones, addresses, operators |
| South Fork FM / South Fork …Artisan & Antique | Separate | Different phones/addresses; the antique market shares an operator with the Creede antique market, not the produce market |
| Pueblo FM / Pueblo Eastside Pop-ups | Separate | Same operator, but a **different address** (1346 E 8th St vs 1604 N Santa Fe) → own pin |

### Notes on the edge cases

- **Same phone, different market:** `(303) 734-0718` appears on *three* Highlands-area
  records — Highland FM (1576 Boulder St), Highland United Neighbors (bad data), and
  Farmers' Market at Highlands Square (3489 W 32nd Ave). The Boulder St market is a
  **separate** entity ~1.2 mi away with its own site (`denverhighland.org`) — a
  textbook case of not merging on a shared phone.
- **Dead link → consolidation, not a stale URL:** *Farmers' Market at Highlands
  Square* was **folded into The Highlands Farmers Market** (`thehighlandsfarmersmarket.com`)
  at the same 32nd & Lowell location. Its dead `highlandssquarefarmersmarket.com`
  domain was the red flag that the standalone market no longer exists under its own
  name — the record should be re-pointed to the surviving identity, not kept as a
  separate "Highlands Square" market. (Still distinct from the Boulder St market
  above.)
- **Seasonal, different address stays separate:** Greeley and Fort Collins run
  summer + winter editions at *different* addresses, so they remain distinct pins —
  the merge-on-seasonality rule only applies at a shared location.
