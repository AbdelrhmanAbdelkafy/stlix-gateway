#!/usr/bin/env python3
"""The tax portal as MCP tools — both entities, everything it can do.

Goes through the STLIX gateway (`/api/v1/eta/*` and `/api/v1/vat/*`), so Claude
Desktop needs one gateway key and no portal credentials: the client_id/secret
live only in the gateway's `.env` on the VPS. Reads are free; the two writes
the portal allows (cancel/reject) are gated server-side and irreversible at
ETA; issuing documents is not offered, because it needs the eSeal certificate.

Claude Desktop (claude_desktop_config.json):
    "stlix-vat": {
      "command": "python",
      "args": ["D:/Nama Code project/stlix-gateway/mcp/eta-einvoicing/server.py"],
      "env": {"STLIX_GATEWAY_URL": "https://gw.stlixvalley.com",
              "STLIX_GATEWAY_KEY": "<gateway key>"}
    }
Deps: pip install mcp httpx
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

GW = os.environ.get("STLIX_GATEWAY_URL", "https://gw.stlixvalley.com").rstrip("/")
KEY = os.environ.get("STLIX_GATEWAY_KEY", "")
H = {"X-API-Key": KEY, "Accept": "application/json", "User-Agent": "stlix-vat-mcp/1"}
DOWNLOADS = Path(os.environ.get("STLIX_DOWNLOAD_DIR", Path(__file__).with_name("downloads")))

mcp = FastMCP("stlix-vat", instructions=(
    "The Egyptian tax portal (ETA e-invoicing) and STLIX's VAT planning, for both entities: "
    "'group' (المجموعة) and 'stlix'. Months are YYYY-MM, figures in EGP. `gap_base` is the value of "
    "purchase invoices still needed (positive) or the surplus (negative). Never invent numbers — if "
    "`synced` is false, call vat_sync first.\n"
    "Two rules that matter: (1) portal_set_state cancels or rejects a tax document and cannot be undone "
    "at ETA — never call it without the owner asking for that specific document, and always pass the "
    "reason they gave; (2) issuing/submitting invoices is not available here at all (it needs the eSeal "
    "certificate), so say so rather than looking for a way."))


def _req(method: str, path: str, **kw):
    with httpx.Client(timeout=180) as c:
        r = c.request(method, GW + path, headers=H, **kw)
        r.raise_for_status()
        return r.json()


def _bytes(path: str, out_name: str, **kw) -> dict:
    """Binary answers (PDF, zip) are saved next to the MCP and the path returned —
    an MCP result is text, and a 4 MB base64 blob helps nobody."""
    with httpx.Client(timeout=300) as c:
        r = c.get(GW + path, headers={"X-API-Key": KEY}, params=kw or None)
        r.raise_for_status()
    p = DOWNLOADS / out_name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(r.content)
    return {"saved_to": str(p), "bytes": len(r.content), "content_type": r.headers.get("content-type")}


@mcp.tool()
def vat_overview() -> dict:
    """Both entities, this month and last: headline, gap, status, filing deadline."""
    return _req("GET", "/api/v1/vat")


@mcp.tool()
def vat_sync(entity: str, month: str) -> dict:
    """Pull the month's documents (sales + purchases, with status) from the portal into the gateway cache."""
    return _req("POST", f"/api/v1/vat/{entity}/{month}/sync")


@mcp.tool()
def vat_plan(entity: str, month: str) -> dict:
    """The full plan: sales (manufacturing/trading), purchases, imports, credit, target, gap, invoice slots, problems."""
    return _req("GET", f"/api/v1/vat/{entity}/{month}")


@mcp.tool()
def vat_documents(entity: str, month: str, direction: str | None = None, status: str | None = None) -> list[dict]:
    """Cached portal documents. direction: Sent (our sales) | Received (our purchases); status: valid|cancelled|rejected|submitted|invalid."""
    params = {k: v for k, v in {"direction": direction, "status": status}.items() if v}
    return _req("GET", f"/api/v1/vat/{entity}/{month}/documents", params=params)["documents"]


@mcp.tool()
def vat_add_import(entity: str, month: str, vat_paid: float, release_no: str = "", note: str = "") -> dict:
    """Record a customs release (الإفراج الضريبي) by the VAT paid; base = VAT ÷ 14%."""
    return _req("POST", f"/api/v1/vat/{entity}/{month}/imports",
                json={"vat": vat_paid, "release_no": release_no, "note": note})


