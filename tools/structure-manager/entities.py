"""Entity extractor: pulls mob IDs out of NBT structure files and jigsaw pools."""

from __future__ import annotations

import gzip
import io
import zipfile
from collections import defaultdict
from typing import Any, Optional

import nbtlib
from nbtlib import File as NbtFile

from scanner import DATAPACK_DIR, Indices, NbtRef, StructureEntry, read_nbt_bytes


# Block names that contain mob spawners
_SPAWNER_BLOCKS = {
    "minecraft:spawner",
    "minecraft:mob_spawner",
}
_TRIAL_SPAWNER_BLOCKS = {
    "minecraft:trial_spawner",
}

# Entities that flag a "villager warning" for the UI
VILLAGER_IDS = frozenset(
    {
        "minecraft:villager",
        "minecraft:wandering_trader",
        "minecraft:zombie_villager",
    }
)

# Pool ID substrings that indicate a structure generates villagers procedurally.
# Villages don't bake villager entities into NBT - the engine spawns them at
# worldgen time - so we can't detect them by scanning NBT entities alone.
_VILLAGE_POOL_HINTS = frozenset({"village/", "village_", "/village"})

# Structure resource ID substrings that imply villager generation even without
# matching pools.
_VILLAGE_ID_HINTS = frozenset(
    {
        ":village_",
        ":village/",
        "/village_",
        "/village/",
        "classic_village",
        "remnant_village",
    }
)


def _structure_implies_villagers(entry: StructureEntry) -> bool:
    """Return True if the structure is known to procedurally spawn villagers."""
    rid = entry.resource_id
    if any(hint in rid for hint in _VILLAGE_ID_HINTS):
        return True
    start_pool = entry.structure_data.get("start_pool", "")
    if start_pool and any(hint in start_pool for hint in _VILLAGE_POOL_HINTS):
        return True
    return False


# ---------------------------------------------------------------------------
# NBT parsing helpers
# ---------------------------------------------------------------------------

def _load_nbt(raw: bytes) -> Optional[nbtlib.Compound]:
    """Parse raw bytes as NBT, handling both gzip and uncompressed."""
    if raw[:2] == b'\x1f\x8b':
        try:
            raw = gzip.decompress(raw)
        except Exception:
            return None
    try:
        return NbtFile.from_fileobj(io.BytesIO(raw), byteorder="big")
    except Exception:
        return None


def _get_str(tag: Any) -> str:
    return str(tag).strip('"')


def _extract_from_nbt(raw: bytes) -> set[str]:
    """Return all entity IDs found in a structure NBT file."""
    nbt = _load_nbt(raw)
    if nbt is None:
        return set()

    found: set[str] = set()

    # 1. Direct entities list
    entities_tag = nbt.get("entities")
    if entities_tag:
        for entity in entities_tag:
            try:
                nbt_sub = entity.get("nbt") or entity.get("Nbt")
                if nbt_sub:
                    eid = nbt_sub.get("id") or nbt_sub.get("Id")
                    if eid:
                        found.add(_get_str(eid))
            except Exception:
                pass

    # 2. Blocks: spawners and trial spawners
    palette = nbt.get("palette", [])
    palette_names: list[str] = []
    for p in palette:
        try:
            palette_names.append(_get_str(p["Name"]))
        except Exception:
            palette_names.append("")

    for block in nbt.get("blocks", []):
        try:
            state_idx = int(block.get("state", 0))
            if state_idx >= len(palette_names):
                continue
            block_name = palette_names[state_idx]
            block_nbt = block.get("nbt")
            if not block_nbt:
                continue

            if block_name in _SPAWNER_BLOCKS:
                spawn_data = block_nbt.get("SpawnData")
                if spawn_data:
                    entity_sub = spawn_data.get("entity")
                    if entity_sub:
                        eid = entity_sub.get("id")
                        if eid:
                            found.add(_get_str(eid))
                potentials = block_nbt.get("SpawnPotentials")
                if potentials:
                    for pot in potentials:
                        data = pot.get("data") or pot.get("Entity")
                        if data:
                            eid = data.get("id") or data.get("Id")
                            if eid:
                                found.add(_get_str(eid))

            elif block_name in _TRIAL_SPAWNER_BLOCKS:
                for config_key in ("normal_config", "ominous_config"):
                    cfg = block_nbt.get(config_key)
                    if cfg:
                        potentials = cfg.get("spawn_potentials")
                        if potentials:
                            for pot in potentials:
                                data = pot.get("data")
                                if data:
                                    entity_sub = data.get("entity")
                                    if entity_sub:
                                        eid = entity_sub.get("id")
                                        if eid:
                                            found.add(_get_str(eid))

        except Exception:
            pass

    return found


