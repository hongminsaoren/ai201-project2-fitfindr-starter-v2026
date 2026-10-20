# FitFindr

> ### 👋 Start here
>
> **New to this repo? Read [RUNNING.md](RUNNING.md) first** — setup, every
> command, and what to do when something breaks.
>
> Once `python test.py` passes:
>
> ```bash
> python app.py listings --full -n 6      # read the data (Milestone 1)
> python app.py fields                    # what you can filter on
> python app.py ask 'vintage graphic tee under $30'
> ```
>
> All three tools are stubs, so that last command will do nothing useful yet.
> That's the starting position.
>
> **The rest of this file is your submission.** Fill it in as you go.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     HOW TO USE THIS FILE

     This is your submission. Fill each section in as you finish the milestone
     it belongs to — don't leave it all to the end.

     Unit 3 asks for the first five sections. Unit 4 adds the five below them.
     Leave the unit 4 sections alone until then; they're here so you know
     what's coming.

     Everything is pasted as TEXT. No screenshots, no images, no video links.
     A typed block of output gets full credit; a picture of the same output
     gets none.
     ───────────────────────────────────────────────────────────────────────── -->

<!-- ═══════════════════════ UNIT 3 — THE BUILD ═══════════════════════ -->

## What This Does

FitFindr takes a plain-language thrift request like *"a vintage graphic tee under $30, size M"*, pulls a description, size and price ceiling out of it, and searches 40 listings from Depop, ThredUp and Poshmark. If something matches, it picks the best match, asks the model for two outfits that use pieces from the user's own wardrobe, and then writes a short caption the user could post, mentioning the item, its price and its platform. If nothing matches, it stops before any model call and tells the user which filters it applied and what to loosen.


---

## Tool Inventory

<!-- Four lines per tool. This is worth 2 points and it's the single most
     common place students lose them.

     "Returns a list" earns NOTHING. The description has to say what is IN
     the list.

     The empty case isn't optional either — it's the thing your loop branches
     on, and if you don't decide it here you'll discover it as a crash in
     Milestone 5. -->

### `search_listings`

- **What it does:** Filters `data/listings.json` by price ceiling and size, then ranks what's left by whole-word keyword overlap with the description (title hits count most, then style tags, then category/colors/brand/description) and returns the best matches first.
- **Inputs:** `description` (str) — keywords like `"vintage graphic tee"`; `size` (str | None) — e.g. `"M"`, `"8"`, `"W30"`, or `None` to skip; `max_price` (float | None) — inclusive ceiling in dollars, or `None` to skip.
- **Returns:** `list[dict]` — up to `config.SEARCH_RESULT_LIMIT` (10) listing dicts, best match first, each with the dataset's own fields: `id`, `title`, `description`, `category`, `style_tags` (list[str]), `size`, `condition`, `price` (float), `colors` (list[str]), `brand` (str or None), `platform`. Results are the original dicts, unmodified.
- **When it has nothing:** an empty list `[]` — never `None`, never an exception. That includes a description with no usable keywords.
- **What counts as a size match:** letter sizes match as whole tokens, so `M` matches `M`, `S/M`, `M/L` but not `XL`; `S` never matches `XS` or `US 9`. `One Size` listings match any letter size. A number matches shoe sizes (`8` → `US 8`, not `US 8.5`) and waist sizes (`30` → `W30`, `W30 L30`).

### `suggest_outfit`

- **What it does:** Asks the model for one or two outfits built around the new item, naming specific pieces from the user's wardrobe by name.
- **Inputs:** `new_item` (dict) — one listing dict, as returned by `search_listings`; `wardrobe` (dict) — `{"items": [ {id, name, category, colors, style_tags, notes}, ... ]}`, the shape in `data/wardrobe_schema.json`.
- **Returns:** `str` — a non-empty plain-text outfit suggestion (a few short lines, one per outfit).
- **When it has nothing:** an empty `wardrobe["items"]` is not an error — it returns general styling advice for the item (what kinds of pieces pair with it) instead of combinations. If `new_item` is empty or `None`, it returns the string `"No item to style — search_listings didn't hand one over."` without calling the model. It never returns `""` or raises for these cases.

