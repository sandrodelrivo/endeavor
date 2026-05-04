"""Sanity-check the post-apply state.

Catches the kinds of drift that would crash worldgen or silently regress
distribution:
  * malformed biome JSONs
  * biome JSONs that still contain catalog ores (apply.py drift)
  * biome_overrides.yaml entries referencing features not in the catalog
    (would be silently dropped at apply time)
  * tag JSONs referencing biomes not on disk
  * orphaned endeavour biome_modifier files (don't correspond to any
    biome_overrides.yaml tag entry)

Usage:
    python validate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from common import (
    BIOME_OVERRIDES_PATH,
    DATAPACK_ROOT,
    ENDEAVOUR_BIOME_MODIFIER_DIR,
    ENDEAVOUR_TAG_DIR,
    GENERATION_STEPS,
    OP_ADD,
    OP_REMOVE,
    OP_SET,
    all_biome_files,
    biome_id_from_path,
    extract_features,
    load_all_endeavour_tags,
    load_ore_catalog,
    normalize_biome_id,
    yaml_load,
)


def validate() -> int:
    issues = 0

    catalog = load_ore_catalog()

    # 1. Parse all biome JSONs + check they don't have catalog ores
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

    # 2. Catalog-ore-leakage check: NO biome JSON should contain any
    #    catalog ore (apply.py strips them from every biome, tagged or
    #    not, to avoid FeatureSorter cycles between biome JSON ordering
    #    and biome_modifier-injected ordering).
    on_disk = set(biome_features)
    raw_tags = load_all_endeavour_tags(on_disk_ids=on_disk)
    leaked: dict[str, list[str]] = {}
    for biome_id, steps in biome_features.items():
        for step in steps:
            for f in step:
                if f in catalog:
                    leaked.setdefault(biome_id, []).append(f)
    if leaked:
        print(f"WARN: {len(leaked)} biome(s) still contain catalog ores "
              f"in their JSON. Re-run apply.py to strip them:",
              file=sys.stderr)
        for biome_id, ores in sorted(leaked.items())[:5]:
            print(f"  {biome_id}: {ores[:5]}{'...' if len(ores) > 5 else ''}",
                  file=sys.stderr)
        if len(leaked) > 5:
            print(f"  ... and {len(leaked) - 5} more", file=sys.stderr)

    # 3. biome_overrides.yaml: check tag entries reference catalog ores
    if BIOME_OVERRIDES_PATH.exists():
        bo = yaml_load(BIOME_OVERRIDES_PATH)
        non_catalog: dict[str, list[str]] = {}
        biome_id_keys: list[str] = []
        for key, steps in bo.items():
            if not isinstance(key, str):
                continue
            if not key.startswith("#endeavour:") and ":" in key:
                # biome-id key (legacy format from pre-catalog architecture)
                biome_id_keys.append(key)
                continue
            if not key.startswith("#endeavour:"):
                continue
            if not isinstance(steps, dict):
                continue
            for step, block in steps.items():
                for f in extract_features(block):
                    if f not in catalog:
                        non_catalog.setdefault(key, []).append(f"{step}: {f}")
        if non_catalog:
            print(f"WARN: biome_overrides.yaml has {sum(len(v) for v in non_catalog.values())} "
                  f"feature ID(s) not in ore_catalog.yaml. apply.py will silently "
                  f"drop these:", file=sys.stderr)
            for key, refs in sorted(non_catalog.items())[:5]:
                print(f"  {key}: {refs[:3]}{'...' if len(refs) > 3 else ''}",
                      file=sys.stderr)
        if biome_id_keys:
            print(f"WARN: biome_overrides.yaml has {len(biome_id_keys)} biome-id "
                  f"keys. The catalog architecture only honors #endeavour:<tag> "
                  f"keys; these will be ignored:", file=sys.stderr)
            for k in biome_id_keys[:5]:
                print(f"  {k}", file=sys.stderr)

    # 4. Tag JSONs: stale biome IDs
    raw_tags_unnormalized = load_all_endeavour_tags()
    stale: dict[str, list[str]] = {}
    for tag, ids in raw_tags_unnormalized.items():
        for bid in ids:
            if normalize_biome_id(bid, on_disk) not in on_disk:
                stale.setdefault(tag, []).append(bid)
    if stale:
        print("WARN: tag JSONs reference biomes not on disk:", file=sys.stderr)
        for tag, ids in sorted(stale.items()):
            print(f"  {tag}: {ids[:5]}{'...' if len(ids) > 5 else ''}",
                  file=sys.stderr)

    # 5. Orphan endeavour biome_modifier files
    if ENDEAVOUR_BIOME_MODIFIER_DIR.exists():
        bo = yaml_load(BIOME_OVERRIDES_PATH) if BIOME_OVERRIDES_PATH.exists() else {}
        expected: set[str] = set()
        for key, steps in bo.items():
            if not isinstance(key, str) or not key.startswith("#endeavour:"):
                continue
            if not isinstance(steps, dict):
                continue
            tag = key[len("#endeavour:"):]
            for step in steps:
                if any(extract_features(steps[step])):
                    expected.add(f"{tag}__{step}.json")
        actual = {f.name for f in ENDEAVOUR_BIOME_MODIFIER_DIR.glob("*.json")}
        orphans = actual - expected
        # Allow legacy 06_*-10_* files; flag others
        legacy = {n for n in orphans if n[:2].isdigit() and "_" in n}
        true_orphans = orphans - legacy
        if true_orphans:
            print(f"WARN: {len(true_orphans)} orphan biome_modifier file(s) in "
                  f"{ENDEAVOUR_BIOME_MODIFIER_DIR.relative_to(DATAPACK_ROOT)} "
                  f"(not produced by current biome_overrides.yaml; re-run apply):",
                  file=sys.stderr)
            for n in sorted(true_orphans)[:5]:
                print(f"  {n}", file=sys.stderr)
        if legacy:
            print(f"NOTE: {len(legacy)} legacy biome_modifier file(s) "
                  f"(06_*-10_*) still present. apply.py will replace them "
                  f"with tool-generated <tag>__<step>.json files on next run.",
                  file=sys.stderr)

    # 6. RUNTIME ordering check: simulate NeoForge applying biome_modifiers
    # in alphabetical order on top of biome JSONs, then look for cycles
    # across the resulting per-biome feature lists. This is what MC's
    # FeatureSorter checks at world load; failing it here prevents
    # "Feature order cycle found" crashes in the actual game.
    runtime_modifiers: list[tuple[str, str, list[str]]] = []
    for f in sorted(ENDEAVOUR_BIOME_MODIFIER_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("type") != "neoforge:add_features":
            continue
        biomes_field = data.get("biomes", "")
        step = data.get("step", "")
        feats_field = data.get("features", [])
        if not isinstance(biomes_field, str) or not biomes_field.startswith("#endeavour:"):
            continue
        if step not in GENERATION_STEPS:
            continue
        feats = [feats_field] if isinstance(feats_field, str) else list(feats_field)
        runtime_modifiers.append((biomes_field[len("#endeavour:"):], step, feats))

    cycle_count = 0
    for step_idx, step in enumerate(GENERATION_STEPS):
        edges: dict[str, set[str]] = {}
        nodes_order: list[str] = []
        seen_node: set[str] = set()
        for biome_id, steps in biome_features.items():
            seq = list(steps[step_idx]) if step_idx < len(steps) else []
            for tag, mstep, feats in runtime_modifiers:
                if mstep != step:
                    continue
                if biome_id in raw_tags.get(tag, set()):
                    seq.extend(feats)
            for f in seq:
                if f not in seen_node:
                    seen_node.add(f)
                    nodes_order.append(f)
                edges.setdefault(f, set())
            for a, b in zip(seq, seq[1:]):
                edges[a].add(b)
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
            cyc = [n for n in nodes_order if n not in emitted]
            print(f"FAIL: runtime ordering cycle at step '{step}' (would crash "
                  f"with 'Feature order cycle found'): "
                  f"{cyc[:8]}{'...' if len(cyc) > 8 else ''}", file=sys.stderr)
            cycle_count += 1
    if cycle_count:
        issues += cycle_count

    print()
    if issues:
        print(f"validate: {issues} hard issue(s) found", file=sys.stderr)
        return 1
    print(f"validate: OK ({len(biome_features)} biomes, "
          f"{len(catalog)} catalog ores)")
    return 0


if __name__ == "__main__":
    raise SystemExit(validate())
