# filename: app/models/schema.py
"""Typed carriers passed between the pipeline stages."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class MemberReflection:
    point_id: str
    summary: str
    source_id: str | None
    vector: list[float] | None = None
    survival_score: float | None = None   # None = no misfit report found


@dataclass
class Node:
    """A cross-source concept theme — the candidate thesis."""
    theme_id: str
    concept: str
    member_ids: list[str]
    full_sources: list[str] = field(default_factory=list)   # true breadth (Pass 1)
    members: list[MemberReflection] = field(default_factory=list)

    @property
    def sample_sources(self) -> list[str]:
        return sorted({m.source_id for m in self.members if m.source_id})

    @property
    def source_ids(self) -> list[str]:
        # prefer true breadth from Pass 1; fall back to hydrated sample
        return self.full_sources or self.sample_sources

    @property
    def n_sources(self) -> int:
        return len(self.source_ids)


@dataclass
class Scored:
    node: Node
    centrality: float
    coherence: float
    survival: float
    convergence: float


@dataclass
class Keystone:
    theme_id: str
    concept: str
    statement: str
    one_liner: str
    themes: list[str]
    reasoning: str
    critic_verdict: str
    critic_notes: str
    convergence: float
    centrality: float
    coherence: float
    survival: float
    n_sources: int
    member_reflection_ids: list[str]
    source_ids: list[str]
    model: str

    def payload(self) -> dict[str, Any]:
        return asdict(self)
