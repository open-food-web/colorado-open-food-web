"""Product groups: the short list of things people look for (honey, beef, eggs...).

A producer's `products` field keeps the source's own words. `product_groups` is the controlled
list used to search and filter. Groups come from two places, unioned: what the business chose for
itself (Chaffee Provides asked providers to tick their product offerings), and keywords found in
its products text, categories and name. Nothing is guessed beyond these keywords.
"""
from __future__ import annotations

import re

PRODUCT_GROUPS = [
    ("veggies", "Veggies", r"veggie|vegetable|\bproduce\b|greens|lettuce|tomato|squash|potato|beet|carrot|\bpeppers?\b|kale|"
                           r"broccoli|asparagus|chile|onion|pumpkin|cucumber|spinach|microgreen|sprouts"),
    ("fruit", "Fruit", r"fruit|apple|apricot|peach|cherr|berr|melon|plum|\bpears?\b|grape"),
    ("beef-meat", "Beef & meat", r"beef|meat|pork|lamb|bison|sausage|jerky|goat meat|hides?"),
    ("poultry-eggs", "Poultry & eggs", r"poultry|\beggs?\b|chicken|turkey|duck"),
    ("dairy", "Dairy", r"dairy|milk|cheese|yogurt|(?<!peach )(?<!apple )(?<!nut )(?<!almond )(?<!cocoa )butter|kefir|chevre"),
    ("honey", "Honey", r"honey|\bbees?\b|apiary|beeswax"),
    ("flowers", "Flowers", r"(?<!wild)flower|lavender|bouquet|zinnia"),
    ("garlic-herbs", "Garlic & herbs", r"spice|garlic|herb"),
    ("mushrooms", "Mushrooms", r"mushroom"),
    ("baked-goods", "Baked goods", r"bread|baked|bakery|pastr|sourdough|cookie|pie\b"),
    ("seeds-plants", "Seeds & plants", r"\bseeds?\b|seedling|plant starts?|\bstarts\b|nursery|houseplant"),
    ("drinks", "Wine & drinks", r"wine|cider|brew|kombucha|juice|coffee"),
]
LABELS = {k: label for k, label, _ in PRODUCT_GROUPS}
# Chaffee Provides' own offering names -> our groups
CHAFFEE_OFFERINGS = {"veggies": "veggies", "beef/meat": "beef-meat", "dairy": "dairy", "flowers": "flowers",
                     "poultry/eggs": "poultry-eggs", "spices/garlic": "garlic-herbs", "fruit": "fruit", "honey": "honey"}


def from_text(*texts: str) -> list:
    text = " ".join(t or "" for t in texts).lower()
    found = [k for k, _, rx in PRODUCT_GROUPS if re.search(rx, text)]
    # "about 250 tomato varieties" on a seed seller's list is seeds, not vegetables for sale
    if "seeds-plants" in found and not re.search(r"vegetable|produce|veggie|fruit", text.replace("tomato", "")):
        found = [k for k in found if k not in ("veggies", "fruit")]
    return found


def union(*lists) -> list:
    seen = set(x for l in lists for x in l)
    return [k for k, _, _ in PRODUCT_GROUPS if k in seen]
