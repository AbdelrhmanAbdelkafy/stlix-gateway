"""Documents read off the portal by a browser, not by an API key.

The scraper's output is messy by nature — Arabic statuses, thousands
separators, two date shapes, missing VAT columns, rows scraped twice. These
tests pin what the gateway is allowed to do with that: normalise it, refuse
what it cannot place, and never invent a figure the page did not show.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import config

ENT = [{"key": "group", "name": "المجموعة", "rin": "100", "k_manufacturing": 7, "k_trading": 1}]
GW = {"X-API-Key": "gw-key-123456"}
AGENT = {"X-ETA-Browser-Key": "browser-secret-1"}
M = "2026-08"


@pytest.fixture
def gw(tmp_path, monkeypatch):
    monkeypatch.setenv("ETA_ENTITIES_JSON", json.dumps(ENT))
    monkeypatch.setenv("ETA_DB_PATH", str(tmp_path / "eta.db"))
    monkeypatch.setenv("VAT_DB_PATH", str(tmp_path / "vat.db"))
    monkeypatch.setenv("ETA_BROWSER_KEY", "browser-secret-1")
    monkeypatch.setenv("GATEWAY_API_KEY", "gw-key-123456")
    monkeypatch.setenv("APP_ENV", "test")
    config.get_settings.cache_clear()
    from app.integrations.vat import engine
    monkeypatch.setattr(engine, "CODES_FILE", tmp_path / "codes.json")
    from app.main import create_app
    yield TestClient(create_app())
    config.get_settings.cache_clear()


ROWS = [
    # as the sales page renders it: Arabic status, separators, day-first date
    {"internal_id": "INV-1001", "direction": "مرسلة", "status": "صالحة", "doc_type": "فاتورة",
     "date": "05-08-2026 10:15", "receiver_name": "عميل ١", "receiver_id": "555",
     "net": "700,000.00", "vat": "98,000.00", "total": "798,000.00"},
    # a purchases row with no VAT column at all
    {"internal_id": "PUR-77", "direction": "Received", "status": "Valid",
     "issued_at": "2026-08-15T09:00:00", "issuer_name": "مورد", "net": "200000", "total": "228000"},
    # cancelled, and dated the other way round
    {"internal_id": "INV-1002", "direction": "Sent", "status": "ملغاة", "date": "2026/08/20",
     "net": "50,000", "total": "57,000", "reason": "بيانات غلط"},
]


def test_scraped_rows_become_documents_the_planner_can_read(gw):
    r = gw.post(f"/api/v1/eta/group/ingest", json={"documents": ROWS}, headers=AGENT)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["stored"] == 3 and out["months"] == [M] and out["skipped_count"] == 0
    docs = {d["internal_id"]: d for d in gw.get(f"/api/v1/vat/group/{M}/documents", headers=GW).json()["documents"]}
    assert docs["INV-1001"]["direction"] == "Sent" and docs["INV-1001"]["status"] == "valid"
    assert docs["INV-1001"]["net"] == 700000 and docs["INV-1001"]["vat"] == 98000
    assert docs["INV-1001"]["vat_known"] == 1
    assert docs["PUR-77"]["direction"] == "Received" and docs["PUR-77"]["vat_known"] == 0
    assert docs["INV-1002"]["status"] == "cancelled" and docs["INV-1002"]["reason"] == "بيانات غلط"
    p = gw.get(f"/api/v1/vat/group/{M}", headers=GW).json()
    assert p["synced"] and p["sales"]["net"] == 700_000        # the cancelled one is out
    assert p["purchases"]["net"] == 200_000
    # the purchase VAT was never on the page: estimated from net+total, not zeroed
    assert p["purchases"]["vat"] == 28_000
    assert [x["internal_id"] for x in p["problems"]] == ["INV-1002"]


def test_rescraping_updates_instead_of_duplicating(gw):
    gw.post(f"/api/v1/eta/group/ingest", json={"documents": ROWS}, headers=AGENT)
    changed = [dict(ROWS[0], status="ملغاة")]
    gw.post(f"/api/v1/eta/group/ingest", json={"documents": changed + ROWS[1:]}, headers=AGENT)
    docs = gw.get(f"/api/v1/vat/group/{M}/documents", headers=GW).json()
    assert docs["count"] == 3, "the same rows must not pile up"
    assert next(d for d in docs["documents"] if d["internal_id"] == "INV-1001")["status"] == "cancelled"


def test_a_row_with_no_usable_date_is_refused_not_misfiled(gw):
    r = gw.post(f"/api/v1/eta/group/ingest",
                json={"documents": [{"internal_id": "X-1", "direction": "Sent", "net": "10"}]}, headers=AGENT)
    assert r.json() == {"ok": True, "stored": 0, "months": [], "skipped": ["X-1"],
                        "skipped_count": 1, "source": "browser"}


def test_the_browser_key_only_opens_the_ingest_door(gw):
    assert gw.post(f"/api/v1/eta/group/ingest", json={"documents": []}).status_code == 401
    assert gw.post(f"/api/v1/eta/group/ingest", json={"documents": []},
                   headers={"X-ETA-Browser-Key": "nope"}).status_code == 401
    assert gw.get("/api/v1/vat", headers=AGENT).status_code == 401
    assert gw.get(f"/api/v1/vat/group/{M}/documents", headers=AGENT).status_code == 401
    assert gw.post("/api/v1/eta/nope/ingest", json={"documents": []}, headers=AGENT).status_code == 404
    assert gw.post(f"/api/v1/eta/group/ingest", json={"documents": "x"}, headers=AGENT).status_code == 400


def test_number_and_status_parsing():
    from app.integrations.eta.ingest import normalise, num
    assert num("1,234.50 EGP") == 1234.5 and num("") is None and num(None) is None and num(7) == 7.0
    # the portal is an Arabic site and does render Arabic-Indic numerals
    assert num("١٢٣") == 123.0 and num("١٬٢٣٤٫٥") == 1234.5
    d = normalise({"internal_id": "A", "direction": "Sent", "status": "مرفوضة",
                   "date": "2026-08-01", "total": "1,140", "vat": "140"})
    assert d["status"] == "rejected" and d["netAmount"] == 1000.0 and d["typeName"] == "I"
    # no vat column -> the key is absent, so the store keeps vat_known = 0
    assert "vat" not in normalise({"internal_id": "B", "direction": "Sent", "date": "2026-08-01",
                                   "net": "100", "total": "114"})


def test_the_same_document_keeps_its_id_across_scrapes():
    from app.integrations.eta.ingest import normalise
    row = {"internal_id": "INV-9", "direction": "Sent", "date": "2026-08-09", "total": "1,000"}
    assert normalise(row)["uuid"] == normalise(dict(row, status="ملغاة"))["uuid"]
    assert normalise(row)["uuid"] != normalise(dict(row, internal_id="INV-10"))["uuid"]
    # a real uuid from the page always wins over the synthetic one
    assert normalise(dict(row, uuid="abc-123"))["uuid"] == "abc-123"
