"""Защита от обновлений HASSLE 2.0: не перекроет ли наш мод новые версии файлов интерфейса.

Мод кладёт в пак ЦЕЛИКОМ пропатченные Hud.js / Hud.css / Authorization.css / PauseMenu.js.
Если игра обновила эти файлы, наша старая копия перекроет новую (пропадут фичи или сломается HUD).

    python tools/check_update.py            # вердикт по текущей установке игры
    python tools/check_update.py --record   # записать базу в out/update_guard.json (делает build_mod.py)
    python tools/check_update.py --json     # вывод для скриптов

Коды выхода: 0 — можно играть; 1 — нужна пересборка; 2 — проверить не удалось.
Только чтение папки игры.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import ROOT, load_config

GUARD = ROOT / "out" / "update_guard.json"
# Файлы, которые мы патчим (а не просто заменяем картинку).
PATCHED = [
    "HassleOnline/Content/UserInterface/Main/assets/Hud.js",
    "HassleOnline/Content/UserInterface/Main/assets/Hud.css",
    "HassleOnline/Content/UserInterface/Main/assets/Authorization.css",
    "HassleOnline/Content/UserInterface/Main/assets/PauseMenu.js",
]


def _cfg() -> dict:
    try:
        return load_config()
    except SystemExit:
        return {}


def game_dir(cfg: dict) -> Path:
    return Path((cfg.get("game") or {}).get("install_dir", ""))


def project(cfg: dict) -> str:
    return (cfg.get("game") or {}).get("project_name", "HassleOnline")


def load_launcher_manifest(cfg: dict, allow_ref: bool = False) -> tuple[dict | None, str]:
    """manifest.json лаунчера из папки игры. allow_ref: при записи базы можно взять копию из game_ref/."""
    gd = game_dir(cfg)
    cands = [gd / "manifest.json"] + ([ROOT / "game_ref" / "hassle_manifest.json"] if allow_ref else [])
    for p in cands:
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8")), str(p)
            except Exception:  # noqa: BLE001
                continue
    return None, ""


def pak_of(target: str) -> str | None:
    idx = ROOT / "game_ref" / "asset_paths_all.txt"
    if not idx.is_file():
        return None
    low = target.lower()
    for line in idx.read_text(encoding="utf-8").splitlines():
        p, _, pak = line.partition("\t")
        if p.lower() == low:
            return pak
    return None


def export_md5(target: str) -> str:
    name = target.rsplit("/", 1)[-1]
    for f in sorted((ROOT / "Exports").glob(f"*/Content/UserInterface/Main/assets/{name}")):
        return hashlib.md5(f.read_bytes()).hexdigest()
    return ""


def entry_info(cfg: dict, pak: str, target: str) -> dict:
    pak_path = game_dir(cfg) / project(cfg) / "Content" / "Paks" / pak
    if not pak_path.is_file():
        return {}
    from pak_index import read_entries  # noqa: PLC0415

    rec = read_entries(pak_path).get(target.lower()) or {}
    return {k: rec[k] for k in ("uncompressed_size", "size", "sha1") if k in rec}


def record(targets: list[str] | None = None) -> dict:
    cfg = _cfg()
    man, man_src = load_launcher_manifest(cfg, allow_ref=True)
    pak_md5 = {f["path"].rsplit("/", 1)[-1]: f.get("hash", "") for f in (man or {}).get("files", [])}
    files = []
    for t in targets or PATCHED:
        pak = pak_of(t)
        rec = {"target": t, "pak": pak, "pak_md5": pak_md5.get(pak or "", ""), "export_md5": export_md5(t)}
        if pak:
            try:
                rec.update(entry_info(cfg, pak, t))
            except Exception as e:  # noqa: BLE001
                rec["entry_error"] = str(e)
        files.append(rec)
    guard = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "game_build": (man or {}).get("build", ""),
        "manifest_source": man_src,
        "files": files,
    }
    GUARD.parent.mkdir(parents=True, exist_ok=True)
    GUARD.write_text(json.dumps(guard, ensure_ascii=False, indent=2), encoding="utf-8")
    return guard


def check() -> dict:
    cfg = _cfg()
    if not GUARD.is_file():
        return {"verdict": "unknown", "message": "Нет out/update_guard.json: соберите мод (build_mod.py) или запустите --record."}
    guard = json.loads(GUARD.read_text(encoding="utf-8"))
    man, man_src = load_launcher_manifest(cfg)
    if man is None:
        return {"verdict": "unknown", "message": "Не найден manifest.json лаунчера HASSLE в папке игры."}
    cur_md5 = {f["path"].rsplit("/", 1)[-1]: f.get("hash", "") for f in man.get("files", [])}
    changed, unknown = [], []
    for rec in guard.get("files", []):
        pak = rec.get("pak")
        if not pak:
            continue
        if rec.get("pak_md5") and cur_md5.get(pak) == rec["pak_md5"]:
            continue  # пак не менялся, значит файл тоже
        # пак изменился: смотрим сам файл по SHA-1 из индекса (без распаковки)
        try:
            now = entry_info(cfg, pak, rec["target"])
        except Exception as e:  # noqa: BLE001
            now = {"error": str(e)}
        if rec.get("sha1") and now.get("sha1"):
            if now["sha1"] != rec["sha1"] or now.get("uncompressed_size") != rec.get("uncompressed_size"):
                changed.append(rec["target"])
        elif not now:
            unknown.append(f"{rec['target']} (пак {pak} не найден)")
        else:
            # нет базы по файлу: считаем изменённым, раз изменился его пак
            changed.append(rec["target"])
    build_now, build_then = man.get("build", ""), guard.get("game_build", "")
    if changed:
        names = ", ".join(t.rsplit("/", 1)[-1] for t in changed)
        return {"verdict": "rebuild", "changed": changed, "game_build": build_now, "built_for": build_then,
                "message": f"Игра обновила файлы {names}: нужна пересборка мода (см. скилл update-rebuild)."}
    if unknown:
        return {"verdict": "unknown", "unknown": unknown, "game_build": build_now, "built_for": build_then,
                "message": "Не удалось проверить: " + "; ".join(unknown)}
    note = "" if build_now == build_then else f" (сборка игры {build_then} → {build_now}, файлы интерфейса не менялись)"
    return {"verdict": "ok", "game_build": build_now, "built_for": build_then, "message": "Можно играть" + note + "."}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.record:
        g = record()
        print(json.dumps(g, ensure_ascii=False, indent=2) if a.json else f"База записана: {GUARD} (сборка игры {g['game_build']})")
        return
    res = check()
    print(json.dumps(res, ensure_ascii=False, indent=2) if a.json else res["message"])
    sys.exit({"ok": 0, "rebuild": 1}.get(res["verdict"], 2))


if __name__ == "__main__":
    main()
