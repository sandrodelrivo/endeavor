"""Structure scanner: discovers all structures from mod JARs and the datapack."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

MODS_DIR = Path(r"C:\Users\jonat\AppData\Roaming\ModrinthApp\profiles\Aetherian Skies\mods")
DATAPACK_DIR = Path(__file__).parent.parent.parent / "datapack-worldgen" / "zzz_endeavour_worldgen"

# Vanilla Minecraft client-extra JAR (contains all vanilla pools and NBT structures).
# Search the ModrinthApp library cache for the 1.21.1 extra JAR dynamically.
_MC_LIBS = Path(r"C:\Users\jonat\AppData\Roaming\ModrinthApp\meta\libraries\net\minecraft\client")


def _find_vanilla_jar() -> Optional[Path]:
    """Return the path to client-1.21.1-*-extra.jar, or None if not found."""
    if not _MC_LIBS.exists():
        return None
    for version_dir in sorted(_MC_LIBS.iterdir(), reverse=True):
        if not version_dir.name.startswith("1.21.1"):
            continue
        for jar in version_dir.glob("*-extra.jar"):
            return jar
    return None

# Paths inside each JAR/datapack to look for
_STRUCTURE_PAT = re.compile(r"^data/([^/]+)/worldgen/structure/(.+)\.json$")
_POOL_PAT = re.compile(r"^data/([^/]+)/worldgen/template_pool/(.+)\.json$")
_NBT_PAT = re.compile(r"^data/([^/]+)/structures?/(.+)\.nbt$")

_MOD_NAME_RE = re.compile(r"^([a-zA-Z0-9_\-]+?)[-_](?:v|mc)?[\d].*$")


@dataclass
class NbtRef:
    """Location of an NBT structure file."""
    jar: Optional[Path]           # None = datapack
    internal: str                 # path inside JAR or relative to datapack root


@dataclass
class StructureEntry:
    """Everything we know about one worldgen/structure."""
    resource_id: str              # e.g. "minecraft:village/plains"
    namespace: str
    path: str
    source_type: str              # "mod", "datapack"
    source_label: str             # JAR stem or "datapack"
    source_jar: Optional[Path]    # None for datapack sources
    structure_data: dict          # raw JSON
    # Resolved after full index is built:
    entities: list[str] = field(default_factory=list)
    nbt_pieces: list[str] = field(default_factory=list)     # top-level pieces (start pool)
    all_nbt_pieces: list[str] = field(default_factory=list) # all reachable pieces (deep BFS)


@dataclass
class Indices:
    """In-memory index of everything we found."""
    structures: dict[str, StructureEntry] = field(default_factory=dict)
    # template pool resource_id -> raw JSON
    pools: dict[str, dict] = field(default_factory=dict)
    # nbt resource_id -> NbtRef
    nbt: dict[str, NbtRef] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mod_label(jar_path: Path) -> str:
    stem = jar_path.stem
    m = _MOD_NAME_RE.match(stem)
    return m.group(1) if m else stem


def _read_json_from_jar(jar: zipfile.ZipFile, name: str) -> Optional[dict]:
    try:
        return json.loads(jar.read(name))
    except Exception:
        return None


def _read_json_from_disk(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_bytes())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def _scan_jar(jar_path: Path, idx: Indices) -> None:
    try:
        with zipfile.ZipFile(jar_path, "r") as z:
            names = z.namelist()
    except Exception:
        return

    label = _mod_label(jar_path)

    with zipfile.ZipFile(jar_path, "r") as z:
        for name in names:
            if m := _STRUCTURE_PAT.match(name):
                ns, path = m.groups()
                rid = f"{ns}:{path}"
                data = _read_json_from_jar(z, name)
                if data is None:
                    continue
                # Last writer wins (later JARs override earlier ones for the same rid)
                idx.structures[rid] = StructureEntry(
                    resource_id=rid,
                    namespace=ns,
                    path=path,
                    source_type="mod",
                    source_label=label,
                    source_jar=jar_path,
                    structure_data=data,
                )
            elif m := _POOL_PAT.match(name):
                ns, path = m.groups()
                rid = f"{ns}:{path}"
                data = _read_json_from_jar(z, name)
                if data is not None:
                    idx.pools[rid] = data
            elif m := _NBT_PAT.match(name):
                ns, path = m.groups()
                rid = f"{ns}:{path}"
                idx.nbt[rid] = NbtRef(jar=jar_path, internal=name)


def _scan_datapack(dp: Path, idx: Indices) -> None:
    if not dp.exists():
        return
    for f in dp.rglob("*.json"):
        rel = f.relative_to(dp).as_posix()
        if m := _STRUCTURE_PAT.match(rel):
            ns, path = m.groups()
            rid = f"{ns}:{path}"
            data = _read_json_from_disk(f)
            if data is None:
                continue
            idx.structures[rid] = StructureEntry(
                resource_id=rid,
                namespace=ns,
                path=path,
                source_type="datapack",
                source_label="datapack",
                source_jar=None,
                structure_data=data,
            )
        elif m := _POOL_PAT.match(rel):
            ns, path = m.groups()
            rid = f"{ns}:{path}"
            data = _read_json_from_disk(f)
            if data is not None:
                idx.pools[rid] = data
    for f in dp.rglob("*.nbt"):
        rel = f.relative_to(dp).as_posix()
        if m := _NBT_PAT.match(rel):
            ns, path = m.groups()
            rid = f"{ns}:{path}"
            idx.nbt[rid] = NbtRef(jar=None, internal=rel)


# ---------------------------------------------------------------------------
# NBT piece discovery (follows jigsaw pool chains)
# ---------------------------------------------------------------------------

def _collect_pool_pieces(
    pool_id: str,
    idx: Indices,
    visited_pools: set[str],
    depth: int,
) -> list[str]:
    """Return all NBT resource IDs reachable from a template pool."""
    if pool_id in visited_pools or depth > 6:
        return []
    visited_pools.add(pool_id)

    pool = idx.pools.get(pool_id)
    if not pool:
        return []

    pieces: list[str] = []

    def _process_element(el: dict) -> None:
        el_type = el.get("element_type", "")
        if "single_pool_element" in el_type or "legacy_single_pool_element" in el_type:
            loc = el.get("location") or el.get("template")
            if loc and isinstance(loc, str):
                pieces.append(loc)
        elif "list_pool_element" in el_type:
            for child in el.get("elements", []):
                _process_element(child)
        elif "feature_pool_element" in el_type:
            pass  # decorators, no NBT template

    for entry in pool.get("elements", []):
        el = entry.get("element") or entry
        _process_element(el)

    # Recurse into fallback pool
    fallback = pool.get("fallback")
    if fallback and isinstance(fallback, str) and fallback != "minecraft:empty":
        pieces.extend(_collect_pool_pieces(fallback, idx, visited_pools, depth + 1))

    return pieces


def _resolve_pieces(entry: StructureEntry, idx: Indices) -> list[str]:
    """Return list of NBT resource IDs for this structure."""
    data = entry.structure_data
    struct_type = data.get("type", "")

    if "jigsaw" in struct_type:
        start_pool = data.get("start_pool")
        if not start_pool:
            return []
        return list(dict.fromkeys(_collect_pool_pieces(start_pool, idx, set(), 0)))

    # Non-jigsaw: look for a direct 'template' field
    if "template" in data:
        t = data["template"]
        if isinstance(t, str):
            return [t]
        if isinstance(t, dict) and "location" in t:
            return [t["location"]]

    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_index() -> Indices:
    """Scan everything and return a fully resolved index."""
    idx = Indices()

    # 1. Vanilla client-extra JAR — provides all vanilla pools and NBT files.
    #    Must be scanned first so mods can override any of its entries.
    vanilla_jar = _find_vanilla_jar()
    if vanilla_jar:
        _scan_jar(vanilla_jar, idx)
        print(f"  Vanilla JAR: {vanilla_jar.name} ({len(idx.nbt)} NBT, {len(idx.pools)} pools)")
    else:
        print("  WARNING: vanilla client-extra JAR not found; vanilla jigsaw structures will have no pieces")

    # 2. Scan all mod JARs (later entries win, so mods override vanilla)
    if MODS_DIR.exists():
        for jar in sorted(MODS_DIR.glob("*.jar")):
            _scan_jar(jar, idx)

    # 3. Scan our datapack (runs after mods so datapack entries win for same rid)
    _scan_datapack(DATAPACK_DIR, idx)

    # 4. Resolve piece lists for each structure
    for entry in idx.structures.values():
        entry.nbt_pieces = _resolve_pieces(entry, idx)

    return idx


_CACHE_PATH = Path(__file__).parent / ".scan_cache.json"


def _source_fingerprint() -> str:
    """SHA-1 of all scanned source files' paths + mtime_ns + size."""
    paths: list[Path] = []
    vanilla = _find_vanilla_jar()
    if vanilla:
        paths.append(vanilla)
    if MODS_DIR.exists():
        paths.extend(sorted(MODS_DIR.glob("*.jar")))
    if DATAPACK_DIR.exists():
        paths.extend(sorted(f for f in DATAPACK_DIR.rglob("*") if f.is_file()))
    parts: list[str] = []
    for p in paths:
        try:
            st = p.stat()
            parts.append(f"{p}|{st.st_mtime_ns}|{st.st_size}")
        except OSError:
            parts.append(f"{p}|missing")
    return hashlib.sha1("\n".join(parts).encode()).hexdigest()


