"""Derived producer fields: farmers_market channel from live vendor lists, last_verified from own-page/partner rows,
and the product-group mapper's extra keywords."""
import os
import sys
import unittest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_tables as bt  # noqa: E402
import products  # noqa: E402


def out(channels="", markets=None, vendors=None, sources=None):
    return {
        "producers": [{"producer_id": "co-p-1", "sales_channels": channels, "last_verified": ""},
                      {"producer_id": "co-p-2", "sales_channels": "", "last_verified": ""}],
        "markets": markets if markets is not None else [{"market_id": "co-m-1", "status": "unverified"}],
        "market_vendors": vendors if vendors is not None else [
            {"market_id": "co-m-1", "producer_id": "co-p-1", "status": "listed", "list_source": "vendor list: X",
             "source_url": "https://x.example/vendors"}],
        "field_sources": sources or [],
    }


class DerivedChannel(unittest.TestCase):
    def test_adds_channel_and_source(self):
        o = out()
        bt.derive_channels(o)
        self.assertEqual(o["producers"][0]["sales_channels"], "farmers_market")
        self.assertEqual(o["producers"][1]["sales_channels"], "")          # not on a list: stays unknown
        fs = o["field_sources"]
        self.assertEqual((fs[0]["record_id"], fs[0]["field"], fs[0]["source"], fs[0]["verified_on"]),
                         ("co-p-1", "sales_channels", "vendor list: X", ""))

    def test_never_removes_or_duplicates(self):
        o = out(channels="csa;farm_stand")
        bt.derive_channels(o)
        self.assertEqual(o["producers"][0]["sales_channels"], "csa;farm_stand;farmers_market")
        o = out(channels="farmers_market")
        bt.derive_channels(o)
        self.assertEqual(o["field_sources"], [])

    def test_closed_market_does_not_count(self):
        o = out(markets=[{"market_id": "co-m-1", "status": "closed"}])
        bt.derive_channels(o)
        self.assertEqual(o["producers"][0]["sales_channels"], "")


class DerivedLastVerified(unittest.TestCase):
    def fs(self, pid, source, by, on):
        return {"record_type": "producer", "record_id": pid, "field": "phone", "source": source,
                "source_url": "", "verified_by": by, "verified_on": on}

    def test_own_page_and_partner_only_latest_dated(self):
        o = out(sources=[self.fs("co-p-1", "producer_site", "source", "2026-10-01"),
                         self.fs("co-p-1", "guidestone", "partner", "2026-10-13"),
                         self.fs("co-p-2", "colorado_proud", "source", ""),
                         self.fs("co-p-2", "producer_site", "source", "")])
        bt.derive_last_verified(o)
        self.assertEqual(o["producers"][0]["last_verified"], "2026-10-13")
        self.assertEqual(o["producers"][1]["last_verified"], "")           # no date, no invented date


class ProductMapper(unittest.TestCase):
    def test_new_keywords(self):
        self.assertEqual(products.from_text("Ice Cream"), ["dairy"])
        self.assertEqual(products.from_text("Quail"), ["poultry-eggs"])
        self.assertIn("drinks", products.from_text("Tea"))
        self.assertEqual(products.from_text("Steak"), [])                  # "tea" must not match inside a word


if __name__ == "__main__":
    unittest.main()
