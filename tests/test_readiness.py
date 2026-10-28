"""scripts/readiness.py counts the same things export_app.py decides, and its tiers add up."""
import csv
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import readiness  # noqa: E402

PROD = ["producer_id", "slug", "name", "producer_type", "source_categories", "products", "product_groups", "dropin_visits", "farm_pickup",
        "website", "phone", "email", "facebook", "instagram", "sales_channels", "status", "claimed", "last_verified"]
LOC = ["location_id", "address", "city", "hide_address", "county_fips", "lat", "lon"]
PL = ["producer_id", "location_id", "role"]
MKT = ["market_id", "location_id", "status", "website", "phone"]
VEN = ["market_id", "producer_id"]


def write(d, name, head, rows):
    with open(os.path.join(d, name + ".csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=head)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in head})


class Readiness(unittest.TestCase):
    def tables(self, producers, locs, plocs, markets=(), vendors=()):
        d = tempfile.mkdtemp()
        write(d, "producers", PROD, producers)
        write(d, "locations", LOC, locs)
        write(d, "producer_locations", PL, plocs)
        write(d, "markets", MKT, markets)
        write(d, "market_vendors", VEN, vendors)
        return readiness.load(d)

    def rows(self, *a, **k):
        return {r["id"]: r for r in readiness.producer_rows(self.tables(*a, **k))}

    def base(self, pid, **kw):
        r = {"producer_id": pid, "slug": pid, "name": pid, "producer_type": "farm", "product_groups": "eggs", "phone": "555",
             "status": "unverified"}
        r.update(kw)
        return r

    def home(self, pid, **kw):
        loc = {"location_id": "l-" + pid, "address": "1 Main", "city": "Salida", "county_fips": "08015", "lat": "38.5", "lon": "-106"}
        loc.update(kw)
        return loc, {"producer_id": pid, "location_id": "l-" + pid, "role": "home_base"}

    def test_farm_stand_at_home_is_ready_and_pinned(self):
        loc, pl = self.home("a")
        r = self.rows([self.base("a", sales_channels="farm_stand")], [loc], [pl])["a"]
        self.assertEqual(r["tier"], "ready")
        self.assertTrue(r["pin"])
        self.assertTrue(r["dropin_known"])      # a farm stand implies drop-ins, as in export_app.py

    def test_csa_only_has_no_home_pin_and_nowhere_to_find_them(self):
        loc, pl = self.home("a")
        r = self.rows([self.base("a", sales_channels="csa")], [loc], [pl])["a"]
        self.assertFalse(r["pin"])
        self.assertEqual(r["missing"], ["place_to_find"])
        self.assertEqual(r["tier"], "near")

    def test_unconfirmed_channel_gives_a_light_pin_but_is_not_ready(self):
        loc, pl = self.home("a")
        r = self.rows([self.base("a")], [loc], [pl])["a"]
        self.assertTrue(r["pin_unconfirmed"])
        self.assertFalse(r["pin"])
        self.assertEqual(sorted(r["missing"]), ["channel", "place_to_find"])
        self.assertEqual(r["tier"], "gap")

    def test_hidden_address_still_pins_but_a_missing_one_does_not(self):
        h1, p1 = self.home("a", address="", hide_address="true")
        h2, p2 = self.home("b", address="")
        rows = self.rows([self.base("a", sales_channels="farm_stand"), self.base("b", sales_channels="farm_stand")],
                         [h1, h2], [p1, p2])
        self.assertTrue(rows["a"]["pin"])
        self.assertFalse(rows["b"]["pin"])

    def test_market_link_counts_only_for_a_live_market(self):
        loc, pl = self.home("a")
        mk = [{"market_id": "m1", "location_id": "x", "status": "unverified"}, {"market_id": "m2", "location_id": "x", "status": "closed"}]
        ok = self.rows([self.base("a", sales_channels="farmers_market")], [loc], [pl], mk, [{"market_id": "m1", "producer_id": "a"}])["a"]
        dead = self.rows([self.base("a", sales_channels="farmers_market")], [loc], [pl], mk, [{"market_id": "m2", "producer_id": "a"}])["a"]
        self.assertTrue(ok["place_to_find"])
        self.assertFalse(dead["place_to_find"])

    def test_closed_producers_are_skipped(self):
        loc, pl = self.home("a")
        self.assertEqual(self.rows([self.base("a", status="closed")], [loc], [pl]), {})

    def test_report_runs_for_state_and_county(self):
        loc, pl = self.home("a")
        T = self.tables([self.base("a", sales_channels="farm_stand")], [loc], [pl])
        self.assertIn("Producers: 1", readiness.report(T))
        self.assertEqual(readiness.county_label("08015"), "Chaffee (08015)")
        self.assertIn("county 08015", readiness.report(T, "08015"))

    def test_matches_the_real_export_pin_rule(self):
        """On the real tables, a confirmed pin here is exactly a confirmed pin in export_app.py."""
        import json
        out = os.path.join(tempfile.mkdtemp(), "x.json")
        fips = ["08%03d" % i for i in range(1, 126, 2)] + ["08014"]
        subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "export_app.py"), "--tables", os.path.join(ROOT, "data", "colorado"),
                        "--out", out, "--release", "t", "--county-fips"] + fips, check=True, capture_output=True)
        rows = {r["id"]: r for r in readiness.producer_rows(readiness.load(readiness.TABLES))}
        for p in json.load(open(out, encoding="utf-8"))["producers"]:
            r = rows[p["id"]]
            confirmed = any(l["pin"] and l["pin_basis"] == "confirmed" for l in p["locations"])
            self.assertEqual(confirmed, r["pin"], p["name"])
            self.assertEqual(p["dropin_visits"] is not None, r["dropin_known"], p["name"])


if __name__ == "__main__":
    unittest.main()
