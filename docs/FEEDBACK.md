# Partner feedback: how corrections and additions reach the data

> Status: **design, not built.** The two GitHub issue forms and the first partner file exist; the
> rest below is what gets built. This is the part of the project that lets partners such as
> Guidestone Colorado improve the dataset and see their changes land.

## Goal

A partner who knows their area should be able to say "this is wrong" or "this is missing", and have
that become a reviewed change to the data, credited to them, without needing to understand the
pipeline. Their contribution survives every future rebuild, and the next update run does not undo it.

## Channels

| Channel | For | Status |
|---|---|---|
| **GitHub issue forms** (`Correction`, `New listing`) | Anyone with a GitHub account | Built |
| **Partner file drop** (`data/partner-additions/<partner>_<date>.csv`) | Partners with a list of changes or new records. Guidestone's first file is there | Convention exists; no validator yet |
| **Public intake form** (`intake/create_business_form.gs`, Google Forms and Sheets) | Producers adding themselves, no GitHub needed | Script exists; not connected to anything |
| **Producer claim** (verify, correct or remove my record) | Producers | Not built |

## How a submission becomes data

```
 submission ──> validate ──> normalise ──> entry in inputs/ ──> pull request ──> merge ──> next build
 (any channel)   (schema,     (phones,      with provenance       (reviewed by    (the entry is
                 links,       URLs, county)  partner:<id>,         a maintainer)   applied every
                 duplicates)                 verified_on                           build, forever)
```

- **One landing place.** Every channel ends as a row in a file under `inputs/` (corrections go to
  `overrides.csv`, additions to `curated_records.csv`, removals to an exclusions list). The pipeline
  already applies these on every build, so a person's decision is never undone by a refresh.
- **Provenance.** The source on each field is `partner:<id>` (or `producer`), with the date, so
  the public data says who confirmed it.
- **Priority.** A partner-verified field outranks a directory listing, as official-site data does
  today. Directories still fill what nobody has confirmed.
- **Nothing is applied without review.** The PR is the approval step, same as for source refreshes.

## What to build, in order

1. **Validator** (`scripts/feedback/validate_submission.py`): checks a partner file or form row against
   the schema and the facts-only rules (no copied descriptions, no personal data, valid counties and
   URLs), and flags likely duplicates of existing records. Output is a short report a non-technical
   partner can read.
2. **Partner registry** (`partners.json`): id, name, counties or topics covered, what they are trusted
   to verify directly versus propose, and a contact. The validator uses it to set provenance.
3. **PR automation**: when a PR touches `data/partner-additions/` or `inputs/`, an Action runs the
   validator and comments with the report.
4. **Converters**: issue form to PR, and form sheet to PR, so no channel needs hand copying.
5. **Gaps report per partner**: a generated page listing what the dataset is missing or has stale in
   their area (from the update pipeline's change reports). This is the "what could we improve" loop,
   and the strongest thing to show a prospective partner.
6. **Producer claim and removal**: a verified path for producers to confirm, correct or remove a
   record. Removals are honored and logged by ID only.

## Rules that apply to every channel

- Business information only, already public. No personal addresses, phone numbers or social profiles.
- Submitted text is accepted under the contributor statement in `LICENSING.md` (CC BY 4.0, credited).
- A removal request is honored first and discussed after.
- Rejected submissions get a reason, so partners learn what the data accepts.

## Open decisions

- Which partners can write `verified` fields directly, and which only propose.
- Whether form submissions need a human check before a PR is opened (spam).
- Where partners see their gaps report: a page in this repo, or something private to them.

## Worked example: Guidestone's first review (Oct 13, 2026)

The first round of partner feedback was applied by hand through this process, as a model for the
rest. See `reports/2026-10-13-guidestone-review.md` for the report that went with it.

1. **Receive.** Alycen's color-coded sheet and a call. Each note was a fact (a phone number, a
   closure, a pickup place) or a scope choice (what the Chaffee site shows).
2. **Translate.** Facts become rows in `inputs/`: `overrides.csv` (set, clear, remove) and
   `curated_records.csv` (new businesses), each noted `partner:guidestone` with the date. Places a
   producer sells beyond its home base go in `inputs/locations.csv`. Scope choices go in the app's
   export config, not the data.
3. **Rebuild.** The build keeps those rows forever, and fields credited to a partner are recorded as
   partner-verified.
4. **Report.** `scripts/change_report.py` compares the tables before and after; the written report
   adds who said what and what is still waiting.
5. **Review.** The pull request carries the report. Merging it is the approval.
