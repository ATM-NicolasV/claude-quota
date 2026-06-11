# claude-usage-indicator

GNOME top-bar tray indicator showing the live Claude Code subscription quota
(5-hour rolling window + 7-day weekly), the same data as the `/usage` command.

## Layout
- `usage_client.py` — read OAuth token from `~/.claude/.credentials.json`, call the
  `/api/oauth/usage` endpoint, parse into a `Usage` dataclass. Network/IO + typed errors.
- `formatting.py` — pure presentation helpers (label, menu lines). No GTK, no IO.
- `indicator.py` — GTK/AyatanaAppIndicator3 tray wiring + GLib refresh timer (threaded fetch).
- `main.py` — entry point: config (`CLAUDE_USAGE_INTERVAL`), wiring, signal handling.
- `install.sh` — per-user autostart install (generates the `.desktop` with the
  absolute app path into `~/.config/autostart`).
- `build-deb.sh` — assemble and build the `.deb` (system install + `/etc/xdg/autostart`).

## Conventions
- Python 3, stdlib only at runtime except PyGObject. Tests use stdlib `unittest`.
- Code, comments, identifiers, logs in English. User-facing menu strings in French.
- Never log the OAuth token or any secret.

## Commands
- Run: `python3 main.py`
- Tests: `python3 -m unittest discover -s tests -v`
- Autostart (from source): `./install.sh`
- Build .deb: `./build-deb.sh [version]` (uses only `dpkg-deb`; output is gitignored)

## Notes
- The usage endpoint is undocumented and may change without notice; the app degrades
  gracefully (auth / offline states) rather than crashing.
- Token refresh is owned by Claude Code; we only read the credentials file.
- `main.py` runs `_check_gtk_dependencies()` before importing GTK, so a missing
  `python3-gi` or AppIndicator typelib prints an actionable `apt install` hint and
  exits cleanly instead of a raw traceback. GTK imports are therefore lazy (inside
  `main()`), which also keeps `import main` GTK-free for tests.
- Install the `.deb` with `apt install ./pkg.deb` (resolves deps), not `dpkg -i`.
- `install.sh` writes the autostart `Exec` as an absolute path resolved at install
  time. The Desktop Entry spec has no home-directory field code (only
  `%f %F %u %U %i %c %k`), so a placeholder like `%h` is silently dropped by the
  launcher and the entry fails to start — hence the path is generated, not shipped.
