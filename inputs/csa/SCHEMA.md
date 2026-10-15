# CSA enrichment — result schema

One file per target: `results/<id>.json`. Only fill a field when the farm's OWN
site (or its own Facebook/sign-up page) states it explicitly. Never guess. Leave
unknown fields as null and say why in `notes`. Dates are ISO (YYYY-MM-DD); if only
a month is stated use the 1st / last day and set `season_precision` to "month".

```json
{
 "id": "<target id>",
 "name": "...",
 "offers_csa": true | false | "unknown",   // does the farm actually run a CSA/farm-share program?
 "csa_status": "open" | "waitlist" | "full" | "opens_later" | "closed_season" | "unknown",
 "signup_url": "<direct CSA sign-up / info page, not just the homepage, or null>",
 "signup_opens": "YYYY-MM-DD or null",
 "season_start": "YYYY-MM-DD or null",
 "season_end": "YYYY-MM-DD or null",
 "season_year": 2026 | 2027 | null,        // year the dates apply to
 "season_precision": "day" | "month" | null,
 "share_types": ["Vegetables","Fruit","Eggs","Meat","Flowers","Grains","Dairy","Bread/Baked","Mushrooms","Other"],
 "frequency": "Weekly" | "Every other week" | "Monthly" | "Other" | null,
 "price": "short text, e.g. '$32/week' or '$560 full season'" | null,
 "snap_accepted": true | false | null,
 "pickup_sites": [ {"name":"","address":"","town":"","day":"Sat","time":"8am-noon","on_farm":true|false} ],
 "delivery": { "offered": true|false|null, "kind": "radius"|"zips"|"towns"|"statewide"|"other"|null,
               "radius_miles": null, "zips": [], "towns": [], "fee": null, "details": "" },
 "evidence": [ {"field":"season_start","quote_or_summary":"<short paraphrase>","url":"<page>"} ],
 "notes": "anything ambiguous, dead links, stale pages (say what year the page content is from)"
}
```
