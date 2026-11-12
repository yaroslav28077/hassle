"""Распаковка GTA .img архивов (v2 'VER2' — GTA SA; v1 — пара .img + .dir).

python tools/img_extract.py source/models/gta3.img work/extracted/gta3
python tools/img_extract.py source work/extracted          # все .img в папке
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

from common import get_logger

SECTOR = 2048


def entries(img: Path):
    with open(img, "rb") as f:
        head = f.read(8)
        if head[:4] == b"VER2":
            count = struct.unpack_from("<I", head, 4)[0]
            for _ in range(count):
                off, streaming, archived, name = struct.unpack("<IHH24s", f.read(32))
                yield name.split(b"\0")[0].decode("latin1"), off, archived or streaming
            return
    dir_file = img.with_suffix(".dir")
    if not dir_file.exists():
        raise ValueError("нет сигнатуры VER2 и рядом нет .dir (v1)")
    raw = dir_file.read_bytes()
    for i in range(0, len(raw) - 31, 32):
        off, size, name = struct.unpack_from("<II24s", raw, i)
        yield name.split(b"\0")[0].decode("latin1"), off, size


def extract(img: Path, out: Path, log) -> int:
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(img, "rb") as f:
        for name, off, sectors in entries(img):
            f.seek(off * SECTOR)
            (out / name).write_bytes(f.read(sectors * SECTOR))
            n += 1
    log.info("%s → %s: %d файлов", img.name, out, n)
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    a = ap.parse_args()
    log = get_logger("img_extract")
    src, out = Path(a.src), Path(a.out)
    if src.is_file():
        extract(src, out, log)
    else:
        for img in sorted(src.rglob("*.img")):
            try:
                extract(img, out / img.stem, log)
            except Exception as e:  # noqa: BLE001
                log.error("%s: %s", img, e)


if __name__ == "__main__":
    main()
