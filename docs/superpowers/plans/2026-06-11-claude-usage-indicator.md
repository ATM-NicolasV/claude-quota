# claude-usage-indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A GNOME top-bar tray indicator showing the live Claude Code subscription quota (5-hour window + 7-day weekly), with a detail menu.

**Architecture:** Three focused modules — `usage_client.py` (token read + HTTP + parse → `Usage`), `formatting.py` (pure presentation helpers), `indicator.py` (GTK tray wiring + GLib refresh timer) — assembled by `main.py`. Network IO runs off the UI thread; the token is re-read from `~/.claude/.credentials.json` on every poll (Claude Code owns the refresh).

**Tech Stack:** Python 3, PyGObject (`AyatanaAppIndicator3 0.1`, `Gtk 3.0`, `GLib`), stdlib `urllib` for HTTP, stdlib `unittest` for tests (no third-party dependency). Working dir: `~/claude-usage-indicator/`.

---

## File Structure

```
claude-usage-indicator/
├── usage_client.py          # Usage dataclass, read_token, parse_usage, fetch, typed errors
├── formatting.py            # color_dot, format_label, humanize_delta, format_menu_lines, MenuText
├── indicator.py             # Indicator class: GTK tray icon/label/menu + refresh timer
├── main.py                  # entry point: config, wiring, signals, Gtk.main()
├── install.sh               # copy .desktop into ~/.config/autostart
├── claude-usage-indicator.desktop   # autostart entry
├── pytest.ini               # (unused for unittest, omitted)
├── README.md
└── tests/
    ├── test_usage_client.py
    └── test_formatting.py
```

Run tests from project root with: `python3 -m unittest discover -s tests -v`

---

### Task 1: `usage_client` — `Usage` dataclass + `parse_usage`

**Files:**
- Create: `usage_client.py`
- Test: `tests/test_usage_client.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_usage_client.py`:

```python
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from usage_client import parse_usage, Usage  # noqa: E402

NOMINAL = {
    "five_hour": {"utilization": 51.0, "resets_at": "2026-06-11T09:40:00.112854+00:00"},
    "seven_day": {"utilization": 23.0, "resets_at": "2026-06-13T10:59:59.112875+00:00"},
    "seven_day_opus": None,
    "seven_day_sonnet": {"utilization": 2.0, "resets_at": "2026-06-13T11:00:00.112884+00:00"},
}
FETCHED = datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc)


class TestParseUsage(unittest.TestCase):
    def test_nominal_fields(self):
        u = parse_usage(NOMINAL, fetched_at=FETCHED)
        self.assertIsInstance(u, Usage)
        self.assertEqual(u.five_hour_pct, 51.0)
        self.assertEqual(u.seven_day_pct, 23.0)
        self.assertEqual(u.sonnet_pct, 2.0)
        self.assertIsNone(u.opus_pct)
        self.assertEqual(u.five_hour_reset.year, 2026)
        self.assertEqual(u.five_hour_reset.hour, 9)
        self.assertEqual(u.fetched_at, FETCHED)

    def test_both_models_null(self):
        data = {**NOMINAL, "seven_day_sonnet": None, "seven_day_opus": None}
        u = parse_usage(data, fetched_at=FETCHED)
        self.assertIsNone(u.sonnet_pct)
        self.assertIsNone(u.opus_pct)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_usage_client -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'usage_client'`

- [ ] **Step 3: Write minimal implementation**

Create `usage_client.py`:

```python
"""Read the local Claude OAuth token and fetch subscription usage quotas."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
BETA_HEADER = "oauth-2025-04-20"
# User-Agent is required: without it the endpoint throttles aggressively.
USER_AGENT = "claude-code/2.1.173"
REQUEST_TIMEOUT = 10  # seconds


class UsageError(Exception):
    """Base class for usage client errors."""


class CredentialsError(UsageError):
    """Credentials file or token missing/unreadable."""


class AuthError(UsageError):
    """Token rejected by the server (HTTP 401)."""


class NetworkError(UsageError):
    """Network failure, timeout, or unexpected response."""


@dataclass
class Usage:
    five_hour_pct: float
    five_hour_reset: datetime
    seven_day_pct: float
    seven_day_reset: datetime
    sonnet_pct: Optional[float]
    opus_pct: Optional[float]
    fetched_at: datetime


def _section_pct(data: dict, key: str) -> Optional[float]:
    section = data.get(key)
    if not section:
        return None
    return section.get("utilization")


def _section_reset(data: dict, key: str) -> datetime:
    section = data.get(key)
    if not section or "resets_at" not in section:
        raise NetworkError(f"missing '{key}.resets_at' in response")
    return datetime.fromisoformat(section["resets_at"])


def parse_usage(data: dict, *, fetched_at: datetime) -> Usage:
    """Map the raw endpoint JSON to a Usage. Pure; raises NetworkError on bad shape."""
    try:
        return Usage(
            five_hour_pct=float(data["five_hour"]["utilization"]),
            five_hour_reset=_section_reset(data, "five_hour"),
            seven_day_pct=float(data["seven_day"]["utilization"]),
            seven_day_reset=_section_reset(data, "seven_day"),
            sonnet_pct=_section_pct(data, "seven_day_sonnet"),
            opus_pct=_section_pct(data, "seven_day_opus"),
            fetched_at=fetched_at,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise NetworkError(f"unexpected response shape: {exc}") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_usage_client -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/claude-usage-indicator
git add usage_client.py tests/test_usage_client.py
git commit -m "feat: Usage dataclass and parse_usage"
```

