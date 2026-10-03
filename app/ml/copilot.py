"""GreenRoute local AI mobility copilot.

The model has two layers:
1) TF-IDF + LogisticRegression understands the commuter's natural-language goal.
2) An explainable constraint/ranking engine selects a transport mode from the
   actual transport-mode table, current weather/AQI, distance and constraints.

No API keys or paid AI services are required.
"""
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from app.db import get_db

TRAINING = [
    ("I want the cheapest option", "cheap"),
    ("save money and spend as little as possible", "cheap"),
    ("which route costs less", "cheap"),
    ("under fifty rupees", "cheap"),
    ("I need to get there quickly", "fast"),
    ("fastest way to campus", "fast"),
    ("I am late choose the quickest mode", "fast"),
    ("minimum travel time", "fast"),
    ("I want the greenest option", "green"),
    ("lowest carbon footprint", "green"),
    ("minimize emissions", "green"),
    ("save the most CO2", "green"),
    ("I want to walk or cycle", "healthy"),
    ("I want exercise on my commute", "healthy"),
    ("burn calories and stay active", "healthy"),
    ("I want a healthy commute", "healthy"),
    ("I need something practical today", "balanced"),
    ("give me a balanced recommendation", "balanced"),
    ("good overall option", "balanced"),
]

_VECTOR = TfidfVectorizer(ngram_range=(1, 2), lowercase=True, max_features=500)
_X = _VECTOR.fit_transform([x for x, _ in TRAINING])
_Y = [y for _, y in TRAINING]
_MODEL = LogisticRegression(max_iter=500, random_state=42).fit(_X, _Y)


def _intent(text):
    text = (text or "").strip()
    p = _MODEL.predict_proba(_VECTOR.transform([text]))[0]
    i = int(np.argmax(p))
    return _MODEL.classes_[i], round(float(p[i]) * 100)


def _number(text, pattern, default=None):
    m = re.search(pattern, text, re.I)
    return float(m.group(1)) if m else default


def _explicit_mode(text):
    """Respect a clear user request before optimizing secondary criteria."""
    t = (text or "").lower()
    patterns = [
        (("carpool", "share a ride", "shared ride"), "carpool"),
        (("e-rickshaw", "erickshaw", "electric rickshaw"), "erickshaw"),
        (("metro",), "metro"),
        (("bus", "public transport"), "bus"),
        (("motorbike", "motorbike", "bike taxi"), "motorbike"),
        (("auto", "auto rickshaw", "autorickshaw"), "auto"),
        (("bicycle", "cycle", "cycling"), "bicycle"),
        (("walk", "walking", "on foot"), "walk"),
        (("car", "drive", "driving"), "car"),
    ]
    for words, code in patterns:
        if any(w in t for w in words):
            return code
    return None


def _rank(value, values, reverse=False):
    """0..100, where 100 means best for the objective."""
    lo, hi = min(values), max(values)
    if abs(hi - lo) < 1e-9:
        return 100.0
    if reverse:
        value = hi - value + lo
    return (value - lo) / (hi - lo) * 100


def _build_items(distance_km, weather):
    db = get_db()
    rows = db.execute("SELECT * FROM transport_modes ORDER BY name").fetchall()
    items = []
    for r in rows:
        code = r["code"]
        speed = max(float(r["speed_kmh"]), 0.1)
        time = distance_km / speed * 60
        # Public-transit waiting/transfer overhead makes the comparison more realistic.
        if code == "metro":
            time += 8
        elif code == "bus":
            time += 5
        cost = float(r["fixed_cost"]) + distance_km * float(r["cost_per_km"])
        co2 = distance_km * float(r["co2_kg_per_km"])
        calories = distance_km * float(r["calories_per_km"])
        if code == "carpool":
            cap = max(int(r["shared_capacity"]), 1)
            cost /= cap
            co2 /= cap
            time *= 1.08

        notes = []
        # Practicality guardrails stop the AI from selecting active travel for
        # unrealistic exhibition inputs such as a 100 km commute.
        feasible = True
        if code in ("walk", "bicycle") and distance_km > 15:
            feasible = False
            notes.append("Not practical at this distance")
        if code == "erickshaw" and distance_km > 15:
            feasible = False
            notes.append("Usually unsuitable for this distance")
        if code == "auto" and distance_km > 25:
            feasible = False
            notes.append("Usually unsuitable for this distance")

        weather_penalty = 0
        if float(weather.get("rain", 0) or 0) > 2 and code in ("walk", "bicycle"):
            weather_penalty += 25
            notes.append("Rain reduces active-travel suitability")
        if float(weather.get("aqi", 0) or 0) > 120 and code in ("walk", "bicycle"):
            weather_penalty += 22
            notes.append("Poor AQI reduces outdoor exposure suitability")
        if float(weather.get("temp", 0) or 0) >= 36 and code in ("walk", "bicycle"):
            weather_penalty += 18
            notes.append("High heat reduces active-travel suitability")

        items.append({
            "code": code, "name": r["name"], "time": time, "cost": cost,
            "co2": co2, "calories": calories, "feasible": feasible,
            "weather_penalty": weather_penalty, "notes": notes,
        })
    return items


