"""Генератор пустого IoStore-контейнера UE 5.8 (.utoc 240 Б + .ucas 64 Б).

Создаётся по спецификации пустых UI-контейнеров (образец структуры — pakchunk166..181 HASSLE 2.0),
без копирования файлов игры, с уникальным стабильным ContainerId для каждого мод-пака
и корректным BLAKE3-160 хэшем FIoChunkHash в FIoStoreTocEntryMeta.
"""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

UTOC_MAGIC = b"-==--==--==--==-"
UTOC_VERSION_LATEST = 8
UTOC_HEADER_SIZE = 144

UCAS_CONTAINER_HEADER_SIG = b"nCoI"  # FIoContainerHeader::Signature ('IoCn' LE)
UCAS_CONTAINER_HEADER_VER = 5

_BLAKE3_IV = (
    0x6A09E667,
    0xBB67AE85,
    0x3C6EF372,
    0xA54FF53A,
    0x510E527F,
    0x9B05688C,
    0x1F83D9AB,
    0x5BE0CD19,
)
_BLAKE3_MSG_PERM = (2, 6, 3, 10, 7, 0, 4, 13, 1, 11, 12, 5, 9, 14, 15, 8)
_BLAKE3_CHUNK_START = 1 << 0
_BLAKE3_CHUNK_END = 1 << 1
_BLAKE3_ROOT = 1 << 3


def _rotr32(x: int, n: int) -> int:
    return ((x >> n) | (x << (32 - n))) & 0xFFFFFFFF


def _b3_g(state: list[int], a: int, b: int, c: int, d: int, mx: int, my: int) -> None:
    state[a] = (state[a] + state[b] + mx) & 0xFFFFFFFF
    state[d] = _rotr32(state[d] ^ state[a], 16)
    state[c] = (state[c] + state[d]) & 0xFFFFFFFF
    state[b] = _rotr32(state[b] ^ state[c], 12)
    state[a] = (state[a] + state[b] + my) & 0xFFFFFFFF
    state[d] = _rotr32(state[d] ^ state[a], 8)
    state[c] = (state[c] + state[d]) & 0xFFFFFFFF
    state[b] = _rotr32(state[b] ^ state[c], 7)


def _b3_compress(cv: list[int], block_words: tuple[int, ...], counter: int, block_len: int, flags: int) -> list[int]:
    s = list(cv) + list(_BLAKE3_IV[:4]) + [counter & 0xFFFFFFFF, (counter >> 32) & 0xFFFFFFFF, block_len, flags]
    m = list(block_words)
    for _ in range(7):
        _b3_g(s, 0, 4, 8, 12, m[0], m[1])
        _b3_g(s, 1, 5, 9, 13, m[2], m[3])
        _b3_g(s, 2, 6, 10, 14, m[4], m[5])
        _b3_g(s, 3, 7, 11, 15, m[6], m[7])
        _b3_g(s, 0, 5, 10, 15, m[8], m[9])
        _b3_g(s, 1, 6, 11, 12, m[10], m[11])
        _b3_g(s, 2, 7, 8, 13, m[12], m[13])
        _b3_g(s, 3, 4, 9, 14, m[14], m[15])
        m = [m[i] for i in _BLAKE3_MSG_PERM]
    for i in range(8):
        s[i] ^= s[i + 8]
        s[i + 8] ^= cv[i]
    return s


def blake3_hash256(data: bytes) -> bytes:
    """BLAKE3-256 для одного блока <= 64 байт (используется в FIoChunkHash[:20])."""
    if len(data) > 64:
        raise ValueError("Пустой IoStore-хедер должен быть <= 64 байт")
    padded = data + b"\x00" * (64 - len(data))
    words = struct.unpack("<16I", padded)
    out = _b3_compress(list(_BLAKE3_IV), words, 0, len(data), _BLAKE3_CHUNK_START | _BLAKE3_CHUNK_END | _BLAKE3_ROOT)
    return struct.pack("<8I", *out[:8])


def container_id_from_name(pak_stem: str) -> int:
    """Стабильный уникальный uint64 ContainerId по имени мод-пака (никогда не 0)."""
    digest = hashlib.sha256(f"oneas_iostore:{pak_stem.lower()}".encode("utf-8")).digest()
    cid = int.from_bytes(digest[:8], "little")
    return cid if cid != 0 else 1


