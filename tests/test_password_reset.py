"""نسيت كلمة السر — the properties that make a reset flow safe rather than convenient.

Each of these is a way the feature could quietly become a liability:

* a reply that differs for a real account turns the endpoint into a way to
  discover usernames;
* a token stored in readable form turns the database into a set of live keys;
* a link that still works after it was used, or after a newer one was issued,
  means an old email is a permanent back door;
* a reset that leaves the old sessions alive defeats the main reason people
  reset — they think somebody else is in the account;
* mail that is not configured must fail *loudly*, or a person waits for a
  message nobody sent.
"""
import sqlite3
import time

import pytest

from app.auth import reset
from app.auth.store import AuthStore


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "auth.db"
    store = AuthStore(path)
    store.create_user("mo", "oldpassword1", display_name="MU", roles=["admin"], actor="test")
    store.create_user("sara", "oldpassword2", display_name="Sara", roles=["sales"], actor="test")
    reset.ensure(path)
    reset.set_email(path, "mo", "abdelrhman.abdelkafy@gmail.com")
    return path, store


# --- accounts and lookup ------------------------------------------------------
def test_lookup_by_username_or_email(db):
    path, _ = db
    assert reset.find_user(path, "mo") == "mo"
    assert reset.find_user(path, "ABDELRHMAN.ABDELKAFY@GMAIL.COM") == "mo"
    assert reset.find_user(path, "nobody") is None


def test_a_disabled_account_cannot_be_reset(db):
    path, store = db
    store.update_user("sara", active=False, actor="test")
    assert reset.find_user(path, "sara") is None


def test_a_bad_email_is_refused_rather_than_stored(db):
    path, _ = db
    with pytest.raises(ValueError):
        reset.set_email(path, "sara", "not-an-email")
    assert reset.get_email(path, "sara") == ""


def test_the_column_is_added_to_an_existing_database(tmp_path):
    """The VPS already has users in auth.db — the upgrade must not need a migration."""
    path = tmp_path / "auth.db"
    AuthStore(path).create_user("mo", "oldpassword1", actor="test")
    with sqlite3.connect(path) as c:
        assert "email" not in {r[1] for r in c.execute("PRAGMA table_info(users)")}
    reset.ensure(path)
    reset.ensure(path)  # idempotent
    with sqlite3.connect(path) as c:
        assert "email" in {r[1] for r in c.execute("PRAGMA table_info(users)")}


# --- tokens -------------------------------------------------------------------
def test_the_token_is_never_stored_in_readable_form(db):
    path, _ = db
    _id, token = reset.record(path, username="mo", system="hub", identifier="mo", ip="1.1.1.1",
                              with_token=True)
    raw = path.read_bytes()
    assert token.encode() not in raw, "اللينك نفسه اتخزّن في القاعدة"
    assert reset.check(path, token)["username"] == "mo"


def test_a_used_link_dies(db):
    path, store = db
    _id, token = reset.record(path, username="mo", system="hub", identifier="mo", ip="", with_token=True)
    ok, who = reset.consume(path, token, "brandnewpass", store)
    assert ok and who == "mo"
    assert reset.check(path, token) is None
    assert reset.consume(path, token, "another-one", store)[0] is False


def test_a_new_link_retires_the_previous_one(db):
    path, store = db
    _i, first = reset.record(path, username="mo", system="hub", identifier="mo", ip="", with_token=True)
    _j, second = reset.record(path, username="mo", system="hub", identifier="mo", ip="", with_token=True)
    assert reset.check(path, first) is None
    assert reset.check(path, second) is not None
    assert reset.consume(path, second, "brandnewpass", store)[0]


def test_an_expired_link_is_refused(db):
    path, store = db
    _id, token = reset.record(path, username="mo", system="hub", identifier="mo", ip="",
                              ttl_minutes=0, with_token=True)
    time.sleep(0.01)
    assert reset.check(path, token) is None
    assert reset.consume(path, token, "brandnewpass", store)[0] is False


def test_a_rejected_password_does_not_burn_the_link(db):
    """A typo must not lock somebody out — the token survives a failed attempt."""
    path, store = db
    _id, token = reset.record(path, username="mo", system="hub", identifier="mo", ip="", with_token=True)
    ok, why = reset.consume(path, token, "short", store)
    assert not ok and "8" in why
    assert reset.check(path, token) is not None
    assert reset.consume(path, token, "longenoughnow", store)[0]


