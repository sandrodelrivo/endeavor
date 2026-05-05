"""Structure Manager FastAPI backend."""

from __future__ import annotations

import mimetypes
import threading
from pathlib import Path
from typing import Optional

# Windows registry often maps .js -> text/plain, which breaks ES modules.
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import assets as asset_mgr
import config_manager
import entities as ent
from scanner import Indices, build_index, load_entity_cache, read_nbt_bytes, save_entity_cache

app = FastAPI(title="Structure Manager", docs_url=None, redoc_url=None)

FRONTEND_DIR = Path(__file__).parent / "frontend"

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_index: Optional[Indices] = None
_entities_ready = False
_nbt_entity_cache: dict = {}
_scan_progress: dict = {"phase": "idle", "done": 0, "total": 0, "pieces_done": 0}


def _get_index() -> Indices:
    if _index is None:
        raise HTTPException(503, "Index not ready yet")
    return _index


# ---------------------------------------------------------------------------
# Background entity-resolution thread
# ---------------------------------------------------------------------------

def _resolve_entities_background(idx: Indices) -> None:
    global _entities_ready, _scan_progress

    cache_hit, fingerprint = load_entity_cache(idx)
    if cache_hit:
        n = len(idx.structures)
        print(f"  Cache hit — loaded entity/piece data for {n} structures.")
        _scan_progress["done"] = n
        _scan_progress["total"] = n
        _entities_ready = True
        return

    print(f"  Resolving entities in background… ({len(idx.structures)} structures)")
    _scan_progress["phase"] = "pieces"
    _scan_progress["done"] = 0
    _scan_progress["total"] = len(idx.structures)
    _scan_progress["pieces_done"] = 0
    try:
        ent.resolve_entities_all(idx, _nbt_entity_cache, progress=_scan_progress)
        _entities_ready = True
        print(
            f"  Entity resolution complete.  "
            f"{sum(1 for e in idx.structures.values() if e.entities)} structures have entities."
        )
        save_entity_cache(idx, fingerprint)
    except Exception as exc:
        print(f"  Entity resolution failed: {exc}")
        _entities_ready = True  # unblock UI even on error


def _build_and_start_bg() -> Indices:
    global _entities_ready
    _entities_ready = False
    idx = build_index()
    t = threading.Thread(target=_resolve_entities_background, args=(idx,), daemon=True)
    t.start()
    return idx


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.post("/api/rescan")
def rescan() -> dict:
    global _index, _nbt_entity_cache, _entities_ready, _scan_progress
    _nbt_entity_cache = {}
    _entities_ready = False
    _scan_progress = {"done": 0, "total": 0}
    _index = _build_and_start_bg()
    return {"count": len(_index.structures), "entities_ready": _entities_ready}


@app.get("/api/stats")
def stats() -> dict:
    idx = _get_index()
    total = len(idx.structures)
    enabled = sum(
        1 for e in idx.structures.values()
        if config_manager.is_enabled(e.resource_id, e.source_type)
    )
    villager = sum(
        1 for e in idx.structures.values()
        if any(en in ent.VILLAGER_IDS for en in e.entities)
    )
    return {
        "total": total,
        "enabled": enabled,
        "disabled": total - enabled,
        "with_villager": villager,
        "nbt_files": len(idx.nbt),
        "entities_ready": _entities_ready,
        "scan_phase": _scan_progress["phase"],
        "scan_done": _scan_progress["done"],
        "scan_total": _scan_progress["total"],
        "scan_pieces_done": _scan_progress["pieces_done"],
    }


@app.get("/api/structures")
def list_structures(
    source: str = Query(default=""),
    search: str = Query(default=""),
    has_villager: Optional[bool] = Query(default=None),
    has_entity: str = Query(default=""),
) -> list[dict]:
    idx = _get_index()
    results = []
    entity_filter = has_entity.lower().strip()

    for entry in sorted(idx.structures.values(), key=lambda e: e.resource_id):
        if source and entry.source_type != source:
            continue
        if search and search.lower() not in entry.resource_id.lower():
            continue

        enabled = config_manager.is_enabled(entry.resource_id, entry.source_type)
        villager_flag = any(e in ent.VILLAGER_IDS for e in entry.entities)

        if has_villager is not None and villager_flag != has_villager:
            continue

        if entity_filter and not any(entity_filter in e.lower() for e in entry.entities):
            continue

        results.append({
            "id": entry.resource_id,
            "source_type": entry.source_type,
            "source_label": entry.source_label,
            "enabled": enabled,
            "entity_count": len(entry.entities) if _entities_ready else -1,
            "has_villager": villager_flag,
            "piece_count": len(entry.nbt_pieces),
        })

    return results


