"""Shared constants, paths, formatting helpers, and resolution algorithm.

Architecture (tag-only, post-2026-05-04 redesign):

- Source of truth for biome -> group membership: tag JSONs at
  data/endeavour/tags/worldgen/biome/*.json. A biome can be in any
  number of tags; there's no concept of a "primary" tier.

- Source of truth for tag -> ore lists (and other features): the
  `#endeavour:<tag>` keys in `biome_overrides.yaml`.

- Per-biome exceptions: `biome_overrides.yaml` keys that match a
  biome ID directly.

- Resolution per (biome, step):
      features = union over (every tag containing the biome) of
                 (that tag's biome_overrides entry, with @add/@remove/@set)
                 then biome-id-specific overrides apply on top.

- The xlsx is documentation. The tool never reads or writes it.

The previous tier_templates.yaml + xlsx Tier column architecture has
been retired. Tags subsume tiers: tier_1 / tier_2 / tier_4 are just
tags whose biome lists happen to be (by convention) mutually exclusive.
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


def all_biome_files() -> list[Path]:
    """Every overworld biome JSON we own, across all source namespaces."""
    out: list[Path] = []
    for sub in ("minecraft/worldgen/biome", "terralith/worldgen/biome",
                "wythers/worldgen/biome"):
        d = DATAPACK_ROOT / sub
        if d.exists():
            out.extend(sorted(d.rglob("*.json")))
    return out


def biome_id_from_path(p: Path) -> str:
    """Map an on-disk biome JSON path to its biome ID.

    The biome ID is `<namespace>:<path under worldgen/biome>` minus the
    `.json` suffix. Subfolders are part of the path: a file at
    `terralith/worldgen/biome/cave/deep_caves.json` has biome ID
    `terralith:cave/deep_caves`.
    """
    rel = p.relative_to(DATAPACK_ROOT)
    parts = rel.parts
    namespace = parts[0]
    leaf = "/".join(parts[3:])[: -len(".json")]
    return f"{namespace}:{leaf}"


def normalize_biome_id(biome_id: str, on_disk_ids: set[str]) -> str:
    """Reconcile a biome ID against on-disk biome IDs.

    Some legacy tag JSONs list Terralith cave biomes without the `cave/`
    prefix (e.g. `terralith:andesite_caves` while the file is actually at
    `cave/andesite_caves.json`). If `biome_id` doesn't match an on-disk
    ID, try inserting `cave/` for terralith biomes.
    """
    if biome_id in on_disk_ids:
        return biome_id
    if biome_id.startswith("terralith:") and "/" not in biome_id.split(":", 1)[1]:
        candidate = biome_id.replace("terralith:", "terralith:cave/", 1)
        if candidate in on_disk_ids:
            return candidate
    return biome_id  # caller will detect the mismatch


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


def load_all_endeavour_tags(on_disk_ids: set[str] | None = None
                            ) -> dict[str, set[str]]:
    """Read every endeavour tag JSON; return {tag_name: set_of_biome_ids}.

    Biome IDs are normalized against on_disk_ids if provided, so legacy
    tag entries with wrong cave/ paths get auto-corrected at read time.
    """
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
    """Inverse of {tag: {biomes}}: return {biome_id: [tag_name, ...]}.

    Tag names are sorted for deterministic resolution order.
    """
    out: dict[str, list[str]] = {}
    for tag, biomes in tags_by_name.items():
        for b in biomes:
            out.setdefault(b, []).append(tag)
    for biomes_tags in out.values():
        biomes_tags.sort()
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
    """Recursively convert OrderedDict -> dict for safe YAML dumping."""
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


# --- Resolution: biome_overrides + tag membership -> per-biome features ---

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


def _apply_op_block(base: list[str], block) -> list[str]:
    """Apply a single override block (list or @-op dict) to `base`."""
    if isinstance(block, list):
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


def resolve_biomes(
    tags_by_biome: dict[str, list[str]],
    biome_overrides: dict,
    existing_features: dict[str, list[list[str]]],
) -> dict[str, list[list[str]]]:
    """Compute the final features array for every biome.

    For each biome, resolution is:
      1. Start with empty feature list per step.
      2. For each tag the biome belongs to (sorted by tag name for
         determinism), apply that tag's biome_overrides entry if any.
      3. Apply the biome-id-specific override entry if any.

    The final per-step list is then ordered against the existing biome
    JSON's order: features that were already there keep their original
    position, and net-new features append at the end. This avoids
    creating cross-biome FeatureSorter ordering cycles where none
    existed before.

    Biomes whose existing JSON has fewer than 11 step arrays (e.g. the
    odd fractured_savanna which has 10) keep the same length on output.

    Args:
      tags_by_biome: biome_id -> list of tag names (without `#endeavour:`).
      biome_overrides: parsed biome_overrides.yaml.
      existing_features: biome_id -> current per-step features array.
        Used both to decide which biomes to emit and to preserve order.

    Returns:
      biome_id -> per-step features array.
    """
    out: dict[str, list[list[str]]] = {}

    for biome_id, existing in existing_features.items():
        per_step: dict[str, list[str]] = {s: [] for s in GENERATION_STEPS}

        # 1. tag overrides (sorted for determinism)
        for tag in sorted(tags_by_biome.get(biome_id, [])):
            tag_block = biome_overrides.get(f"#endeavour:{tag}")
            if not tag_block:
                continue
            for step, op_block in tag_block.items():
                if step not in STEP_INDEX:
                    raise ValueError(
                        f"#endeavour:{tag}: unknown step {step!r}. "
                        f"Valid: {GENERATION_STEPS}"
                    )
                per_step[step] = _apply_op_block(per_step[step], op_block)

        # 2. biome-id override
        biome_block = biome_overrides.get(biome_id)
        if biome_block:
            for step, op_block in biome_block.items():
                if step not in STEP_INDEX:
                    raise ValueError(
                        f"biome {biome_id!r}: unknown step {step!r}. "
                        f"Valid: {GENERATION_STEPS}"
                    )
                per_step[step] = _apply_op_block(per_step[step], op_block)

        n_steps = min(len(existing) if existing else len(GENERATION_STEPS),
                      len(GENERATION_STEPS))
        arr: list[list[str]] = []
        for i in range(n_steps):
            step = GENERATION_STEPS[i]
            existing_step = existing[i] if i < len(existing) else []
            arr.append(_order_against_existing(per_step.get(step, []),
                                                existing_step))
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
