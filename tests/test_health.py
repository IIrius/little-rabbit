from __future__ import annotations


async def test_health_endpoint(async_client) -> None:
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_metrics_endpoint_returns_prometheus_payload(async_client) -> None:
    response = await async_client.get("/api/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "python_info" in response.text