def _extract_jigsaw_sub_pools(raw: bytes) -> list[str]:
    """
    Return the pool IDs referenced by minecraft:jigsaw blocks inside this
    NBT piece.  These point to sub-structures that won't appear in the
    top-level template pool JSON files.
    """
    nbt = _load_nbt(raw)
    if not nbt:
        return []

    palette = nbt.get("palette", [])
    jigsaw_states = {
        i for i, p in enumerate(palette)
        if _get_str(p.get("Name", "")) == "minecraft:jigsaw"
    }
    if not jigsaw_states:
        return []

    pools: list[str] = []
    seen: set[str] = set()
    for block in nbt.get("blocks", []):
        try:
            if int(block.get("state", 0)) not in jigsaw_states:
                continue
            bnbt = block.get("nbt") or {}
            pool_val = bnbt.get("pool")
            if pool_val:
                pool_str = _get_str(pool_val)
                if pool_str and pool_str not in ("minecraft:empty", "") and pool_str not in seen:
                    seen.add(pool_str)
                    pools.append(pool_str)
        except Exception:
            pass
    return pools


def _pieces_from_pool(pool_id: str, idx: Indices, visited: set[str]) -> list[str]:
    """Return NBT piece IDs directly listed in a pool (no recursion, no I/O)."""
    pool = idx.pools.get(pool_id)
    if not pool:
        return []
    pieces: list[str] = []

    def _proc(el: dict) -> None:
        el_type = el.get("element_type", "")
        if "single_pool_element" in el_type or "legacy_single_pool_element" in el_type:
            loc = el.get("location") or el.get("template")
            if loc and isinstance(loc, str) and loc not in visited:
                pieces.append(loc)
        elif "list_pool_element" in el_type:
            for child in el.get("elements", []):
                _proc(child)

    for entry in pool.get("elements", []):
        _proc(entry.get("element") or entry)
    return pieces


# ---------------------------------------------------------------------------
# Sort helper
# ---------------------------------------------------------------------------

def _sort_entities(found: set[str]) -> list[str]:
    def sort_key(eid: str) -> tuple[int, str]:
        return (0 if eid in VILLAGER_IDS else 1, eid)
    return sorted(found, key=sort_key)


# ---------------------------------------------------------------------------
# Public resolve API
# ---------------------------------------------------------------------------

def resolve_entities(entry: StructureEntry, idx: Indices) -> list[str]:
    """Return sorted unique entity IDs reachable from this structure."""
    found: set[str] = set()
    if _structure_implies_villagers(entry):
        found.add("minecraft:villager")
    for nbt_id in entry.nbt_pieces:
        ref = idx.nbt.get(nbt_id)
        if ref is None:
            continue
        try:
            raw = read_nbt_bytes(ref)
            found |= _extract_from_nbt(raw)
        except Exception:
            pass
    return _sort_entities(found)


