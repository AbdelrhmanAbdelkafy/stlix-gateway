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


def test_metrics_html_view():
    r = client.get("/metrics?format=html")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "By route" in r.text
    # raw JSON snapshot kept inside the HTML page
    assert "requests_total" in r.text


def test_metrics_default_is_prometheus_for_scrapers():
    # Accept */* (curl/scraper) must NOT get HTML
    r = client.get("/metrics", headers={"Accept": "*/*"})
    assert "text/plain" in r.headers["content-type"]
    assert "gateway_requests_total" in r.text


def test_api_keys_property_merges_single_and_list():
    s = Settings(gateway_api_key="k1", gateway_api_keys="k2, k3")
    assert s.api_keys == {"k1", "k2", "k3"}


def _req(method: str = "GET"):
    """Minimal ASGI scope — require_api_key only reads request.method."""
    from starlette.requests import Request

    return Request({"type": "http", "method": method, "headers": [], "path": "/"})


def test_require_api_key_accepts_any_configured_key():
    import fastapi

    s = Settings(gateway_api_keys="a,b")
    # valid key -> no raise
    require_api_key(_req(), x_api_key="b", settings=s)
    # invalid -> 401
    try:
        require_api_key(_req(), x_api_key="zzz", settings=s)
        assert False, "expected 401"
    except fastapi.HTTPException as exc:
        assert exc.status_code == 401


def test_browser_cookie_is_read_only():
    """The cookie lets a plain <a> into /api/v1/*; it must never allow a write."""
    import fastapi

    s = Settings(gateway_api_keys="a,b")
    require_api_key(_req("GET"), sg_key="a", settings=s)      # navigation: fine
    try:
        require_api_key(_req("POST"), sg_key="a", settings=s)  # write: never
        assert False, "expected 401 — a cookie must not authorise a write"
    except fastapi.HTTPException as exc:
        assert exc.status_code == 401
