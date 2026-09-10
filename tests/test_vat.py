"""ض.ق.م planner: the arithmetic, the slots, the procedure — against a fake portal."""
from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import config

ENTITIES = [
    {"key": "group", "name": "المجموعة", "rin": "100", "client_id": "cid", "client_secret": "sec",
     "k_manufacturing": 7, "k_trading": 1, "customs_issuer_ids": ["CUSTOMS"]},
    {"key": "stlix", "name": "ستليكس", "rin": "200", "client_id": "", "client_secret": "",
     "k_manufacturing": 4, "k_trading": 1},
]
GW = {"X-API-Key": "gw-key-123456"}
M = "2026-08"


def _doc(uuid, direction, net, day, status="Valid", typ="I", issuer="SUP", receiver="CUST", internal="INV"):
    return {"uuid": uuid, "internalId": f"{internal}-{uuid}", "typeName": typ, "status": status,
            "issuerId": issuer, "issuerName": issuer, "receiverId": receiver, "receiverName": receiver,
            "dateTimeIssued": f"{M}-{day:02d}T10:00:00Z", "dateTimeReceived": f"{M}-{day:02d}T11:00:00Z",
            "totalSales": net, "netAmount": net, "total": round(net * 1.14, 2), "direction": direction}


# a month: 1,000,000 sales (700k manufacturing item M1, 300k trading), 500k purchases so far,
# one cancelled sale, one customs doc, no credit
PORTAL = {
    "Sent": [_doc("s1", "Sent", 700000, 5), _doc("s2", "Sent", 300000, 12), _doc("s3", "Sent", 50000, 20, "Cancelled")],
    "Received": [_doc("p1", "Received", 300000, 2), _doc("p2", "Received", 200000, 15),
                 _doc("i1", "Received", 100000, 9, issuer="CUSTOMS")],
}
DETAILS = {
    "s1": {"document": {"invoiceLines": [{"itemCode": "EG-M1", "internalCode": "M1", "netTotal": 700000,
                                          "taxableItems": [{"taxType": "T1", "amount": 98000}]}],
                        "taxTotals": [{"taxType": "T1", "amount": 98000}]}},
    "s2": {"document": {"invoiceLines": [{"itemCode": "EG-T9", "internalCode": "T9", "netTotal": 300000,
                                          "taxableItems": [{"taxType": "T1", "amount": 42000}]}],
                        "taxTotals": [{"taxType": "T1", "amount": 42000}]}},
}


class FakeEta:
    def __init__(self, entity, env):
        self.entity = entity

    async def search(self, client, *, issue_from, issue_to, direction=None, status=None, page_size=100):
        return [dict(d) for d in PORTAL.get(direction, [])]

    async def details(self, client, uuid):
        if uuid in DETAILS:
            return DETAILS[uuid]
        d = next(x for v in PORTAL.values() for x in v if x["uuid"] == uuid)
        return {"document": {"invoiceLines": [], "taxTotals": [{"taxType": "T1", "amount": round(d["netAmount"] * 0.14, 2)}]}}


@pytest.fixture
def vat(tmp_path, monkeypatch):
    monkeypatch.setenv("ETA_ENTITIES_JSON", json.dumps(ENTITIES))
    monkeypatch.setenv("ETA_DB_PATH", str(tmp_path / "eta.db"))
    monkeypatch.setenv("VAT_DB_PATH", str(tmp_path / "vat.db"))
    monkeypatch.setenv("GATEWAY_API_KEY", "gw-key-123456")
    monkeypatch.setenv("APP_ENV", "test")
    config.get_settings.cache_clear()
    from app.integrations.eta import store as eta_store
    from app.integrations.vat import engine
    monkeypatch.setattr(engine, "CODES_FILE", tmp_path / "codes.json")
    engine.save_manufacturing_codes(["M1"])
    real_sync = eta_store.sync

    async def fake_sync(entity_key, month, settings=None, with_details=True, client_factory=None):
        return await real_sync(entity_key, month, settings, with_details, client_factory=FakeEta)
    monkeypatch.setattr(eta_store, "sync", fake_sync)
    monkeypatch.setattr(engine, "date", _FrozenDate)
    from app.main import create_app
    yield TestClient(create_app())
    config.get_settings.cache_clear()


