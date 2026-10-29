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
from export_app import compact_hours as export_app_compact, clean_city  # noqa: E402


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
        self.assertFalse(loc["pin"])      # a town is not a place: it is listed by its town, never drawn on a map
        self.assertFalse(loc["pin_unconfirmed_home"])

    def test_statewide_covers_all_64_counties_and_counts_records_with_no_county(self):
        rows = [row("Hidden Farm", "On-Farm / Ranch Sales", Latitude="38.80", Longitude="-106.10")]
        doc = self.export(rows, extra=("--statewide",))
        self.assertEqual(len(doc["export"]["county_fips"]), 64)
        self.assertIn("08014", doc["export"]["county_fips"])
        self.assertEqual(doc["vocab"]["counties"]["08015"], "Chaffee")
        self.assertEqual(doc["vocab"]["counties"]["08014"], "Broomfield")
        self.assertEqual(len(doc["vocab"]["counties"]), 64)
        self.assertEqual(doc["export"]["format_version"], 3)
        self.assertEqual(self.export(rows, extra=("--county-fips", "all"))["export"]["county_fips"], doc["export"]["county_fips"])
        c = doc["export"]["counts"]
        self.assertEqual(c["excluded_no_county"]["producers"], 0)
        self.assertEqual(c["excluded_outside_area"]["producers"], 0)

    def test_records_without_a_county_are_counted_not_lost(self):
        rows = [row("Placed Farm", "On-Farm / Ranch Sales", Latitude="38.80", Longitude="-106.10"),
                row("Nowhere Farm", "On-Farm / Ranch Sales")]
        def strip_locations(tables, pid):
            for name in ("producer_locations", "service_areas"):
                path = os.path.join(tables, name + ".csv")
                with open(path, encoding="utf-8", newline="") as f:
                    r = list(csv.DictReader(f))
                with open(path, "w", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=list(r[0].keys()), lineterminator="\n")
                    w.writeheader()
                    w.writerows(x for x in r if x["producer_id"] != pid)
        d = tempfile.mkdtemp()
        raw, tables, out = os.path.join(d, "raw.csv"), os.path.join(d, "tables"), os.path.join(d, "app.json")
        with open(raw, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEAD)
            w.writeheader()
            w.writerows(rows)
        subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "build_tables.py"), "--raw", raw,
                        "--county", "Chaffee", "--out", tables, "--registry", os.path.join(d, "reg.csv")],
                       check=True, capture_output=True)
        with open(os.path.join(tables, "producers.csv"), encoding="utf-8", newline="") as f:
            self._prod = list(csv.DictReader(f))
        total = len(self._prod)
        strip_locations(tables, next(p["producer_id"] for p in self._prod if p["name"] == "Nowhere Farm"))
        res = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "export_app.py"), "--tables", tables,
                              "--out", out, "--release", "2026-11", "--statewide"], check=True, capture_output=True, text=True)
        with open(out, encoding="utf-8") as f:
            c = json.load(f)["export"]["counts"]
        self.assertEqual(c["excluded_no_county"]["producers"], 1)
        self.assertEqual(c["producers"] + c["excluded_no_county"]["producers"] + c["excluded_outside_area"]["producers"], total)
        self.assertIn("excluded_no_county", res.stdout)

    def test_county_export_counts_other_counties_as_outside_area(self):
        doc = self.export([row("Hidden Farm", "On-Farm / Ranch Sales", Latitude="38.80", Longitude="-106.10")])
        self.assertEqual(doc["vocab"]["counties"], {"08015": "Chaffee"})
        self.assertEqual(doc["export"]["counts"]["excluded_no_county"]["producers"], 0)

    def test_unknown_county_fips_is_refused(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.export([row("Hidden Farm", "On-Farm / Ranch Sales")], extra=("--county-fips", "08999"))

    def test_removed_config_keys_are_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "old.json")
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump({"exclude_categories": {"Bakery": "x"}}, f)
            with self.assertRaises(subprocess.CalledProcessError):
                self.export([row("A Farm", "On-Farm / Ranch Sales")], extra=("--config", cfg))

    def test_statewide_config_is_valid_and_every_exclusion_has_a_reason(self):
        with open(os.path.join(ROOT, "exports", "open-food-web.config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(sorted(cfg["exclude_producer_types"]), ["bakery"])
        self.assertEqual(cfg["exclude_only_source_categories"], ["Agritourism"])   # a farm that also sells at the farm stays
        self.assertNotIn("exclude_categories", cfg)   # categories are gone from the model: scope is by producer type
        self.assertEqual(sorted(cfg["include_outlet_kinds"]), ["apothecary", "farm_store", "garden_center", "grocery"])
        self.assertIn("PROPOSAL", cfg["_comment"])

    def test_outlets_are_exported_only_when_the_app_asks_for_them(self):
        rows = [row("Herb Shop", "Apothecary", Address="138 W 1st St", City="Salida", Latitude="38.53", Longitude="-105.99"),
                row("Hidden Farm", "On-Farm / Ranch Sales", Latitude="38.80", Longitude="-106.10")]
        plain = self.export(rows)
        self.assertNotIn("outlets", plain)
        self.assertNotIn("outlets", plain["export"]["counts"])
        cfg = os.path.join(tempfile.mkdtemp(), "app.config.json")
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump({"include_outlet_kinds": ["apothecary"]}, f)
        doc = self.export(rows, extra=("--config", cfg))
        self.assertEqual([o["name"] for o in doc["outlets"]], ["Herb Shop"])
        o = doc["outlets"][0]
        self.assertEqual((o["kind"], o["group"]), ("apothecary", "shops"))
        self.assertTrue(o["location"]["pin"])
        self.assertEqual(doc["export"]["counts"]["outlets"], 1)
        self.assertEqual(doc["vocab"]["outlet_groups"]["shops"], "Shops & Grocers")
        # the pin count stays producers + markets + access points, so a site that predates outlets still checks out
        self.assertEqual(doc["export"]["counts"]["pins"], plain["export"]["counts"]["pins"])

    def test_on_farm_channels_carry_their_text_and_nothing_is_guessed(self):
        import export_app
        # parse: a channel and its text; channels we do not know are ignored
        self.assertEqual(export_app.parse_details("farm_stand|Tue 4:00pm - 6:00pm;tour|By booking;bogus|x;by_appointment|y"),
                         {"farm_stand": "Tue 4:00pm - 6:00pm", "tour": "By booking"})
        self.assertEqual(export_app.parse_details("farm_visit|Sat-Sun 1:00pm - 4:00pm"), {"farm_visit": "Sat-Sun 1:00pm - 4:00pm"})
        self.assertEqual(export_app.parse_details(""), {})
        # derived from the listing: a farm stand shows its hours only when they contain times; pick-your-own says "by appointment" when it does
        d = tempfile.mkdtemp()
        kinds = os.path.join(d, "kinds.csv")
        with open(kinds, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(["name", "producer_type", "product_groups", "farm_pickup", "visit_note", "channel_details"])
            w.writerow(["Booked Farm", "farm", "", "", "", "tour|Book at https://example.org/tour"])
        doc = self.export([
            row("Stand Farm", "Roadside Market", Address="1 Rd", Latitude="38.5", Longitude="-106", Hours="Fri: 2 pm - 7 pm"),
            row("Pick Farm", "U-Pick", Address="2 Rd", Latitude="38.6", Longitude="-106", Hours="By appointment only"),
            row("Booked Farm", "On-Farm / Ranch Sales", Address="3 Rd", Latitude="38.7", Longitude="-106"),
            row("Quiet Farm", "On-Farm / Ranch Sales", Address="4 Rd", Latitude="38.8", Longitude="-106", Hours="Mon: 9 am - 5 pm")],
            build_extra=["--producer-types", kinds])
        farms = self.by_name(doc)
        self.assertEqual(farms["Stand Farm"]["channel_details"], {"farm_stand": "Fri: 2 pm - 7 pm"})
        self.assertEqual(farms["Pick Farm"]["channel_details"], {"u_pick": "By appointment"})
        self.assertIn("tour", farms["Booked Farm"]["sales_channels"])                  # naming a channel in channel_details adds it
        self.assertEqual(farms["Booked Farm"]["channel_details"], {"tour": "Book at https://example.org/tour"})
        self.assertEqual(farms["Quiet Farm"]["channel_details"], {})                   # no channel, so nothing is guessed
        self.assertNotIn("visits", farms["Stand Farm"])
        self.assertNotIn("visit_types", doc["vocab"])
        for c in ("farm_visit", "tour", "stay", "volunteer"):
            self.assertIn(c, doc["vocab"]["sales_channels"])
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

    def test_an_online_ranch_with_a_stated_farm_pickup_has_a_confirmed_pin(self):
        d = tempfile.mkdtemp()
        kinds = os.path.join(d, "kinds.csv")
        with open(kinds, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(["name", "producer_type", "product_groups", "farm_pickup", "visit_note"])
            w.writerow(["Pickup Ranch", "ranch", "", "yes", "Pick up at the ranch by arrangement"])
        doc = self.export([row("Pickup Ranch", "Farm Products (online)", Address="1 Rd", Latitude="38.5", Longitude="-106"),
                           row("Online Farm", "Farm Products (online)", Address="3 Rd", Latitude="38.7", Longitude="-106")],
                          build_extra=["--producer-types", kinds])
        farms = self.by_name(doc)
        home = farms["Pickup Ranch"]["locations"][0]
        self.assertEqual((home["pin"], home["pin_basis"]), (True, "confirmed"))    # a person said orders are collected here
        self.assertFalse(farms["Online Farm"]["locations"][0]["pin"])             # an unstated pickup stays unpinned
    def test_an_on_farm_channel_confirms_the_home_pin(self):
        d = tempfile.mkdtemp()
        kinds = os.path.join(d, "kinds.csv")
        with open(kinds, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(["name", "producer_type", "product_groups", "farm_pickup", "visit_note", "channel_details"])
            w.writerow(["Learning Center", "education", "", "no", "", "farm_visit|Sat-Sun 1:00pm - 4:00pm"])
        doc = self.export([row("Learning Center", "On-Farm / Ranch Sales", Address="1 Rd", Latitude="38.5", Longitude="-106"),
                           row("Unknown Farm", "On-Farm / Ranch Sales", Address="2 Rd", Latitude="38.6", Longitude="-106")],
                          build_extra=["--producer-types", kinds])
        farms = self.by_name(doc)
        home = farms["Learning Center"]["locations"][0]
        self.assertEqual((home["pin"], home["pin_basis"]), (True, "confirmed"))    # a person stated an on-farm channel
        self.assertEqual(farms["Learning Center"]["sales_channels"], ["farm_visit"])
        self.assertEqual(farms["Learning Center"]["channel_details"], {"farm_visit": "Sat-Sun 1:00pm - 4:00pm"})
        self.assertEqual(farms["Unknown Farm"]["locations"][0]["pin_basis"], "unconfirmed")   # nothing stated
    def test_unconfirmed_home_pins_can_be_hidden(self):
        doc = self.export([row("Unknown Farm", "On-Farm / Ranch Sales", Address="2 Rd", Latitude="38.6", Longitude="-106")],
                          extra=["--unconfirmed-home-pins", "hide"])
        self.assertFalse(self.by_name(doc)["Unknown Farm"]["locations"][0]["pin"])

    def test_hidden_home_pin_is_offered_to_apps_that_choose_to_show_it(self):
        rows = [row("Unknown Farm", "On-Farm / Ranch Sales", Address="2 Rd", Latitude="38.6", Longitude="-106"),
                row("Stand Farm", "Roadside Market", Address="1 Rd", Latitude="38.5", Longitude="-106")]
        doc = self.export(rows, extra=["--unconfirmed-home-pins", "hide"])
        farms = self.by_name(doc)
        self.assertFalse(farms["Unknown Farm"]["locations"][0]["pin"])
        self.assertTrue(farms["Unknown Farm"]["locations"][0]["pin_unconfirmed_home"])
        self.assertFalse(farms["Stand Farm"]["locations"][0]["pin_unconfirmed_home"])  # already pinned for real
        shown = self.by_name(self.export(rows))
        self.assertFalse(shown["Unknown Farm"]["locations"][0]["pin_unconfirmed_home"])

    def test_producers_carry_service_counties_and_all_outlet_kinds_can_be_exported(self):
        rows = [row("Herb Shop", "Apothecary", Address="138 W 1st St", City="Salida", Latitude="38.53", Longitude="-105.99"),
                row("Plain Farm", "On-Farm / Ranch Sales", Address="2 Rd", Latitude="38.6", Longitude="-106")]
        doc = self.export(rows, extra=["--all-outlet-kinds"])
        self.assertIn("08015", self.by_name(doc)["Plain Farm"]["service_county_fips"])
        self.assertEqual([o["name"] for o in doc["outlets"]], ["Herb Shop"])

    def test_app_config_scopes_by_producer_type_and_hides_a_pin(self):
        rows = [row("Plain Farm", "On-Farm / Ranch Sales", Address="2 Rd", Latitude="38.6", Longitude="-106"),
                row("Bread Shop", "Bakery", Address="3 Rd", Latitude="38.6", Longitude="-106"),
                row("Goat Stay", "Agritourism", Address="4 Rd", Latitude="38.6", Longitude="-106"),
                row("Social Ranch", "On-Farm / Ranch Sales", Address="5 Rd", Latitude="38.6", Longitude="-106")]
        cfg = os.path.join(tempfile.mkdtemp(), "cfg.json")
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump({"include_producer_types": ["farm", "ranch"],
                       "exclude_only_source_categories": ["Agritourism"],
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

    def test_a_pickup_place_says_which_sales_channel_it_serves(self):
        d = tempfile.mkdtemp()
        locs = os.path.join(d, "locations.csv")
        head = "name,city,role,place_name,address,place_city,zip,county,lat,lon,geo_source,hide_address,days,hours_text,season_start,season_end,market_ref,sales_channels,note,source,date".split(",")
        with open(locs, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(head)
            w.writerow([{"name": "Ranch", "role": "pickup", "place_name": "Church lot", "address": "1 Main St", "place_city": "Salida",
                         "zip": "81201", "county": "Chaffee", "lat": "38.53", "lon": "-105.99", "geo_source": "source",
                         "sales_channels": "online"}.get(h, "") for h in head])
            w.writerow([{"name": "Ranch", "role": "pickup", "market_ref": "Salida Market", "sales_channels": "farmers_market"}.get(h, "") for h in head])
        rows = [row("Ranch", "On-Farm / Ranch Sales", Address="9 Rd", Latitude="38.6", Longitude="-106.1"),
                row("Salida Market", "Farmers' Market", Address="Alpine Park, 404 E St", City="Salida", Latitude="38.5", Longitude="-106.0")]
        doc = self.export(rows, build_extra=["--locations", locs])
        places = {l["name"]: l for l in self.by_name(doc)["Ranch"]["locations"] if l["role"] == "pickup"}
        self.assertEqual(places["Church lot"]["channels"], ["online"])            # pickup point for online orders
        self.assertEqual(places["Salida Market"]["channels"], ["farmers_market"])  # a stop at the market
        home = [l for l in self.by_name(doc)["Ranch"]["locations"] if l["role"] == "home_base"][0]
        self.assertEqual(home["channels"], [])                                   # nothing stated, nothing guessed

    def test_food_access_is_a_channel_that_is_not_a_sale(self):
        d = tempfile.mkdtemp()
        locs = os.path.join(d, "locations.csv")
        head = "name,city,role,place_name,address,place_city,zip,county,lat,lon,geo_source,hide_address,days,hours_text,season_start,season_end,market_ref,sales_channels,note,source,date".split(",")
        with open(locs, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(head)
            w.writerow([{"name": "Donation Farm", "role": "home_base", "sales_channels": "food_access"}.get(h, "") for h in head])
        doc = self.export([row("Donation Farm", "On-Farm / Ranch Sales", Address="1 Rd", Latitude="38.5", Longitude="-106")],
                          build_extra=["--locations", locs])
        farm = self.by_name(doc)["Donation Farm"]
        self.assertEqual(farm["sales_channels"], ["food_access"])
        self.assertIn("food_access", doc["vocab"]["sales_channels"])
        self.assertFalse(farm["locations"][0]["pin"])      # nothing is sold to the public, so no home pin

    def test_producer_type_and_product_groups(self):
        d = tempfile.mkdtemp()
        kinds = os.path.join(d, "kinds.csv")
        with open(kinds, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(["name", "producer_type", "product_groups", "note", "source", "date"])
            w.writerow(["Sunny Place", "ranch", "", "", "", ""])
            w.writerow(["Quiet Place", "farm", "veggies", "", "", ""])
        doc = self.export([row("Sunny Place", "On-Farm / Ranch Sales", Products="Grass-fed beef, wildflower honey", Address="1 Rd", Latitude="38.5", Longitude="-106"),
                           row("Quiet Place", "On-Farm / Ranch Sales", Address="2 Rd", Latitude="38.6", Longitude="-106"),
                           row("Meat Producer Co", "Meat Producer & Packer", Address="3 Rd", Latitude="38.7", Longitude="-106")],
                          build_extra=["--producer-types", kinds])
        farms = self.by_name(doc)
        self.assertEqual(farms["Sunny Place"]["producer_type"], "ranch")
        self.assertEqual(farms["Sunny Place"]["product_groups"], ["beef-meat", "honey"])
        self.assertEqual(farms["Quiet Place"]["product_groups"], ["veggies"])   # falls back to what the business ticked
        self.assertNotIn("veggies", farms["Meat Producer Co"]["product_groups"])  # "Producer" is not "produce"
        self.assertIn("honey", doc["vocab"]["product_groups"])
        self.assertEqual(doc["vocab"]["producer_types"]["ranch"], "Ranches")

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

    def test_farm_pickup_is_a_persons_answer_else_the_listing_else_unknown(self):
        d = tempfile.mkdtemp()
        kinds = os.path.join(d, "kinds.csv")
        with open(kinds, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(["name", "producer_type", "product_groups", "farm_pickup", "visit_note"])
            w.writerow(["Closed Ranch", "ranch", "", "yes", "Pick up at the annex by arrangement"])
        doc = self.export([row("Closed Ranch", "On-Farm / Ranch Sales", Address="1 Rd", Latitude="38.5", Longitude="-106"),
                           row("Stand Farm", "Roadside Market", Address="2 Rd", Latitude="38.6", Longitude="-106"),
                           row("Mystery Farm", "On-Farm / Ranch Sales", Address="3 Rd", Latitude="38.7", Longitude="-106")],
                          build_extra=["--producer-types", kinds])
        farms = self.by_name(doc)
        self.assertEqual(farms["Closed Ranch"]["farm_pickup"], True)
        self.assertEqual(farms["Closed Ranch"]["visit_note"], "Pick up at the annex by arrangement")
        self.assertEqual(farms["Stand Farm"]["farm_pickup"], True)      # a farm stand is a place to collect an order too
        self.assertEqual(farms["Stand Farm"]["visit_basis"], {"pickup": "listing"})
        self.assertEqual(farms["Closed Ranch"]["visit_basis"], {"pickup": "set"})
        self.assertIsNone(farms["Mystery Farm"]["farm_pickup"])         # no evidence stays unknown
        self.assertNotIn("dropin_visits", farms["Stand Farm"])         # we do not label farms by whether people may drop in
    def test_farm_tours_are_evidence_for_farm_pickup(self):
        doc = self.export([row("Tour Farm", "On-Farm / Ranch Sales, Agritourism", Address="1 Rd", Latitude="38.5", Longitude="-106")])
        farm = self.by_name(doc)["Tour Farm"]
        self.assertEqual(farm["farm_pickup"], True)
    def test_a_farm_stand_carries_its_hours_never_appointment_time(self):
        doc = self.export([
            row("Stand Farm", "Roadside Market", Address="1 Rd", Latitude="38.5", Longitude="-106",
                Hours="Mon: 8 am - 6 pm; Tue: 8 am - 6 pm; Wed: 8 am - 6 pm; Sat: 9 am - 1 pm"),
            row("Appointment Farm", "U-Pick", Address="2 Rd", Latitude="38.6", Longitude="-106", Hours="Pick-your-own by appointment, June-October"),
            row("Quiet Farm", "On-Farm / Ranch Sales", Address="3 Rd", Latitude="38.7", Longitude="-106", Hours="Mon: 9 am - 5 pm")])
        farms = self.by_name(doc)
        self.assertEqual(farms["Stand Farm"]["channel_details"]["farm_stand"], "Mon-Wed: 8 am - 6 pm; Sat: 9 am - 1 pm")
        self.assertEqual(farms["Appointment Farm"]["channel_details"]["u_pick"], "By appointment")
        self.assertEqual(export_app_compact("Tue-Sun: 8:00am - 6:00pm"), "Tue-Sun: 8:00am - 6:00pm")  # already compact
        self.assertEqual(farms["Quiet Farm"]["channel_details"], {})        # no stand channel, so nothing is guessed
    def test_metadata_counts_match(self):
        doc = self.export([row("A Farm", "Roadside Market", Address="1 Rd", Latitude="38.5", Longitude="-106")])
        self.assertEqual(doc["export"]["format_version"], 3)
        self.assertEqual(doc["export"]["counts"]["producers"], len(doc["producers"]))
        self.assertEqual(doc["export"]["counts"]["pins"], 1)

    def test_city_names_are_tidied(self):
        for raw, want in [("LONGMONT", "Longmont"), ("Fort collins", "Fort Collins"), ("Rocky Ford, CO", "Rocky Ford"),
                          ("Carbondale 81623", "Carbondale"), ("McCoy", "McCoy"), ("Bennett,", "Bennett"), ("Ft. Collins", "Fort Collins"), ("CANON CITY", "Cañon City"), ("Ca�on City", "Cañon City"), ("DeBeque", "DeBeque"), ("", "")]:
            self.assertEqual(clean_city(raw), want)
        doc = self.export([row("A Farm", "Roadside Market", Address="1 Rd", City="FORT COLLINS", Latitude="38.5", Longitude="-106")])
        self.assertEqual(doc["producers"][0]["locations"][0]["city"], "Fort Collins")


if __name__ == "__main__":
    unittest.main()
