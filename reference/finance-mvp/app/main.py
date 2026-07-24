"""Finance OS MVP — FastAPI application entrypoint (Modular Monolith)."""
from __future__ import annotations

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import create_all
from app.core.logging_config import CorrelationIdMiddleware, configure_logging, logger
from app.modules.finance.router import router as finance_router
from app.modules.governance.router import router as governance_router
from app.modules.identity.router import router as identity_router
from app.modules.integration.router import router as integration_router

configure_logging()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0-mvp",
    description="Finance Operating System — MVP. ERP is the System of Record; "
                "posting happens only through the approved workflow.",
)
app.add_middleware(CorrelationIdMiddleware)


@app.on_event("startup")
def _startup() -> None:
    # MVP convenience: ensure tables exist. Production uses managed migrations.
    create_all()
    logger.info("Finance OS MVP started env=%s", settings.environment)


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok", "service": settings.app_name, "version": "1.0.0-mvp"}


api = settings.api_prefix
app.include_router(identity_router, prefix=api)
app.include_router(finance_router, prefix=api)
app.include_router(integration_router, prefix=api)
app.include_router(governance_router, prefix=api)
