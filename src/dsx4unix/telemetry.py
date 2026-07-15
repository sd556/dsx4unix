"""Telemetry data packet — mirrors RacingDSX DataPacket."""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class TelemetryPacket:
    """Parsed telemetry data from a racing game."""

    # Race state
    is_race_on: bool = False
    car_class: int = 0
    car_performance_index: int = 0

    # Engine
    engine_max_rpm: float = 0.0
    engine_idle_rpm: float = 0.0
    current_engine_rpm: float = 0.0
    speed: float = 0.0
    power: float = 0.0
    torque: float = 0.0

    # Controls
    accelerator: float = 0.0  # 0–1
    brake: float = 0.0        # 0–1
    clutch: float = 0.0
    handbrake: float = 0.0
    gear: int = 0
    steer: int = 0

    # Acceleration (G-force)
    acceleration_x: float = 0.0  # lateral
    acceleration_y: float = 0.0  # vertical
    acceleration_z: float = 0.0  # forward

    # Tire slip
    tire_combined_slip_fl: float = 0.0
    tire_combined_slip_fr: float = 0.0
    tire_combined_slip_rl: float = 0.0
    tire_combined_slip_rr: float = 0.0
    front_left_contact_patch_v: float = 0.0

    # Derived
    four_wheel_combined_tire_slip: float = field(default=0.0, init=False)
    front_wheels_combined_tire_slip: float = field(default=0.0, init=False)
    rear_wheels_combined_tire_slip: float = field(default=0.0, init=False)

    # Extra fields for lightbar
    boost: float = 0.0
    fuel: float = 0.0

    def __post_init__(self) -> None:
        self.recompute_derived_fields()

    def recompute_derived_fields(self) -> None:
        self.four_wheel_combined_tire_slip = (
            abs(self.tire_combined_slip_fl)
            + abs(self.tire_combined_slip_fr)
            + abs(self.tire_combined_slip_rl)
            + abs(self.tire_combined_slip_rr)
        ) / 4.0
        self.front_wheels_combined_tire_slip = (
            abs(self.tire_combined_slip_fl) + abs(self.tire_combined_slip_fr)
        ) / 2.0
        self.rear_wheels_combined_tire_slip = (
            abs(self.tire_combined_slip_rl) + abs(self.tire_combined_slip_rr)
        ) / 2.0