### `create_fit_card`

- **What it does:** Asks the model to write a 2–4 sentence caption someone would post about the find, mentioning the item's title, price and platform once each.
- **Inputs:** `outfit` (str) — the text `suggest_outfit` returned; `new_item` (dict) — the same listing dict that went into `suggest_outfit`.
- **Returns:** `str` — the caption, plain text, 2–4 sentences, at most two hashtags.
- **When it has nothing:** if `outfit` is empty or whitespace-only, it returns the string `"Can't write a fit card: there's no outfit suggestion to build it from."` without calling the model. It never raises for that case.

---

## Planning Loop

<!-- Your branch rule, stated as a rule — the condition AND both paths — plus
     the file and function that holds it.

     Like this:
       "If search_listings returns an empty list, put a message in the session
        and stop. Otherwise take the first result and go to suggest_outfit."
        — agent.py::run_agent

     The grader checks your code against what you claim here, so the file and
     function have to be real. -->

**Branch rule:** If `search_listings` returns an empty list, put a message in `session["error"]` that names the filters that were applied and what to loosen (raise the price, drop or change the size, use fewer/different keywords), and stop — `suggest_outfit` and `create_fit_card` are never called and `session["fit_card"]` stays `None`. Otherwise, take the first (best-scoring) result as `session["selected_item"]` and go to `suggest_outfit`.

**Where it lives:** `agent.py::run_agent`

**How the query is parsed:** Regex, in `agent.py::parse_query`. No model call. A price comes from `under $30`, `under 50 dollars`, `max $20`, `up to 40` or a bare `$30`. A size comes from `size M`, `in size M`, `size 8`, `size W30` or `in M`. Whatever's left, minus commas, becomes the description, and `search_listings` drops filler words like "looking for a" itself.

**How the loop runs:** `run_agent` is a `while` loop driven by `session["next_step"]` (`parse` → `search` → `suggest` → `card` → `done`). Each pass calls `trace.check_iterations(count)` and then does the one step the session names. The `search` step is the only place where two different next steps are possible, and that's the branch.

**What moves through the session:** `query` → `parsed` (`description`, `size`, `max_price`) → `search_results` (the list `search_listings` returned) → `selected_item` (`search_results[0]`) → `outfit_suggestion` → `fit_card`. Each tool reads its inputs back out of the session, not from a local variable, so `suggest_outfit` gets `session["selected_item"]` and `create_fit_card` gets `session["outfit_suggestion"]` plus that same `session["selected_item"]`. `session["tool_calls"]` records every tool call with the item `id` it received, so criterion 3 can check that the hand-off really happened. On the empty path, `session["error"]` holds the message, and `selected_item`, `outfit_suggestion` and `fit_card` stay `None`.

---

## Sample Run

<!-- Two things go here.

     1. One FULL query and its output, pasted as text.
     2. Your three per-tool terminal tests — the command and what it printed. -->

**One full query** (example wardrobe)

```
$ python app.py ask 'a vintage graphic tee under $30, size M'
  Found:    Y2K Baby Tee — Butterfly Print — $18.0 on depop

  Outfit:   Outfit 1: Y2K Baby Tee — Butterfly Print paired with Baggy straight-leg jeans, dark wash, Vintage black denim jacket, and Chunky white sneakers.

Outfit 2: Y2K Baby Tee — Butterfly Print paired with Wide-leg khaki trousers, Black cropped zip hoodie, and Black combat boots.

  Fit card: Scored the cutest little butterfly tee on depop for just $18 and I am obsessed. It gives major early 2000s mall-rat energy, especially styled with baggy denim and chunky sneakers. Going to live in this all season. #y2kstyle #thriftfinds

0 model calls this session, 2 served from cache
```

The "served from cache" line is there because this exact query had already run once. The first run made 2 real model calls.

**The empty path**, which stops after `search_listings` with 0 model calls:

