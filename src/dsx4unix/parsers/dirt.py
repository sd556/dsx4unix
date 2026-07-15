"""DiRT Rally telemetry parser.

Parses DiRT Rally 1.0 binary telemetry packets.
Format: fixed-offset binary with float32 fields.
"""

from __future__ import annotations
import struct

from dsx4unix.parsers.base import BaseParser
from dsx4unix.telemetry import TelemetryPacket


class DirtParser(BaseParser):
    """Parser for DiRT Rally telemetry."""

    def parse(self, packet: bytes) -> TelemetryPacket:
        pkt = TelemetryPacket()
        pkt.is_race_on = True
        pkt.power = 1.0

        pkt.current_engine_rpm = self._f(packet, 148) * 10.0
        pkt.speed = self._f(packet, 28)
        pkt.acceleration_x = self._f(packet, 136)
        pkt.acceleration_z = self._f(packet, 140)
        pkt.engine_max_rpm = self._f(packet, 252) * 10.0
        pkt.engine_idle_rpm = 0.0

        # Tire contact patch velocities
        fl_contact = self._f(packet, 108)
        pkt.front_left_contact_patch_v = fl_contact
        pkt.tire_combined_slip_fl = _calc_slip(fl_contact, pkt.speed)
        pkt.tire_combined_slip_fr = _calc_slip(self._f(packet, 112), pkt.speed)
        pkt.tire_combined_slip_rl = _calc_slip(self._f(packet, 100), pkt.speed)
        pkt.tire_combined_slip_rr = _calc_slip(self._f(packet, 104), pkt.speed)

        # Controls
        pkt.accelerator = min(self._f(packet, 116), 1.0)
        pkt.brake = min(self._f(packet, 120), 1.0)
        pkt.recompute_derived_fields()

        return pkt

    def expected_packet_size(self) -> int:
        return 264  # DiRT Rally packet size

    @staticmethod
    def _f(data: bytes, offset: int) -> float:
        return struct.unpack_from("<f", data, offset)[0]


def _calc_slip(contact_patch_speed: float, vehicle_speed: float) -> float:
    if abs(vehicle_speed) < 0.1:
        return 0.0
    return 3.0 * (abs(abs(contact_patch_speed) - vehicle_speed) / vehicle_speed)
