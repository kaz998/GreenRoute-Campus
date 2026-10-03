"""Shared transport calculations used by the planner and AI.

Keeping the calculations in one place prevents the UI, trip logger and AI from
quietly drifting apart and reporting different time/cost/emissions numbers.
"""


def driving_baseline(distance_km):
    distance_km = max(float(distance_km), 0.0)
    return {
        "co2": distance_km * 0.18 + 8,
        "cost": distance_km * 8.5 + 8,
    }


def mode_metrics(mode, distance_km, weather):
    distance_km = max(float(distance_km), 0.0)
    speed = max(float(mode["speed_kmh"]), 0.1)
    minutes = distance_km / speed * 60
    code = mode["code"]
    if code == "metro":
        minutes += 8
    elif code == "bus":
        minutes += 5

    cost = float(mode["fixed_cost"]) + distance_km * float(mode["cost_per_km"])
    co2 = distance_km * float(mode["co2_kg_per_km"])
    calories = distance_km * float(mode["calories_per_km"])
    if code == "carpool":
        capacity = max(int(mode["shared_capacity"]), 1)
        cost /= capacity
        co2 /= capacity
        minutes *= 1.08

    notes = []
    feasible = True
    rain = float(weather.get("rain", 0) or 0)
    aqi = float(weather.get("aqi", 0) or 0)
    temp = float(weather.get("temp", 0) or 0)
    if code in ("walk", "bicycle") and distance_km > 15:
        feasible = False
        notes.append("Not practical at this distance")
    if code == "erickshaw" and distance_km > 15:
        feasible = False
        notes.append("Usually unsuitable for this distance")
    if code == "auto" and distance_km > 25:
        feasible = False
        notes.append("Usually unsuitable for this distance")
    if rain > 2 and code in ("walk", "bicycle"):
        notes.append("Rain reduces active-travel suitability")
    if aqi > 120 and code in ("walk", "bicycle"):
        notes.append("Poor AQI reduces outdoor exposure suitability")
    if temp >= 36 and code in ("walk", "bicycle"):
        notes.append("High heat reduces active-travel suitability")

    # A transparent comparative index, not an official environmental score.
    per_km_co2 = co2 / distance_km if distance_km else co2
    per_km_cost = cost / max(distance_km, 1)
    per_km_time = minutes / max(distance_km, 1)
    green_score = max(
        0,
        min(
            100,
            100
            - per_km_co2 * 35
            - per_km_cost * 4
            - per_km_time * 1.2
            + (calories / max(distance_km, 1)) * 0.05,
        ),
    )
    if not feasible:
        green_score = max(0, green_score - 25)

    return {
        "code": code,
        "name": mode["name"],
        "time": round(minutes, 1),
        "cost": round(cost, 2),
        "co2": round(co2, 3),
        "calories": round(calories, 1),
        "green_score": round(green_score, 1),
        "feasible": feasible,
        "notes": notes,
        "weather_note": "; ".join(notes) if any("Rain" in n or "AQI" in n or "heat" in n.lower() for n in notes) else None,
    }


def build_candidates(modes, distance_km, weather):
    return [mode_metrics(mode, distance_km, weather) for mode in modes]
