"""TF-IDF retrieval with tier-controlled excerpts, entirely offline at runtime."""
import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

TIER_CHARACTERS = {"A": 400, "B": 900, "C": 1800}
STOP = set("a an the of to and or in on for is are be by with from as at that this it test testing tool target http https 127 localhost".split())


def tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1 and t not in STOP]


class TechniqueIndex:
    def __init__(self, path=None):
        data = json.loads(Path(path or Path(__file__).with_name("index.json")).read_text(encoding="utf-8"))
        self.metadata = {k: v for k, v in data.items() if k != "entries"}
        self.entries = [e for e in data["entries"] if not e.get("revoked") and not e.get("deprecated") and not e.get("historical")]
        self.counts = [Counter(tokens(" ".join([e["name"], e["name"], e["description"], " ".join(e["keywords"])]))) for e in self.entries]
        frequencies = Counter(t for count in self.counts for t in count)
        self.idf = {t: math.log((len(self.entries) + 1) / (n + 1)) + 1 for t, n in frequencies.items()}
        self.norms = [math.sqrt(sum(((1 + math.log(n)) * self.idf[t]) ** 2 for t, n in c.items())) for c in self.counts]

    def retrieve(self, task, model_tier, limit=3, domain="enterprise-attack"):
        if model_tier not in TIER_CHARACTERS:
            raise ValueError("model_tier must be A, B or C")
        if not 1 <= limit <= 3:
            raise ValueError("retrieve top 1–3 entries")
        query = Counter(tokens(task))
        weights = {t: (1 + math.log(n)) * self.idf[t] for t, n in query.items() if t in self.idf}
        norm = math.sqrt(sum(v*v for v in weights.values()))
        if not norm:
            return []
        scored = []
        for i, count in enumerate(self.counts):
            if self.entries[i]["framework"] == "mitre-attack" and domain not in self.entries[i].get("domains", []):
                continue
            score = sum(value * (1 + math.log(count[t])) * self.idf[t] for t, value in weights.items() if count[t])
            score = score / (norm * self.norms[i]) if self.norms[i] else 0
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda item: (-item[0], self.entries[item[1]]["id"]))
        result = []
        for score, i in scored[:limit]:
            entry = self.entries[i]
            cap = TIER_CHARACTERS[model_tier]
            result.append({**entry, "description": entry["description"][:cap],
                           "description_truncated": len(entry["description"]) > cap, "score": round(score, 6)})
        return result


@lru_cache(maxsize=1)
def local_index():
    return TechniqueIndex()
