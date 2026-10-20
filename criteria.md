# Acceptance criteria — FitFindr

Five criteria that say what "working" means for this agent, written in unit 3
**before** any results existed.

An acceptance criterion names a target: a number, a count, a rate, or something
a person could plainly observe. *"The agent handles errors"* is an opinion.
*"When search returns nothing, the agent stops before calling the second tool,
in 5 of 5 tries"* is a criterion.

Under each one, write a sentence or two on **why that target** and not a
stricter one. A reason that says something about your tools, your loop, or the
data earns credit; *"80% seemed reasonable"* does not.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

**Two are written for you. You write three.**

---

## 1. A matching query completes all three tools

Given a query that matches at least one listing, the agent completes all three
tool calls and returns a fit card — in at least 4 of 5 tries.

**Why this target:**
My search is a whole-word keyword match, not a semantic one, so a phrasing the
data doesn't use ("t-shirt" when listings say "tee") can come back empty even
though a match exists. Two of the three calls also go to a free-tier model that
can rate-limit or time out mid-run. One miss in five allows for either; two
would mean something structural is wrong.

---

## 2. An impossible query stops before the second tool

Given a query that matches no listings, the agent stops before calling
`suggest_outfit` and returns a message naming what to change — 5 of 5 tries.

**Why this target:**
This path never touches the model. The branch is a plain `if not results:`
check on a list that `search_listings` always returns (never `None`), and the
message is built from the parsed filters in code. Nothing on this path is
random, so anything less than 5 of 5 would be a bug, not variance.

---

## 3. The item search found is the item every later tool received

For 5 different matching queries, the `id` of `session["selected_item"]` is
identical to the `id` of the item recorded as the input to `suggest_outfit`
**and** to `create_fit_card` in `session["tool_calls"]`, and
`session["selected_item"]` is the first entry of `session["search_results"]`
— 5 of 5 runs.

**Why this target:**
The hand-off between tools is pure code reading from the session dict; no
model sits between search and the next call, so there is no legitimate source
of variation. A single mismatch would mean the loop passed something other
than what the session holds, which is exactly the failure this criterion
exists to catch.

---

## 4. The fit card names the find and stays caption-sized

For the query `vintage graphic tee under $30` run 5 times with the cache off,
the fit card (a) contains the selected item's price written as `$` followed by
the number (e.g. `$24`), (b) contains the item's platform name
(case-insensitive), and (c) is between 2 and 4 sentences and under 400
characters — all three in at least 4 of 5 tries. Separately, no two of the
5 cards are word-for-word identical.

**Why this target:**
The wording is supposed to change between runs, so I check facts and shape,
not phrasing. The price, platform and length are things my prompt asks for
explicitly, but the model can still write "24 bucks" or run long at
temperature 0.9, so I allow one miss. The "not identical" check is 5 of 5
because identical cards would mean the cache or temperature is wrong, not the
model.

---

## 5. Search results respect the price ceiling and size the user typed

For these 5 queries, every listing in `session["search_results"]` has
`price` ≤ the dollar amount in the query and (where a size is given) a size
that matches it under the rules in my Tool Inventory, and
`session["parsed"]` shows the right `max_price` and `size` — 5 of 5 queries:

1. `vintage graphic tee under $30` → max_price 30.0, no size
2. `90s track jacket in size M` → size "M", no price
3. `platform sneakers size 8` → size "8"; only `US 8` shoes, never `US 8.5`
4. `denim jacket under 50 dollars` → max_price 50.0
5. `band tee, size L, max $20` → size "L" (not `XL`), max_price 20.0

**Why this target:**
Showing someone a $45 jacket when they said under $30, or an XL when they
asked for L, makes the whole agent look broken even if the fit card is
lovely. Parsing is regex and the filters are code, so this should be
deterministic — but the five queries deliberately use different phrasings
("under $30", "under 50 dollars", "max $20", "in size M", "size 8") so a
parser that only handles one form will miss.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 4 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 4. Something about the fit card

         The fit card is different every time.

         **Why this target:** ...

         > **Revised in unit 4:** For 5 different items, the 5 fit cards share
         > no opening sentence.
         >
         > **Why revised:** "different" wasn't checkable — two cards that
         > differed by one word still counted. The new version is something I
         > can actually score.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said the empty search stops it 5 of 5 times, but I got 3 of 5,
            so 3 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->
