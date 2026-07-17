# filename: app/main.py
"""
Keystone orchestrator.

    harvest  →  score  →  [convergence gate]  →  forge (R1)  →  critic (Gemma)  →  write

Anchored on cross-source concept themes: the last operation that triangulates
meaning, breadth, and adversarial survival into a small canon.
"""

from __future__ import annotations
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
from app.services import qdrant as q
from app.services import harvest as h
from app.services import scoring
from app.services import synth
from app.services import writer
from app.utils.log import get_logger

log = get_logger()


def run(limit: int | None = None, min_convergence: float | None = None,
        dry_run: bool = False, resume: bool = False) -> None:
    threshold = config.MIN_CONVERGENCE if min_convergence is None else min_convergence
    c = q.client()

    log.info("=" * 64)
    log.info(f"KEYSTONE run — threshold={threshold} limit={limit} dry_run={dry_run}")
    log.info("=" * 64)

    # harvest hydrates every theme that can reach the gate (breadth prune inside).
    # --limit no longer caps hydration; it caps how many keystones we FORGE, taken
    # from the top by convergence, so a taste test previews the real top of the canon.
    nodes = h.harvest(c, min_convergence=threshold)
    scored = sorted((scoring.score(n) for n in nodes),
                    key=lambda s: s.convergence, reverse=True)
    survivors = [s for s in scored if s.convergence >= threshold]
    log.info(f"{len(survivors)}/{len(scored)} themes cleared convergence >= {threshold}")

    if dry_run:
        _report(scored, threshold)
        return

    if resume:
        existing = q.existing_theme_ids(c)
        before = len(survivors)
        survivors = [s for s in survivors if s.node.theme_id not in existing]
        log.info(f"resume: skipping {before - len(survivors)} already forged, {len(survivors)} to go")

    if limit:
        survivors = survivors[:limit]
        log.info(f"limit={limit}: forging the top {len(survivors)} by convergence")

    q.ensure_keystones(c)
    total = len(survivors)
    written = 0

    def _forge_one(s):
        k = synth.forge(s)           # R1 synthesis + critic gate (rejects → None)
        if k is not None:
            writer.write(c, k)       # embed + guarded upsert
        return k

    log.info(f"forging {total} keystones with {config.FORGE_WORKERS} workers…")
    with ThreadPoolExecutor(max_workers=config.FORGE_WORKERS) as ex:
        futures = {ex.submit(_forge_one, s): s for s in survivors}
        # as_completed runs in this (main) thread, so the counters need no lock
        for i, fut in enumerate(as_completed(futures), 1):
            s = futures[fut]
            try:
                k = fut.result()
            except Exception as e:
                log.warning(f"[{i}/{total}] forge failed for {s.node.concept!r}: {e}")
                continue
            if k is None:
                log.info(f"[{i}/{total}] rejected {s.node.concept!r}")
            else:
                written += 1
                log.info(f"[{i}/{total}] ok [{k.convergence}] {k.concept!r} — {k.one_liner[:64]}")

    log.info("-" * 64)
    log.info(f"done — {written} keystones written to '{config.KEYSTONES_COLLECTION}'")


def _report(scored, threshold: float) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    path = os.path.join(config.DATA_DIR, "dry_run_scores.json")
    rows = [{
        "concept": s.node.concept,
        "sources": s.node.n_sources,
        "members": len(s.node.members),
        "centrality": round(s.centrality, 3),
        "coherence": round(s.coherence, 3),
        "survival": round(s.survival, 3),
        "convergence": s.convergence,
        "clears": s.convergence >= threshold,
    } for s in scored]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    log.info(f"dry-run scores written to {path}")
    for r in rows[:25]:
        flag = "OK" if r["clears"] else "  "
        log.info(f"  {flag} {r['convergence']:.3f}  src={r['sources']:<2} "
                 f"c={r['centrality']:.2f} h={r['coherence']:.2f} s={r['survival']:.2f}  "
                 f"{r['concept'][:44]}")

    # ── distribution + gate picker ────────────────────────────────────────
    convs = sorted((s.convergence for s in scored), reverse=True)
    total = len(convs)
    log.info("─" * 64)
    log.info("convergence distribution:")
    lo = 0.30
    while lo < 0.95:
        hi = lo + 0.05
        n = sum(1 for v in convs if lo <= v < hi)
        bar = "█" * min(50, n // max(1, total // 200))
        log.info(f"  {lo:.2f}–{hi:.2f}  {n:>4}  {bar}")
        lo = round(lo + 0.05, 2)
    log.info("─" * 64)
    log.info("keystones kept at each gate (pick one for MIN_CONVERGENCE):")
    for g in (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80):
        n = sum(1 for v in convs if v >= g)
        log.info(f"  gate {g:.2f}  →  {n:>4} keystones")
