"""The producer type and `sales_channels` mapping from the directory labels (docs/PROPOSAL_PRODUCER_TYPE.md).

Every producer label must land somewhere: either it says what the business is (producer type) or how it sells (a channel),
so retiring `categories` loses nothing."""
import csv
import os
import sys
import unittest

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_tables as bt  # noqa: E402


class ProducerType(unittest.TestCase):
    def test_every_producer_label_lands_in_producer_type_or_a_channel(self):
        for label in bt.PRODUCER_CATS:
            ptype = bt.producer_type("Some Business", [label])
            self.assertIn(ptype, bt.PRODUCER_TYPES, label)
            says_how_it_sells = label in bt.CHANNEL or label in bt.SELLING_ONLY
            says_what_it_is = ptype != "farm" or label in bt.SELLING_ONLY
            self.assertTrue(says_how_it_sells or says_what_it_is, "%s says neither what it is nor how it sells" % label)

    def test_selling_labels_become_channels(self):
        self.assertEqual(bt.channels({}, ["Roadside Market"]), "farm_stand")
        self.assertEqual(bt.channels({}, ["U-Pick"]), "u_pick")
        self.assertEqual(bt.channels({}, ["CSA Farm"]), "csa")
        self.assertEqual(bt.channels({}, ["Farm Products (online)"]), "online")
        self.assertEqual(bt.channels({}, ["Wholesale Grower"]), "wholesale")

    def test_what_a_business_is(self):
        k = bt.producer_type
        self.assertEqual(k("A", ["Winery"]), "winery")
        self.assertEqual(k("A", ["Bakery"]), "bakery")
        self.assertEqual(k("A", ["Food Maker"]), "maker")
        self.assertEqual(k("A", ["Bakery", "Food Maker"]), "bakery")
        self.assertEqual(k("A", ["Meat Producer & Packer"]), "ranch")
        self.assertEqual(k("Blue Mesa Cattle Co", ["On-Farm / Ranch Sales"]), "ranch")
        self.assertEqual(k("A", ["On-Farm / Ranch Sales"]), "farm")
        self.assertEqual(k("A", ["Wholesale Grower"]), "farm")
        self.assertEqual(k("A", ["Agricultural Education"]), "education")

    def test_agritourism_is_a_sales_channel_not_a_producer_type(self):
        k = bt.producer_type
        self.assertNotIn("agritourism", bt.PRODUCER_TYPES)
        self.assertEqual(k("A", ["Agritourism"]), "farm")
        self.assertEqual(k("A", ["Agritourism", "On-Farm / Ranch Sales"]), "farm")
        self.assertEqual(k("A", ["Agritourism", "Meat Producer & Packer"]), "ranch")
        self.assertEqual(bt.channels({}, ["Agritourism"]), "agritourism")
        self.assertEqual(bt.channels({}, ["Agritourism", "CSA Farm"]), "agritourism;csa")

    def test_a_bakery_that_is_also_a_farm_stays_a_farm(self):
        self.assertEqual(bt.producer_type("A", ["Bakery", "On-Farm / Ranch Sales"]), "farm")

    def test_tables_have_one_valid_producer_type_and_no_categories_column(self):
        with open(os.path.join(ROOT, "data", "colorado", "producers.csv"), encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertNotIn("categories", rows[0])
        self.assertIn("source_categories", rows[0])
        known = set(bt.PRODUCER_TYPES)
        bad = {r["name"]: r["producer_type"] for r in rows if r["producer_type"] not in known}
        self.assertEqual(bad, {}, "producer types outside the defined list")


if __name__ == "__main__":
    unittest.main()
