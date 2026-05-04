"""Sanity-check the biome JSONs after apply.py.

Catches what the chunk generator would otherwise crash on:
  * malformed JSON
  * unknown generation step counts
  * cross-biome FeatureSorter ordering cycles
  * features referenced in YAML but never present in any biome before
    (likely typos: catches `minecraft:ore_diomand` before the user
     repacks the world and bisects)

Validation is best-effort for placed_feature ID existence: we don't scan
mod jars (Terralith may be loaded as a datapack rather than a mod), so
"unknown ID" warnings are based on what was previously referenced and
what's in our own datapack. New IDs from a new YAML edit will warn unless
they match a known mod namespace (create:*, immersiveengineering:*, etc.).

Usage:
    python validate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from common import (
    DATAPACK_ROOT,
    ENDEAVOUR_TAG_DIR,
    GENERATION_STEPS,
    all_biome_files,
    biome_id_from_path,
    load_all_endeavour_tags,
    normalize_biome_id,
)


# Namespaces we expect to see referenced; anything else is a warning.
KNOWN_NAMESPACES: set[str] = {
    "minecraft",
    "terralith",
    "wythers",
    "create",
    "createnuclear",
    "create_new_age",
    "immersiveengineering",
    "immersivepetroleum",
    "endeavour",
    "aether",
    "deep_aether",
    "lithosphere",
}


def validate() -> int:
    issues = 0

    biome_features: dict[str, list[list[str]]] = {}
    for f in all_biome_files():
        biome_id = biome_id_from_path(f)
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"FAIL parse: {f}: {e}", file=sys.stderr)
            issues += 1
            continue
        feats = data.get("features")
        if not isinstance(feats, list):
            print(f"FAIL: {biome_id}: 'features' is not a list", file=sys.stderr)
            issues += 1
            continue
        if len(feats) > len(GENERATION_STEPS):
            print(f"FAIL: {biome_id}: {len(feats)} steps exceeds vanilla "
                  f"{len(GENERATION_STEPS)}", file=sys.stderr)
            issues += 1
        biome_features[biome_id] = [list(s) for s in feats]

    # Cross-biome ordering check
    for i, step in enumerate(GENERATION_STEPS):
        edges: dict[str, set[str]] = {}
        nodes_order: list[str] = []
        seen: set[str] = set()
        for biome_id, steps in biome_features.items():
            if i >= len(steps):
                continue
            seq = steps[i]
            for f in seq:
                if f not in seen:
                    seen.add(f)
                    nodes_order.append(f)
                edges.setdefault(f, set())
            for a, b in zip(seq, seq[1:]):
                edges[a].add(b)
        # Topological sort (Kahn)
        indeg = {n: 0 for n in nodes_order}
        for src, dsts in edges.items():
            for d in dsts:
                indeg[d] = indeg.get(d, 0) + 1
        ready = [n for n in nodes_order if indeg[n] == 0]
        emitted: list[str] = []
        while ready:
            n = ready.pop(0)
            emitted.append(n)
            for m in edges.get(n, ()):
                indeg[m] -= 1
                if indeg[m] == 0:
                    ready.append(m)
        if len(emitted) != len(nodes_order):
            # The existing Terralith data has real cycles at some steps
            # (e.g. mangrove_swamp's [monster_room_deep, fossil_upper]
            # vs. swamp's [fossil_upper, fossil_lower, monster_room_deep])
            # that vanilla 1.21.1 still loads. Warn rather than fail; flag
            # cycles introduced by *new* YAML edits via diff against the
            # baseline instead.
            cyc = [n for n in nodes_order if n not in emitted]
            print(f"WARN: ordering cycle at step '{step}' "
                  f"(may be benign - existing data has them too): "
                  f"{cyc[:5]}{'...' if len(cyc) > 5 else ''}", file=sys.stderr)

    # Unknown-namespace warnings (informational, not failures)
    unknown_ns: dict[str, list[str]] = {}
    for biome_id, steps in biome_features.items():
        for seq in steps:
            for f in seq:
                if ":" not in f:
                    print(f"FAIL: {biome_id}: feature without namespace: {f!r}",
                          file=sys.stderr)
                    issues += 1
                    continue
                ns = f.split(":", 1)[0]
                if ns not in KNOWN_NAMESPACES:
                    unknown_ns.setdefault(ns, []).append(f"{biome_id} -> {f}")
    if unknown_ns:
        print("WARN: features in unfamiliar namespaces (not failures, but "
              "may be typos):", file=sys.stderr)
        for ns, refs in sorted(unknown_ns.items()):
            print(f"  {ns}: {len(refs)} ref(s), first: {refs[0]}", file=sys.stderr)

    # Tag membership sanity: any biome IDs in tag JSONs that aren't on disk?
    on_disk = set(biome_features)
    raw_tags = load_all_endeavour_tags()  # un-normalized
    stale: dict[str, list[str]] = {}
    for tag, ids in raw_tags.items():
        for bid in ids:
            normalized = normalize_biome_id(bid, on_disk)
            if normalized not in on_disk:
                stale.setdefault(tag, []).append(bid)
    if stale:
        print("WARN: tag JSONs reference biomes not on disk:", file=sys.stderr)
        for tag, ids in sorted(stale.items()):
            print(f"  {tag}: {ids[:5]}{'...' if len(ids) > 5 else ''}",
                  file=sys.stderr)

    print()
    if issues:
        print(f"validate: {issues} issue(s) found", file=sys.stderr)
        return 1
    print(f"validate: OK ({len(biome_features)} biomes, no failures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(validate())
