"""Local ranking alternatives for defensive, retrospective ATT&CK evidence review."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from .stix import MitreTechnique

E5_REVISION = "ffb93f3bd4047442299a41ebb6fa998a38507c52"
Ranked = list[tuple[str, float]]
_WORD = re.compile(r"(?i)\bt\d{4}(?:\.\d{3})?\b|[a-z][a-z0-9]+")
_MARKUP = re.compile(r"\(Citation:[^)]*\)|\[([^\]]+)\]\([^)]*\)|https?://\S+|</?code>", re.I)


def tokens(text: str) -> list[str]:
    text = _MARKUP.sub(lambda match: match.group(1) or " ", text)
    words = [word.lower() for word in _WORD.findall(text.lower())]
    output = []
    for word in words:
        if word in ENGLISH_STOP_WORDS:
            continue
        if len(word) > 5 and word.endswith("ing"):
            word = word[:-3]
        elif len(word) > 4 and word.endswith(("ed", "es")):
            word = word[:-2]
        elif len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        output.append(word)
    return output


class BM25:
    def __init__(self, documents: dict[str, str]) -> None:
        if not documents:
            raise ValueError("BM25 requires documents")
        postings = defaultdict(dict)
        lengths = {}
        for doc, value in documents.items():
            terms = tokens(value)
            lengths[doc] = len(terms)
            for word, count in Counter(terms).items():
                postings[word][doc] = count
        average_length = max(1.0, sum(lengths.values()) / len(lengths))
        self._length_normalizer = {key: 1.2 * (0.25 + 0.75 * length / average_length)
                                   for key, length in lengths.items()}
        self._postings = postings
        self._count = len(documents)

    def score(self, query: str) -> dict[str, float]:
        scores: dict[str, float] = defaultdict(float)
        for term in sorted(set(tokens(query))):
            documents = self._postings.get(term, {})
            if not documents:
                continue
            idf = math.log1p((self._count - len(documents) + 0.5) / (len(documents) + 0.5))
            for key, frequency in documents.items():
                scores[key] += idf * 2.2 * frequency / (frequency + self._length_normalizer[key])
        return dict(scores)


def rank(scores: dict[str, float]) -> Ranked:
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


class FieldBM25:
    """Combine separately length-normalized identity, behavior, and context fields."""

    def __init__(self, techniques: list[MitreTechnique]) -> None:
        self._fields = (
            (2.0, BM25({t.technique_id: " ".join((t.technique_id, t.name, *t.aliases)) for t in techniques})),
            (1.0, BM25({t.technique_id: t.description for t in techniques})),
            (0.35, BM25({t.technique_id: " ".join((*t.platforms, *t.tactics, t.detection,
                                                 *t.detection_strategies, t.parent_id or ""))
                        for t in techniques})),
        )

    def __call__(self, records: dict[str, str]) -> Ranked:
        joined = " ".join(records.values())
        maxima: dict[str, float] = defaultdict(float)
        queries = (joined, *records.values()) if len(records) > 1 else (joined,)
        for query in queries:
            scores: dict[str, float] = defaultdict(float)
            for weight, field in self._fields:
                for tid, score in field.score(query).items():
                    scores[tid] += weight * score
            for tid, score in scores.items():
                maxima[tid] = max(maxima[tid], score)
        return rank(maxima)


def rank_fusion(*rankings: Ranked) -> Ranked:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for position, (tid, _) in enumerate(ranking[:100], 1):
            scores[tid] += 1 / (60 + position)
    return rank(scores)


class DenseRanker:
    """Embed public technique descriptions and fictional records with a cached CPU encoder."""

    def __init__(self, snapshot: Path, techniques: list[MitreTechnique], *, max_length: int = 192) -> None:
        if not 1 <= max_length <= 512:
            raise ValueError("E5 token limit must be between 1 and 512")
        import torch
        from transformers import AutoModel, AutoTokenizer
        from transformers.utils.logging import disable_progress_bar

        if snapshot.name != E5_REVISION or not (snapshot / "model.safetensors").is_file():
            raise ValueError("Expected the pinned local E5-small-v2 safetensors snapshot")
        disable_progress_bar()
        torch.set_num_threads(6)
        self._torch = torch
        self._max_length = max_length
        self._tokenizer = AutoTokenizer.from_pretrained(snapshot, trust_remote_code=False, local_files_only=True)
        self._model = AutoModel.from_pretrained(snapshot, use_safetensors=True, trust_remote_code=False,
                                                local_files_only=True).eval()
        self._ids = [t.technique_id for t in techniques]
        passages = [self.passage_text(technique) for technique in techniques]
        self._passages = self._encode(passages)

    @staticmethod
    def passage_text(technique: MitreTechnique) -> str:
        return "passage: " + " ".join((technique.name, technique.description, *technique.detection_strategies))

    @staticmethod
    def query_text(records: dict[str, str]) -> str:
        return "query: " + " ".join(records.values())

    def token_lengths(self, texts: list[str]) -> list[int]:
        encoded = self._tokenizer(texts, add_special_tokens=True, truncation=False, verbose=False)
        return [len(ids) for ids in encoded["input_ids"]]

    def _encode(self, texts: list[str]):
        torch = self._torch
        vectors = []
        with torch.inference_mode():
            for start in range(0, len(texts), 24):
                inputs = self._tokenizer(texts[start:start + 24], padding=True, truncation=True,
                                         max_length=self._max_length, return_tensors="pt")
                hidden = self._model(**inputs).last_hidden_state
                mask = inputs.attention_mask.unsqueeze(-1)
                pooled = (hidden * mask).sum(1) / mask.sum(1).clamp_min(1)
                vectors.append(torch.nn.functional.normalize(pooled, dim=1))
        return torch.cat(vectors)

    def __call__(self, records: dict[str, str]) -> Ranked:
        query = self._encode([self.query_text(records)])[0]
        scores = (self._passages @ query).tolist()
        return rank(dict(zip(self._ids, scores, strict=True)))
