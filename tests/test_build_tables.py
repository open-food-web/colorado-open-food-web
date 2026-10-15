"""Run: python -I -m unittest discover -s tests   (from the repo root)"""
import csv
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
HEAD = ["Business Name", "Category", "Address", "City", "County", "State", "Zip", "Phone", "Call first?",
        "Website", "Email", "Facebook", "Instagram", "Hours", "Months Open", "Products", "Certified Organic",
        "SNAP", "ADA Accessible", "Notes", "Where to Get It", "Latitude", "Longitude", "Source", "Geo Source",
        "Possible Dup Of", "Provenance", "Source ID", "Source Updated"]


def row(name, cat, **kw):
    r = {k: "" for k in HEAD}
    r.update({"Business Name": name, "Category": cat, "County": "Chaffee", "State": "CO", "Source": "chaffee_provides",
              "Source ID": name.lower().replace(" ", "-")}, **kw)
    return r


class BuildTables(unittest.TestCase):
    def build(self, rows, extra=()):
        d = tempfile.mkdtemp()
        raw, out = os.path.join(d, "raw.csv"), os.path.join(d, "out")
        with open(raw, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEAD)
            w.writeheader()
            w.writerows(rows)
        subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "build_tables.py"), "--raw", raw,
                        "--county", "Chaffee", "--out", out,
                        "--registry", os.path.join(d, "reg.csv"), *extra], check=True, capture_output=True)
        self.out = out

    def table(self, name):
        with open(os.path.join(self.out, name + ".csv"), encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def test_record_types(self):
        self.build([row("A Farm", "On-Farm / Ranch Sales", Address="1 Rd", City="Salida", Latitude="38.5", Longitude="-106"),
                    row("A Market", "Farmers' Market", Address="Park", City="Salida"),
                    row("A Cafe", "Restaurant"),
                    row("A Pantry", "Food Bank"),
                    row("Garlic Co", "CSA Farm, Garden Center / Greenhouse")])
        self.assertEqual([r["name"] for r in self.table("producers")], ["A Farm", "Garlic Co"])
        self.assertEqual([r["name"] for r in self.table("markets")], ["A Market"])
        self.assertEqual([r["name"] for r in self.table("outlets")], ["A Cafe"])
        self.assertEqual([r["name"] for r in self.table("_deferred_organizations")], ["A Pantry"])

    def test_hidden_address_and_county(self):
        self.build([row("Hidden Farm", "On-Farm / Ranch Sales", Latitude="38.8", Longitude="-106.1"),
                    row("Fremont Ranch", "On-Farm / Ranch Sales", County="Fremont", Address="2 Rd")])
        places = {r["location_id"]: r for r in self.table("locations")}
        hidden = [p for p in places.values() if p["hide_address"] == "true"]
        self.assertEqual(len(hidden), 1)
        self.assertEqual(sorted(p["county_fips"] for p in places.values()), ["08015", "08043"])

    def test_one_producer_location_per_producer(self):
        self.build([row("A Farm", "On-Farm / Ranch Sales")])
        pres = self.table("producer_locations")
        self.assertEqual([p["role"] for p in pres], ["home_base"])

    def test_sales_channels_only_from_stated_categories(self):
        self.build([row("Stand Farm", "Roadside Market, U-Pick, CSA Farm, On-Farm / Ranch Sales"),
                    row("Ranch", "On-Farm / Ranch Sales")])
        ch = {r["name"]: r["sales_channels"] for r in self.table("producers")}
        self.assertEqual(ch["Stand Farm"], "csa;farm_stand;u_pick")
        self.assertEqual(ch["Ranch"], "")
    def test_partner_additions_replace_by_source_id_and_make_access_points(self):
        d = tempfile.mkdtemp()
        add = os.path.join(d, "add.csv")
        with open(add, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEAD)
            w.writeheader()
            w.writerow(row("Fridge: Salida", "Community Fridge", Address="419 D St", Source="guidestone_review",
                           **{"Source ID": "fridge", "Source Updated": "2026-10-13"}))
        self.build([row("Fridge", "Organization", **{"Source ID": "fridge"})], extra=["--additions", add])
        pts = self.table("access_points")
        self.assertEqual([(p["name"], p["kind"]) for p in pts], [("Fridge: Salida", "community_fridge")])
        self.assertEqual(self.table("_deferred_organizations"), [])
        fs = [r for r in self.table("field_sources") if r["record_type"] == "access_point"]
        self.assertTrue(fs and all(r["verified_by"] == "partner" and r["verified_on"] == "2026-10-13" for r in fs))


if __name__ == "__main__":
    unittest.main()
