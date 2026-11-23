"""Deterministic offline retrieval for the verified ATT&CK corpus."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer

from ..config import MitreConfig
from .stix import MitreTechnique, load_techniques


@dataclass(frozen=True)
class MitreEvidence:
    technique_id: str
    name: str
    score: float
    excerpt: str
    url: str
    tactics: tuple[str, ...]
    stix_id: str = ""
    object_version: str = ""
    bundle_sha256: str = ""
    bundle_version: str = ""

    def citation(self) -> str:
        return f"[{self.technique_id}] {self.name} ({self.url})"


class MitreRAG:
    def __init__(self, config: MitreConfig) -> None:
        self.config = config
        self.techniques: list[MitreTechnique] = []
        self._index = None

    @property
    def ready(self) -> bool:
        return self._index is not None

    def _build(self) -> None:
        techniques = load_techniques(self.config)
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        matrix = vectorizer.fit_transform(t.raw_text[:self.config.max_technique_chars] for t in techniques)
        self.techniques = techniques
        self._index = vectorizer, matrix

    async def build(self) -> int:
        await asyncio.to_thread(self._build)
        return len(self.techniques)

    async def retrieve(self, query: str, *, top_k: int | None = None) -> list[MitreEvidence]:
        if self._index is None:
            raise RuntimeError("Build the ATT&CK index before retrieval")
        vectorizer, matrix = self._index
        scores = (matrix @ vectorizer.transform([query]).T).tocoo()
        ranked = sorted(zip(scores.row, scores.data),
                        key=lambda entry: (-entry[1], self.techniques[entry[0]].technique_id))
        limit = self.config.top_k if top_k is None else top_k
        result = []
        for index, score in ranked[:max(0, limit)]:
            technique = self.techniques[index]
            result.append(MitreEvidence(
                technique_id=technique.technique_id, name=technique.name,
                score=float(score), excerpt=technique.raw_text[:420],
                url=technique.url, tactics=technique.tactics,
                stix_id=technique.stix_id, object_version=technique.object_version,
                bundle_sha256=self.config.sha256, bundle_version=self.config.version,
            ))
        return result

    def validate_technique_ids(self, ids: list[str]) -> tuple[list[str], list[str]]:
        catalogue = {item.technique_id for item in self.techniques}
        return [tid for tid in ids if tid in catalogue], [tid for tid in ids if tid not in catalogue]
