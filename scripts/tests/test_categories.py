"""Every Category label in the Phase 2 output must roll up into a map filter group."""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrape import categories

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def test_groups_for_multi_label_and_badges():
    assert categories.groups_for("Agritourism, On-Farm / Ranch Sales, Sells to Schools") == \
        ["agritourism", "farms"]
    assert categories.groups_for("Bakery") == ["shops"]
    assert categories.groups_for("Community Food Hub") == ["assistance"]


def test_no_label_is_left_without_a_group():
    path = os.path.join(REPO, ".cache", "build", "co_farmers_markets_all_raw.csv")
    if not os.path.exists(path):
        import pytest
        pytest.skip("run scripts/scrape/build.py first")
    with open(path, encoding="utf-8-sig") as fh:
        cats = [r["Category"] for r in csv.DictReader(fh)]
    assert categories.unknown_labels(cats) == []      # add new labels to GROUPS/BADGES
    assert "Other" not in {c.strip() for cat in cats for c in cat.split(",")}


def test_food_system_labels_roll_up_without_moving_existing_ones():
    # Added 2026-10-14: nurseries, seed companies, processors, distributors, vendors ...
    assert categories.groups_for("Flower Farm") == ["plants"]
    assert categories.groups_for("Plant Nursery, Seed Company") == ["plants"]
    assert categories.groups_for("Food Processor") == ["makers"]
    assert categories.groups_for("Distributor / Aggregator") == ["wholesale"]
    assert categories.groups_for("Brewery / Distillery") == ["drinks"]
    assert categories.groups_for("Ag Input Supplier") == ["inputs"]
    assert categories.groups_for("Market Vendor") == ["vendors"]
    assert categories.groups_for("Cottage Food, Food Truck") == ["shops", "dining"]
    # existing mappings are unchanged
    assert categories.groups_for("Food Maker") == ["shops"]
    assert categories.groups_for("Garden Center / Greenhouse") == ["garden"]
    assert categories.groups_for("Meat Producer & Packer") == ["farms"]


def test_public_groups_exclude_the_newer_groups_and_cover_the_original_ones():
    original = {"markets", "farms", "agritourism", "csa", "stands", "upick", "garden",
                "wineries", "shops", "dining", "wholesale", "assistance"}
    assert categories.PUBLIC_GROUPS == original
    assert {k for k, *_ in categories.GROUPS} >= categories.PUBLIC_GROUPS
    for newer in ("plants", "makers", "drinks", "inputs", "vendors"):
        assert newer not in categories.PUBLIC_GROUPS


def test_hide_address_keeps_raw_but_blanks_public_row():
    from scrape.schema import Market
    m = Market(business_name="Test Farm", category="On-Farm / Ranch Sales", address="1 Farm Rd",
               city="Town", zip="80000", latitude=39.0, longitude=-105.0, hide_address="yes")
    pub = m.to_mymaps_row()
    assert pub["Address"] == "" and pub["Latitude"] == "" and pub["Longitude"] == "" and pub["Zip"] == ""
    assert pub["City"] == "Town"
    raw = m.to_mymaps_row(public=False)
    assert raw["Address"] == "1 Farm Rd" and raw["Latitude"] == 39.0
    shown = Market(business_name="Shop", address="2 Main St", latitude=39.1, longitude=-105.1)
    assert shown.to_mymaps_row()["Address"] == "2 Main St"
