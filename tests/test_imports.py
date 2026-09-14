"""الاستيراد والشحن — the arithmetic and the gates, without a server.

What these hold in place, in order of what it costs when it breaks:

* **The ACID walk.** One transposed digit between نافذة and the supplier's
  invoice stops the container in the port. The check must name the position,
  not just say "no match", and it must not pass a file where no document has
  been looked at yet.
* **The free-time countdown.** It decides when an alert fires, so it is tested
  against fixed dates rather than `today`.
* **No invented rate.** With no demurrage tariff entered, the estimate is
  `None` and says so. A default tariff here would be a number somebody would
  later put in an email to a shipping line.
* **The procedure is the document.** Every step keeps an owner and a checkpoint,
  and the two SOPs keep their step counts — a step quietly dropped from the code
  is a step that stops being done.
"""
from datetime import date
from types import SimpleNamespace

import pytest

from app.integrations.imports import engine, nama_link, sop, store

TODAY = date(2026, 9, 13)
ACID = "1" * 19


@pytest.fixture
def db(tmp_path):
    return SimpleNamespace(imports_db_path=str(tmp_path / "imports.db"))


def _docs(**acids):
    return [{"kind": k, "acid_on_doc": v, "received": 1} for k, v in acids.items()]


# --- the procedure -----------------------------------------------------------
def test_both_sops_are_complete():
    assert len(sop.IMPORT_STEPS) == 28, "SOP-IMP-001 فيه 28 خطوة"
    assert len(sop.BL_STEPS) == 18, "SOP-IMP-002 فيه 18 خطوة"
    assert len(sop.BL_CHECKLIST) == 12, "checklist مسودة البوليصة 12 بند"
    assert {s.no for s in sop.IMPORT_STEPS} == set(range(1, 29))
    assert {s.no for s in sop.BL_STEPS} == set(range(1, 19))


def test_every_step_names_an_owner_and_a_checkpoint():
    """The SOP's own two columns. A step without them is not auditable."""
    naked = [f"{s.sop}#{s.no}" for s in sop.ALL_STEPS if not s.owner.strip() or not s.check.strip()]
    assert not naked, f"خطوات من غير مسؤول أو نقطة تحقق: {naked}"


def test_every_auto_rule_has_a_reason_sentence():
    """A step that stays open must be able to say why, in words the owner can act on."""
    ev = engine._evidence({}, [], [], {}, engine.acid_check({}, []),
                          engine.clock({}, [], TODAY), engine.landed({}, []))
    silent = [s.auto for s in sop.ALL_STEPS
              if s.auto and not s.auto.startswith("doc:") and not engine._why(s.auto, ev)]
    assert not silent, f"قواعد بدون جملة سبب: {silent}"


# --- ACID --------------------------------------------------------------------
def test_acid_must_be_nineteen_digits():
    assert engine.acid_valid(ACID)
    assert not engine.acid_valid("1" * 18)
    assert not engine.acid_valid("1" * 18 + "A")
    assert not engine.acid_valid(None)


def test_acid_mismatch_names_the_position():
    wrong = ACID[:6] + "2" + ACID[7:]
    out = engine.acid_check({"acid": ACID}, _docs(invoice=ACID, packing=wrong, bl_draft=ACID))
    assert not out["ok"]
    assert [m["kind"] for m in out["mismatches"]] == ["packing"]
    assert "خانة 7" in out["mismatches"][0]["detail"]


def test_acid_gate_does_not_pass_an_unexamined_file():
    """No mismatches because nothing has been checked is not a pass."""
    out = engine.acid_check({"acid": ACID}, _docs(invoice=ACID))
    assert not out["ok"] and not out["mismatches"]


def test_acid_gate_passes_once_three_documents_agree():
    out = engine.acid_check({"acid": ACID}, _docs(invoice=ACID, packing=ACID, bl_draft=ACID))
    assert out["ok"]


