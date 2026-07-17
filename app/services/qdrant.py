# filename: app/services/qdrant.py
"""Qdrant layer. Reads reflections + misfit reports (joined by point id), writes keystones."""

from __future__ import annotations
import json
import re
from typing import Any, Iterable

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

import config
from app.utils.log import get_logger

log = get_logger()

_JSON_BLOCK = re.compile(r"\{[^{}]*\}", re.DOTALL)


def client() -> QdrantClient:
    return QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY, timeout=120)


def scroll_all(c: QdrantClient, collection: str, with_vectors: bool = False,
               flt: qm.Filter | None = None, page: int = 512) -> Iterable[qm.Record]:
    offset = None
    while True:
        recs, offset = c.scroll(
            collection_name=collection, scroll_filter=flt,
            with_payload=True, with_vectors=with_vectors, limit=page, offset=offset,
        )
        for r in recs:
            yield r
        if offset is None:
            break


def retrieve(c: QdrantClient, collection: str, ids: list[Any],
             with_vectors: bool = False) -> list[qm.Record]:
    if not ids:
        return []
    return c.retrieve(collection_name=collection, ids=ids,
                      with_payload=True, with_vectors=with_vectors)


def _num(v, default: float = 0.0) -> float:
    """float() that survives None / null / '' / garbage."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _parse_rubric(text: str) -> float | None:
    """Pull the JSON rubric out of a misfit verdict essay → a 0..1 survival score."""
    if not text:
        return None
    best = None
    for m in _JSON_BLOCK.finditer(text):
        blob = m.group(0)
        if config.RUBRIC_CONSISTENCY not in blob and config.RUBRIC_VALIDITY not in blob:
            continue
        try:
            d = json.loads(blob)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        cons = _num(d.get(config.RUBRIC_CONSISTENCY))
        val = _num(d.get(config.RUBRIC_VALIDITY))
        drift = _num(d.get(config.RUBRIC_DRIFT))
        best = max(0.0, min(1.0, ((cons + val) / 2.0) * (1.0 - drift)))
    return best


def survival_by_id(c: QdrantClient, reflection_ids: list[Any]) -> dict[str, float]:
    """misfit_reports shares point ids with meta_reflections. Retrieve, parse rubric."""
    out: dict[str, float] = {}
    if not reflection_ids:
        return out
    try:
        recs = retrieve(c, config.MISFIT_COLLECTION, reflection_ids)
    except Exception as e:
        log.warning(f"misfit retrieve skipped: {e}")
        return out
    for r in recs:
        try:
            p = r.payload or {}
            text = str(p.get(config.M_VERDICT_FIELD, "") or p.get(config.M_FALLBACK_FIELD, "") or "")
            score = _parse_rubric(text)
            if score is not None:
                out[str(r.id)] = score
        except Exception as e:
            log.warning(f"rubric parse skipped for {r.id}: {e}")
    return out


def ensure_keystones(c: QdrantClient) -> None:
    existing = {col.name for col in c.get_collections().collections}
    if config.KEYSTONES_COLLECTION in existing:
        return
    log.info(f"creating collection '{config.KEYSTONES_COLLECTION}' ({config.EMBED_DIM}d)")
    c.create_collection(
        collection_name=config.KEYSTONES_COLLECTION,
        vectors_config=qm.VectorParams(size=config.EMBED_DIM, distance=qm.Distance.COSINE),
    )


def upsert_keystone(c: QdrantClient, point_id: str, vector: list[float],
                    payload: dict[str, Any]) -> None:
    c.upsert(collection_name=config.KEYSTONES_COLLECTION,
             points=[qm.PointStruct(id=point_id, vector=vector, payload=payload)])
