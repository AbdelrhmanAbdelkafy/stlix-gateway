"""Monitoring endpoint: /metrics as HTML (browser), Prometheus text, or JSON."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from ..core.metrics import metrics
from ..core.render import html_page, table, wants_html

router = APIRouter(tags=["monitoring"])


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
            + '<p class="s" style="margin:1rem 0 .5rem;font-weight:600;">By route</p>'
            + table(path_rows, ["path", "count", "errors", "avg_ms"])
        )
        badges = (
            f'<span class="badge">{snap["requests_total"]} req</span>'
            f'<span class="badge ro">{snap["uptime_seconds"]}s up</span>'
        )
        return html_page("Metrics", body, snap, badges=badges)

    if fmt == "json" or ("application/json" in accept and fmt != "prom"):
        return JSONResponse(metrics.snapshot())

    return PlainTextResponse(metrics.prometheus(), media_type="text/plain; version=0.0.4")
