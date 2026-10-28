"""Only emails the business lists on its own website may be committed."""
import os
import subprocess

from scrape import contact_policy as cp
from scrape.schema import Market

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def test_finds_plain_mailto_and_obfuscated_addresses():
    page = ('<a href="mailto:Hello@Farm.com">mail</a> and bob [at] farm [dot] org '
            'and <span>sam&#64;ranch.net</span>')
    got = cp.emails_in(page)
    assert {"hello@farm.com", "bob@farm.org", "sam@ranch.net"} <= got


def test_decodes_cloudflare_protected_addresses():
    key = 0x2A
    enc = "%02x" % key + "".join("%02x" % (ord(c) ^ key) for c in "info@farm.com")
    assert "info@farm.com" in cp.emails_in(f'<a data-cfemail="{enc}">[email&#160;protected]</a>')


def test_an_address_not_on_the_site_is_blanked_and_a_verified_one_kept(tmp_path):
    t = cp.Table(str(tmp_path / "v.csv"))
    t.put("a@gmail.com", "https://farm.com", cp.VERIFIED, "https://farm.com/contact")
    t.put("b@gmail.com", "https://farm.com", "not_found")
    keep = Market(business_name="A", email="a@gmail.com", website="https://farm.com")
    drop = Market(business_name="B", email="b@gmail.com", website="https://farm.com")
    none = Market(business_name="C", email="c@gmail.com", website="")
    assert cp.apply([keep, drop, none], t, verify=False) == 2
    assert (keep.email, drop.email, none.email) == ("a@gmail.com", "", "")


def test_unverified_addresses_are_stored_only_as_hashes(tmp_path):
    t = cp.Table(str(tmp_path / "v.csv"))
    t.put("private@gmail.com", "https://farm.com", "not_found")
    t.save()
    assert "private@gmail.com" not in open(tmp_path / "v.csv", encoding="utf-8").read()


def test_no_committed_file_holds_an_unverified_email():
    """Run `python scripts/verify_emails.py --from-build` then `--scrub` if this fails."""
    ok = cp.Table().verified_emails()
    files = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout.split("\n")
    bad = []
    for f in files:
        if not f.endswith((".csv", ".json", ".md", ".py", ".yml", ".gs")) or f == "inputs/email_verification.csv":
            continue
        if f.endswith(".py") and ("tests/" in f):
            continue          # test code uses obvious placeholders such as x@y.org
        path = os.path.join(REPO, f)
        if not os.path.exists(path):
            continue
        for e in cp.EMAIL_RE.findall(open(path, encoding="utf-8", errors="replace").read()):
            e = e.lower().rstrip(".")
            if e not in ok and not cp.ALWAYS_OK.search(e):
                bad.append((f, e))
    assert not bad, bad[:5]


def test_a_cell_with_several_addresses_is_judged_per_address(tmp_path):
    t = cp.Table(str(tmp_path / "v.csv"))
    t.put("a@farm.com", "https://farm.com", cp.VERIFIED, "https://farm.com/contact")
    t.put("b@farm.com", "https://farm.com", "not_found")
    m = Market(business_name="X", email="a@farm.com*b@farm.com", website="https://farm.com")
    assert cp.apply([m], t, verify=False) == 1
    assert m.email == "a@farm.com"
    assert cp.split_emails("x@y.org; z@y.org/ x@y.org") == ["x@y.org", "z@y.org"]


def test_an_address_on_the_businesses_own_instagram_or_facebook_page_counts(tmp_path):
    import pytest
    t = cp.Table(str(tmp_path / "v.csv"))
    # a business with no website: the address is listed on its own Instagram page, seen by a person
    assert t.confirm_on_page("Ranch@Example.com", "", "https://www.instagram.com/someranch/") == "verified_instagram"
    assert cp.publishable("ranch@example.com", "", t)
    assert t.confirm_on_page("a@farm.org", "", "https://www.facebook.com/somefarm") == "verified_facebook"
    # anything else is refused: a directory, the bare site root, or no path at all
    for bad in ("https://directory.example.com/farm", "https://www.instagram.com/", "https://twitter.com/farm"):
        with pytest.raises(ValueError):
            t.confirm_on_page("b@farm.org", "", bad)
    assert not cp.publishable("b@farm.org", "", t)
    t.save()
    assert cp.Table(str(tmp_path / "v.csv")).is_verified("ranch@example.com", "")
