"""Фаза 1. Инвентаризация сборки Radmir: что лежит в source/ и как каждый тип переносить.

python tools/inventory.py --src source --out work/inventory
"""
from __future__ import annotations

import argparse
import csv
import struct
from collections import Counter, defaultdict
from pathlib import Path

from common import ROOT, get_logger, rw_header, rw_version_str, source_dir

CATEGORIES = {
    "texture_dict": {".txd"},
    "model": {".dff"},
    "collision": {".col"},
    "animation": {".ifp"},
    "archive": {".img", ".dir", ".zip", ".rar", ".7z"},
    "map_def": {".ide", ".ipl"},
    "image": {".png", ".jpg", ".jpeg", ".bmp", ".tga", ".dds", ".webp", ".svg", ".gif"},
    "audio": {".wav", ".mp3", ".ogg", ".flac", ".m4a"},
    "font": {".ttf", ".otf", ".fnt", ".woff", ".woff2"},
    "ui_web": {".html", ".htm", ".css", ".js"},
    "config": {".ini", ".cfg", ".dat", ".txt", ".xml", ".yaml", ".yml", ".json", ".toml"},
    "code_plugin": {".asi", ".dll", ".cs", ".lua", ".luac", ".sf", ".exe", ".cleo"},
    "game_text": {".gxt", ".fxt"},
    "video": {".mp4", ".webm", ".bik", ".avi"},
}
EXT2CAT = {e: c for c, exts in CATEGORIES.items() for e in exts}

STRATEGY = {
    "texture_dict": "tools/txd_extract.py → PNG → подмена текстур UE (convert-textures)",
    "model": "Blender + DragonFF → FBX → импорт в UE на путь оригинала (convert-models)",
    "collision": "skip: в UE используется коллизия оригинального ассета",
    "animation": "skip по умолчанию: анимации GTA несовместимы со скелетами HASSLE",
    "archive": "распаковать (tools/img_extract.py для .img, 7-Zip для остального) и повторить инвентарь",
    "map_def": "skip: карты GTA не переносятся",
    "image": "напрямую как текстуры UI/HUD (rebuild-ui / convert-textures)",
    "audio": "tools/audio_convert.py → WAV 48k → подмена SoundWave (convert-audio)",
    "font": "перенос только при лицензии на встраивание",
    "ui_web": "источник картинок и раскладки для rebuild-ui, код не переносится",
    "config": "читать вручную: может описывать варианты сборки (Basic/Maximum)",
    "code_plugin": "skip: код не переносится (при необходимости описать, что делал плагин)",
    "game_text": "skip, либо ручной перенос текстов",
    "video": "по ситуации: заставки/фоны → MediaSource, обычно skip",
    "other": "разобрать вручную",
}


def sniff(path: Path) -> tuple[str, str]:
    """Определить формат по сигнатуре: (detected, details)."""
    try:
        with open(path, "rb") as f:
            head = f.read(64)
    except OSError as e:
        return "unreadable", str(e)
    if head[:4] == b"VER2":
        n = struct.unpack_from("<I", head, 4)[0]
        return "img_v2", f"{n} entries"
    if len(head) >= 12:
        t, size, stamp = rw_header(head)
        if t in (0x16, 0x10) and size <= path.stat().st_size:
            kind = "rw_txd" if t == 0x16 else "rw_dff"
            return kind, rw_version_str(stamp)
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png", ""
    if head[:4] == b"DDS ":
        return "dds", ""
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav", ""
    if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3"):
        return "mp3", ""
    if head[:4] == b"OggS":
        return "ogg", ""
    if head[:2] == b"MZ":
        return "pe_binary", "исполняемый код"
    if head[:4] in (b"COLL", b"COL2", b"COL3", b"COL4"):
        return "gta_col", head[:4].decode()
    return "", ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=None, help="по умолчанию source.build_dir из config.yaml")
    ap.add_argument("--out", default=str(ROOT / "work" / "inventory"))
    a = ap.parse_args()
    log = get_logger("inventory")

    src, out = Path(a.src) if a.src else source_dir(), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in sorted(src.rglob("*")):
        if not p.is_file() or (p.parent == src and p.name == "README.txt"):
            continue
        ext = p.suffix.lower()
        cat = EXT2CAT.get(ext, "other")
        detected, details = sniff(p)
        if detected == "img_v2":
            cat = "archive"
        rows.append({
            "path": p.relative_to(src).as_posix(),
            "top_folder": p.relative_to(src).parts[0] if len(p.relative_to(src).parts) > 1 else "",
            "ext": ext, "category": cat, "size_kb": round(p.stat().st_size / 1024, 1),
            "detected": detected, "details": details,
        })

    with open(out / "inventory.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["path"])
        w.writeheader()
        w.writerows(rows)

    by_cat = Counter(r["category"] for r in rows)
    size_cat = defaultdict(float)
    for r in rows:
        size_cat[r["category"]] += r["size_kb"]
    by_folder = Counter(r["top_folder"] or "(корень)" for r in rows)
    mismatches = [r for r in rows if r["ext"] in (".txd", ".dff") and not r["detected"].startswith("rw_")]
    rw_versions = Counter(r["details"] for r in rows if r["detected"].startswith("rw_"))

    lines = ["# Инвентарь сборки", "", f"Всего файлов: **{len(rows)}**", "",
             "| Категория | Файлов | МБ | Как переносим |", "|---|---:|---:|---|"]
    for cat, n in by_cat.most_common():
        lines.append(f"| {cat} | {n} | {size_cat[cat] / 1024:.1f} | {STRATEGY.get(cat, '')} |")
    lines += ["", "## Верхние папки (части сборки)", ""]
    lines += [f"- `{k}`: {v}" for k, v in by_folder.most_common()]
    if rw_versions:
        lines += ["", "## Версии RenderWare", ""] + [f"- {k}: {v}" for k, v in rw_versions.most_common()]
    if mismatches:
        lines += ["", "## Внимание: расширение не совпадает с содержимым", ""]
        lines += [f"- `{r['path']}` ({r['detected'] or 'неизвестно'})" for r in mismatches[:50]]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Файлов: %d. Категории: %s", len(rows), dict(by_cat))
    log.info("Отчёт: %s", out / "summary.md")


if __name__ == "__main__":
    main()
