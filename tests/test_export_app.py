"""Run: python -I -m unittest discover -s tests   (from the repo root)"""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_build_tables import HEAD, ROOT, row  # noqa: E402


class ExportApp(unittest.TestCase):
    def export(self, rows, edit=None, extra=(), build_extra=()):
        d = tempfile.mkdtemp()
        raw, tables, out = os.path.join(d, "raw.csv"), os.path.join(d, "tables"), os.path.join(d, "x", "app.json")
        with open(raw, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEAD)
            w.writeheader()
            w.writerows(rows)
        subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "build_tables.py"), "--raw", raw,
                        "--county", "Chaffee", "--out", tables, "--registry", os.path.join(d, "reg.csv"), *build_extra],
                       check=True, capture_output=True)
        if edit:
            path = os.path.join(tables, "producers.csv")
            with open(path, encoding="utf-8", newline="") as f:
                prod = list(csv.DictReader(f))
            edit(prod)
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(prod[0].keys()), lineterminator="\n")
                w.writeheader()
                w.writerows(prod)
        subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "export_app.py"), "--tables", tables,
                        "--out", out, "--release", "2026-11", "--county-fips", "08015", *extra],
                       check=True, capture_output=True)
        with open(out, encoding="utf-8") as f:
            return json.load(f)

    def by_name(self, doc):
        return {p["name"]: p for p in doc["producers"]}

    def test_hidden_address_moves_pin_to_town_and_withholds_address(self):
        doc = self.export([row("Hidden Farm", "On-Farm / Ranch Sales", Latitude="38.80", Longitude="-106.10")])
        loc = self.by_name(doc)["Hidden Farm"]["locations"][0]
        self.assertEqual(loc["precision"], "town")
        self.assertIsNone(loc["address"])
        self.assertEqual(loc["city"], "Buena Vista")
        self.assertEqual((loc["lat"], loc["lon"]), (38.8422, -106.1311))

    def test_po_box_is_not_an_address(self):
        doc = self.export([row("Box Farm", "On-Farm / Ranch Sales", Address="P.O. Box 654", City="Poncha Springs",
                               Latitude="38.51", Longitude="-106.07")])
        loc = self.by_name(doc)["Box Farm"]["locations"][0]
        self.assertIsNone(loc["address"])
        self.assertEqual(loc["precision"], "approximate")

    def test_pin_rule(self):
        doc = self.export([
            row("Stand Farm", "Roadside Market", Address="1 Rd", Latitude="38.5", Longitude="-106"),
            row("Unknown Farm", "On-Farm / Ranch Sales", Address="2 Rd", Latitude="38.6", Longitude="-106"),
            row("Online Farm", "Farm Products (online)", Address="3 Rd", Latitude="38.7", Longitude="-106")])
        farms = self.by_name(doc)
        self.assertEqual((farms["Stand Farm"]["locations"][0]["pin"], farms["Stand Farm"]["locations"][0]["pin_basis"]),
                         (True, "confirmed"))
        self.assertEqual((farms["Unknown Farm"]["locations"][0]["pin"], farms["Unknown Farm"]["locations"][0]["pin_basis"]),
                         (True, "unconfirmed"))
        self.assertFalse(farms["Online Farm"]["locations"][0]["pin"])  # channels known, none is selling at the farm

    def test_unconfirmed_home_pins_can_be_hidden(self):
        doc = self.export([row("Unknown Farm", "On-Farm / Ranch Sales", Address="2 Rd", Latitude="38.6", Longitude="-106")],
                          extra=["--unconfirmed-home-pins", "hide"])
        self.assertFalse(self.by_name(doc)["Unknown Farm"]["locations"][0]["pin"])

    def test_closed_and_removed_leave_the_file(self):
        def edit(prod):
            for p in prod:
                p["status"] = {"Closed Farm": "closed", "Gone Farm": "removed"}.get(p["name"], p["status"])
        doc = self.export([row(n, "On-Farm / Ranch Sales", Address="1 Rd", Latitude="38.5", Longitude="-106")
                           for n in ("Open Farm", "Closed Farm", "Gone Farm")], edit=edit)
        self.assertEqual(list(self.by_name(doc)), ["Open Farm"])
        self.assertEqual(len(doc["removed_ids"]), 1)

    def test_opted_out_field_is_blanked(self):
        def edit(prod):
            prod[0]["opted_out_fields"] = "phone;email"
        doc = self.export([row("Shy Farm", "On-Farm / Ranch Sales", Phone="(719) 555-0100", Email="a@b.co",
                               Address="1 Rd", Latitude="38.5", Longitude="-106")], edit=edit)
        farm = self.by_name(doc)["Shy Farm"]
        self.assertIsNone(farm["phone"])
        self.assertIsNone(farm["email"])

    def test_a_producer_pickup_at_a_market_is_named_for_the_market(self):
        d = tempfile.mkdtemp()
        locs = os.path.join(d, "locations.csv")
        head = "name,city,role,place_name,address,place_city,zip,county,lat,lon,geo_source,hide_address,days,hours_text,season_start,season_end,market_ref,sales_channels,note,source,date".split(",")
        with open(locs, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(head)
            w.writerow([{"name": "Ranch", "role": "pickup", "market_ref": "Salida Market"}.get(h, "") for h in head])
        rows = [row("Ranch", "On-Farm / Ranch Sales", Address="9 Rd", Latitude="38.6", Longitude="-106.1"),
                row("Salida Market", "Farmers' Market", Address="Alpine Park, 404 E St", City="Salida", Latitude="38.5", Longitude="-106.0")]
        doc = self.export(rows, build_extra=["--locations", locs])
        pickup = [l for l in self.by_name(doc)["Ranch"]["locations"] if l["role"] == "pickup"][0]
        self.assertEqual(pickup["name"], "Salida Market")

    def test_kind_and_product_groups(self):
        d = tempfile.mkdtemp()
        kinds = os.path.join(d, "kinds.csv")
        with open(kinds, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(["name", "kind", "product_groups", "note", "source", "date"])
            w.writerow(["Sunny Place", "ranch", "", "", "", ""])
            w.writerow(["Quiet Place", "farm", "veggies", "", "", ""])
        doc = self.export([row("Sunny Place", "On-Farm / Ranch Sales", Products="Grass-fed beef, wildflower honey", Address="1 Rd", Latitude="38.5", Longitude="-106"),
                           row("Quiet Place", "On-Farm / Ranch Sales", Address="2 Rd", Latitude="38.6", Longitude="-106"),
                           row("Meat Producer Co", "Meat Producer & Packer", Address="3 Rd", Latitude="38.7", Longitude="-106")],
                          build_extra=["--kinds", kinds])
        farms = self.by_name(doc)
        self.assertEqual(farms["Sunny Place"]["kind"], "ranch")
        self.assertEqual(farms["Sunny Place"]["product_groups"], ["beef-meat", "honey"])
        self.assertEqual(farms["Quiet Place"]["product_groups"], ["veggies"])   # falls back to what the business ticked
        self.assertNotIn("veggies", farms["Meat Producer Co"]["product_groups"])  # "Producer" is not "produce"
        self.assertIn("honey", doc["vocab"]["product_groups"])
        self.assertEqual(doc["vocab"]["kinds"]["ranch"], "Ranches")

    def test_metadata_counts_match(self):
        doc = self.export([row("A Farm", "Roadside Market", Address="1 Rd", Latitude="38.5", Longitude="-106")])
        self.assertEqual(doc["export"]["format_version"], 1)
        self.assertEqual(doc["export"]["counts"]["producers"], len(doc["producers"]))
        self.assertEqual(doc["export"]["counts"]["pins"], 1)


if __name__ == "__main__":
    unittest.main()