---

### Task 2: `usage_client` — `read_token`

**Files:**
- Modify: `usage_client.py`
- Test: `tests/test_usage_client.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_usage_client.py` (before the `if __name__` block):

```python
import json as _json
import tempfile


class TestReadToken(unittest.TestCase):
    def _write_creds(self, payload: dict) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        _json.dump(payload, tmp)
        tmp.close()
        return Path(tmp.name)

    def test_reads_access_token(self):
        from usage_client import read_token
        path = self._write_creds({"claudeAiOauth": {"accessToken": "sk-ant-oat01-x"}})
        self.assertEqual(read_token(path), "sk-ant-oat01-x")

    def test_missing_file_raises_credentials_error(self):
        from usage_client import read_token, CredentialsError
        with self.assertRaises(CredentialsError):
            read_token(Path("/nonexistent/creds.json"))

    def test_missing_key_raises_credentials_error(self):
        from usage_client import read_token, CredentialsError
        path = self._write_creds({"claudeAiOauth": {}})
        with self.assertRaises(CredentialsError):
            read_token(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_usage_client.TestReadToken -v`
Expected: FAIL — `ImportError: cannot import name 'read_token'`

- [ ] **Step 3: Write minimal implementation**

Add to `usage_client.py` (after the `Usage` dataclass, before `_section_pct`):

```python
def read_token(credentials_path: Path = CREDENTIALS_PATH) -> str:
    """Return the Claude OAuth access token from the local credentials file."""
    try:
        with open(credentials_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data["claudeAiOauth"]["accessToken"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError, TypeError) as exc:
        raise CredentialsError(f"cannot read Claude credentials: {exc}") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_usage_client.TestReadToken -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add usage_client.py tests/test_usage_client.py
git commit -m "feat: read_token from local credentials"
```

---

### Task 3: `usage_client` — `fetch` (HTTP, mocked)

**Files:**
- Modify: `usage_client.py`
- Test: `tests/test_usage_client.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_usage_client.py`:

```python
from unittest import mock
import io
import urllib.error


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class TestFetch(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        _json.dump({"claudeAiOauth": {"accessToken": "sk-ant-oat01-x"}}, tmp)
        tmp.close()
        self.creds = Path(tmp.name)

    def test_fetch_success(self):
        from usage_client import fetch
        body = _json.dumps(NOMINAL).encode("utf-8")
        with mock.patch("usage_client.urllib.request.urlopen", return_value=_FakeResp(body)):
            u = fetch(self.creds)
        self.assertEqual(u.five_hour_pct, 51.0)
        self.assertEqual(u.seven_day_pct, 23.0)

    def test_fetch_401_raises_auth_error(self):
        from usage_client import fetch, AuthError
        err = urllib.error.HTTPError(USAGE_URL, 401, "Unauthorized", {}, None)
        with mock.patch("usage_client.urllib.request.urlopen", side_effect=err):
            with self.assertRaises(AuthError):
                fetch(self.creds)

    def test_fetch_network_failure_raises_network_error(self):
        from usage_client import fetch, NetworkError
        err = urllib.error.URLError("connection refused")
        with mock.patch("usage_client.urllib.request.urlopen", side_effect=err):
            with self.assertRaises(NetworkError):
                fetch(self.creds)


from usage_client import USAGE_URL  # noqa: E402  (used by TestFetch)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_usage_client.TestFetch -v`
Expected: FAIL — `ImportError: cannot import name 'fetch'`

- [ ] **Step 3: Write minimal implementation**

Add to `usage_client.py` (at the end of the file):

