"""USDA keyed-API field gaps found in the 2026-10-03 live spot-check of all five
directories: agritourism has no location_street, csa/foodhub carry season +
products in `mydesc`. Offline, synthetic records shaped like the live payload."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrape.sources import usda


@pytest.mark.parametrize("full,city,exp", [
    ("590 W. Colfax, Golden, CO 80401", "Golden", "590 W. Colfax"),
    ("PO Box 352, 41373 Highway 85, Ault, Colorado 80610", "Ault", "41373 Highway 85"),
    ("PO BOX 84, Mancos, Colorado 81328", "Mancos", ""),       # mailing only
    ("12 Main St, Somewhere, CO 80000", "Elsewhere", ""),       # city not found
    ("", "Golden", ""),
])
def test_street_from_address(full, city, exp):
    assert usda._street_from_address(full, city) == exp


@pytest.mark.parametrize("text,exp", [
    ("June to August", "June, July, August"),
    ("November to February", "November, December, January, February"),
    ("Year-round", ", ".join(usda._MONTHS)),
    ("Summer", ""),
    ("", ""),
])
def test_months_open(text, exp):
    assert usda._months_open(text) == exp


def _rec(**kw):
    base = {"listing_id": "1", "listing_name": "Test Farm", "location_state": "Colorado",
            "location_city": "Golden", "location_zipcode": "80401"}
    base.update(kw)
    return base


def test_agritourism_street_parsed_from_one_line_address():
    [m] = usda.parse_api({"data": [_rec(
        directory_type="agritourism",
        location_address="590 W. Colfax, Golden, CO 80401")]})
    assert m.address == "590 W. Colfax"
    assert m.provenance["Address"] == "usda"


def test_location_street_still_wins_when_present():
    [m] = usda.parse_api({"data": [_rec(
        location_street="1 Real St", location_address="9 Other Rd, Golden, CO 80401")]})
    assert m.address == "1 Real St"


def test_csa_mydesc_fills_months_and_truncated_products_go_to_notes():
    [m] = usda.parse_api({"data": [_rec(
        directory_type="csa",
        mydesc="Open: May to July<br>Available Products: Arugula; Beets; Bok Choy; ...")]})
    assert m.months_open == "May, June, July"
    assert m.products == ""   # truncated at source -> fails explicit-only bar
    assert m.notes == "Products listed on USDA: Arugula; Beets; Bok Choy (partial list)"


def test_listing_desc_keeps_priority_over_mydesc_products():
    [m] = usda.parse_api({"data": [_rec(
        listing_desc="A family farm.",
        mydesc="Open: Year-round<br>Available Products: Eggs")]})
    assert m.notes == "A family farm."
    assert m.months_open.startswith("January")
