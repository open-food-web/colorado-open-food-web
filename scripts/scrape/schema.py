"""Normalized schema for the Colorado farmers-market scrape.

Every source is mapped into a `Market` record whose public columns are exactly the
23 My Maps columns that the Colorado Proud / Farm Fresh pipeline emits
(see scripts/fetch_farm_data.py and DATA.md). This lets the output import into the
same Google My Maps setup with no changes.

Confidence rule: a field is only ever populated when a source *states it explicitly*.
Nothing is inferred or guessed. Every populated field records which source it came
from in `.provenance`, so conflicts and coverage can be audited later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# The 23 output columns, in the exact order fetch_farm_data.py writes them.
COLUMNS = [
    "Business Name", "Category", "Address", "City", "County", "State", "Zip",
    "Phone", "Call first?", "Website", "Email", "Facebook", "Instagram",
    "Hours", "Months Open", "Products", "Certified Organic", "SNAP",
    "ADA Accessible", "Notes", "Where to Get It", "Latitude", "Longitude",
]

CATEGORY_SEP = ", "   # Category holds several labels, primary first

# Fields that may carry a source label in `provenance`. (State/Category are constant
# for this project, and Latitude/Longitude provenance is tracked via `geo_source`.)
PROVENANCED = [
    "Business Name", "Address", "City", "County", "Zip", "Phone", "Website",
    "Email", "Facebook", "Instagram", "Hours", "Months Open", "Products",
    "Certified Organic", "SNAP", "ADA Accessible", "Notes", "Where to Get It",
]


@dataclass
class Market:
    """One farmers market, normalized. All string fields default to "" (not None) so
    CSV output is clean and merge logic can treat "" uniformly as 'missing'."""

    business_name: str = ""
    # One or more labels, comma-joined, primary first ("Agritourism, On-Farm / Ranch
    # Sales") — the same format the live pipeline writes (see DATA.md). Defaults to
    # "Farmers' Market" for the market directories (Colorado Proud, CFMA); USDA and
    # Chaffee set their own; a source that states no category sets "" so merging
    # never adds a label nobody stated. Merge unions categories across sources.
    category: str = "Farmers' Market"
    address: str = ""
    city: str = ""
    county: str = ""
    state: str = "CO"
    zip: str = ""
    phone: str = ""
    call_first: str = ""
    website: str = ""
    email: str = ""
    facebook: str = ""
    instagram: str = ""
    hours: str = ""
    months_open: str = ""
    products: str = ""
    certified_organic: str = ""
    snap: str = ""
    ada_accessible: str = ""
    notes: str = ""
    # For growers that don't sell on site: "Whole Foods Market (Colorado stores); ..."
    # (semicolon-separated, as in the live Phase 1 file's "Where to Get It" column).
    where_to_get: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Bookkeeping (not written to the My Maps CSV, but kept in the raw CSV).
    # "" = open as far as we know. "Closed" = we are confident it once operated and no
    # longer does: kept in the raw CSV (so it is never re-researched or re-added), left out
    # of the public directory.
    status: str = ""
    # Year the business started; the evidence goes in the override note. Raw CSV only.
    year_opened: str = ""
    source: str = ""                 # primary source that created this record
    geo_source: str = ""             # "source" | "census-geocoder" | "" (none)
    dup_hint: str = ""               # name of a suspected duplicate, for human review
    provenance: dict = field(default_factory=dict)   # column -> source label
    source_id: str = ""              # stable id at the source (e.g. USDA listing_id)
    source_updated: str = ""         # source's own last-updated stamp (change detection)
    notes_hash: str = ""             # fingerprint of the source's description text (the text itself is not kept)

    # Display flags (raw export only). The data set holds more than a public app may show:
    # `public_listing` = it advertises a sales channel (yes/no, "" = not yet judged);
    # `local_sales_channel` = it has a local channel such as a farm stand, market, CSA pickup,
    # local delivery or local retail (yes/no/unknown); `sales_channels` = semicolon list from
    # on_farm, farm_stand, farmers_market, csa, delivery, wholesale, retail_partners, online;
    # `sales_locations` = where it sells (markets, pickup points), free text, semicolon-separated.
    public_listing: str = ""
    # "yes" = keep the full address and coordinates in the raw data, but leave them out of the
    # public output (the My Maps CSV, so no map pin). For farms whose sales happen elsewhere
    # (markets, delivery, CSA pickup, wholesale) and that have not published a visiting address.
    hide_address: str = ""
    local_sales_channel: str = ""
    sales_channels: str = ""
    sales_locations: str = ""

    def set(self, attr: str, value, source: str) -> None:
        """Set a field only if `value` is non-empty and the field is currently
        empty; record provenance. Enforces the explicit-only confidence rule and
        makes 'first source wins' the default merge behavior for a single field."""
        if value is None:
            return
        value = value.strip() if isinstance(value, str) else value
        if value == "" or value == []:
            return
        current = getattr(self, attr)
        if current in ("", None):
            setattr(self, attr, value)
            col = ATTR_TO_COLUMN.get(attr)
            if col in PROVENANCED:
                self.provenance[col] = source

    @property
    def categories(self) -> list:
        return [c.strip() for c in self.category.split(",") if c.strip()]

    def add_categories(self, labels) -> None:
        """Union `labels` into this record's categories, keeping existing order first."""
        merged = self.categories
        for label in labels:
            if label and label not in merged:
                merged.append(label)
        self.category = CATEGORY_SEP.join(merged)

    def to_mymaps_row(self, public: bool = True) -> dict:
        row = self._row()
        if public and self.hide_address == "yes":
            for col in ("Address", "Zip", "Latitude", "Longitude"):
                row[col] = ""
        return row

    def _row(self) -> dict:
        return {
            "Business Name": self.business_name,
            "Category": self.category,
            "Address": self.address,
            "City": self.city,
            "County": self.county,
            "State": self.state,
            "Zip": self.zip,
            "Phone": self.phone,
            "Call first?": self.call_first,
            "Website": self.website,
            "Email": self.email,
            "Facebook": self.facebook,
            "Instagram": self.instagram,
            "Hours": self.hours,
            "Months Open": self.months_open,
            "Products": self.products,
            "Certified Organic": self.certified_organic,
            "SNAP": self.snap,
            "ADA Accessible": self.ada_accessible,
            "Notes": self.notes,
            "Where to Get It": self.where_to_get,
            "Latitude": "" if self.latitude is None else self.latitude,
            "Longitude": "" if self.longitude is None else self.longitude,
        }


# attribute name -> output column label (for provenance bookkeeping)
ATTR_TO_COLUMN = {
    "business_name": "Business Name", "address": "Address", "city": "City",
    "county": "County", "zip": "Zip", "phone": "Phone", "website": "Website",
    "email": "Email", "facebook": "Facebook", "instagram": "Instagram",
    "hours": "Hours", "months_open": "Months Open", "products": "Products",
    "certified_organic": "Certified Organic", "snap": "SNAP",
    "ada_accessible": "ADA Accessible", "notes": "Notes",
    "where_to_get": "Where to Get It",
}
