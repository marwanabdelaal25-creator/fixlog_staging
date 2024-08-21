"""Search dwellings and logs by free-text query.

Author: Marwan Helmy
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .storage import JsonStorage


@dataclass
class SearchHit:
    kind: str
    id: str
    title: str
    snippet: str
    score: float


class HomesteadSearch:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def _tokenize(self, query: str) -> list[str]:
        return [t for t in query.lower().split() if t]

    def _score_text(self, text: str, tokens: list[str]) -> float:
        if not tokens:
            return 0.0
        lower = text.lower()
        hits = sum(1 for t in tokens if t in lower)
        return hits / len(tokens)

    def search_dwellings(self, query: str) -> list[SearchHit]:
        tokens = self._tokenize(query)
        hits = []
        for dwelling in self.storage.list_dwellings(active_only=False):
            blob = " ".join([
                dwelling.name,
                str(dwelling.metadata.get("notes", "")),
                " ".join(dwelling.tag_ids),
                dwelling.contractor_key or "",
            ])
            score = self._score_text(blob, tokens)
            if score > 0:
                hits.append(SearchHit(
                    kind="dwelling",
                    id=dwelling.id,
                    title=dwelling.name,
                    snippet=str(dwelling.metadata.get("notes", ""))[:120],
                    score=score,
                ))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    def search_walkthroughs(self, query: str) -> list[SearchHit]:
        tokens = self._tokenize(query)
        hits = []
        for log in self.storage.list_walkthroughs():
            blob = " ".join([
                log.get("action", ""),
                log.get("details", ""),
                log.get("dwelling_id", ""),
            ])
            score = self._score_text(blob, tokens)
            if score > 0:
                hits.append(SearchHit(
                    kind="walkthrough",
                    id=log.get("id", ""),
                    title=log.get("action", "care"),
                    snippet=(log.get("details") or "")[:120],
                    score=score,
                ))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    def search_notes(self, query: str) -> list[SearchHit]:
        tokens = self._tokenize(query)
        hits = []
        for note in self.storage.list_notes():
            blob = " ".join([note.get("title", ""), note.get("body", "")])
            score = self._score_text(blob, tokens)
            if score > 0:
                hits.append(SearchHit(
                    kind="note",
                    id=note.get("id", ""),
                    title=note.get("title", "note"),
                    snippet=(note.get("body") or "")[:120],
                    score=score,
                ))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    def search_all(self, query: str, limit: Optional[int] = None) -> list[SearchHit]:
        combined = (
            self.search_dwellings(query)
            + self.search_walkthroughs(query)
            + self.search_notes(query)
        )
        combined.sort(key=lambda h: h.score, reverse=True)
        if limit:
            combined = combined[:limit]
        return combined

    def to_dicts(self, hits: list[SearchHit]) -> list[dict[str, Any]]:
        return [
            {"kind": h.kind, "id": h.id, "title": h.title, "snippet": h.snippet, "score": h.score}
            for h in hits
        ]
