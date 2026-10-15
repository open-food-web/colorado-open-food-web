> Moved from the Colorado Farm Trail repo on 2026-10-15. File paths in this document may still use the old layout (`source-data/`, `data-compiled/`); the raw material now lives in the private sources repo, and inputs, snapshots and tables in this repo.

# The update engine — keeping the directory fresh without babysitting it

> Status: **design doc — nothing here is built yet.** Phase 2 scoped: everything
> described operates on `scripts/scrape/` and the `phase2/` outputs. The live
> Phase 1 map files are untouched (see [`../PHASE2.md`](../PHASE2.md)).

This is the product's key differentiator. Directories rot: markets change days,
farms fold, links die, phone numbers move. Every existing Colorado directory
(Colorado Proud, CFMA, USDA, the tourism guides) goes stale between manual
refreshes. Our promise is the opposite: **take in many sources continuously, and
make smart, provenance-tracked updates automatically** — verified data, working
links, with very little manual input required. Manual input is still welcome
(submissions, curated fixes); it's just never *required* to keep the data alive.

## What already exists (the pieces this design composes)

| Piece | Where | What it gives the engine |
|---|---|---|
| Multi-source pull, 5 USDA directories + Colorado Proud + CFMA | `scripts/scrape/sources/` | Fresh statewide snapshots on demand |
| Field-level provenance | `schema.py` (`provenance` dict → `Provenance` col) | Knows *which source* said every value |
| Source priority + official-site override | scrape README "Field-value priority" | Knows which source to *believe* on conflict |
| Stable source ids + source update stamps | `Source ID` / `Source Updated` cols (USDA `listing_id` / `updatetime`) | Cheap change detection against a source |
| Dedup + possible-dup flags for human review | `merge.py` | New records land without duplicating old ones |
| Link checker with confirmed-BROKEN-only rule | `scripts/check_links.py`, [`LINK_CHECKING.md`](LINK_CHECKING.md) | Link health signal with a low false-positive bar |
| Human intake | [`BUSINESS_SUBMISSIONS.md`](BUSINESS_SUBMISSIONS.md) form | Manual input path, already live |
| Entity registry | `scripts/scrape/registry.py`, [`ENTITY_REGISTRY.md`](ENTITY_REGISTRY.md) | Remembers businesses we declined, closed, merged or could not resolve, so a source cannot bring them back as "new" |

The engine is mostly *orchestration and memory* on top of these: run the pulls on
a schedule, remember what we knew last time, diff, and act by rule.

## Principles

1. **Explicit-only stays.** A field is filled only when a source states it; the
   engine never guesses. (Same confidence rule as the scraper.)
2. **Every automatic change must be attributable and reversible.** Each applied
   update records what changed, from which source, and why the rule allowed it.
3. **Asymmetric caution.** Adding/filling is cheap to get wrong (a human can
   prune); *overwriting or deleting* existing verified data is expensive to get
   wrong. Auto-apply is generous for the former, conservative for the latter.
4. **A vanished listing is a review item, not a deletion.** Sources drop records
   for boring reasons (site migrations, opt-outs). Only a human — or a confirmed
   signal like a dead official site *plus* directory removal — retires a record.
5. **Manual beats automatic, permanently.** A curated human decision is stored as
   an override that survives every future rebuild, so the engine never re-breaks
   what a person fixed.

## Architecture

```
        ┌─ sources (USDA ×5, Colorado Proud, CFMA, operators, official sites)
        ▼
  [1] scheduled pull  ──►  [2] snapshot store  ──►  [3] diff engine
                                (per-run raw JSON)        │
                                                          ▼
                              [6] curated overrides  ◄─ [4] rules: auto-apply │ review
                                        │                 │            │
                                        ▼                 ▼            ▼
                                   [5] rebuild ◄── applied updates   review queue
                                        │                            (one rolling
                                        ▼                             report/issue)
                                  phase2/ CSVs + report
```

**[1] Scheduled pull.** A weekly GitHub Actions cron (same skeleton as the
link-check backlog item in [`LINK_CHECKING.md`](LINK_CHECKING.md) — the two runs
belong in one workflow) re-fetches every source. Stagger nothing; the whole pull
is a few dozen HTTP requests. `USDA_API_KEY` lives in an Actions secret.

