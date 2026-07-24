"""Inventory / Stocktake connector: mode, config gating, registry, workspace."""
import pytest

from app.config import Settings
from app.core.errors import UpstreamError
from app.integrations.inventory.connector import InventoryConnector
from app.main import app
from app.workspace.providers import PROVIDERS
from fastapi.testclient import TestClient

client = TestClient(app)


def _bare(**kw):
    return Settings(_env_file=None, **kw)


def test_inventory_default_read_only():
    assert _bare().inventory_mode == "read_only"
    assert InventoryConnector(_bare()).read_only is True


def test_inventory_configured_flag():
    assert _bare().inventory_configured is False
    assert _bare(inventory_base_url="https://x/count", inventory_key="k").inventory_configured is True


@pytest.mark.asyncio
async def test_snapshot_unconfigured_raises():
    with pytest.raises(UpstreamError):
        await InventoryConnector(_bare()).snapshot()


def test_inventory_live_in_registry():
    systems = client.get("/systems?format=json").json()["systems"]
    inv = next(s for s in systems if s["key"] == "inventory")
    assert inv["status"] == "live"


def test_inventory_has_workspace_provider():
    assert any(p.key == "inventory" for p in PROVIDERS)
