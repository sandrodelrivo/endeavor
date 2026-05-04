"""Bootstrap the YAML config from the current biome JSONs.

One-shot: reads every biome JSON in the datapack + tier-map.xlsx, factors
out per-(tier, step) intersections into tier_templates.yaml, and emits the
per-biome additions/removals into biome_overrides.yaml. After this runs,
`apply.py` should reproduce the existing JSONs feature-list-equivalent.

Usage:
    python extract.py            # writes config/{tier_templates,biome_overrides}.yaml
    python extract.py --force    # overwrite even if files already exist

Intentionally NOT idempotent with apply.py output - this is the bootstrap
seed. Run it once on a fresh checkout, then iterate by editing the YAML.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict, Counter
from pathlib import Path

import openpyxl

from common import (
    CONFIG_DIR,
    DATAPACK_ROOT,
    GENERATION_STEPS,
    TIER_MAP_XLSX,
    all_biome_files,
    biome_id_from_path,
    normalize_biome_id,
    yaml_dump,
)


# Tiers we group for template extraction. Other tiers (TURN OFF, TX, or biomes
# absent from the xlsx) get per-biome @set entries with no template fallback.
GROUP_TIERS = ("T1", "T2", "T4")

TIER_TEMPLATES_HEADER = """\
# Per-tier baseline feature lists. Resolution order per biome:
#   tier_templates[biome.tier][step] -> tag overrides -> biome-id overrides
#
# Steps follow vanilla 1.21.1 GenerationStep.Decoration order:
#   raw_generation, lakes, local_modifications, underground_structures,
#   surface_structures, strongholds, underground_ores, underground_decoration,
#   fluid_springs, vegetal_decoration, top_layer_modification.
#
# Ops (in dict-form blocks):
#   "@inherit": <other tier>      -- start from another tier's resolved list
#   "@set":   [...]               -- replace whatever was inherited
#   "@add":   [...]               -- append (dedup)
#   "@remove":[...]               -- drop by ID
# A bare list is shorthand for @set.
#
# IE secondary ores (immersiveengineering:bauxite/lead/nickel/silver/deep_nickel)
# are intentionally absent: their tier home is undecided. createnuclear:lead_ore
# and create:striated_ores_overworld are likewise pending. To enable, add them
# under the appropriate tier or under a tag-based biome_overrides entry.
"""

BIOME_OVERRIDES_HEADER = """\
# Per-biome additions/removals on top of the tier template.
#
# Keys:
#   "<namespace>:<path>"          -- single biome (e.g. "minecraft:badlands")
#   "#endeavour:<tag>"            -- expands via the tag JSON; tag overrides
#                                    apply BEFORE biome-id overrides so a
#                                    specific biome can override a tag default.
#
# Per-step ops: same vocabulary as tier_templates.yaml (@set/@add/@remove).
#
# Bootstrap note: this file was seeded by extract.py from the current
# biome JSONs. Each biome carries its full delta from the tier template.
# As you iterate, prefer adding shared features to tier_templates.yaml
# and removing them from individual biome entries here.
"""


def load_tier_map(on_disk_ids: set[str] | None = None) -> dict[str, str]:
    """Read the Biomes sheet -> {biome_id: tier_string}.

    If on_disk_ids is provided, normalize xlsx biome IDs against on-disk
    paths so xlsx-side cave/ prefix typos don't drop biomes.
    """
    wb = openpyxl.load_workbook(TIER_MAP_XLSX, data_only=True)
    ws = wb["Biomes"]
    out: dict[str, str] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        biome_id, source, _climate, _terrain, tier, *_ = row
        if not biome_id:
            continue
        bid = str(biome_id).strip()
        if on_disk_ids:
            bid = normalize_biome_id(bid, on_disk_ids)
        out[bid] = (str(tier).strip() if tier else "")
    return out


def load_existing_features() -> tuple[dict[str, list[list[str]]], dict[str, Path]]:
    """Read every biome JSON; return {biome_id: features_array} + {biome_id: path}."""
    feats: dict[str, list[list[str]]] = {}
    paths: dict[str, Path] = {}
    for f in all_biome_files():
        biome_id = biome_id_from_path(f)
        data = json.loads(f.read_text(encoding="utf-8"))
        feats[biome_id] = [list(s) for s in data.get("features", [])]
        paths[biome_id] = f
    return feats, paths


def first_appearance_order(biome_lists: list[list[str]]) -> list[str]:
    """Stable ordering of features by first-appearance across the input lists.

    Used to give the tier template a deterministic order even though set
    intersection itself is unordered.
    """
    out: list[str] = []
    seen: set[str] = set()
    for lst in biome_lists:
        for f in lst:
            if f not in seen:
                seen.add(f)
                out.append(f)
    return out


def compute_tier_template(
    biomes_in_tier: list[tuple[str, list[list[str]]]],
) -> dict[str, list[str]]:
    """Per step: intersection of features across all biomes in this tier.

    Result is keyed by step name (only steps with non-empty intersection).
    """
    out: dict[str, list[str]] = {}
    for i, step in enumerate(GENERATION_STEPS):
        per_step_lists = [feats[i] if i < len(feats) else [] for _, feats in biomes_in_tier]
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
    template: dict[str, list[str]],
) -> dict[str, dict]:
    """Diff one biome's features against its tier template.

    Returns step_name -> {"@add": [...], "@remove": [...]} (only present
    when non-empty). If the diff is empty across all steps, returns {}.
    """
    out: dict[str, dict] = {}
    for i, step in enumerate(GENERATION_STEPS):
        biome_step = biome_features[i] if i < len(biome_features) else []
        tmpl_step = template.get(step, [])
        adds = [f for f in biome_step if f not in tmpl_step]
        removes = [f for f in tmpl_step if f not in biome_step]
        block: dict = {}
        if adds:
            block["@add"] = adds
        if removes:
            block["@remove"] = removes
        if block:
            out[step] = block
    return out


def compute_biome_set(biome_features: list[list[str]]) -> dict[str, dict]:
    """For untiered biomes: emit a full @set per step with content."""
    out: dict[str, dict] = {}
    for i, step in enumerate(GENERATION_STEPS):
        biome_step = biome_features[i] if i < len(biome_features) else []
        if biome_step:
            out[step] = {"@set": list(biome_step)}
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing YAML files")
    args = parser.parse_args()

    feats, paths = load_existing_features()
    tier_map = load_tier_map(on_disk_ids=set(feats))

    in_xlsx_not_in_dp = sorted(set(tier_map) - set(feats))
    in_dp_not_in_xlsx = sorted(set(feats) - set(tier_map))
    if in_xlsx_not_in_dp:
        print(f"WARN: {len(in_xlsx_not_in_dp)} biomes in xlsx but no JSON file: "
              f"{in_xlsx_not_in_dp[:5]}{'...' if len(in_xlsx_not_in_dp) > 5 else ''}",
              file=sys.stderr)
    if in_dp_not_in_xlsx:
        print(f"NOTE: {len(in_dp_not_in_xlsx)} biomes have JSON but aren't in xlsx; "
              f"will emit per-biome @set: {in_dp_not_in_xlsx}",
              file=sys.stderr)

    # Group by tier
    by_tier: dict[str, list[tuple[str, list[list[str]]]]] = {t: [] for t in GROUP_TIERS}
    untiered: list[str] = []
    for biome_id, biome_feats in feats.items():
        tier = tier_map.get(biome_id, "")
        if tier in GROUP_TIERS:
            by_tier[tier].append((biome_id, biome_feats))
        else:
            untiered.append(biome_id)

    # Compute tier templates
    tier_templates: OrderedDict = OrderedDict()
    tier_templates["tiers"] = OrderedDict()
    for tier in GROUP_TIERS:
        if not by_tier[tier]:
            continue
        tmpl = compute_tier_template(by_tier[tier])
        if tmpl:
            tier_templates["tiers"][tier] = tmpl

    # Compute per-biome overrides
    biome_overrides: OrderedDict = OrderedDict()
    # Tiered biomes first (sorted), then untiered
    tiered_biomes = sorted(b for t in GROUP_TIERS for b, _ in by_tier[t])
    for biome_id in tiered_biomes:
        tier = tier_map[biome_id]
        tmpl = tier_templates["tiers"].get(tier, {})
        diff = compute_biome_diff(feats[biome_id], tmpl)
        if diff:
            biome_overrides[biome_id] = diff
    for biome_id in sorted(untiered):
        s = compute_biome_set(feats[biome_id])
        if s:
            biome_overrides[biome_id] = s

    # Write
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tt_path = CONFIG_DIR / "tier_templates.yaml"
    bo_path = CONFIG_DIR / "biome_overrides.yaml"
    if not args.force:
        for p in (tt_path, bo_path):
            if p.exists():
                print(f"ERROR: {p} already exists. Use --force to overwrite.",
                      file=sys.stderr)
                return 2

    yaml_dump(tt_path, tier_templates, header=TIER_TEMPLATES_HEADER)
    yaml_dump(bo_path, biome_overrides, header=BIOME_OVERRIDES_HEADER)

    # Summary
    print(f"Wrote {tt_path.relative_to(CONFIG_DIR.parent)}: "
          f"{len(tier_templates['tiers'])} tier templates")
    for tier in GROUP_TIERS:
        if tier in tier_templates["tiers"]:
            tmpl = tier_templates["tiers"][tier]
            steps_filled = sum(1 for v in tmpl.values() if v)
            print(f"  {tier}: {steps_filled} non-empty steps, "
                  f"{sum(len(v) for v in tmpl.values())} total features")
    print(f"Wrote {bo_path.relative_to(CONFIG_DIR.parent)}: "
          f"{len(biome_overrides)} biome entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
