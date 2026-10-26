"""
packing.py - the AI part of PackSmart (no machine learning, no external APIs).

Two ideas are implemented here:

1. CSP (Constraint Satisfaction Problem)
   - Every item is a VARIABLE with the DOMAIN {0, 1}  (0 = leave, 1 = pack).
   - Constraint A (capacity):  sum(weight of packed items) <= luggage limit.
   - Constraint B (essential): an essential item must have the value 1.
   build_csp() applies Constraint B up front (the domain of an essential item
   becomes {1}) and does "forward checking": a non-essential item that cannot
   fit next to the essentials gets the domain {0}.  Smaller domains = less search.

2. Backtracking search with branch-and-bound pruning
   - Decide the variables one at a time (try "pack" first, then "leave").
   - Backtrack as soon as the capacity constraint is broken.
   - Prune a branch when even an optimistic estimate of its best possible score
     cannot beat the best complete solution found so far.
   - Result: the feasible assignment with the MAXIMUM total priority score.

Weights are converted to whole grams internally so that float rounding
errors (0.1 + 0.2 != 0.3) can never break the capacity check.
"""

NODE_LIMIT = 300_000   # safety net so the web page never hangs


def grams(kg):
    """Convert kilograms to integer grams."""
    return int(round(float(kg) * 1000))


def kg(g):
    """Convert integer grams back to kilograms for display."""
    return round(g / 1000, 3)


# --------------------------------------------------------------------------
# 1. CSP definition
# --------------------------------------------------------------------------
def build_csp(items, capacity_g):
    """Create the CSP: variables, domains and a feasibility check."""
    domains = {}
    forced_weight = sum(grams(i["weight"]) for i in items if i["essential"])

    csp = {"capacity": capacity_g, "forced_weight": forced_weight,
           "domains": domains, "feasible": True, "message": ""}

    # Constraint check: the essentials alone must fit in the luggage.
    if forced_weight > capacity_g:
        csp["feasible"] = False
        csp["message"] = (
            f"No valid packing exists: essential items weigh {kg(forced_weight)} kg "
            f"but the limit is {kg(capacity_g)} kg. Raise the limit or "
            f"un-mark an item as essential.")
        return csp

    free = capacity_g - forced_weight
    for item in items:
        if item["essential"]:
            domains[item["id"]] = [1]            # Constraint B
        elif grams(item["weight"]) > free:
            domains[item["id"]] = [0]            # forward checking: can never fit
        else:
            domains[item["id"]] = [0, 1]         # still undecided
    return csp


# --------------------------------------------------------------------------
# 2. Backtracking search (maximise total priority)
# --------------------------------------------------------------------------
def solve_backtracking(items, capacity_g):
    csp = build_csp(items, capacity_g)
    if not csp["feasible"]:
        return _infeasible("Backtracking (optimal)", csp)

    by_id = {i["id"]: i for i in items}
    base_weight = csp["forced_weight"]
    base_score = sum(i["priority"] for i in items if i["essential"])

    # Only variables whose domain is still {0,1} need to be searched.
    # Sorting by value-per-gram makes good solutions appear early, which
    # makes pruning much more effective.
    undecided = sorted(
        (by_id[v] for v, d in csp["domains"].items() if len(d) == 2),
        key=lambda i: i["priority"] / grams(i["weight"]), reverse=True)

    # Best solution so far: start with "pack only the essentials".
    best = {"score": base_score, "choice": {}}
    stats = {"nodes": 0, "pruned": 0, "truncated": False}

    def optimistic_bound(index, room):
        """Upper bound on extra score still reachable from `index`.
        Fill the room with the remaining items, allowing the last one to be
        taken fractionally. A real solution can never beat this number."""
        bound = 0.0
        for it in undecided[index:]:
            w = grams(it["weight"])
            if w <= room:
                bound += it["priority"]
                room -= w
            else:
                bound += it["priority"] * room / w
                break
        return bound

    def search(index, weight, score, choice):
        stats["nodes"] += 1
        if stats["nodes"] > NODE_LIMIT:
            stats["truncated"] = True
            return
        if index == len(undecided):                       # every variable assigned
            if score > best["score"]:
                best["score"], best["choice"] = score, dict(choice)
            return
        # Branch-and-bound pruning
        if score + optimistic_bound(index, capacity_g - weight) <= best["score"]:
            stats["pruned"] += 1
            return

        item = undecided[index]
        w = grams(item["weight"])
        # Value 1 (pack) - only if the capacity constraint still holds
        if weight + w <= capacity_g:
            choice[item["id"]] = 1
            search(index + 1, weight + w, score + item["priority"], choice)
            del choice[item["id"]]                        # BACKTRACK
        else:
            stats["pruned"] += 1                          # constraint violated
        # Value 0 (leave)
        choice[item["id"]] = 0
        search(index + 1, weight, score, choice)
        del choice[item["id"]]                            # BACKTRACK

    search(0, base_weight, base_score, {})

    packed_ids = {i["id"] for i in items if i["essential"]}
    packed_ids |= {k for k, v in best["choice"].items() if v == 1}
    stats["search_space"] = 2 ** len(undecided)
    note = ""
    if stats["truncated"]:
        note = "Search stopped at the safety limit; this is the best list found, not guaranteed optimal."
    return _build_result("Backtracking (optimal)", items, packed_ids, capacity_g, csp, stats, note)


# --------------------------------------------------------------------------
# Helpers: explanations and result formatting
# --------------------------------------------------------------------------
def _infeasible(method, csp):
    return {"method": method, "feasible": False, "message": csp["message"],
            "packed": [], "excluded": [], "total_weight": 0, "capacity": kg(csp["capacity"]),
            "remaining": kg(csp["capacity"]), "score": 0, "max_score": 0,
            "stats": {"nodes": 0, "pruned": 0, "truncated": False}}


def _build_result(method, items, packed_ids, capacity_g, csp, stats, note):
    total_g = sum(grams(i["weight"]) for i in items if i["id"] in packed_ids)
    left_g = capacity_g - total_g
    free_after_essentials = capacity_g - csp["forced_weight"]
    packed, excluded = [], []

    for it in items:
        w = grams(it["weight"])
        row = dict(it)
        if it["id"] in packed_ids:
            if it["essential"]:
                row["reason"] = "Essential: the CSP forces this item to be packed."
            else:
                row["reason"] = (f"Packed: priority {it['priority']} for {kg(w)} kg "
                                 f"({it['priority'] / (w / 1000):.1f} points per kg) "
                                 f"gives a high score for the space it uses.")
            packed.append(row)
        else:
            if w > free_after_essentials:
                row["reason"] = (f"Excluded: {kg(w)} kg is more than the {kg(free_after_essentials)} kg "
                                 f"left after packing the essentials.")
            elif w > left_g:
                row["reason"] = (f"Excluded: only {kg(left_g)} kg is left in the final list. "
                                 f"Fitting this item would mean dropping items worth more points.")
            else:
                row["reason"] = "Excluded: lower value than the items that were chosen."
            excluded.append(row)

    packed.sort(key=lambda r: (not r["essential"], -r["priority"]))
    excluded.sort(key=lambda r: -r["priority"])
    return {"method": method, "feasible": True, "message": note,
            "packed": packed, "excluded": excluded,
            "total_weight": kg(total_g), "capacity": kg(capacity_g), "remaining": kg(left_g),
            "score": sum(r["priority"] for r in packed),
            "max_score": sum(i["priority"] for i in items), "stats": stats}


def optimize(items, capacity_kg):
    """Run the CSP + backtracking solver and return the result."""
    return {"backtracking": solve_backtracking(items, grams(capacity_kg))}
