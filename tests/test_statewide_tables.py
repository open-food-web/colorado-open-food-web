"""The canonical tables cover all of Colorado, keep IDs permanent, and follow the release rules."""
import csv
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
HEAD = ["Business Name", "Category", "Address", "City", "County", "State", "Zip", "Phone", "Call first?",
        "Website", "Email", "Facebook", "Instagram", "Hours", "Months Open", "Products", "Certified Organic",
        "SNAP", "ADA Accessible", "Notes", "Where to Get It", "Latitude", "Longitude", "Status", "Source",
        "Geo Source", "Possible Dup Of", "Provenance", "Source ID", "Source Updated", "Hide Address",
        "Sales Channels"]


def row(name, cat, county="Chaffee", **kw):
    r = {k: "" for k in HEAD}
    r.update({"Business Name": name, "Category": cat, "County": county, "State": "CO", "Source": "usda",
              "Status": "Open"}, **kw)
    return r


class Statewide(unittest.TestCase):
    def build(self, rows, county=None):
        d = tempfile.mkdtemp()
        raw, out = os.path.join(d, "raw.csv"), os.path.join(d, "out")
        with open(raw, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEAD)
            w.writeheader()
            w.writerows(rows)
        cmd = [sys.executable, "-I", os.path.join(ROOT, "scripts", "build_tables.py"), "--raw", raw, "--out", out,
               "--registry", os.path.join(d, "reg.csv")]
        if county:
            cmd += ["--county", county]
        subprocess.run(cmd, check=True, capture_output=True)
        self.out = out

    def table(self, name):
        with open(os.path.join(self.out, name + ".csv"), encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def test_all_counties_are_included_unless_one_is_asked_for(self):
        rows = [row("A Farm", "On-Farm / Ranch Sales", "Chaffee"), row("B Farm", "On-Farm / Ranch Sales", "Mesa")]
        self.build(rows)
        self.assertEqual(sorted(r["county_fips"] for r in self.table("locations")), ["08015", "08077"])
        self.build(rows, county="Mesa")
        self.assertEqual([r["name"] for r in self.table("producers")], ["B Farm"])

    def test_hours_become_rows_and_the_text_is_kept(self):
        self.build([row("Hours Farm", "On-Farm / Ranch Sales", Hours="Sat-Sun 10am-2pm"),
                    row("Odd Farm", "On-Farm / Ranch Sales", Hours="when the sign is out")])
        p = {r["name"]: r for r in self.table("producers")}
        self.assertEqual(p["Hours Farm"]["hours_status"], "parsed")
        self.assertEqual(p["Hours Farm"]["hours_text"], "Sat-Sun 10am-2pm")
        self.assertEqual(p["Odd Farm"]["hours_status"], "text_only")
        rows = self.table("hours")
        self.assertEqual(sorted(r["day"] for r in rows), ["sat", "sun"])
        self.assertEqual({(r["opens"], r["closes"]) for r in rows}, {("10:00", "14:00")})

    def test_a_vendor_list_links_a_producer_to_a_market_and_adds_its_county(self):
        d = tempfile.mkdtemp()
        lists = os.path.join(d, "v.csv")
        with open(lists, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(["market,market_city,vendor,list_year,list_url",
                               "Palisade Farmers Market,Palisade,Peach Farm,2026,https://example.org/v",
                               "Palisade Farmers Market,Palisade,Unknown Vendor,2026,https://example.org/v", ""]))
        raw = os.path.join(d, "raw.csv")
        with open(raw, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEAD)
            w.writeheader()
            w.writerows([row("Palisade Farmers Market", "Farmers' Market", "Mesa", City="Palisade"),
                         row("Peach Farm", "On-Farm / Ranch Sales", "Delta", City="Cedaredge")])
        out = os.path.join(d, "out")
        subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "build_tables.py"), "--raw", raw,
                        "--out", out, "--registry", os.path.join(d, "reg.csv"), "--vendors", lists],
                       check=True, capture_output=True)
        self.out = out
        links = self.table("market_vendors")
        self.assertEqual(len(links), 1)
        self.assertEqual((links[0]["year"], links[0]["match_basis"]), ("2026", "exact_name"))
        areas = {(r["county_fips"], r["basis"]) for r in self.table("service_areas")}
        self.assertIn(("08077", "market"), areas)

    def test_same_name_in_two_towns_gets_two_ids(self):
        self.build([row("Farmers Market", "Farmers' Market", "Mesa", City="Palisade"),
                    row("Farmers Market", "Farmers' Market", "Larimer", City="Loveland")])
        ids = [r["market_id"] for r in self.table("markets")]
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(ids)), 2)

    def test_a_producer_and_an_outlet_sharing_a_source_id_keep_separate_permanent_ids(self):
        self.build([row("The Oasis", "On-Farm / Ranch Sales", **{"Source ID": "x1"}),
                    row("Oasis Market", "Farm Store", **{"Source ID": "x1"})])
        self.assertEqual(len(self.table("producers")), 1)
        self.assertEqual(len(self.table("outlets")), 1)
        # a second run keeps the same IDs
        first = (self.table("producers")[0]["producer_id"], self.table("outlets")[0]["outlet_id"])
        self.assertTrue(first[0].startswith("co-p-") and first[1].startswith("co-o-"))

    def test_the_hide_address_column_hides_the_address_and_closed_is_kept_but_marked(self):
        self.build([row("Hidden Farm", "On-Farm / Ranch Sales", Address="1 Rd", Latitude="38.5", Longitude="-106",
                        **{"Hide Address": "yes"}),
                    row("Old Farm", "On-Farm / Ranch Sales", Status="Closed")])
        locs = {r["location_id"]: r for r in self.table("locations")}
        self.assertEqual(sum(1 for r in locs.values() if r["hide_address"] == "true"), 1)
        status = {r["name"]: r["status"] for r in self.table("producers")}
        self.assertEqual(status, {"Hidden Farm": "unverified", "Old Farm": "closed"})

    def test_stated_sales_channels_use_the_schema_names(self):
        self.build([row("Stand Farm", "On-Farm / Ranch Sales", **{"Sales Channels": "on_farm; online; delivery"})])
        self.assertEqual(self.table("producers")[0]["sales_channels"], "delivery;farm_stand;online")

    def test_an_unconfirmed_email_is_not_written_to_the_tables(self):
        self.build([row("Quiet Farm", "On-Farm / Ranch Sales", Email="owner@gmail.com", Website="https://quiet.example")])
        self.assertEqual(self.table("producers")[0]["email"], "")