def test_a_reset_logs_every_existing_session_out(db):
    """session_version is what the cookie is checked against on every request."""
    path, store = db
    before = store.get_user("mo")["session_version"]
    _id, token = reset.record(path, username="mo", system="hub", identifier="mo", ip="", with_token=True)
    reset.consume(path, token, "brandnewpass", store)
    assert store.get_user("mo")["session_version"] > before
    assert store.authenticate("mo", "oldpassword1") is None
    assert store.authenticate("mo", "brandnewpass")


def test_a_request_for_another_system_carries_no_token(db):
    """Nothing here can set a password on نما or ووردبريس, so nothing is issued."""
    path, _ = db
    _id, token = reset.record(path, username="mo", system="erp-site", identifier="mo", ip="",
                              with_token=False)
    assert token == ""
    assert reset.check(path, "") is None


# --- limits and the admin view ------------------------------------------------
def test_requests_are_capped_per_account_and_per_ip(db):
    path, _ = db
    for _ in range(reset.MAX_PER_ACCOUNT_HOUR):
        reset.record(path, username="mo", system="hub", identifier="mo", ip="9.9.9.9", with_token=True)
    assert "الحساب" in reset.throttled(path, "mo", "9.9.9.9")
    assert reset.throttled(path, "", "2.2.2.2") == ""


def test_the_same_sentence_is_returned_whether_or_not_the_account_exists():
    """The wording itself is the guard, so it is pinned by a test."""
    assert "لو الحساب موجود" in reset.SAME_ANSWER


def test_with_mail_off_the_answer_stops_promising_a_message():
    """A promise of an email that cannot be sent is the one lie this flow can tell."""
    assert "مقفول" in reset.NO_MAIL_ANSWER
    assert "هتوصلك" not in reset.NO_MAIL_ANSWER


def test_the_admin_view_shows_state_and_whether_mail_left(db):
    path, _ = db
    rid, _t = reset.record(path, username="mo", system="hub", identifier="mo", ip="", with_token=True)
    reset.mark_delivery(path, rid, "failed", "SMTPAuthenticationError")
    row = reset.pending(path)[0]
    assert row["state"] == "open" and row["delivery"] == "failed"
    assert "SMTP" in row["delivery_note"]
    assert row["system_label"]


def test_cancelling_kills_the_link(db):
    path, store = db
    rid, token = reset.record(path, username="mo", system="hub", identifier="mo", ip="", with_token=True)
    assert reset.cancel(path, rid)
    assert reset.check(path, token) is None
    assert reset.consume(path, token, "brandnewpass", store)[0] is False


# --- the directory of other systems -------------------------------------------
def test_every_system_says_how_it_is_recovered():
    silent = [s["key"] for s in reset.systems() if not s["how"].strip()]
    assert not silent, f"أنظمة من غير طريقة استرجاع مكتوبة: {silent}"


def test_only_the_hub_claims_self_service_here():
    """Claiming to reset a system we do not own would be a lie on the screen."""
    assert [s["key"] for s in reset.systems() if s.get("self")] == ["hub"]


# --- mail ---------------------------------------------------------------------
def test_mail_that_is_not_configured_fails_out_loud():
    from types import SimpleNamespace

    from app.core import mailer
    s = SimpleNamespace(smtp_host="", smtp_from="", smtp_port=587, smtp_user="",
                        smtp_password="", smtp_tls=True)
    ok, why = mailer.send(s, "x@example.com", "s", "b")
    assert ok is False and "SMTP_HOST" in why


def test_the_reset_mail_carries_a_link_and_never_a_password():
    _subject, body = reset.user_mail("MU", "https://hub.stlixvalley.com/reset?t=abc", 30)
    assert "/reset?t=abc" in body and "30 دقيقة" in body
    assert "كلمة المرور الجديدة" not in body


def test_more_than_one_owner_address_is_notified():
    """Receiving and sending are different problems.

    A personal outlook.com/hotmail address cannot authenticate SMTP any more
    (Microsoft retired basic auth for personal accounts in September 2024), but
    it is still a fine place to be *told* about a reset — so the owner field
    takes a list, and a second inbox means a locked-out owner is not blind too.
    """
    from types import SimpleNamespace

    from app.auth.reset_router import owners
    s = SimpleNamespace(auth_owner_email=" a@gmail.com , b@hotmail.com;  ")
    assert owners(s) == ["a@gmail.com", "b@hotmail.com"]
    assert owners(SimpleNamespace(auth_owner_email="")) == []
    assert owners(SimpleNamespace()) == []