class _FrozenDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 8, 18)


def test_unsynced_month_is_honest(vat):
    p = vat.get(f"/api/v1/vat/group/{M}", headers=GW).json()
    assert not p["synced"] and p["action"] == "none" and p["documents"] == 0


def test_sync_then_the_gap_is_the_owners_formula(vat):
    r = vat.post(f"/api/v1/vat/group/{M}/sync", headers=GW)
    assert r.status_code == 200 and r.json()["documents"] == 6, r.text
    p = vat.get(f"/api/v1/vat/group/{M}", headers=GW).json()
    assert p["synced"] and p["sales"]["net"] == 1_000_000 and p["sales"]["count"] == 2   # cancelled one excluded
    assert p["sales"]["net_m"] == 700_000 and p["sales"]["net_t"] == 300_000
    assert p["sales"]["vat"] == 140_000
    assert p["purchases"]["net"] == 500_000 and p["purchases"]["vat"] == 70_000
    assert p["imports"]["vat"] == 14_000 and p["imports"]["portal_docs"] == 1
    # k_total = 8‰ of 1,000,000 = 8,000 to pay
    assert p["target_payable"] == 8_000
    # need 140,000 − 14,000 − 0 − 8,000 = 118,000 of purchase VAT; have 70,000 → gap 48,000 VAT = 342,857 base
    assert p["purchases_vat_needed"] == 118_000 and p["gap_vat"] == 48_000
    assert p["gap_base"] == pytest.approx(342_857.14, abs=0.01)
    assert p["action"] == "buy" and "342,857" in p["headline"]
    assert p["payable_now"] == 140_000 - 70_000 - 14_000
    assert [x["internal_id"] for x in p["problems"]] == ["INV-s3"]


def test_per_activity_mode_uses_each_k_on_its_own_sales(vat, monkeypatch):
    vat.post(f"/api/v1/vat/group/{M}/sync", headers=GW)
    monkeypatch.setenv("VAT_K_MODE", "per_activity")
    config.get_settings.cache_clear()
    p = vat.get(f"/api/v1/vat/group/{M}", headers=GW).json()
    assert p["target_payable"] == 7 * 700_000 / 1000 + 1 * 300_000 / 1000  # 5,200


def test_credit_and_manual_import_shrink_the_gap(vat):
    vat.post(f"/api/v1/vat/group/{M}/sync", headers=GW)
    vat.patch(f"/api/v1/vat/group/{M}", json={"credit_in": 20_000}, headers=GW)
    r = vat.post(f"/api/v1/vat/group/{M}/imports", json={"vat": 28_000, "release_no": "REL-7"}, headers=GW)
    assert r.status_code == 200 and r.json()["base"] == 200_000
    p = vat.get(f"/api/v1/vat/group/{M}", headers=GW).json()
    assert p["imports"]["vat"] == 42_000 and p["credit_in"] == 20_000
    assert p["gap_vat"] == 140_000 - 42_000 - 20_000 - 8_000 - 70_000  # 0 → exactly right
    assert p["action"] == "ok"
    vat.post(f"/api/v1/vat/group/{M}/imports", json={"vat": 50_000}, headers=GW)
    p = vat.get(f"/api/v1/vat/group/{M}", headers=GW).json()
    assert p["action"] == "surplus" and p["gap_vat"] == -50_000


def test_slots_follow_the_rules(vat):
    vat.post(f"/api/v1/vat/group/{M}/sync", headers=GW)
    p = vat.get(f"/api/v1/vat/group/{M}", headers=GW).json()
    days = [s["day"] for s in p["slots"]]
    assert days == [7, 14, 21, 28]                   # imports exist → no day-1 slot
    by = {s["day"]: s for s in p["slots"]}
    assert by[14]["covered"] and not by[7]["covered"] and by[7]["past"] and not by[28]["past"]
    assert p["per_slot_base"] == pytest.approx(342_857.14 / 2, abs=0.01)   # 21 and 28 remain
    # no imports and no credit → day-1 slot appears
    from app.integrations.vat.engine import schedule
    s = schedule(M, date(2026, 8, 18), has_imports=False, credit_in=0, purchase_days=[1, 30])
    assert s[0]["day"] == 1 and s[0]["covered"]
    assert not any(x["covered"] for x in s[1:])       # the 30th never counts


