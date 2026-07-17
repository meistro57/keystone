#!/usr/bin/env python
# filename: run.py
"""
Keystone CLI.

  python run.py --dry-run                 # score everything, write nothing, eyeball it
  python run.py --limit 25                # forge the 25 richest nodes
  python run.py --min-convergence 0.55    # tighter canon
  python run.py                           # full run at config defaults
"""

import argparse

from app.main import run


def main():
    ap = argparse.ArgumentParser(description="Keystone — forge canon from the meta-bridge stack")
    ap.add_argument("--limit", type=int, default=None, help="cap number of nodes")
    ap.add_argument("--min-convergence", type=float, default=None, help="override score gate")
    ap.add_argument("--dry-run", action="store_true", help="score only, write nothing")
    args = ap.parse_args()
    run(limit=args.limit, min_convergence=args.min_convergence, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
