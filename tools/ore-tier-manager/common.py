"""Shared constants, paths, formatting helpers, and resolution algorithm.

Single source of truth for the layout of the datapack and the schema of the
YAML inputs. Both extract.py and apply.py use these.
"""

from __future__ import annotations

import json
import os
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = TOOL_ROOT / "config"
DATAPACK_ROOT = REPO_ROOT / "datapack-worldgen" / "zzz_endeavour_worldgen" / "data"
TIER_MAP_XLSX = REPO_ROOT / "design" / "tier-map.xlsx"
ENDEAVOUR_TAG_DIR = DATAPACK_ROOT / "endeavour" / "tags" / "worldgen" / "biome"

# Vanilla 1.21.1 generation step registry order. Confirmed against
# net.minecraft.world.level.levelgen.GenerationStep.Decoration values.
GENERATION_STEPS: tuple[str, ...] = (
    "raw_generation",
    "lakes",
    "local_modifications",
    "underground_structures",
    "surface_structures",
    "strongholds",
    "underground_ores",
    "underground_decoration",
    "fluid_springs",
    "vegetal_decoration",
    "top_layer_modification",
)
STEP_INDEX: dict[str, int] = {name: i for i, name in enumerate(GENERATION_STEPS)}


def biome_id_to_path(biome_id: str) -> Path:
    """Map `namespace:path` to its biome JSON inside the datapack.

    Minecraft's biome ID is the file path relative to `data/<ns>/worldgen/
    biome/` minus the `.json` extension - so `terralith:cave/deep_caves`
    lives at `terralith/worldgen/biome/cave/deep_caves.json`.

    The tier-map.xlsx is inconsistent: some Terralith cave biomes appear
    with the `cave/` prefix and some without. We try the literal path
    first; if missing and there's no slash in the leaf, we also try
    `cave/<leaf>` for terralith biomes (covers the xlsx typos).
    """
    namespace, path = biome_id.split(":", 1)
    base = DATAPACK_ROOT / namespace / "worldgen" / "biome"
    literal = base / f"{path}.json"
    if literal.exists():
        return literal
    if namespace == "terralith" and "/" not in path:
        cave = base / "cave" / f"{path}.json"
        if cave.exists():
            return cave
    return literal  # caller will raise on missing


def all_biome_files() -> list[Path]:
    """Every overworld biome JSON we own, across all source namespaces."""
    out: list[Path] = []
    for sub in ("minecraft/worldgen/biome", "terralith/worldgen/biome",
                "wythers/worldgen/biome"):
        d = DATAPACK_ROOT / sub
        if d.exists():
            out.extend(sorted(d.rglob("*.json")))
    return out


def normalize_biome_id(biome_id: str, on_disk_ids: set[str]) -> str:
    """Reconcile a biome ID from the xlsx against on-disk biome IDs.

    The xlsx is inconsistent about Terralith's `cave/` subfolder: some
    cave biomes are listed as `terralith:andesite_caves` but their JSON
    actually lives at `cave/andesite_caves.json` (real ID:
    `terralith:cave/andesite_caves`). If `biome_id` doesn't match any
    on-disk ID, try inserting `cave/` for terralith biomes.
    """
    if biome_id in on_disk_ids:
        return biome_id
    if biome_id.startswith("terralith:") and "/" not in biome_id.split(":", 1)[1]:
        candidate = biome_id.replace("terralith:", "terralith:cave/", 1)
        if candidate in on_disk_ids:
            return candidate
    return biome_id  # caller will detect the mismatch


def biome_id_from_path(p: Path) -> str:
    """Inverse of biome_id_to_path.

    The biome ID is the namespace plus the slash-joined path under
    `worldgen/biome/`, including any subfolders. Files in `cave/` keep
    the prefix - that's how the chunk generator addresses them.
    """
    rel = p.relative_to(DATAPACK_ROOT)
    parts = rel.parts
    namespace = parts[0]
    # parts[1]/parts[2] = "worldgen"/"biome"
    leaf = "/".join(parts[3:])[: -len(".json")]
    return f"{namespace}:{leaf}"


