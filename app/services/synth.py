# filename: app/services/synth.py
"""Forge a scored theme into a canonical thesis (R1), then gate it (Gemma critic)."""

from __future__ import annotations
import os

import config
from app.models.schema import Scored, Keystone
from app.services import llm
from app.utils.log import get_logger

log = get_logger()
_PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "prompts")


def _load(name: str) -> str:
    with open(os.path.join(_PROMPT_DIR, name), encoding="utf-8") as f:
        return f.read()


def _bundle(s: Scored) -> str:
    n = s.node
    lines = [
        f"CONCEPT THEME: {n.concept}",
        f"CONVERGENCE: {s.convergence}  "
        f"(centrality={s.centrality:.2f}, coherence={s.coherence:.2f}, survival={s.survival:.2f})",
        f"TRADITIONS SPANNED ({n.n_sources}): {', '.join(n.source_ids)}",
        "",
        "MEMBER REFLECTIONS (across those sources):",
    ]
    for i, m in enumerate(n.members, 1):
        surv = f" [survival {m.survival_score:.2f}]" if m.survival_score is not None else ""
        src = f" ({m.source_id})" if m.source_id else ""
        lines.append(f"{i}. {m.summary}{src}{surv}")
    return "\n".join(lines)


def forge(s: Scored) -> Keystone | None:
    bundle = _bundle(s)
    try:
        raw = llm.chat_synth(_load("synthesis.md"), bundle, temperature=0.5)
        thesis = llm.parse_json(raw)
    except Exception as e:
        log.warning(f"synthesis failed for {s.node.concept!r}: {e}")
        return None

    try:
        critic_input = (f"CANDIDATE THESIS:\n{thesis.get('statement', '')}\n\n"
                        f"EVIDENCE BUNDLE:\n{bundle}")
        crit = llm.parse_json(llm.chat(config.CRITIC_MODEL, _load("critic.md"),
                                       critic_input, temperature=0.2))
    except Exception as e:
        log.warning(f"critic failed for {s.node.concept!r}: {e}")
        crit = {"verdict": "pass", "notes": "critic unavailable; passed by default"}

    verdict = str(crit.get("verdict", "pass")).lower()
    if verdict == "reject":
        log.info(f"  x rejected {s.node.concept!r}: {crit.get('notes', '')[:120]}")
        return None

    statement = crit.get("revised_statement") or thesis.get("statement", "")
    return Keystone(
        theme_id=s.node.theme_id,
        concept=s.node.concept,
        statement=statement,
        one_liner=thesis.get("one_liner", ""),
        themes=thesis.get("themes", []) or [],
        reasoning=thesis.get("reasoning", ""),
        critic_verdict=verdict,
        critic_notes=crit.get("notes", ""),
        convergence=s.convergence,
        centrality=s.centrality,
        coherence=s.coherence,
        survival=s.survival,
        n_sources=s.node.n_sources,
        member_reflection_ids=[m.point_id for m in s.node.members],
        source_ids=s.node.source_ids,
        model=f"{llm.active_synth_model()} + {config.CRITIC_MODEL}",
    )
