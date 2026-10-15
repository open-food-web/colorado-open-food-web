"""Entity registry: matching, enforcement, seeding."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrape import registry
from scrape.registry import Registry
from scrape.schema import Market


def row(name, city="", decision="not_listed", **kw):
    r = {"name": name, "city": city, "decision": decision, "reason_code": kw.pop("reason_code", "did_not_qualify")}
    r.update(kw)
    return r


def test_find_matches_name_and_town_but_not_a_different_town():
    reg = Registry([row("Hugs Farm", "Walsenburg")])
    assert reg.find("Hugs Farm", "Walsenburg")
    assert reg.find("HUGS FARM LLC", "walsenburg")
    assert not reg.find("Hugs Farm", "Boulder")


def test_find_matches_by_domain_or_phone_across_a_rename():
    reg = Registry([row("Old Name Ranch", "Salida", website="https://www.oldranch.com/", phone="(719) 555-0101")])
    assert reg.find("New Name Ranch", "Salida", website="oldranch.com")
    assert reg.find("Totally Different", "Elsewhere", phone="719-555-0101")
    # an aggregator or social page is never evidence of identity
    reg2 = Registry([row("Some Farm", "Delta", website="https://www.facebook.com/somefarm")])
    assert not reg2.find("Other Farm", "Delta", website="https://www.facebook.com/otherfarm")


def test_aliases_match_and_latest_decision_wins():
    reg = Registry([row("Jumpin Good Goat Dairy", "Buena Vista", aliases="Jumping Good Goats"),
                    row("Jumpin Good Goat Dairy", "Buena Vista", decision="closed")])
    assert reg.find("Jumping Good Goats", "Buena Vista")[0]["decision"] == "closed"


def test_strict_needs_town_domain_or_phone():
    reg = Registry([row("Mystery Farm", "")])
    assert reg.find("Mystery Farm", "Salida")            # a lookup hint
    assert not reg.find("Mystery Farm", "Salida", strict=True)


def test_recheck_after_stops_blocking():
    r = row("Old Farm", "X", recheck_after="2020-01-01")
    assert not Registry.is_blocking(r, today="2026-10-15")
    assert Registry.is_blocking(row("Old Farm", "X"), today="2026-10-15")
    assert not Registry.is_blocking(row("Old Farm", "X", decision="unresolved"))


def test_guard_drops_resurfaced_not_listed_marks_closed_and_spares_curated_and_survivors():
    reg = Registry([
        row("Declined Farm", "Delta"),
        row("Closed Farm", "Delta", decision="closed", reason_code="closed_permanently"),
        row("Curated Again", "Delta"),
        row("Old Market", "Aspen", decision="merged", reason_code="merged_into", successor_name="New Market", successor_city="Aspen"),
        row("New Market", "Aspen", decision="merged", reason_code="merged_into", successor_name="New Market", successor_city="Aspen"),
    ])
    ms = [Market(business_name="Declined Farm", city="Delta", source="usda"),
          Market(business_name="Closed Farm", city="Delta", source="usda"),
          Market(business_name="Curated Again", city="Delta", source="curated"),
          Market(business_name="Old Market", city="Aspen", source="usda"),
          Market(business_name="New Market", city="Aspen", source="usda"),
          Market(business_name="Fine Farm", city="Delta", source="usda")]
    kept = {m.business_name: m for m in registry.guard(ms, reg, quiet=True)}
    assert "Declined Farm" not in kept and "Old Market" not in kept
    assert kept["Closed Farm"].status == "Closed"
    assert "Curated Again" in kept and "New Market" in kept and "Fine Farm" in kept


def test_sync_is_idempotent_and_append_only():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "registry", "decisions.csv")
        seed = [row("A Farm", "Town"), row("B Farm", "Town", decision="closed", reason_code="closed_permanently")]
        assert registry.sync(path, seed) == 2
        assert registry.sync(path, seed) == 0
        registry.add_decision("C Farm", "Town", "not_listed", "not_food_system", "landscaper", path=path)
        reg = registry.load(path)
        assert len(reg.rows) == 3
        assert reg.find("C Farm", "Town")[0]["reason_code"] == "not_food_system"


def test_sync_records_a_reversal_when_curated_adds_a_declined_entity():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "r", "decisions.csv")
        registry.sync(path, [row("Hugs Farm", "Walsenburg")], adds=[])
        n = registry.sync(path, [row("Hugs Farm", "Walsenburg")], adds=[{"Business Name": "Hugs Farm", "City": "Walsenburg", "Researched": "2026-11-01"}])
        assert n == 1
        reg = registry.load(path)
        assert reg.find("Hugs Farm", "Walsenburg")[0]["decision"] == "listed"
        assert not Registry.is_blocking(reg.find("Hugs Farm", "Walsenburg")[0])
        # idempotent: the entity is no longer blocked, so nothing more is added
        assert registry.sync(path, [row("Hugs Farm", "Walsenburg")], adds=[{"Business Name": "Hugs Farm", "City": "Walsenburg"}]) == 0


def test_spelling_variant_merges_are_not_seeded_and_do_not_trigger_reversals():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "r", "decisions.csv")
        # a merged row whose name and successor differ only in spelling is the same business
        reg_row = row("Buck & Bloom Cheese Co", "Buena Vista", decision="merged", reason_code="merged_into",
                      successor_name="Buck and Bloom Cheese Co", successor_city="Buena Vista")
        assert registry.sync(path, [reg_row], adds=[{"Business Name": "Buck and Bloom Cheese Co", "City": "Buena Vista"}]) == 1
        assert registry.load(path).find("Buck and Bloom Cheese Co", "Buena Vista")[0]["decision"] == "merged"   # no reversal row


def test_overrides_status_closed_is_seeded_as_closed(monkeypatch=None):
    # seed_rows reads the repo files; check the shape on the real data
    rows = registry.seed_rows()
    assert any(r["decision"] == "closed" and r["origin"].startswith("overrides.csv (Status") for r in rows)
