"""Workspace dashboard API tests."""
from __future__ import annotations

import time
from typing import Any

import pytest


def _wait_for_pipeline_completion(client, workspace: str) -> dict[str, Any]:
    for _ in range(20):
        response = client.get(f"/api/workspaces/{workspace}/pipeline/runs")
        assert response.status_code == 200
        runs = response.json()
        if runs:
            status = runs[0]["status"]
            if status in {"success", "failure"}:
                return runs[0]
        time.sleep(0.05)
    pytest.fail("pipeline run did not complete in time")


def test_workspace_source_crud_flow(client) -> None:
    workspace = "dev"
    payload = {
        "name": "Primary Feed",
        "kind": "rss",
        "endpoint": "https://example.com/feed.xml",
        "is_active": True,
    }

    created = client.post(f"/api/workspaces/{workspace}/sources", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == payload["name"]
    assert body["kind"] == payload["kind"]
    assert body["endpoint"] == payload["endpoint"]
    source_id = body["id"]

    duplicate = client.post(f"/api/workspaces/{workspace}/sources", json=payload)
    assert duplicate.status_code == 409

    listing = client.get(f"/api/workspaces/{workspace}/sources")
    assert listing.status_code == 200
    entries = listing.json()
    assert len(entries) == 1
    assert entries[0]["id"] == source_id

    update_payload = {
        "name": "Primary Feed",
        "kind": "api",
        "endpoint": "https://example.com/api-feed",
        "is_active": False,
    }
    updated = client.put(
        f"/api/workspaces/{workspace}/sources/{source_id}", json=update_payload
    )
    assert updated.status_code == 200
    update_body = updated.json()
    assert update_body["kind"] == "api"
    assert update_body["is_active"] is False

    deleted = client.delete(f"/api/workspaces/{workspace}/sources/{source_id}")
    assert deleted.status_code == 204

    empty = client.get(f"/api/workspaces/{workspace}/sources")
    assert empty.status_code == 200
    assert empty.json() == []


def test_workspace_proxy_crud_flow(client) -> None:
    workspace = "dev"
    payload = {
        "name": "Primary Proxy",
        "protocol": "http",
        "address": "http://proxy.example:8080",
        "is_active": True,
    }

    created = client.post(f"/api/workspaces/{workspace}/proxies", json=payload)
    assert created.status_code == 201
    proxy_id = created.json()["id"]

    listing = client.get(f"/api/workspaces/{workspace}/proxies")
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == proxy_id

    update_payload = {
        "name": "Primary Proxy",
        "protocol": "socks5",
        "address": "socks5://proxy.example:9090",
        "is_active": False,
    }
    updated = client.put(
        f"/api/workspaces/{workspace}/proxies/{proxy_id}", json=update_payload
    )
    assert updated.status_code == 200
    assert updated.json()["protocol"] == "socks5"

    deleted = client.delete(f"/api/workspaces/{workspace}/proxies/{proxy_id}")
    assert deleted.status_code == 204

    empty = client.get(f"/api/workspaces/{workspace}/proxies")
    assert empty.status_code == 200
    assert empty.json() == []


def test_workspace_telegram_channel_crud_flow(client) -> None:
    workspace = "dev"
    payload = {
        "name": "Alerts Channel",
        "chat_id": "@alerts_channel",
        "is_active": True,
    }

    created = client.post(
        f"/api/workspaces/{workspace}/telegram-channels", json=payload
    )
    assert created.status_code == 201
    channel_id = created.json()["id"]

    listing = client.get(f"/api/workspaces/{workspace}/telegram-channels")
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == channel_id

    update_payload = {
        "name": "Alerts Channel",
        "chat_id": "123456789",
        "is_active": False,
    }
    updated = client.put(
        f"/api/workspaces/{workspace}/telegram-channels/{channel_id}",
        json=update_payload,
    )
    assert updated.status_code == 200
    assert updated.json()["chat_id"] == "123456789"

    deleted = client.delete(
        f"/api/workspaces/{workspace}/telegram-channels/{channel_id}"
    )
    assert deleted.status_code == 204

    empty = client.get(f"/api/workspaces/{workspace}/telegram-channels")
    assert empty.status_code == 200
    assert empty.json() == []


def test_pipeline_trigger_and_websocket_updates(client) -> None:
    workspace = "dev"
    with client.websocket_connect(
        f"/api/workspaces/{workspace}/pipeline/status"
    ) as websocket:
        snapshot = websocket.receive_json()
        assert snapshot["event"] == "snapshot"
        assert snapshot["runs"] == []

        trigger = client.post(f"/api/workspaces/{workspace}/pipeline/trigger")
        assert trigger.status_code == 202
        run_id = trigger.json()["id"]

        queued = websocket.receive_json()
        assert queued["event"] == "update"
        assert queued["run"]["id"] == run_id
        assert queued["run"]["status"] == "queued"

        running = websocket.receive_json()
        assert running["run"]["status"] == "running"

        completed = websocket.receive_json()
        assert completed["run"]["status"] == "success"
        assert "published" in completed["run"]["message"]

    runs_response = client.get(f"/api/workspaces/{workspace}/pipeline/runs")
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert runs
    assert runs[0]["status"] == "success"


def test_workspace_dashboard_snapshot(client) -> None:
    workspace = "dev"

    source_resp = client.post(
        f"/api/workspaces/{workspace}/sources",
        json={
            "name": "Secondary Feed",
            "kind": "rss",
            "endpoint": "https://example.com/secondary.xml",
            "is_active": True,
        },
    )
    assert source_resp.status_code == 201

    proxy_resp = client.post(
        f"/api/workspaces/{workspace}/proxies",
        json={
            "name": "Secondary Proxy",
            "protocol": "https",
            "address": "https://proxy.example:8443",
            "is_active": True,
        },
    )
    assert proxy_resp.status_code == 201

    channel_resp = client.post(
        f"/api/workspaces/{workspace}/telegram-channels",
        json={
            "name": "Updates Channel",
            "chat_id": "@updates_channel",
            "is_active": True,
        },
    )
    assert channel_resp.status_code == 201

    trigger = client.post(f"/api/workspaces/{workspace}/pipeline/trigger")
    assert trigger.status_code == 202
    run = _wait_for_pipeline_completion(client, workspace)
    assert run["status"] == "success"

    dashboard = client.get(f"/api/workspaces/{workspace}/dashboard")
    assert dashboard.status_code == 200
    payload = dashboard.json()

    assert payload["workspace"] == workspace
    counts = payload["counts"]
    assert counts["sources"] == 1
    assert counts["proxies"] == 1
    assert counts["telegram_channels"] == 1
    assert counts["pipeline_runs"] >= 1

    assert payload["sources"][0]["name"] == "Secondary Feed"
    assert payload["proxies"][0]["name"] == "Secondary Proxy"
    assert payload["telegram_channels"][0]["name"] == "Updates Channel"
    assert payload["pipeline_runs"][0]["id"] == run["id"]
