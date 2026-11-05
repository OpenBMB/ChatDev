"""Cluster-only delay before an already-authorized model transport retry."""

import os
import random
import time

import httpcore
import httpx
from loguru import logger
from openai import APIConnectionError, APITimeoutError

from .direct_network import load_model_proxy
from .model_request_budget import ModelTimeBudgetError, require_retry_time


def _proxy_connect_refused(error: BaseException) -> bool:
    if not isinstance(error, (APIConnectionError, httpx.ConnectError)) or isinstance(
        error, APITimeoutError
    ):
        return False
    seen: set[int] = set()
    connecting = False
    cause: BaseException | None = error
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        if isinstance(cause, httpx.TransportError):
            if not isinstance(cause, httpx.ConnectError):
                return False
            connecting = True
        if connecting and isinstance(cause, ConnectionRefusedError):
            return True
        # httpcore's pool re-raises its ConnectError from None. The socket's
        # original errno can survive only as that specific error's context.
        if isinstance(cause, httpcore.ConnectError) and cause.__cause__ is None:
            cause = cause.__context__
        else:
            cause = cause.__cause__
    return False


def wait_for_proxy_retry(error: BaseException, attempt: int) -> bool:
    """Return False if waiting for a refused connection would consume the task reserve."""
    if os.environ.get("SGAR_PROXY_CONNECT_BACKOFF") != "1":
        return True
    if not _proxy_connect_refused(error) or not load_model_proxy():
        return True
    delay = (5.0 if attempt == 1 else 12.0) + random.SystemRandom().uniform(0, 1)
    try:
        require_retry_time(delay)
    except ModelTimeBudgetError:
        logger.info("Proxy connection refused; insufficient time for a delayed retry")
        return False
    logger.info("Proxy connection refused; waiting {:.1f}s before retry", delay)
    time.sleep(delay)
    return True
