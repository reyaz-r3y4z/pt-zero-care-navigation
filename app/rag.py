"""Dependency-free local retrieval with visible evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.models import Evidence


TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.lower()))


class KnowledgeBase:
    def __init__(self, path: Path) -> None:
        self.documents = json.loads(path.read_text(encoding="utf-8"))

    def search(self, query: str, limit: int = 3) -> list[Evidence]:
        query_tokens = tokens(query)
        scored = []
        for document in self.documents:
            document_tokens = tokens(document["text"] + " " + " ".join(document["tags"]))
            overlap = len(query_tokens & document_tokens)
            score = overlap / max(1, len(query_tokens))
            if overlap:
                scored.append((score, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [Evidence(
            title=document["title"], source=document["source"],
            excerpt=document["text"], score=round(score, 3),
        ) for score, document in scored[:limit]]

