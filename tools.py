"""
The three FitFindr tools.

Each one is a standalone function you can call and test on its own, before any
of them are wired into the loop. Build and test them one at a time — three
untested tools joined by a loop is one problem that looks like six, because you
can't tell which layer is lying to you.

    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str

All three are stubs right now. They run and they do nothing — that's the
starting position and it's deliberate.

⚠️ Before you write any of them, fill in the **Tool Inventory** section of your
README (Milestone 2). Four lines per tool: what it does, each input with its
type, exactly what it returns, and what it returns when it has nothing to give.
That last line is what your loop branches on. "Returns a list" earns nothing —
the description has to say what is *in* the list.
"""

import re

import config
from generate import generate
from utils.data_loader import load_listings


# ── search helpers ────────────────────────────────────────────────────────────

# Words that say nothing about the item. Leaving them in would let "looking for
# a ..." match every description that happens to contain "for" or "a".
_STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "with", "in", "of", "to", "on", "my",
    "me", "i", "im", "looking", "want", "need", "find", "some", "something",
    "any", "that", "is", "it", "size", "under", "below", "max", "less", "than",
    "around", "about", "cheap", "please", "dollars", "dollar", "usd",
}

# A few spellings the data doesn't use, folded into the ones it does.
_SYNONYMS = {
    "tshirt": "tee", "t-shirt": "tee", "shirt": "shirt", "tees": "tee",
    "jeans": "jeans", "sneaker": "sneakers", "boot": "boots", "jacket": "jacket",
    "pant": "pants", "trouser": "trousers", "short": "shorts", "hoody": "hoodie",
}

_LETTER_SIZES = {"XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"}


def _words(text: str) -> list[str]:
    """Lowercase whole words. 'dressed' is one word, so it never matches 'dress'."""
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", (text or "").lower())


def _keywords(description: str) -> list[str]:
    out = []
    for w in _words(description):
        w = _SYNONYMS.get(w, w)
        if w not in _STOPWORDS and not w.isdigit() and w not in out:
            out.append(w)
    return out


def _score(listing: dict, keywords: list[str]) -> int:
    """Title hits count most, then style tags, then everything else."""
    title = set(_words(listing["title"]))
    tags = set(w for tag in listing["style_tags"] for w in _words(tag))
    other = set(
        _words(listing["description"])
        + _words(listing["category"])
        + [w for c in listing["colors"] for w in _words(c)]
        + _words(listing.get("brand") or "")
    )
    score = 0
    for kw in keywords:
        if kw in title:
            score += 3
        elif kw in tags:
            score += 2
        elif kw in other:
            score += 1
    return score


