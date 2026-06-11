import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from formatting import color_dot, format_label  # noqa: E402
from usage_client import Usage  # noqa: E402


def make_usage(five=51.0, seven=23.0, sonnet=2.0, opus=None):
    base = datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc)
    return Usage(
        five_hour_pct=five, five_hour_reset=base,
        seven_day_pct=seven, seven_day_reset=base,
        sonnet_pct=sonnet, opus_pct=opus, fetched_at=base,
    )


class TestColorDot(unittest.TestCase):
    def test_green_below_70(self):
        self.assertEqual(color_dot(69.9), "🟢")

    def test_orange_70_to_90(self):
        self.assertEqual(color_dot(70.0), "🟠")
        self.assertEqual(color_dot(90.0), "🟠")

    def test_red_above_90(self):
        self.assertEqual(color_dot(90.1), "🔴")


class TestFormatLabel(unittest.TestCase):
    def test_uses_worst_of_two_for_dot(self):
        label = format_label(make_usage(five=95.0, seven=23.0))
        self.assertTrue(label.startswith("🔴"))
        self.assertIn("95%", label)
        self.assertIn("23%", label)


from formatting import humanize_delta, format_menu_lines, MenuText  # noqa: E402
from datetime import timedelta  # noqa: E402


class TestHumanizeDelta(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc)

    def test_future_hours_and_minutes(self):
        target = self.now + timedelta(hours=2, minutes=47)
        self.assertEqual(humanize_delta(target, self.now), "dans 2 h 47")

    def test_future_minutes_only(self):
        target = self.now + timedelta(minutes=12)
        self.assertEqual(humanize_delta(target, self.now), "dans 12 min")

    def test_past_or_now(self):
        target = self.now - timedelta(minutes=1)
        self.assertEqual(humanize_delta(target, self.now), "maintenant")


class TestFormatMenuLines(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc)

    def test_lines_contain_percentages(self):
        m = format_menu_lines(make_usage(five=51.0, seven=23.0, sonnet=2.0, opus=None), self.now)
        self.assertIsInstance(m, MenuText)
        self.assertIn("51", m.five_hour)
        self.assertIn("23", m.seven_day)
        self.assertIn("2", m.sonnet)
        self.assertIn("—", m.opus)  # null opus shows an em dash


if __name__ == "__main__":
    unittest.main()
