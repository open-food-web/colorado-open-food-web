"""Map filter groups: how the many Category labels in the data roll up into chips.

The data keeps precise labels ("Meat Producer & Packer", "Bakery", "Community Food
Hub" ...) because they're accurate and searchable. The map shows a short list of
groups instead; a listing appears under every group any of its labels belongs to.
Some labels are attributes rather than places to go and render as badges.

Reviewed with the maintainer 2026-10-03 (cutover step 2 uses this table).
"""
from __future__ import annotations

from typing import Dict, List

# (key, chip label, emoji, data labels) in chip order.
GROUPS = [
    ("markets", "Farmers' Markets", "🧺", {"Farmers' Market"}),
    ("farms", "Farms & Ranches", "🐄", {"On-Farm / Ranch Sales", "Meat Producer & Packer",
                                       "Farm Products (online)"}),
    ("agritourism", "Agritourism", "🌻", {"Agritourism"}),
    ("csa", "CSA & Farm Shares", "🚜", {"CSA Farm"}),
    ("stands", "Farm Stands", "🛻", {"Roadside Market"}),
    ("upick", "U-Pick", "🍓", {"U-Pick"}),
    ("garden", "Garden Centers", "🌱", {"Garden Center / Greenhouse"}),
    ("wineries", "Wineries", "🍷", {"Winery"}),
    ("shops", "Shops & Grocers", "🛒", {"Grocery Store", "Farm Store", "Bakery", "Food Maker", "Cottage Food"}),
    ("dining", "Restaurants & Caterers", "🍽️", {"Restaurant", "Caterer", "Food Truck", "Cafe / Coffee Shop"}),
    ("wholesale", "Wholesale & Food Hubs", "📦", {"Wholesale Grower", "Food Hub", "Distributor / Aggregator"}),
    ("assistance", "Food Assistance", "🥫", {"Food Bank", "Community Food Hub", "Organization"}),
    # Added 2026-10-14 (food-system scope: any food production, making, distribution or
    # consumption can be in the data set). The public map only shows groups index.html
    # styles; these are available to the data set and to other applications now.
    ("plants", "Flowers, Plants & Seeds", "🌸", {"Flower Farm", "Plant Nursery", "Seed Company"}),
    ("makers", "Food Processors", "🏭", {"Food Processor"}),
    ("drinks", "Breweries & Distilleries", "🍺", {"Brewery / Distillery"}),
    ("inputs", "Farm Inputs & Services", "🌾", {"Ag Input Supplier"}),
    ("vendors", "Market Vendors", "🧑‍🌾", {"Market Vendor"}),
]

# Groups the public map shows today (the ones index.html styles). Groups added later
# (plants, makers, drinks, inputs, vendors) are in the data set but stay off the public map
# until the maintainer enables them: what the data holds and what an app shows are separate.
PUBLIC_GROUPS = {"markets", "farms", "agritourism", "csa", "stands", "upick", "garden",
                 "wineries", "shops", "dining", "wholesale", "assistance"}

# Labels shown as a badge on the listing, not as a filter chip.
BADGES = {"Sells to Schools": "🏫 Sells to schools"}

LABEL_TO_GROUP: Dict[str, str] = {lab: key for key, _, _, labels in GROUPS for lab in labels}


def groups_for(category: str) -> List[str]:
    """'Agritourism, On-Farm / Ranch Sales' -> ['agritourism', 'farms'] (label order,
    deduped). Unknown labels are ignored here; tests guard that none exist."""
    out = []
    for lab in (c.strip() for c in (category or "").split(",")):
        key = LABEL_TO_GROUP.get(lab)
        if key and key not in out:
            out.append(key)
    return out


def unknown_labels(categories) -> List[str]:
    """Labels that belong to no group and aren't badges (should be empty)."""
    seen = {c.strip() for cat in categories for c in (cat or "").split(",") if c.strip()}
    return sorted(seen - set(LABEL_TO_GROUP) - set(BADGES))