**[2] Snapshot store.** Each run saves the raw per-source payloads under
`source-data/phase2/snapshots/<date>/<source>.json` (committed; they're small).
This is the engine's memory — diffs are computed source-against-its-own-last-
snapshot, *before* merging, so "USDA changed this phone" is distinguishable from
"our merged value changed".

**[3] Diff engine.** For each source, key records by stable id where the source
has one (`Source ID` for USDA) and by `name_key(name) + city` otherwise. Classify
every record: **new** (in source, not in last snapshot), **changed** (field-level
diff; skip records whose `Source Updated` stamp is unchanged), **vanished** (in
last snapshot, gone now). Cheap, deterministic, no network beyond the pull.

**[4] Rules — what auto-applies vs. what queues.** The heart of the engine:

| Change | Action | Why it's safe (or isn't) |
|---|---|---|
| New record from any directory | **Auto-add**, flagged `new since <date>` in the raw CSV; dup-flag pass runs as usual | Additive; dup flags catch collisions |
| Field currently **empty**, source now states a value | **Auto-fill** with provenance | Pure gap-fill, explicit-only rule holds |
| Source updates a field **it already owns** (provenance says this value came from it) | **Auto-update**, old value logged | The believed source changed its mind; freshest wins |
| Lower-priority source conflicts with a value owned by a **higher-priority** source | **Ignore**, log only | Priority order exists precisely for this |
| Higher-priority source conflicts with a lower-priority value | **Auto-update** + log | Upgrade in authority |
| Official-site enrichment conflicts with any directory | **Auto-update** (official site wins per the README rule) | Already the standing rule |
| Record **vanished** from a source | **Review queue**; auto-retire only if *every* source dropped it **and** its official link is confirmed dead | Principle 4 |
| Link confirmed **BROKEN** (per the `check_links.py` bar: 404/410, dead DNS, refused, TLS handshake) | **Auto-blank** the link (not the record), logged | The bar was tuned for near-zero false positives |
| Link **UNCERTAIN** (403/429/timeout/5xx), moved domains, social links | **Review queue** / advisory | Facebook & Instagram block bots; see LINK_CHECKING |
| Anything the rules can't classify | **Review queue** | Default-closed |

**[5] Rebuild + report.** After applying, rerun the normal
`build.py` → merge → geocode pipeline and emit `update_report.md` per run: N
added / N filled / N updated / N queued, each line with record, field, old → new,
source, rule. The report is the audit trail *and* the notification (posted to the
rolling GitHub issue; the Action fails loudly only on pipeline errors, never on
data findings).

**[6] Curated overrides — the manual-input path, upgraded.** A single
`source-data/phase2/overrides.csv` (record key, column, value, note, date). Loaded
*above* official-site enrichment in the priority order, i.e. it always wins and
always survives. Three feeders: review-queue decisions, business-form submissions
(after the human vet in [`BUSINESS_SUBMISSIONS.md`](BUSINESS_SUBMISSIONS.md) —
the vetted row becomes an override instead of a hand-edited CSV cell), and ad-hoc
fixes. This is how "manual input is also welcome" works without manual input ever
being load-bearing: people correct, the engine remembers, rebuilds never regress.

## What "verified" means per field (truth ladder)

Reused from the scrape README, now with overrides on top:

1. Curated override (human decision — permanent until changed)
2. The record's own official website, clearly stated
3. Colorado Proud → 4. CFMA → 5. USDA → 6. aggregator consensus

A field's displayed value always carries provenance from this ladder; the diff
engine's job is keeping each rung *current*, and the rules table's job is making
sure a lower rung never silently overwrites a higher one.

## Rollout

| Stage | What runs | Trust level |
|---|---|---|
| 0 (now) | Manual `build.py` runs; snapshots begin accumulating on first run | — |
| 1 | Weekly Action: pull + snapshot + diff + **report only** (includes link check) | Read the reports for 2–3 weeks; tune rules |
| 2 | Auto-apply ON for the additive classes (new records, gap-fills) | Overwrites still queue |
| 3 | Full rules table live; review queue is the only human touchpoint | Steady state: minutes/week |

Stage 1 deliberately mirrors the link-check plan's report-only-first philosophy —
earn trust in the signal before letting it write.

## Build order (when implementation starts)

1. `scripts/scrape/snapshot.py` — save/load per-source raw payloads (tiny).
2. `scripts/scrape/diff.py` — classify new/changed/vanished + field diffs, keyed
   by source id or name-key. Pure functions, fixture-tested offline.
3. `overrides.csv` loader as a top-priority source in `build.py` (small; makes
   manual input durable immediately, even before any automation).
4. `update_report.md` writer.
5. The GitHub Actions workflow (cron + `workflow_dispatch`), report-only.
6. Flip on auto-apply per the rules table, one class at a time.

Steps 1–3 are useful on their own the moment they land; nothing blocks on the
scheduler existing.
