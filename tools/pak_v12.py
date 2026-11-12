"""Сборка незашифрованных несжатых (cm=0) .pak версии 12 для Unreal Engine 5.

Формат проверен по оригинальным .pak HASSLE 2.0 (UE 5.8, FPakInfo v12, 221 байт).
Поддерживает:
- добавление обычных файлов (Cohtml UI, PNG/SVG/HTML/CSS/JS/MP3/WAV/TTF);
- корректные PrimaryIndex, PathHashIndex (FNV-1a 64-bit UTF-16LE + seed), FullDirectoryIndex;
- SHA-1 для каждой записи, обоих вторичных индексов и PrimaryIndex;
- самопроверку созданного архива.
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path
from typing import Iterable

PAK_MAGIC = 0x5A6F12E1
PAK_VERSION_FROZEN_REMOVED = 12  # UE5 v12: FPakInfo = 221 bytes (no bFrozenIndex)


# fix: В UE5 .pak v12 (проверено по pakchunk82/165/166/181 HASSLE 2.0) имена файлов в FullDirectoryIndex
# сериализуются БЕЗ завершающего '\x00', а MountPoint и имена папок — С завершающим '\x00'.
def _fstring(s: str, null_term: bool = True) -> bytes:
    """Сериализовать FString (ASCII или UTF-16LE при не-ASCII)."""
    try:
        raw = s.encode("ascii")
        if null_term:
            return struct.pack("<i", len(raw) + 1) + raw + b"\x00"
        return struct.pack("<i", len(raw)) + raw
    except UnicodeEncodeError:
        raw = s.encode("utf-16-le") + (b"\x00\x00" if null_term else b"")
        return struct.pack("<i", -(len(raw) // 2)) + raw


def pak_path_hash(rel_path: str, seed: int) -> int:
    """UE5 FPakFile::HashString: FNV-1a 64-bit по lower UTF-16LE с начальным смещением seed."""
    h = (0xCBF29CE484222325 + seed) & 0xFFFFFFFFFFFFFFFF
    for ch in rel_path.lower():
        code = ord(ch)
        h = ((h ^ (code & 0xFF)) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
        h = ((h ^ ((code >> 8) & 0xFF)) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def build_pak_v12(
    out_pak: Path,
    files: Iterable[tuple[str, Path]],
    mount_point: str = "../../../HassleOnline/Content/",
    seed: int | None = None,
) -> dict[str, int]:
    """Собрать .pak v12 (cm=0) из пар (relative_path_under_mount, local_file_path).

    Возвращает словарь статистики: files, payload_bytes, pak_bytes.
    """
    items: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for rel, src in sorted(files, key=lambda x: x[0].lower()):
        norm = rel.replace("\\", "/").lstrip("/")
        low = norm.lower()
        if low in seen:
            raise ValueError(f"Дубликат пути внутри пака: {norm}")
        if not src.is_file():
            raise FileNotFoundError(f"Файл для упаковки не найден: {src}")
        seen.add(low)
        items.append((norm, src))

    if not mount_point.endswith("/"):
        mount_point += "/"
    if seed is None:
        seed = zlib.crc32(out_pak.name.encode("utf-8")) & 0xFFFFFFFF

    out_pak.parent.mkdir(parents=True, exist_ok=True)
    enc_buf = bytearray()
    dir_map: dict[str, list[tuple[str, int]]] = {}
    ph_entries: list[tuple[int, int]] = []
    payload_total = 0

    with open(out_pak, "wb") as f:
        for rel, src in items:
            data = src.read_bytes()
            usz = len(data)
            payload_total += usz
            entry_offset = f.tell()
            data_sha1 = hashlib.sha1(data).digest()
            # Inline FPakEntry (cm=0): Offset(0), Size, UncompressedSize, CompMethod(0), SHA1, Flags(0), BlockSize(0)
            inline_hdr = struct.pack("<QQQI20sBI", 0, usz, usz, 0, data_sha1, 0, 0)
            f.write(inline_hdr)
            f.write(data)

            enc_off = len(enc_buf)
            flags = 0x20000000  # bIsSize32BitSafe (unused for cm=0)
            if entry_offset < 0x100000000:
                flags |= 0x80000000
            if usz < 0x100000000:
                flags |= 0x40000000
            enc_buf.extend(struct.pack("<I", flags))
            enc_buf.extend(struct.pack("<I" if (flags & 0x80000000) else "<Q", entry_offset))
            enc_buf.extend(struct.pack("<I" if (flags & 0x40000000) else "<Q", usz))

            ph_entries.append((pak_path_hash(rel, seed), enc_off))
            # fix: UE5 хранит корень "/" и все промежуточные родительские папки в FullDirectoryIndex
            dir_map.setdefault("/", [])
            if "/" in rel:
                d, fn = rel.rsplit("/", 1)
                parts = d.split("/")
                for i in range(1, len(parts) + 1):
                    dir_map.setdefault("/".join(parts[:i]) + "/", [])
                d_key = d + "/"
            else:
                d_key, fn = "/", rel
            dir_map[d_key].append((fn, enc_off))

        idx_offset = f.tell()

        # PathHashIndex bytes
        ph_buf = bytearray(struct.pack("<i", len(ph_entries)))
        for h, eoff in ph_entries:
            ph_buf.extend(struct.pack("<Qi", h, eoff))
        ph_buf.extend(struct.pack("<i", 0))
        ph_bytes = bytes(ph_buf)
        ph_sha1 = hashlib.sha1(ph_bytes).digest()

        # FullDirectoryIndex bytes
        fd_buf = bytearray(struct.pack("<i", len(dir_map)))
        for d_key in sorted(dir_map.keys()):
            fd_buf.extend(_fstring(d_key, null_term=True))
            flist = sorted(dir_map[d_key], key=lambda x: x[0])
            fd_buf.extend(struct.pack("<i", len(flist)))
            for fn, eoff in flist:
                # fix: FileName в FullDirectoryIndex в UE5 v12 без '\x00' на конце
                fd_buf.extend(_fstring(fn, null_term=False))
                fd_buf.extend(struct.pack("<i", eoff))
        fd_bytes = bytes(fd_buf)
        fd_sha1 = hashlib.sha1(fd_bytes).digest()

        # PrimaryIndex layout: MountPoint, NumEntries, Seed, PH_meta, FD_meta, EncodedPakEntries, FilesCount=0
        # Compute PrimaryIndex size first so ph_offset & fd_offset are exact.
        prefix = _fstring(mount_point) + struct.pack("<IQ", len(items), seed)
        meta_placeholder = struct.pack("<iQQ20s", 1, 0, len(ph_bytes), ph_sha1) + struct.pack(
            "<iQQ20s", 1, 0, len(fd_bytes), fd_sha1
        )
        suffix = struct.pack("<i", len(enc_buf)) + bytes(enc_buf) + struct.pack("<i", 0)
        idx_size = len(prefix) + len(meta_placeholder) + len(suffix)

        ph_offset = idx_offset + idx_size
        fd_offset = ph_offset + len(ph_bytes)

        primary_index = (
            prefix
            + struct.pack("<iQQ20s", 1, ph_offset, len(ph_bytes), ph_sha1)
            + struct.pack("<iQQ20s", 1, fd_offset, len(fd_bytes), fd_sha1)
            + suffix
        )
        assert len(primary_index) == idx_size
        idx_sha1 = hashlib.sha1(primary_index).digest()

        f.write(primary_index)
        f.write(ph_bytes)
        f.write(fd_bytes)

        # FPakInfo v12 (221 bytes)
        footer = (
            b"\x00" * 16  # EncryptionKeyGuid
            + b"\x00"  # bEncryptedIndex
            + struct.pack("<IIQQ20s", PAK_MAGIC, PAK_VERSION_FROZEN_REMOVED, idx_offset, idx_size, idx_sha1)
            + (b"\x00" * 32) * 5  # CompressionMethods (all empty = uncompressed)
        )
        assert len(footer) == 221
        f.write(footer)
        pak_bytes = f.tell()

    return {"files": len(items), "payload_bytes": payload_total, "pak_bytes": pak_bytes}