def _size_matches(wanted: str, listing_size: str) -> bool:
    """
    Whole-token size matching, so "S" never matches "XS" or "US 9" and "L"
    never matches "XL".

      letter size  →  matches a token of the listing size (M ↔ S/M, M/L),
                      or any "One Size" listing
      number       →  matches a shoe size (8 ↔ US 8, not US 8.5) or a
                      waist (30 ↔ W30, W30 L30)
    """
    wanted = wanted.strip().upper().replace("US", "").strip()
    listing = listing_size.upper()
    tokens = re.findall(r"[A-Z]+\d*(?:\.\d+)?|\d+(?:\.\d+)?", listing)

    if wanted in _LETTER_SIZES:
        return wanted in tokens or "ONE SIZE" in listing

    number = wanted.lstrip("W")
    if re.fullmatch(r"\d+(?:\.\d+)?", number):
        shoe = re.search(r"US\s*(\d+(?:\.\d+)?)", listing)
        waist = re.search(r"W(\d+)", listing)
        if shoe and float(shoe.group(1)) == float(number):
            return True
        if waist and float(waist.group(1)) == float(number):
            return True
        return False

    # Anything else ("one size", "oversized") — fall back to a token match.
    return wanted in tokens


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the listings data for items matching a description, and optionally a
    size and a price ceiling.

    This is the tool that doesn't call the model, which makes it the easiest one
    to test and the one to move onto MCP in unit 4.

    Args:
        description: keywords describing what the user wants
                     (e.g. "vintage graphic tee").
        size:        a size string to filter by, or None to skip size filtering.
                     Match case-insensitively — "M" should match "S/M".

                     ⚠️ Read the sizes in the data before you reach for a plain
                     substring test. `"s" in "us 9"` is True, and so is
                     `"l" in "xl"`. A filter that returns shoes when someone
                     asked for a small top reads like a broken search, and it
                     will quietly cost you in unit 4 when you test criterion 1.
                     What counts as a size match is part of your spec — decide
                     it and write it into your Tool Inventory.
        max_price:   maximum price, inclusive, or None to skip price filtering.

    Returns:
        A list of matching listing dicts, best match first.
        **Returns an empty list when nothing matches — an empty list, not None,
        and not an exception.** Your loop branches on this.

    Each listing dict has these fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand (str or None), platform

    Note that `brand` is None for most listings. That is deliberate and
    realistic — thrift listings often have no brand. If something you write
    assumes a brand is always there, you will find out in unit 4.

    TODO:
        1. Load every listing with load_listings().
        2. Filter by max_price and by size, when each is provided.
        3. Score what's left by keyword overlap with `description`.
        4. Drop anything scoring zero.
        5. Sort by score, highest first, and return the listing dicts —
           at most config.SEARCH_RESULT_LIMIT of them.

    Test it from a terminal before you move on:
        python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
    """
    keywords = _keywords(description)
    if not keywords:
        return []

    scored = []
    for listing in load_listings():
        if max_price is not None and listing["price"] > max_price:
            continue
        if size and not _size_matches(size, listing["size"]):
            continue
        score = _score(listing, keywords)
        if score > 0:
            scored.append((score, listing))

    # Highest score first; cheaper item wins a tie.
    scored.sort(key=lambda pair: (-pair[0], pair[1]["price"]))
    return [listing for _, listing in scored[: config.SEARCH_RESULT_LIMIT]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest one or two outfits.

    This one calls the model, through `generate()`. You don't need to think
    about rate limits — the adapter handles pacing for you.

    Args:
        new_item: a listing dict — the item the user is considering.
        wardrobe: a wardrobe dict with an 'items' key holding a list of items.
                  **It may be empty.** Handle that.

    Returns:
        A non-empty string with outfit suggestions.
        With an empty wardrobe, return general styling advice rather than
        raising or returning "". Unit 4 has you trigger the empty wardrobe on
        purpose, so decide now what it should do.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If it is, ask the model for general styling ideas for this item.
        3. If it isn't, format the wardrobe items into the prompt and ask for
           specific combinations naming pieces the user already owns.
        4. Return the model's response.

    Test it from a terminal before you move on:
        python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
    """
    if not new_item:
        return "No item to style — search_listings didn't hand one over."

    item_text = _describe_item(new_item)
    items = (wardrobe or {}).get("items") or []

    if not items:
        prompt = (
            f"Someone is thinking about buying this thrifted item:\n{item_text}\n\n"
            "They haven't told us what's in their closet. Give general styling "
            "advice: two short outfit ideas built around this item, naming the "
            "kinds of pieces that pair well with it (e.g. 'straight-leg dark "
            "jeans', 'chunky white sneakers'). Plain text, one line per outfit, "
            "under 90 words total."
        )
    else:
        closet = "\n".join(
            f"- {w['name']} ({w['category']}; colors: {', '.join(w.get('colors') or [])}; "
            f"style: {', '.join(w.get('style_tags') or [])})"
            + (f" — note: {w['notes']}" if w.get("notes") else "")
            for w in items
        )
        prompt = (
            f"Someone is thinking about buying this thrifted item:\n{item_text}\n\n"
            f"Here is what they already own:\n{closet}\n\n"
            "Suggest two outfits built around the new item. Each outfit must use "
            "pieces from their closet, named exactly as written above. Plain text, "
            "one line per outfit, like 'Outfit 1: ...'. Under 90 words total."
        )

    response = generate(
        prompt,
        system="You are a practical thrift stylist. Be specific and brief. No markdown.",
    )
    return response or f"Try the {new_item.get('title', 'item')} with simple basics in a neutral color."


def _describe_item(item: dict) -> str:
    """The listing in a few lines for a prompt. Brand is often None — skip it then."""
    lines = [
        f"Title: {item.get('title')}",
        f"Category: {item.get('category')}",
        f"Colors: {', '.join(item.get('colors') or [])}",
        f"Style: {', '.join(item.get('style_tags') or [])}",
        f"Size: {item.get('size')}  Condition: {item.get('condition')}",
        f"Price: ${item.get('price'):g} on {item.get('platform')}",
    ]
    if item.get("brand"):
        lines.insert(1, f"Brand: {item['brand']}")
    if item.get("description"):
        lines.append(f"Seller says: {item['description']}")
    return "\n".join(lines)


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a short caption someone would actually post about the find.

    This calls the model too.

    Args:
        outfit:   the outfit suggestion string from suggest_outfit().
        new_item: the listing dict for the item.

    Returns:
        A two-to-four sentence caption.
        If `outfit` is empty or whitespace, return a descriptive message rather
        than raising.

    The caption should read like a real post rather than a product description,
    mention the item and its price and platform once each, and be specific about
    the vibe.

    It should also come out **differently for different inputs**. If you run
    this three times on the same item and get three word-for-word identical
    strings, it's one of two things, and both are near the top of `config.py`:

        • CACHE_ENABLED — the adapter handed back an answer it already had
        • TEMPERATURE   — at 0.0 the model gives the same words every time

    TODO:
        1. Guard against an empty or whitespace-only `outfit`.
        2. Build a prompt with the item details and the outfit.
        3. Call generate() and return the response.

    Test it from a terminal before you move on:
        python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
    """
    if not outfit or not outfit.strip():
        return "Can't write a fit card: there's no outfit suggestion to build it from."

    price = f"${new_item.get('price'):g}"
    prompt = (
        f"Write a caption for a social post about this thrift find.\n\n"
        f"{_describe_item(new_item)}\n\n"
        f"How they plan to wear it:\n{outfit.strip()}\n\n"
        f"Rules: 2 to 4 sentences, under 350 characters. Mention the item, the "
        f"price written exactly as {price}, and the platform ({new_item.get('platform')}) "
        f"once each. Sound like a real person posting, not a product listing — be "
        f"specific about the vibe. At most two hashtags. No markdown, no quotes "
        f"around the caption."
    )
    return generate(
        prompt,
        system="You write short, natural captions for outfit posts.",
    )
