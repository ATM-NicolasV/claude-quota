"""Entry point for the Claude usage tray indicator."""
from __future__ import annotations

import logging
import os
import signal

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib  # noqa: E402

from indicator import Indicator  # noqa: E402
from usage_client import fetch  # noqa: E402

DEFAULT_INTERVAL = 60


def _read_interval() -> int:
    raw = os.environ.get("CLAUDE_USAGE_INTERVAL", str(DEFAULT_INTERVAL))
    try:
        return max(15, int(raw))
    except ValueError:
        logging.warning("invalid CLAUDE_USAGE_INTERVAL=%r, using %d", raw, DEFAULT_INTERVAL)
        return DEFAULT_INTERVAL


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    interval = _read_interval()
    indicator = Indicator(fetch=fetch, interval=interval)
    indicator.start()

    # Allow Ctrl-C / SIGTERM to quit the GTK loop cleanly.
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, Gtk.main_quit)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, Gtk.main_quit)

    Gtk.main()


if __name__ == "__main__":
    main()
