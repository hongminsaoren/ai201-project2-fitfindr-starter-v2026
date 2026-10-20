"""
The FitFindr planning loop.

This is the file that makes FitFindr an agent rather than a script. It decides
which tool to run next based on what the last one returned.

If your loop calls all three tools no matter what comes back, you have a list
of function calls. A loop looks at the last result before it picks the next
step. **That branch is the graded part of this unit.**

Build and test your three tools in `tools.py` first. Then come here.

    python agent.py          runs both example paths below
"""

import re

import config
import trace
from tools import search_listings, suggest_outfit, create_fit_card
from generate import ModelUnavailable


# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """
    A fresh session for one user interaction.

    The session is the single source of truth for a run. Every tool result goes
    in here, and the next tool reads it back out.

    You could pass values straight from one call to the next. It would work,
    and you would not be able to test it — you can't print a variable you have
    already overwritten. Going through the session is what makes the state
    visible, and unit 4 has you write a criterion about exactly that.

    Add fields if you need them.
    """
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price you pulled out of it
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one you chose — goes into suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "fit_card": None,            # what create_fit_card returned
        "error": None,               # set when the run ended early
        "tool_calls": [],            # one entry per tool call: name + the inputs it got
        "next_step": "parse",        # what the loop will do on its next pass
    }


# ── query parsing ─────────────────────────────────────────────────────────────
# Regex, not the model: it's free, it's deterministic, and criterion 5 checks it.

_PRICE = re.compile(
    r"(?:under|below|less than|max(?:imum)?|up to|<)\s*\$?\s*(\d+(?:\.\d+)?)"
    r"(?:\s*(?:dollars|bucks|usd))?"
    r"|\$\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_SIZE = re.compile(
    r"(?:\bin\s+)?\bsize\s+(xxs|xs|s|m|l|xl|xxl|xxxl|w?\d+(?:\.\d+)?|us\s*\d+(?:\.\d+)?)\b"
    r"|\bin\s+(?:a\s+)?(xxs|xs|s|m|l|xl|xxl|xxxl)\b",
    re.IGNORECASE,
)


def parse_query(query: str) -> dict:
    """
    Pull a description, a size and a max_price out of plain language.

        "band tee, size L, max $20"  →  {"description": "band tee",
                                          "size": "L", "max_price": 20.0}
    """
    text = query
    max_price = None
    m = _PRICE.search(text)
    if m:
        max_price = float(m.group(1) or m.group(2))
        text = text[: m.start()] + " " + text[m.end():]

    size = None
    m = _SIZE.search(text)
    if m:
        size = (m.group(1) or m.group(2)).upper().replace("US", "").strip()
        text = text[: m.start()] + " " + text[m.end():]

    description = re.sub(r"[,;]+", " ", text)
    description = re.sub(r"\s+", " ", description).strip()
    return {"description": description, "size": size, "max_price": max_price}


def _no_results_message(parsed: dict) -> str:
    """Say what was searched and what to loosen — "No results" alone isn't useful."""
    applied = [f'"{parsed["description"]}"']
    tips = []
    if parsed["max_price"] is not None:
        applied.append(f"under ${parsed['max_price']:g}")
        tips.append(f"raise the price above ${parsed['max_price']:g} (most listings are $15–$50)")
    if parsed["size"]:
        applied.append(f"size {parsed['size']}")
        tips.append(f"drop the size {parsed['size']} filter or try a neighbouring size")
    tips.append(
        "use broader keywords — e.g. a category like tee, jacket, jeans, "
        "sneakers, or a style like vintage, 90s, y2k, grunge"
    )
    return (
        f"No listings matched {', '.join(applied)}. "
        f"To find something, try: " + "; ".join(tips) + "."
    )


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Run the loop once and return the finished session.

    Args:
        query:    what the user asked for, in plain language
                  (e.g. "vintage graphic tee under $30, size M").
        wardrobe: a wardrobe dict — get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py.

    Returns:
        The session dict. **Check session["error"] first** — if it isn't None,
        the run ended early and the later fields will still be None.

    ─────────────────────────────────────────────────────────────────────────
    TODO — build this, following the branch rule you wrote in Milestone 2.

      1. Start a session with new_session().

      2. Count the times round the loop, and call trace.check_iterations(count)
         on each one before you go again. It raises when the count passes
         MAX_ITERATIONS in config.py — see trace.py.

      3. Parse the query into a description, a size, and a max_price. Regex,
         string splitting, or asking the model are all fine — say which you
         chose in your README. Put the result in session["parsed"].

      4. Call search_listings() with what you parsed.
         Put the results in session["search_results"].

         ⚠️ THIS IS THE BRANCH. If nothing came back:
              - put a message in session["error"] saying what the user could
                change — "No results" is not that message
              - return the session
              - do NOT call suggest_outfit with nothing

      5. Choose an item — the first result is fine. Put it in
         session["selected_item"].

      6. Call suggest_outfit() with the selected item and the wardrobe.
         Put the result in session["outfit_suggestion"].

      7. Call create_fit_card() with the outfit and the item.
         Put the result in session["fit_card"].

      8. Return the session.

    ─────────────────────────────────────────────────────────────────────────
    IN UNIT 4 you come back and add two things:

      • Trace calls. One per step. `trace.step("search_listings", inputs=...,
        returned=...)` — see trace.py. Your README needs the output.

      • A handler for ModelUnavailable, so a bad key produces a message rather
        than a stack trace. The import is already at the top of this file.
    """
    session = new_session(query, wardrobe)
    count = 0

    while session["next_step"] != "done":
        count += 1
        trace.check_iterations(count)
        step = session["next_step"]

        if step == "parse":
            session["parsed"] = parse_query(session["query"])
            session["next_step"] = "search"

        elif step == "search":
            parsed = session["parsed"]
            session["tool_calls"].append({"tool": "search_listings", "inputs": dict(parsed)})
            session["search_results"] = search_listings(
                parsed["description"], parsed["size"], parsed["max_price"]
            )

            # THE BRANCH: nothing found → explain and stop. Never style nothing.
            if not session["search_results"]:
                session["error"] = _no_results_message(parsed)
                session["next_step"] = "done"
            else:
                session["selected_item"] = session["search_results"][0]
                session["next_step"] = "suggest"

        elif step == "suggest":
            item = session["selected_item"]
            session["tool_calls"].append(
                {"tool": "suggest_outfit", "item_id": item["id"],
                 "wardrobe_items": len(session["wardrobe"].get("items") or [])}
            )
            session["outfit_suggestion"] = suggest_outfit(item, session["wardrobe"])
            session["next_step"] = "card"

        elif step == "card":
            item = session["selected_item"]
            session["tool_calls"].append({"tool": "create_fit_card", "item_id": item["id"]})
            session["fit_card"] = create_fit_card(session["outfit_suggestion"], item)
            session["next_step"] = "done"

    return session


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    if session["error"]:
        print(f"  stopped: {session['error']}")
        print(f"  fit_card is {session['fit_card']!r} — it should still be None here")
        return

    item = session["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    print(f"  outfit:   {session['outfit_suggestion']}")
    print(f"  fit card: {session['fit_card']}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== A query the data can match ===")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    _show(session)
    print(f"  parsed:   {session['parsed']}")
    print(f"  selected: {session['selected_item']['id']}")
    print(f"  calls:    {session['tool_calls']}")

    print("\n=== A query it can't ===")
    session = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    _show(session)
    print(f"  tools called: {[c['tool'] for c in session['tool_calls']]}")

    print(
        "\nThe second one should stop before the fit card. If both paths look "
        "the same,\nthe branch isn't doing anything yet."
    )
