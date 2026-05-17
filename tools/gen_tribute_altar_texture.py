"""Generate the tribute_altar.png block texture (16x16, RGB PNG)."""
import zlib
import struct
import os

# Colour palette
E  = (30,  26,  44)   # edge - very dark stone border
D  = (40,  36,  54)   # dark stone ring
B  = (58,  54,  72)   # base stone
L  = (78,  74,  96)   # stone highlight (corner accents)
R  = (85,  55, 108)   # rune / carved channel (purple-grey)
O  = (140, 85,  10)   # glow outer (deep amber)
M  = (200, 135, 20)   # glow mid
C  = (245, 185, 45)   # glow core
H  = (255, 220, 100)  # glow hot centre

# fmt: off
# 16x16 grid, row-major, top-to-bottom.
# The design: dark stone with a concentric amber glow and cardinal rune marks.
GRID = [
#   0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
   [E, E, E, E, E, E, E, E, E, E, E, E, E, E, E, E],  # 0
   [E, D, D, D, D, D, D, D, D, D, D, D, D, D, D, E],  # 1
   [E, D, B, B, B, B, B, R, R, B, B, B, B, B, D, E],  # 2  top rune
   [E, D, B, L, B, B, B, B, B, B, B, B, L, B, D, E],  # 3  corner highlight
   [E, D, B, B, B, B, O, O, O, O, B, B, B, B, D, E],  # 4
   [E, D, B, B, B, O, M, M, M, M, O, B, B, B, D, E],  # 5
   [E, D, B, R, B, O, M, C, C, M, O, B, R, B, D, E],  # 6  side runes + core
   [E, D, R, B, B, O, C, H, H, C, O, B, B, R, D, E],  # 7  hot centre
   [E, D, R, B, B, O, C, H, H, C, O, B, B, R, D, E],  # 8  hot centre
   [E, D, B, R, B, O, M, C, C, M, O, B, R, B, D, E],  # 9  side runes + core
   [E, D, B, B, B, O, M, M, M, M, O, B, B, B, D, E],  # 10
   [E, D, B, B, B, B, O, O, O, O, B, B, B, B, D, E],  # 11
   [E, D, B, L, B, B, B, B, B, B, B, B, L, B, D, E],  # 12 corner highlight
   [E, D, B, B, B, B, B, R, R, B, B, B, B, B, D, E],  # 13 bottom rune
   [E, D, D, D, D, D, D, D, D, D, D, D, D, D, D, E],  # 14
   [E, E, E, E, E, E, E, E, E, E, E, E, E, E, E, E],  # 15
]
# fmt: on


def _chunk(tag: bytes, data: bytes) -> bytes:
    payload = tag + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def write_png(path: str, pixels: list[list[tuple[int, int, int]]]) -> None:
    h = len(pixels)
    w = len(pixels[0])
    raw = b"".join(
        b"\x00" + bytes(v for rgb in row for v in rgb)
        for row in pixels
    )
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    idat = _chunk(b"IDAT", zlib.compress(raw, 9))
    iend = _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend)


if __name__ == "__main__":
    out = os.path.join(
        os.path.dirname(__file__),
        "..", "mod", "src", "main", "resources",
        "assets", "endeavour", "textures", "block",
        "tribute_altar.png",
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    write_png(out, GRID)
    print(f"Written: {os.path.abspath(out)}")
