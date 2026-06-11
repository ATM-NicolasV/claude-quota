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

## Autostart at login (from source)
    ./install.sh

## Install as a .deb package
Build the package (needs only `dpkg-deb`, already present on Debian/Ubuntu):

    ./build-deb.sh            # produces claude-usage-indicator_1.0.0_all.deb
    ./build-deb.sh 1.2.0      # optional explicit version

Install it (pulls in python3-gi and the AppIndicator typelib as dependencies):

    sudo apt install ./claude-usage-indicator_1.0.0_all.deb

The package installs the modules under `/usr/lib/claude-usage-indicator/`, a
`claude-usage-indicator` launcher in `/usr/bin/`, and a system-wide autostart
entry in `/etc/xdg/autostart/`, so the indicator starts at the next login for
each user (reading that user's own `~/.claude/.credentials.json`).

Remove with:

    sudo apt remove claude-usage-indicator

## Tests
    python3 -m unittest discover -s tests -v

## How it works
The app re-reads the OAuth token from `~/.claude/.credentials.json` on every poll
and calls the undocumented `https://api.anthropic.com/api/oauth/usage` endpoint
(Claude Code's own usage source). Token refresh is owned by Claude Code; if the
token is expired the indicator shows a degraded "auth" state until Claude Code
refreshes it. The endpoint is undocumented and may change without notice.
