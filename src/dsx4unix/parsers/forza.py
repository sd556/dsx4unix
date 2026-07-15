"""Forza Motorsport telemetry parser.

Parses Forza Motorsport 7/8 and Forza Horizon 4 binary telemetry.
Format: fixed-offset binary with float32 and uint8 fields.

Packet layouts:
  - FM7:  sled (232 bytes) + dash (311 bytes) = 543 bytes total, OR dash only (311 bytes)
  - FM8:  dash only, 331 bytes
  - FH4:  324 bytes total: sled fields remain at their normal offsets, but dash fields are shifted by a 12-byte header

FH4 packet layout (324 bytes):
  - Sled-compatible fields still live at the normal sled offsets (0..231)
  - Dash section uses the same combined-format offsets but shifted by +12 bytes
  - Speed at offset 244+12=256 (float32)
  - Accelerator at offset 303+12=315 (uint8)
  - Brake at offset 304+12=316 (uint8)
  - Gear at offset 307+12=319 (uint8)
"""

from __future__ import annotations
import struct

from dsx4unix.parsers.base import BaseParser
from dsx4unix.telemetry import TelemetryPacket

# Forza packet format sizes
SLED_SIZE = 232
DASH_FM7_SIZE = 311
DASH_FM8_SIZE = 331
DASH_FH4_SIZE = 324

# Sled field offsets (float32 unless noted)
SLED_IS_RACE_ON = 0
SLED_ENGINE_MAX_RPM = 8
SLED_ENGINE_IDLE_RPM = 12
SLED_CURRENT_ENGINE_RPM = 16
SLED_ACCEL_X = 20
SLED_ACCEL_Y = 24
SLED_ACCEL_Z = 28
SLED_TIRE_SLIP_FL = 180
SLED_TIRE_SLIP_FR = 184
SLED_TIRE_SLIP_RL = 188
SLED_TIRE_SLIP_RR = 192
SLED_CAR_CLASS = 216
SLED_CAR_PERFORMANCE_INDEX = 220

# Dash field offsets in the COMBINED format (sled + dash)
# These are the absolute offsets in the combined 543-byte packet
DASH_COMBINED_SPEED = 244
DASH_COMBINED_POWER = 248
DASH_COMBINED_TORQUE = 252
DASH_COMBINED_BOOST = 272
DASH_COMBINED_FUEL = 276
DASH_COMBINED_ACCELERATOR = 303   # uint8
DASH_COMBINED_BRAKE = 304         # uint8
DASH_COMBINED_CLUTCH = 305        # uint8
DASH_COMBINED_HANDBRAKE = 306     # uint8
DASH_COMBINED_GEAR = 307          # uint8
DASH_COMBINED_STEER = 308         # int8

# FH4 uses the same dash layout but with a 12-byte header
# So all dash offsets are shifted by +12
FH4_HEADER_SIZE = 12