@mcp.tool()
def vat_set_status(entity: str, month: str, status: str, credit_in: float | None = None, notes: str | None = None) -> dict:
    """Move the month along the procedure: open → closing → packaged → draft_review → ready_to_pay → paid → closed."""
    body = {"status": status}
    if credit_in is not None:
        body["credit_in"] = credit_in
    if notes is not None:
        body["notes"] = notes
    return _req("PATCH", f"/api/v1/vat/{entity}/{month}", json=body)


@mcp.tool()
def vat_compare_draft(entity: str, month: str, sales_vat: float, purchases_vat: float,
                      imports_vat: float = 0.0, credit_in: float = 0.0, payable: float | None = None) -> dict:
    """Compare the draft return's figures with ours, line by line; a full match marks the month ready_to_pay."""
    body = {"sales_vat": sales_vat, "purchases_vat": purchases_vat, "imports_vat": imports_vat, "credit_in": credit_in}
    if payable is not None:
        body["payable"] = payable
    return _req("POST", f"/api/v1/vat/{entity}/{month}/draft", json=body)


@mcp.tool()
def vat_package(entity: str, month: str) -> dict:
    """The return package: figures + cancelled/rejected list + calendar — what goes on the return."""
    return _req("GET", f"/api/v1/vat/{entity}/{month}/package")


# --- the portal itself ------------------------------------------------------------
@mcp.tool()
def portal_ping(entity: str) -> dict:
    """Check the portal credentials for one entity right now."""
    return _req("GET", f"/api/v1/eta/{entity}/ping")


@mcp.tool()
def portal_recent(entity: str, page: int = 1, page_size: int = 50,
                  direction: str | None = None, status: str | None = None) -> dict:
    """Latest documents straight from the portal (no date window). direction: Sent|Received."""
    params = {"page": page, "page_size": page_size}
    if direction:
        params["direction"] = direction
    if status:
        params["status"] = status
    return _req("GET", f"/api/v1/eta/{entity}/recent", params=params)


@mcp.tool()
def portal_notifications(entity: str, page: int = 1) -> dict:
    """ETA's own notifications to this taxpayer — the portal inbox."""
    return _req("GET", f"/api/v1/eta/{entity}/notifications", params={"page": page})


@mcp.tool()
def portal_document_types(entity: str) -> dict:
    """Document types and their workflow parameters — where the cancellation window is defined."""
    return _req("GET", f"/api/v1/eta/{entity}/document-types")


@mcp.tool()
def portal_document(entity: str, uuid: str, raw: bool = False) -> dict:
    """One document: details (lines, taxes, validation) or, with raw=True, the original submission."""
    tail = "" if raw else "/details"
    return _req("GET", f"/api/v1/eta/{entity}/documents/{uuid}{tail}")


@mcp.tool()
def portal_document_pdf(entity: str, uuid: str) -> dict:
    """Download ETA's own PDF of a document; returns the saved file path."""
    return _bytes(f"/api/v1/eta/{entity}/documents/{uuid}/pdf", f"{entity}-{uuid}.pdf")


@mcp.tool()
def portal_request_package(entity: str, month: str, fmt: str = "JSON", type_: str = "full") -> dict:
    """Ask ETA to prepare a whole month as one package; returns its request id."""
    return _req("POST", f"/api/v1/eta/{entity}/packages",
                json={"month": month, "format": fmt, "type": type_})


@mcp.tool()
def portal_package_requests(entity: str) -> dict:
    """Which packages were requested and which are ready to download."""
    return _req("GET", f"/api/v1/eta/{entity}/packages")


@mcp.tool()
def portal_download_package(entity: str, package_id: str) -> dict:
    """Download a prepared package (zip); returns the saved file path."""
    return _bytes(f"/api/v1/eta/{entity}/packages/{package_id}", f"{entity}-{package_id}.zip")


@mcp.tool()
def portal_set_state(entity: str, uuid: str, status: str, reason: str, month: str | None = None) -> dict:
    """IRREVERSIBLE. Cancel one of our documents (status='cancelled') or reject one issued to us
    ('rejected'), with the reason the owner gave. Only works while ETA_ALLOW_STATE_CHANGES is on;
    otherwise it returns a refusal, which is the expected answer, not an error to work around.
    Never call this on your own initiative."""
    body = {"status": status, "reason": reason}
    if month:
        body["month"] = month
    return _req("PUT", f"/api/v1/eta/{entity}/documents/{uuid}/state", json=body)


@mcp.tool()
def vat_manufacturing_codes() -> dict:
    """Item codes counted as manufacturing (AssemblyBOM items)."""
    return _req("GET", "/api/v1/vat/codes")


if __name__ == "__main__":
    mcp.run()
