"""Scorer summaries with a fixed metric projection and a rubric-free citation screen."""
from eval.attack_evidence_v2 import summarise

SCORE_FIELDS = (
    "disposition", "contract", "abstain", "exact", "tech_tp", "tech_fp", "tech_fn",
    "groups_complete", "targets", "unsupported", "missed", "citations", "keyed",
    "corroborating", "bad_cites", "pair_tp", "pair_fp", "pair_fn", "cost", "trace",
)


def summarise_scores(rows):
    return summarise([{key: row[key] for key in SCORE_FIELDS} for row in rows])


def multi_record_candidates(trace):
    """Necessary structural screen for this cohort. Record IDs alone establish no support."""
    return sorted(tid for tid in {c["technique"] for c in trace}
                  if len({c["cite"].split(".")[0] for c in trace
                          if c["technique"] == tid and c["text"] is not None}) >= 2)
