import struct
import unittest

from dsx4unix.parsers.forza import (
    DASH_FH4_SIZE,
    DASH_FM7_SIZE,
    FH4_HEADER_SIZE,
    SLED_ENGINE_IDLE_RPM,
    SLED_ENGINE_MAX_RPM,
    SLED_CURRENT_ENGINE_RPM,
    SLED_SIZE,
    SLED_TIRE_SLIP_FL,
    SLED_TIRE_SLIP_FR,
    SLED_TIRE_SLIP_RL,
    SLED_TIRE_SLIP_RR,
    ForzaParser,
)


class ForzaParserSlipDerivationTests(unittest.TestCase):
    def test_combined_slip_metrics_are_recomputed_from_parsed_packet(self):
        packet = bytearray(SLED_SIZE + DASH_FM7_SIZE)
        for offset, value in [
            (SLED_TIRE_SLIP_FL, 0.8),
            (SLED_TIRE_SLIP_FR, 0.7),
            (SLED_TIRE_SLIP_RL, 0.4),
            (SLED_TIRE_SLIP_RR, 0.2),
        ]:
            struct.pack_into("<f", packet, offset, value)

        pkt = ForzaParser().parse(bytes(packet))

        self.assertAlmostEqual(pkt.front_wheels_combined_tire_slip, 0.75, places=5)
        self.assertAlmostEqual(pkt.rear_wheels_combined_tire_slip, 0.30, places=5)
        self.assertAlmostEqual(pkt.four_wheel_combined_tire_slip, 0.525, places=5)

    def test_fh4_packet_reads_sled_fields_plus_dash_with_header_offset(self):
        packet = bytearray(DASH_FH4_SIZE)
        struct.pack_into("<f", packet, 0, 1.0)
        struct.pack_into("<f", packet, SLED_ENGINE_MAX_RPM, 8000.0)
        struct.pack_into("<f", packet, SLED_ENGINE_IDLE_RPM, 1000.0)
        struct.pack_into("<f", packet, SLED_CURRENT_ENGINE_RPM, 7000.0)
        for offset, value in [
            (SLED_TIRE_SLIP_FL, 0.9),
            (SLED_TIRE_SLIP_FR, 0.8),
            (SLED_TIRE_SLIP_RL, 0.7),
            (SLED_TIRE_SLIP_RR, 0.6),
        ]:
            struct.pack_into("<f", packet, offset, value)

        speed_offset = 244 + FH4_HEADER_SIZE
        accelerator_offset = 303 + FH4_HEADER_SIZE
        brake_offset = 304 + FH4_HEADER_SIZE
        gear_offset = 307 + FH4_HEADER_SIZE
        struct.pack_into("<f", packet, speed_offset, 33.0)
        packet[accelerator_offset] = 255
        packet[brake_offset] = 128
        packet[gear_offset] = 3

        pkt = ForzaParser().parse(bytes(packet))

        self.assertTrue(pkt.is_race_on)
        self.assertAlmostEqual(pkt.engine_max_rpm, 8000.0, places=5)
        self.assertAlmostEqual(pkt.engine_idle_rpm, 1000.0, places=5)
        self.assertAlmostEqual(pkt.current_engine_rpm, 7000.0, places=5)
        self.assertAlmostEqual(pkt.speed, 33.0, places=5)
        self.assertAlmostEqual(pkt.accelerator, 1.0, places=5)
        self.assertAlmostEqual(pkt.brake, 128 / 255.0, places=5)
        self.assertEqual(pkt.gear, 3)
        self.assertAlmostEqual(pkt.front_wheels_combined_tire_slip, 0.85, places=5)
        self.assertAlmostEqual(pkt.rear_wheels_combined_tire_slip, 0.65, places=5)
        self.assertAlmostEqual(pkt.four_wheel_combined_tire_slip, 0.75, places=5)


if __name__ == "__main__":
    unittest.main()