@app.get("/api/structure/details")
def structure_details(id: str = Query(...)) -> dict:
    idx = _get_index()
    entry = idx.structures.get(id)
    if entry is None:
        raise HTTPException(404, f"Unknown structure: {id}")

    # If background resolution hasn't reached this entry yet, compute it now
    if not _entities_ready and not entry.entities:
        entry.entities = ent.resolve_entities(entry, idx)

    enabled = config_manager.is_enabled(entry.resource_id, entry.source_type)

    return {
        "id": entry.resource_id,
        "namespace": entry.namespace,
        "path": entry.path,
        "source_type": entry.source_type,
        "source_label": entry.source_label,
        "enabled": enabled,
        "entities": entry.entities,
        "pieces": entry.nbt_pieces,
        "all_pieces": entry.all_nbt_pieces if _entities_ready else [],
        "structure_type": entry.structure_data.get("type", "unknown"),
        "entities_ready": _entities_ready,
    }


@app.get("/api/structure/render")
def structure_render(
    id: str = Query(...),
    piece: str = Query(...),
) -> dict:
    idx = _get_index()
    if id not in idx.structures:
        raise HTTPException(404, f"Unknown structure: {id}")

    ref = idx.nbt.get(piece)
    if ref is None:
        raise HTTPException(404, f"NBT piece not found: {piece}")

    try:
        raw = read_nbt_bytes(ref)
    except Exception as exc:
        raise HTTPException(500, f"Failed to read NBT: {exc}") from exc

    return ent.get_render_data(raw)


@app.get("/api/entities")
def list_entities() -> list[str]:
    idx = _get_index()
    found: set[str] = set()
    for entry in idx.structures.values():
        found.update(entry.entities)
    return sorted(found)


@app.get("/api/structure/jigsaw")
def structure_jigsaw(
    id: str = Query(...),
    depth: int = Query(default=4),
    seed: Optional[int] = Query(default=None),
) -> dict:
    idx = _get_index()
    if id not in idx.structures:
        raise HTTPException(404, f"Unknown structure: {id}")
    from jigsaw_sim import simulate_jigsaw
    result = simulate_jigsaw(id, idx, max_depth=min(depth, 20), seed=seed)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.post("/api/structure/set_enabled")
def set_enabled(id: str = Query(...), enabled: bool = Query(...)) -> dict:
    idx = _get_index()
    entry = idx.structures.get(id)
    if entry is None:
        raise HTTPException(404, f"Unknown structure: {id}")

    try:
        config_manager.set_enabled(id, entry.source_type, enabled, entry.structure_data)
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc

    return {"id": id, "enabled": enabled}


# ---------------------------------------------------------------------------
# Asset endpoints (texture atlas served from local cache)
# ---------------------------------------------------------------------------

@app.get("/api/assets/atlas.png", response_class=FileResponse)
def get_atlas():
    try:
        path = asset_mgr.ensure_atlas()
    except Exception as exc:
        raise HTTPException(503, f"Could not fetch atlas: {exc}") from exc
    return FileResponse(str(path), media_type="image/png")


@app.get("/api/assets/uvmap.json")
def get_uvmap():
    try:
        uvmap = asset_mgr.ensure_uvmap()
    except Exception as exc:
        raise HTTPException(503, f"Could not fetch UV map: {exc}") from exc
    return JSONResponse(uvmap)


@app.get("/api/assets/block_textures.json")
def get_block_textures():
    try:
        uvmap = asset_mgr.ensure_uvmap()
        mapping = asset_mgr.ensure_block_textures(uvmap)
    except Exception as exc:
        raise HTTPException(503, f"Could not build block textures: {exc}") from exc
    return JSONResponse(mapping)


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup() -> None:
    global _index
    print("Scanning structures…")
    _index = _build_and_start_bg()
    print(f"  Index ready: {len(_index.structures)} structures, {len(_index.nbt)} NBT files.")
    print("  Entity resolution running in background.")
    print("  Open http://localhost:8765 in your browser.")
