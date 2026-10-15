"""Live Phase 1 data (Colorado Proud Farm Fresh, hand-maintained) as a Phase 2 source."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrape.sources import farm_fresh


def test_parse_keeps_hand_fixes_and_normalizes_links():
    [m] = farm_fresh.parse([{
        "Business Name": " Jones Farms Organics ", "Category": "Wholesale Grower",
        "Address": "11221 E County Rd 110 N", "City": "Hooper", "County": "Alamosa",
        "Phone": "(719) 378-2299", "Call first?": "Yes", "Website": "jonesfarmsorganics.com",
        "Facebook": "@jonesfarms", "Instagram": "Jones Farms Page", "Certified Organic": "Yes",
        "Where to Get It": "Whole Foods Market (Colorado stores); Boulder County Farmers Markets",
        "Latitude": "37.7", "Longitude": "-105.9"}])
    assert m.business_name == "Jones Farms Organics"
    assert m.category == "Wholesale Grower"             # live labels pass through as-is
    assert m.where_to_get.startswith("Whole Foods Market")
    assert m.website.startswith("http") and m.facebook == "https://facebook.com/jonesfarms"
    assert m.instagram == ""                            # a page name is not a link
    assert (m.latitude, m.geo_source) == (37.7, "source")
    assert m.provenance["Where to Get It"] == farm_fresh.SOURCE


def test_live_file_loads_every_listing():
    assert len(farm_fresh.fetch()) >= 160
