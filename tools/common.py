"""Общие утилиты конвейера: конфиг, логи, RenderWare-заголовки."""
from __future__ import annotations

import datetime as _dt
import logging
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path | None = None) -> dict:
    import yaml  # pyyaml

    path = path or ROOT / "config.yaml"
    if not path.exists():
        sys.exit(f"Нет {path}. Скопируй config.example.yaml в config.yaml и заполни пути.")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_logger(step: str) -> logging.Logger:
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    stamp = _dt.datetime.now().astimezone().strftime("%Y%m%d_%H%M")
    logger = logging.getLogger(step)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
        fh = logging.FileHandler(logs / f"{stamp}_{step}.log", encoding="utf-8")
        fh.setFormatter(fmt)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(sh)
    return logger


def source_dir() -> Path:
    """Папка сборки: source.build_dir из config.yaml или ./source."""
    try:
        d = (load_config().get("source") or {}).get("build_dir")
    except SystemExit:
        d = None
    return Path(d) if d else ROOT / "source"


# ---------------- RenderWare ----------------
RW_STRUCT = 0x01
RW_STRING = 0x02
RW_EXTENSION = 0x03
RW_TEXTURE_NATIVE = 0x15
RW_TEX_DICTIONARY = 0x16
RW_CLUMP = 0x10

RW_GAMES = {
    0x31001: "GTA III", 0x33002: "GTA III/VC", 0x34003: "GTA VC",
    0x35000: "GTA VC (PS2)", 0x36003: "GTA SA",
}


def rw_header(data: bytes, off: int = 0) -> tuple[int, int, int]:
    """(type, size, library_stamp) чанка RenderWare."""
    return struct.unpack_from("<III", data, off)


def rw_version(stamp: int) -> int:
    """Library stamp → версия вида 0x36003."""
    if stamp & 0xFFFF0000:
        return ((stamp >> 14) & 0x3FF00) + 0x30000 | ((stamp >> 16) & 0x3F)
    return stamp << 8


def rw_version_str(stamp: int) -> str:
    v = rw_version(stamp)
    s = f"{(v >> 16) & 0xF}.{(v >> 12) & 0xF}.{(v >> 8) & 0xF}.{v & 0xFF}"
    game = RW_GAMES.get(v)
    return f"{s} ({game})" if game else s
