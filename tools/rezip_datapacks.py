"""Rebuild Endeavour datapack zips with forward-slash entry paths.

Minecraft on Linux servers cannot load datapack zips whose entry names
contain backslashes. Windows zip tools (Compress-Archive, .NET
ZipFile.CreateFromDirectory, the Windows shell's "Send to compressed
folder") all default to backslashes, which silently break the pack on
any non-Windows host.

This script walks each datapack source directory and rebuilds the
matching .zip with normalized POSIX paths.

Run from anywhere — paths are resolved relative to the repo root:

    python tools/rezip_datapacks.py
"""

import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DATAPACKS = [
    ("datapack-rules", "zzz_endeavour_rules"),
    ("datapack-worldgen", "zzz_endeavour_worldgen"),
]


def build_zip(source_dir: Path, zip_path: Path) -> None:
    """Rebuild zip_path from the contents of source_dir.

    Entry names are written as POSIX paths (forward slashes) regardless
    of the host OS, so the resulting zip loads correctly on Linux
    Minecraft servers.
    """
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                arcname = path.relative_to(source_dir).as_posix()
                zf.write(path, arcname)


def main() -> None:
    for parent_name, pack_name in DATAPACKS:
        source = REPO_ROOT / parent_name / pack_name
        target = REPO_ROOT / parent_name / f"{pack_name}.zip"
        if not source.is_dir():
            print(f"skip: {source.relative_to(REPO_ROOT)} (not a directory)")
            continue
        build_zip(source, target)
        size_kb = target.stat().st_size / 1024
        print(f"built: {target.relative_to(REPO_ROOT)} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
