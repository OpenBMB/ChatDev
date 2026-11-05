"""Shared BGE query/passage text preparation.

BGE v1.5 retrieval instructions belong on queries only.  Keeping these tiny
helpers shared by indexing and online retrieval prevents a query/query index
from being rebuilt accidentally.
"""

from __future__ import annotations

from typing import Iterable, List


ENCODING_POLICY_VERSION = "bge-query-prefix-only-v1"


def prepare_query_texts(texts: Iterable[str], query_prefix: str) -> List[str]:
    return [f"{query_prefix}{text}" for text in texts]


def prepare_passage_texts(texts: Iterable[str]) -> List[str]:
    return [str(text) for text in texts]
