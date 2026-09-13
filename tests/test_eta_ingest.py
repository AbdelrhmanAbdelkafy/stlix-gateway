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


# --- the portal's own document grid -------------------------------------------------
ETA_HEADERS = ["ID / Internal ID", "Date Time Received", "Type / Version",
               "Total Value (EGP)", "Issuer (From)", "Receiver (To)", "Submission", "Status"]
ETA_ROW = ["CKP4XT3J92A2M4G1VNKXWZ1M10 FA2609-4002", "8/9/2026 9:57 AM", "Invoice 1.0",
           "2,736.00", "المجموعه المصريه لتشكيل المعادن 504685740",
           "شركة العميل 205168604", "WMV92BHFKDY9KQHCVNKXWZ1M10", "Valid"]


def test_the_grid_splits_the_cells_that_hold_two_facts():
    from app.integrations.eta.ingest import map_grid
    row = map_grid(ETA_HEADERS, [ETA_ROW], "504685740")[0]
    assert row["uuid"] == "CKP4XT3J92A2M4G1VNKXWZ1M10"
    assert row["internal_id"] == "FA2609-4002"
    assert row["issuer_id"] == "504685740" and row["receiver_id"] == "205168604"
    assert row["issuer_name"].startswith("المجموعه")
    assert row["doc_type"] == "Invoice"
    assert row["total"] == "2,736.00"


def test_our_own_registration_number_is_what_says_sale_or_purchase():
    from app.integrations.eta.ingest import map_grid
    assert map_grid(ETA_HEADERS, [ETA_ROW], "504685740")[0]["direction"] == "Sent"
    assert map_grid(ETA_HEADERS, [ETA_ROW], "205168604")[0]["direction"] == "Received"
    # An entity we are neither side of: better unset than guessed.
    assert "direction" not in map_grid(ETA_HEADERS, [ETA_ROW], "999999999")[0]


def test_the_portal_writes_the_day_first_and_a_twelve_hour_clock():
    from app.integrations.eta.ingest import _iso, normalise, map_grid
    assert _iso("8/9/2026 9:57 AM") == "2026-09-08T09:57:00Z"      # 8 September, not 9 August
    assert _iso("8/9/2026 2:05 PM") == "2026-09-08T14:05:00Z"
    doc = normalise(map_grid(ETA_HEADERS, [ETA_ROW], "504685740")[0])
    assert doc["dateTimeIssued"].startswith("2026-09-08")
    assert doc["total"] == 2736.0
    assert "vat" not in doc           # the list shows no VAT — it must not invent one


def test_a_grid_with_unreadable_headers_falls_back_to_the_known_order():
    from app.integrations.eta.ingest import map_grid
    row = map_grid([], [ETA_ROW], "504685740")[0]
    assert row["internal_id"] == "FA2609-4002" and row["direction"] == "Sent"


def test_the_agent_may_post_what_it_read_but_may_not_read_anything_back():
    """The browser agent has no session, only its own key — so the ingest path
    has to pass the login middleware. Nothing else under /api/v1/eta does."""
    from app.auth.resources import is_public
    assert is_public("/api/v1/eta/group/ingest")
    assert is_public("/api/v1/eta/group/ingest?source=browser")
    for guarded in ("/api/v1/eta/group/documents", "/api/v1/eta/group/ingest/x",
                    "/api/v1/eta", "/api/v1/eta/group/../../auth/admin/users"):
        assert not is_public(guarded), guarded


def test_an_icon_in_the_status_cell_does_not_make_a_valid_invoice_unknown():
    """The portal renders "<icon> Valid" in one cell. Read literally that is not
    "valid", and the whole month silently drops out of the plan."""
    from app.integrations.eta.ingest import _status, clean
    assert _status(" Valid") == "valid"
    assert _status(" Invalid") == "invalid"      # longest name wins
    assert _status(" ملغاة") == "cancelled"
    assert clean(" 18 09732108260") == "18 09732108260"


def test_a_total_without_a_net_is_backed_out_not_read_as_zero():
    """The list shows one money column, tax included. Zero would erase the month."""
    from app.integrations.vat.engine import _net_or_estimate, _vat_or_estimate
    doc = {"total": 11400.0, "net": None, "vat": None, "vat_known": 0}
    assert _net_or_estimate(doc) == 10000.0
    assert _vat_or_estimate(doc) == 1400.0
    # a figure the portal actually printed is never second-guessed
    known = {"total": 11400.0, "net": 10000.0, "vat": 1234.0, "vat_known": 1}
    assert _vat_or_estimate(known) == 1234.0
