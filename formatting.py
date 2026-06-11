"""Pure presentation helpers for the usage indicator (no GTK, no IO)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from usage_client import Usage

# French weekday abbreviations indexed by datetime.weekday() (Mon=0).
FR_DAYS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]


def color_dot(pct: float) -> str:
    """Traffic-light dot for a utilization percentage."""
    if pct > 90:
        return "🔴"
    if pct >= 70:
        return "🟠"
    return "🟢"


def format_label(usage: Usage) -> str:
    """Compact top-bar label, e.g. '🟢 51% · 23%' (5h · 7d)."""
    worst = max(usage.five_hour_pct, usage.seven_day_pct)
    return f"{color_dot(worst)} {usage.five_hour_pct:.0f}% · {usage.seven_day_pct:.0f}%"
