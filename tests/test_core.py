import os
import tempfile

import pytest

from app import create_app
from app.db import get_db
from app.services.routing import haversine


@pytest.fixture
def app():
    db_path = tempfile.NamedTemporaryFile(delete=False).name

    app = create_app(
        {
            "TESTING": True,
            "DATABASE": db_path,
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
        }
    )

    # Keep tests self-contained: seed the transport modes required
    # by /api/compare instead of relying on the demo seed script.
    with app.app_context():
        db = get_db()

        modes = [
            (
                "walk",
                "Walk",
                5,
                0,
                0,
                0,
                45,
                1,
                "Test fixture",
                "Test transport mode",
            ),
            (
                "bicycle",
                "Bicycle",
                15,
                0,
                0,
                0,
                25,
                1,
                "Test fixture",
                "Test transport mode",
            ),
            (
                "erickshaw",
                "E-rickshaw",
                20,
                2.5,
                10,
                0.035,
                0,
                4,
                "Test fixture",
                "Test transport mode",
            ),
            (
                "bus",
                "City Bus",
                22,
                2.5,
                0,
                0.06,
                0,
                40,
                "Test fixture",
                "Test transport mode",
            ),
            (
                "metro",
                "Metro",
                35,
                3,
                10,
                0.04,
                0,
                1,
                "Test fixture",
                "Test transport mode",
            ),
            (
                "motorbike",
                "Motorbike",
                38,
                3.2,
                8,
                0.11,
                0,
                1,
                "Test fixture",
                "Test transport mode",
            ),
            (
                "auto",
                "Auto-rickshaw",
                25,
                5,
                10,
                0.12,
                0,
                3,
                "Test fixture",
                "Test transport mode",
            ),
            (
                "car",
                "Car",
                30,
                8.5,
                8,
                0.18,
                0,
                1,
                "Test fixture",
                "Test transport mode",
            ),
            (
                "carpool",
                "Carpool",
                30,
                8.5,
                8,
                0.18,
                0,
                4,
                "Test fixture",
                "Test transport mode",
            ),
        ]

        db.executemany(
            """
            INSERT INTO transport_modes
            (
                code,
                name,
                speed_kmh,
                cost_per_km,
                fixed_cost,
                co2_kg_per_km,
                calories_per_km,
                shared_capacity,
                source,
                assumption
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            modes,
        )
        db.commit()

    yield app

    os.unlink(db_path)


def test_haversine(app):
    assert haversine(
        26.8467,
        80.9462,
        26.8467,
        80.9462,
    ) == 0


def test_auth_and_route_api(app):
    client = app.test_client()

    response = client.post(
        "/register",
        data={
            "name": "A",
            "email": "a@example.com",
            "password": "secret123",
            "department": "CSE",
            "year": "1st",
            "home_area": "Gomti Nagar",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    client.post(
        "/login",
        data={
            "email": "a@example.com",
            "password": "secret123",
        },
    )

    response = client.post(
        "/api/route",
        json={
            "olat": 26.8467,
            "olon": 80.9462,
            "dlat": 26.85,
            "dlon": 80.95,
        },
    )

    assert response.status_code == 200
    assert response.json["distance_km"] > 0


def test_compare(app):
    client = app.test_client()

    client.post(
        "/register",
        data={
            "name": "A",
            "email": "a2@example.com",
            "password": "secret123",
        },
    )

    client.post(
        "/login",
        data={
            "email": "a2@example.com",
            "password": "secret123",
        },
    )

    response = client.post(
        "/api/compare",
        json={"distance_km": 5},
    )

    assert response.status_code == 200
    assert len(response.json["items"]) >= 8
