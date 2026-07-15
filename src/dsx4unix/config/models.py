"""Pydantic configuration models."""

from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class TriggerMode(str, Enum):
    OFF = "off"
    RESISTANCE = "resistance"
    VIBRATION = "vibration"
    HYBRID = "hybrid"
    CUSTOM = "custom"


class GameType(str, Enum):
    FORZA = "forza"
    DIRT = "dirt"
    NULL = "null"


class ThrottleSettings(BaseModel):
    trigger_mode: TriggerMode = TriggerMode.VIBRATION
    grip_loss_value: float = 0.6
    effect_intensity: float = 1.0
    turn_acceleration_scale: float = 0.25
    forward_acceleration_scale: float = 1.0
    acceleration_limit: int = 10
    vibration_mode_start: int = 5
    min_vibration: int = 5
    max_vibration: int = 55
    vibration_smoothing: float = 1.0
    min_stiffness: int = 255
    max_stiffness: int = 175
    min_resistance: int = 0
    max_resistance: int = 3
    resistance_smoothing: float = 0.9


class BrakeSettings(BaseModel):
    trigger_mode: TriggerMode = TriggerMode.VIBRATION
    effect_intensity: float = 1.0
    grip_loss_value: float = 0.05
    vibration_start: int = 0
    vibration_mode_start: int = 30
    min_vibration: int = 15
    max_vibration: int = 20
    vibration_smoothing: float = 1.0
    min_stiffness: int = 150
    max_stiffness: int = 5
    min_resistance: int = 0
    max_resistance: int = 7
    resistance_smoothing: float = 0.4


class LightBarSettings(BaseModel):
    rpm_redline_ratio: float = 0.9


class Profile(BaseModel):
    game: GameType = GameType.FORZA
    name: str = "Default"
    telemetry_port: int = 30778
    dsx_host: str = "127.0.0.1"
    dsx_port: int = 6969
    throttle: ThrottleSettings = Field(default_factory=ThrottleSettings)
    brake: BrakeSettings = Field(default_factory=BrakeSettings)
    lightbar: LightBarSettings = Field(default_factory=LightBarSettings)
    verbose: bool = False
