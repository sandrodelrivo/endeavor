"""
Simulates one Minecraft jigsaw structure generation pass and returns all block
data in world-space coordinates for the 3-D viewer.

Key correction vs. naive implementations: jigsaw block `orientation` is a block
state property stored in the palette entry under ["Properties"]["orientation"],
NOT in the tile entity NBT compound.
"""
from __future__ import annotations

import random
from typing import Optional

import nbtlib

from entities import _get_str, _load_nbt
from scanner import Indices, read_nbt_bytes

# ---------------------------------------------------------------------------
# Direction / orientation helpers
# ---------------------------------------------------------------------------

# orientation property value → which direction the connector faces outward
_ORIENTATION_TO_DIR: dict[str, str] = {
    "north_up": "north", "south_up": "south",
    "east_up":  "east",  "west_up":  "west",
    "up_east":  "up",    "up_north": "up",  "up_south": "up",  "up_west": "up",
    "down_east":"down",  "down_north":"down","down_south":"down","down_west":"down",
}

_OPPOSITE: dict[str, str] = {
    "north": "south", "south": "north",
    "east":  "west",  "west":  "east",
    "up":    "down",  "down":  "up",
}

_DIR_VEC: dict[str, list[int]] = {
    "north": [0, 0, -1], "south": [0, 0, 1],
    "east":  [1, 0, 0],  "west":  [-1, 0, 0],
    "up":    [0, 1, 0],  "down":  [0, -1, 0],
}

# How a direction transforms under one 90° CW Y-axis rotation
_CW90_DIR: dict[str, str] = {
    "north": "east", "east": "south", "south": "west", "west": "north",
    "up": "up", "down": "down",
}


def _rotate_dir(direction: str, cw90_steps: int) -> str:
    d = direction
    for _ in range(cw90_steps % 4):
        d = _CW90_DIR.get(d, d)
    return d


def _rotations_to_align(natural: str, required: str) -> int:
    """Number of 90° CW Y-axis rotations to turn `natural` direction into `required`."""
    if natural in ("up", "down") or required in ("up", "down"):
        return 0
    for steps in range(4):
        if _rotate_dir(natural, steps) == required:
            return steps
    return 0


# ---------------------------------------------------------------------------
# Block position rotation (around Y axis, keeps coords non-negative)
# ---------------------------------------------------------------------------

def _rotate_pos(
    pos: list[int], cw90_steps: int, size: list[int]
) -> tuple[list[int], list[int]]:
    """
    Rotate local block position `pos` by `cw90_steps` 90° CW turns around Y.
    `size` is the piece's [sx, sy, sz] before rotation.
    Returns (rotated_pos, rotated_size).
    """
    x, y, z = pos
    sx, sy, sz = size
    for _ in range(cw90_steps % 4):
        x, z = sz - 1 - z, x
        sx, sz = sz, sx
    return [x, y, z], [sx, sy, sz]


# ---------------------------------------------------------------------------
# Palette helpers: extract per-state orientation and block name
# ---------------------------------------------------------------------------

def _build_palette_info(
    palette: list,
) -> tuple[list[str], dict[int, str]]:
    """
    Returns:
      palette_names  — list[str], block name for each state index
      state_orient   — dict[int → orientation_string] for jigsaw states only
    """
    names: list[str] = []
    orients: dict[int, str] = {}
    for i, entry in enumerate(palette):
        try:
            name = _get_str(entry["Name"])
        except Exception:
            name = "minecraft:air"
        names.append(name)
        if name == "minecraft:jigsaw":
            try:
                props = entry.get("Properties") or {}
                orient = _get_str(props.get("orientation", "north_up"))
                orients[i] = orient
            except Exception:
                orients[i] = "north_up"
    return names, orients


# ---------------------------------------------------------------------------
# Jigsaw block extraction (reads orientation from palette, not from nbt)
# ---------------------------------------------------------------------------

