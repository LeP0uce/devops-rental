from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


def test_cars_lists_categories():
    response = client.get("/cars")
    assert response.status_code == 200
    assert {item["category"] for item in response.json()} == {"economy", "standard", "premium"}


def test_quote_standard_two_days():
    response = client.get("/quote", params={"category": "standard", "days": 2})
    assert response.status_code == 200
    assert response.json() == {"category": "standard", "days": 2, "total": 120.0, "currency": "EUR"}


def test_quote_rejects_unknown_category():
    response = client.get("/quote", params={"category": "spaceship", "days": 2})
    assert response.status_code == 400