def load_entity_cache(idx: Indices) -> tuple[bool, str]:
    """Try to restore entity/piece data from disk cache.

    Returns (cache_hit, fingerprint).  fingerprint is always returned so callers
    can pass it to save_entity_cache regardless of hit/miss.
    """
    fp = _source_fingerprint()
    if not _CACHE_PATH.exists():
        return False, fp
    try:
        raw = json.loads(_CACHE_PATH.read_bytes())
    except Exception:
        return False, fp
    if raw.get("fingerprint") != fp:
        return False, fp
    cached = raw.get("structures", {})
    for rid, entry in idx.structures.items():
        if rid in cached:
            c = cached[rid]
            entry.entities = c.get("entities", [])
            entry.nbt_pieces = c.get("nbt_pieces", entry.nbt_pieces)
            entry.all_nbt_pieces = c.get("all_nbt_pieces", [])
    return True, fp


def save_entity_cache(idx: Indices, fingerprint: str) -> None:
    """Persist entity/piece data to disk cache."""
    structures = {
        rid: {
            "entities": entry.entities,
            "nbt_pieces": entry.nbt_pieces,
            "all_nbt_pieces": entry.all_nbt_pieces,
        }
        for rid, entry in idx.structures.items()
    }
    try:
        _CACHE_PATH.write_text(
            json.dumps({"fingerprint": fingerprint, "structures": structures}),
            encoding="utf-8",
        )
        print(f"  Cache saved ({len(structures)} structures).")
    except Exception as exc:
        print(f"  Cache write failed: {exc}")


def read_nbt_bytes(ref: NbtRef) -> bytes:
    """Return raw bytes for an NBT file (caller handles gzip)."""
    if ref.jar is not None:
        with zipfile.ZipFile(ref.jar, "r") as z:
            return z.read(ref.internal)
    else:
        full = DATAPACK_DIR / ref.internal
        return full.read_bytes()