def test_procedure_states_and_draft_match(vat):
    vat.post(f"/api/v1/vat/group/{M}/sync", headers=GW)
    for st in ("closing", "packaged", "draft_review"):
        assert vat.patch(f"/api/v1/vat/group/{M}", json={"status": st}, headers=GW).json()["status"] == st
    assert vat.patch(f"/api/v1/vat/group/{M}", json={"status": "flying"}, headers=GW).status_code == 400
    bad = vat.post(f"/api/v1/vat/group/{M}/draft", json={"sales_vat": 140_000, "purchases_vat": 70_000,
                                                       "imports_vat": 0, "credit_in": 0, "payable": 70_000}, headers=GW).json()
    assert not bad["match"] and next(r for r in bad["rows"] if r["field"] == "imports_vat")["diff"] == -14_000
    assert vat.get(f"/api/v1/vat/group/{M}", headers=GW).json()["status"] == "draft_review"
    good = vat.post(f"/api/v1/vat/group/{M}/draft", json={"sales_vat": 140_000, "purchases_vat": 70_000,
                                                        "imports_vat": 14_000, "credit_in": 0, "payable": 56_000}, headers=GW).json()
    assert good["match"]
    assert vat.get(f"/api/v1/vat/group/{M}", headers=GW).json()["status"] == "ready_to_pay"
    vat.patch(f"/api/v1/vat/group/{M}", json={"status": "paid", "paid_amount": 56_000, "receipt": "R-1"}, headers=GW)
    vat.patch(f"/api/v1/vat/group/{M}", json={"status": "closed", "credit_out": 0}, headers=GW)
    log = vat.get("/api/v1/vat/log?entity=group", headers=GW).json()["log"]
    assert log[0]["action"] == "month.update" and any(l["action"] == "import.add" for l in log) is False


def test_credit_out_carries_into_next_month(vat):
    vat.patch(f"/api/v1/vat/group/{M}", json={"status": "closed", "credit_out": 12_345}, headers=GW)
    p = vat.get("/api/v1/vat/group/2026-09", headers=GW).json()
    assert p["credit_in"] == 12_345


def test_cancellation_shows_up_on_resync(vat, monkeypatch):
    vat.post(f"/api/v1/vat/group/{M}/sync", headers=GW)
    PORTAL["Received"][0]["status"] = "Cancelled"
    try:
        vat.post(f"/api/v1/vat/group/{M}/sync", headers=GW)
        p = vat.get(f"/api/v1/vat/group/{M}", headers=GW).json()
        assert p["purchases"]["vat"] == 28_000 and any(x["uuid"] == "p1" for x in p["problems"])
    finally:
        PORTAL["Received"][0]["status"] = "Valid"


def test_unconfigured_entity_cannot_sync_but_still_reads(vat):
    assert vat.post(f"/api/v1/vat/stlix/{M}/sync", headers=GW).status_code == 503
    assert vat.get(f"/api/v1/vat/stlix/{M}", headers=GW).status_code == 200
    assert vat.get(f"/api/v1/vat/nope/{M}", headers=GW).status_code == 404
    assert vat.get("/api/v1/vat/group/2026-8", headers=GW).status_code == 400


