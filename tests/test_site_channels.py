from scripts.scrape import site_channels as sc

HOME = """<html><body><script>var farm_stand=1</script>
<a href="/shop">Shop</a><a href="https://other.com/csa">x</a><a href="/about">About</a>
<p>Visit our farm stand on Saturdays. Join our CSA today! We offer U-pick strawberries.</p>
<p>We do not offer home delivery.</p></body></html>"""
SHOP = ("<p>Order online for pickup location at the barn. Wholesale accounts welcome. "
        "Find us at the Boulder County Farmers Market.</p>")


def test_evidence_and_negation():
    ev = sc.find_evidence(sc.to_text(HOME))
    assert {"farm_stand", "csa", "u_pick"} <= set(ev)
    assert "delivery" not in ev          # a negated mention is not evidence
    assert all(len(p.split()) < 15 for _, p in ev.values())


def test_script_content_ignored():
    assert sc.find_evidence(sc.to_text("<script>farm stand csa</script><p>Hello</p>")) == {}


def test_classify_site_follows_same_site_links_only():
    pages = {"http://f.com": HOME, "http://f.com/shop": SHOP}
    fetched = []

    def fetch(u):
        fetched.append(u)
        return pages.get(u)

    status, n, found = sc.classify_site("f.com", fetch=fetch, allowed=lambda u: True, sleep=lambda s: None)
    assert status == "ok"
    assert not any("other.com" in u for u in fetched)
    assert found["wholesale"][1] == "http://f.com/shop"
    assert {"online", "pickup", "farmers_market", "farm_stand"} <= set(found)


def test_robots_and_unreachable():
    assert sc.classify_site("f.com", allowed=lambda u: False)[0] == "robots_blocked"
    assert sc.classify_site("f.com", fetch=lambda u: None, allowed=lambda u: True,
                            sleep=lambda s: None)[0] == "unreachable"


def test_retailer_list_pages_are_not_evidence():
    pages = {"http://f.com": '<a href="/pages/retailers">Retailers</a><p>Hello</p>',
             "http://f.com/pages/retailers": "<p>Aspen Market on Farm Stand (seasonal). Order online at the BCFM store.</p>"}
    _, _, found = sc.classify_site("f.com", fetch=pages.get, allowed=lambda u: True, sleep=lambda s: None)
    assert found == {}
