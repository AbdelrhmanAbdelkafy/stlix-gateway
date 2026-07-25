"""Monitoring endpoint: /metrics as HTML (browser), Prometheus text, or JSON."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from .. import catalog
from ..core.metrics import metrics
from ..core.render import html_page, table, wants_html

router = APIRouter(tags=["monitoring"])


def _by_connector(by_path: dict) -> list[dict]:
    """Traffic rolled up per connector.

    `by_path` alone cannot answer "how much load is the banks connector taking"
    — the paths are raw strings with no idea which system they belong to.
    """
    agg: dict[str, dict] = {}
    for path, v in by_path.items():
        ep = catalog.get_endpoint(path)
        key = ep.connector if ep and ep.connector else "—"
        row = agg.setdefault(key, {"connector": key, "count": 0, "errors": 0})
        row["count"] += v.get("count", 0)
        row["errors"] += v.get("errors", 0)
    rows = sorted(agg.values(), key=lambda r: -r["count"])
    for r in rows:
        conn = catalog.get_connector(r["connector"])
        r["system"] = conn.system if conn else ""
    return rows


@router.get("/metrics")
async def get_metrics(request: Request):
    """Format negotiation:
    - browser (Accept: text/html) -> styled dashboard
    - ?format=json / Accept: application/json -> JSON snapshot
    - default (scrapers, */*, text/plain) -> Prometheus text
    Force with ?format=html|json|prom.
    """
    fmt = request.query_params.get("format")
    accept = request.headers.get("accept", "")

    if fmt == "html" or (fmt is None and wants_html(request)):
        snap = metrics.snapshot()
        summary = [
            {"metric": "uptime_seconds", "value": snap["uptime_seconds"]},
            {"metric": "requests_total", "value": snap["requests_total"]},
            {"metric": "rate_limited_total", "value": snap["rate_limited_total"]},
        ]
        for cls, n in sorted(snap["by_status_class"].items()):
            summary.append({"metric": f"status {cls}", "value": n})
        path_rows = [{"path": p, **v} for p, v in snap["by_path"].items()]
        path_rows.sort(key=lambda r: r["count"], reverse=True)
        body = (
            '<p class="s" style="margin:.25rem 0 .5rem;font-weight:600;">Summary</p>'
            + table(summary, ["metric", "value"])
            + '<p class="s" style="margin:1rem 0 .5rem;font-weight:600;">By connector</p>'
            + table(_by_connector(snap["by_path"]), ["connector", "system", "count", "errors"])
            + '<p class="s" style="margin:1rem 0 .5rem;font-weight:600;">By route</p>'
            + table(path_rows, ["path", "count", "errors", "avg_ms"])
        )
        badges = (
            f'<span class="badge">{snap["requests_total"]} req</span>'
            f'<span class="badge ro">{snap["uptime_seconds"]}s up</span>'
        )
        return html_page("Metrics", body, snap, badges=badges)

    if fmt == "json" or ("application/json" in accept and fmt != "prom"):
        snap = metrics.snapshot()
        snap["by_connector"] = _by_connector(snap["by_path"])
        return JSONResponse(snap)

    return PlainTextResponse(metrics.prometheus(), media_type="text/plain; version=0.0.4")
