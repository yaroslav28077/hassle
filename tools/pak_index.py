"""Чтение индекса .pak v11/v12 (UE5) без распаковки данных: путь -> смещение, размеры, метод сжатия, SHA-1.

SHA-1 берётся из inline FPakEntry перед данными файла: это хэш хранимых (сжатых) данных,
по нему можно понять, менялся ли файл после обновления игры, не распаковывая Oodle.

Только чтение. Используется tools/check_update.py.
"""
from __future__ import annotations

import struct
from pathlib import Path

from list_paks import PAK_MAGIC, norm_mount, read_fstring


def _decode_entry(buf: bytes, pos: int) -> dict:
    """UE5 FPakFile::DecodePakEntry (encoded entries в PrimaryIndex)."""
    value, = struct.unpack_from("<I", buf, pos)
    pos += 4
    if (value & 0x3F) == 0x3F:
        pos += 4  # CompressionBlockSize u32
    offset32 = bool(value & (1 << 31))
    usz32 = bool(value & (1 << 30))
    sz32 = bool(value & (1 << 29))
    method = (value >> 23) & 0x3F
    encrypted = bool(value & (1 << 22))
    blocks = (value >> 6) & 0xFFFF

    def rd(is32: bool) -> int:
        nonlocal pos
        if is32:
            v, = struct.unpack_from("<I", buf, pos)
            pos += 4
        else:
            v, = struct.unpack_from("<Q", buf, pos)
            pos += 8
        return v

    offset = rd(offset32)
    usz = rd(usz32)
    csz = rd(sz32) if method else usz
    return {"offset": offset, "uncompressed_size": usz, "size": csz, "method": method,
            "encrypted": encrypted, "blocks": blocks}


def read_entries(pak: Path) -> dict[str, dict]:
    """{полный_путь_в_нижнем_регистре: {path, offset, size, uncompressed_size, method, sha1}}."""
    out: dict[str, dict] = {}
    with open(pak, "rb") as f:
        f.seek(0, 2)
        fsize = f.tell()
        f.seek(max(0, fsize - 1024))
        tail = f.read()
        i = tail.rfind(PAK_MAGIC)
        if i < 17:
            raise ValueError(f"{pak.name}: не найден footer pak")
        if tail[i - 1]:
            raise ValueError(f"{pak.name}: индекс зашифрован")
        ver, idx_off, idx_sz = struct.unpack_from("<IQQ", tail, i + 4)
        if ver < 10:
            raise ValueError(f"{pak.name}: версия pak {ver} без encoded entries не поддержана")
        f.seek(idx_off)
        idx = f.read(idx_sz)
        mp, pos = read_fstring(idx, 0)
        mp_clean = norm_mount(mp)
        _num, _seed, has_ph = struct.unpack_from("<IQi", idx, pos)
        pos += 16
        if has_ph:
            pos += 8 + 8 + 20
        has_fd, = struct.unpack_from("<i", idx, pos)
        pos += 4
        if not has_fd:
            return out
        fd_off, fd_sz = struct.unpack_from("<qq", idx, pos)
        pos += 8 + 8 + 20
        enc_len, = struct.unpack_from("<i", idx, pos)
        enc = idx[pos + 4: pos + 4 + enc_len]

        f.seek(fd_off)
        fd = f.read(fd_sz)
        dir_cnt, = struct.unpack_from("<i", fd, 0)
        fp = 4
        for _ in range(dir_cnt):
            dname, fp = read_fstring(fd, fp)
            if dname == "/":
                dname = ""
            file_cnt, = struct.unpack_from("<i", fd, fp)
            fp += 4
            for _ in range(file_cnt):
                fname, fp = read_fstring(fd, fp)
                eoff, = struct.unpack_from("<i", fd, fp)
                fp += 4
                rel = f"{dname}{fname}".lstrip("/")
                full = f"{mp_clean}{rel}" if mp_clean else rel
                rec = {"path": full}
                if eoff >= 0:
                    rec.update(_decode_entry(enc, eoff))
                    # inline FPakEntry: Offset(8) Size(8) UncompressedSize(8) Method(4) SHA1(20)
                    f.seek(rec["offset"] + 28)
                    rec["sha1"] = f.read(20).hex()
                out[full.lower()] = rec
    return out
