"""REP — العهدة والمستندات والحركة، وقد صارت داتاهم كنكتور.

The owner's requirement, verbatim in spirit: take custody, documents and
movement from `rep-system.html` and make *their data* the connector that top
management's reports are drawn from. So the properties these tests defend are
exactly those two clauses:

1. **Verbatim data** — what is served is what was in the original file, with
   the original author's own warnings still attached. The extraction was done
   by evaluating the file's arrays, not by retyping them; the tests here can't
   re-run that extraction, but they can pin the shape and the provenance so a
   later hand-edit that invents a record or drops a warning fails loudly.
2. **Reports are computed** — every figure in `/overview` must equal a sum or
   count over the records, never a number typed into the code. The tests
   recompute each one independently from the raw JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.integrations.rep import store
from app.main import app

client = TestClient(app)

RAW = json.loads(store.DATA.read_text(encoding="utf-8"))


# --- the store: verbatim data, provenance attached --------------------------

def test_data_file_lives_in_the_repo():
    """`data/rep/rep.json` ships with the platform — the Dockerfile copies
    `data/` and test_deploy checks that, but the store's own path must resolve
    inside the project root, not to an absolute path from some machine."""
    assert store.DATA.is_file()
    assert store.DATA == Path(store._ROOT) / "data" / "rep" / "rep.json"


def test_source_block_travels_with_every_unit():
    """Provenance is not documentation, it is payload: two datasets carry
    warnings written by REP's own author, and a consumer that never sees them
    will trust a placeholder distance or a hand-flagged opening balance."""
    for unit in (store.custody(), store.movement(), store.documents(),
                 store.overview()):
        src = unit["source"]
        assert src["file"] == "rep-system.html"
        assert len(src["warnings"]) >= 3


def test_the_original_files_own_caveats_survive():
    """The PLACES distances are declared placeholder in the original file, and
    E000155's opening equals the Nama figure the master runbook flags as false.
    Those two facts must be present as warnings — absorbing them would make
    the management report *more* confident than its own source."""
    text = " ".join(store.source()["warnings"])
    assert "افتراضية" in text          # PLACES distances are placeholders
    assert "D-04" in text              # opening cash is hand-counted, per rule
    assert "3,814,499" in text         # the specific flagged figure, named


def test_custody_matches_the_raw_records():
    c = store.custody()
    raw_holders = [p for p in RAW["people"] if p.get("holder")]
    assert [h["id"] for h in c["holders"]] == [p["id"] for p in raw_holders]
    assert c["opening_total"] == sum(p.get("open", 0) for p in raw_holders)
    assert len(c["vehicle_custody"]) == len(RAW["cars"])
    # orphan = the holder left the company but the vehicle is still his custody
    assert len(c["orphan_vehicles"]) == sum(1 for x in RAW["cars"] if x.get("gone"))


def test_movement_matches_the_raw_records():
    m = store.movement()
    raw_team = [p for p in RAW["people"] if p["dept"] == "الحركة"]
    assert [t["id"] for t in m["team"]] == [p["id"] for p in raw_team]
    assert m["drivers_without_mobile"] == [p["n"] for p in raw_team if not p.get("mob")]
    assert len(m["places"]) == len(RAW["places"])
    assert "افتراضية" in m["places_warning"]


def test_documents_are_the_seven_templates_verbatim():
    d = store.documents()
    assert d["count"] == len(RAW["doc_templates"]) == 7
    for t in d["templates"]:
        # every template carries its code prefix, its why-text and its fields —
        # the page builds the printable document from exactly these
        assert t["prefix"] and t["title"] and t["fields"]


def test_overview_is_computed_not_typed():
    """Recompute every figure independently; a hand-edit to overview() that
    types a number in place of a sum fails here."""
    o = store.overview()
    holders = [p for p in RAW["people"] if p.get("holder")]
    drivers = [p for p in RAW["people"] if p["dept"] == "الحركة"]
    assert o["custody"]["holders"] == len(holders)
    assert o["custody"]["opening_total"] == sum(p.get("open", 0) for p in holders)
    assert o["custody"]["vehicles_held"] == len(RAW["cars"])
    assert o["custody"]["orphan_vehicles"] == sum(1 for c in RAW["cars"] if c.get("gone"))
    assert o["movement"]["team"] == len(drivers)
    assert o["movement"]["drivers_without_mobile"] == sum(
        1 for p in drivers if not p.get("mob"))
    assert o["movement"]["fleet"] == len(RAW["cars"])
    assert o["movement"]["destinations"] == len(RAW["places"])
    assert o["documents"]["templates"] == len(RAW["doc_templates"])
    assert o["alert_count"] == len(o["alerts"])


def test_alerts_are_recomputed_from_records_not_copied_as_text():
    """REP's engine raised these alerts from its data; ours must derive from
    the same records. Each orphan car, each flagged person, each driver with
    no mobile produces exactly one alert; empty km readings produce one more."""
    o = store.overview()
    expected = (sum(1 for c in RAW["cars"] if c.get("gone"))
                + sum(1 for p in RAW["people"] if p.get("flag"))
                + sum(1 for p in RAW["people"]
                      if p["dept"] == "الحركة" and not p.get("mob"))
                + (1 if all(c.get("km") is None for c in RAW["cars"]) else 0))
    assert o["alert_count"] == expected
    assert all(a["level"] in ("bad", "warn") for a in o["alerts"])


def test_reload_reflects_a_changed_file(tmp_path, monkeypatch):
    """POST /reload exists so an updated rep.json is picked up without a
    restart — prove reset() actually rereads the disk."""
    doctored = dict(RAW)
    doctored["people"] = RAW["people"] + [dict(RAW["people"][0], id="E999999")]
    p = tmp_path / "rep.json"
    p.write_text(json.dumps(doctored, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(store, "DATA", p)
    try:
        assert len(store.reset()["people"]) == len(RAW["people"]) + 1
    finally:
        monkeypatch.undo()
        store.reset()


# --- the endpoints ----------------------------------------------------------

def test_status_names_what_is_adopted_and_what_is_not():
    """Three units are in; eight are still only in the original file. The
    status endpoint must say both — advertising REP as 'merged' while 8 of 11
    units live elsewhere is exactly the kind of overclaim the tour page's
    'not working' section exists to prevent."""
    r = client.get("/api/v1/rep")
    assert r.status_code == 200
    body = r.json()
    assert len(body["adopted_units"]) == 3
    assert len(body["remaining_units"]) == 8
    assert body["counts"]["people"] == len(RAW["people"])


def test_each_unit_endpoint_answers_with_its_source():
    for path in ("/api/v1/rep/custody", "/api/v1/rep/movement",
                 "/api/v1/rep/documents", "/api/v1/rep/overview"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.json()["source"]["file"] == "rep-system.html", path


def test_overview_html_view_renders_the_management_table():
    r = client.get("/api/v1/rep/overview", headers={"Accept": "text/html"})
    assert r.status_code == 200
    assert "تقرير الإدارة" in r.text


def test_ops_page_serves_without_the_original_files_secrets():
    """The original PWA carried a live sync key inside an alert's text and its
    author's passwords in prose. None of that crossed over: the page holds the
    gateway key placeholder only, and the served data contains no secret."""
    page = client.get("/tools/rep").text
    blob = page + json.dumps(store.load(), ensure_ascii=False)
    for secret in ("KELMETAK", "Nourhan@2026"):
        assert secret not in blob
    assert "/api/v1/rep" in page  # the page reads the connector, not its own copy


def test_rep_is_on_the_map_and_in_the_catalogue():
    systems = {s["key"]: s for s in client.get("/systems").json()["systems"]}
    assert systems["rep"]["status"] == "live"
    conns = {c["key"]: c for c in client.get("/connectors").json()["connectors"]}
    assert conns["rep"]["live"] is True
    assert "rep-system.html" in conns["rep"]["upstream"]