def build_empty_iostore_bytes(container_id: int) -> tuple[bytes, bytes]:
    """Собрать пару байтовых буферов (utoc 240 Б, ucas 64 Б) для пустого контейнера."""
    if not (0 < container_id <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError(f"Некорректный ContainerId: {container_id}")

    # 1. .ucas (64 байта): FIoContainerHeader v5 (0 пакетов)
    ucas = (
        struct.pack("<4sIQ", UCAS_CONTAINER_HEADER_SIG, UCAS_CONTAINER_HEADER_VER, container_id)
        + b"\x00" * 28  # пустые поля/счётчики FIoContainerHeader (0 пакетов)
        + struct.pack("<IIIII", 0x3C, 0, 4, 0, 0)  # Redirects/SoftPackageReferences (пустой 64-байтный блок)
    )
    assert len(ucas) == 64

    # 2. .utoc header (144 байта): FIoStoreTocHeader v8
    dir_index = struct.pack("<I2sIiiiiII", 2, b"/\x00", 1, -1, -1, -1, -1, 0, 0)
    assert len(dir_index) == 34

    utoc_header = (
        UTOC_MAGIC
        + struct.pack(
            "<10IQ16sIIQ48s",
            UTOC_VERSION_LATEST,  # Version = 8
            UTOC_HEADER_SIZE,     # TocHeaderSize = 144
            1,                    # TocEntryCount = 1 (только ContainerHeader)
            1,                    # TocCompressedBlockEntryCount = 1
            12,                   # TocCompressedBlockEntrySize = 12
            0,                    # CompressionMethodNameCount = 0
            32,                   # CompressionMethodNameLength = 32
            65536,                # CompressionBlockSize = 65536
            len(dir_index),       # DirectoryIndexSize = 34
            1,                    # PartitionCount = 1
            container_id,         # ContainerId (uint64)
            b"\x00" * 16,         # EncryptionKeyGuid
            8,                    # ContainerFlags = Indexed (0x08)
            1,                    # ChunkPerfectHashSeedsCount = 1
            0xFFFFFFFFFFFFFFFF,   # PartitionSize = MAX_uint64
            b"\x00" * 48,         # Padding / Reserved до 144 Б
        )
    )
    assert len(utoc_header) == UTOC_HEADER_SIZE

    # 3. TOC тела (96 байт):
    # - FIoChunkId (12 Б): ContainerId + 3B zero index + EIoChunkType::ContainerHeader(6)
    chunk_id = struct.pack("<Q4s", container_id, b"\x00\x00\x00\x06")
    # - FIoOffsetAndLength (10 Б): offset=0 (5B BE), length=64 (5B BE)
    offset_and_length = b"\x00" * 9 + b"\x40"
    # - ChunkPerfectHashSeeds (4 Б): -1 (без хеш-бакета)
    perfect_hash_seed = struct.pack("<i", -1)
    # - FIoStoreTocCompressedBlockEntry (12 Б): offset=0 (5B), comp_sz=64 (3B LE), uncomp_sz=64 (3B LE), method=0
    compressed_block = b"\x00" * 5 + b"\x40\x00\x00" + b"\x40\x00\x00" + b"\x00"
    # - FIoStoreTocEntryMeta (24 Б): BLAKE3-160 от 64-байтного FIoContainerHeader в .ucas + Flags(0)
    chunk_hash = blake3_hash256(ucas)[:20]
    chunk_meta = chunk_hash + struct.pack("<I", 0)

    utoc = utoc_header + chunk_id + offset_and_length + perfect_hash_seed + compressed_block + dir_index + chunk_meta
    assert len(utoc) == 240
    return utoc, ucas


def build_empty_iostore(pak_or_base: Path, container_id: int | None = None) -> dict[str, int | str]:
    """Записать <stem>.utoc (240 Б) и <stem>.ucas (64 Б) рядом с .pak."""
    base = pak_or_base.with_suffix("")
    cid = container_id if container_id is not None else container_id_from_name(base.name)
    utoc_bytes, ucas_bytes = build_empty_iostore_bytes(cid)
    base.parent.mkdir(parents=True, exist_ok=True)
    utoc_path = base.with_suffix(".utoc")
    ucas_path = base.with_suffix(".ucas")
    utoc_path.write_bytes(utoc_bytes)
    ucas_path.write_bytes(ucas_bytes)
    return {
        "container_id": f"0x{cid:016x}",
        "utoc_bytes": len(utoc_bytes),
        "ucas_bytes": len(ucas_bytes),
    }
