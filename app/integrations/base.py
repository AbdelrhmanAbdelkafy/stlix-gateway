"""Connector base: every integrated system is a Connector with a MODE.

A connector in READ_ONLY mode physically refuses write operations
(`guard_write` raises), so a misconfigured client or a stray call can never
mutate the upstream system. Flipping to READ_WRITE is a deliberate act.
"""
from __future__ import annotations

from enum import Enum

from fastapi import status

from ..core.errors import GatewayError


class ConnectorMode(str, Enum):
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


class ReadOnlyError(GatewayError):
    """Raised when a write is attempted on a read-only connector."""

    def __init__(self, connector: str) -> None:
        super().__init__(
            f"Connector '{connector}' is in read-only mode; write operations are disabled.",
            status.HTTP_403_FORBIDDEN,
        )


class Connector:
    key: str = "connector"

    def __init__(self, mode: ConnectorMode) -> None:
        self.mode = mode

    @property
    def read_only(self) -> bool:
        return self.mode is ConnectorMode.READ_ONLY

    def guard_write(self) -> None:
        """Call at the top of every write op; raises if read-only."""
        if self.read_only:
            raise ReadOnlyError(self.key)
