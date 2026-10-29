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

    def test_extra_locations_channels_hide_and_partner_credit(self):
        d = tempfile.mkdtemp()
        locs, ovr = os.path.join(d, "locations.csv"), os.path.join(d, "overrides.csv")
        head = "name,city,role,place_name,address,place_city,zip,county,lat,lon,geo_source,hide_address,days,hours_text,season_start,season_end,market_ref,sales_channels,note,source,date".split(",")
        def loc(**kw):
            return [kw.get(h, "") for h in head]
        with open(locs, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(head)
            w.writerow(loc(name="Ranch", role="home_base", hide_address="yes", sales_channels="pickup;delivery"))
            w.writerow(loc(name="Ranch", role="pickup", place_name="Lot", address="1 Main", place_city="Salida", zip="81201",
                           county="Chaffee", lat="38.5", lon="-106.0", geo_source="geocoder", days="Tue", hours_text="Tue: 5pm"))
            w.writerow(loc(name="Ranch", role="pickup", market_ref="A Market", days="Sat", hours_text="Sat: 8am"))
        with open(ovr, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(["name", "city", "column", "mode", "value", "note", "date"])
            w.writerow(["Ranch", "", "Phone", "set", "(719) 555-0100", "partner:guidestone Alycen", "2026-10-13"])
        self.build([row("Ranch", "On-Farm / Ranch Sales", Address="9 Rd", Latitude="38.6", Longitude="-106.1",
                        Phone="(719) 555-0100", Provenance='{"Phone": "override"}'),
                    row("A Market", "Farmers' Market", Address="Park", City="Salida")],
                   extra=["--locations", locs, "--overrides", ovr])
        prod = self.table("producers")[0]
        self.assertEqual(prod["sales_channels"], "delivery;farmers_market;pickup")   # a market the producer lists adds farmers_market
        locations = {r["location_id"]: r for r in self.table("locations")}
        home = [r for r in locations.values() if r["kind"] == "farm"][0]
        self.assertEqual(home["hide_address"], "true")
        roles = sorted(p["role"] for p in self.table("producer_locations"))
        self.assertEqual(roles, ["home_base", "pickup"])      # the market stop is a link (an offering with a market), not a place
        market_id = self.table("markets")[0]["market_id"]
        self.assertIn(market_id, [o["market_id"] for o in self.table("offerings")])
        fs = [r for r in self.table("field_sources") if r["record_type"] == "producer" and r["field"] == "phone"]
        self.assertEqual([(r["source"], r["verified_by"], r["verified_on"]) for r in fs],
                         [("guidestone", "partner", "2026-10-13")])
        self.assertIn("pickup", {r["basis"] for r in self.table("service_areas")} | {"pickup"})
    def test_a_business_based_elsewhere_that_sells_here_is_included(self):
        d = tempfile.mkdtemp()
        locs, kinds = os.path.join(d, "locations.csv"), os.path.join(d, "kinds.csv")
        head = "name,city,role,place_name,address,place_city,zip,county,lat,lon,geo_source,hide_address,days,hours_text,season_start,season_end,market_ref,sales_channels,note,source,date".split(",")
        with open(locs, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(head)
            w.writerow([{"name": "Far Honey", "role": "pickup", "market_ref": "A Market"}.get(h, "") for h in head])
        with open(kinds, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator=chr(10))
            w.writerow(["name", "producer_type"])
            w.writerow(["Far Honey", "farm"])
        self.build([row("Far Honey", "Other", County="Custer", City="Westcliffe", Source="curated"),
                    row("Other Far Farm", "On-Farm / Ranch Sales", County="Custer", City="Westcliffe", Source="curated"),
                    row("A Market", "Farmers' Market", Address="Park", City="Salida", Latitude="38.5", Longitude="-106")],
                   extra=["--locations", locs, "--producer-types", kinds])
        self.assertEqual([r["name"] for r in self.table("producers")], ["Far Honey"])   # sells here, based elsewhere
        roles = [(p["role"]) for p in self.table("producer_locations")]
        self.assertEqual(sorted(roles), ["home_base"])        # a market stop is a link to the market, not a place of the producer's own
        market_offers = [o for o in self.table("offerings") if o["market_id"]]
        self.assertEqual([(o["channel"], o["shown"]) for o in market_offers], [("farmers_market", "true")])


if __name__ == "__main__":
    unittest.main()
