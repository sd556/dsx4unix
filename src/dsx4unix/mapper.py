"""Trigger mapper — converts telemetry to DSX trigger instructions.

Implements the same logic as RacingDSX:
- Resistance mode: maps throttle/brake input to continuous resistance
- Vibration mode: adds pulsing vibration when tires lose grip
- Lightbar: RPM-based color (green → yellow → red)
"""

from __future__ import annotations

import math

from dsx4unix.config.models import (
    BrakeSettings,
    LightBarSettings,
    ThrottleSettings,
    TriggerMode as TM,
)
from dsx4unix.dsx import LightBarInstruction, TriggerInstruction
from dsx4unix.telemetry import TelemetryPacket


def _ewma(current: float, previous: float, alpha: float) -> float:
    """Exponentially weighted moving average."""
    return alpha * current + (1.0 - alpha) * previous


def _map_range(x: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    """Clamp x to the input range and map it linearly to the output range."""
    if in_max == in_min:
        return out_min
    x = min(max(x, in_min), in_max)
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def map_throttle(
    pkt: TelemetryPacket,
    settings: ThrottleSettings,
    prev_resistance: float,
) -> tuple[TriggerInstruction, float]:
    """Map throttle telemetry to right trigger instruction."""
    accel_metric = math.sqrt(
        settings.turn_acceleration_scale * (pkt.acceleration_x ** 2)
        + settings.forward_acceleration_scale * (pkt.acceleration_z ** 2)
    )
    accel_metric = min(accel_metric, settings.acceleration_limit)

    front_slip = pkt.front_wheels_combined_tire_slip
    rear_slip = pkt.rear_wheels_combined_tire_slip
    four_wheel_slip = pkt.four_wheel_combined_tire_slip
    accelerator_raw = pkt.accelerator * 255.0

    baseline_resistance = _map_range(
        accel_metric,
        0,
        settings.acceleration_limit,
        settings.min_resistance,
        settings.max_resistance,
    )
    filtered_baseline_resistance = _ewma(
        baseline_resistance,
        prev_resistance,
        settings.resistance_smoothing,
    )

    if settings.trigger_mode == TM.OFF:
        return TriggerInstruction(trigger="right", mode="Normal"), filtered_baseline_resistance

    if settings.trigger_mode == TM.RESISTANCE:
        ratio = accel_metric / settings.acceleration_limit if settings.acceleration_limit else 0
        resistance_level = int(
            settings.min_resistance
            + ratio * (settings.max_resistance - settings.min_resistance)
        )
        stiffness = int(
            settings.min_stiffness
            + ratio * (settings.max_stiffness - settings.min_stiffness)
        )
        return TriggerInstruction(
            trigger="right",
            mode="Resistance",
            stiffness=stiffness,
            resistance=resistance_level,
        ), filtered_baseline_resistance

    losing_accel_grip = front_slip > settings.grip_loss_value or (
        rear_slip > settings.grip_loss_value and accelerator_raw > 200
    )

    if losing_accel_grip:
        vibration = int(_map_range(
            four_wheel_slip,
            settings.grip_loss_value,
            5.0,
            0,
            settings.max_vibration,
        ))
        vibration = max(0, min(settings.max_vibration, vibration))
        hybrid_resistance = int(_map_range(
            accel_metric,
            0,
            settings.acceleration_limit,
            settings.min_stiffness,
            settings.max_stiffness,
        ))

        if vibration <= settings.min_vibration or accelerator_raw <= settings.vibration_mode_start:
            resistance_level = int(filtered_baseline_resistance)
            return TriggerInstruction(
                trigger="right",
                mode="Resistance",
                stiffness=settings.min_stiffness,
                resistance=resistance_level,
            ), filtered_baseline_resistance

        return TriggerInstruction(
            trigger="right",
            mode="Custom",
            custom_mode="VibrateResistance",
            custom_forces=(
                int(vibration * settings.effect_intensity),
                max(0, min(255, int(hybrid_resistance * settings.effect_intensity))),
                max(0, min(255, int(settings.vibration_mode_start))),
                0,
                0,
                0,
                0,
            ),
        ), filtered_baseline_resistance

    resistance_level = int(filtered_baseline_resistance)
    return TriggerInstruction(
        trigger="right",
        mode="Resistance",
        stiffness=settings.min_stiffness,
        resistance=resistance_level,
    ), filtered_baseline_resistance


def map_brake(
    pkt: TelemetryPacket,
    settings: "BrakeSettings",
    prev_resistance: float,
) -> tuple[TriggerInstruction, float]:
    """Map brake telemetry to left trigger instruction."""
    from dsx4unix.config.models import BrakeSettings  # noqa: F811

    accel_metric = min(abs(pkt.acceleration_z), 10)
    four_wheel_slip = pkt.four_wheel_combined_tire_slip
    brake_raw = pkt.brake * 255.0

    baseline_resistance = _map_range(
        brake_raw,
        0,
        255,
        settings.min_resistance,
        settings.max_resistance,
    )
    filtered_baseline_resistance = _ewma(
        baseline_resistance,
        prev_resistance,
        settings.resistance_smoothing,
    )

    if settings.trigger_mode == TM.OFF:
        return TriggerInstruction(trigger="left", mode="Normal"), filtered_baseline_resistance

    if settings.trigger_mode == TM.RESISTANCE:
        ratio = accel_metric / 10
        resistance_level = int(
            settings.min_resistance
            + ratio * (settings.max_resistance - settings.min_resistance)
        )
        stiffness = int(
            settings.min_stiffness
            + ratio * (settings.max_stiffness - settings.min_stiffness)
        )
        return TriggerInstruction(
            trigger="left",
            mode="Resistance",
            stiffness=stiffness,
            resistance=resistance_level,
        ), filtered_baseline_resistance

    losing_brake_grip = four_wheel_slip > settings.grip_loss_value and brake_raw > 100

    if losing_brake_grip:
        vibration = int(_map_range(
            four_wheel_slip,
            settings.grip_loss_value,
            5.0,
            0,
            settings.max_vibration,
        ))
        vibration = max(0, min(settings.max_vibration, vibration))
        hybrid_resistance = int(_map_range(
            brake_raw,
            0,
            255,
            settings.min_stiffness,
            settings.max_stiffness,
        ))

        if vibration <= settings.min_vibration:
            resistance_level = int(filtered_baseline_resistance)
            return TriggerInstruction(
                trigger="left",
                mode="Resistance",
                stiffness=settings.min_stiffness,
                resistance=resistance_level,
            ), filtered_baseline_resistance

        return TriggerInstruction(
            trigger="left",
            mode="Custom",
            custom_mode="VibrateResistance",
            custom_forces=(
                int(vibration * settings.effect_intensity),
                max(0, min(255, int(hybrid_resistance * settings.effect_intensity))),
                max(0, min(255, int(settings.vibration_start))),
                0,
                0,
                0,
                0,
            ),
        ), filtered_baseline_resistance

    resistance_level = int(filtered_baseline_resistance)
    return TriggerInstruction(
        trigger="left",
        mode="Resistance",
        stiffness=settings.min_stiffness,
        resistance=resistance_level,
    ), filtered_baseline_resistance


def map_lightbar(
    pkt: TelemetryPacket,
    settings: LightBarSettings,
) -> LightBarInstruction:
    """Map RPM to lightbar color (green → yellow → red)."""
    if pkt.engine_max_rpm <= pkt.engine_idle_rpm:
        rpm_ratio = 0.0
    else:
        rpm_ratio = (pkt.current_engine_rpm - pkt.engine_idle_rpm) / (
            pkt.engine_max_rpm - pkt.engine_idle_rpm
        )

    redline_start = settings.rpm_redline_ratio

    if rpm_ratio < redline_start:
        # Green → Yellow
        t = rpm_ratio / redline_start
        r = int(t * 255)
        g = 255
        b = 0
    else:
        # Yellow → Red
        t = (rpm_ratio - redline_start) / (1.0 - redline_start)
        r = 255
        g = int((1.0 - t) * 255)
        b = 0

    return LightBarInstruction(
        red=min(255, max(0, r)),
        green=min(255, max(0, g)),
        blue=min(255, max(0, b)),
    )
