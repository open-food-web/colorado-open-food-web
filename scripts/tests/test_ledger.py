"""Transaction ledger: baseline / added / changed / closed / removed events."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrape import ledger
from scrape.schema import Market


def _m(name, city="Paonia", **kw):
    m = Market(source="curated", category="On-Farm / Ranch Sales")
    m.set("business_name", name, "curated")
    m.set("city", city, "curated")
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def _events(old, new, baseline=False):
    return [(r["Event"], r["Business Name"], r["Field"], r["New Value"])
            for r in ledger.diff(ledger.snapshot_of(old), ledger.snapshot_of(new), "2026-10-08", "t", baseline)]


def test_first_run_is_baseline_then_new_records_are_added():
    a = _m("A Farm")
    assert _events([], [a], baseline=True) == [("baseline", "A Farm", "", "")]
    assert _events([a], [a, _m("B Farm")]) == [("added", "B Farm", "", "")]


def test_nothing_new_logs_nothing():
    a = _m("A Farm", phone="970-555-0100")
    assert _events([a], [_m("A Farm", phone="970-555-0100")]) == []


def test_field_change_closed_year_and_removed():
    old = [_m("A Farm", phone="1"), _m("Gone Farm")]
    new = [_m("A Farm", phone="2", year_opened="2006", status="Closed")]
    ev = _events(old, new)
    assert ("changed", "A Farm", "Phone", "2") in ev
    assert ("changed", "A Farm", "Year Opened", "2006") in ev
    assert ("closed", "A Farm", "Status", "Closed") in ev
    assert ("removed", "Gone Farm", "", "") in ev


def test_rebuild_is_stable_for_a_closed_record():
    c = _m("Old Farm", status="Closed")
    assert _events([c], [_m("Old Farm", status="Closed")]) == []
