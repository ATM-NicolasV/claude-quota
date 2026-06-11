# claude-usage-indicator

GNOME top-bar tray indicator showing the live Claude Code subscription quota
(5-hour rolling window + 7-day weekly), the same data as the `/usage` command.

## Requirements
- Ubuntu GNOME (or any GNOME with the AppIndicator extension enabled).
- Python 3 with PyGObject + `AyatanaAppIndicator3` (preinstalled on Ubuntu GNOME).
- An active Claude Code login (token read from `~/.claude/.credentials.json`).

## Run
    python3 main.py

Refresh interval (seconds) is configurable:
    CLAUDE_USAGE_INTERVAL=120 python3 main.py

## Autostart at login
    ./install.sh

## Tests
    python3 -m unittest discover -s tests -v

## How it works
The app re-reads the OAuth token from `~/.claude/.credentials.json` on every poll
and calls the undocumented `https://api.anthropic.com/api/oauth/usage` endpoint
(Claude Code's own usage source). Token refresh is owned by Claude Code; if the
token is expired the indicator shows a degraded "auth" state until Claude Code
refreshes it. The endpoint is undocumented and may change without notice.
