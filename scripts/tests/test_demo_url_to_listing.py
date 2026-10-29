from scripts.demo import url_to_listing as u

PAGE = ('<html><title>Test Farm | Salida</title><body><p>1 Main St, Salida, CO 81201. (719) 555-0100. '
        'Hours: Sat 9am-1pm. Join our CSA.</p></body></html>')


def test_derives_facts_offline():
    L = u.derive_listing("https://testfarm.example/", PAGE, offline=True)
    assert L["name"] == "Test Farm"
    assert L["phone"] == "(719) 555-0100"
    assert L["address"].endswith("CO 81201")
    assert [h["day"] for h in L["hours"]] == ["sat"]
    assert "csa" in L["sales_channels"]


def test_diff_reports_new_changed_and_gone():
    old = {"phone": "", "hours_text": "Sat 9am-1pm", "email": "a@b.co", "sales_channels": ["csa"]}
    new = {"phone": "(719) 555-0100", "hours_text": "Sat 8am-2pm", "email": "", "sales_channels": ["csa", "online"]}
    kinds = {c["field"]: c["kind"] for c in u.diff(old, new)}
    assert kinds == {"phone": "new", "hours_text": "changed", "email": "gone (review)", "sales_channels": "changed"}
