#!/usr/bin/env python
# filename: inspect.py
"""
Keystone field mapper.

Dumps the REAL payload shape of your three lens collections so you can map
config.py to what's actually in Qdrant. Run this, read the output, fix the
field names in .env. No LLM, no writes.

    python inspect.py
"""

from collections import Counter

import config
from app.services import qdrant as q

SAMPLE = 5          # sample points per collection
TYPE_SCAN = 400     # points to scan for distinct "type-like" values


def truncate(v, n=70):
    s = str(v)
    return s if len(s) <= n else s[:n] + "…"


def describe(c, collection, guess_type=None, guess_members=None):
    print("\n" + "═" * 70)
    print(f"  {collection}")
    print("═" * 70)
    try:
        info = c.get_collection(collection)
        print(f"  points: {info.points_count}")
        # vector config (named vs single)
        vp = info.config.params.vectors
        print(f"  vectors: {vp}")
    except Exception as e:
        print(f"  !! could not read collection: {e}")
        return

    recs = list(q.scroll_all(c, collection))[:SAMPLE]
    if not recs:
        print("  (empty)")
        return

    # payload keys from first sample point, with types + example values
    print("\n  payload fields (from sample point):")
    p0 = recs[0].payload or {}
    for k, v in p0.items():
        kind = type(v).__name__
        note = ""
        if isinstance(v, list):
            note = f"  ← LIST[{len(v)}]  (member-ids candidate?)"
        print(f"    {k:<24} {kind:<8} = {truncate(v)}{note}")

    print(f"\n  point id type: {type(recs[0].id).__name__}  e.g. {truncate(recs[0].id)}")

    # scan distinct values of a suspected "type" field
    if guess_type:
        vals = Counter()
        for r in list(q.scroll_all(c, collection))[:TYPE_SCAN]:
            pv = (r.payload or {}).get(guess_type)
            if pv is not None:
                vals[str(pv)] += 1
        if vals:
            print(f"\n  distinct '{guess_type}' values (top): "
                  f"{dict(vals.most_common(12))}")
        else:
            print(f"\n  field '{guess_type}' not present — look above for the real type field")

    if guess_members:
        has = sum(1 for r in recs if isinstance((r.payload or {}).get(guess_members), list))
        print(f"  '{guess_members}' present as list in {has}/{len(recs)} sample points")


def main():
    c = q.client()
    print(f"Qdrant: {config.QDRANT_URL}")
    existing = {col.name for col in c.get_collections().collections}
    print(f"collections present: {sorted(existing)}")

    describe(c, config.FINDINGS_COLLECTION,
             guess_type=config.F_TYPE, guess_members=config.F_MEMBERS)
    describe(c, config.REFLECTIONS_COLLECTION, guess_type=config.R_SOURCE)
    describe(c, config.MISFIT_COLLECTION, guess_type=config.M_VERDICT)

    print("\n" + "─" * 70)
    print("  Now edit .env so F_TYPE / F_MEMBERS / CANDIDATE_TYPES match what you see.")
    print("─" * 70)


if __name__ == "__main__":
    main()
