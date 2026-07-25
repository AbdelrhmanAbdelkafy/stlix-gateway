"""Nama's HTTP 400 does not mean "no data" — sometimes it carries most of it.

Nama answers 400 in two very different situations, and telling them apart is the
difference between seeing the company's live collections and seeing nothing:

  * a valid filter matching zero rows  -> 400 with an empty body
  * *some* records failed to serialise -> 400 with the successful ones included

The second shape was being raised as an error, so `ReceiptVoucher` and
`PaymentVoucher` — the live customer collections and supplier payments — looked
unreadable when the data was in the response all along.
"""
import httpx
import pytest

from app.config import Settings
from app.core.errors import UpstreamError
from app.integrations.nama.client import PAGE_SIZE_MAX, NamaClient, is_draft


def _resp(status: int, body) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("POST", "http://x/list"))


def test_partial_400_keeps_the_records_it_did_return():
    data = NamaClient._handle(_resp(400, {
        "records_count": 23,
        "failed_records_count": 2,
        "records": {"ReceiptVoucher": [{"code": "CR1"}, {"code": "CR2"}]},
    }))
    assert len(data["records"]["ReceiptVoucher"]) == 2


def test_a_partial_result_says_so():
    """A total summed from an incomplete set must not look like a true total."""
    data = NamaClient._handle(_resp(400, {
        "records_count": 23,
        "failed_records_count": 2,
        "records": {"ReceiptVoucher": [{"code": "CR1"}]},
    }))
    assert data["_partial"] == {"http_status": 400, "returned": 1, "failed": 2}


def test_a_full_success_is_not_marked_partial():
    data = NamaClient._handle(_resp(200, {"records": {"Employee": [{"code": "E1"}]}}))
    assert "_partial" not in data


def test_400_with_no_records_is_still_an_error():
    with pytest.raises(UpstreamError):
        NamaClient._handle(_resp(400, {"failed_records_count": 3, "records": {}}))


def test_empty_400_is_only_a_clean_end_for_list_calls():
    assert NamaClient._handle(_resp(400, {}), empty_400_ok=True) == {}
    with pytest.raises(UpstreamError):
        NamaClient._handle(_resp(400, {}))


def test_a_page_where_every_record_is_inaccessible_is_still_partial_data():
    data = NamaClient._handle(_resp(400, {
        "records": {"X": []},
        "failed_records": [{"errors": [{"extraInfo": {"code": "LOCKED1"}}]}],
    }))
    assert data["_partial"]["returned"] == 0
    assert data["_partial"]["failed"] == 1


def test_a_declared_failure_is_still_an_error():
    """`failureOccurred` outranks any records in the body."""
    with pytest.raises(UpstreamError):
        NamaClient._handle(_resp(200, {
            "failureOccurred": True,
            "failureMessage": "boom",
            "records": {"X": [{"a": 1}]},
        }))


def test_auth_failure_is_reported_as_auth():
    with pytest.raises(UpstreamError, match="401"):
        NamaClient._handle(_resp(401, {"errors": []}))


# --- paging -----------------------------------------------------------------
#
# `maxRecords` is accepted and ignored by the tenant: 5, 50 and 1000 all return
# the same 25-row default page. Every list call was therefore capped at 25 rows
# while looking like it had asked for more — which is why entities with thousands
# of documents read as tiny. `startPage` + `pageSize` are what Nama honours.


def _client() -> NamaClient:
    return NamaClient(Settings(_env_file=None, nama_base="http://x", nama_client_id="i",
                               nama_client_secret="s"))


@pytest.mark.asyncio
async def test_list_asks_with_paging_not_maxrecords(monkeypatch):
    sent = {}

    async def fake(self, method, path, json=None, **kw):
        sent.update(json or {})
        return {"records": {"Employee": []}}

    monkeypatch.setattr(NamaClient, "_request", fake)
    await _client().list("Employee", max_records=200)
    assert sent == {"startPage": 1, "pageSize": 200}
    assert "maxRecords" not in sent


@pytest.mark.asyncio
async def test_list_all_stops_on_a_short_page_counting_failures_too(monkeypatch):
    """A page holding 999 records + 1 unreadable one is FULL, not the last page.

    Deciding on `len(records)` alone ends the sweep early and silently truncates
    the total — the exact failure this pages against.
    """
    pages = [
        {"records": {"X": [{"code": f"a{i}"} for i in range(PAGE_SIZE_MAX - 1)]},
         "failed_records": [{"errors": [{"extraInfo": {"code": "LOCKED1"}}]}]},
        {"records": {"X": [{"code": "b1"}]}},
    ]
    seen = []

    async def fake(self, method, path, json=None, **kw):
        seen.append(json["startPage"])
        return pages[json["startPage"] - 1]

    monkeypatch.setattr(NamaClient, "_request", fake)
    out = await _client().list_all("X")
    assert seen == [1, 2], "a full page containing a failed record must not end the sweep"
    assert out["count"] == PAGE_SIZE_MAX
    assert out["inaccessible"] == ["LOCKED1"] and out["complete"] is False


@pytest.mark.asyncio
async def test_list_all_treats_an_empty_page_as_the_end(monkeypatch):
    async def fake(self, method, path, json=None, **kw):
        if json["startPage"] == 1:
            return {"records": {"X": [{"code": "a"}]}}
        return {}  # 400 + empty body: nothing left

    monkeypatch.setattr(NamaClient, "_request", fake)
    out = await _client().list_all("X")
    assert out["count"] == 1 and out["complete"] is True


@pytest.mark.asyncio
async def test_list_all_never_calls_a_max_page_cap_complete(monkeypatch):
    async def fake(self, method, path, json=None, **kw):
        return {"records": {"X": [{"code": str(i)} for i in range(PAGE_SIZE_MAX)]}}

    monkeypatch.setattr(NamaClient, "_request", fake)
    out = await _client().list_all("X", max_pages=1)
    assert out["truncated"] is True and out["complete"] is False


@pytest.mark.asyncio
async def test_a_sweep_retries_a_dropped_connection_but_a_request_does_not(monkeypatch):
    calls = []

    class Flaky:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, *a, **kw):
            calls.append(1)
            if len(calls) < 3:
                raise httpx.ConnectError("dropped")
            return _resp(200, {"records": {"X": [{"code": "a"}]}})

    async def no_sleep(*_):
        return None

    monkeypatch.setattr(httpx, "AsyncClient", Flaky)
    monkeypatch.setattr("asyncio.sleep", no_sleep)
    out = await _client()._request("POST", "X/list", {}, retries=3)
    assert out["records"]["X"][0]["code"] == "a" and len(calls) == 3

    calls.clear()
    with pytest.raises(UpstreamError, match="unreachable"):
        await _client()._request("POST", "X/list", {})
    assert len(calls) == 1


def test_draft_codes_are_recognisable():
    assert is_draft({"code": "CR2026030001@draft"}) is True
    assert is_draft({"code": "CR2026030001"}) is False
    assert is_draft({"code": "draft-helper-CR1"}) is False


def test_an_unnumbered_document_is_a_draft_too():
    """`@draft` is the usual marker for unposted, not the only one.

    Measured on the restored database: four unposted invoices, three carrying
    `@draft` and one PurchaseInvoice carrying no code at all — Nama had not
    numbered it yet. The suffix test alone passed it through as posted. It was
    worth 0 EGP, so nothing looked wrong; the next one need not be.

    Requiring a code is safe because none of the 13,686 posted invoice rows has
    an empty one.
    """
    assert is_draft({"code": ""}) is True
    assert is_draft({"code": "   "}) is True
    assert is_draft({}) is True
