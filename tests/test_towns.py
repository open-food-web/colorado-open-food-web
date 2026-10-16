"""Run: python -I -m unittest discover -s tests   (from the repo root)

A statewide export must snap hidden-address pins to a town in the record's own county.
"""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL_FIPS = ["08%03d" % i for i in range(1, 126, 2)] + ["08014"]


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class StatewideTowns(unittest.TestCase):
    def test_towns_cover_every_county(self):
        have = {r["county_fips"] for r in read(os.path.join(ROOT, "data", "towns.csv"))}
        self.assertEqual(sorted(set(ALL_FIPS) - have), [])

    def test_hidden_pins_stay_in_their_own_county(self):
        out = os.path.join(tempfile.mkdtemp(), "app.json")
        subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "export_app.py"),
                        "--tables", os.path.join(ROOT, "data", "colorado"), "--out", out,
                        "--release", "2026-11", "--county-fips", *ALL_FIPS], check=True, capture_output=True)
        with open(out, encoding="utf-8") as f:
            data = json.load(f)
        towns = {(r["lat"], r["lon"]): r["county_fips"] for r in read(os.path.join(ROOT, "data", "towns.csv"))}
        town_pins = 0
        def walk(o):
            if isinstance(o, dict):
                if o.get("precision") == "town":
                    yield o
                for v in o.values():
                    yield from walk(v)
            elif isinstance(o, list):
                for v in o:
                    yield from walk(v)
        for loc in walk(data):
            if loc.get("lat") is None or not loc.get("county_fips"):
                continue
            town_pins += 1
            key = ("%.4f" % loc["lat"], "%.4f" % loc["lon"])
            self.assertEqual(towns.get(key), loc["county_fips"], loc)
        self.assertGreater(town_pins, 0)


if __name__ == "__main__":
    unittest.main()
