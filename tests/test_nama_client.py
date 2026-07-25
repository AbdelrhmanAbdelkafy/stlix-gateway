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

from app.core.errors import UpstreamError
from app.integrations.nama.client import NamaClient


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