# --- free time ---------------------------------------------------------------
def test_free_time_counts_from_arrival():
    c = engine.clock({"eta": "2026-09-10", "free_days": 7}, [], TODAY)
    assert c["free_time_end"] == "2026-09-17"
    assert c["days_left"] == 4
    assert c["state"] == "warn"          # inside the SOP's 5-day warning
    assert c["overdue_days"] == 0


def test_free_time_overdue_counts_to_today_until_release():
    c = engine.clock({"eta": "2026-08-20", "free_days": 7}, [], TODAY)
    assert c["overdue_days"] == (date(2026, 9, 13) - date(2026, 8, 27)).days == 17
    assert c["state"] == "overdue"


def test_free_time_stops_counting_at_release():
    c = engine.clock({"eta": "2026-08-20", "free_days": 7, "released_at": "2026-08-30"}, [], TODAY)
    assert c["overdue_days"] == 3 and c["state"] == "released"


def test_no_tariff_means_no_demurrage_figure():
    c = engine.clock({"eta": "2026-08-20", "free_days": 7, "containers": 2}, [], TODAY)
    assert c["demurrage_estimate"] is None
    assert "تعريفة الأرضيات مش متحطة" in c["demurrage_note"]


def test_demurrage_is_tiered_per_container_per_day():
    ship = {"eta": "2026-09-01", "free_days": 5, "containers": 2,
            "demurrage_tariff": [{"from": 1, "to": 3, "rate": 10}, {"from": 4, "rate": 20}]}
    c = engine.clock(ship, [], TODAY)          # free time ended 2026-09-06 → 7 days over
    assert c["overdue_days"] == 7
    # 3 days × 10 + 4 days × 20 = 110, per container, × 2
    assert c["demurrage_estimate"] == 220.0


def test_aci_deadline_is_two_days_before_sailing():
    c = engine.clock({"etd": "2026-09-20"}, [], TODAY)
    assert c["aci_deadline"] == "2026-09-18"


# --- landed cost -------------------------------------------------------------
def test_landed_cost_needs_a_rate_before_it_converts():
    ship = {"currency": "USD", "value_fob": 100.0, "qty_ton": 2}
    assert engine.landed(ship, [])["cif"] is None
    assert engine.landed(dict(ship, fx_rate=50), [])["cif"] == 5000.0


def test_landed_cost_per_ton_and_tolerance():
    ship = {"currency": "EGP", "value_fob": 1000.0, "freight": 200.0, "insurance": 0,
            "qty_ton": 2, "est_landed_per_ton": 600.0}
    out = engine.landed(ship, [{"kind": "clearance", "amount": 200, "currency": "EGP",
                                "invoice_no": "A-1"}])
    assert out["cif"] == 1200.0 and out["total"] == 1400.0 and out["per_ton"] == 700.0
    assert out["diff_pct"] == pytest.approx(16.67, abs=0.01)
    assert out["within_tolerance"] is False


def test_a_cost_without_an_invoice_number_is_flagged_not_hidden():
    out = engine.landed({"value_fob": 10, "qty_ton": 1},
                        [{"id": 1, "kind": "clearance", "amount": 500, "currency": "EGP"}])
    assert [u["id"] for u in out["undocumented"]] == [1]
    assert out["ready"] is False


# --- steps, gates, alerts ----------------------------------------------------
def _plan(**over):
    ship = {"ref": "IMP-2026-001", "acid": ACID, "payment_term": "TT100", "bl_type": "telex",
            "eta": "2026-09-20", "free_days": 10, "qty_ton": 1, "currency": "EGP", **over}
    docs = _docs(invoice=ACID, packing=ACID, bl_draft=ACID)
    return engine.plan(ship, docs, [], [], {}, {}, TODAY)


def test_a_step_ticks_itself_from_evidence():
    p = _plan()
    acid_step = next(s for s in p["steps"] if s["sop"] == "IMP-001" and s["no"] == 9)
    assert acid_step["state"] == "done" and acid_step["source"] == "تلقائي"


