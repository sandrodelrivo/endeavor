"""Bootstrap biome_overrides.yaml from current biome JSONs + tag JSONs + catalog.

For each tag:
  - Look at the biomes in the tag.
  - Find every catalog ore that's currently in EVERY one of those biomes
    at some step (intersection per step).
  - Write that as `#endeavour:<tag>: {<step>: {@add: [...]}}` in
    biome_overrides.yaml.

That's it. No biome-id keys. Non-ore features stay in biome JSONs.

The first apply.py run after extract will:
  - Strip the listed catalog ores from biome JSONs.
  - Generate biome_modifier files that re-inject them via tag tags.
  - Net: the post-migration worldgen should be feature-list-equivalent
    to current state (you'll be able to verify via git diff and a
    fresh-world test).

Usage:
    python extract.py            # writes config/biome_overrides.yaml
    python extract.py --force    # overwrite if it already exists
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path

from common import (
    BIOME_OVERRIDES_PATH,
    CONFIG_DIR,
    ENDEAVOUR_BIOME_MODIFIER_DIR,
    GENERATION_STEPS,
    STEP_INDEX,
    all_biome_files,
    biome_id_from_path,
    biome_to_tags,
    load_all_endeavour_tags,
    load_ore_catalog,
    load_ore_catalog_ordered,
    yaml_dump,
)


BIOME_OVERRIDES_HEADER = """\
# Tag -> ore assignments. The single source of truth for ore distribution.
#
# Keys:
#   "#endeavour:<tag>"            -- applies to every biome listed in
#                                    `data/endeavour/tags/worldgen/biome/<tag>.json`.
#                                    Biome-id keys are NOT supported in this
#                                    architecture; per-biome ore exceptions
#                                    require putting the biome in a tag of
#                                    its own.
#
# Per-step ops:
#   "@set":   [...]               -- replace whatever was inherited from earlier tags
#   "@add":   [...]               -- append (dedup)
#   "@remove":[...]               -- drop by ID
# Use @add for tag entries; @set will silently wipe earlier tags' contributions.
#
# Resolution per biome (at apply time):
#   biome's ores = union over (tags this biome is in, sorted) of
#                  (each tag's ore list per step)
#
# Steps follow vanilla 1.21.1 GenerationStep.Decoration order:
#   raw_generation, lakes, local_modifications, underground_structures,
#   surface_structures, strongholds, underground_ores, underground_decoration,
#   fluid_springs, vegetal_decoration, top_layer_modification.
#
# Only ores in config/ore_catalog.yaml are valid here. Non-catalog
# features get silently dropped at apply time and are flagged by validate.py.
"""


def load_existing_features() -> dict[str, list[list[str]]]:
    feats: dict[str, list[list[str]]] = {}
    for f in all_biome_files():
        feats[biome_id_from_path(f)] = [
            list(s) for s in json.loads(f.read_text(encoding="utf-8")).get("features", [])
        ]
    return feats


def per_tag_unassigned_union(
    biomes_in_tag: list[tuple[str, list[list[str]]]],
    catalog: set[str],
    catalog_order: list[str],
    already_assigned: dict[str, dict[int, set[str]]],
) -> dict[str, list[str]]:
    """Per step: UNION of catalog ores across biomes in this tag, minus
    ores already claimed by a previously-processed tag, emitted in
    catalog order.

    Catalog ordering is critical: NeoForge applies multiple
    biome_modifiers to a biome and the resulting per-step feature list
    must have a consistent cross-biome ordering. If tier_2 emits ores
    in one order and tier_4 in another, biomes that share ores via the
    union of their tag memberships hit MC's FeatureSorter cycle check
    ("Feature order cycle found"). Sorting every tag's emission by
    catalog position guarantees they all agree.
    """
    catalog_index = {ore: i for i, ore in enumerate(catalog_order)}
    out: dict[str, list[str]] = {}
    for i, step in enumerate(GENERATION_STEPS):
        union: set[str] = set()
        for biome_id, feats in biomes_in_tag:
            biome_step = feats[i] if i < len(feats) else []
            covered = already_assigned.get(biome_id, {}).get(i, set())
            for f in biome_step:
                if f in catalog and f not in covered:
                    union.add(f)
        if union:
            out[step] = sorted(union, key=lambda f: catalog_index.get(f, 1 << 30))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing biome_overrides.yaml")
    args = parser.parse_args()

    catalog = load_ore_catalog()
    catalog_order = load_ore_catalog_ordered()
    feats = load_existing_features()
    on_disk = set(feats)
    tags = load_all_endeavour_tags(on_disk_ids=on_disk)

    # Validate tag membership against on-disk biomes; drop stale entries
    for tag, biomes in tags.items():
        stale = biomes - on_disk
        if stale:
            print(f"NOTE: tag '{tag}' has {len(stale)} biomes not on disk; "
                  f"dropping for extract.", file=sys.stderr)
            tags[tag] = biomes & on_disk

    bo: OrderedDict = OrderedDict()
    # Track per-(biome, step) which ores have already been assigned to a tag.
    # The next tag's intersection only considers ores not yet claimed.
    already_assigned: dict[str, dict[int, set[str]]] = {
        b: {i: set() for i in range(len(GENERATION_STEPS))} for b in feats
    }

    # Path A: seed modded ores from LEGACY endeavour biome_modifiers (the
    # 06_*-10_* files that inject zinc/uranium/thorium/oil). These ores
    # aren't in any biome JSON (mod biome_modifiers were neutralized),
    # so the union pass below would otherwise miss them.
    #
    # Skip files using our tool-generated naming convention (`<tag>__<step>.json`).
    # If we re-ingested those, second-run extract would resurrect any ore
    # we'd previously deleted via the GUI - the tool would never converge.
    seeded_from_modifiers: list[str] = []
    if ENDEAVOUR_BIOME_MODIFIER_DIR.exists():
        for mf in sorted(ENDEAVOUR_BIOME_MODIFIER_DIR.glob("*.json")):
            if "__" in mf.stem:
                continue  # tool-generated file; biome_overrides.yaml is authoritative
            try:
                data = json.loads(mf.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if data.get("type") != "neoforge:add_features":
                continue
            biomes_field = data.get("biomes", "")
            step = data.get("step")
            features_field = data.get("features", [])
            if (not isinstance(biomes_field, str)
                    or not biomes_field.startswith("#endeavour:")
                    or step not in STEP_INDEX):
                continue
            tag = biomes_field[len("#endeavour:"):]
            features = ([features_field] if isinstance(features_field, str)
                        else list(features_field))
            features = [f for f in features if f in catalog]
            if not features:
                continue
            entry = bo.setdefault(f"#endeavour:{tag}", OrderedDict())
            step_block = entry.setdefault(step, {"@add": []})
            adds = step_block.setdefault("@add", [])
            step_idx = STEP_INDEX[step]
            for f in features:
                if f not in adds:
                    adds.append(f)
                    seeded_from_modifiers.append(f"{mf.name} -> {tag}/{step}/{f}")
            # Mark these ores as covered for biomes in the tag
            for b in tags.get(tag, set()):
                if b in already_assigned:
                    already_assigned[b][step_idx].update(features)
    if seeded_from_modifiers:
        print(f"NOTE: seeded {len(seeded_from_modifiers)} ore(s) from existing "
              f"endeavour biome_modifiers:", file=sys.stderr)
        for s in seeded_from_modifiers:
            print(f"  {s}", file=sys.stderr)

    # Path B: tag-driven intersection extraction, processing tags in order
    # of decreasing biome-set size. Each tag claims ores common to its
    # biomes that no earlier tag has already covered. This partitions
    # catalog ores across tags (no double-counting -> no NeoForge multi-add).
    tag_order = sorted(tags, key=lambda t: (-len(tags[t]), t))
    for tag in tag_order:
        biomes_in_tag = [(b, feats[b]) for b in sorted(tags[tag]) if b in feats]
        if not biomes_in_tag:
            continue
        per_step = per_tag_unassigned_union(
            biomes_in_tag, catalog, catalog_order, already_assigned)
        if not per_step:
            continue
        entry = bo.setdefault(f"#endeavour:{tag}", OrderedDict())
        for step, ores in per_step.items():
            step_block = entry.setdefault(step, {"@add": []})
            adds = step_block.setdefault("@add", [])
            for f in ores:
                if f not in adds:
                    adds.append(f)
            step_idx = STEP_INDEX[step]
            for b, _ in biomes_in_tag:
                already_assigned[b][step_idx].update(ores)

    # Report ores that won't be covered for biomes that ARE in some tag.
    # Untagged biomes are skipped by apply.py and keep their existing ores,
    # so reporting them here is noise.
    tagged_biome_set = {b for b in feats if b in {bb for ids in tags.values() for bb in ids}}
    leftover: dict[str, dict[str, list[str]]] = {}
    for biome_id, feats_arr in feats.items():
        if biome_id not in tagged_biome_set:
            continue
        for i, step_arr in enumerate(feats_arr):
            biome_ores = {f for f in step_arr if f in catalog}
            covered = already_assigned[biome_id][i]
            missing = biome_ores - covered
            if missing:
                step_name = GENERATION_STEPS[i] if i < len(GENERATION_STEPS) else f"step{i}"
                leftover.setdefault(biome_id, {}).setdefault(step_name, []).extend(sorted(missing))
    if leftover:
        n_biomes = len(leftover)
        n_total = sum(len(s) for v in leftover.values() for s in v.values())
        print(f"\nWARN: {n_total} ore-instance(s) across {n_biomes} biome(s) "
              f"are NOT covered by any tag (they currently exist in the "
              f"biome JSON but no tag's full membership shares them). "
              f"They'll be lost when apply.py strips the biome JSONs.",
              file=sys.stderr)
        # Show first few examples
        shown = 0
        for biome_id, steps in sorted(leftover.items()):
            for step, ores in steps.items():
                for f in ores:
                    print(f"  {biome_id} [{step}] {f}", file=sys.stderr)
                    shown += 1
                    if shown >= 15:
                        break
                if shown >= 15:
                    break
            if shown >= 15:
                break
        if n_total > 15:
            print(f"  ... and {n_total - 15} more", file=sys.stderr)
        print(f"  Fix: assign these biomes to a tag that includes the ore, "
              f"or add a singleton tag for the exception.", file=sys.stderr)

    if BIOME_OVERRIDES_PATH.exists() and not args.force:
        print(f"ERROR: {BIOME_OVERRIDES_PATH} exists. Use --force to overwrite.",
              file=sys.stderr)
        return 2

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    yaml_dump(BIOME_OVERRIDES_PATH, bo, header=BIOME_OVERRIDES_HEADER)

    # Drop tier_templates.yaml if present (legacy)
    tt_path = CONFIG_DIR / "tier_templates.yaml"
    if tt_path.exists():
        tt_path.unlink()
        print(f"Removed legacy {tt_path.name}", file=sys.stderr)

    # Summary
    print(f"Wrote {BIOME_OVERRIDES_PATH.relative_to(CONFIG_DIR.parent)}: "
          f"{len(bo)} tag entries")
    for key, steps in bo.items():
        total = sum(len(extract_features_for_summary(b)) for b in steps.values())
        print(f"  {key}: {total} ores across {len(steps)} step(s)")
    return 0


def extract_features_for_summary(block) -> list[str]:
    if isinstance(block, list):
        return list(block)
    if isinstance(block, dict):
        return list(block.get("@add", [])) + list(block.get("@set", []))
    return []


if __name__ == "__main__":
    raise SystemExit(main())
