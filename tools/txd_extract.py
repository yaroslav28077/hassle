"""Извлечение текстур из RenderWare .txd (GTA SA D3D9, GTA III/VC D3D8) в PNG с альфой.

python tools/txd_extract.py source work/textures            # рекурсивно всю папку
python tools/txd_extract.py source/hud/hud.txd work/textures

Результат: work/textures/<имя_txd>/<имя_текстуры>.png и work/textures/manifest.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import struct
from pathlib import Path

from PIL import Image

from common import (RW_EXTENSION, RW_STRUCT, RW_TEX_DICTIONARY, RW_TEXTURE_NATIVE,
                    get_logger, rw_header)

FMT_MASK = 0x0F00
FMT_NAMES = {0x0100: "1555", 0x0200: "565", 0x0300: "4444", 0x0400: "LUM8",
             0x0500: "8888", 0x0600: "888", 0x0A00: "555"}
PAL8, PAL4 = 0x2000, 0x4000
FOURCC = {b"DXT1": "DXT1", b"DXT2": "DXT3", b"DXT3": "DXT3", b"DXT4": "DXT5", b"DXT5": "DXT5"}
D3DFMT = {21: "8888", 22: "888", 23: "565", 24: "555", 25: "1555", 26: "4444", 50: "LUM8"}


def _dds_from_dxt(fourcc: str, w: int, h: int, data: bytes) -> Image.Image:
    block = 8 if fourcc == "DXT1" else 16
    linear = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * block
    header = struct.pack(
        "<4s7I44x2I4s5I5I",
        b"DDS ", 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000, h, w, linear, 0, 1,
        32, 0x4, fourcc.encode(), 0, 0, 0, 0, 0,
        0x1000, 0, 0, 0, 0,
    )
    assert len(header) == 128
    return Image.open(io.BytesIO(header + data[:linear])).convert("RGBA")


def _raw_to_image(fmt: str, w: int, h: int, data: bytes) -> Image.Image:
    n = w * h
    if fmt == "8888":
        return Image.frombuffer("RGBA", (w, h), data[: n * 4], "raw", "BGRA", 0, 1).copy()
    if fmt == "888":
        return Image.frombuffer("RGBX", (w, h), data[: n * 4], "raw", "BGRX", 0, 1).convert("RGBA")
    if fmt == "LUM8":
        return Image.frombuffer("L", (w, h), data[:n], "raw", "L", 0, 1).convert("RGBA")
    px = struct.unpack_from(f"<{n}H", data)
    out = bytearray(n * 4)
    for i, v in enumerate(px):
        if fmt == "1555":
            a, r, g, b = (255 if v >> 15 else 0), (v >> 10) & 31, (v >> 5) & 31, v & 31
            r, g, b = r * 255 // 31, g * 255 // 31, b * 255 // 31
        elif fmt == "555":
            a, r, g, b = 255, ((v >> 10) & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, (v & 31) * 255 // 31
        elif fmt == "565":
            a, r, g, b = 255, (v >> 11) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31
        elif fmt == "4444":
            a, r, g, b = ((v >> 12) & 15) * 17, ((v >> 8) & 15) * 17, ((v >> 4) & 15) * 17, (v & 15) * 17
        else:
            raise ValueError(f"формат {fmt} не поддержан")
        out[i * 4: i * 4 + 4] = bytes((r, g, b, a))
    return Image.frombytes("RGBA", (w, h), bytes(out))


def _pal_to_image(pal: bytes, bits: int, w: int, h: int, data: bytes) -> Image.Image:
    colors = [tuple(pal[i * 4: i * 4 + 4]) for i in range(len(pal) // 4)]
    out = bytearray(w * h * 4)
    for i in range(w * h):
        idx = data[i] if bits == 8 else (data[i >> 1] >> ((i & 1) * 4)) & 0xF
        out[i * 4: i * 4 + 4] = bytes(colors[idx])
    return Image.frombytes("RGBA", (w, h), bytes(out))


def parse_texture_native(buf: bytes) -> dict:
    """buf = содержимое Struct-чанка внутри TextureNative."""
    platform, = struct.unpack_from("<I", buf, 0)
    name = buf[8:40].split(b"\0")[0].decode("latin1")
    mask = buf[40:72].split(b"\0")[0].decode("latin1")
    raster_fmt, fmt_field = struct.unpack_from("<II", buf, 72)
    w, h, depth, levels, rtype, flags = struct.unpack_from("<HHBBBB", buf, 80)
    off = 88
    tex = {"name": name, "mask": mask, "platform": platform, "width": w, "height": h,
           "depth": depth, "levels": levels}
    compression = None
    if platform == 9:  # D3D9 (GTA SA)
        fourcc = struct.pack("<I", fmt_field)
        if fourcc in FOURCC:
            compression = FOURCC[fourcc]
        tex["has_alpha"] = bool(flags & 1)
        raw_fmt = FMT_NAMES.get(raster_fmt & FMT_MASK) or D3DFMT.get(fmt_field)
    elif platform == 8:  # D3D8 (GTA III / VC PC)
        if flags:
            compression = f"DXT{flags}" if flags in (1, 3, 5) else None
        tex["has_alpha"] = bool(fmt_field)
        raw_fmt = FMT_NAMES.get(raster_fmt & FMT_MASK)
    else:
        raise ValueError(f"платформа {platform} не поддержана (не ПК-версия)")

    palette = None
    if raster_fmt & PAL8:
        palette, off = buf[off: off + 1024], off + 1024
    elif raster_fmt & PAL4:
        palette, off = buf[off: off + 64], off + 64

    size, = struct.unpack_from("<I", buf, off)
    data = buf[off + 4: off + 4 + size]
    if compression:
        img = _dds_from_dxt(compression, w, h, data)
        tex["format"] = compression
    elif palette is not None:
        img = _pal_to_image(palette, 8 if raster_fmt & PAL8 else 4, w, h, data)
        tex["format"] = "PAL8" if raster_fmt & PAL8 else "PAL4"
    else:
        img = _raw_to_image(raw_fmt, w, h, data)
        tex["format"] = raw_fmt
    tex["image"] = img
    return tex


def iter_textures(data: bytes):
    t, size, _ = rw_header(data)
    if t != RW_TEX_DICTIONARY:
        raise ValueError("это не TXD (нет чанка TexDictionary)")
    off, end = 12, 12 + size
    while off + 12 <= end:
        ct, csize, _ = rw_header(data, off)
        body = off + 12
        if ct == RW_TEXTURE_NATIVE:
            st, ssize, _ = rw_header(data, body)
            if st == RW_STRUCT:
                try:
                    yield parse_texture_native(data[body + 12: body + 12 + ssize]), None
                except Exception as e:  # noqa: BLE001
                    yield None, e
        elif ct not in (RW_STRUCT, RW_EXTENSION):
            pass
        off = body + csize


def safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s).strip("_") or "unnamed"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    a = ap.parse_args()
    log = get_logger("txd_extract")
    src, out = Path(a.src), Path(a.out)
    # fix: пропускать директории с именем, оканчивающимся на .txd (например oneasData/.../VEHICLE.TXD)
    files = [src] if src.is_file() else sorted(p for p in src.rglob("*") if p.is_file() and p.suffix.lower() == ".txd")
    out.mkdir(parents=True, exist_ok=True)
    rows, ok, bad = [], 0, 0
    for f in files:
        try:
            data = f.read_bytes()
            textures = list(iter_textures(data))
        except Exception as e:  # noqa: BLE001
            log.error("%s: %s", f, e)
            bad += 1
            continue
        tdir = out / safe(f.stem)
        tdir.mkdir(exist_ok=True)
        for tex, err in textures:
            if err:
                log.warning("%s: текстура пропущена: %s", f.name, err)
                bad += 1
                continue
            png = tdir / f"{safe(tex['name'])}.png"
            tex.pop("image").save(png)
            rows.append({"txd": str(f), "texture": tex["name"], "mask": tex["mask"],
                         "png": png.as_posix(), "width": tex["width"], "height": tex["height"],
                         "format": tex["format"], "has_alpha": tex.get("has_alpha"),
                         "mip_levels": tex["levels"]})
            ok += 1
    # манифест дополняется: строки из других запусков сохраняются, обработанные сейчас TXD перезаписываются
    manifest = out / "manifest.csv"
    done = {str(f) for f in files}
    if manifest.exists():
        with open(manifest, encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh) if r["txd"] not in done] + rows
    with open(manifest, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["txd", "texture", "mask", "png", "width", "height",
                                           "format", "has_alpha", "mip_levels"])
        w.writeheader()
        w.writerows(rows)
    log.info("TXD: %d, текстур извлечено: %d, ошибок: %d", len(files), ok, bad)


if __name__ == "__main__":
    main()