class ForzaParser(BaseParser):
    """Parser for Forza Motorsport / Horizon telemetry."""

    def parse(self, packet: bytes) -> TelemetryPacket:
        pkt = TelemetryPacket()

        # Determine layout
        total = len(packet)
        is_combined = total >= SLED_SIZE + DASH_FM7_SIZE
        is_fh4 = total == DASH_FH4_SIZE
        dash_offset = 0
        if is_combined:
            # FM7 combined sled + dash — dash section starts at offset 232
            dash_offset = SLED_SIZE
            pkt.is_race_on = self._f(packet, SLED_IS_RACE_ON) > 0
            pkt.engine_max_rpm = self._f(packet, SLED_ENGINE_MAX_RPM)
            pkt.engine_idle_rpm = self._f(packet, SLED_ENGINE_IDLE_RPM)
            pkt.current_engine_rpm = self._f(packet, SLED_CURRENT_ENGINE_RPM)
            pkt.acceleration_x = self._f(packet, SLED_ACCEL_X)
            pkt.acceleration_y = self._f(packet, SLED_ACCEL_Y)
            pkt.acceleration_z = self._f(packet, SLED_ACCEL_Z)
            pkt.tire_combined_slip_fl = self._f(packet, SLED_TIRE_SLIP_FL)
            pkt.tire_combined_slip_fr = self._f(packet, SLED_TIRE_SLIP_FR)
            pkt.tire_combined_slip_rl = self._f(packet, SLED_TIRE_SLIP_RL)
            pkt.tire_combined_slip_rr = self._f(packet, SLED_TIRE_SLIP_RR)
            pkt.car_class = self._b(packet, SLED_CAR_CLASS)
            pkt.car_performance_index = self._b(packet, SLED_CAR_PERFORMANCE_INDEX)
        elif is_fh4:
            # FH4 keeps the sled fields at their normal offsets, but shifts dash fields by a 12-byte header.
            dash_offset = FH4_HEADER_SIZE
            pkt.is_race_on = self._f(packet, SLED_IS_RACE_ON) > 0
            pkt.engine_max_rpm = self._f(packet, SLED_ENGINE_MAX_RPM)
            pkt.engine_idle_rpm = self._f(packet, SLED_ENGINE_IDLE_RPM)
            pkt.current_engine_rpm = self._f(packet, SLED_CURRENT_ENGINE_RPM)
            pkt.acceleration_x = self._f(packet, SLED_ACCEL_X)
            pkt.acceleration_y = self._f(packet, SLED_ACCEL_Y)
            pkt.acceleration_z = self._f(packet, SLED_ACCEL_Z)
            pkt.tire_combined_slip_fl = self._f(packet, SLED_TIRE_SLIP_FL)
            pkt.tire_combined_slip_fr = self._f(packet, SLED_TIRE_SLIP_FR)
            pkt.tire_combined_slip_rl = self._f(packet, SLED_TIRE_SLIP_RL)
            pkt.tire_combined_slip_rr = self._f(packet, SLED_TIRE_SLIP_RR)
            pkt.car_class = self._b(packet, SLED_CAR_CLASS)
            pkt.car_performance_index = self._b(packet, SLED_CAR_PERFORMANCE_INDEX)
        else:
            # FM8 dash-only
            # FM8 uses the same dash layout as FM7 combined format
            dash_offset = 0
            pkt.is_race_on = True

        # Parse dash section
        do = dash_offset
        pkt.speed = self._f(packet, DASH_COMBINED_SPEED + do)
        pkt.power = self._f(packet, DASH_COMBINED_POWER + do)
        pkt.torque = self._f(packet, DASH_COMBINED_TORQUE + do)
        pkt.boost = self._f(packet, DASH_COMBINED_BOOST + do)
        pkt.fuel = self._f(packet, DASH_COMBINED_FUEL + do)
        pkt.accelerator = self._b(packet, DASH_COMBINED_ACCELERATOR + do) / 255.0
        pkt.brake = self._b(packet, DASH_COMBINED_BRAKE + do) / 255.0
        pkt.clutch = self._b(packet, DASH_COMBINED_CLUTCH + do) / 255.0
        pkt.handbrake = self._b(packet, DASH_COMBINED_HANDBRAKE + do) / 255.0
        pkt.gear = self._b(packet, DASH_COMBINED_GEAR + do)
        pkt.steer = self._b_signed(packet, DASH_COMBINED_STEER + do)
        pkt.recompute_derived_fields()

        return pkt

    def expected_packet_size(self) -> int:
        return DASH_FM8_SIZE  # default

    @staticmethod
    def _f(data: bytes, offset: int) -> float:
        return struct.unpack_from("<f", data, offset)[0]

    @staticmethod
    def _b(data: bytes, offset: int) -> int:
        return data[offset]

    @staticmethod
    def _b_signed(data: bytes, offset: int) -> int:
        return struct.unpack_from("<b", data, offset)[0]
