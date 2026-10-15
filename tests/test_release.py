"""A release never carries descriptions, unverified emails, or anything but what the rules allow."""
import csv
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
spec = importlib.util.spec_from_file_location("make_release", os.path.join(REPO, "scripts", "make_release.py"))
mr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mr)
from scrape import contact_policy as cp  # noqa: E402

COLS = ["Business Name", "Category", "Address", "City", "County", "State", "Zip", "Phone", "Call first?",
        "Website", "Email", "Facebook", "Instagram", "Hours", "Months Open", "Products", "Certified Organic",
        "SNAP", "ADA Accessible", "Notes", "Where to Get It", "Latitude", "Longitude"]


def _write(path, rows, cols):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def test_release_strips_notes_and_unverified_emails(tmp_path, monkeypatch):
    build = tmp_path / "build"
    build.mkdir()
    base = {c: "" for c in COLS}
    rows = [dict(base, **{"Business Name": "A Farm", "City": "Salida", "Website": "https://a.farm",
                          "Email": "ok@gmail.com*bad@gmail.com", "Notes": "Copied description."}),
            dict(base, **{"Business Name": "B Farm", "City": "Salida", "Email": "x@gmail.com"})]
    _write(build / "co_farmers_markets_all_mymaps.csv", rows, COLS)
    _write(build / "co_farmers_markets_all_raw.csv", [dict(base, Source="usda")], COLS + ["Source"])
    t = cp.Table(str(tmp_path / "v.csv"))
    t.put("ok@gmail.com", "https://a.farm", cp.VERIFIED, "https://a.farm/contact")
    (build / "csa.json").write_text("[]", encoding="utf-8")
    sup = tmp_path / "sup"
    sup.mkdir()
    for n in ("nodes.csv", "edges.csv"):
        (sup / n).write_text("a,b\n", encoding="utf-8")
    (tmp_path / "places.json").write_text("{}", encoding="utf-8")
    tabs = tmp_path / "tabs"
    tabs.mkdir()
    (tabs / "producers.csv").write_text("producer_id\n", encoding="utf-8")
    monkeypatch.setattr(mr, "TABLES", str(tabs))
    monkeypatch.setattr(mr, "PLACES", str(tmp_path / "places.json"))
    monkeypatch.setattr(mr, "SUPPLY", str(sup))
    monkeypatch.setattr(mr, "BUILD", str(build))
    monkeypatch.setattr(mr.cp, "Table", lambda *a, **k: t)
    monkeypatch.setattr(sys, "argv", ["make_release.py", "--version", "v2026.10.1", "--out", str(tmp_path / "out")])
    mr.main()
    out = list(csv.DictReader(open(tmp_path / "out" / "directory.csv", encoding="utf-8")))
    assert [r["Email"] for r in out] == ["ok@gmail.com", ""]
    assert all(r["Notes"] == "" for r in out)
    m = json.load(open(tmp_path / "out" / "MANIFEST.json"))
    assert m["version"] == "v2026.10.1" and m["files"]["directory.csv"]["rows"] == 2
    assert m["files"]["directory.csv"]["sha256"] == mr.sha256(str(tmp_path / "out" / "directory.csv"))


def test_version_must_look_like_a_calendar_release(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(sys, "argv", ["make_release.py", "--version", "latest", "--out", str(tmp_path)])
    with pytest.raises(SystemExit):
        mr.main()
