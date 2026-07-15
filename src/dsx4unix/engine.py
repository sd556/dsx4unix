"""Main engine — receives telemetry, maps to triggers, sends DSX instructions."""

from __future__ import annotations
import logging
import socket
import threading
import time
from dataclasses import dataclass

from dsx4unix.config.loader import load_profile
from dsx4unix.config.models import GameType, Profile
from dsx4unix.dsx import DSXSender, TriggerInstruction
from dsx4unix.mapper import map_brake, map_lightbar, map_throttle
from dsx4unix.parsers.dirt import DirtParser
from dsx4unix.parsers.forza import ForzaParser
from dsx4unix.telemetry import TelemetryPacket

logger = logging.getLogger(__name__)


@dataclass
class State:
    throttle_resistance: float = 0.0
    brake_resistance: float = 0.0
    packets_received: int = 0
    packets_dropped: int = 0


class Engine:
    """Main processing loop."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self.state = State()
        self._running = threading.Event()

        # Parser
        if profile.game == GameType.FORZA:
            self.parser = ForzaParser()
        elif profile.game == GameType.DIRT:
            self.parser = DirtParser()
        else:
            self.parser = ForzaParser()  # default

        # DSX sender
        self.dsx = DSXSender(host=profile.dsx_host, port=profile.dsx_port)

        # Telemetry socket
        self.telemetry_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.telemetry_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.telemetry_sock.bind(("0.0.0.0", profile.telemetry_port))
        self.telemetry_sock.setblocking(False)

    def run(self, interval: float = 0.016) -> None:  # ~60 Hz
        """Run the main processing loop."""
        self._running.set()
        logger.info("Listening for telemetry on UDP port %d", self.profile.telemetry_port)
        logger.info("Sending DSX instructions to %s:%d", self.profile.dsx_host, self.profile.dsx_port)
        logger.info("Profile: %s (game=%s)", self.profile.name, self.profile.game.value)

        last_packet: TelemetryPacket | None = None
        last_send = 0.0

        while self._running.is_set():
            now = time.monotonic()

            # Read telemetry packets (non-blocking, drain all)
            pkt = self._read_packet()
            if pkt:
                last_packet = pkt
                self.state.packets_received += 1

            # Send DSX instructions at fixed rate
            if now - last_send >= interval and last_packet:
                left, self.state.brake_resistance = map_brake(
                    last_packet, self.profile.brake, self.state.brake_resistance
                )
                right, self.state.throttle_resistance = map_throttle(
                    last_packet, self.profile.throttle, self.state.throttle_resistance
                )
                lightbar = map_lightbar(last_packet, self.profile.lightbar)
                self.dsx.send_all(left=left, right=right, lightbar=lightbar)
                last_send = now

                if self.state.packets_received % 60 == 0:
                    logger.info(
                        "Packets: %d received, %d dropped",
                        self.state.packets_received,
                        self.state.packets_dropped,
                    )

            time.sleep(max(0.001, interval - (time.monotonic() - now)))

    def _read_packet(self) -> TelemetryPacket | None:
        """Read one telemetry packet (non-blocking)."""
        try:
            data, _ = self.telemetry_sock.recvfrom(4096)
            return self.parser.parse(data)
        except socket.error:
            return None

    def stop(self) -> None:
        """Stop the engine."""
        self._running.clear()
        # Reset triggers
        self.dsx.send_triggers(
            left=TriggerInstruction(trigger="left", mode="Normal"),
            right=TriggerInstruction(trigger="right", mode="Normal"),
        )
        self.dsx.close()
        self.telemetry_sock.close()
        logger.info("Engine stopped. Total packets: %d", self.state.packets_received)
