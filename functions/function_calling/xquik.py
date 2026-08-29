"""Read-only X research through the public Xquik API."""

import os
from collections.abc import Callable
from typing import Annotated, Any, Literal

import requests

from utils.function_catalog import ParamMeta

_SEARCH_URL = "https://xquik.com/api/v1/x/tweets/search"


def _error_detail(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "unexpected response"
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("code") or error.get("message") or "request failed")
    if isinstance(error, str):
        return error
    return "request failed"


def search_x_tweets(
    query: Annotated[
        str,
        ParamMeta(
            description="X search query. Supports keywords, hashtags, handles, and X search operators."
        ),
    ],
    limit: Annotated[
        int,
        ParamMeta(description="Maximum posts to return. Use 1 through 100."),
    ] = 10,
    query_type: Annotated[
        Literal["Latest", "Top"],
        ParamMeta(description="Use Latest for recency or Top for engagement ranking."),
    ] = "Latest",
    cursor: Annotated[
        str | None,
        ParamMeta(description="Opaque next_cursor from a previous response."),
    ] = None,
    *,
    _request: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    """Search public X posts with Xquik's read-only tweet search endpoint."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("X search query cannot be empty.")
    if not 1 <= limit <= 100:
        raise ValueError("X search limit must be between 1 and 100.")
    if query_type not in {"Latest", "Top"}:
        raise ValueError("X search query_type must be Latest or Top.")

    api_key = os.getenv("XQUIK_API_KEY", "").strip()
    if not api_key:
        raise ValueError("XQUIK_API_KEY is required. Add it to your environment first.")

    params: dict[str, Any] = {
        "q": normalized_query,
        "limit": limit,
        "queryType": query_type,
    }
    if cursor:
        params["cursor"] = cursor

    try:
        response = _request(
            _SEARCH_URL,
            headers={"x-api-key": api_key},
            params=params,
            timeout=30,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise RuntimeError("Xquik request failed. Check the network and try again.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Xquik returned an invalid response (HTTP {response.status_code})."
        ) from exc

    if not response.ok:
        raise RuntimeError(
            f"Xquik request failed (HTTP {response.status_code}: {_error_detail(payload)})."
        )
    if not isinstance(payload, dict) or not isinstance(payload.get("tweets"), list):
        raise RuntimeError("Xquik returned an unexpected tweet search response.")
    return payload