def test_a_manual_tick_survives_the_engine():
    ship = {"ref": "X", "acid": "", "currency": "EGP"}
    saved = {("IMP-001", 9): {"state": "done", "who": "mo", "at": 0, "note": "بالإيد"}}
    p = engine.plan(ship, [], [], [], {}, saved, TODAY)
    s9 = next(s for s in p["steps"] if s["sop"] == "IMP-001" and s["no"] == 9)
    assert s9["state"] == "done" and s9["source"] == "يدوي"


def test_the_next_action_is_an_open_gate_with_an_owner():
    p = _plan()
    assert p["next"]["gate"] is True
    assert p["next"]["owner"] and p["next"]["why"]


def test_payment_term_and_bl_type_must_agree():
    """LC with a telex release is the control that protects the bank's security."""
    p = _plan(payment_term="LC", bl_type="telex")
    assert any(a["level"] == "critical" and "اعتماد مستندي" in a["text"] for a in p["alerts"])


def test_overdue_free_time_raises_a_critical_alert_with_an_action():
    p = _plan(eta="2026-08-01", free_days=7)
    a = next(a for a in p["alerts"] if "free time" in a["text"])
    assert a["level"] == "critical" and a["do"] and a["who"]


def test_every_alert_says_what_to_do_and_who_does_it():
    p = _plan(eta="2026-08-01", free_days=7, payment_term="LC", bl_type="telex")
    assert all(a["do"] and a["who"] for a in p["alerts"])


def test_progress_counts_only_the_steps_that_exist():
    p = _plan()
    assert p["progress"]["steps"] == len(sop.ALL_STEPS)
    assert 0 <= p["progress"]["pct"] <= 100


# --- the store ---------------------------------------------------------------
def test_reference_is_issued_not_typed(db):
    a = store.create({"supplier": "Foshan"}, settings=db)
    b = store.create({"supplier": "Foshan"}, settings=db)
    assert a["ref"].startswith("IMP-") and b["ref"] != a["ref"]
    assert int(b["ref"].rsplit("-", 1)[1]) == int(a["ref"].rsplit("-", 1)[1]) + 1


def test_unknown_fields_are_refused(db):
    ref = store.create({}, settings=db)["ref"]
    with pytest.raises(ValueError):
        store.update(ref, {"whatever": 1}, settings=db)


def test_every_change_lands_in_the_log(db):
    ref = store.create({"supplier": "A"}, who="mo", settings=db)["ref"]
    store.update(ref, {"acid": ACID}, who="mo", settings=db)
    store.set_step(ref, "IMP-001", 1, "done", who="mo", settings=db)
    actions = [r["action"] for r in store.log(ref, settings=db)]
    assert "shipment.create" in actions and "step" in actions


def test_costs_and_containers_round_trip(db):
    ref = store.create({}, settings=db)["ref"]
    store.add_cost(ref, "clearance", 100, invoice_no="INV-1", settings=db)
    store.add_container(ref, "MSKU1", deposit=500, settings=db)
    assert store.costs(ref, settings=db)[0]["invoice_no"] == "INV-1"
    assert store.containers(ref, settings=db)[0]["container_no"] == "MSKU1"


# --- Nama link ---------------------------------------------------------------
def test_nama_dates_are_read_in_namas_own_format():
    """Nama writes DD-MM-YYYY. Reading it as ISO turns 09-10-2026 into October."""
    m = nama_link.map_record({"code": "LCS-1", "estimatedArrivalDate": "09-10-2026",
                              "billOfLading": "BL-9", "commercialInvoiceValue": "1500.5",
                              "shippingLine": {"code": "MSC", "name1": "MSC"},
                              "portOfDischarge": {"name1": "الإسكندرية"}})
    assert m["eta"] == "2026-10-09"
    assert m["bl_no"] == "BL-9" and m["value_fob"] == 1500.5
    assert m["shipping_line"] == "MSC" and m["port_discharge"] == "الإسكندرية"


def test_nama_mapping_drops_nothing_it_cannot_read():
    m = nama_link.map_record({})
    assert set(m) <= set(store.NAMA_FIELDS)
    assert all(v is None for v in m.values())
