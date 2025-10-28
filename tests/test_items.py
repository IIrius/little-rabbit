"""Item API tests."""
from __future__ import annotations


def test_create_and_list_items(client) -> None:
    payload = {"name": "Widget", "description": "A useful widget"}

    create_response = client.post("/api/items", json=payload)
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["name"] == payload["name"]
    assert body["description"] == payload["description"]
    assert "id" in body

    list_response = client.get("/api/items")
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["name"] == payload["name"]


def test_prevent_duplicate_items(client) -> None:
    payload = {"name": "Gadget"}

    first = client.post("/api/items", json=payload)
    assert first.status_code == 201

    duplicate = client.post("/api/items", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Item already exists"
