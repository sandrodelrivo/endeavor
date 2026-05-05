"""Shared constants, paths, formatting helpers, and resolution algorithm.

Architecture (catalog-only, post-2026-05-04 redesign):

The tool is the SOLE source of truth for ore distribution. It does not
edit ore lists into biome JSONs; it neutralizes them and replaces them
with NeoForge biome_modifier files.

Inputs:
    config/ore_catalog.yaml      - explicit list of every placed_feature ID
                                   the tool treats as an ore. Anything not
                                   in this list is "terrain" and the tool
                                   never touches it.

    config/biome_overrides.yaml  - tag-keyed ore assignments. Only
                                   `#endeavour:<tag>` keys; biome-id keys
                                   are no longer supported.

    data/endeavour/tags/worldgen/biome/*.json
                                 - biome -> tag membership.

Outputs (rewritten on every apply):
    Biome JSONs                  - all catalog ore IDs stripped from each
                                   biome's features array. Other features
                                   are left in original positions.

    data/endeavour/neoforge/biome_modifier/<tag>__<step>.json
                                 - one NeoForge `add_features` modifier per
                                   (tag, step) combination, with the ore IDs
                                   listed in `features`. NeoForge applies
                                   these on top of biome JSONs at world load.

The xlsx is documentation only.
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
ENDEAVOUR_TAG_DIR = DATAPACK_ROOT / "endeavour" / "tags" / "worldgen" / "biome"
ENDEAVOUR_BIOME_MODIFIER_DIR = DATAPACK_ROOT / "endeavour" / "neoforge" / "biome_modifier"

ORE_CATALOG_PATH = CONFIG_DIR / "ore_catalog.yaml"
BIOME_OVERRIDES_PATH = CONFIG_DIR / "biome_overrides.yaml"

# Vanilla 1.21.1 generation step registry order.
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


def all_biome_files() -> list[Path]:
    out: list[Path] = []
    for sub in ("minecraft/worldgen/biome", "terralith/worldgen/biome",
                "wythers/worldgen/biome", "endeavour/worldgen/biome"):
        d = DATAPACK_ROOT / sub
        if d.exists():
            out.extend(sorted(d.rglob("*.json")))
    return out


def biome_id_from_path(p: Path) -> str:
    """`namespace:<rest of path under worldgen/biome, no .json>`"""
    rel = p.relative_to(DATAPACK_ROOT)
    parts = rel.parts
    namespace = parts[0]
    leaf = "/".join(parts[3:])[: -len(".json")]
    return f"{namespace}:{leaf}"


def normalize_biome_id(biome_id: str, on_disk_ids: set[str]) -> str:
    """Insert `cave/` prefix for terralith cave biomes if missing."""
    if biome_id in on_disk_ids:
        return biome_id
    if biome_id.startswith("terralith:") and "/" not in biome_id.split(":", 1)[1]:
        candidate = biome_id.replace("terralith:", "terralith:cave/", 1)
        if candidate in on_disk_ids:
            return candidate
    return biome_id


def load_all_endeavour_tags(on_disk_ids: set[str] | None = None
                            ) -> dict[str, set[str]]:
    """Read every endeavour tag JSON; return {tag_name: set_of_biome_ids}."""
    out: dict[str, set[str]] = {}
    for f in sorted(ENDEAVOUR_TAG_DIR.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        ids: set[str] = set()
        for v in data.get("values", []):
            if isinstance(v, str):
                bid = v
            elif isinstance(v, dict) and "id" in v:
                bid = v["id"]
            else:
                continue
            if on_disk_ids is not None:
                bid = normalize_biome_id(bid, on_disk_ids)
            ids.add(bid)
        out[f.stem] = ids
    return out


def biome_to_tags(tags_by_name: dict[str, set[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for tag, biomes in tags_by_name.items():
        for b in biomes:
            out.setdefault(b, []).append(tag)
    for biomes_tags in out.values():
        biomes_tags.sort()
    return out


# --- ore catalog ----------------------------------------------------------

def load_ore_catalog() -> set[str]:
    """Return the flat set of ore feature IDs from ore_catalog.yaml."""
    return set(load_ore_catalog_ordered())


def load_ore_catalog_ordered() -> list[str]:
    """Return the ore catalog as an ordered list, preserving YAML order.

    Used as the canonical order for emitting ores across tags. If two
    biome_modifiers add overlapping ores, both must use the same relative
    order to satisfy MC's FeatureSorter; sorting by catalog position
    guarantees consistency.
    """
    if not ORE_CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"missing {ORE_CATALOG_PATH}. Catalog is required."
        )
    with ORE_CATALOG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out: list[str] = []
    seen: set[str] = set()
    for category, items in data.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, str) and item not in seen:
                seen.add(item)
                out.append(item)
    return out


def load_ore_catalog_categorized() -> dict[str, list[str]]:
    """Return {category: [ore_id, ...]} preserving YAML structure.

    Used by the GUI to organize the picker by mod.
    """
    if not ORE_CATALOG_PATH.exists():
        raise FileNotFoundError(f"missing {ORE_CATALOG_PATH}")
    with ORE_CATALOG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out: dict[str, list[str]] = {}
    for category, items in data.items():
        if isinstance(items, list):
            out[category] = [x for x in items if isinstance(x, str)]
    return out


# --- JSON formatting preservation -----------------------------------------

@dataclass
class JsonFormat:
    indent: int
    trailing_newline: bool
    key_order: list[str]


def detect_format(text: str) -> JsonFormat:
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
    if isinstance(obj, OrderedDict):
        return {k: _ordered_to_plain(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {k: _ordered_to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_ordered_to_plain(x) for x in obj]
    return obj


def yaml_dump(path: Path, data: dict, header: str = "") -> None:
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


# --- Resolution: tags + ore catalog -> per-tag biome_modifier outputs -----

OP_SET = "@set"
OP_ADD = "@add"
OP_REMOVE = "@remove"
ALL_OPS = {OP_SET, OP_ADD, OP_REMOVE}


def _ensure_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return list(v)


def extract_features(block) -> list[str]:
    """Return the resolved feature list from a step block.

    A step block is either a bare list (= @set) or a dict with @-prefixed
    ops. For tag entries, the typical shape is `{@add: [...]}`.
    """
    if isinstance(block, list):
        return list(block)
    if not isinstance(block, dict):
        return []
    out: list[str] = []
    if OP_SET in block:
        out = _ensure_list(block[OP_SET])
    for f in _ensure_list(block.get(OP_ADD)):
        if f not in out:
            out.append(f)
    remove = set(_ensure_list(block.get(OP_REMOVE)))
    if remove:
        out = [f for f in out if f not in remove]
    return out


def strip_catalog_ores(features: list[list[str]],
                       catalog: set[str]) -> list[list[str]]:
    """Remove any catalog ore from every step of the features array.

    Returns a new array; preserves step count and non-ore ordering.
    """
    return [[f for f in step if f not in catalog] for step in features]


def biome_modifier_files(
    biome_overrides: dict,
    catalog: set[str],
    catalog_order: list[str],
    tags_by_biome: dict[str, list[str]],
) -> dict[str, dict]:
    """Resolve to per-biome ore sets, then group biomes by equivalence.

    Why not one biome_modifier per (tag, step)?

    NeoForge `add_features` modifiers don't dedupe and don't enforce
    cross-biome ordering. If a biome is in multiple tags, it receives
    each tag's modifier in alphabetical ResourceLocation order, and
    the relative position of any given ore depends on which tag
    provided it. Different biomes have different tag combinations -
    so a single ore can land at different relative positions across
    biomes, creating MC `FeatureSorter` cycles even when no biome
    has a literal duplicate.

    The fix: ignore tag boundaries at apply time. For each biome,
    compute the union of ore lists from every tag it belongs to,
    sort by catalog position so cross-biome ordering is identical,
    then group biomes by their resulting ore-tuple. Each unique
    (step, ordered-ore-tuple) gets one modifier targeting all
    biomes that share that ore set.

    Effects:
      - Each biome matches exactly one modifier per step. No double
        injection regardless of how many tags it's in.
      - Every biome's ore list is in canonical catalog order. No
        cross-biome ordering disagreement.
      - Same ore can appear in multiple input tags freely; the tool
        merges them automatically.

    Returns {filename: json_content}. Filenames use a deterministic
    hash to remain stable across runs (no churn from set ordering).
    """
    import hashlib

    catalog_index = {ore: i for i, ore in enumerate(catalog_order)}

    # 1. Per (biome, step), compute the union of catalog ores from
    # every tag the biome belongs to.
    per_biome_step: dict[str, dict[str, list[str]]] = {}
    for biome_id, tags in tags_by_biome.items():
        per_step: dict[str, set[str]] = {}
        for tag in tags:
            tag_block = biome_overrides.get(f"#endeavour:{tag}")
            if not isinstance(tag_block, dict):
                continue
            for step, op_block in tag_block.items():
                if step not in STEP_INDEX:
                    raise ValueError(
                        f"#endeavour:{tag}: unknown step {step!r}. "
                        f"Valid: {GENERATION_STEPS}"
                    )
                for f in extract_features(op_block):
                    if f in catalog:
                        per_step.setdefault(step, set()).add(f)
        # Sort each step's ores by catalog position
        ordered: dict[str, list[str]] = {}
        for step, ore_set in per_step.items():
            ordered[step] = sorted(
                ore_set, key=lambda f: catalog_index.get(f, 1 << 30)
            )
        if ordered:
            per_biome_step[biome_id] = ordered

    # 2. Group biomes by (step, ordered_ore_tuple).
    groups: dict[tuple[str, tuple[str, ...]], list[str]] = {}
    for biome_id, per_step in per_biome_step.items():
        for step, ores in per_step.items():
            key = (step, tuple(ores))
            groups.setdefault(key, []).append(biome_id)

    # 3. Emit one modifier per group.
    out: dict[str, dict] = {}
    for (step, ore_tuple), biomes in sorted(groups.items()):
        # Hash the ore tuple for stable, content-derived filenames.
        digest = hashlib.sha1(
            "|".join(ore_tuple).encode("utf-8")
        ).hexdigest()[:8]
        filename = f"{step}__{digest}.json"
        biomes_field = (sorted(biomes) if len(biomes) > 1
                        else sorted(biomes)[0])
        features_field = (list(ore_tuple) if len(ore_tuple) > 1
                          else ore_tuple[0])
        out[filename] = {
            "type": "neoforge:add_features",
            "biomes": biomes_field,
            "features": features_field,
            "step": step,
        }
    return out
