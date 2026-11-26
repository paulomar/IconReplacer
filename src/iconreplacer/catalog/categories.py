"""Keyword based categorisation of external icons into the canonical CATEGORIES."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from functools import cache
from importlib import resources

from iconreplacer.core.models import CATEGORIES

_TOKEN = re.compile(r"[a-z0-9]+")


@cache
def _table() -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]], str]:
    text = resources.files("iconreplacer.catalog").joinpath(
        "external_data", "category_keywords.json"
    )
    raw = json.loads(text.read_text("utf-8"))
    index: dict[str, list[str]] = {}
    for category, words in raw["keywords"].items():
        if category not in CATEGORIES:
            continue
        for w in words:
            index.setdefault(w, []).append(category)
    collections = {
        k: tuple(c for c in v if c in CATEGORIES) for k, v in raw["collection_categories"].items()
    }
    fallback = raw["fallback"] if raw["fallback"] in CATEGORIES else "System"
    return {k: tuple(v) for k, v in index.items()}, collections, fallback


def fallback_category() -> str:
    return _table()[2]


def tokens(*texts: str) -> list[str]:
    out: list[str] = []
    for text in texts:
        out.extend(_TOKEN.findall(text.lower()))
    return out


def categorize(*texts: str, collection_category: str | None = None) -> frozenset[str]:
    """Canonical categories for the given names/path segments (never empty)."""
    index, collections, fallback = _table()
    found: list[str] = []
    for tok in tokens(*texts):
        for cand in (tok, tok[:-1] if tok.endswith("s") else tok):
            for cat in index.get(cand, ()):
                if cat not in found:
                    found.append(cat)
    if not found and collection_category:
        found.extend(collections.get(collection_category, ()))
    return frozenset(found or [fallback])


def iter_tags(*texts: str) -> Iterable[str]:
    return dict.fromkeys(tokens(*texts))
