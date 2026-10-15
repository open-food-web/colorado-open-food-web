"""sources.json, the fetchers and the scheduled workflows stay in step; notes never reach a snapshot."""
import json
import os
import re

from scrape import refresh_sources, snapshots
from scrape.schema import Market

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG = json.load(open(os.path.join(REPO, "sources.json"), encoding="utf-8"))
SOURCES = {k: v for k, v in CONFIG.items() if not k.startswith("_")}


def test_every_fetcher_has_an_active_entry():
    for name in refresh_sources.FETCHERS:
        assert SOURCES[name]["status"] == "active", name


def test_every_active_source_has_a_fetcher_and_a_schedule():
    for name, cfg in SOURCES.items():
        wf = os.path.join(REPO, ".github", "workflows", "refresh-%s.yml" % name.replace("_", "-"))
        if cfg["status"] == "active":
            assert name in refresh_sources.FETCHERS, name
            text = open(wf, encoding="utf-8").read()
            assert "source: %s" % name in text
            assert re.search(r'cron: "[^"]+"', text)
        else:
            assert not os.path.exists(wf), "frozen source %s must not be scheduled" % name


def test_retired_chaffee_provides_is_frozen_not_fetched():
    assert SOURCES["chaffee_provides"]["status"] == "frozen"
    assert "chaffee_provides" not in refresh_sources.FETCHERS
    assert "chaffee_provides" in snapshots.NETWORK_SOURCES   # its snapshot is still built in


def test_cfma_is_monthly():
    assert SOURCES["cfma"]["cadence"] == "monthly"


def test_snapshot_keeps_a_hash_of_notes_not_the_text(tmp_path):
    m = Market(business_name="Test Farm", city="Salida", notes="Third-party description text.")
    path = snapshots.save("t", [m], str(tmp_path))
    raw = open(path, encoding="utf-8").read()
    assert "Third-party description text." not in raw
    recs, _ = snapshots.load("t", str(tmp_path))
    assert recs[0].notes == "" and recs[0].notes_hash == snapshots.notes_id(m) != ""


def test_notes_change_is_detected_through_the_hash():
    old = Market(business_name="Test Farm", city="Salida", source_id="1", notes_hash=snapshots.notes_id(Market(notes="a")))
    new = Market(business_name="Test Farm", city="Salida", source_id="1", notes="b")
    rows = snapshots.diff([old], [new])
    assert [r["field"] for r in rows] == ["notes"]
    assert snapshots.diff([old], [Market(business_name="Test Farm", city="Salida", source_id="1", notes="a")]) == []


def test_an_empty_or_collapsed_pull_never_replaces_a_snapshot(tmp_path):
    old = [Market(business_name="Farm %d" % i, city="Salida", source_id=str(i)) for i in range(10)]
    snapshots.save("x", old, str(tmp_path))
    out = refresh_sources.refresh(["x"], fetchers={"x": lambda: []}, snapshot_dir=str(tmp_path))
    assert out["x"].startswith("failed, kept previous snapshot")
    assert len(snapshots.load("x", str(tmp_path))[0]) == 10
    out = refresh_sources.refresh(["x"], fetchers={"x": lambda: old[:7]}, snapshot_dir=str(tmp_path))
    assert out["x"] == 7


def test_the_user_agent_names_the_project_and_looks_like_a_crawler():
    from scrape.useragent import USER_AGENT
    assert USER_AGENT.startswith("Mozilla/5.0 (compatible; ColoradoOpenFoodWeb")
    assert "github.com/open-food-web" in USER_AGENT