def _extract_jigsaw_blocks(nbt: nbtlib.Compound) -> list[dict]:
    """
    Return a list of jigsaw connector descriptors.

    Each descriptor:
      pos         — [x, y, z] local position
      direction   — outward facing direction string (from block state)
      name        — this block's name (what child looks for as 'target')
      target      — which name to look for in the child piece
      pool        — template pool to draw the child from
      joint       — "rollable" | "aligned"
    """
    palette = nbt.get("palette", [])
    _, state_orient = _build_palette_info(palette)
    if not state_orient:
        return []

    out: list[dict] = []
    for block in nbt.get("blocks", []):
        try:
            state_idx = int(block.get("state", 0))
            if state_idx not in state_orient:
                continue
            pos_tag = block["pos"]
            pos = [int(pos_tag[0]), int(pos_tag[1]), int(pos_tag[2])]
            bnbt = block.get("nbt") or {}
            pool = _get_str(bnbt.get("pool", ""))
            if not pool or pool == "minecraft:empty":
                continue
            orientation = state_orient[state_idx]
            out.append({
                "pos":       pos,
                "direction": _ORIENTATION_TO_DIR.get(orientation, "north"),
                "name":      _get_str(bnbt.get("name", "")),
                "target":    _get_str(bnbt.get("target", "")),
                "pool":      pool,
                "joint":     _get_str(bnbt.get("joint", "rollable")),
            })
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# All-jigsaw-block extraction (includes empty-pool input connectors)
# ---------------------------------------------------------------------------

def _extract_all_jigsaw_blocks(nbt: nbtlib.Compound) -> list[dict]:
    """
    Like _extract_jigsaw_blocks but includes blocks with pool='minecraft:empty'.
    Used for name-matching (finding the input connector a parent connects to).
    """
    palette = nbt.get("palette", [])
    _, state_orient = _build_palette_info(palette)
    if not state_orient:
        return []

    out: list[dict] = []
    for block in nbt.get("blocks", []):
        try:
            state_idx = int(block.get("state", 0))
            if state_idx not in state_orient:
                continue
            pos_tag = block["pos"]
            pos = [int(pos_tag[0]), int(pos_tag[1]), int(pos_tag[2])]
            bnbt = block.get("nbt") or {}
            orientation = state_orient[state_idx]
            out.append({
                "pos":       pos,
                "direction": _ORIENTATION_TO_DIR.get(orientation, "north"),
                "name":      _get_str(bnbt.get("name", "")),
                "target":    _get_str(bnbt.get("target", "")),
                "pool":      _get_str(bnbt.get("pool", "")),
                "joint":     _get_str(bnbt.get("joint", "rollable")),
            })
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# Pool helpers
# ---------------------------------------------------------------------------

def _all_pieces_from_pool(pool_id: str, idx: Indices) -> list[tuple[str, int]]:
    """Return [(piece_id, weight)] for every concrete NBT piece in the pool, in order."""
    pool = idx.pools.get(pool_id)
    if not pool:
        return []

    def _from_element(el: dict, weight: int) -> list[tuple[str, int]]:
        el_type = el.get("element_type", "")
        if "single_pool_element" in el_type or "legacy_single_pool_element" in el_type:
            loc = el.get("location") or el.get("template")
            if isinstance(loc, str) and loc in idx.nbt:
                return [(loc, weight)]
        elif "list_pool_element" in el_type:
            results: list[tuple[str, int]] = []
            for child in el.get("elements", []):
                results.extend(_from_element(child, weight))
            return results
        return []

    result: list[tuple[str, int]] = []
    for entry in pool.get("elements", []):
        try:
            weight = max(1, int(entry.get("weight", 1)))
        except (TypeError, ValueError):
            weight = 1
        el = entry.get("element") or entry
        result.extend(_from_element(el, weight))
    return result


def _load_piece_nbt(
    piece_id: str, idx: Indices, cache: dict
) -> Optional[nbtlib.Compound]:
    """Load and cache a piece's NBT compound. Returns None on any failure."""
    if piece_id in cache:
        return cache[piece_id]
    ref = idx.nbt.get(piece_id)
    if ref is None:
        cache[piece_id] = None
        return None
    try:
        raw = read_nbt_bytes(ref)
        nbt = _load_nbt(raw)
    except Exception:
        nbt = None
    cache[piece_id] = nbt
    return nbt


