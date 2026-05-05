"""
Downloads and caches Minecraft 1.21.1 texture assets from mcmeta.

Cached to tools/structure-manager/cache/:
  atlas.png           — full block texture atlas image
  uvmap.json          — {texture_id: [u_norm, v_norm, u2_norm, v2_norm]}  (0–1 range)
  block_textures.json — {block_id: texture_id} resolved via block state + model chain
"""

from __future__ import annotations

import io
import json
import ssl
import tarfile
import urllib.request
from pathlib import Path

MCMETA = "https://raw.githubusercontent.com/misode/mcmeta"
MC_VERSION = "1.21.1"
ATLAS_URL    = f"{MCMETA}/{MC_VERSION}-atlas/all/atlas.png"
UVDATA_URL   = f"{MCMETA}/{MC_VERSION}-atlas/all/data.min.json"
ASSETS_TAR_URL = f"https://github.com/misode/mcmeta/tarball/{MC_VERSION}-assets-json"

CACHE_DIR = Path(__file__).parent / "cache"

# Texture variable keys to try, in priority order (prefer top-face look)
_TEX_PRIORITY = [
    "top", "particle", "all", "end", "up",
    "side", "cross", "wool", "content",
    "0", "1", "2", "3",
]


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _download(url: str, dest: Path) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    print(f"  Downloading {url} …")
    with urllib.request.urlopen(url, context=_ssl_ctx(), timeout=60) as r:
        dest.write_bytes(r.read())
    print(f"  Cached to {dest.name}  ({dest.stat().st_size // 1024} KB)")


# ---------------------------------------------------------------------------
# Atlas
# ---------------------------------------------------------------------------

def ensure_atlas() -> Path:
    dest = CACHE_DIR / "atlas.png"
    if not dest.exists():
        _download(ATLAS_URL, dest)
    return dest


def ensure_uvmap() -> dict[str, list[float]]:
    """Return {texture_id: [u0, v0, u1, v1]} normalised to 0–1."""
    cache = CACHE_DIR / "uvmap.json"
    if cache.exists():
        return json.loads(cache.read_bytes())

    raw_path = CACHE_DIR / "uvdata_raw.json"
    if not raw_path.exists():
        _download(UVDATA_URL, raw_path)
    raw: dict = json.loads(raw_path.read_bytes())

    atlas_path = ensure_atlas()
    w, h = _png_dimensions(atlas_path)

    uvmap: dict[str, list[float]] = {}
    for tid, coords in raw.items():
        if not isinstance(coords, list) or len(coords) < 4:
            continue
        u, v, du, dv = coords[:4]
        if tid.startswith("block/") and dv > du:
            dv = du  # clamp animated textures to one frame
        uvmap[tid] = [
            round(u / w, 6),
            round(v / h, 6),
            round((u + du) / w, 6),
            round((v + dv) / h, 6),
        ]

    cache.write_text(json.dumps(uvmap), encoding="utf-8")
    print(f"  UV map built: {len(uvmap)} textures")
    return uvmap


# ---------------------------------------------------------------------------
# Block textures — resolved via block state + model chain
# ---------------------------------------------------------------------------

def ensure_block_textures(uvmap: dict) -> dict[str, str]:
    """
    Return {block_id: texture_id} for every vanilla block, resolved through
    the Minecraft block state → model → texture variable chain.

    block_id   e.g. "smooth_sandstone"  (no namespace)
    texture_id e.g. "block/sandstone_top"  (as it appears in uvmap keys)
    """
    cache = CACHE_DIR / "block_textures.json"
    if cache.exists():
        return json.loads(cache.read_bytes())

    blockstates, models = _load_assets_json()
    result: dict[str, str] = {}

    for block_name, bs_data in blockstates.items():
        tex = _resolve_block_texture(block_name, bs_data, models, uvmap)
        if tex:
            result[block_name] = tex

    cache.write_text(json.dumps(result), encoding="utf-8")
    print(f"  Block texture map built: {len(result)} entries")
    return result


