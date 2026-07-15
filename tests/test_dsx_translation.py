import unittest

from dsx4unix.config.models import ThrottleSettings, TriggerMode
from dsx4unix.dsx import LightBarInstruction, TriggerInstruction


class DsxTranslationTests(unittest.TestCase):
    def test_normal_translates_to_off(self):
        instr = TriggerInstruction(trigger="right", mode="Normal")
        self.assertEqual(instr.to_hefesto_parameters(), ["right", "Off"])

    def test_custom_translates_to_hefesto_custom_shape(self):
        instr = TriggerInstruction(
            trigger="right",
            mode="Custom",
            custom_mode="VibrateResistance",
            custom_forces=(23, 198, 5, 0, 0, 0, 0),
        )
        self.assertEqual(
            instr.to_hefesto_parameters(),
            ["right", "Custom", "VibrateResistance", 23, 198, 5, 0, 0, 0, 0],
        )

    def test_resistance_translates_to_hefesto_shape(self):
        instr = TriggerInstruction(
            trigger="left",
            mode="Resistance",
            stiffness=255,
            resistance=7,
        )
        self.assertEqual(instr.to_hefesto_parameters(), ["left", "Resistance", 9, 7])

    def test_vibration_translates_to_hefesto_shape(self):
        instr = TriggerInstruction(
            trigger="right",
            mode="Vibration",
            frequency=23,
            intensity=255,
        )
        self.assertEqual(instr.to_hefesto_parameters(), ["right", "Vibration", 0, 8, 23])

    def test_lightbar_translates_to_hefesto_shape(self):
        rgb = LightBarInstruction(red=228, green=255, blue=0)
        self.assertEqual(rgb.hefesto_parameters, [0, 228, 255, 0])

    def test_config_accepts_hybrid_alias_for_trigger_mode(self):
        settings = ThrottleSettings(trigger_mode="hybrid")
        self.assertEqual(settings.trigger_mode, TriggerMode.HYBRID)


if __name__ == "__main__":
    unittest.main()
