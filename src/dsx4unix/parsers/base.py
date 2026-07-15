"""Base telemetry parser."""

from __future__ import annotations
from abc import ABC, abstractmethod

from dsx4unix.telemetry import TelemetryPacket


class BaseParser(ABC):
    """Abstract base for game-specific telemetry parsers."""

    @abstractmethod
    def parse(self, packet: bytes) -> TelemetryPacket:
        """Parse a raw UDP packet into a TelemetryPacket."""
        ...

    @abstractmethod
    def expected_packet_size(self) -> int:
        """Return the expected packet size for this game format."""
        ...
