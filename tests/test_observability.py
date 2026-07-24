"""Layer 6: logging/monitoring/security behaviour."""
from fastapi.testclient import TestClient

from app.config import Settings
from app.core.security import require_api_key
from app.main import app

client = TestClient(app)


def test_request_id_and_timing_headers():
    r = client.get("/systems")
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID")
    assert r.headers.get("X-Response-Time-ms")


def test_security_headers_present():
    r = client.get("/systems")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_metrics_prometheus_and_json():
    client.get("/systems")  # generate at least one data point
    prom = client.get("/metrics")
    assert prom.status_code == 200
    assert "gateway_requests_total" in prom.text

    js = client.get("/metrics?format=json")
    assert js.status_code == 200
    body = js.json()
    assert body["requests_total"] >= 1
    assert "by_status_class" in body


def test_api_keys_property_merges_single_and_list():
    s = Settings(gateway_api_key="k1", gateway_api_keys="k2, k3")
    assert s.api_keys == {"k1", "k2", "k3"}


def test_require_api_key_accepts_any_configured_key():
    import fastapi

    s = Settings(gateway_api_keys="a,b")
    # valid key -> no raise
    require_api_key(x_api_key="b", settings=s)
    # invalid -> 401
    try:
        require_api_key(x_api_key="zzz", settings=s)
        assert False, "expected 401"
    except fastapi.HTTPException as exc:
        assert exc.status_code == 401