def _find_piece_with_connector(
    pool_id: str,
    target_name: str,
    idx: Indices,
    nbt_cache: dict,
    rng: random.Random,
) -> tuple[Optional[str], Optional[dict]]:
    """
    Pick a piece from the pool whose jigsaw `name` matches `target_name`,
    chosen by weighted random from all matching candidates.

    If no piece has a matching connector, falls back to weighted random
    across all loadable pieces in the pool (with matching_jb = None).

    Returns (piece_id, matching_jb) or (None, None) if the pool is empty.
    """
    pieces = _all_pieces_from_pool(pool_id, idx)
    if not pieces:
        return None, None

    # First pass: find all pieces with a matching connector name
    candidates: list[tuple[str, dict, int]] = []  # (piece_id, jb, weight)
    all_loadable: list[tuple[str, int]] = []        # (piece_id, weight)

    for piece_id, weight in pieces:
        nbt = _load_piece_nbt(piece_id, idx, nbt_cache)
        if nbt is None:
            continue
        all_loadable.append((piece_id, weight))
        # Use all jigsaw blocks (including empty-pool input connectors) for name matching
        for jb in _extract_all_jigsaw_blocks(nbt):
            if jb["name"] == target_name:
                candidates.append((piece_id, jb, weight))
                break  # one matching connector per piece is sufficient

    if candidates:
        chosen = rng.choices(candidates, weights=[c[2] for c in candidates])[0]
        return chosen[0], chosen[1]

    # No connector match — weighted random fallback to any piece
    if all_loadable:
        piece_id, _ = rng.choices(all_loadable, weights=[w for _, w in all_loadable])[0]
        return piece_id, None

    return None, None


# ---------------------------------------------------------------------------
# Simulation limits
# ---------------------------------------------------------------------------

MAX_PIECES = 48
MAX_BLOCKS = 80_000
AIR_BLOCKS = {"minecraft:air", "minecraft:void_air", "minecraft:cave_air", "minecraft:barrier"}


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------

