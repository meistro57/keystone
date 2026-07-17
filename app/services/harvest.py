# filename: app/services/harvest.py
"""
Harvest = build cross-source concept themes, then hang meaning + validity on each.

Two passes so we never pull 34k vectors into RAM:
  Pass 1 (payload only)  — scroll reflections, map concept -> [(id, source)]
  Pass 2 (with vectors)  — for qualifying themes, retrieve members + misfit survival
"""

from __future__ import annotations
import hashlib
from collections import defaultdict

from qdrant_client import QdrantClient

import config
from app.models.schema import Node, MemberReflection
from app.services import qdrant as q
from app.services import scoring
from app.utils.log import get_logger

log = get_logger()


def _slug(concept: str) -> str:
    return hashlib.sha256(concept.lower().encode()).hexdigest()[:16]


def _named_vector(rec) -> list[float] | None:
    v = rec.vector
    if v is None:
        return None
    if isinstance(v, dict):
        return v.get(config.REFLECTION_VECTOR_NAME) or next(iter(v.values()), None)
    return v


def harvest(c: QdrantClient, limit: int | None = None,
            min_convergence: float = 0.0) -> list[Node]:
    # ── Pass 1: concept → members (payload only) ──────────────────────────
    concept_members: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
    scanned = 0
    for rec in q.scroll_all(c, config.REFLECTIONS_COLLECTION, with_vectors=False):
        p = rec.payload or {}
        if p.get(config.R_EMPTY):
            continue
        src = p.get(config.R_SOURCE)
        for concept in (p.get(config.R_CONCEPTS) or []):
            key = str(concept).strip().lower()
            if not key or key in config.STOP_CONCEPTS:
                continue
            concept_members[key].append((str(rec.id), str(src) if src else None))
        scanned += 1
    log.info(f"scanned {scanned} reflections → {len(concept_members)} distinct concepts")

    # ── Qualify themes: enough members AND enough distinct sources ─────────
    themes: list[Node] = []
    for concept, members in concept_members.items():
        ids = [mid for mid, _ in members]
        sources = sorted({s for _, s in members if s})
        if len(ids) >= config.MIN_MEMBERS and len(sources) >= config.MIN_SOURCES:
            themes.append(Node(theme_id=_slug(concept), concept=concept,
                               member_ids=ids, full_sources=sources))

    qualified = len(themes)
    # breadth first, then volume
    themes.sort(key=lambda n: (n.n_sources, len(n.member_ids)), reverse=True)

    # ── PRUNE before hydration ─────────────────────────────────────
    # max possible convergence = centrality (coherence, survival are both <=1),
    # so anything whose breadth can't reach the gate can be dropped with zero
    # false negatives — and never hydrated. This is the whole speedup.
    if min_convergence > 0:
        themes = [n for n in themes if scoring.centrality(n) >= min_convergence]
        log.info(f"{qualified} themes qualified; {len(themes)} can reach gate "
                 f">= {min_convergence} (breadth prune skipped {qualified - len(themes)})")
    else:
        log.info(f"{qualified} themes clear >= {config.MIN_MEMBERS} members "
                 f"across >= {config.MIN_SOURCES} sources")

    if limit:
        themes = themes[:limit]

    for i, n in enumerate(themes, 1):
        _hydrate(c, n)
        if i % 100 == 0 or i == len(themes):
            log.info(f"  hydrated {i}/{len(themes)} themes")
    return themes


def _hydrate(c: QdrantClient, node: Node) -> None:
    # sample members for coherence (cap the vector pull)
    sample = node.member_ids[:config.COHERENCE_SAMPLE]
    recs = q.retrieve(c, config.REFLECTIONS_COLLECTION, sample, with_vectors=True)
    survival = q.survival_by_id(c, sample)

    for r in recs:
        p = r.payload or {}
        node.members.append(MemberReflection(
            point_id=str(r.id),
            summary=str(p.get(config.R_SUMMARY, "") or ""),
            source_id=(str(p[config.R_SOURCE]) if config.R_SOURCE in p else None),
            vector=_named_vector(r),
            survival_score=survival.get(str(r.id)),
        ))
    reviewed = sum(1 for m in node.members if m.survival_score is not None)
    log.debug(f"  · {node.concept!r} — {node.n_sources} sources, "
              f"{len(node.members)} members, {reviewed} critiqued")
