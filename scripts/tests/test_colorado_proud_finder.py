"""Offline tests for the Colorado Proud member-directory source (Phase 2)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


from scrape.sources import colorado_proud_finder as cpf  # noqa: E402

CARD = """
<a href="/business/?bid=business_profile_828" class="featuredBusiness FarmRanch  Flowers   Cash  "
 data-filter="FarmRanch  Flowers   "  data-lat="40.1670336" data-lng="-105.119934">
  <div class="featuredBusinessDetails">
    <div class="businessTitle"><h2 class="bnameacc">100x Farm</h2></div>
    <div class="businessAddress">
      1618 3rd Avenue<br />Longmont, Colorado 80501 <br />
      (303) 746-5675 </div>
  </div>
</a>"""

PROFILE = """<main>
<div class="businessFullAddress"><div>1618 3rd Avenue<br />Longmont, Colorado  80501</div>
<i class="fas fa-globe-americas"></i> <a href="https://www.modernfarmsteads.com/" target="_blank">Visit Website</a><br />
</div>
<div class="businessSocial"><ul>
<li><a href="https://www.facebook.com/mfarmsteads" rel="noopener" target="_blank" title="Facebook"></a></li>
</ul></div>
<div class="businessAff"><div class="headlineSmall">Payment Methods</div>
<div class="prettyArray">Cash</div><div class="prettyArray">EBT / SNAP</div></div>
<h1 class="entry-title">100x Farm</h1>
<label for="tabone"><div class="headlineSmall">Business Type</div></label>
<div class="tab"><div class="prettyArray">Food Truck</div><div class="prettyArray">Farm / Ranch</div></div>
<label for="tabtwo"><div class="headlineSmall">Products</div></label>
<div class="tab"><div class="prettyArray">Flowers</div><div class="prettyArray">Vegetables</div></div>
<div class="entry-content"><div style="white-space: pre-wrap;">A diversified flower farm.</div></div>
</main>"""


def test_parse_listing_card():
    [c] = cpf.parse_listing(CARD)
    assert c["bid"] == "business_profile_828"
    assert (c["name"], c["street"], c["city"], c["zip"]) == (
        "100x Farm", "1618 3rd Avenue", "Longmont", "80501")
    assert c["phone"] == "(303) 746-5675"


def test_parse_profile_keeps_every_item_in_each_group():
    p = cpf.parse_profile(PROFILE)
    assert p["business_types"] == ["Food Truck", "Farm / Ranch"]
    assert p["products"] == ["Flowers", "Vegetables"]
    assert p["payment_methods"] == ["Cash", "EBT / SNAP"]
    assert p["social"]["facebook"] == "https://www.facebook.com/mfarmsteads"


def test_to_market_scope_and_fields():
    card = cpf.parse_listing(CARD)[0]
    m = cpf.to_market(card, cpf.parse_profile(PROFILE))
    assert m.category == "On-Farm / Ranch Sales"  # Food Truck is out of scope, dropped
    assert m.snap == "Yes" and m.products == "Flowers, Vegetables"
    assert m.latitude == 40.1670336
    # Out-of-scope only -> not a member of the trail list
    assert cpf.to_market(card, {"business_types": ["Wholesaler"]}) is None


def test_placeholder_address_is_dropped():
    card = dict(cpf.parse_listing(CARD)[0], street="12345 Test St.", city="Arvada", zip="80222")
    m = cpf.to_market(card, {"business_types": ["Bakery"]})
    assert (m.address, m.city, m.zip, m.latitude) == ("", "", "", None)
    assert m.category == "Bakery"


def test_farmers_market_type_only_for_markets():
    # Members tick "Farmers Market" when they sell at one; only actual markets keep it.
    fm = ["Farmers Market"]
    assert cpf.categories_for(fm, "Durango Farmers Market") == ["Farmers' Market"]
    assert cpf.categories_for(fm, "Rebel Marketplace") == ["Farmers' Market"]
    assert cpf.categories_for(fm, "Mercado Del Norte") == ["Farmers' Market"]
    assert cpf.categories_for(fm, "Rocky Mountain Events, LLC.") == ["Farmers' Market"]  # organizer
    assert cpf.categories_for(fm + ["Farm / Ranch"], "Koha Farm") == ["On-Farm / Ranch Sales"]
    assert cpf.categories_for(fm + ["Cottage Food"], "Latina Salsas") == ["Food Maker"]
    assert cpf.categories_for(fm, "Tongue Burners") == []          # market-only vendor: off the map
    assert cpf.categories_for(fm + ["Retailer"], "Young's Market & Garden Center") == [
        "Garden Center / Greenhouse"]                                  # "Market" in name, not a market


def test_market_only_vendor_is_out_of_scope():
    card = dict(cpf.parse_listing(CARD)[0], name="Moon Peppers Co. LLC")
    assert cpf.to_market(card, {"business_types": ["Farmers Market", "Food Manufacturer"]}) is None
