# Releases: how apps use the Food Web

Apps do not run the pipeline and do not read the working files in this repository. They **pin a release**:
a tagged, checksummed snapshot published on this repo's Releases page.

## What a release contains

| File | What it is |
|---|---|
| `directory.csv` | The public flat directory, one row per listing. The 23 My Maps columns apps already read (name, category labels, address, city, county, phone, website, email, social links, hours, months open, products, organic, SNAP, ADA, where to get it, latitude, longitude). `Notes` is always empty |
| `MANIFEST.json` | Version, date, format version, license and attribution, row counts, counts by source, the columns, and the **sha256** of each file |
| `RELEASE.md` | The same in words |

Rules applied to every release: facts only (no copied descriptions), closed businesses left out, hidden addresses
withheld, and an email appears only if the business lists it on its own website or Facebook page. The data is
CC BY 4.0: credit "Colorado Open Food Web".

## Versions

Calendar versions: `vYYYY.MM.N` (for example `v2026.10.1`; `N` counts releases in that month). Apps pin one version
and upgrade deliberately. A new release never changes an old one.

## Pinning a release in an app

1. Download `directory.csv` and `MANIFEST.json` for the version you want from
   `https://github.com/open-food-web/colorado-open-food-web/releases`.
2. Check the file's sha256 against the manifest.
3. Commit both into the app (for example `data/foodweb/`), and read `directory.csv` in the app's build.
4. To upgrade, repeat with the new version and review the diff.

The Colorado Farm Trail does this with `scripts/update_foodweb.py`.

## Making a release

1. Merge the latest snapshot and input changes.
2. Actions -> Release -> Run workflow, with a version. The workflow runs the tests, builds the directory from the
   committed snapshots and inputs, assembles the release, and publishes it.

Locally: `python scripts/scrape/build.py` then `python scripts/make_release.py --version v2026.10.1 --out release`.

## What is not in a release (yet)

The canonical tables (`producers`, `markets`, `outlets`, `locations` and the link tables, see `SCHEMA.md`) exist for
Chaffee County in `data/`. A statewide set and app exports built from it come next; the flat directory is the
bridge so apps can switch to the Food Web now.