def load_endeavour_tag(tag_name: str) -> set[str]:
    """Read `endeavour:<tag_name>` from the tag JSONs and return biome IDs.

    Tags use the standard MC format: `{"replace": false, "values": [...]}`.
    """
    tag_path = ENDEAVOUR_TAG_DIR / f"{tag_name}.json"
    if not tag_path.exists():
        raise FileNotFoundError(f"unknown endeavour tag: {tag_name} ({tag_path})")
    data = json.loads(tag_path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for v in data.get("values", []):
        if isinstance(v, str):
            out.add(v)
        elif isinstance(v, dict) and "id" in v:
            out.add(v["id"])
    return out


# --- JSON formatting preservation -----------------------------------------

@dataclass
class JsonFormat:
    """Captured byte-level formatting of a JSON file we'll round-trip."""
    indent: int
    trailing_newline: bool
    key_order: list[str]


def detect_format(text: str) -> JsonFormat:
    """Inspect the raw text to recover indentation + trailing newline."""
    # Find first indented line to detect indent width.
    indent = 4
    for line in text.split("\n"):
        stripped = line.lstrip(" ")
        if stripped and stripped != line and stripped[0] not in (",", "}", "]"):
            indent = len(line) - len(stripped)
            break
    data = json.loads(text, object_pairs_hook=OrderedDict)
    return JsonFormat(
        indent=indent,
        trailing_newline=text.endswith("\n"),
        key_order=list(data.keys()),
    )


def write_json_preserving(path: Path, data: OrderedDict, fmt: JsonFormat) -> None:
    """Emit JSON with the original file's indent + trailing-newline behavior."""
    text = json.dumps(data, indent=fmt.indent, ensure_ascii=False)
    if fmt.trailing_newline and not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


# --- YAML helpers ----------------------------------------------------------

def yaml_load(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def _ordered_to_plain(obj):
    """Recursively convert OrderedDict -> dict for safe YAML dumping.

    Python 3.7+ preserves insertion order, so ordering survives.
    """
    if isinstance(obj, OrderedDict):
        return {k: _ordered_to_plain(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {k: _ordered_to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_ordered_to_plain(x) for x in obj]
    return obj


def yaml_dump(path: Path, data: dict, header: str = "") -> None:
    """Dump YAML with stable key ordering and an optional header comment."""
    text = yaml.safe_dump(
        _ordered_to_plain(data),
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=10000,
    )
    if header:
        text = header.rstrip() + "\n\n" + text
    path.write_text(text, encoding="utf-8")


# --- Resolution: tier_template + biome_overrides -> per-biome features ----

# YAML override keys (used in both tier_templates and biome_overrides)
OP_INHERIT = "@inherit"
OP_SET = "@set"
OP_ADD = "@add"
OP_REMOVE = "@remove"

ALL_OPS = {OP_INHERIT, OP_SET, OP_ADD, OP_REMOVE}


@dataclass
class Resolved:
    """Resolved feature list for one biome+step plus diagnostic info."""
    features: list[str]
    sources: list[str] = field(default_factory=list)  # for debugging


def _ensure_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return list(v)


def _resolve_template(
    tier: str,
    step: str,
    tier_templates: dict,
    seen: tuple[str, ...] = (),
) -> list[str]:
    """Recursively resolve a tier_templates entry honoring @inherit chains."""
    if tier in seen:
        chain = " -> ".join(seen + (tier,))
        raise ValueError(f"@inherit cycle in tier_templates: {chain}")
    block = (tier_templates.get(tier) or {}).get(step)
    if block is None:
        return []
    if isinstance(block, list):
        return list(block)
    if not isinstance(block, dict):
        raise ValueError(
            f"tier_templates.{tier}.{step}: expected list or dict with @* ops, "
            f"got {type(block).__name__}"
        )
    base: list[str] = []
    if OP_INHERIT in block:
        parent = block[OP_INHERIT]
        base = _resolve_template(parent, step, tier_templates, seen + (tier,))
    if OP_SET in block:
        base = _ensure_list(block[OP_SET])
    for f in _ensure_list(block.get(OP_ADD)):
        if f not in base:
            base.append(f)
    remove = set(_ensure_list(block.get(OP_REMOVE)))
    if remove:
        base = [f for f in base if f not in remove]
    return base


def _apply_op_block(base: list[str], block) -> list[str]:
    """Apply a single override block (list or @-op dict) to `base`."""
    if isinstance(block, list):
        # Bare list = full override (same as @set)
        return list(block)
    if not isinstance(block, dict):
        raise ValueError(
            f"override step must be list or dict, got {type(block).__name__}"
        )
    out = list(base)
    if OP_SET in block:
        out = _ensure_list(block[OP_SET])
    for f in _ensure_list(block.get(OP_ADD)):
        if f not in out:
            out.append(f)
    remove = set(_ensure_list(block.get(OP_REMOVE)))
    if remove:
        out = [f for f in out if f not in remove]
    return out


def _expand_override_keys(
    biome_overrides: dict,
) -> list[tuple[str, dict]]:
    """Yield (biome_id, step_block_dict) pairs.

    Tag keys (`#endeavour:foo`) are expanded by reading the tag JSONs.
    Tag overrides are applied BEFORE biome-specific overrides so that an
    explicit biome key can override a tag-applied default.
    """
    tag_entries: list[tuple[str, dict]] = []
    biome_entries: list[tuple[str, dict]] = []
    for key, block in biome_overrides.items():
        if not block:
            continue
        if key.startswith("#"):
            # `#namespace:tag` -> we only support endeavour: tags here
            ns, tag = key[1:].split(":", 1)
            if ns != "endeavour":
                raise ValueError(
                    f"unsupported tag namespace in override key {key!r}: "
                    f"only #endeavour:* tags are recognized"
                )
            for biome_id in sorted(load_endeavour_tag(tag)):
                tag_entries.append((biome_id, block))
        else:
            biome_entries.append((key, block))
    return tag_entries + biome_entries


def resolve_biomes(
    tier_map: dict[str, str],          # biome_id -> tier
    tier_templates: dict,
    biome_overrides: dict,
    existing_features: dict[str, list[list[str]]],
) -> dict[str, list[list[str]]]:
    """Compute the final features array for every biome.

    Returns biome_id -> array-of-step-arrays (in vanilla generation order).

    Resolution per (biome, step):
      1. Start with tier_templates[biome.tier][step] (resolved with @inherit).
      2. Apply tag-based overrides (#endeavour:foo) in YAML order.
      3. Apply biome-id-specific overrides.

    Per-step ordering policy:
      - For features that were already in the existing biome JSON, preserve
        their original order. The existing data is empirically known to
        load (cycles and all - vanilla 1.21.1's FeatureSorter is more
        permissive than its error message suggests, and Terralith ships
        biomes that disagree on e.g. fossil_upper vs monster_room_deep
        ordering at underground_structures).
      - New features added via YAML are appended at the end of the step
        in YAML-encounter order.

    Biomes whose existing JSON has fewer than 11 step arrays (e.g. the
    odd fractured_savanna which has 10) keep the same length on output.
    """
    expanded = _expand_override_keys(biome_overrides)

    out: dict[str, list[list[str]]] = {}
    for biome_id in tier_map:
        tier = tier_map[biome_id]
        per_step: dict[str, list[str]] = {}
        for step in GENERATION_STEPS:
            base = _resolve_template(tier, step, tier_templates) if tier else []
            per_step[step] = list(base)
        for ov_biome, block in expanded:
            if ov_biome != biome_id:
                continue
            for step, op_block in block.items():
                if step not in STEP_INDEX:
                    raise ValueError(
                        f"biome {biome_id!r}: unknown step {step!r}. "
                        f"Valid steps: {GENERATION_STEPS}"
                    )
                per_step[step] = _apply_op_block(per_step[step], op_block)

        existing = existing_features.get(biome_id, [])
        n_steps = min(len(existing) if existing else len(GENERATION_STEPS),
                      len(GENERATION_STEPS))
        arr: list[list[str]] = []
        for i in range(n_steps):
            step = GENERATION_STEPS[i]
            resolved = per_step.get(step, [])
            existing_step = existing[i] if i < len(existing) else []
            arr.append(_order_against_existing(resolved, existing_step))
        out[biome_id] = arr
    return out


def _order_against_existing(
    resolved: list[str],
    existing: list[str],
) -> list[str]:
    """Reorder `resolved` to match `existing` for shared features; append rest.

    Preserves the original biome JSON's per-step ordering for any feature
    that's still in the resolved set. Net-new features (in resolved but
    not existing) come at the end in the order they appear in `resolved`.
    """
    resolved_set = set(resolved)
    out: list[str] = [f for f in existing if f in resolved_set]
    seen = set(out)
    for f in resolved:
        if f not in seen:
            out.append(f)
            seen.add(f)
    return out