def resolve_entities_all(idx: Indices, _nbt_cache: dict, progress: dict | None = None) -> None:
    """
    Resolve entities for every structure, following jigsaw connectors
    recursively through NBT pieces to find sub-structure entities.

    Mutates entry.entities in place.  Designed to be called from a
    background thread.
    """
    # -------------------------------------------------------------------
    # Phase 1: BFS over jigsaw graph
    #   _piece_entities:   piece_id -> set[entity_id]
    #   _piece_sub_pools:  piece_id -> list[pool_id]  (from jigsaw blocks)
    # We process pieces in waves; each wave expands via jigsaw sub-pools.
    # -------------------------------------------------------------------

    _piece_entities: dict[str, set[str]] = {}
    _piece_sub_pools: dict[str, list[str]] = {}

    visited_pieces: set[str] = set()
    visited_pools: set[str] = set()

    # Seed: all pieces referenced directly by any structure's piece list
    for entry in idx.structures.values():
        for pid in entry.nbt_pieces:
            visited_pieces.add(pid)

    work_set: set[str] = set(visited_pieces)

    for _round in range(6):           # max 6 levels deep
        if not work_set:
            break

        # Batch-read by JAR to minimise ZIP opens
        jar_to_pieces: dict = defaultdict(list)
        for pid in work_set:
            ref = idx.nbt.get(pid)
            if ref is not None:
                jar_to_pieces[ref.jar].append(pid)

        for jar_path, piece_ids in jar_to_pieces.items():
            if jar_path is None:
                # Datapack files - read directly from disk
                for pid in piece_ids:
                    ref = idx.nbt[pid]
                    try:
                        raw = (DATAPACK_DIR / ref.internal).read_bytes()
                        if len(raw) > 8_000_000:
                            print(f"  Skipping oversized NBT piece ({len(raw)//1024}KB): {pid}")
                            _piece_entities[pid] = set()
                            _piece_sub_pools[pid] = []
                        else:
                            _piece_entities[pid] = _extract_from_nbt(raw)
                            _piece_sub_pools[pid] = _extract_jigsaw_sub_pools(raw)
                    except Exception:
                        _piece_entities[pid] = set()
                        _piece_sub_pools[pid] = []
                    if progress is not None:
                        progress["pieces_done"] = progress.get("pieces_done", 0) + 1
            else:
                try:
                    with zipfile.ZipFile(jar_path, "r") as z:
                        for pid in piece_ids:
                            ref = idx.nbt[pid]
                            try:
                                info = z.getinfo(ref.internal)
                                if info.file_size > 8_000_000:
                                    print(f"  Skipping oversized NBT piece ({info.file_size//1024}KB): {pid}")
                                    _piece_entities[pid] = set()
                                    _piece_sub_pools[pid] = []
                                else:
                                    raw = z.read(ref.internal)
                                    _piece_entities[pid] = _extract_from_nbt(raw)
                                    _piece_sub_pools[pid] = _extract_jigsaw_sub_pools(raw)
                            except Exception:
                                _piece_entities[pid] = set()
                                _piece_sub_pools[pid] = []
                            if progress is not None:
                                progress["pieces_done"] = progress.get("pieces_done", 0) + 1
                except Exception:
                    for pid in piece_ids:
                        _piece_entities.setdefault(pid, set())
                        _piece_sub_pools.setdefault(pid, [])
                        if progress is not None:
                            progress["pieces_done"] = progress.get("pieces_done", 0) + 1

        # Expand: find new pieces reachable via jigsaw sub-pools in this wave
        next_work: set[str] = set()
        for pid in work_set:
            for pool_id in _piece_sub_pools.get(pid, []):
                if pool_id in visited_pools:
                    continue
                visited_pools.add(pool_id)
                for new_pid in _pieces_from_pool(pool_id, idx, visited_pieces):
                    if new_pid not in visited_pieces:
                        visited_pieces.add(new_pid)
                        next_work.add(new_pid)

        work_set = next_work

    # -------------------------------------------------------------------
    # Phase 2: Assign entities + full piece list to each structure
    # -------------------------------------------------------------------
    all_entries = list(idx.structures.values())
    total = len(all_entries)
    if progress is not None:
        progress["phase"] = "structures"
        progress["total"] = total
        progress["done"] = 0

    for i, entry in enumerate(all_entries):
        found: set[str] = set()
        if _structure_implies_villagers(entry):
            found.add("minecraft:villager")

        s_visited_pieces: set[str] = set(entry.nbt_pieces)
        s_visited_pools: set[str] = set()
        s_queue: list[str] = list(entry.nbt_pieces)

        while s_queue:
            pid = s_queue.pop()
            found |= _piece_entities.get(pid, set())
            for pool_id in _piece_sub_pools.get(pid, []):
                if pool_id in s_visited_pools:
                    continue
                s_visited_pools.add(pool_id)
                for new_pid in _pieces_from_pool(pool_id, idx, s_visited_pieces):
                    if new_pid not in s_visited_pieces:
                        s_visited_pieces.add(new_pid)
                        s_queue.append(new_pid)

        entry.entities = _sort_entities(found)
        # All pieces reachable from this structure (start pool + sub-pools via jigsaw blocks)
        entry.all_nbt_pieces = sorted(s_visited_pieces)

        if progress is not None:
            progress["done"] = i + 1


# ---------------------------------------------------------------------------
# Render data
# ---------------------------------------------------------------------------

def get_render_data(raw: bytes) -> dict:
    """Convert an NBT structure file into JSON-serialisable block data for the viewer."""
    nbt = _load_nbt(raw)
    if nbt is None:
        return {"size": [0, 0, 0], "blocks": [], "error": "Failed to parse NBT"}

    size_tag = nbt.get("size", [])
    try:
        size = [int(size_tag[0]), int(size_tag[1]), int(size_tag[2])]
    except Exception:
        size = [0, 0, 0]

    palette = nbt.get("palette", [])
    palette_names: list[str] = []
    for p in palette:
        try:
            palette_names.append(_get_str(p["Name"]))
        except Exception:
            palette_names.append("minecraft:air")

    air_variants = {"minecraft:air", "minecraft:void_air", "minecraft:cave_air", "minecraft:barrier"}

    blocks: list[dict] = []
    for block in nbt.get("blocks", []):
        try:
            state_idx = int(block.get("state", 0))
            if state_idx >= len(palette_names):
                continue
            name = palette_names[state_idx]
            if name in air_variants:
                continue
            pos_tag = block["pos"]
            blocks.append({
                "pos": [int(pos_tag[0]), int(pos_tag[1]), int(pos_tag[2])],
                "type": name,
            })
        except Exception:
            pass

    return {"size": size, "blocks": blocks}
