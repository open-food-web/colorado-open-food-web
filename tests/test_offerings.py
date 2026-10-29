"""scripts/offerings.py: a market link has two sides (the market's vendor list, the producer's own page), reconciled into one offering."""
import os
import sys
import unittest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import offerings  # noqa: E402


def nkey(s):
    import re
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def world(vendor_links=(), market_status="listed"):
    producers = [{"producer_id": "p1", "name": "Alder Farm", "sales_channels": "farmers_market", "channel_details": ""},
                 {"producer_id": "p2", "name": "Birch Ranch", "sales_channels": "", "channel_details": ""}]
    markets = [{"market_id": "m1", "name": "Salida Market", "status": market_status}, {"market_id": "m2", "name": "Vail Market", "status": "listed"}]
    vendors = [{"market_id": m, "producer_id": p, "year": "2026", "source_url": "https://list/" + m} for p, m in vendor_links]
    return {"producers": producers, "markets": markets, "market_vendors": vendors, "producer_locations": [], "offerings": []}


def row(producer, market="", on="", url="", checked="2026-10-29", resolution="", note=""):
    return {"producer": producer, "producer_city": "", "market": market, "market_city": "", "on_producer_page": on,
            "producer_page_url": url, "checked_on": checked, "resolution": resolution, "note": note}


class MarketLinks(unittest.TestCase):
    def links(self, rows, **kw):
        return offerings.reconcile(world(**kw), rows, nkey, warn=lambda *a: None)

    def test_both_sides_agree(self):
        l = self.links([row("Alder Farm", "Salida Market", "yes")], vendor_links=[("p1", "m1")])[("p1", "m1")]
        self.assertEqual((l["link_state"], l["confirmed_by_market"], l["confirmed_by_producer"], l["shown"]), ("confirmed_both", "true", "true", "true"))

    def test_only_the_producers_page_says_so(self):
        l = self.links([row("Alder Farm", "Vail Market", "yes")], vendor_links=[])[("p1", "m2")]
        self.assertEqual((l["link_state"], l["confirmed_by_market"], l["confirmed_by_producer"], l["shown"]), ("producer_only", "false", "true", "true"))

    def test_a_vendor_list_link_stays_when_the_producers_page_was_not_checked(self):
        l = self.links([], vendor_links=[("p1", "m1")])[("p1", "m1")]
        self.assertEqual((l["link_state"], l["shown"]), ("market_only", "true"))

    def test_a_page_that_names_no_markets_says_nothing_either_way(self):
        l = self.links([row("Alder Farm", "", "no_markets")], vendor_links=[("p1", "m1")])[("p1", "m1")]
        self.assertEqual((l["link_state"], l["shown"]), ("market_only", "true"))
        self.assertIn("names no markets", l["link_note"])

    def test_a_conflict_is_hidden_because_the_producers_page_wins(self):
        rows = [row("Alder Farm", "", "lists_markets"), row("Alder Farm", "Vail Market", "yes")]
        links = self.links(rows, vendor_links=[("p1", "m1"), ("p1", "m2")])
        self.assertEqual((links[("p1", "m1")]["link_state"], links[("p1", "m1")]["shown"]), ("conflict", "false"))
        self.assertEqual((links[("p1", "m2")]["link_state"], links[("p1", "m2")]["shown"]), ("confirmed_both", "true"))
        self.assertIn("hidden unless kept", links[("p1", "m1")]["link_note"])

    def test_a_person_can_keep_a_conflict_or_drop_a_link(self):
        rows = [row("Alder Farm", "", "lists_markets"), row("Alder Farm", "Salida Market", "no", resolution="keep", note="Confirmed by phone"),
                row("Birch Ranch", "Salida Market", "", resolution="drop")]
        links = self.links(rows, vendor_links=[("p1", "m1"), ("p2", "m1")])
        self.assertEqual((links[("p1", "m1")]["link_state"], links[("p1", "m1")]["shown"]), ("conflict", "true"))
        self.assertIn("Confirmed by phone", links[("p1", "m1")]["link_note"])
        self.assertEqual(links[("p2", "m1")]["shown"], "false")

    def test_a_closed_market_is_not_shown(self):
        l = self.links([], vendor_links=[("p1", "m1")], market_status="closed")[("p1", "m1")]
        self.assertEqual(l["shown"], "false")

    def test_offerings_tie_places_to_channels_and_carry_the_links(self):
        out = world(vendor_links=[("p1", "m1")])
        out["producers"][0]["sales_channels"] = "farm_stand;online;farmers_market"
        out["producers"][0]["channel_details"] = "farm_stand|Sat 9-1"
        out["producer_locations"] = [
            {"producer_id": "p1", "location_id": "home", "role": "home_base", "channels": "", "confirm_url": ""},
            {"producer_id": "p1", "location_id": "lot", "role": "pickup", "channels": "online", "confirm_url": ""},
            {"producer_id": "p1", "location_id": "church", "role": "pickup", "channels": "", "confirm_url": ""}]

        class Reg:
            def get(self, prefix, key):
                return prefix + "|" + key
        links = offerings.reconcile(out, [], nkey, warn=lambda *a: None)
        offerings.build(out, links, Reg(), lambda t: {c for c in (t or "").split(";") if c}, lambda t: dict(
            part.split("|", 1) for part in (t or "").split(";") if "|" in part))
        got = sorted((o["channel"], o["location_id"], o["market_id"], o["basis"]) for o in out["offerings"])
        self.assertEqual(got, [("farm_stand", "home", "", "derived"), ("farmers_market", "", "m1", "link"),
                               ("online", "church", "", "role"),       # no one said, so it goes by the place's role
                               ("online", "lot", "", "stated")])       # a person said which channel it serves
        self.assertEqual([o["text"] for o in out["offerings"] if o["channel"] == "farm_stand"], ["Sat 9-1"])


if __name__ == "__main__":
    unittest.main()
