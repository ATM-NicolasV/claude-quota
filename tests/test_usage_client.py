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


if __name__ == "__main__":
    unittest.main()