def simulate_jigsaw(
    structure_id: str,
    idx: Indices,
    max_depth: int = 4,
    seed: Optional[int] = None,
) -> dict:
    """
    Simulate one jigsaw generation pass and return assembled block data.

    Returns:
      blocks        — list of {pos:[x,y,z], type:str} in world space
      size          — [sx, sy, sz] bounding box
      pieces_placed — how many NBT pieces were used
      capped        — True if MAX_PIECES or MAX_BLOCKS was hit
      seed          — the RNG seed used (pass back in to reproduce)
      error         — present (and str) if structure isn't jigsawable
    """
    entry = idx.structures.get(structure_id)
    if not entry:
        return {"error": f"Unknown structure: {structure_id}"}

    struct_type = entry.structure_data.get("type", "")
    if "jigsaw" not in struct_type:
        return {"error": "Not a jigsaw structure — use the single-piece viewer."}

    start_pool = entry.structure_data.get("start_pool")
    if not start_pool:
        return {"error": "No start_pool defined."}

    if seed is None:
        seed = random.getrandbits(32)
    rng = random.Random(seed)

    # NBT cache shared across the whole simulation to avoid redundant disk reads
    _nbt_cache: dict = {}

    start_pieces = _all_pieces_from_pool(start_pool, idx)
    if not start_pieces:
        return {"error": f"No concrete piece found in start pool: {start_pool}"}

    start_piece = rng.choices(start_pieces, weights=[w for _, w in start_pieces])[0][0]

    all_blocks: list[dict] = []
    pieces_placed = 0
    capped = False
    visited_piece_positions: set[tuple] = set()  # (piece_id, ox, oy, oz) — dedup

    def _place(piece_id: str, origin: list[int], rotation: int, depth: int) -> None:
        nonlocal pieces_placed, capped

        if capped or pieces_placed >= MAX_PIECES or len(all_blocks) >= MAX_BLOCKS:
            capped = True
            return

        # Deduplicate: same piece at same origin is a cycle
        key = (piece_id, origin[0], origin[1], origin[2])
        if key in visited_piece_positions:
            return
        visited_piece_positions.add(key)

        nbt = _load_piece_nbt(piece_id, idx, _nbt_cache)
        if nbt is None:
            return

        size_tag = nbt.get("size", [])
        try:
            base_size = [int(size_tag[0]), int(size_tag[1]), int(size_tag[2])]
        except Exception:
            base_size = [16, 16, 16]

        palette = nbt.get("palette", [])
        palette_names, _ = _build_palette_info(palette)

        pieces_placed += 1

        # Place blocks
        for block in nbt.get("blocks", []):
            if len(all_blocks) >= MAX_BLOCKS:
                capped = True
                break
            try:
                state_idx = int(block.get("state", 0))
                if state_idx >= len(palette_names):
                    continue
                name = palette_names[state_idx]
                if name in AIR_BLOCKS:
                    continue
                pos_tag = block["pos"]
                local_pos = [int(pos_tag[0]), int(pos_tag[1]), int(pos_tag[2])]
                rotated_pos, _ = _rotate_pos(local_pos, rotation, base_size)
                world_pos = [
                    origin[0] + rotated_pos[0],
                    origin[1] + rotated_pos[1],
                    origin[2] + rotated_pos[2],
                ]
                all_blocks.append({"pos": world_pos, "type": name})
            except Exception:
                pass

        if depth >= max_depth:
            return

        # Recurse into jigsaw connectors
        jb_list = _extract_jigsaw_blocks(nbt)
        for jb in jb_list:
            if capped or pieces_placed >= MAX_PIECES:
                capped = True
                break

            # Pick the pool piece whose jigsaw `name` matches our `target`
            child_id, matching_cjb = _find_piece_with_connector(
                jb["pool"], jb["target"], idx, _nbt_cache, rng
            )
            if not child_id:
                continue

            child_nbt = _load_piece_nbt(child_id, idx, _nbt_cache)
            if child_nbt is None:
                continue

            child_size_tag = child_nbt.get("size", [])
            try:
                child_base_size = [int(child_size_tag[0]), int(child_size_tag[1]), int(child_size_tag[2])]
            except Exception:
                child_base_size = [16, 16, 16]

            # If the targeted search found no name match, fall back to first connector.
            # Prefer INPUT connectors (empty pool) since they face toward the parent.
            if matching_cjb is None:
                all_child_jbs = _extract_all_jigsaw_blocks(child_nbt)
                input_jbs = [j for j in all_child_jbs
                             if not j.get("pool") or j["pool"] == "minecraft:empty"]
                matching_cjb = input_jbs[0] if input_jbs else (all_child_jbs[0] if all_child_jbs else None)

            # Parent connector direction in world space (after parent rotation)
            parent_world_dir = _rotate_dir(jb["direction"], rotation)
            required_child_dir = _OPPOSITE[parent_world_dir]

            # Determine child Y rotation to align its connector toward parent
            if matching_cjb is not None:
                child_rotation = _rotations_to_align(matching_cjb["direction"], required_child_dir)
            else:
                child_rotation = 0

            # Parent connector world position
            parent_rotated_conn, _ = _rotate_pos(jb["pos"], rotation, base_size)
            parent_world_conn = [
                origin[0] + parent_rotated_conn[0],
                origin[1] + parent_rotated_conn[1],
                origin[2] + parent_rotated_conn[2],
            ]
            dir_vec = _DIR_VEC[parent_world_dir]
            # Attachment point: one step from parent connector in its facing direction
            attach = [
                parent_world_conn[0] + dir_vec[0],
                parent_world_conn[1] + dir_vec[1],
                parent_world_conn[2] + dir_vec[2],
            ]

            if matching_cjb is not None:
                child_conn_rotated, _ = _rotate_pos(
                    matching_cjb["pos"], child_rotation, child_base_size
                )
                child_origin = [
                    attach[0] - child_conn_rotated[0],
                    attach[1] - child_conn_rotated[1],
                    attach[2] - child_conn_rotated[2],
                ]
            else:
                child_origin = attach

            _place(child_id, child_origin, child_rotation, depth + 1)

    _place(start_piece, [0, 0, 0], 0, 0)

    # Normalise to non-negative coords
    if all_blocks:
        min_x = min(b["pos"][0] for b in all_blocks)
        min_y = min(b["pos"][1] for b in all_blocks)
        min_z = min(b["pos"][2] for b in all_blocks)
        if min_x < 0 or min_y < 0 or min_z < 0:
            for b in all_blocks:
                b["pos"][0] -= min_x
                b["pos"][1] -= min_y
                b["pos"][2] -= min_z
        max_x = max(b["pos"][0] for b in all_blocks)
        max_y = max(b["pos"][1] for b in all_blocks)
        max_z = max(b["pos"][2] for b in all_blocks)
        size = [max_x + 1, max_y + 1, max_z + 1]
    else:
        size = [0, 0, 0]

    return {
        "blocks":        all_blocks,
        "size":          size,
        "pieces_placed": pieces_placed,
        "capped":        capped,
        "seed":          seed,
    }