def _load_assets_json() -> tuple[dict, dict]:
    """
    Download the mcmeta assets-json tarball and return
    (blockstates, models) dicts keyed by bare name / path.
    """
    tar_path = CACHE_DIR / "assets_json.tar.gz"
    if not tar_path.exists():
        _download(ASSETS_TAR_URL, tar_path)

    blockstates: dict[str, dict] = {}
    models: dict[str, dict] = {}

    print("  Parsing assets tarball…")
    with tarfile.open(tar_path, "r:gz") as tf:
        for member in tf.getmembers():
            name = member.name
            # Match  .../assets/minecraft/blockstates/{name}.json
            if "/assets/minecraft/blockstates/" in name and name.endswith(".json"):
                key = name.rsplit("/", 1)[-1][:-5]  # strip .json
                try:
                    data = json.loads(tf.extractfile(member).read())
                    blockstates[key] = data
                except Exception:
                    pass
            # Match  .../assets/minecraft/models/block/{path}.json  (may be nested)
            elif "/assets/minecraft/models/" in name and name.endswith(".json"):
                # key = everything after "models/"  e.g. "block/stone"
                idx = name.find("/assets/minecraft/models/")
                key = name[idx + len("/assets/minecraft/models/"):-5]
                try:
                    data = json.loads(tf.extractfile(member).read())
                    models[key] = data
                except Exception:
                    pass

    print(f"  Loaded {len(blockstates)} blockstates, {len(models)} models")
    return blockstates, models


def _resolve_block_texture(
    block_name: str,
    bs_data: dict,
    models: dict,
    uvmap: dict,
) -> str | None:
    """Walk blockstate → model chain and return the best atlas texture_id."""

    model_id = _first_model_from_blockstate(bs_data)
    if not model_id:
        return None

    # Strip namespace  e.g. "minecraft:block/stone" → "block/stone"
    model_id = model_id.split(":", 1)[-1]

    # Collect all texture variable assignments walking up the parent chain
    textures = _collect_textures(model_id, models)

    # Resolve a variable reference to a concrete texture path (no namespace, no #)
    def resolve(ref: str) -> str | None:
        ref = ref.split(":", 1)[-1]  # strip namespace
        seen: set[str] = set()
        while ref.startswith("#"):
            key = ref[1:]
            if key in seen:
                return None
            seen.add(key)
            ref = textures.get(key, "")
            ref = ref.split(":", 1)[-1]
        return ref or None

    # Try keys in priority order; require the resolved ID to actually be in uvmap
    for key in _TEX_PRIORITY:
        if key not in textures:
            continue
        resolved = resolve(textures[key])
        if resolved and resolved in uvmap:
            return resolved

    # Fall through: resolve all texture values, return first that hits the atlas
    for val in textures.values():
        resolved = resolve(val)
        if resolved and resolved in uvmap:
            return resolved

    return None


def _first_model_from_blockstate(bs_data: dict) -> str | None:
    """Extract the first model reference from a blockstate JSON."""
    if "variants" in bs_data:
        for variant_val in bs_data["variants"].values():
            entry = variant_val[0] if isinstance(variant_val, list) else variant_val
            if isinstance(entry, dict) and "model" in entry:
                return entry["model"]
    if "multipart" in bs_data:
        for part in bs_data["multipart"]:
            apply = part.get("apply", {})
            entry = apply[0] if isinstance(apply, list) else apply
            if isinstance(entry, dict) and "model" in entry:
                return entry["model"]
    return None


def _collect_textures(model_id: str, models: dict) -> dict[str, str]:
    """Walk model parent chain, collecting texture variable assignments."""
    textures: dict[str, str] = {}
    visited: set[str] = set()

    def _walk(mid: str) -> None:
        if mid in visited:
            return
        visited.add(mid)
        model = models.get(mid)
        if not model:
            return
        # Child textures take priority over parent — only add if key not yet set
        for k, v in model.get("textures", {}).items():
            if k not in textures:
                textures[k] = v
        parent = model.get("parent", "")
        if parent:
            _walk(parent.split(":", 1)[-1])

    _walk(model_id)
    return textures


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _png_dimensions(path: Path) -> tuple[int, int]:
    """Read PNG width/height from the IHDR chunk (bytes 16–24)."""
    import struct
    data = path.read_bytes()
    w = struct.unpack(">I", data[16:20])[0]
    h = struct.unpack(">I", data[20:24])[0]
    return w, h
