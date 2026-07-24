"""Banks connector (Nama-backed): mode, config gating, registry, workspace."""
from fastapi.testclient import TestClient

from app.config import Settings
from app.integrations.banks.connector import BanksConnector
from app.main import app
from app.workspace.providers import PROVIDERS

client = TestClient(app)


def test_banks_default_read_only():
    assert Settings(_env_file=None).banks_mode == "read_only"
    assert BanksConnector(Settings(_env_file=None)).read_only is True


def test_banks_live_in_registry():
    systems = client.get("/systems?format=json").json()["systems"]
    banks = next(s for s in systems if s["key"] == "banks")
    assert banks["status"] == "live"


def test_banks_has_workspace_provider():
    assert any(p.key == "banks" for p in PROVIDERS)
