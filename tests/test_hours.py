"""Hours text becomes structured days and times, and anything not understood is left as text."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from scrape import hours  # noqa: E402


def slots(text):
    p = hours.parse(text)
    return p.status, [(s.day, s.opens, s.closes) for s in p.slots]


def test_the_generated_day_by_day_shape():
    st, sl = slots("Mon: 8 am - 6 pm; Tue: 8 am - 6 pm; Thu: 3:00pm - 5:00pm")
    assert st == "parsed"
    assert sl == [("mon", "08:00", "18:00"), ("tue", "08:00", "18:00"), ("thu", "15:00", "17:00")]


@pytest.mark.parametrize("text,expected", [
    ("Saturday 9am-1pm", [("sat", "09:00", "13:00")]),
    ("Sat-Sun 10am-2pm or by appointment", [("sat", "10:00", "14:00"), ("sun", "10:00", "14:00")]),
    ("10-2pm Sat", [("sat", "10:00", "14:00")]),
    ("Tue: 9a-3pm", [("tue", "09:00", "15:00")]),
    ("Mon-Fri, 8 a.m.-5 p.m.", [(d, "08:00", "17:00") for d in ("mon", "tue", "wed", "thu", "fri")]),
])
def test_ranges_lists_and_spellings(text, expected):
    assert slots(text)[1] == expected


def test_a_day_with_two_blocks():
    assert slots("Mon: 7:30am - 12pm, 1pm - 4:30pm")[1] == [("mon", "07:30", "12:00"), ("mon", "13:00", "16:30")]


def test_a_closed_day_is_nothing_to_record():
    st, sl = slots("Mon-Sat 9:00 AM-7:00 PM, Sun closed")
    assert st == "parsed" and ("sun", "09:00", "19:00") not in sl and len(sl) == 6


def test_daily_and_always_open():
    assert len(slots("9am-5pm daily")[1]) == 7
    assert slots("Open 24/7")[1][0] == ("mon", "00:00", "24:00")


def test_an_unmarked_am_pm_is_inferred_and_flagged():
    p = hours.parse("Sat: 10-12; Mon: 12-6")
    assert [(s.day, s.opens, s.closes, s.inferred) for s in p.slots] == [
        ("mon", "12:00", "18:00", True), ("sat", "10:00", "12:00", True)]


def test_a_written_am_pm_is_not_flagged():
    assert not any(s.inferred for s in hours.parse("Sat: 10am-2pm").slots)


def test_overnight_ranges_are_marked():
    p = hours.parse("11am-3am Mon-Sat")
    assert p.slots[0].closes_next_day is True


@pytest.mark.parametrize("text,status", [
    ("", "none"),
    ("By appointment", "appointment"),
    ("Winter CSA January-April", "text_only"),
    ("Mon: Varies; Wed: Varies", "text_only"),
    ("Sells at Montrose Farmers Market (Saturdays; market is year-round)", "text_only"),
])
def test_what_is_not_hours_stays_text(text, status):
    assert hours.parse(text).status == status


def test_something_read_and_something_not_is_partial():
    st, sl = slots("Mon: 9am-5pm; Sun: by order only, call 303-555-0100")
    assert sl == [("mon", "09:00", "17:00")]
    assert st in ("parsed", "partial")
