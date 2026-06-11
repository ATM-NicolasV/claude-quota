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


def read_token(credentials_path: Path = CREDENTIALS_PATH) -> str:
    """Return the Claude OAuth access token from the local credentials file."""
    try:
        with open(credentials_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data["claudeAiOauth"]["accessToken"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError, TypeError) as exc:
        raise CredentialsError(f"cannot read Claude credentials: {exc}") from exc


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
