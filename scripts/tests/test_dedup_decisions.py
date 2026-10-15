"""Multi-category merge + reviewed dedup decisions (inputs/dedup_decisions.csv)."""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrape import merge as merge_mod
from scrape.schema import Market

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _m(name, city, category="Farmers' Market", source="usda", **kw):
    m = Market(source=source, category=category)
    m.set("business_name", name, source)
    m.set("city", city, source)
    for k, v in kw.items():
        m.set(k, v, source)
    return m


def test_add_categories_unions_in_order():
    m = _m("X", "Y", category="Agritourism")
    m.add_categories(["On-Farm / Ranch Sales", "Agritourism", ""])
    assert m.category == "Agritourism, On-Farm / Ranch Sales"
    assert m.categories == ["Agritourism", "On-Farm / Ranch Sales"]


def test_merge_unions_categories_across_directories():
    a = _m("Sunny Farm", "Paonia", category="CSA Farm", phone="(970) 555-0100")
    b = _m("Sunny Farm", "Paonia", category="On-Farm / Ranch Sales")
    [out] = merge_mod.merge([a, b])
    assert out.category == "CSA Farm, On-Farm / Ranch Sales"


def test_category_less_source_adds_no_label():
    a = Market(source="official-site", category="")
    a.business_name, a.city = "Sunny Farm", "Paonia"
    b = _m("Sunny Farm", "Paonia", category="CSA Farm")
    [out] = merge_mod.merge([a, b])
    assert out.category == "CSA Farm"


def test_merge_decision_folds_and_renames():
    keep = _m("Golden Farmers Market", "Golden", website="https://goldenfarmersmarket.org")
    dupe = _m("Golden Chamber of Commerce", "Golden", source="colorado_proud",
              hours="Sat: 8am-1pm")
    other = _m("Golden Creamery", "Golden", category="Agritourism")
    out, distinct = merge_mod.apply_decisions([keep, dupe, other], [
        {"action": "merge", "name": "Golden Chamber of Commerce", "city": "Golden",
         "target_name": "Golden Farmers Market", "target_city": "Golden",
         "keep_name": "Golden Farmers Market (Golden)"},
    ])
    assert [m.business_name for m in out] == ["Golden Farmers Market (Golden)", "Golden Creamery"]
    assert out[0].hours == "Sat: 8am-1pm"                     # gap filled from the dupe
    assert out[0].website == "https://goldenfarmersmarket.org"  # target value kept
    assert out[0].provenance["Business Name"] == "dedup-decision"
    assert distinct == set()


def test_merge_decision_with_missing_record_is_reported_not_fatal(capsys):
    a = _m("Only Market", "Town")
    out, _ = merge_mod.apply_decisions([a], [
        {"action": "merge", "name": "Gone Market", "city": "Town",
         "target_name": "Only Market", "target_city": "Town"}])
    assert out == [a]
    assert "not applied" in capsys.readouterr().out


def test_distinct_decision_suppresses_dup_flag():
    a = _m("Pueblo Farmers Market", "Pueblo")
    b = _m("Pueblo Farmers Market Eastside Pop-ups", "Pueblo")
    c = _m("Pueblo Farmers Market North", "Pueblo")
    ms, distinct = merge_mod.apply_decisions([a, b, c], [
        {"action": "distinct", "name": "Pueblo Farmers Market Eastside Pop-ups",
         "city": "Pueblo", "target_name": "Pueblo Farmers Market", "target_city": "Pueblo"}])
    merge_mod.flag_possible_dups(ms, distinct=distinct)
    assert b.dup_hint == ""                         # confirmed distinct from a; unrelated to c
    assert a.dup_hint == "Pueblo Farmers Market North"   # an unreviewed pair still flags


def test_committed_decisions_file_is_well_formed():
    path = os.path.join(REPO, "inputs", "dedup_decisions.csv")
    rows = merge_mod.load_decisions(path)
    assert rows, "decisions file should not be empty"
    for r in rows:
        assert r["action"] in ("merge", "distinct"), r
        assert r["name"] and r["target_name"], r   # city may be blank (some Chaffee records have none)


def test_override_set_and_prepend_win_over_sources():
    m = _m("Scanga Meat Company", "Salida", notes="Family meat market since 1952.")
    merge_mod.apply_overrides([m], [
        {"name": "Scanga Meat Company", "city": "Salida", "column": "Category", "mode": "set",
         "value": "Meat Producer & Packer"},
        {"name": "Scanga Meat Company", "city": "Salida", "column": "Notes", "mode": "prepend",
         "value": "Meat producer and meat packer."},
    ])
    assert m.category == "Meat Producer & Packer"
    assert m.notes == "Meat producer and meat packer. Family meat market since 1952."
    assert m.provenance["Notes"] == "override" and m.provenance["Category"] == "override"


def test_clear_override_empties_the_field():
    m = _m("Fountain Farmers Market", "Fountain")
    m.website = "http://hijacked.example"
    merge_mod.apply_overrides([m], [{"name": "Fountain Farmers Market", "city": "Fountain",
                                     "column": "Website", "mode": "clear", "value": ""}])
    assert m.website == "" and m.provenance["Website"] == "override"


def test_override_for_missing_record_is_reported(capsys):
    merge_mod.apply_overrides([_m("A", "B")], [
        {"name": "Gone", "city": "B", "column": "Hours", "mode": "set", "value": "x"}])
    assert "not applied" in capsys.readouterr().out


def test_committed_overrides_file_is_well_formed():
    rows = merge_mod.load_overrides(os.path.join(REPO, "inputs", "overrides.csv"))
    assert rows
    for r in rows:
        assert r["mode"] in ("set", "prepend", "clear", "remove"), r
        assert r["column"] or r["mode"] == "remove", r
        assert bool(r["value"]) == (r["mode"] in ("set", "prepend")), r  # clear/remove: no value


def test_snapshot_load_renormalizes_link_fields(tmp_path):
    from scrape import snapshots
    m = Market(source="usda", business_name="DELYAKS", city="X",
               website="https://www.yakmeat.us  , www.yaksale.com", facebook="Some Page Name",
               instagram="@yaks")
    snapshots.save("t", [m], snapshot_dir=str(tmp_path))
    [got], _ = snapshots.load("t", snapshot_dir=str(tmp_path))
    assert got.website == "https://www.yakmeat.us"
    assert got.facebook == ""                      # a page name is not a link
    assert got.instagram == "https://instagram.com/yaks"


def test_coordinate_override_sets_a_float_pin():
    m = _m("Hutchinson Ranch", "Salida")
    merge_mod.apply_overrides([m], [
        {"name": "Hutchinson Ranch", "city": "Salida", "column": "Latitude", "mode": "set", "value": "38.5165519"},
        {"name": "Hutchinson Ranch", "city": "Salida", "column": "Longitude", "mode": "set", "value": "-106.0435714"},
        {"name": "Hutchinson Ranch", "city": "Salida", "column": "Latitude", "mode": "set", "value": "north-ish"},
    ])
    assert (m.latitude, m.longitude) == (38.5165519, -106.0435714)   # the bad row is skipped
    assert m.geo_source == "override" and m.provenance["Latitude"] == "override"


def test_remove_override_drops_the_record():
    keep, gone = _m("LoCo Food Distribution", "Fort Collins"), _m("US Potato Board", "Denver Tech Center")
    ms = [keep, gone]
    merge_mod.apply_overrides(ms, [{"name": "US Potato Board", "city": "Denver Tech Center",
                                    "column": "", "mode": "remove", "value": ""}])
    assert ms == [keep]
