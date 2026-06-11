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


@dataclass
class MenuText:
    five_hour: str
    seven_day: str
    sonnet: str
    opus: str


def humanize_delta(target: datetime, now: datetime) -> str:
    """Relative time until target, e.g. 'dans 2 h 47', 'dans 12 min', 'maintenant'."""
    total_minutes = int((target - now).total_seconds() // 60)
    if total_minutes <= 0:
        return "maintenant"
    hours, minutes = divmod(total_minutes, 60)
    if hours == 0:
        return f"dans {minutes} min"
    return f"dans {hours} h {minutes:02d}"


def _local_time(dt: datetime) -> str:
    return dt.astimezone().strftime("%H:%M")


def _local_date(dt: datetime) -> str:
    local = dt.astimezone()
    return f"{FR_DAYS[local.weekday()]} {local.strftime('%d/%m')}"


def _pct_line(prefix: str, pct: Optional[float]) -> str:
    value = f"{pct:.0f} %" if pct is not None else "—"
    return f"{prefix} : {value}"


def format_menu_lines(usage: Usage, now: datetime) -> MenuText:
    """Build the four detail lines shown in the indicator menu."""
    five = (
        f"Fenêtre 5h : {usage.five_hour_pct:.0f} % — reset à "
        f"{_local_time(usage.five_hour_reset)} ({humanize_delta(usage.five_hour_reset, now)})"
    )
    seven = (
        f"Hebdo 7j : {usage.seven_day_pct:.0f} % — reset "
        f"{_local_date(usage.seven_day_reset)} {_local_time(usage.seven_day_reset)}"
    )
    return MenuText(
        five_hour=five,
        seven_day=seven,
        sonnet=_pct_line("· Sonnet 7j", usage.sonnet_pct),
        opus=_pct_line("· Opus 7j", usage.opus_pct),
    )
