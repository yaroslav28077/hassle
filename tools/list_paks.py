"""Фаза 2б. Выгрузка списка файлов из незашифрованных .pak (UE4/UE5 v11-v12) через FullDirectoryIndex.

python tools/list_paks.py
python tools/list_paks.py --out game_ref/asset_paths_all.txt

Примечание: для IoStore (.utoc/.ucas) без UE/FModel список uasset не извлекается —
для них используйте FModel (UE 5.8).
"""
from __future__ import annotations

import argparse
import struct
from collections import Counter
from pathlib import Path

from common import ROOT, get_logger, load_config

PAK_MAGIC = struct.pack("<I", 0x5A6F12E1)


def read_fstring(buf: bytes, pos: int) -> tuple[str, int]:
    n, = struct.unpack_from("<i", buf, pos)
    pos += 4
    if n >= 0:
        s = buf[pos: pos + n].rstrip(b"\x00").decode("utf-8", errors="replace")
        return s, pos + n
    cnt = -n
    s = buf[pos: pos + cnt * 2].decode("utf-16-le", errors="replace").rstrip("\x00")
    return s, pos + cnt * 2


def norm_mount(mp: str) -> str:
    while mp.startswith("../"):
        mp = mp[3:]
    return mp.lstrip("/")


def read_pak_files(pak: Path) -> tuple[str, list[str], str | None]:
    """Вернуть (mount_point, [full_paths], error_or_none)."""
    with open(pak, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 1024))
        tail = f.read()
        i = tail.rfind(PAK_MAGIC)
        if i < 17:
            return "", [], "не найден footer pak"
        if tail[i - 1]:
            return "", [], "индекс зашифрован"
        ver, idx_off, idx_sz = struct.unpack_from("<IQQ", tail, i + 4)
        if ver < 8:
            return "", [], f"неподдерживаемая версия pak={ver}"
        f.seek(idx_off)
        idx = f.read(idx_sz)
        mp, pos = read_fstring(idx, 0)
        mp_clean = norm_mount(mp)
        num_entries, _seed, has_ph = struct.unpack_from("<IQi", idx, pos)
        pos += 16
        if has_ph:
            pos += 8 + 8 + 20
        has_fd, = struct.unpack_from("<i", idx, pos)
        pos += 4
        if not has_fd:
            return mp, [], None if num_entries == 0 else f"нет FullDirectoryIndex (entries={num_entries})"
        fd_off, fd_sz = struct.unpack_from("<qq", idx, pos)
        f.seek(fd_off)
        fd = f.read(fd_sz)
        dir_cnt, = struct.unpack_from("<i", fd, 0)
        fp = 4
        out: list[str] = []
        for _ in range(dir_cnt):
            dname, fp = read_fstring(fd, fp)
            if dname == "/":
                dname = ""
            file_cnt, = struct.unpack_from("<i", fd, fp)
            fp += 4
            for _ in range(file_cnt):
                fname, fp = read_fstring(fd, fp)
                fp += 4  # EncodedPakEntries offset
                rel = f"{dname}{fname}".lstrip("/")
                out.append(f"{mp_clean}{rel}" if mp_clean else rel)
        return mp, out, None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", help="путь к корню игры (по умолчанию из config.yaml)")
    ap.add_argument("--out", default=str(ROOT / "game_ref" / "asset_paths_all.txt"))
    a = ap.parse_args()
    log = get_logger("list_paks")

    cfg = {} if a.game else load_config()
    game = Path(a.game or cfg.get("game", {}).get("install_dir", ""))
    if not game.is_dir():
        raise SystemExit(f"Папка игры не найдена: {game}")

    paks_dirs = [p for p in game.rglob("Paks") if p.is_dir() and p.parent.name == "Content"]
    pak_files = sorted(p for d in paks_dirs for p in d.rglob("*.pak"))
    utoc_count = sum(len(list(d.rglob("*.utoc"))) for d in paks_dirs)

    entries: list[tuple[str, str]] = []
    errors = 0
    for pak in pak_files:
        try:
            _mp, paths, err = read_pak_files(pak)
            if err:
                log.warning("%s: %s", pak.name, err)
                errors += 1
                continue
            for p in paths:
                entries.append((p, pak.name))
        except Exception as e:  # noqa: BLE001
            log.error("%s: %s", pak.name, e)
            errors += 1

    entries.sort(key=lambda x: x[0].lower())
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(f"{p}\t{pak}" for p, pak in entries) + ("\n" if entries else ""), encoding="utf-8")

    ext_cnt = Counter(Path(p).suffix.lower() or "(no_ext)" for p, _ in entries)
    log.info("Просканировано .pak: %d (ошибок: %d), файлов в индексах: %d", len(pak_files), errors, len(entries))
    if utoc_count:
        log.info("Найдено .utoc (IoStore): %d — для просмотра uasset внутри них используйте FModel (UE 5.8)", utoc_count)
    log.info("Топ расширений: %s", ext_cnt.most_common(15))
    log.info("Список сохранён: %s", out)


if __name__ == "__main__":
    main()
