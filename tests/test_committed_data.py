"""Integrity checks on the committed tables in data/colorado, run on every pull request.

The other table tests build from fixtures; these read the real files, so a data PR that breaks an ID,
a link or a release rule fails before it is merged.
"""
import csv
import os
import re
import unittest

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "colorado")

ID_COLUMNS = {
    "producers": ("producer_id", "co-p-"),
    "markets": ("market_id", "co-m-"),
    "outlets": ("outlet_id", "co-o-"),
    "access_points": ("access_point_id", "co-ap-"),
    "locations": ("location_id", "co-loc-"),
}


def table(name):
    with open(os.path.join(DIR, name + ".csv"), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class CommittedData(unittest.TestCase):
    def test_ids_are_unique_and_namespaced(self):
        for name, (col, prefix) in ID_COLUMNS.items():
            ids = [r[col] for r in table(name)]
            self.assertEqual(len(ids), len(set(ids)), name + " has duplicate ids")
            for i in ids:
                self.assertTrue(i.startswith(prefix), f"{name}: {i!r} should start with {prefix}")

    def test_every_link_points_at_a_real_record(self):
        loc = {r["location_id"] for r in table("locations")}
        prod = {r["producer_id"] for r in table("producers")}
        market = {r["market_id"] for r in table("markets")}
        outlet = {r["outlet_id"] for r in table("outlets")}
        for r in table("producer_locations"):
            self.assertIn(r["producer_id"], prod)
            self.assertIn(r["location_id"], loc)
        for name in ("markets", "outlets", "access_points"):
            for r in table(name):
                if r["location_id"]:
                    self.assertIn(r["location_id"], loc, name)
        for r in table("service_areas"):
            self.assertIn(r["producer_id"], prod)
        for r in table("market_vendors"):
            self.assertIn(r["market_id"], market)
            self.assertIn(r["producer_id"], prod)
        for r in table("outlet_suppliers"):
            self.assertIn(r["outlet_id"], outlet)
            self.assertIn(r["producer_id"], prod)

    def test_county_codes_are_five_digit_colorado_fips(self):
        for r in table("locations") + table("service_areas"):
            if r["county_fips"]:
                self.assertRegex(r["county_fips"], r"^08\d{3}$", r.get("location_id") or r.get("producer_id"))

    def test_no_third_party_photos_are_stored(self):
        for r in table("locations"):
            self.assertEqual(r["photo_url"], "", r["location_id"])
