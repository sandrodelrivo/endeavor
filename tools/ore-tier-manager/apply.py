"""Regenerate biome JSON `features` arrays from YAML inputs.

Reads:
    config/tier_templates.yaml
    config/biome_overrides.yaml
    design/tier-map.xlsx (Biomes sheet -> biome_id -> tier)

For every biome in the xlsx (and any biome present only in biome_overrides),
recomputes the features array as:
    tier_template[tier] -> tag overrides -> biome-id overrides
then writes that array back into the biome JSON, preserving every other
field (climate, mob spawns, surface rules, original key order, indent,
trailing newline behavior).

Cross-biome ordering is enforced by a single global topological sort per
generation step, so two biomes can't end up listing a shared feature in
opposite orders (which crashes worldgen with FeatureSorter's
"Feature order cycle found").

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

import openpyxl

from common import (
    CONFIG_DIR,
    DATAPACK_ROOT,
    GENERATION_STEPS,
    TIER_MAP_XLSX,
    all_biome_files,
    biome_id_from_path,
    detect_format,
    normalize_biome_id,
    resolve_biomes,
    write_json_preserving,
    yaml_load,
)


def load_tier_map(on_disk_ids: set[str]) -> dict[str, str]:
    wb = openpyxl.load_workbook(TIER_MAP_XLSX, data_only=True)
    ws = wb["Biomes"]
    out: dict[str, str] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        biome_id, _src, _climate, _terr, tier, *_ = row
        if not biome_id:
            continue
        bid = normalize_biome_id(str(biome_id).strip(), on_disk_ids)
        out[bid] = (str(tier).strip() if tier else "")
    return out


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
    """Return [(step_name, '+'/'-', feature_id)] for adds/removes."""
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

    tt_path = CONFIG_DIR / "tier_templates.yaml"
    bo_path = CONFIG_DIR / "biome_overrides.yaml"
    if not tt_path.exists() or not bo_path.exists():
        print(
            f"ERROR: missing config files. Run extract.py first to bootstrap.\n"
            f"  expected: {tt_path}\n"
            f"  expected: {bo_path}",
            file=sys.stderr,
        )
        return 2

    tier_templates = yaml_load(tt_path).get("tiers") or {}
    biome_overrides = yaml_load(bo_path) or {}
    existing = load_existing()
    tier_map = load_tier_map(set(existing))

    # Union of biomes from xlsx, biome_overrides (excluding tag keys), and disk
    biomes_in_overrides = {
        k for k in biome_overrides
        if not k.startswith("#") and ":" in k
    }
    all_biomes = set(tier_map) | biomes_in_overrides | set(existing)
    # Restrict to biomes we have files for - we won't create new biome JSONs.
    target_biomes = {b for b in all_biomes if b in existing}
    missing = sorted(all_biomes - target_biomes)
    if missing:
        print(f"WARN: {len(missing)} biomes referenced but no JSON file on disk: "
              f"{missing[:5]}{'...' if len(missing) > 5 else ''}", file=sys.stderr)

    # Pass tier map filtered to target biomes; resolve_biomes also needs the
    # existing features so it can preserve odd step counts (fractured_savanna).
    tm = {b: tier_map.get(b, "") for b in target_biomes}
    existing_feats = {b: existing[b][2] for b in target_biomes}

    try:
        resolved = resolve_biomes(tm, tier_templates, biome_overrides, existing_feats)
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
