# filename: app/services/writer.py
"""Embed the canonical statement and upsert it into the keystones collection."""

from __future__ import annotations
import hashlib
import threading

from qdrant_client import QdrantClient

from app.models.schema import Keystone
from app.services import qdrant as q
from app.services import llm
from app.utils.log import get_logger

log = get_logger()
_write_lock = threading.Lock()  # serialize only the upsert; embeds run parallel


def _stable_id(k: Keystone) -> str:
    h = hashlib.sha256(f"keystone:{k.theme_id}".encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def write(c: QdrantClient, k: Keystone) -> None:
    vector = llm.embed(k.statement)          # network-bound, safe to run concurrently
    with _write_lock:                        # guard the shared client's upsert
        q.upsert_keystone(c, _stable_id(k), vector, k.payload())