```python
def fetch(credentials_path: Path = CREDENTIALS_PATH) -> Usage:
    """Read the token, call the usage endpoint, return a parsed Usage.

    Raises CredentialsError, AuthError, or NetworkError on failure.
    """
    token = read_token(credentials_path)
    request = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": BETA_HEADER,
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise AuthError("token rejected (401)") from exc
        raise NetworkError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise NetworkError(f"network failure: {exc.reason}") from exc
    except (TimeoutError, OSError) as exc:
        raise NetworkError(f"request failed: {exc}") from exc
    return parse_usage(payload, fetched_at=datetime.now(timezone.utc))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_usage_client -v`
Expected: PASS (all usage_client tests)

- [ ] **Step 5: Commit**

```bash
git add usage_client.py tests/test_usage_client.py
git commit -m "feat: fetch usage from oauth endpoint with typed errors"
```

---

### Task 4: `formatting` — `color_dot` + `format_label`

**Files:**
- Create: `formatting.py`
- Test: `tests/test_formatting.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_formatting.py`:

```python
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from formatting import color_dot, format_label  # noqa: E402
from usage_client import Usage  # noqa: E402


def make_usage(five=51.0, seven=23.0, sonnet=2.0, opus=None):
    base = datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc)
    return Usage(
        five_hour_pct=five, five_hour_reset=base,
        seven_day_pct=seven, seven_day_reset=base,
        sonnet_pct=sonnet, opus_pct=opus, fetched_at=base,
    )


class TestColorDot(unittest.TestCase):
    def test_green_below_70(self):
        self.assertEqual(color_dot(69.9), "🟢")

    def test_orange_70_to_90(self):
        self.assertEqual(color_dot(70.0), "🟠")
        self.assertEqual(color_dot(90.0), "🟠")

    def test_red_above_90(self):
        self.assertEqual(color_dot(90.1), "🔴")


class TestFormatLabel(unittest.TestCase):
    def test_uses_worst_of_two_for_dot(self):
        label = format_label(make_usage(five=95.0, seven=23.0))
        self.assertTrue(label.startswith("🔴"))
        self.assertIn("95%", label)
        self.assertIn("23%", label)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_formatting -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'formatting'`

- [ ] **Step 3: Write minimal implementation**

Create `formatting.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_formatting -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add formatting.py tests/test_formatting.py
git commit -m "feat: color_dot and compact format_label"
```

---

### Task 5: `formatting` — `humanize_delta` + `format_menu_lines`

**Files:**
- Modify: `formatting.py`
- Test: `tests/test_formatting.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_formatting.py` (before the `if __name__` block):

```python
from formatting import humanize_delta, format_menu_lines, MenuText  # noqa: E402
from datetime import timedelta  # noqa: E402


class TestHumanizeDelta(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc)

    def test_future_hours_and_minutes(self):
        target = self.now + timedelta(hours=2, minutes=47)
        self.assertEqual(humanize_delta(target, self.now), "dans 2 h 47")

    def test_future_minutes_only(self):
        target = self.now + timedelta(minutes=12)
        self.assertEqual(humanize_delta(target, self.now), "dans 12 min")

    def test_past_or_now(self):
        target = self.now - timedelta(minutes=1)
        self.assertEqual(humanize_delta(target, self.now), "maintenant")


class TestFormatMenuLines(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc)

    def test_lines_contain_percentages(self):
        m = format_menu_lines(make_usage(five=51.0, seven=23.0, sonnet=2.0, opus=None), self.now)
        self.assertIsInstance(m, MenuText)
        self.assertIn("51", m.five_hour)
        self.assertIn("23", m.seven_day)
        self.assertIn("2", m.sonnet)
        self.assertIn("—", m.opus)  # null opus shows an em dash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_formatting.TestHumanizeDelta -v`
Expected: FAIL — `ImportError: cannot import name 'humanize_delta'`

- [ ] **Step 3: Write minimal implementation**