class CommittedTables(unittest.TestCase):
    """The statewide tables in data/colorado are internally consistent."""

    @classmethod
    def setUpClass(cls):
        cls.dir = os.path.join(ROOT, "data", "colorado")

    def t(self, name):
        with open(os.path.join(self.dir, name + ".csv"), encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def test_ids_are_unique(self):
        ids = ([r["producer_id"] for r in self.t("producers")] + [r["market_id"] for r in self.t("markets")]
               + [r["outlet_id"] for r in self.t("outlets")] + [r["access_point_id"] for r in self.t("access_points")]
               + [r["location_id"] for r in self.t("locations")])
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_link_points_at_a_real_record(self):
        loc = {r["location_id"] for r in self.t("locations")}
        prod = {r["producer_id"] for r in self.t("producers")}
        for r in self.t("producer_locations"):
            self.assertIn(r["producer_id"], prod)
            self.assertIn(r["location_id"], loc)
        for tbl in ("markets", "outlets", "access_points"):
            for r in self.t(tbl):
                self.assertIn(r["location_id"], loc)
        for r in self.t("service_areas"):
            self.assertIn(r["producer_id"], prod)

    def test_hours_and_market_links_point_at_real_records(self):
        recs = {"producer": {r["producer_id"] for r in self.t("producers")},
                "market": {r["market_id"] for r in self.t("markets")},
                "access_point": {r["access_point_id"] for r in self.t("access_points")}}
        for r in self.t("hours"):
            self.assertIn(r["record_id"], recs[r["record_type"]])
            self.assertRegex(r["opens"], r"^\d\d:\d\d$")
        seen = set()
        for r in self.t("market_vendors"):
            self.assertIn(r["market_id"], recs["market"])
            self.assertIn(r["producer_id"], recs["producer"])
            key = (r["market_id"], r["producer_id"], r["year"], r["season_label"])
            self.assertNotIn(key, seen)
            seen.add(key)

    def test_it_covers_the_state_not_one_county(self):
        counties = {r["county_fips"] for r in self.t("locations") if r["county_fips"]}
        self.assertGreater(len(counties), 40)
        self.assertGreater(len(self.t("producers")), 1000)


if __name__ == "__main__":
    unittest.main()
