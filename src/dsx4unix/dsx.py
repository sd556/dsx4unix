"""DSX/Hefesto protocol UDP sender.

Sends JSON instructions over UDP to Hefesto (localhost:6969) which drives the
DualSense controller.

Important compatibility note:
- `dsx4unix` internally thinks in simplified RacingDSX/DSX terms (`Normal`,
  `Resistance`, `Vibration`).
- Hefesto's UDP server expects its own preset names/parameter shapes.

This module translates the simplified model into the concrete Hefesto UDP
payloads so runtime packets are actually applied on Linux.
"""

from __future__ import annotations

import json
import logging
import socket
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TriggerInstruction:
    """High-level trigger instruction expressed in RacingDSX/DSX terms."""

    trigger: str  # "left" | "right"
    mode: str  # "Normal" | "Resistance" | "Vibration" | "Custom"
    # Resistance-style inputs from the mapper
    stiffness: int = 0  # 0–255
    resistance: int = 0  # 0–7
    # Vibration-style inputs from the mapper
    frequency: int = 0  # 0–255
    intensity: int = 0  # 0–255
    # DSX custom / hybrid raw trigger values
    custom_mode: str | int | None = None
    custom_forces: tuple[int, int, int, int, int, int, int] | None = None

    def to_hefesto_parameters(self) -> list[Any]:
        """Translate the simplified mode/params to Hefesto UDP parameters.

        Hefesto accepts:
        - Off:         [trigger, "Off"]
        - Resistance:  [trigger, "Resistance", start(0-9), force(0-8)]
        - Vibration:   [trigger, "Vibration", position(0-9), amplitude(0-8), frequency(0-255)]

        Translation choices:
        - `Normal` means no effect -> `Off`
        - DSX `stiffness` is approximated to Hefesto `start` (0..9)
        - DSX `resistance` maps to Hefesto `force` (0..8)
        - DSX vibration uses position=0 and maps intensity 0..255 -> amplitude 0..8
        """
        trigger = str(self.trigger).lower()
        mode = str(self.mode)

        if mode == "Resistance":
            start = max(0, min(9, round((int(self.stiffness) / 255) * 9)))
            force = max(0, min(8, int(self.resistance)))
            return [trigger, "Resistance", start, force]

        if mode == "Vibration":
            amplitude = max(0, min(8, round((int(self.intensity) / 255) * 8)))
            frequency = max(0, min(255, int(self.frequency)))
            return [trigger, "Vibration", 0, amplitude, frequency]

        if mode == "Custom":
            custom_mode = self.custom_mode if self.custom_mode is not None else "Off"
            forces = self.custom_forces if self.custom_forces is not None else (0, 0, 0, 0, 0, 0, 0)
            return [trigger, "Custom", custom_mode, *[max(0, min(255, int(v))) for v in forces]]

        return [trigger, "Off"]


@dataclass
class LightBarInstruction:
    """High-level RGB instruction."""

    red: int = 0
    green: int = 0
    blue: int = 0

    @property
    def hefesto_parameters(self) -> list[int]:
        # Hefesto expects [idx, r, g, b]. The idx field is ignored by its UDP
        # handler, so we use 0 as a stable placeholder.
        return [0, self.red, self.green, self.blue]


class DSXSender:
    """Sends Hefesto-compatible JSON instructions via UDP."""

    def __init__(self, host: str = "127.0.0.1", port: int = 6969) -> None:
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)

    def send_triggers(
        self,
        left: TriggerInstruction | None = None,
        right: TriggerInstruction | None = None,
    ) -> None:
        instructions = []
        if left:
            instructions.append({
                "type": "TriggerUpdate",
                "parameters": left.to_hefesto_parameters(),
            })
        if right:
            instructions.append({
                "type": "TriggerUpdate",
                "parameters": right.to_hefesto_parameters(),
            })
        if instructions:
            self._send(instructions)

    def send_lightbar(self, lightbar: LightBarInstruction) -> None:
        self._send([{
            "type": "RGBUpdate",
            "parameters": lightbar.hefesto_parameters,
        }])

    def send_all(
        self,
        left: TriggerInstruction | None = None,
        right: TriggerInstruction | None = None,
        lightbar: LightBarInstruction | None = None,
    ) -> None:
        instructions = []
        if left:
            instructions.append({
                "type": "TriggerUpdate",
                "parameters": left.to_hefesto_parameters(),
            })
        if right:
            instructions.append({
                "type": "TriggerUpdate",
                "parameters": right.to_hefesto_parameters(),
            })
        if lightbar:
            instructions.append({
                "type": "RGBUpdate",
                "parameters": lightbar.hefesto_parameters,
            })
        if instructions:
            self._send(instructions)

    def _send(self, instructions: list[dict]) -> None:
        payload = {"version": 1, "instructions": instructions}
        data = json.dumps(payload).encode("utf-8")
        try:
            self.sock.sendto(data, (self.host, self.port))
        except (ConnectionRefusedError, OSError) as e:
            logger.debug("DSX send error: %s", e)

    def close(self) -> None:
        self.sock.close()
