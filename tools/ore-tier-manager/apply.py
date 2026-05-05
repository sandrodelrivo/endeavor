"""Strip catalog ores from biome JSONs + regenerate endeavour biome_modifiers.

Reads:
    config/ore_catalog.yaml
    config/biome_overrides.yaml
    data/endeavour/tags/worldgen/biome/*.json

Writes (or rewrites on every run):
    All biome JSONs              - catalog ores removed from `features`
    data/endeavour/neoforge/biome_modifier/<tag>__<step>.json
                                 - one per (tag, step) with ores

The biome_modifier directory is fully tool-managed: any pre-existing
endeavour biome_modifier file is wiped and replaced. The mod-side
`neoforge:none` shadows under data/<modid>/ are NEVER touched.

Usage:
    python apply.py             # do it
    python apply.py --dry-run   # report what would change
    python apply.py --diff      # per-biome ore stripping diff + biome_modifier list
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path

from common import (
    BIOME_OVERRIDES_PATH,
    ENDEAVOUR_BIOME_MODIFIER_DIR,
    GENERATION_STEPS,
    all_biome_files,
    biome_id_from_path,
    biome_modifier_files,
    biome_to_tags,
    detect_format,
    load_all_endeavour_tags,
    load_ore_catalog,
    load_ore_catalog_ordered,
    strip_catalog_ores,
    write_json_preserving,
    yaml_load,
)


def load_existing() -> dict[str, tuple[Path, OrderedDict, list[list[str]]]]:
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
                        help="per-biome ore stripping diff")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="only summary output")
    args = parser.parse_args()

    if not BIOME_OVERRIDES_PATH.exists():
        print(f"ERROR: missing {BIOME_OVERRIDES_PATH}. Run extract.py first.",
              file=sys.stderr)
        return 2

    catalog = load_ore_catalog()
    biome_overrides = yaml_load(BIOME_OVERRIDES_PATH)
    existing = load_existing()

    # Strip catalog ores from EVERY biome JSON, including ones in zero
    # endeavour tags. Otherwise an untagged biome keeps its Terralith
    # default ores at positions that conflict with the biome_modifier
    # ordering used for tagged biomes, and MC's FeatureSorter rejects
    # the world with "Feature order cycle found" on first chunk gen.
    #
    # Practically: untagged biomes end up with no catalog ores at all.
    # That's the tool's design ("tool entirely drives ore distribution").
    # To bring an untagged biome under tool management, add it to a tag
    # in the GUI; otherwise it generates with no ores.
    on_disk = set(existing)
    tags = load_all_endeavour_tags(on_disk_ids=on_disk)
    tags_by_biome = biome_to_tags(tags)
    untagged = sorted(on_disk - set(tags_by_biome))

    json_changes: list[tuple[str, list[tuple[str, str, str]]]] = []
    biome_writes: list[tuple[Path, OrderedDict, list[list[str]]]] = []
    for biome_id in sorted(existing):
        path, data, before = existing[biome_id]
        after = strip_catalog_ores(before, catalog)
        if before == after:
            continue
        json_changes.append((biome_id, diff_features(before, after)))
        biome_writes.append((path, data, after))

    # 2. Compute biome_modifier file set (per-biome ore-set resolution +
    # equivalence-class grouping; each biome matches exactly one
    # modifier per step, ores in catalog order)
    catalog_order = load_ore_catalog_ordered()
    try:
        modifiers = biome_modifier_files(
            biome_overrides, catalog, catalog_order, tags_by_biome
        )
    except ValueError as e:
        print(f"ERROR resolving biome_modifiers: {e}", file=sys.stderr)
        return 3

    # 3. Compute biome_modifier diff against existing dir
    existing_modifier_files = {
        f.name: json.loads(f.read_text(encoding="utf-8"))
        for f in ENDEAVOUR_BIOME_MODIFIER_DIR.glob("*.json")
    } if ENDEAVOUR_BIOME_MODIFIER_DIR.exists() else {}

    new_filenames = set(modifiers)
    old_filenames = set(existing_modifier_files)
    to_create = new_filenames - old_filenames
    to_delete = old_filenames - new_filenames
    to_update = {
        n for n in (new_filenames & old_filenames)
        if existing_modifier_files[n] != modifiers[n]
    }
    unchanged = (new_filenames & old_filenames) - to_update

    # Print
    if args.diff or (args.dry_run and not args.quiet):
        for biome_id, d in json_changes:
            print(f"\n{biome_id}")
            for step, sign, feat in d:
                print(f"  {sign} [{step}] {feat}")
        if json_changes:
            print()
        for n in sorted(to_create):
            print(f"  + biome_modifier {n}")
        for n in sorted(to_update):
            print(f"  ~ biome_modifier {n}")
        for n in sorted(to_delete):
            print(f"  - biome_modifier {n}")

    # Write
    if not args.dry_run:
        for path, data, after in biome_writes:
            data["features"] = after
            fmt = detect_format(path.read_text(encoding="utf-8"))
            write_json_preserving(path, data, fmt)
        ENDEAVOUR_BIOME_MODIFIER_DIR.mkdir(parents=True, exist_ok=True)
        for n in to_delete:
            (ENDEAVOUR_BIOME_MODIFIER_DIR / n).unlink()
        for n in (to_create | to_update):
            content = modifiers[n]
            text = json.dumps(content, indent=2, ensure_ascii=False) + "\n"
            (ENDEAVOUR_BIOME_MODIFIER_DIR / n).write_text(text, encoding="utf-8")

    print()
    print(f"  biomes:           {len(existing)} read, "
          f"{len(json_changes)} stripped, "
          f"{len(existing) - len(json_changes)} clean")
    print(f"  biome_modifiers:  "
          f"{len(to_create)} added, "
          f"{len(to_update)} updated, "
          f"{len(to_delete)} removed, "
          f"{len(unchanged)} unchanged")
    if untagged and not args.quiet:
        print(f"  untagged biomes (no ores at runtime): "
              f"{untagged[:5]}{'...' if len(untagged) > 5 else ''}")
    if args.dry_run:
        print("  (dry-run; no writes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
