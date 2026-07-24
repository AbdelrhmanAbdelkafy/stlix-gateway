"""Read-only connector enforcement: reads pass, writes are blocked."""
import pytest

from app.config import Settings
from app.integrations.base import ConnectorMode, ReadOnlyError
from app.integrations.nama.connector import NamaConnector


def _conn(mode: str) -> NamaConnector:
    return NamaConnector(Settings(nama_mode=mode, nama_client_id="x", nama_client_secret="y"))


def test_default_mode_is_read_only():
    assert Settings().nama_mode == "read_only"


def test_read_only_blocks_save():
    conn = _conn("read_only")
    assert conn.read_only is True
    with pytest.raises(ReadOnlyError):
        conn.guard_write()


def test_read_write_allows_guard():
    conn = _conn("read_write")
    assert conn.mode is ConnectorMode.READ_WRITE
    # should not raise
    conn.guard_write()


@pytest.mark.asyncio
async def test_save_raises_in_read_only():
    conn = _conn("read_only")
    with pytest.raises(ReadOnlyError):
        await conn.save("TimeAttendance", {"attendanceLines": []})
