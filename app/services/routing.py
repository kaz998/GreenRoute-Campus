import math
import requests


def haversine(a_lat, a_lon, b_lat, b_lon):
    r = 6371
    p = math.pi / 180
    dlat = (b_lat - a_lat) * p
    dlon = (b_lon - a_lon) * p
    x = math.sin(dlat / 2) ** 2 + math.cos(a_lat * p) * math.cos(b_lat * p) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def route_details(lat1, lon1, lat2, lon2):
    straight = haversine(lat1, lon1, lat2, lon2)
    try:
        u = (
            f"https://router.project-osrm.org/route/v1/driving/"
            f"{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        )
        r = requests.get(u, timeout=5, headers={"User-Agent": "GreenRouteCampus/4.0"})
        r.raise_for_status()
        route = r.json()["routes"][0]
        return (
            route["distance"] / 1000,
            route["duration"] / 60,
            "OSRM road route",
            route.get("geometry"),
        )
    except Exception:
        # 1.25 is a transparent road-network approximation when OSRM is unavailable.
        return (
            max(straight * 1.25, 0.2),
            max(straight * 1.25 / 28 * 60, 1),
            "Offline haversine fallback",
            None,
        )


def route_distance(lat1, lon1, lat2, lon2):
    km, mins, source, _ = route_details(lat1, lon1, lat2, lon2)
    return km, mins, source


def geocode(q):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q + ", Lucknow", "format": "json", "limit": 1},
            headers={"User-Agent": "GreenRouteCampus/4.0"},
            timeout=5,
        )
        r.raise_for_status()
        items = r.json()
        if not items:
            return None
        x = items[0]
        return float(x["lat"]), float(x["lon"]), x.get("display_name", q)
    except Exception:
        return None
