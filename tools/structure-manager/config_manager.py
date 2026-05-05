"""
Config management: reads/writes structurify.json for mod structures, and
creates/removes biome-override files in the datapack for datapack structures.

Structurify v2 format (single file):
    config/structurify.json
    {
      "structures": [
        {"name": "namespace:path", "is_disabled": true, ...},
        ...
      ],
      ...
    }

Datapack disable strategy:
  - Creates  data/<ns>/worldgen/structure/<path>.json in our datapack
    with biomes overridden to an empty tag.
  - Backs up the original biomes list in
    tools/structure-manager/datapack_overrides.json
    so we can restore on re-enable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STRUCTURIFY_CONFIG = Path(
    r"C:\Users\jonat\AppData\Roaming\ModrinthApp\profiles\Aetherian Skies\config\structurify.json"
)
DATAPACK_DIR = Path(__file__).parent.parent.parent / "datapack-worldgen" / "zzz_endeavour_worldgen"
OVERRIDES_FILE = Path(__file__).parent / "datapack_overrides.json"

# Biome tag we create (empty list → structure never spawns)
_DISABLED_TAG = "zzz_endeavour_worldgen:structure_manager/disabled"
_DISABLED_TAG_PATH = (
    DATAPACK_DIR
    / "data"
    / "zzz_endeavour_worldgen"
    / "tags"
    / "worldgen"
    / "biome"
    / "structure_manager"
    / "disabled.json"
)


# ---------------------------------------------------------------------------
# Structurify helpers
# ---------------------------------------------------------------------------

def _read_structurify() -> dict:
    try:
        return json.loads(STRUCTURIFY_CONFIG.read_bytes())
    except Exception:
        return {}


def _write_structurify(cfg: dict) -> None:
    cfg_copy = dict(cfg)
    STRUCTURIFY_CONFIG.write_text(json.dumps(cfg_copy, indent=2), encoding="utf-8")


def structurify_is_enabled(resource_id: str) -> bool:
    cfg = _read_structurify()
    for entry in cfg.get("structures", []):
        if entry.get("name") == resource_id:
            return not entry.get("is_disabled", False)
    return True


def structurify_set_enabled(resource_id: str, enabled: bool) -> None:
    cfg = _read_structurify()
    structures: list[dict] = cfg.setdefault("structures", [])

    for entry in structures:
        if entry.get("name") == resource_id:
            if enabled:
                entry["is_disabled"] = False
            else:
                entry["is_disabled"] = True
            _write_structurify(cfg)
            return

    if not enabled:
        structures.append({"name": resource_id, "is_disabled": True})
        _write_structurify(cfg)


# ---------------------------------------------------------------------------
# Datapack override helpers
# ---------------------------------------------------------------------------

def _read_overrides() -> dict[str, Any]:
    try:
        return json.loads(OVERRIDES_FILE.read_bytes())
    except Exception:
        return {}


def _write_overrides(data: dict) -> None:
    OVERRIDES_FILE.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _ensure_disabled_tag() -> None:
    """Create the empty biome tag that disables structures."""
    _DISABLED_TAG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _DISABLED_TAG_PATH.exists():
        _DISABLED_TAG_PATH.write_text(json.dumps({"values": []}), encoding="utf-8")


def _structure_file_in_datapack(namespace: str, path: str) -> Path:
    return DATAPACK_DIR / "data" / namespace / "worldgen" / "structure" / f"{path}.json"


def datapack_is_enabled(namespace: str, path: str) -> bool:
    overrides = _read_overrides()
    rid = f"{namespace}:{path}"
    return rid not in overrides.get("disabled", [])


def datapack_set_enabled(namespace: str, path: str, enabled: bool, original_structure_data: dict) -> None:
    overrides = _read_overrides()
    disabled: list[str] = overrides.setdefault("disabled", [])
    backups: dict = overrides.setdefault("backups", {})

    rid = f"{namespace}:{path}"
    struct_file = _structure_file_in_datapack(namespace, path)

    if not enabled:
        # Back up original biomes if we haven't already
        if rid not in backups:
            backups[rid] = original_structure_data.get("biomes")

        if rid not in disabled:
            disabled.append(rid)

        # Write the override into the datapack
        _ensure_disabled_tag()
        override = dict(original_structure_data)
        override["biomes"] = f"#{_DISABLED_TAG}"
        struct_file.parent.mkdir(parents=True, exist_ok=True)
        struct_file.write_text(json.dumps(override, indent=2), encoding="utf-8")

    else:
        # Re-enable: restore original biomes
        if rid in disabled:
            disabled.remove(rid)

        original_biomes = backups.pop(rid, None)
        if struct_file.exists():
            if original_biomes is not None:
                restored = dict(original_structure_data)
                restored["biomes"] = original_biomes
                struct_file.write_text(json.dumps(restored, indent=2), encoding="utf-8")
            else:
                # No backup; just remove the override so the mod/vanilla version takes over.
                # Only delete if WE created it (check the disabled tag fingerprint).
                try:
                    current = json.loads(struct_file.read_bytes())
                    if current.get("biomes") == f"#{_DISABLED_TAG}":
                        struct_file.unlink()
                except Exception:
                    pass

    _write_overrides(overrides)


# ---------------------------------------------------------------------------
# Unified API
# ---------------------------------------------------------------------------

def is_enabled(resource_id: str, source_type: str) -> bool:
    ns, _, path = resource_id.partition(":")
    if source_type == "datapack":
        return datapack_is_enabled(ns, path)
    return structurify_is_enabled(resource_id)


def set_enabled(
    resource_id: str,
    source_type: str,
    enabled: bool,
    original_structure_data: dict,
) -> None:
    ns, _, path = resource_id.partition(":")
    if source_type == "datapack":
        datapack_set_enabled(ns, path, enabled, original_structure_data)
    else:
        structurify_set_enabled(resource_id, enabled)
