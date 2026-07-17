# filename: app/services/scoring.py
"""
The convergence score.

  centrality  = cross-tradition breadth   (how many independent sources touch it)
  coherence   = semantic tightness        (member summary_vecs vs their centroid)
  survival    = adversarial rubric         (MisfitCrew consistency/validity - drift)

convergence = centrality**Wc * coherence**Ws * survival**Wv

Multiplicative: weak in any lens → not canon. Centrality-as-breadth is the point —
independent traditions converging on a concept is exactly your evidence.
"""

from __future__ import annotations
import math

import config
from app.models.schema import Node, Scored


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def centrality(node: Node) -> float:
    """Cross-tradition breadth, saturating."""
    return max(0.0, min(1.0, node.n_sources / config.SOURCE_SATURATION))


def coherence(node: Node) -> float:
    vecs = [m.vector for m in node.members if m.vector]
    if len(vecs) < 2:
        return 0.5
    dim = len(vecs[0])
    centroid = [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]
    sims = [_cosine(v, centroid) for v in vecs]
    raw = max(0.0, min(1.0, sum(sims) / len(sims)))
    # verbatim guard: near-identical members = boilerplate/repetition, not convergence
    if raw > config.VERBATIM_CEIL:
        raw *= config.VERBATIM_PENALTY
    return raw


def survival(node: Node) -> float:
    scored = [m.survival_score for m in node.members if m.survival_score is not None]
    if not scored:
        return config.SURVIVAL_NEUTRAL
    return sum(scored) / len(scored)


def score(node: Node) -> Scored:
    ce, co, su = centrality(node), coherence(node), survival(node)
    conv = (ce ** config.W_CENTRALITY) * (co ** config.W_COHERENCE) * (su ** config.W_SURVIVAL)
    return Scored(node=node, centrality=ce, coherence=co, survival=su,
                  convergence=round(conv, 4))
