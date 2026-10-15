"""Offline tests: source snapshots, the refresh change report, and offline collect()."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrape import build, refresh_sources, snapshots
from scrape.schema import Market


def _m(name, city="Salida", **kw):
    m = Market(business_name=name, city=city, source="x", **kw)
    m.provenance["Business Name"] = "x"
    return m


def test_snapshot_round_trip(tmp_path):
    a = _m("Farm A", phone="(719) 555-1234", latitude=38.5, longitude=-106.0, source_id="a1")
    snapshots.save("cfma", [a], str(tmp_path), fetched="2026-10-04T10:00:00-06:00")
    recs, fetched = snapshots.load("cfma", str(tmp_path))
    assert fetched == "2026-10-04T10:00:00-06:00"
    assert recs[0] == a                          # every field, incl. provenance, survives
    assert snapshots.load("missing", str(tmp_path)) == ([], None)


def test_diff_reports_new_removed_changed():
    old = [_m("Farm A", phone="1"), _m("Farm B")]
    new = [_m("Farm A", phone="2"), _m("Farm C")]
    rows = snapshots.diff(old, new)
    got = {(r["change"], r["business_name"], r["field"]) for r in rows}
    assert got == {("changed", "Farm A", "phone"), ("new", "Farm C", ""), ("removed", "Farm B", "")}


def test_refresh_saves_snapshot_and_change_report_and_keeps_old_on_failure(tmp_path):
    d = str(tmp_path)
    snapshots.save("cfma", [_m("Farm A")], d)

    def boom():
        raise OSError("down")
    res = refresh_sources.refresh(["cfma", "usda_api"], {"cfma": lambda: [_m("Farm A"), _m("Farm B")],
                                                         "usda_api": boom}, d)
    assert res["cfma"] == 2 and res["usda_api"].startswith("failed")
    assert len(snapshots.load("cfma", d)[0]) == 2
    report = open(os.path.join(d, "changes", "cfma.csv"), encoding="utf-8").read()
    assert "new" in report and "Farm B" in report
    assert snapshots.load("usda_api", d) == ([], None)     # failed source: nothing written


def test_collect_is_offline_and_ordered(tmp_path, monkeypatch):
    d = str(tmp_path)
    snapshots.save("usda_api", [_m("U")], d)
    snapshots.save("colorado_proud", [_m("C")], d)
    monkeypatch.setattr(build.enrichment, "fetch", lambda: [])
    monkeypatch.setattr(build.curated, "fetch", lambda: [_m("Curated")])
    monkeypatch.setattr(build.farm_fresh, "fetch", lambda: [_m("FarmFresh")])
    names = [m.business_name for m in build.collect(d)]
    # priority order (live Farm Fresh data right after the Colorado Proud snapshot);
    # missing snapshots skipped
    assert names == ["C", "FarmFresh", "Curated", "U"]
