import unittest

from dsx4unix.config.models import BrakeSettings, ThrottleSettings
from dsx4unix.mapper import map_brake, map_throttle
from dsx4unix.telemetry import TelemetryPacket


class RacingDSXParityTests(unittest.TestCase):
    def test_throttle_vibration_mode_keeps_baseline_resistance_when_not_slipping(self):
        pkt = TelemetryPacket(
            acceleration_x=2.0,
            acceleration_z=6.0,
            accelerator=1.0,
            tire_combined_slip_fl=0.1,
            tire_combined_slip_fr=0.1,
            tire_combined_slip_rl=0.1,
            tire_combined_slip_rr=0.1,
        )

        instr, _ = map_throttle(pkt, ThrottleSettings(), prev_resistance=0.0)

        self.assertEqual(instr.mode, "Resistance")
        self.assertGreater(instr.resistance, 0)

    def test_throttle_vibration_mode_supports_rear_slip_under_hard_acceleration(self):
        pkt = TelemetryPacket(
            acceleration_x=1.0,
            acceleration_z=7.0,
            accelerator=0.9,
            tire_combined_slip_fl=0.1,
            tire_combined_slip_fr=0.1,
            tire_combined_slip_rl=2.4,
            tire_combined_slip_rr=2.2,
        )

        instr, _ = map_throttle(pkt, ThrottleSettings(), prev_resistance=0.0)

        self.assertEqual(instr.mode, "Custom")
        self.assertEqual(instr.custom_mode, "VibrateResistance")
        self.assertEqual(instr.custom_forces, (7, 198, 5, 0, 0, 0, 0))

    def test_brake_vibration_mode_uses_brake_threshold_before_switching_to_vibration(self):
        pkt = TelemetryPacket(
            acceleration_z=4.0,
            brake=0.7,
            tire_combined_slip_fl=5.0,
            tire_combined_slip_fr=5.0,
            tire_combined_slip_rl=4.0,
            tire_combined_slip_rr=4.0,
        )

        instr, _ = map_brake(pkt, BrakeSettings(), prev_resistance=0.0)

        self.assertEqual(instr.mode, "Custom")
        self.assertEqual(instr.custom_mode, "VibrateResistance")
        self.assertEqual(instr.custom_forces, (17, 48, 0, 0, 0, 0, 0))
    def test_headless_defaults_match_original_forza_throttle_tuning(self):
        """The native mapper defaults must retain the original FH4 pedal feel."""
        settings = ThrottleSettings()
        self.assertEqual(settings.effect_intensity, 1)
        self.assertEqual(settings.min_stiffness, 255)
        self.assertEqual(settings.max_stiffness, 175)
        self.assertEqual(settings.min_resistance, 0)
        self.assertEqual(settings.max_resistance, 3)
        self.assertEqual(settings.resistance_smoothing, 0.9)


if __name__ == "__main__":
    unittest.main()
