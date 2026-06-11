"""GTK tray indicator: shows the Claude usage quota and refreshes on a timer."""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk, GLib  # noqa: E402
from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402

from formatting import format_label, format_menu_lines
from usage_client import Usage, AuthError, CredentialsError, NetworkError, UsageError

logger = logging.getLogger(__name__)

INDICATOR_ID = "claude-usage-indicator"
# A widely-available stock icon so we never ship binary assets.
ICON_NAME = "utilities-system-monitor-symbolic"


class Indicator:
    """Tray indicator wiring a fetch callable to a GTK label + menu."""

    def __init__(self, fetch: Callable[[], Usage], interval: int = 60):
        self._fetch = fetch
        self._interval = max(15, interval)
        self._last_usage: Optional[Usage] = None

        self._ind = AppIndicator.Indicator.new(
            INDICATOR_ID, ICON_NAME, AppIndicator.IndicatorCategory.SYSTEM_SERVICES
        )
        self._ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self._ind.set_label("Cl …", "")

        self._menu = Gtk.Menu()
        self._item_five = Gtk.MenuItem(label="Fenêtre 5h : …")
        self._item_seven = Gtk.MenuItem(label="Hebdo 7j : …")
        self._item_sonnet = Gtk.MenuItem(label="· Sonnet 7j : …")
        self._item_opus = Gtk.MenuItem(label="· Opus 7j : …")
        self._item_updated = Gtk.MenuItem(label="Dernière maj : …")
        for item in (self._item_five, self._item_seven, self._item_sonnet,
                     self._item_opus, self._item_updated):
            item.set_sensitive(False)
            self._menu.append(item)

        self._menu.append(Gtk.SeparatorMenuItem())
        refresh = Gtk.MenuItem(label="Rafraîchir maintenant")
        refresh.connect("activate", lambda _w: self._trigger_fetch())
        self._menu.append(refresh)
        quit_item = Gtk.MenuItem(label="Quitter")
        quit_item.connect("activate", lambda _w: Gtk.main_quit())
        self._menu.append(quit_item)

        self._menu.show_all()
        self._ind.set_menu(self._menu)

    # --- lifecycle -----------------------------------------------------------
    def start(self) -> None:
        """Do an initial fetch and start the periodic timer."""
        self._trigger_fetch()
        GLib.timeout_add_seconds(self._interval, self._on_timer)

    def _on_timer(self) -> bool:
        self._trigger_fetch()
        return True  # keep the timer running

    # --- fetch (off the UI thread) ------------------------------------------
    def _trigger_fetch(self) -> None:
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self) -> None:
        try:
            usage = self._fetch()
            GLib.idle_add(self._apply_usage, usage)
        except (AuthError, CredentialsError, NetworkError, UsageError) as exc:
            GLib.idle_add(self._apply_error, exc)
        except Exception as exc:  # noqa: BLE001 - last-resort guard, never crash the loop
            logger.exception("unexpected fetch error")
            GLib.idle_add(self._apply_error, exc)

    # --- UI updates (main thread only) --------------------------------------
    def _apply_usage(self, usage: Usage) -> bool:
        self._last_usage = usage
        self._ind.set_label(format_label(usage), "")
        lines = format_menu_lines(usage, datetime.now(timezone.utc))
        self._item_five.set_label(lines.five_hour)
        self._item_seven.set_label(lines.seven_day)
        self._item_sonnet.set_label(lines.sonnet)
        self._item_opus.set_label(lines.opus)
        self._item_updated.set_label(
            f"Dernière maj : {usage.fetched_at.astimezone().strftime('%H:%M:%S')}"
        )
        return False  # one-shot idle callback

    def _apply_error(self, exc: Exception) -> bool:
        if isinstance(exc, CredentialsError):
            self._ind.set_label("Cl ⚠", "")
            self._item_five.set_label("credentials Claude introuvables")
        elif isinstance(exc, AuthError):
            self._ind.set_label("Cl ⚠ auth", "")
            self._item_five.set_label("lance Claude Code pour rafraîchir le token")
        else:
            # Network/unexpected: keep last known label if we have one.
            if self._last_usage is None:
                self._ind.set_label("Cl ⚠", "")
            self._item_updated.set_label(f"hors-ligne — {datetime.now().strftime('%H:%M')}")
        logger.warning("usage fetch failed: %s", exc)
        return False