def test_overview_package_csv_and_page(vat):
    vat.post(f"/api/v1/vat/group/{M}/sync", headers=GW)
    ov = vat.get("/api/v1/vat", headers=GW).json()
    assert {i["entity"] for i in ov["items"]} == {"group", "stlix"} and not ov["configured"]
    pk = vat.get(f"/api/v1/vat/group/{M}/package", headers=GW).json()
    assert pk["figures"]["payable"] == 56_000 and pk["figures"]["sales_manufacturing_net"] == 700_000
    csv_ = vat.get(f"/api/v1/vat/group/{M}/package.csv", headers=GW)
    assert csv_.status_code == 200 and "INV-s1" in csv_.text and csv_.text.count("\n") >= 6
    page = vat.get("/tools/vat", headers=GW)
    assert page.status_code == 200 and "/api/v1/vat" in page.text


def test_vat_card_guards_its_paths():
    from app.auth.resources import BY_KEY, resource_for_path
    assert BY_KEY["vat"].live_key == "vat"
    assert resource_for_path("/api/v1/vat/group/2026-08/sync") == "vat" and resource_for_path("/tools/vat") == "vat"


# --- the watcher: the part that runs with nobody asking ---------------------------
def test_sweep_syncs_and_raises_the_alerts_a_person_used_to_remember(vat):
    import asyncio
    from app.integrations.vat import watcher
    out = asyncio.run(watcher.sweep(config.get_settings(), today=date(2026, 8, 18)))
    kinds = {a["kind"] for a in watcher.alerts()}
    assert out["ok"] and any(m["entity"] == "group" and m["month"] == M for m in out["months"])
    assert "gap" in kinds and "slot_missed" in kinds and "problems" in kinds
    gap = next(a for a in watcher.alerts() if a["kind"] == "gap" and a["entity"] == "group")
    assert "342,857" in gap["text"] and gap["amount"] == pytest.approx(342857.14, abs=0.01)
    # the unconfigured entity is not silently reported as fine
    assert any(a["kind"] == "not_synced" and a["entity"] == "stlix" for a in watcher.alerts())
    # same day, same fact -> filed once
    before = len(watcher.alerts(limit=200))
    asyncio.run(watcher.sweep(config.get_settings(), today=date(2026, 8, 18)))
    assert len(watcher.alerts(limit=200)) == before


def test_deadline_and_recheck_alerts_depend_on_the_calendar(vat):
    from app.integrations.vat import engine as eng, watcher
    vat.post(f"/api/v1/vat/group/{M}/sync", headers=GW)
    e = __import__("app.integrations.eta.store", fromlist=["x"]).entity("group", config.get_settings())
    kinds = lambda d: {a["kind"] for a in watcher.review(eng.plan(e, M, config.get_settings(), d), d)}
    assert "recheck" not in kinds(date(2026, 8, 18)) and "deadline" not in kinds(date(2026, 8, 18))
    mid = kinds(date(2026, 9, 8))
    assert {"month_over", "recheck"} <= mid
    assert "deadline" in kinds(date(2026, 9, 26))
    # a paid month stops nagging about the deadline
    vat.patch(f"/api/v1/vat/group/{M}", json={"status": "paid", "paid_amount": 1}, headers=GW)
    assert "deadline" not in kinds(date(2026, 9, 26))


def test_alerts_endpoint_and_seen_flag(vat):
    import asyncio
    from app.integrations.vat import watcher
    asyncio.run(watcher.sweep(config.get_settings(), today=date(2026, 8, 18)))
    r = vat.get("/api/v1/vat/alerts?entity=group", headers=GW).json()
    assert r["count"] and all(a["entity"] == "group" for a in r["alerts"])
    ids = [a["id"] for a in r["alerts"][:2]]
    assert vat.post("/api/v1/vat/alerts/seen", json={"ids": ids}, headers=GW).json()["updated"] == 2
    assert all(a["id"] not in ids for a in vat.get("/api/v1/vat/alerts?unseen=true", headers=GW).json()["alerts"])


def test_months_in_play_drops_a_closed_month(vat):
    from app.integrations.vat import store as vstore, watcher
    s = config.get_settings()
    assert watcher.months_in_play(s, "group", date(2026, 9, 3)) == ["2026-09", "2026-08"]
    vstore.save_month("group", "2026-08", status="closed")
    assert watcher.months_in_play(s, "group", date(2026, 9, 3)) == ["2026-09"]
