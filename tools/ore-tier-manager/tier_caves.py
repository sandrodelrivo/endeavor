"""Replace each cave biome's overworld.json entry with tier-aligned variants.

Endeavour's noise router drives biome selection off custom temperature
(linear N/S gradient, clamped at +/-1 in the wastelands ~30k from spawn)
and vegetation (periodic sinusoid). Vanilla weirdness is unused. Tier
boundaries fall along the temperature axis per
`design/tier-map.xlsx` Climate Map sheet:

    very_cold  temp in [-1.0, -0.6]   -> T4
    cold       temp in [-0.6, -0.2]   -> T2
    temperate  temp in [-0.2,  0.2]   -> T1
    warm       temp in [ 0.2,  0.6]   -> T2
    hot        temp in [ 0.6,  1.0]   -> T4

Each cave biome has an existing temperature range set by Terralith
(e.g. lush_caves T=[-1, 0.3]). For each tier band that intersects the
cave's range, this script:

  1. Ensures the tier variant biome JSON exists at
     `data/endeavour/worldgen/biome/<short>_t<N>.json` (cloned from
     the original biome JSON; identical content).
  2. Adds an overworld.json entry pointing to that tier variant with
     the band's temperature sub-range and the cave's other parameters
     unchanged (humidity, continentalness, depth, weirdness, erosion,
     offset all preserved).

A single tier variant biome may receive multiple overworld.json entries
when more than one band of the same tier intersects the cave's temp
range (e.g. T2 cold band + T2 warm band -> two entries pointing to
`endeavour:lush_caves_t2`).

Tag JSONs (tier_1.json, tier_2.json, tier_4.json) get updated to
include exactly the tier variants that were generated, with the
original cave biome IDs removed.

Idempotent: deletes any pre-existing endeavour cave entries from
overworld.json before re-adding, so re-running with new band
boundaries Just Works.

Usage:
    python tier_caves.py             # do it
    python tier_caves.py --dry-run   # report what would change

After running, re-run apply.py to regenerate biome_modifier files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import DATAPACK_ROOT, ENDEAVOUR_TAG_DIR


CAVE_BIOMES = [
    "minecraft:dripstone_caves",
    "minecraft:lush_caves",
    "terralith:cave/deep_caves",
    "terralith:cave/underground_jungle",
    "terralith:cave/thermal_caves",
    "terralith:cave/infested_caves",
    "terralith:cave/fungal_caves",
    "terralith:cave/granite_caves",
    "terralith:cave/andesite_caves",
    "terralith:cave/diorite_caves",
    "terralith:cave/tuff_caves",
    "terralith:cave/frostfire_caves",
    "terralith:cave/mantle_caves",
]

# (band_name, temp_range, tier_suffix)
# Tier suffix matches the tag tier_<N>.json. Multiple bands can map to
# the same tier (e.g. cold + warm both map to t2).
BANDS: list[tuple[str, tuple[float, float], str]] = [
    ("very_cold", (-1.0, -0.6), "t4"),
    ("cold",      (-0.6, -0.2), "t2"),
    ("temperate", (-0.2,  0.2), "t1"),
    ("warm",      ( 0.2,  0.6), "t2"),
    ("hot",       ( 0.6,  1.0), "t4"),
]
TIERS = ("t1", "t2", "t4")

OVERWORLD_PATH = DATAPACK_ROOT / "minecraft" / "dimension" / "overworld.json"
ENDEAVOUR_BIOME_DIR = DATAPACK_ROOT / "endeavour" / "worldgen" / "biome"


def clone_biome_id(original: str, tier_suffix: str) -> str:
    namespace, path = original.split(":", 1)
    return f"endeavour:{path}_{tier_suffix}"


def clone_biome_path(original: str, tier_suffix: str) -> Path:
    namespace, path = original.split(":", 1)
    return ENDEAVOUR_BIOME_DIR / f"{path}_{tier_suffix}.json"


def find_original_biome_path(original: str) -> Path:
    namespace, path = original.split(":", 1)
    return DATAPACK_ROOT / namespace / "worldgen" / "biome" / f"{path}.json"


def intersect(a: tuple[float, float], b: tuple[float, float]
              ) -> tuple[float, float] | None:
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    if lo >= hi:
        return None
    return (lo, hi)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="report changes; do not write")
    args = parser.parse_args()

    overworld = json.loads(OVERWORLD_PATH.read_text(encoding="utf-8"))
    bs_biomes: list[dict] = overworld["generator"]["biome_source"]["biomes"]

    # 1. Find the parameter blocks for original cave entries (they're
    #    the source of truth for non-temperature parameters).
    cave_to_entry: dict[str, dict] = {}
    for entry in bs_biomes:
        if entry["biome"] in CAVE_BIOMES and entry["biome"] not in cave_to_entry:
            cave_to_entry[entry["biome"]] = entry

    # 2. Strip ALL existing entries that point to cave biomes:
    #    - originals (CAVE_BIOMES list) - we replace them
    #    - any pre-existing tiered clones (endeavour:*_t1/_t2/_t4) from
    #      previous runs - they get rebuilt
    def is_cave_clone(biome_id: str) -> bool:
        if not biome_id.startswith("endeavour:"):
            return False
        leaf = biome_id.split(":", 1)[1]
        return any(leaf.endswith(f"_{t}") for t in TIERS)

    keep_biomes = [
        b for b in bs_biomes
        if b["biome"] not in CAVE_BIOMES and not is_cave_clone(b["biome"])
    ]
    removed_count = len(bs_biomes) - len(keep_biomes)

    # 3. For each cave biome present, find which tiers + which bands
    #    intersect its temperature range. Generate a new entry per band.
    new_entries: list[dict] = []
    tiers_used_per_cave: dict[str, set[str]] = {}  # cave -> {t1, t2, t4}
    missing_caves = []
    for cave in CAVE_BIOMES:
        entry = cave_to_entry.get(cave)
        if entry is None:
            missing_caves.append(cave)
            continue
        cave_temp = entry["parameters"]["temperature"]
        cave_temp_tuple = (float(cave_temp[0]), float(cave_temp[1]))
        for band_name, band_range, tier in BANDS:
            inter = intersect(cave_temp_tuple, band_range)
            if inter is None:
                continue
            new_entry = json.loads(json.dumps(entry))  # deep copy
            new_entry["biome"] = clone_biome_id(cave, tier)
            new_entry["parameters"]["temperature"] = [inter[0], inter[1]]
            new_entries.append(new_entry)
            tiers_used_per_cave.setdefault(cave, set()).add(tier)

    # 4. Determine which tier variant biome JSONs need to be on disk.
    biome_files_to_write: list[tuple[Path, dict]] = []
    biome_files_to_remove: list[Path] = []
    for cave in CAVE_BIOMES:
        if cave in missing_caves:
            continue
        orig_path = find_original_biome_path(cave)
        if not orig_path.exists():
            print(f"FAIL: original {cave} not at {orig_path}", file=sys.stderr)
            return 2
        orig_data = json.loads(orig_path.read_text(encoding="utf-8"))
        used = tiers_used_per_cave.get(cave, set())
        for tier in TIERS:
            target = clone_biome_path(cave, tier)
            if tier in used:
                if not target.exists():
                    biome_files_to_write.append((target, orig_data))
            else:
                if target.exists():
                    biome_files_to_remove.append(target)

    if missing_caves:
        print(f"NOTE: {len(missing_caves)} cave biomes have no overworld.json "
              f"entry: {missing_caves}", file=sys.stderr)

    # 5. Tag JSON updates: each tier_X tag carries clones for every
    #    cave that has a variant at that tier.
    tag_updates: dict[str, dict] = {}
    for tier in TIERS:
        tag_name = f"tier_{tier[1:]}"
        tag_path = ENDEAVOUR_TAG_DIR / f"{tag_name}.json"
        tag_data = json.loads(tag_path.read_text(encoding="utf-8"))
        values = [
            v for v in tag_data.get("values", [])
            if v not in CAVE_BIOMES and not is_cave_clone(v)
        ]
        for cave in CAVE_BIOMES:
            if tier in tiers_used_per_cave.get(cave, set()):
                values.append(clone_biome_id(cave, tier))
        tag_data["values"] = sorted(set(values))
        tag_updates[tag_name] = tag_data

    # Report
    print("Plan:")
    print(f"  Removed {removed_count} stale cave/clone entries from overworld.json")
    print(f"  Adding  {len(new_entries)} new tier-banded entries")
    print(f"  Biome JSONs: {len(biome_files_to_write)} to create, "
          f"{len(biome_files_to_remove)} to remove")
    print(f"  Tag JSONs:   {len(tag_updates)} to update")
    print()
    for cave in CAVE_BIOMES:
        if cave in missing_caves:
            continue
        tiers_str = ", ".join(sorted(tiers_used_per_cave.get(cave, set())))
        bands_for_cave = []
        for band_name, band_range, tier in BANDS:
            cave_temp = cave_to_entry[cave]["parameters"]["temperature"]
            if intersect((float(cave_temp[0]), float(cave_temp[1])), band_range):
                bands_for_cave.append(f"{band_name}->{tier}")
        print(f"  {cave}: tiers={{{tiers_str}}}  bands={', '.join(bands_for_cave)}")

    if args.dry_run:
        print("\n(dry-run; no writes)")
        return 0

    # Execute
    overworld["generator"]["biome_source"]["biomes"] = keep_biomes + new_entries
    OVERWORLD_PATH.write_text(json.dumps(overworld, indent=4) + "\n",
                              encoding="utf-8")

    ENDEAVOUR_BIOME_DIR.mkdir(parents=True, exist_ok=True)
    for target, data in biome_files_to_write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    for target in biome_files_to_remove:
        target.unlink()

    for tag_name, tag_data in tag_updates.items():
        tag_path = ENDEAVOUR_TAG_DIR / f"{tag_name}.json"
        tag_path.write_text(json.dumps(tag_data, indent=4) + "\n",
                            encoding="utf-8")

    print()
    print("Done. Re-run apply.py to regenerate biome_modifier files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
