import unittest
from datetime import datetime

from sportsbro.timeutils import isoformat_z, parse_clock_time


class TimeUtilsTests(unittest.TestCase):
    def test_isoformat_z_treats_naive_datetime_as_utc(self) -> None:
        self.assertEqual(isoformat_z(datetime(2026, 4, 15, 20, 36, 30)), "2026-04-15T20:36:30Z")

    def test_parse_clock_time_validates_clock_range(self) -> None:
        for value in ("0 PM", "13 PM", "12:60 PM"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_clock_time(value)

    def test_parse_clock_time_handles_boundaries(self) -> None:
        self.assertEqual(parse_clock_time("12 AM"), (0, 0))
        self.assertEqual(parse_clock_time("12:59 PM"), (12, 59))
