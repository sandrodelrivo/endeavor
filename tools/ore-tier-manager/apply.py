"""Regenerate biome JSON `features` arrays from biome_overrides.yaml.

Reads:
    config/biome_overrides.yaml
    data/endeavour/tags/worldgen/biome/*.json (for biome -> tag membership)

For every biome JSON on disk, recomputes the features array as:
    union over (tags the biome belongs to) of (tag's biome_overrides entry)
    then biome-id-specific override applied on top.
Writes that array back into the biome JSON, preserving every other
field (climate, mob spawns, surface rules, original key order, indent,
trailing newline).

The xlsx is NEVER read.

Usage:
    python apply.py             # write biome JSONs
    python apply.py --dry-run   # report what would change, no writes
    python apply.py --diff      # show per-biome feature diffs vs. current
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path

from common import (
    CONFIG_DIR,
    GENERATION_STEPS,
    all_biome_files,
    biome_id_from_path,
    biome_to_tags,
    detect_format,
    load_all_endeavour_tags,
    resolve_biomes,
    write_json_preserving,
    yaml_load,
)


def load_existing() -> dict[str, tuple[Path, OrderedDict, list[list[str]]]]:
    """Return biome_id -> (path, parsed_json, current_features_array)."""
    out: dict[str, tuple[Path, OrderedDict, list[list[str]]]] = {}
    for f in all_biome_files():
        biome_id = biome_id_from_path(f)
        text = f.read_text(encoding="utf-8")
        data = json.loads(text, object_pairs_hook=OrderedDict)
        feats = [list(s) for s in data.get("features", [])]
        out[biome_id] = (f, data, feats)
    return out


def diff_features(
    before: list[list[str]],
    after: list[list[str]],
) -> list[tuple[str, str, str]]:
    n = max(len(before), len(after))
    out: list[tuple[str, str, str]] = []
    for i in range(n):
        b = set(before[i]) if i < len(before) else set()
        a = set(after[i]) if i < len(after) else set()
        step = GENERATION_STEPS[i] if i < len(GENERATION_STEPS) else f"step{i}"
        for f in sorted(a - b):
            out.append((step, "+", f))
        for f in sorted(b - a):
            out.append((step, "-", f))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report changes; do not write")
    parser.add_argument("--diff", action="store_true",
                        help="print per-biome feature additions/removals")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="only summary output")
    args = parser.parse_args()

    bo_path = CONFIG_DIR / "biome_overrides.yaml"
    if not bo_path.exists():
        print(f"ERROR: missing {bo_path}. Run extract.py first to bootstrap.",
              file=sys.stderr)
        return 2

    biome_overrides = yaml_load(bo_path) or {}
    existing = load_existing()
    on_disk_ids = set(existing)
    tags = load_all_endeavour_tags(on_disk_ids=on_disk_ids)
    b2t = biome_to_tags(tags)

    existing_feats = {b: t[2] for b, t in existing.items()}

    try:
        resolved = resolve_biomes(b2t, biome_overrides, existing_feats)
    except ValueError as e:
        print(f"ERROR resolving biomes: {e}", file=sys.stderr)
        return 3

    changed = 0
    unchanged = 0
    diffs: list[tuple[str, list[tuple[str, str, str]]]] = []

    for biome_id in sorted(resolved):
        path, data, before = existing[biome_id]
        after = resolved[biome_id]
        if before == after:
            unchanged += 1
            continue
        changed += 1
        diffs.append((biome_id, diff_features(before, after)))
        if not args.dry_run:
            data["features"] = after
            fmt = detect_format(path.read_text(encoding="utf-8"))
            write_json_preserving(path, data, fmt)

    if args.diff or (args.dry_run and not args.quiet):
        for biome_id, d in diffs:
            print(f"\n{biome_id}")
            for step, sign, feat in d:
                print(f"  {sign} [{step}] {feat}")

    print()
    print(f"  resolved: {len(resolved)} biomes")
    print(f"  unchanged: {unchanged}")
    print(f"  changed:   {changed}{' (dry-run; no writes)' if args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
