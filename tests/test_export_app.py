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


sys.path.insert(0, os.path.join(ROOT, "scripts"))
from export_app import compact_hours as export_app_compact  # noqa: E402


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

    def test_app_config_scopes_by_category_and_hides_a_pin(self):
        rows = [row("Plain Farm", "On-Farm / Ranch Sales", Address="2 Rd", Latitude="38.6", Longitude="-106"),
                row("Bread Shop", "Bakery", Address="3 Rd", Latitude="38.6", Longitude="-106"),
                row("Goat Stay", "Agritourism", Address="4 Rd", Latitude="38.6", Longitude="-106"),
                row("Social Ranch", "On-Farm / Ranch Sales", Address="5 Rd", Latitude="38.6", Longitude="-106")]
        cfg = os.path.join(tempfile.mkdtemp(), "cfg.json")
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump({"include_categories": {"On-Farm / Ranch Sales": "x"},
                       "exclude_categories": {"Agritourism": "x"},
                       "hide_pin_slugs": {"social-ranch": "x"}}, f)
        names = self.by_name(self.export(rows, extra=["--config", cfg]))
        self.assertEqual(set(names), {"Plain Farm", "Social Ranch"})
        self.assertTrue(names["Plain Farm"]["locations"][0]["pin"])
        self.assertFalse(names["Social Ranch"]["locations"][0]["pin"])

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

    def test_confirmed_by_names_the_partner_or_the_business_page(self):
        d = tempfile.mkdtemp()
        ovr = os.path.join(d, "overrides.csv")
        with open(ovr, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(["name", "city", "column", "mode", "value", "note", "date"])
            w.writerow(["Ranch", "", "Phone", "set", "(719) 555-0100", "partner:guidestone Alycen", "2026-10-13"])
            w.writerow(["Ranch", "", "Products", "set", "Eggs", "via:facebook https://www.facebook.com/RanchPage/ seen", "2026-10-15"])
        doc = self.export([row("Ranch", "On-Farm / Ranch Sales", Address="9 Rd", Latitude="38.6", Longitude="-106.1",
                               Phone="(719) 555-0100", Products="Eggs", Provenance='{"Phone": "override", "Products": "override"}')],
                          build_extra=["--overrides", ovr])
        conf = {c["by"]: c for c in self.by_name(doc)["Ranch"]["confirmed_by"]}
        self.assertEqual(conf["Guidestone Colorado"]["fields"], ["phone"])
        self.assertEqual(conf["Guidestone Colorado"]["date"], "2026-10-13")
        self.assertEqual(conf["the business's Facebook page"]["fields"], ["products"])
        self.assertEqual(conf["the business's Facebook page"]["url"], "https://www.facebook.com/RanchPage/")

    def test_visit_flags_are_separate_and_never_assumed(self):
        d = tempfile.mkdtemp()
        kinds = os.path.join(d, "kinds.csv")
        with open(kinds, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(["name", "kind", "product_groups", "dropin_visits", "farm_pickup", "visit_note"])
            w.writerow(["Closed Ranch", "ranch", "", "no", "yes", "Pick up at the annex by arrangement"])
        doc = self.export([row("Closed Ranch", "On-Farm / Ranch Sales", Address="1 Rd", Latitude="38.5", Longitude="-106"),
                           row("Stand Farm", "Roadside Market", Address="2 Rd", Latitude="38.6", Longitude="-106"),
                           row("Mystery Farm", "On-Farm / Ranch Sales", Address="3 Rd", Latitude="38.7", Longitude="-106")],
                          build_extra=["--kinds", kinds])
        farms = self.by_name(doc)
        self.assertEqual((farms["Closed Ranch"]["dropin_visits"], farms["Closed Ranch"]["farm_pickup"]), (False, True))
        self.assertEqual(farms["Closed Ranch"]["visit_note"], "Pick up at the annex by arrangement")
        self.assertEqual(farms["Stand Farm"]["dropin_visits"], True)    # a stated farm stand means drop-ins
        self.assertEqual(farms["Stand Farm"]["farm_pickup"], True)      # visits advertised, so farm pickup too
        self.assertEqual(farms["Stand Farm"]["visit_basis"], {"dropin": "listing", "pickup": "listing"})
        self.assertEqual(farms["Closed Ranch"]["visit_basis"], {"dropin": "set", "pickup": "set"})
        self.assertIsNone(farms["Mystery Farm"]["dropin_visits"])      # no evidence stays unknown
        self.assertIsNone(farms["Mystery Farm"]["farm_pickup"])

    def test_farm_tours_are_evidence_for_farm_pickup_but_not_drop_ins(self):
        doc = self.export([row("Tour Farm", "On-Farm / Ranch Sales, Agritourism", Address="1 Rd", Latitude="38.5", Longitude="-106")])
        farm = self.by_name(doc)["Tour Farm"]
        self.assertEqual(farm["farm_pickup"], True)
        self.assertIsNone(farm["dropin_visits"])

    def test_dropin_hours_are_the_stand_hours_and_never_appointment_time(self):
        doc = self.export([
            row("Stand Farm", "Roadside Market", Address="1 Rd", Latitude="38.5", Longitude="-106",
                Hours="Mon: 8 am - 6 pm; Tue: 8 am - 6 pm; Wed: 8 am - 6 pm; Sat: 9 am - 1 pm"),
            row("Appointment Farm", "U-Pick", Address="2 Rd", Latitude="38.6", Longitude="-106", Hours="Pick-your-own by appointment, June-October"),
            row("Quiet Farm", "On-Farm / Ranch Sales", Address="3 Rd", Latitude="38.7", Longitude="-106", Hours="Mon: 9 am - 5 pm")])
        farms = self.by_name(doc)
        self.assertEqual(farms["Stand Farm"]["dropin_hours"], "Mon-Wed: 8 am - 6 pm; Sat: 9 am - 1 pm")
        self.assertIsNone(farms["Appointment Farm"]["dropin_hours"])
        self.assertEqual(export_app_compact("Tue-Sun: 8:00am - 6:00pm"), "Tue-Sun: 8:00am - 6:00pm")  # already compact
        self.assertIsNone(farms["Quiet Farm"]["dropin_hours"])     # drop-ins unknown, so no drop-in hours

    def test_metadata_counts_match(self):
        doc = self.export([row("A Farm", "Roadside Market", Address="1 Rd", Latitude="38.5", Longitude="-106")])
        self.assertEqual(doc["export"]["format_version"], 1)
        self.assertEqual(doc["export"]["counts"]["producers"], len(doc["producers"]))
        self.assertEqual(doc["export"]["counts"]["pins"], 1)


if __name__ == "__main__":
    unittest.main()
