"""Closed businesses stay in the dataset (raw CSV) but never reach the map file."""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrape import build, merge as merge_mod
from scrape.schema import Market
from scrape.sources import curated


def _m(name, city="Salida", **kw):
    m = Market(source="usda", category="Grocery Store")
    m.set("business_name", name, "usda")
    m.set("city", city, "usda")
    for k, v in kw.items():
        m.set(k, v, "usda")
    return m


def test_curated_closed_row_becomes_a_closed_record():
    rows = [{"Business Name": "Old Shop", "Category": "Grocery Store", "City": "Salida", "Status": "closed"},
            {"Business Name": "Ghost", "Status": "skip"}]
    out = curated.parse(rows)
    assert [(m.business_name, m.status) for m in out] == [("Old Shop", "Closed")]


def test_override_can_mark_a_record_closed():
    m = _m("Old Farm")
    merge_mod.apply_overrides([m], [{"name": "Old Farm", "city": "Salida", "column": "Status",
                                     "mode": "set", "value": "Closed", "note": "", "date": ""}])
    assert m.status == "Closed"


def test_write_keeps_closed_in_raw_but_not_in_mymaps(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "COMPILED_DIR", str(tmp_path / "c"))
    monkeypatch.setattr(build, "SOURCE_DIR", str(tmp_path / "s"))
    closed, open_ = _m("Old Farm"), _m("New Farm")
    closed.status = "Closed"
    build.write([closed, open_])
    mymaps = list(csv.DictReader(open(tmp_path / "c" / "co_farmers_markets_all_mymaps.csv", encoding="utf-8-sig")))
    raw = list(csv.DictReader(open(tmp_path / "s" / "co_farmers_markets_all_raw.csv", encoding="utf-8-sig")))
    assert [r["Business Name"] for r in mymaps] == ["New Farm"]
    assert {r["Business Name"]: r["Status"] for r in raw} == {"Old Farm": "Closed", "New Farm": "Open"}
