> Moved from the Colorado Farm Trail repo on 2026-10-15. File paths in this document may still use the old layout (`source-data/`, `data-compiled/`); the raw material now lives in the private sources repo, and inputs, snapshots and tables in this repo.

# Entity registry: remembering what we decided

The data set lists the businesses we chose to list. The **entity registry** remembers everything
else: businesses we investigated and chose **not** to list, ones we listed that **closed** or were
**folded into another business** or **renamed**, owners who **opted out**, and ones we looked for and
**could not resolve**. Automation checks it before it suggests, adds or re-researches anything, so an
old record is never "found" again and proposed as a new business.

It is the memory half of the [update engine](UPDATE_ENGINE.md): the engine takes in many sources and
diffs them, and the registry makes sure a source cannot undo a decision a person made.

## What it is

`source-data/phase2/registry/decisions.csv`, append-only. Each row is one decision about one entity;
the **latest** row for an entity is its current decision. Past rows are never edited.

| Column | Meaning |
|---|---|
| `decided_on`, `decided_by` | When, and who (`review`, `research`, `manual`, `owner`) |
| `name`, `city`, `website`, `phone`, `aliases` | How to recognize the entity again (aliases are other names, `;`-separated) |
| `decision` | `not_listed`, `closed`, `merged`, `renamed`, `opted_out`, `on_hold`, `unresolved`, `listed` |
| `reason_code`, `reason_note` | Why (see below), with the evidence in plain words |
| `successor_name`, `successor_city` | For `merged` and `renamed`: where it went |
| `evidence_url` | A page that supports the decision |
| `recheck_after` | A date after which the entity may be re-surfaced for **review** (never auto-added) |
| `origin` | Which file or step produced the row |

**Decisions.** `not_listed`, `closed`, `merged`, `renamed` and `opted_out` **block**: the entity is not
suggested or added again. `on_hold` and `unresolved` do not block research; they stop the same work being done
twice. `listed` records a deliberate reversal (an earlier decision was overturned on new evidence).

**Reason codes.** `not_food_system`, `not_colorado`, `changed_business`, `closed_permanently`,
`closed_temporarily`, `merged_into`, `renamed_to`, `duplicate_of`, `wholesale_only`, `no_public_presence`,
`owner_opt_out`, `did_not_qualify`, `reconsidered`, `other`.

## How an entity is recognized

An entity matches a decision on its **name and town**, or its **website domain**, or its **phone number**
(aliases count as names). A name alone is never enough when the towns differ. Social pages and aggregators
(Facebook, MarketSpread, LocalHarvest, Barn2Door ...) are never evidence of identity.

## What the automation does with it

| Step | Behavior |
|---|---|
| `scripts/scrape/build.py` | After merging sources, **suppresses** an entity a source brought back if the registry says `not_listed`, `merged`, `renamed` or `opted_out`; marks a re-surfaced `closed` business Closed. It prints what it did. |
| Curated records | A human adding a record in `curated_records.csv` **wins** over a registry decision. The build reports the contradiction so the registry gets a `listed` row (done automatically on the next build). |
| Every build | `registry.sync()` captures decisions made in the other files: curated `skip` / `closed` / `hold` / `call` / `unclear`, `overrides.csv` `remove` and `Status = Closed`, `dedup_decisions.csv` `merge`, and out-of-scope prospects. Idempotent. |
| Research and prospect lists | Check candidates first: `python scripts/scrape/registry.py check candidates.csv` (a column named `Business Name` or `Prospect Name`) prints which already have a decision. |

Never delete a registry row. If a decision is wrong, add a new row (for example `listed`, reason
`reconsidered`).

## Using it by hand

```
python scripts/scrape/registry.py lookup "Hugs Farm" Walsenburg
python scripts/scrape/registry.py add --name "Some Farm" --city Delta --decision not_listed \
    --reason not_food_system --note "Landscaping company, no food" --evidence https://example.com --by review
python scripts/scrape/registry.py add --name "Old Dairy" --city "Buena Vista" --decision merged \
    --reason merged_into --successor-name "New Creamery" --successor-city "Buena Vista"
python scripts/scrape/registry.py report
```

When you decide something about a business, whether to skip, close, merge or remove it, record it in the
normal file (curated, overrides or dedup decisions); the next build copies it into the registry. Use `add`
for decisions that have no other home, such as an owner opt-out.

## What is not built yet

- The weekly source refresh (`refresh_sources.py`) does not annotate its change reports with registry
  decisions yet; use `check` on a change report until it does.
- The prospect reconciliation (`scripts/phase3/reconcile_prospects.py`) should read the registry so a
  declined entity shows as "Decided" rather than "Unclear".
- `recheck_after` is recorded but nothing yet schedules the re-review.
- The Open Food Web repository needs the same table in its schema (`entity_decisions`).
