import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import _derive_label  # noqa: E402


class TestDeriveLabel(unittest.TestCase):
    def test_default_claude_dir(self):
        self.assertEqual(_derive_label(Path.home() / ".claude"), "Cl")

    def test_pro_suffix(self):
        self.assertEqual(_derive_label(Path("/home/user/.claude-pro")), "Pro")

    def test_perso_suffix(self):
        self.assertEqual(_derive_label(Path("/home/user/.claude-perso")), "Perso")

    def test_custom_non_claude_dir(self):
        self.assertEqual(_derive_label(Path("/tmp/custom")), "Custom")

    def test_trailing_dash_fallback(self):
        self.assertEqual(_derive_label(Path("/home/user/.claude-")), "Cl")


if __name__ == "__main__":
    unittest.main()
