"""Edges become outlet_suppliers rows only when both names match exactly one record."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "supply_network"))
import build_outlet_suppliers as b  # noqa: E402

PRODUCERS = [{"producer_id": "p1", "name": "Ela Family Farms"}, {"producer_id": "p2", "name": "Twin Farm"},
             {"producer_id": "p3", "name": "Twin Farm"}]
OUTLETS = [{"outlet_id": "o1", "name": "The Regional", "location_id": "l1"}]
LOCS = [{"location_id": "l1", "city": "Denver"}, {"location_id": "l2", "city": "Salida"},
        {"location_id": "l3", "city": "Aspen"}]
PLOC = [{"producer_id": "p2", "location_id": "l2"}, {"producer_id": "p3", "location_id": "l3"},
        {"producer_id": "p1", "location_id": "l2"}]
NODES = [{"name": "Twin Farm", "city": "Salida"}]


def edge(s, buyer="Regional", status="", conf="medium", date="2024"):
    return {"supplier": s, "buyer": buyer, "date": date, "confidence": conf, "source": "https://x.test/a",
            "note": "", "status": status}


class T(unittest.TestCase):
    def run_b(self, edges):
        return b.build(edges, NODES, PRODUCERS, OUTLETS, LOCS, PLOC)

    def test_match_and_fields(self):
        kept, review = self.run_b([edge("Ela Family Farms", "The Regional", status="unconfirmed")])
        self.assertEqual(review, [])
        self.assertEqual(kept[0]["outlet_id"], "o1")
        self.assertEqual(kept[0]["status"], "unverified")
        self.assertEqual(kept[0]["observed_on"], "2026-10-03")
        self.assertEqual(kept[0]["basis"], "third_party")

    def test_unknown_names_go_to_review(self):
        kept, review = self.run_b([edge("Nobody Farm", "The Regional"), edge("Ela Family Farms", "Nowhere Cafe")])
        self.assertEqual(kept, [])
        self.assertEqual({(r["side"], r["reason"]) for r in review}, {("supplier", "no match"), ("buyer", "no match")})

    def test_city_breaks_tie_never_guesses(self):
        kept, _ = self.run_b([edge("Twin Farm", "The Regional")])
        self.assertEqual(kept[0]["producer_id"], "p2")
        kept, review = b.build([edge("Twin Farm", "The Regional")], [], PRODUCERS, OUTLETS, LOCS, PLOC)
        self.assertEqual(kept, [])
        self.assertEqual(review[0]["reason"], "ambiguous")

    def test_undated_and_dedup(self):
        kept, _ = self.run_b([edge("Ela Family Farms", "The Regional", date="unknown"),
                              edge("Ela Family Farms", "The Regional")])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["source_dated"], "")


if __name__ == "__main__":
    unittest.main()
