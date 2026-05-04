"""Bootstrap biome_overrides.yaml from the current biome JSONs + tag JSONs.

One-shot. Reads every biome JSON in the datapack and every endeavour
tag JSON, factors per-(tag, step) feature intersections into
`#endeavour:<tag>` entries in biome_overrides.yaml, and emits the
per-biome diffs as biome-id keys. After this runs, `apply.py` should
reproduce the existing biome JSONs feature-list-equivalent.

The xlsx is NEVER read. Tag JSONs are the sole source of truth for
biome -> tag membership.

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
    CONFIG_DIR,
    DATAPACK_ROOT,
    GENERATION_STEPS,
    all_biome_files,
    biome_id_from_path,
    biome_to_tags,
    load_all_endeavour_tags,
    yaml_dump,
)


# Tags whose biome lists are large enough that intersection-based extraction
# is useful. Other tags (cross-cutting, often small) get empty entries that
# the user fills in manually as they migrate ore distribution into tags.
INTERSECTION_TAGS_DEFAULT = ("tier_1", "tier_2", "tier_4")


BIOME_OVERRIDES_HEADER = """\
# Biome-overrides: the only place where ore lists live.
#
# Two kinds of keys:
#   "#endeavour:<tag>"            -- applies to every biome listed in
#                                    `data/endeavour/tags/worldgen/biome/<tag>.json`.
#   "<namespace>:<biome>"         -- applies to a single biome on top of
#                                    its tag overrides.
#
# Per-step ops:
#   "@set":   [...]               -- replace whatever was inherited from tags
#   "@add":   [...]               -- append (dedup)
#   "@remove":[...]               -- drop by ID
# A bare list is shorthand for @set.
#
# Resolution per biome:
#   features = (apply each tag's overrides in tag-name sort order)
#              then (apply biome-id-specific overrides)
#
# Steps follow vanilla 1.21.1 GenerationStep.Decoration order:
#   raw_generation, lakes, local_modifications, underground_structures,
#   surface_structures, strongholds, underground_ores, underground_decoration,
#   fluid_springs, vegetal_decoration, top_layer_modification.
#
# IE secondary ores (immersiveengineering:bauxite/lead/nickel/silver/deep_nickel),
# createnuclear:lead_ore, and create:striated_ores_overworld are intentionally
# absent: their tag home is undecided. To enable, add them under the
# appropriate tag entry.
#
# The xlsx (design/tier-map.xlsx) is documentation only; this tool never
# reads or writes it.
"""


def load_existing_features() -> dict[str, list[list[str]]]:
    feats: dict[str, list[list[str]]] = {}
    for f in all_biome_files():
        biome_id = biome_id_from_path(f)
        data = json.loads(f.read_text(encoding="utf-8"))
        feats[biome_id] = [list(s) for s in data.get("features", [])]
    return feats


def first_appearance_order(biome_lists: list[list[str]]) -> list[str]:
    """Stable ordering of features by first-appearance across the input lists."""
    out: list[str] = []
    seen: set[str] = set()
    for lst in biome_lists:
        for f in lst:
            if f not in seen:
                seen.add(f)
                out.append(f)
    return out


def compute_tag_intersection(
    biomes_in_tag: list[tuple[str, list[list[str]]]],
) -> dict[str, list[str]]:
    """Per step: features present in EVERY biome in the tag.

    Result keyed by step name; only steps with non-empty intersection
    are included.
    """
    out: dict[str, list[str]] = {}
    for i, step in enumerate(GENERATION_STEPS):
        per_step_lists = [feats[i] if i < len(feats) else [] for _, feats in biomes_in_tag]
        if not per_step_lists:
            continue
        intersection = set(per_step_lists[0])
        for lst in per_step_lists[1:]:
            intersection &= set(lst)
        if not intersection:
            continue
        ordering = first_appearance_order(per_step_lists)
        out[step] = [f for f in ordering if f in intersection]
    return out


def compute_biome_diff(
    biome_features: list[list[str]],
    baseline: dict[str, list[str]],
) -> dict[str, dict]:
    """Diff one biome's features against its tag-derived baseline.

    Returns step_name -> {"@add": [...], "@remove": [...]} (only present
    when non-empty). Empty diffs return {}.
    """
    out: dict[str, dict] = {}
    for i, step in enumerate(GENERATION_STEPS):
        biome_step = biome_features[i] if i < len(biome_features) else []
        base_step = baseline.get(step, [])
        adds = [f for f in biome_step if f not in base_step]
        removes = [f for f in base_step if f not in biome_step]
        block: dict = {}
        if adds:
            block["@add"] = adds
        if removes:
            block["@remove"] = removes
        if block:
            out[step] = block
    return out


def compute_biome_set(biome_features: list[list[str]]) -> dict[str, dict]:
    """For biomes with no tag baseline: emit a full @set per non-empty step."""
    out: dict[str, dict] = {}
    for i, step in enumerate(GENERATION_STEPS):
        biome_step = biome_features[i] if i < len(biome_features) else []
        if biome_step:
            out[step] = {"@set": list(biome_step)}
    return out


def union_baselines(biome_id: str,
                    biome_to_tags_map: dict[str, list[str]],
                    tag_baselines: dict[str, dict[str, list[str]]],
                    ) -> dict[str, list[str]]:
    """Compute the per-step baseline a biome inherits from all its tags.

    Tags are applied in alphabetical order (matches resolve_biomes).
    A feature added by an earlier tag survives later tag passes unless
    a later tag explicitly removes it (which extract doesn't generate).
    """
    out: dict[str, list[str]] = {}
    for tag in sorted(biome_to_tags_map.get(biome_id, [])):
        tag_steps = tag_baselines.get(tag, {})
        for step, feats in tag_steps.items():
            cur = out.setdefault(step, [])
            for f in feats:
                if f not in cur:
                    cur.append(f)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing biome_overrides.yaml")
    parser.add_argument("--intersection-tags", nargs="*",
                        default=list(INTERSECTION_TAGS_DEFAULT),
                        help=f"tags to factor by intersection. "
                             f"Default: {INTERSECTION_TAGS_DEFAULT}")
    args = parser.parse_args()

    feats = load_existing_features()
    on_disk_ids = set(feats)
    tags = load_all_endeavour_tags(on_disk_ids=on_disk_ids)
    b2t = biome_to_tags(tags)

    # Drop biomes from tag membership that aren't actually on disk
    for tag, biomes in tags.items():
        missing = biomes - on_disk_ids
        if missing:
            print(f"WARN: tag '{tag}' lists {len(missing)} biome(s) not on "
                  f"disk: {sorted(missing)[:3]}{'...' if len(missing) > 3 else ''}",
                  file=sys.stderr)
            tags[tag] = biomes & on_disk_ids

    # Compute intersection-based baseline for selected tags
    tag_baselines: dict[str, dict[str, list[str]]] = {}
    for tag in args.intersection_tags:
        if tag not in tags:
            print(f"NOTE: --intersection-tag '{tag}' not present, skipping",
                  file=sys.stderr)
            continue
        biomes_in_tag = [(b, feats[b]) for b in sorted(tags[tag]) if b in feats]
        if not biomes_in_tag:
            continue
        baseline = compute_tag_intersection(biomes_in_tag)
        if baseline:
            tag_baselines[tag] = baseline

    # Build biome_overrides
    bo: OrderedDict = OrderedDict()
    # Tag entries first, sorted (matches resolution order). Wrap each step's
    # list in `{@add: [...]}` so multiple tags compose additively rather
    # than the later tag's bare list silently @set-wiping earlier tags'
    # contributions during resolution.
    for tag in sorted(tag_baselines):
        bo[f"#endeavour:{tag}"] = {
            step: {"@add": list(feats)}
            for step, feats in tag_baselines[tag].items()
        }

    # Per-biome diffs/sets
    for biome_id in sorted(feats):
        baseline = union_baselines(biome_id, b2t, tag_baselines)
        if baseline:
            diff = compute_biome_diff(feats[biome_id], baseline)
        else:
            diff = compute_biome_set(feats[biome_id])
        if diff:
            bo[biome_id] = diff

    bo_path = CONFIG_DIR / "biome_overrides.yaml"
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if bo_path.exists() and not args.force:
        print(f"ERROR: {bo_path} already exists. Use --force to overwrite.",
              file=sys.stderr)
        return 2

    yaml_dump(bo_path, bo, header=BIOME_OVERRIDES_HEADER)

    # Drop tier_templates.yaml if it's still hanging around from the old design
    tt_path = CONFIG_DIR / "tier_templates.yaml"
    if tt_path.exists():
        tt_path.unlink()
        print(f"Removed legacy {tt_path.relative_to(CONFIG_DIR.parent)}",
              file=sys.stderr)

    # Summary
    print(f"Wrote {bo_path.relative_to(CONFIG_DIR.parent)}: "
          f"{len(bo)} entries "
          f"({sum(1 for k in bo if k.startswith('#'))} tag, "
          f"{sum(1 for k in bo if not k.startswith('#'))} biome)")
    for tag, baseline in tag_baselines.items():
        print(f"  #endeavour:{tag}: {sum(len(v) for v in baseline.values())} "
              f"features across {len(baseline)} step(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
