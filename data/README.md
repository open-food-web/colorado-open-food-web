# data/

The canonical tables for all of Colorado, built from the raw build and kept in step with the schema
([../docs/SCHEMA.md](../docs/SCHEMA.md)). Generated; do not edit by hand.

- `colorado/`: `producers`, `markets`, `outlets`, `access_points`, `locations`, `producer_locations`,
  `service_areas`, `source_links`, `field_sources`. `_deferred_organizations.csv` holds food banks and
  organizations, which the schema defers to v2. Rebuild with:

  ```bash
  python scripts/scrape/build.py
  python scripts/build_tables.py --raw .cache/build/co_farmers_markets_all_raw.csv --out data/colorado \
      --additions data/partner-additions/guidestone_2026-10-13.csv
  ```

  Emails appear only when the business lists them itself (see `docs/PIPELINE.md`); a partner file's own
  contact details are kept as the partner states them.
- `id_registry.csv`: stable IDs. A business keeps its ID across runs and IDs are never reused.
- `partner-additions/`: rows supplied by partners in the raw layout, merged in by `--additions`. A row replaces
  the raw row with the same Source ID and is marked partner-verified.
- `towns.csv`: town centres, used to place the pin for a hidden address.

Apps do not read these tables. They read an app export (`docs/EXPORTS.md`) or a release (`docs/RELEASES.md`).
