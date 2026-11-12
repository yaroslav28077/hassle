"""Фаза 2. Разведка установки HASSLE 2.0. Только чтение заголовков, ничего не меняет и не расшифровывает.

python tools/check_target.py                     # путь игры из config.yaml
python tools/check_target.py --game "D:/Games/HASSLE" --mods "D:/Downloads/some_hassle_build"

Что определяет:
- имя UE-проекта игры (папка, где лежит Content/Paks);
- версию движка (строка ++UE4/5+Release-X.Y в exe);
- формат контента: .pak (версия, зашифрован ли индекс) и/или IoStore .utoc/.ucas (флаги Encrypted/Signed);
- наличие .sig (подпись паков) и античита;
- как устроены сторонние сборки (если передан --mods): какие файлы и куда кладутся.
Отчёт: game_ref/target_report.md и game_ref/target_report.json
"""
from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path

from common import ROOT, get_logger, load_config

PAK_MAGIC = struct.pack("<I", 0x5A6F12E1)
UTOC_MAGIC = b"-==--==--==--==-"
UTOC_FLAGS = {1: "Compressed", 2: "Encrypted", 4: "Signed", 8: "Indexed", 16: "OnDemand"}
ANTICHEAT_HINTS = ["EasyAntiCheat", "BattlEye", "BEService", "EAC", "anticheat", "AntiCheat", "xigncode", "GameGuard"]


def pak_info(p: Path) -> dict:
    size = p.stat().st_size
    with open(p, "rb") as f:
        f.seek(max(0, size - 1024))
        tail = f.read()
    i = tail.rfind(PAK_MAGIC)
    if i < 17:
        return {"file": p.name, "error": "не найден footer pak (возможно, не стандартный формат)"}
    version, = struct.unpack_from("<I", tail, i + 4)
    enc_index = tail[i - 1]
    guid = tail[i - 17: i - 1]
    return {"file": p.name, "size_mb": round(size / 2**20, 1), "pak_version": version,
            "encrypted_index": bool(enc_index), "encryption_key_guid_set": any(guid)}


def utoc_info(p: Path) -> dict:
    with open(p, "rb") as f:
        h = f.read(96)
    if h[:16] != UTOC_MAGIC:
        return {"file": p.name, "error": "не найдена сигнатура utoc"}
    flags = h[80]
    return {"file": p.name, "toc_version": h[16], "entries": struct.unpack_from("<I", h, 24)[0],
            "flags": [n for b, n in UTOC_FLAGS.items() if flags & b],
            "encrypted": bool(flags & 2), "signed": bool(flags & 4)}


def ue_version_from_pe(exe: Path) -> str | None:
    """Fallback для UE-сборок из исходников (UE5-CL-0): читает VS_FIXEDFILEINFO из ресурсов PE."""
    data = exe.read_bytes()
    marker = b"\xbd\x04\xef\xfe"  # VS_FIXEDFILEINFO signature 0xFEEF04BD
    off = data.find(marker)
    if off < 0 or off + 16 > len(data):
        return None
    _, _, ms, ls = struct.unpack_from("<IIII", data, off)
    major, minor, build, rev = ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF
    if major in (4, 5) and minor < 100:
        return f"UE{major} {major}.{minor}.{build}.{rev} (из PE FileVersion)"
    return None


def ue_version_from_exe(exe: Path) -> str | None:
    pat = re.compile(rb"\+\+UE[45]\+Release-\d+\.\d+")
    wpat = re.compile(re.escape("++UE".encode("utf-16-le")) + rb"[45]\x00\+\x00R\x00e\x00l\x00e\x00a\x00s\x00e\x00-\x00(?:\d\x00)+\.\x00(?:\d\x00)+")
    tail = b""
    with open(exe, "rb") as f:
        while chunk := f.read(8 * 2**20):
            buf = tail + chunk
            if m := pat.search(buf):
                return m.group().decode()
            if m := wpat.search(buf):
                return m.group().decode("utf-16-le")
            tail = buf[-128:]
    # fix: fallback на PE FileVersion для сборок UE из исходников (UE5-CL-0)
    return ue_version_from_pe(exe)


