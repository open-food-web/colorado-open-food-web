"""Matching vendor-list names to producer records is made only when it is unambiguous."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from scrape import vendors as v  # noqa: E402

LOCS = {"l1": {"city": "Salida", "county_fips": "08015"}, "l2": {"city": "Buena Vista", "county_fips": "08015"},
        "l3": {"city": "Aspen", "county_fips": "08097"}}
MARKETS = [{"market_id": "m1", "name": "Salida Farmers Market", "location_id": "l1"}]


def linker(names):
    prods = [{"producer_id": "p%d" % i, "name": n} for i, n in enumerate(names)]
    lk = v.Linker(MARKETS, prods, LOCS)
    lk.attach_locations([{"producer_id": "p%d" % i, "location_id": "l2"} for i in range(len(names))])
    return lk


class Linking(unittest.TestCase):
    def test_exact_and_punctuation_variants_match(self):
        lk = linker(["Banyan Breads", "Bob's Farm & Ranch"])
        m = lk.market_for("Salida Farmers Market", "Salida")
        self.assertEqual(lk.producer_for("Banyan Breads", m)[1], "exact_name")
        self.assertEqual(lk.producer_for("Bob's Farm and Ranch", m)[0]["producer_id"], "p1")

    def test_two_records_with_the_same_name_are_not_guessed(self):
        lk = linker(["Sunny Acres", "Sunny Acres"])
        m = lk.market_for("Salida Farmers Market", "Salida")
        self.assertIsNone(lk.producer_for("Sunny Acres", m)[0])

    def test_one_word_loose_match_needs_the_same_county(self):
        lk = linker(["Sunny Farm"])
        m = lk.market_for("Salida Farmers Market", "Salida")
        self.assertEqual(lk.producer_for("Sunny Ranch", m)[1], "normalized_name")
        lk.prod_loc["p0"] = LOCS["l3"]
        self.assertIsNone(lk.producer_for("Sunny Ranch", m)[0])

    def test_list_rows_keep_ids_and_year_not_descriptions(self):
        lk = linker(["Banyan Breads"])
        rows, un = lk.from_lists([{"market": "Salida Farmers Market", "market_city": "Salida", "vendor": "Banyan Breads",
                                   "list_year": "2025-26 winter", "list_url": "https://example.org"},
                                  {"market": "Nowhere Market", "market_city": "X", "vendor": "Banyan Breads",
                                   "list_year": "2026", "list_url": ""}])
        self.assertEqual((rows[0]["year"], rows[0]["season_label"]), ("2025", "2025-26 winter"))
        self.assertEqual(un, {"market:Nowhere Market": 1})

    def test_stated_text_names_a_market(self):
        lk = linker(["Banyan Breads"])
        out = lk.from_text({"p0": "Sells at the Salida Farmers Market on Saturdays"}, set())
        self.assertEqual([(r["market_id"], r["match_basis"]) for r in out], [("m1", "stated_text")])


if __name__ == "__main__":
    unittest.main()
