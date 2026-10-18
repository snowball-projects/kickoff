import gzip
import io
from unittest.mock import patch

import pytest

from kickoff import feeds, http
from kickoff.settings import Settings


class Response(io.BytesIO):
    def __init__(self, payload, encoding=""):
        super().__init__(payload)
        self.headers = {"Content-Encoding": encoding}


@pytest.mark.parametrize("payload,encoding", [(b"{}", ""), (gzip.compress(b"{}"), "GZip"), (gzip.compress(b"{}"), "")])
def test_bounded_response_accepts_plain_and_gzip(payload, encoding):
    assert http.read_bounded_response(Response(payload, encoding), max_bytes=100) == b"{}"


def test_transfer_limit_is_checked_before_gzip_expansion():
    response = Response(b"x" * 101, "gzip")
    with patch.object(gzip.GzipFile, "read", side_effect=AssertionError("must not decompress")):
        with pytest.raises(ValueError, match="transfer size limit"):
            http.read_bounded_response(response, max_bytes=100)


@pytest.mark.parametrize("payload", [gzip.compress(b"x" * 101), gzip.compress(b"x" * 60) + gzip.compress(b"x" * 60)])
def test_expansion_limit_includes_concatenated_gzip_members(payload):
    with pytest.raises(ValueError, match="expanded size limit"):
        http.read_bounded_response(Response(payload), max_bytes=100)


def test_gzip_reader_never_requests_unbounded_output():
    with patch.object(gzip.GzipFile, "read", return_value=b"{}") as read:
        assert http.read_bounded_response(Response(gzip.compress(b"{}")), max_bytes=100) == b"{}"
    read.assert_called_once_with(101)


def test_feed_and_legacy_adapters_both_apply_response_limits(monkeypatch, tmp_path):
    monkeypatch.setattr(feeds, "MAX_BYTES", 100)
    monkeypatch.setattr(feeds, "urlopen", lambda *a, **k: Response(gzip.compress(b"x" * 101), "gzip"))
    with pytest.raises(ValueError, match="expanded size limit"):
        feeds.get_json("https://example.test/feed")
    monkeypatch.setattr(http, "urlopen", lambda *a, **k: Response(b"{}"))
    with patch.object(http, "read_bounded_response", return_value=b"{}") as bounded:
        assert http.fetch_json("https://example.test/feed", Settings.load(tmp_path)) == {}
    bounded.assert_called_once()