def scan_mod_build(mods: Path) -> list[dict]:
    out = []
    for p in sorted(mods.rglob("*")):
        if p.is_file():
            item = {"path": p.relative_to(mods).as_posix(), "size_kb": round(p.stat().st_size / 1024, 1)}
            if p.suffix.lower() == ".pak":
                item.update(pak_info(p))
            elif p.suffix.lower() == ".utoc":
                item.update(utoc_info(p))
            out.append(item)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game")
    ap.add_argument("--mods", help="папка со сторонней сборкой HASSLE (только для изучения формата)")
    a = ap.parse_args()
    log = get_logger("check_target")
    cfg = {} if a.game else load_config()
    game = Path(a.game or cfg.get("game", {}).get("install_dir", ""))
    if not game.is_dir():
        raise SystemExit(f"Папка игры не найдена: {game}")

    paks_dirs = [p for p in game.rglob("Paks") if p.is_dir() and p.parent.name == "Content"]
    project = paks_dirs[0].parent.parent.name if paks_dirs else None
    exes = sorted(game.rglob("*-Win64-Shipping.exe")) or sorted(game.rglob("*.exe"))
    ue_ver = None
    for exe in exes[:5]:
        if ue_ver := ue_version_from_exe(exe):
            break

    paks, utocs, sigs = [], [], []
    for d in paks_dirs:
        paks += [pak_info(p) for p in sorted(d.rglob("*.pak"))]
        utocs += [utoc_info(p) for p in sorted(d.rglob("*.utoc"))]
        sigs += [p.name for p in d.rglob("*.sig")]
    names = [p.name.lower() for p in game.rglob("*")]
    anticheat = sorted({h for h in ANTICHEAT_HINTS if any(h.lower() in n for n in names)})
    mods_subdirs = [str(p.relative_to(game)) for d in paks_dirs for p in d.iterdir() if p.is_dir()]

    encrypted = any(x.get("encrypted_index") for x in paks) or any(x.get("encrypted") for x in utocs)
    signed = bool(sigs) or any(x.get("signed") for x in utocs)
    report = {"game_dir": str(game), "project_name": project, "ue_version": ue_ver,
              "exe_candidates": [e.name for e in exes[:5]], "paks_dirs": [str(d) for d in paks_dirs],
              "paks_subfolders": mods_subdirs, "pak_files": paks, "utoc_files": utocs,
              "sig_files": sigs[:20], "anticheat_hints": anticheat,
              "content_encrypted": encrypted, "content_signed": signed}
    if a.mods:
        report["reference_build"] = scan_mod_build(Path(a.mods))

    out = ROOT / "game_ref"
    out.mkdir(exist_ok=True)
    (out / "target_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    verdict = ("🔴 Контент зашифрован или подписан. Путь подмены паков закрыт: остановиться и обсудить с пользователем."
               if encrypted or signed else
               "🟢 Шифрование и подпись не обнаружены. Подмена через пак с приоритетом `_P` технически возможна.")
    md = ["# HASSLE 2.0: разведка установки", "", f"**Вердикт:** {verdict}", "",
          f"- Папка игры: `{game}`", f"- Имя UE-проекта: `{project}`", f"- Версия движка: `{ue_ver or 'не найдена'}`",
          f"- Папки Paks: {', '.join(f'`{d}`' for d in report['paks_dirs']) or 'нет'}",
          f"- Подпапки в Paks (возможно ~mods): {', '.join(mods_subdirs) or 'нет'}",
          f"- .pak: {len(paks)}, .utoc: {len(utocs)}, .sig: {len(sigs)}",
          f"- Признаки античита: {', '.join(anticheat) or 'не найдены'}", "",
          "## .pak", "", "| файл | МБ | версия | индекс зашифрован |", "|---|---:|---:|---|"]
    md += [f"| {p['file']} | {p.get('size_mb', '')} | {p.get('pak_version', '')} | {p.get('encrypted_index', p.get('error'))} |" for p in paks[:40]]
    md += ["", "## IoStore (.utoc)", "", "| файл | флаги |", "|---|---|"]
    md += [f"| {u['file']} | {', '.join(u.get('flags', [])) or u.get('error', '')} |" for u in utocs[:40]]
    if a.mods:
        md += ["", "## Сторонняя сборка (формат установки)", ""]
        md += [f"- `{x['path']}` ({x['size_kb']} КБ)" for x in report["reference_build"][:80]]
    (out / "target_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log.info("Проект: %s, UE: %s, encrypted=%s, signed=%s", project, ue_ver, encrypted, signed)
    log.info("Отчёт: %s", out / "target_report.md")


if __name__ == "__main__":
    main()
