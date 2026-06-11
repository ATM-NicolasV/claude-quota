import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from usage_client import parse_usage, Usage  # noqa: E402

NOMINAL = {
    "five_hour": {"utilization": 51.0, "resets_at": "2026-06-11T09:40:00.112854+00:00"},
    "seven_day": {"utilization": 23.0, "resets_at": "2026-06-13T10:59:59.112875+00:00"},
    "seven_day_opus": None,
    "seven_day_sonnet": {"utilization": 2.0, "resets_at": "2026-06-13T11:00:00.112884+00:00"},
}
FETCHED = datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc)


class TestParseUsage(unittest.TestCase):
    def test_nominal_fields(self):
        u = parse_usage(NOMINAL, fetched_at=FETCHED)
        self.assertIsInstance(u, Usage)
        self.assertEqual(u.five_hour_pct, 51.0)
        self.assertEqual(u.seven_day_pct, 23.0)
        self.assertEqual(u.sonnet_pct, 2.0)
        self.assertIsNone(u.opus_pct)
        self.assertEqual(u.five_hour_reset.year, 2026)
        self.assertEqual(u.five_hour_reset.hour, 9)
        self.assertEqual(u.fetched_at, FETCHED)

    def test_both_models_null(self):
        data = {**NOMINAL, "seven_day_sonnet": None, "seven_day_opus": None}
        u = parse_usage(data, fetched_at=FETCHED)
        self.assertIsNone(u.sonnet_pct)
        self.assertIsNone(u.opus_pct)


if __name__ == "__main__":
    unittest.main()