```
$ python app.py ask 'designer ballgown size XXS under $5'
  No listings matched "designer ballgown", under $5, size XXS. To find something, try: raise the price above $5 (most listings are $15–$50); drop the size XXS filter or try a neighbouring size; use broader keywords — e.g. a category like tee, jacket, jeans, sneakers, or a style like vintage, 90s, y2k, grunge.

0 model calls this session
```

**The three tools, tested one at a time**

```
$ python -c "from tools import search_listings; print([(r['id'], r['title'], r['size'], r['price']) for r in search_listings('graphic tee', max_price=30)])"
[('lst_006', 'Graphic Tee — 2003 Tour Bootleg Style', 'L', 24.0), ('lst_002', 'Y2K Baby Tee — Butterfly Print', 'S/M', 18.0), ('lst_033', 'Vintage Band Tee — Faded Grey', 'L', 19.0), ('lst_015', 'Vintage Graphic Hoodie — Faded Black', 'L', 26.0), ('lst_017', 'Mesh Long-Sleeve Top — Black', 'S/M', 15.0), ('lst_011', 'Low-Rise Cargo Pants — Khaki', 'W29', 27.0)]
```

```
$ python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
Outfit 1: Vintage Levi's 501 Jeans — Medium Wash paired with White ribbed tank top, Black cropped zip hoodie, and Chunky white sneakers.

Outfit 2: Vintage Levi's 501 Jeans — Medium Wash paired with Oversized grey crewneck sweatshirt, Brown leather belt, and Black combat boots.
```

```
$ python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
Scored these vintage Levi's 501s on depop for just $38 and I am obsessed. The medium wash and broken-in fade at the knees give them that ultimate effortless streetwear vibe. Can't wait to style them with my favorite white sneakers on repeat. #vintagelevis #denimstyle
```

---

## How I Used AI

<!-- Two specific moments. What you asked, what came back, what you changed.

     "I used Claude to help me code" is not enough.

     "I gave Claude my search_listings spec. It returned None on no match
     instead of an empty list, so I changed it" is the level we want. -->

**Moment 1: the query parser**

- *What I asked for:* I had Claude Code write `parse_query` in `agent.py`, a regex that pulls `size` and `max_price` out of the query, and run it on the five phrasings in my criterion 5.
- *What came back:* Size and price parsed correctly in all five, but `90s track jacket in size M` left the description as `"90s track jacket in"`. The size regex consumed `size M` but not the `in` before it.
- *What I changed:* I made the size pattern also consume an optional leading `in ` (`(?:\bin\s+)?\bsize\s+...`) and re-ran it. The description became `"90s track jacket"`. Search happened to work either way, because `in` is a stopword, but criterion 5 checks `session["parsed"]`, so the leftover word would have counted against it.

**Moment 2: checking the fit cards for invented details**

- *What I asked for:* I ran all five example queries through `app.py ask` and read the fit cards. Two of them named brands ("vintage Champion track jacket", "vintage Wrangler cropped denim jacket") that weren't in the query.
- *What came back:* I suspected the model was making brands up. I had Claude check the listings, and `lst_004` really is `Champion` and `lst_007` really is `Wrangler`. `_describe_item` in `tools.py` passes the brand to the model only when it isn't `None`, and the platform-sneaker card (brand `None`) named no brand.
- *What I changed:* Nothing in the prompt. The brand handling was already right, and I left it alone. What I did change was the plan for criterion 4: in unit 4 I'll check fit cards against the listing's fields, not just for price and platform, because a hallucinated brand would look just as confident as a real one.

<!-- ═══════════════════════ UNIT 4 — THE TEST ═══════════════════════

     Don't fill these in during unit 3.
     ═══════════════════════════════════════════════════════════════════ -->

---

## Run Log — Before

<!-- Five criteria, five tries each, in this exact format.

     Five, because your criteria are written out of five. Mark each try PASS
     or FAIL, count the passes, and read that count against your target — a
     row targeting 4 of 5 with three PASS cells is MISSED (3/5).

     `python run_eval.py --label before` runs everything and writes the table
     into results/. Paste it here and fill in the verdicts. -->

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |  |  |
| 2.  |  |  |  |  |  |  |  |
| 3.  |  |  |  |  |  |  |  |
| 4.  |  |  |  |  |  |  |  |
| 5.  |  |  |  |  |  |  |  |

