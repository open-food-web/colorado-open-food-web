"""Phase 3 county columns: stated town beats market town, overrides beat both, rebuild is stable."""
import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("build_prospects", ROOT / "scripts/phase3/build_prospects.py")
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)

BY_CITY = {"crested butte": "Gunnison", "paonia": "Delta", "hygiene": "Boulder",
           "longmont": "Boulder", "denver": "Denver", "thornton": "Adams"}


def tables(overrides=None):
    return BY_CITY, overrides or {}


def test_stated_town_beats_market_town():
    # a Delta County vendor at the Crested Butte market is not a Gunnison County vendor
    assert bp.vendor_county("Zephyros", "Crested Butte Farmers Market", "Crested Butte",
                            "Paonia, CO", tables()) == ("Delta", "location_stated")


def test_market_city_is_the_fallback():
    assert bp.vendor_county("X", "M", "Crested Butte", "", tables()) == ("Gunnison", "market_city")


def test_multi_town_and_county_strings():
    assert bp.vendor_county("X", "M", "Denver", "Hygiene, CO, Longmont, CO", tables())[0] == "Boulder"
    assert bp.vendor_county("X", "M", "Denver", "Denver, CO, Thornton, CO", tables())[0] == "Denver; Adams"
    assert bp.vendor_county("X", "M", "Denver", "Chaffee County", tables())[0] == "Chaffee"


def test_unresolved_when_no_town():
    assert bp.vendor_county("X", "M", "Denver metro", "", tables()) == ("", "unresolved")


def test_override_beats_everything():
    ov = {(bp.norm("Gunnison Gardens"), "crested butte farmers market"): "Gunnison"}
    assert bp.vendor_county("Gunnison Gardens", "Crested Butte Farmers Market", "Crested Butte",
                            "Paonia, CO", tables(ov)) == ("Gunnison", "manual")


def test_every_saved_city_resolves_and_columns_are_saved():
    import pytest
    if not bp.OUT_SRC.exists():
        pytest.skip("needs the private sources checkout (FOODWEB_SOURCES)")
    by_city, _ = bp.load_county_tables()
    with open(bp.OUT_SRC / "all_vendors.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows and "County" in rows[0] and "County Source" in rows[0]
    bad = [r for r in rows if r["Market City"].lower() not in by_city and r["County Source"] != "unresolved"
           and r["County Source"] != "location_stated"]
    assert not bad
    with open(bp.SRC_ROOT / "data-compiled/phase3/prospective_farms.csv", encoding="utf-8") as f:
        assert "County Source" in next(csv.DictReader(f))