Add to `formatting.py` (after `format_label`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_formatting -v`
Expected: PASS (all formatting tests)

- [ ] **Step 5: Commit**

```bash
git add formatting.py tests/test_formatting.py
git commit -m "feat: humanize_delta and format_menu_lines"
```

---

### Task 6: `indicator.py` — GTK tray wiring

**Files:**
- Create: `indicator.py`

No unit test (GTK/display-bound); verified by the manual smoke test in Task 8.
The network call runs in a worker thread; UI updates are marshalled back onto the
GLib main loop with `GLib.idle_add`.

- [ ] **Step 1: Create `indicator.py`**

```python
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
```

- [ ] **Step 2: Smoke-check the import (no GTK main loop yet)**

Run: `cd ~/claude-usage-indicator && python3 -c "import indicator; print('import OK')"`
Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add indicator.py
git commit -m "feat: GTK tray indicator with threaded refresh"
```

---

### Task 7: `main.py` — entry point

**Files:**
- Create: `main.py`

- [ ] **Step 1: Create `main.py`**

```python
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
```

- [ ] **Step 2: Verify it imports and parses**

Run: `cd ~/claude-usage-indicator && python3 -c "import main; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: main entry point with interval config and signal handling"
```

---

### Task 8: Manual end-to-end run

**Files:** none (verification only)

- [ ] **Step 1: Run the app live**

Run: `cd ~/claude-usage-indicator && python3 main.py`
Expected:
- An indicator appears in the GNOME top-right area showing e.g. `🟢 51% · 23%`.
- Clicking it shows the 5h/7d/Sonnet/Opus lines with reset times and "Dernière maj".
- Console logs an INFO line on start, no traceback.

- [ ] **Step 2: Verify the degraded auth state (optional)**

Temporarily point at a bad credentials file:
Run: `CLAUDE_USAGE_INTERVAL=15 python3 -c "from indicator import Indicator; from usage_client import AuthError; ind=Indicator(fetch=lambda: (_ for _ in ()).throw(AuthError('x'))); ind._apply_error(AuthError('x')); print('label set, menu shows auth hint')"`
Expected: prints the confirmation line (label would read `Cl ⚠ auth`).

- [ ] **Step 3: Stop the app**

Press `Ctrl-C` in the terminal. Expected: clean exit, no traceback.

---

### Task 9: Autostart packaging + README

**Files:**
- Create: `claude-usage-indicator.desktop`
- Create: `install.sh`
- Create: `README.md`

- [ ] **Step 1: Create `claude-usage-indicator.desktop`**

```ini
[Desktop Entry]
Type=Application
Name=Claude Usage Indicator
Comment=Live Claude Code quota in the top bar
Exec=python3 %h/claude-usage-indicator/main.py
Icon=utilities-system-monitor-symbolic
Terminal=false
Categories=Utility;
X-GNOME-Autostart-enabled=true
```

- [ ] **Step 2: Create `install.sh`**

```bash
#!/usr/bin/env bash
# Install the autostart entry so the indicator launches at login.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="${HOME}/.config/autostart"

mkdir -p "${AUTOSTART_DIR}"
install -m 644 "${APP_DIR}/claude-usage-indicator.desktop" \
    "${AUTOSTART_DIR}/claude-usage-indicator.desktop"

echo "Installed autostart entry to ${AUTOSTART_DIR}/claude-usage-indicator.desktop"
echo "Start now with: python3 ${APP_DIR}/main.py"
```

- [ ] **Step 3: Create `README.md`**

```markdown
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
```

- [ ] **Step 4: Make install.sh executable and run the test suite once more**

```bash
cd ~/claude-usage-indicator
chmod +x install.sh
python3 -m unittest discover -s tests -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add claude-usage-indicator.desktop install.sh README.md
git commit -m "feat: autostart packaging and README"
```

---

### Task 10: Enable autostart (optional final step)

**Files:** none

- [ ] **Step 1: Install the autostart entry**

Run: `cd ~/claude-usage-indicator && ./install.sh`
Expected: confirmation line printed; `~/.config/autostart/claude-usage-indicator.desktop` exists.

- [ ] **Step 2: Confirm it survives a login (manual)**

Log out and back in (or reboot). Expected: the indicator appears automatically in
the top bar.

---

## Self-Review Notes

- **Spec coverage:** endpoint/headers (Task 3), token-from-credentials + DIP (Tasks 2–3), `Usage` shape with null models (Task 1), compact label + colour dot (Task 4), menu lines + reset times + relative time (Task 5), graceful degradation for credentials/401/network (Task 6), threaded non-blocking UI (Task 6), 60s configurable interval + signals (Task 7), autostart `.desktop` (Task 9), isolated unit tests with no real network (Tasks 1–5). All spec sections map to a task.
- **Naming consistency:** `fetch`, `Usage`, `parse_usage`, `read_token`, `format_label`, `format_menu_lines`, `MenuText`, `color_dot`, `humanize_delta` are referenced identically across tasks and modules.
- **No placeholders:** every code step shows complete code; every run step shows the command and expected result.
- **User-Agent caveat:** `USER_AGENT = "claude-code/2.1.173"` is hardcoded (required by the endpoint). If a future Claude Code version is needed, bump this one constant.
