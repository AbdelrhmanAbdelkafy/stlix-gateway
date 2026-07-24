"""Monitoring endpoints: /metrics (Prometheus text or JSON)."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from ..core.metrics import metrics

router = APIRouter(tags=["monitoring"])


@router.get("/metrics")
async def get_metrics(request: Request):
    """Prometheus text by default; JSON via ?format=json or Accept: application/json."""
    fmt = request.query_params.get("format")
    accept = request.headers.get("accept", "")
    want_json = fmt == "json" or ("application/json" in accept and fmt != "prom")
    if want_json:
        return JSONResponse(metrics.snapshot())
    return PlainTextResponse(metrics.prometheus(), media_type="text/plain; version=0.0.4")
