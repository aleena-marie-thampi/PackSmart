"""
app.py - Flask web server for PackSmart.
Run with:  python app.py   then open http://127.0.0.1:5000
All data is kept in memory and saved to data.json so it survives restarts.
"""
import json
import math
import os
from flask import Flask, jsonify, render_template, request

from packing import optimize

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
CATEGORIES = ["Documents", "Clothing", "Footwear", "Toiletries", "Electronics", "Health", "Miscellaneous"]
MAX_ITEMS = 50

SAMPLE = {
    "trip": {"name": "5-day Munnar getaway", "limit": 8.0},
    "items": [  # name, kg, category, priority, essential
        ("Passport / ID", 0.1, "Documents", 10, True),
        ("Medicines", 0.4, "Health", 10, True),
        ("Toiletry kit", 0.8, "Toiletries", 9, True),
        ("Phone charger", 0.2, "Electronics", 9, True),
        ("Rain jacket", 0.8, "Clothing", 8, False),
        ("T-shirts (3)", 0.6, "Clothing", 7, False),
        ("Sneakers", 1.1, "Footwear", 7, False),
        ("Camera", 0.9, "Electronics", 7, False),
        ("Power bank", 0.4, "Electronics", 7, False),
        ("Sweater", 0.9, "Clothing", 6, False),
        ("Laptop", 1.8, "Electronics", 6, False),
        ("Umbrella", 0.5, "Miscellaneous", 6, False),
        ("Jeans", 0.7, "Clothing", 5, False),
        ("Water bottle", 0.3, "Miscellaneous", 5, False),
        ("Sandals", 0.5, "Footwear", 4, False),
        ("Towel", 0.6, "Toiletries", 4, False),
        ("Formal outfit", 1.2, "Clothing", 3, False),
        ("Paperback book", 0.4, "Miscellaneous", 3, False),
        ("Binoculars", 0.6, "Miscellaneous", 3, False),
        ("Hair dryer", 0.7, "Toiletries", 2, False),
    ],
}

state = {"trip": {"name": "", "limit": None}, "items": [], "next_id": 1}


# ---------------------------- storage -------------------------------------
def save():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                state.update(json.load(f))
        except (OSError, ValueError):
            pass  # corrupt file: start fresh


def load_sample():
    state["trip"] = dict(SAMPLE["trip"])
    state["items"] = []
    state["next_id"] = 1
    for n, w, c, p, e in SAMPLE["items"]:
        state["items"].append({"id": state["next_id"], "name": n, "weight": w,
                               "category": c, "priority": p, "essential": e})
        state["next_id"] += 1


# --------------------------- validation -----------------------------------
def to_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def validate_trip(data):
    errors = []
    name = str(data.get("name", "")).strip()
    limit = to_number(data.get("limit"))
    if not name or len(name) > 60:
        errors.append("Trip name is required (max 60 characters).")
    if limit is None or not 0.5 <= limit <= 100:
        errors.append("Weight limit must be a number between 0.5 and 100 kg.")
    return {"name": name, "limit": round(limit, 3) if limit is not None else None}, errors


def validate_item(data, editing_id=None):
    errors = []
    name = str(data.get("name", "")).strip()
    weight = to_number(data.get("weight"))
    priority = to_number(data.get("priority"))
    category = data.get("category")
    if not name or len(name) > 60:
        errors.append("Item name is required (max 60 characters).")
    if any(i["name"].lower() == name.lower() and i["id"] != editing_id for i in state["items"]):
        errors.append(f'"{name}" is already in the list.')
    if weight is None or not 0.001 <= weight <= 100:
        errors.append("Weight must be a number between 0.001 and 100 kg.")
    if priority is None or priority != int(priority) or not 1 <= priority <= 10:
        errors.append("Priority must be a whole number from 1 to 10.")
    if category not in CATEGORIES:
        errors.append("Please choose a valid category.")
    if not isinstance(data.get("essential", False), bool):
        errors.append("Essential must be true or false.")
    if editing_id is None and len(state["items"]) >= MAX_ITEMS:
        errors.append(f"A trip can have at most {MAX_ITEMS} items.")
    clean = {"name": name, "weight": round(weight, 3) if weight is not None else None,
             "category": category, "priority": int(priority) if priority is not None and priority == int(priority) else None,
             "essential": bool(data.get("essential", False))}
    return clean, errors


def fail(errors, code=400):
    return jsonify({"errors": errors}), code


def snapshot():
    return {"trip": state["trip"], "items": state["items"], "categories": CATEGORIES}


# ------------------------------ routes ------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def get_state():
    return jsonify(snapshot())


@app.post("/api/trip")
def set_trip():
    trip, errors = validate_trip(request.get_json(silent=True) or {})
    if errors:
        return fail(errors)
    state["trip"] = trip
    save()
    return jsonify(snapshot())


@app.post("/api/items")
def add_item():
    item, errors = validate_item(request.get_json(silent=True) or {})
    if errors:
        return fail(errors)
    item["id"] = state["next_id"]
    state["next_id"] += 1
    state["items"].append(item)
    save()
    return jsonify(snapshot()), 201


@app.put("/api/items/<int:item_id>")
def edit_item(item_id):
    target = next((i for i in state["items"] if i["id"] == item_id), None)
    if target is None:
        return fail(["Item not found."], 404)
    item, errors = validate_item(request.get_json(silent=True) or {}, editing_id=item_id)
    if errors:
        return fail(errors)
    target.update(item)
    save()
    return jsonify(snapshot())


@app.delete("/api/items/<int:item_id>")
def delete_item(item_id):
    before = len(state["items"])
    state["items"] = [i for i in state["items"] if i["id"] != item_id]
    if len(state["items"]) == before:
        return fail(["Item not found."], 404)
    save()
    return jsonify(snapshot())


@app.post("/api/sample")
def sample():
    load_sample()
    save()
    return jsonify(snapshot())


@app.post("/api/clear")
def clear():
    state.update({"trip": {"name": "", "limit": None}, "items": [], "next_id": 1})
    save()
    return jsonify(snapshot())


@app.post("/api/optimize")
def run_optimizer():
    if not state["trip"].get("limit"):
        return fail(["Create a trip and set a weight limit first."])
    if not state["items"]:
        return fail(["Add at least one item first."])
    return jsonify(optimize(state["items"], state["trip"]["limit"]))


load()
if not state["items"] and not state["trip"].get("limit"):
    load_sample()   # first launch: start with demo data

if __name__ == "__main__":
    app.run(debug=True)
