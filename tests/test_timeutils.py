import unittest
from datetime import datetime

from kickoff.timeutils import isoformat_z


class TimeUtilsTests(unittest.TestCase):
    def test_isoformat_z_treats_naive_datetime_as_utc(self) -> None:
        self.assertEqual(isoformat_z(datetime(2026, 4, 15, 20, 36, 30)), "2026-04-15T20:36:30Z")