**Real output from one try**, pasted as text, naming the file and function
that produced it:

```

```

---

## Verdicts and Diagnoses

<!-- MET or MISSED per criterion against LAST UNIT's target, plus a sentence on
     how you decided.

     Then, for every miss: which of the four places it happened — a tool, the
     loop's branch, the session, or the model's output — AND the mechanism.

     Not a diagnosis:  "The fit card was bad."
     A diagnosis:      "The fit card criterion missed on 2 of 5 items. Both had
                        an empty brand field. My prompt puts the brand in the
                        first sentence, so the card opened with a blank and read
                        like a fragment. The tool worked; the prompt assumed a
                        field that isn't always there."

     Look for a pattern. Three misses on the same tool is one problem, not
     three. -->

| # | Criterion | Target | Verdict | How I decided |
|---|---|---|---|---|
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |
| 4 |  |  |  |  |
| 5 |  |  |  |  |

**Diagnoses**



---

## Loop Trace

<!-- One full run, printed step by step, with the MCP call visible in it.

     `python app.py ask '...' --trace` once you've added the trace.step()
     calls in Milestone 2.

     Worth pasting BOTH the happy path and the empty-search path. The empty
     one should be visibly shorter, because it stops. If your two traces are
     the same length, your branch isn't working — and this is the fastest way
     anyone will ever find that out. -->

**Happy path**

```

```

**Empty search**

```

```

**On the MCP move:** <!-- what changed in your code, and whether anything
behaved differently afterwards. If the rewire didn't work, say exactly where it
broke — the error text and the last thing that worked. That earns the point in
full. -->



---

## The Improvement

<!-- What you changed, why your diagnosis pointed at it, and the after-run in
     the same table format. One change, measured properly.

     `python run_eval.py --label after` -->

**What I changed:**

**Which failure it was meant to fix:**

### Run Log — After

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |  |  |
| 2.  |  |  |  |  |  |  |  |
| 3.  |  |  |  |  |  |  |  |
| 4.  |  |  |  |  |  |  |  |
| 5.  |  |  |  |  |  |  |  |

**Did it help, and how do I know:**

<!-- If it made things worse, say that. Honestly reported, that earns full
     credit and is more interesting than one that worked. -->



---

## What's Still Broken

<!-- For each criterion still missed: what you'd do, and why you stopped where
     you did. "I ran out of time" is fine if it's true. Pretending nothing is
     left is not. -->



<!-- ═════════════════════════════════════════════════════════════════════

     SUBMISSION CHECKLIST — unit 3

       [ ] criteria.md has five numbered criteria, each with a target
       [ ] Each criterion has a reason underneath it
       [ ] All five unit 3 sections above have real content
       [ ] Tool Inventory: all three tools, inputs WITH TYPES, a specific
           return value, and the empty case
       [ ] Planning Loop names the branch rule and agent.py::run_agent
       [ ] Sample Run: one full query plus the three per-tool tests, as text
       [ ] At least four new commits
       [ ] Repository URL submitted — WRITE IT DOWN, you submit the same one
           next unit

     SUBMISSION CHECKLIST — unit 4

       [ ] mcp_server.py exists with one tool registered
           (or a written record of exactly where the rewire broke)
       [ ] Run Log — Before, five criteria, five tries each
       [ ] Real output pasted underneath, naming file and function
       [ ] A verdict on every criterion
       [ ] A diagnosis for every miss, naming a place AND a mechanism
       [ ] Loop Trace, with the MCP call visible in it
       [ ] All three failure modes triggered and handled
       [ ] One improvement, with Run Log — After in the same format
       [ ] What's Still Broken
       [ ] At least four new commits
       [ ] The SAME repository URL as last unit

     Do not delete and recreate this repository. Your commit history is what
     shows your criteria existed before your results did.
     ═════════════════════════════════════════════════════════════════════ -->

---

📖 **How to run this project: [RUNNING.md](RUNNING.md)**
