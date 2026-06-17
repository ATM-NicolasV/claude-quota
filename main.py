"""Entry point for the Claude usage tray indicator."""
from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

DEFAULT_INTERVAL = 60

DEPENDENCY_HINT = (
    "Missing GTK / AppIndicator bindings (PyGObject + typelibs).\n"
    "Install them with:\n"
    "    sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1\n"
    "If you installed the .deb with 'dpkg -i', run 'sudo apt -f install' afterwards "
    "to pull missing dependencies (or install with 'sudo apt install ./<file>.deb')."
)


def _check_gtk_dependencies() -> None:
    """Fail early with an actionable message if the GTK bindings are absent.

    Covers both a missing python3-gi (ImportError on `import gi`) and missing
    GObject-Introspection typelibs (ValueError on require_version / ImportError
    on the repository import).
    """
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import Gtk, GLib, AyatanaAppIndicator3  # noqa: F401
    except (ImportError, ValueError) as exc:
        sys.stderr.write(f"{DEPENDENCY_HINT}\n\nDetails: {exc}\n")
        raise SystemExit(1)


def _read_interval() -> int:
    raw = os.environ.get("CLAUDE_USAGE_INTERVAL", str(DEFAULT_INTERVAL))
    try:
        return max(15, int(raw))
    except ValueError:
        logging.warning("invalid CLAUDE_USAGE_INTERVAL=%r, using %d", raw, DEFAULT_INTERVAL)
        return DEFAULT_INTERVAL


def _read_config_dir() -> Path:
    raw = os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))
    return Path(raw).expanduser()


def _derive_label(config_dir: Path) -> str:
    name = config_dir.name.lstrip(".").removeprefix("claude").lstrip("-")
    return (name or "Cl").capitalize()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _check_gtk_dependencies()

    # Imported lazily so the dependency check above can report a friendly
    # message before any GTK import would raise a raw traceback.
    from gi.repository import Gtk, GLib
    import functools
    from indicator import Indicator
    from usage_client import fetch

    interval = _read_interval()
    config_dir = _read_config_dir()
    label = _derive_label(config_dir)
    credentials_path = config_dir / ".credentials.json"
    fetch_fn = functools.partial(fetch, credentials_path=credentials_path)
    indicator = Indicator(fetch=fetch_fn, interval=interval, label=label)
    indicator.start()

    # Allow Ctrl-C / SIGTERM to quit the GTK loop cleanly.
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, Gtk.main_quit)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, Gtk.main_quit)

    Gtk.main()


if __name__ == "__main__":
    main()
