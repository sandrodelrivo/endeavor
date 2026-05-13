"""Strip blocks pointing to minecraft:structure_void from a structure NBT file.

Structure_void is ignored by the structure SAVER, not the loader. If you edit a
saved structure's palette to repoint a real block (e.g. air) at structure_void,
the loader still places "void air" at those coordinates and obliterates natural
terrain. The fix is to delete the offending block entries entirely so the loader
does not touch those positions.

Usage:
    .venv/Scripts/python.exe strip_structure_voids.py <path-to.nbt> [--dry-run] [--no-backup]
"""

from __future__ import annotations

import argparse
import gzip
import io
import shutil
import sys
from pathlib import Path

import nbtlib
from nbtlib import File as NbtFile

STRUCTURE_VOID = "minecraft:structure_void"
GZIP_MAGIC = b"\x1f\x8b"


def _void_indices(palette) -> set[int]:
    return {i for i, e in enumerate(palette) if str(e.get("Name", "")) == STRUCTURE_VOID}


def strip(nbt_path: Path, dry_run: bool, backup: bool) -> int:
    raw = nbt_path.read_bytes()
    gzipped = raw[:2] == GZIP_MAGIC
    decompressed = gzip.decompress(raw) if gzipped else raw

    nbt = NbtFile.from_fileobj(io.BytesIO(decompressed), byteorder="big")

    void_indices: set[int] = set()
    if "palette" in nbt:
        void_indices |= _void_indices(nbt["palette"])
    if "palettes" in nbt:
        for pal in nbt["palettes"]:
            void_indices |= _void_indices(pal)

    if not void_indices:
        print("No minecraft:structure_void entries found. Nothing to do.")
        return 0

    print(f"structure_void palette indices: {sorted(void_indices)}")

    blocks = nbt["blocks"]
    before = len(blocks)
    kept = type(blocks)(b for b in blocks if int(b["state"]) not in void_indices)
    nbt["blocks"] = kept
    after = len(kept)
    removed = before - after
    print(f"blocks: {before} -> {after} (removed {removed})")

    if dry_run:
        print("Dry-run; not writing.")
        return removed

    if backup:
        backup_path = nbt_path.with_suffix(nbt_path.suffix + ".bak")
        if backup_path.exists():
            print(f"Backup already exists, not overwriting: {backup_path}")
        else:
            shutil.copy2(nbt_path, backup_path)
            print(f"Backup written: {backup_path}")

    buf = io.BytesIO()
    nbt.write(buf, byteorder="big")
    payload = buf.getvalue()
    if gzipped:
        payload = gzip.compress(payload)
    nbt_path.write_bytes(payload)
    print(f"Wrote: {nbt_path} ({len(payload)} bytes)")
    return removed


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("path", type=Path, help="Path to structure .nbt file")
    p.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    p.add_argument("--no-backup", action="store_true", help="Skip writing a .bak alongside")
    args = p.parse_args()

    if not args.path.is_file():
        print(f"Not a file: {args.path}", file=sys.stderr)
        return 2

    strip(args.path, args.dry_run, not args.no_backup)
    return 0


if __name__ == "__main__":
    sys.exit(main())
