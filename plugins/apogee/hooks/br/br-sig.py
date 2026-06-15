#!/usr/bin/env python3
"""Reduce `br list --json` (stdin) to a stable signature: sha256 of sorted id|status|updated_at
plus the count. Used by br-snapshot.sh (baseline) and br-progress-gate.sh (compare)."""
import sys, json, hashlib
try:
    d = json.load(sys.stdin)
    items = d.get("issues", []) if isinstance(d, dict) else (d or [])
    parts = sorted(f"{i.get('id')}|{i.get('status')}|{i.get('updated_at')}" for i in items)
    print(hashlib.sha256("\n".join(parts).encode()).hexdigest() + " " + str(len(parts)))
except Exception:
    print("NA")
