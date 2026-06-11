# claude-usage-indicator — Design

**Date:** 2026-06-11
**Status:** Approved (ready for implementation plan)

## Goal

A small system-tray indicator for the GNOME top bar (top-right indicator area on
Ubuntu GNOME) that shows, live, the usage of the Claude Code subscription quota:
the 5-hour rolling window and the 7-day weekly limit — the same data shown by the
`/usage` command. Clicking the indicator opens a menu with the full breakdown and
reset times.

## Context / Environment

- Ubuntu GNOME, X11. `ubuntu-appindicators` extension enabled (tray works natively).
- Python 3 with PyGObject already installed. `AyatanaAppIndicator3 0.1`, `Gtk 3.0`,
  `GLib` all available. **No extra dependency to install.**
- HTTP done with the Python **stdlib `urllib`** — no `requests` dependency.

## Data source (feasibility confirmed, tested live)

Undocumented endpoint used internally by Claude Code:

```
GET https://api.anthropic.com/api/oauth/usage
Headers:
  Authorization: Bearer <oauth_access_token>
  anthropic-beta: oauth-2025-04-20
  User-Agent: claude-code/<version>
  Content-Type: application/json
```

OAuth token read from `~/.claude/.credentials.json` →
`claudeAiOauth.accessToken` (format `sk-ant-oat01-...`).

Verified response shape (live):

```json
{
  "five_hour":  { "utilization": 51.0, "resets_at": "2026-06-11T09:40:00+00:00" },
  "seven_day":  { "utilization": 23.0, "resets_at": "2026-06-13T10:59:59+00:00" },
  "seven_day_opus":   null,
  "seven_day_sonnet": { "utilization": 2.0, "resets_at": "..." },
  "extra_usage": { "is_enabled": false, "monthly_limit": null, "...": null }
}
```

`utilization` is a percentage 0–100. Model-specific fields may be `null`.

**Caveat (documented risk):** the endpoint is undocumented and could change or be
removed by Anthropic without notice. The app must degrade gracefully if it changes.

## Token strategy (DIP — depend on a contract we don't own as little as possible)

The app **re-reads `~/.claude/.credentials.json` on every poll** rather than
implementing its own OAuth refresh. Claude Code already owns and refreshes that
file; we depend on that file as the single source of truth. The OAuth refresh
flow's `client_id` is not reliably known, so we deliberately do NOT implement
refresh ourselves. If the token is expired and Claude Code has not refreshed it,
we show an explicit degraded state and tell the user to run Claude Code.

## Architecture

Three modules, one responsibility each (SRP):

```
claude-usage-indicator/
├── usage_client.py   # network/IO: read token, call endpoint, parse -> Usage
├── indicator.py      # tray UI: label + menu, GLib refresh timer
├── main.py           # entry point: wire client + indicator, run Gtk.main()
├── claude-usage-indicator.desktop   # autostart entry (installed to ~/.config/autostart/)
├── install.sh        # copy .desktop to ~/.config/autostart, make runnable
└── docs/superpowers/specs/2026-06-11-claude-usage-indicator-design.md
```

### `usage_client.py`
- `read_token() -> str` : load `claudeAiOauth.accessToken` and `expiresAt` from the
  credentials JSON. Raises a typed error (`CredentialsError`) if file/key missing.
- `Usage` dataclass: `five_hour_pct`, `five_hour_reset` (datetime),
  `seven_day_pct`, `seven_day_reset`, `sonnet_pct`, `opus_pct`, `fetched_at`.
- `fetch() -> Usage` : read token, GET endpoint via `urllib.request`, parse JSON,
  map to `Usage`. Handles `null` model fields. Raises typed errors:
  - `CredentialsError` (no file/key)
  - `AuthError` (HTTP 401 / token rejected)
  - `NetworkError` (timeout, connection, non-200)
- No GTK import here — pure logic, unit-testable without a display or network.

### `indicator.py`
- Builds an `AyatanaAppIndicator3.Indicator` with an icon + text label.
- Holds last-known `Usage` and last error.
- `refresh()` : call `client.fetch()` in a worker thread (so the UI never blocks on
  network), then schedule the UI update on the GLib main loop. On success update
  label + menu; on typed error set the matching degraded state.
- GLib timer every `interval` seconds (default 60, override via env
  `CLAUDE_USAGE_INTERVAL`).
- Menu items: 5h line, 7d line, Sonnet/Opus lines, separator, "Rafraîchir
  maintenant", "Dernière maj : HH:MM:SS", "Quitter".

### `main.py`
- Parse env config (interval), construct `UsageClient` and `Indicator`, do an
  initial refresh, start `Gtk.main()`. Handle `SIGINT`/`SIGTERM` for clean quit.

## Data flow

1. GLib timer fires every 60 s (and once at startup).
2. Worker thread: `usage_client.fetch()` → re-read token → GET endpoint → parse.
3. Result (or typed error) handed back to the GLib main loop.
4. `indicator` updates the compact bar label and the detail menu.

## Display

- **Bar label (compact):** `Cl 51% · 23%` (5h · 7d), prefixed by a colour dot
  derived from `max(five_hour, seven_day)`: 🟢 `<70`, 🟠 `70–90`, 🔴 `>90`.
- **Menu:**
  - `Fenêtre 5h : 51 % — reset à 11:40 (dans 2 h 47)`
  - `Hebdo 7j : 23 % — reset jeu. 13/06 11:00`
  - `· Sonnet 7j : 2 %`
  - `· Opus 7j : —`  (shown as `—` when null)
  - ─────
  - `Rafraîchir maintenant`
  - `Dernière maj : 08:53:12`
  - `Quitter`

User-facing menu strings are in French (product language). All code, comments,
identifiers, and logs are in English.

## Error handling (graceful degradation)

| Situation                     | Bar label    | Menu hint                                            |
|-------------------------------|--------------|------------------------------------------------------|
| credentials file/key missing  | `Cl ⚠`       | « credentials Claude introuvables »                  |
| HTTP 401 / token expired      | `Cl ⚠ auth`  | « lance Claude Code pour rafraîchir le token »       |
| network down / timeout / non-200 | last value + ⚠ | « hors-ligne — dernière maj HH:MM », retry next tick |

- Network call runs off the UI thread; the UI never freezes.
- All `except` clauses are typed; never log the token or any secret.
- Structured logging via `logging` to stderr (levels debug/info/warn/error).

## Deployment

- Run: `python3 main.py`.
- Autostart: `install.sh` copies `claude-usage-indicator.desktop` into
  `~/.config/autostart/` so it launches at login.
- Standalone folder `~/claude-usage-indicator/` with its own git repo (separate
  from the `lastsignal` repo).

## Testing

- `usage_client` unit-tested in isolation, no real network:
  - parse a mocked nominal JSON → correct `Usage` (percentages, datetimes).
  - `opus`/`sonnet` null → `None` fields, no crash.
  - 401 response → `AuthError`.
  - missing file/key → `CredentialsError`.
  - timeout/connection error → `NetworkError`.
- `indicator` label/menu formatting tested via pure formatter helpers (no GTK):
  extract `format_label(usage)` and `format_menu_lines(usage)` as pure functions.

## Out of scope (YAGNI)

- No OAuth refresh implementation (rely on Claude Code's credentials file).
- No historical graphs / persistence.
- No config GUI (env var is enough).
- No packaging beyond the autostart `.desktop` (no .deb / pip package for now).