def _score_items(items, intent, budget=None, max_minutes=None):
    feasible = [x for x in items if x["feasible"]]
    pool = feasible or items
    costs = [x["cost"] for x in pool]
    times = [x["time"] for x in pool]
    co2s = [x["co2"] for x in pool]
    cals = [x["calories"] for x in pool]

    for x in items:
        if not x["feasible"]:
            x["ai_score"] = -1000
            continue
        cheap = _rank(x["cost"], costs, reverse=True)
        fast = _rank(x["time"], times, reverse=True)
        green = _rank(x["co2"], co2s, reverse=True)
        healthy = _rank(x["calories"], cals) * 0.65 + green * 0.35

        # Objective weights are deliberately explicit and explainable.
        weights = {
            "cheap": (0.70, 0.10, 0.15, 0.05),
            "fast": (0.10, 0.70, 0.15, 0.05),
            "green": (0.10, 0.15, 0.70, 0.05),
            "healthy": (0.15, 0.10, 0.30, 0.45),
            "balanced": (0.25, 0.25, 0.35, 0.15),
        }[intent]
        x["ai_score"] = (
            cheap * weights[0] + fast * weights[1] + green * weights[2] + healthy * weights[3]
            - x["weather_penalty"]
        )
        if budget is not None and x["cost"] > budget:
            x["ai_score"] -= min(70, (x["cost"] - budget) * 5)
        if max_minutes is not None and x["time"] > max_minutes:
            x["ai_score"] -= min(70, (x["time"] - max_minutes) * 3)


def advise(text, distance_km=5.0, time_hour=8, weather=None):
    weather = weather or {}
    text = text or ""
    intent, intent_confidence = _intent(text)
    explicit = _explicit_mode(text)
    budget = _number(text, r"(?:under|below|within|budget(?:\s+of)?)\s*[₹rs\.]*\s*(\d+(?:\.\d+)?)")
    max_minutes = _number(text, r"(?:in|within|under)\s*(\d+)\s*(?:minutes|min|mins)")

    items = _build_items(float(distance_km), weather)
    _score_items(items, intent, budget, max_minutes)

    # An explicit transport request is a user constraint, not something the
    # model should override merely because another mode scores higher.
    selected = None
    if explicit:
        selected = next((x for x in items if x["code"] == explicit and x["feasible"]), None)
    if selected is None:
        ranked = sorted(items, key=lambda x: x["ai_score"], reverse=True)
        selected = ranked[0]

    ranked = sorted([x for x in items if x["feasible"]], key=lambda x: x["ai_score"], reverse=True)
    selected_score = selected["ai_score"]
    second_score = next((x["ai_score"] for x in ranked if x["code"] != selected["code"]), selected_score - 20)
    margin = max(0, selected_score - second_score)
    final_conf = min(97, max(58, round(55 + intent_confidence * 0.30 + margin * 0.20)))

    reasons = {
        "cheap": "The AI prioritized the lowest fare first, then used time and CO₂ as tie-breakers.",
        "fast": "The AI prioritized the shortest travel time, while still applying emissions and weather constraints.",
        "green": "The AI prioritized the lowest passenger CO₂ impact, with cost and time as secondary factors.",
        "healthy": "The AI prioritized active calories while rewarding low-emission travel.",
        "balanced": "The AI balanced cost, time, CO₂ and health instead of optimizing only one metric.",
    }
    reason = reasons[intent]
    if explicit:
        reason = f"You explicitly asked for {selected['name']}, so the AI treated that as a constraint. " + reason
    if selected["notes"]:
        reason += " " + " ".join(selected["notes"][:2]) + "."

    return {
        "intent": intent,
        "intent_confidence": intent_confidence,
        "mode": selected["code"],
        "name": selected["name"],
        "confidence": final_conf,
        "reason": reason,
        "time": round(selected["time"], 1),
        "cost": round(selected["cost"], 2),
        "co2": round(selected["co2"], 3),
        "calories": round(selected["calories"], 1),
        "alternatives": [
            {"name": x["name"], "score": round(max(0, min(100, x["ai_score"])), 1),
             "cost": round(x["cost"], 1), "time": round(x["time"], 1),
             "co2": round(x["co2"], 3)}
            for x in ranked if x["code"] != selected["code"]
        ][:4],
        "parsed": {
            "budget": budget, "max_minutes": max_minutes,
            "distance_km": float(distance_km), "departure_hour": int(time_hour),
            "priority": intent, "explicit_mode": explicit,
        },
    }
