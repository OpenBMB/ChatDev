from unittest.mock import MagicMock, patch

import requests

from functions.function_calling.web import read_webpage_content, web_search


def test_web_search_empty_query():
    assert web_search("") == "Error: query must be a non-empty string."
    assert web_search("   ") == "Error: query must be a non-empty string."
    assert web_search(None) == "Error: query must be a non-empty string."


def test_web_search_missing_api_key(monkeypatch):
    monkeypatch.delenv("SERPER_DEV_API_KEY", raising=False)
    assert web_search("python") == "Error: SERPER_DEV_API_KEY environment variable is not set."


def test_web_search_success(monkeypatch):
    monkeypatch.setenv("SERPER_DEV_API_KEY", "test-serper-key")
    sample_response = {
        "knowledgeGraph": {
            "title": "Python",
            "type": "Programming language",
            "description": "Python is a high-level programming language.",
            "attributes": {"Developer": "Python Software Foundation"},
        },
        "organic": [
            {
                "title": "Welcome to Python.org",
                "link": "https://www.python.org",
                "snippet": "The official home of the Python Programming Language.",
                "attributes": {"Release": "3.12"},
            }
        ],
        "peopleAlsoAsk": [
            {
                "question": "What is Python used for?",
                "snippet": "Python is used for web development, data science, etc.",
                "title": "Python FAQ",
                "link": "https://faq.example.com",
            }
        ],
        "relatedSearches": [
            {"query": "python tutorial"},
            {"query": "python download"},
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_response

    with patch("functions.function_calling.web.requests.request", return_value=mock_resp) as mock_req:
        result = web_search("python", page=0)  # page 0 should default to 1
        assert "## Knowledge Graph" in result
        assert "**Title**: Python" in result
        assert "## Organic Results" in result
        assert "Welcome to Python.org" in result
        assert "## People Also Ask" in result
        assert "## Related Searches" in result
        assert "python tutorial, python download" in result

        mock_req.assert_called_once()
        _, kwargs = mock_req.call_args
        import json
        payload = json.loads(kwargs["data"])
        assert payload["page"] == 1
        assert kwargs["timeout"] == 30.0


def test_web_search_no_results(monkeypatch):
    monkeypatch.setenv("SERPER_DEV_API_KEY", "test-serper-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {}

    with patch("functions.function_calling.web.requests.request", return_value=mock_resp):
        assert web_search("qwertyuiopxyz123") == "No search results found."


def test_web_search_api_error_message(monkeypatch):
    monkeypatch.setenv("SERPER_DEV_API_KEY", "test-serper-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.json.return_value = {"statusCode": 403, "message": "Unauthorized: invalid API key"}

    with patch("functions.function_calling.web.requests.request", return_value=mock_resp):
        result = web_search("python")
        assert result == "Search error (403): Unauthorized: invalid API key"


def test_web_search_api_error_field(monkeypatch):
    monkeypatch.setenv("SERPER_DEV_API_KEY", "test-serper-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": "Invalid country parameter"}

    with patch("functions.function_calling.web.requests.request", return_value=mock_resp):
        result = web_search("python")
        assert result == "Search error: Invalid country parameter"


def test_web_search_network_error(monkeypatch):
    monkeypatch.setenv("SERPER_DEV_API_KEY", "test-serper-key")
    with patch(
        "functions.function_calling.web.requests.request",
        side_effect=requests.ConnectionError("Connection refused"),
    ):
        result = web_search("python")
        assert "Error executing web search request" in result
        assert "Connection refused" in result


def test_web_search_non_json_response(monkeypatch):
    monkeypatch.setenv("SERPER_DEV_API_KEY", "test-serper-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 502
    mock_resp.json.side_effect = ValueError("Bad Gateway")
    mock_resp.text = "Bad Gateway from upstream proxy"

    with patch("functions.function_calling.web.requests.request", return_value=mock_resp):
        result = web_search("python")
        assert result == "Bad Gateway from upstream proxy"


def test_read_webpage_content_invalid_url():
    assert read_webpage_content("") == "Error: URL must be a non-empty string."
    assert read_webpage_content("   ") == "Error: URL must be a non-empty string."
    assert read_webpage_content(None) == "Error: URL must be a non-empty string."


def test_read_webpage_content_with_api_key(monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "secret-token")
    mock_resp = MagicMock()
    mock_resp.text = "# Sample Page Content"

    with patch("functions.function_calling.web.requests.get", return_value=mock_resp) as mock_get:
        result = read_webpage_content("  https://example.com/article  ")
        assert result == "# Sample Page Content"
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == "https://r.jina.ai/https://example.com/article"
        assert kwargs["headers"]["Authorization"] == "Bearer secret-token"
        assert kwargs["timeout"] == 30.0


def test_read_webpage_content_network_error(monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "Bearer existing-token")
    with patch(
        "functions.function_calling.web.requests.get",
        side_effect=requests.Timeout("Read timeout"),
    ):
        result = read_webpage_content("https://example.com")
        assert "Error reading webpage content" in result
        assert "Read timeout" in result
