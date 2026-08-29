"""Tests for the read-only Xquik function tool."""

from typing import Any

import pytest

from functions.function_calling.xquik import search_x_tweets


class FakeResponse:
    def __init__(self, status_code: int, payload: Any, *, valid_json: bool = True):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._payload = payload
        self._valid_json = valid_json

    def json(self) -> Any:
        if not self._valid_json:
            raise ValueError("invalid JSON")
        return self._payload


def test_search_x_tweets_sends_a_bounded_read_request(monkeypatch):
    monkeypatch.setenv("XQUIK_API_KEY", "xq_test")
    captured: dict[str, Any] = {}

    def fake_request(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse(
            200,
            {
                "tweets": [{"id": "1", "text": "ChatDev"}],
                "has_next_page": True,
                "next_cursor": "next-page",
            },
        )

    result = search_x_tweets(
        " ChatDev agents ",
        limit=20,
        query_type="Top",
        cursor="page-one",
        _request=fake_request,
    )

    assert captured == {
        "url": "https://xquik.com/api/v1/x/tweets/search",
        "headers": {"x-api-key": "xq_test"},
        "params": {
            "q": "ChatDev agents",
            "limit": 20,
            "queryType": "Top",
            "cursor": "page-one",
        },
        "timeout": 30,
        "allow_redirects": False,
    }
    assert result["next_cursor"] == "next-page"


@pytest.mark.parametrize(
    "query, limit, query_type",
    [
        ("", 10, "Latest"),
        ("topic", 0, "Latest"),
        ("topic", 101, "Latest"),
        ("topic", 10, "Popular"),
    ],
)
def test_search_x_tweets_rejects_invalid_input(monkeypatch, query, limit, query_type):
    monkeypatch.setenv("XQUIK_API_KEY", "xq_test")

    with pytest.raises(ValueError):
        search_x_tweets(query, limit=limit, query_type=query_type)


def test_search_x_tweets_requires_an_api_key(monkeypatch):
    monkeypatch.delenv("XQUIK_API_KEY", raising=False)

    with pytest.raises(ValueError, match="XQUIK_API_KEY is required"):
        search_x_tweets("ChatDev")

    monkeypatch.setenv("XQUIK_API_KEY", "   ")

    with pytest.raises(ValueError, match="XQUIK_API_KEY is required"):
        search_x_tweets("ChatDev")


def test_search_x_tweets_reports_public_api_error_without_secret(monkeypatch):
    monkeypatch.setenv("XQUIK_API_KEY", "xq_secret_value")

    with pytest.raises(RuntimeError, match="HTTP 429: rate_limit_exceeded") as error:
        search_x_tweets(
            "ChatDev",
            _request=lambda *args, **kwargs: FakeResponse(
                429,
                {"error": {"code": "rate_limit_exceeded"}},
            ),
        )

    assert "xq_secret_value" not in str(error.value)


def test_search_x_tweets_rejects_malformed_success(monkeypatch):
    monkeypatch.setenv("XQUIK_API_KEY", "xq_test")

    with pytest.raises(RuntimeError, match="unexpected tweet search response"):
        search_x_tweets(
            "ChatDev",
            _request=lambda *args, **kwargs: FakeResponse(200, {"results": []}),
        )


def test_search_x_tweets_rejects_non_json_response(monkeypatch):
    monkeypatch.setenv("XQUIK_API_KEY", "xq_test")

    with pytest.raises(RuntimeError, match=r"invalid response \(HTTP 502\)"):
        search_x_tweets(
            "ChatDev",
            _request=lambda *args, **kwargs: FakeResponse(
                502,
                None,
                valid_json=False,
            ),
        )
