"""Фаза 6. Cook + упаковка мода.

Режим pak (UE4 и UE5 без IoStore):
  python tools/pak_build.py cook        # cook проекта мода
  python tools/pak_build.py pak         # собрать out/<mod>_P.pak только из ассетов asset_map.csv
Режим iostore (UE5 с .utoc/.ucas):
  python tools/pak_build.py iostore-cmd      # напечатать команду BuildCookRun (ассеты мода в отдельном чанке)
  python tools/pak_build.py iostore-collect  # забрать pakchunk<ID>-Windows.* и переименовать в <mod>_P.*
Флаг --dry-run печатает команды, ничего не запуская.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
from pathlib import Path

from common import ROOT, get_logger, load_config

MAP = ROOT / "mapping" / "asset_map.csv"
PACK_STATUSES = {"imported", "packed", "verified"}
EXTS = (".uasset", ".uexp", ".ubulk", ".uptnl", ".umap")


def cfg_paths(cfg):
    ue = cfg["ue"]
    engine = Path(ue["engine_dir"])
    major = int(ue.get("engine_major", 5))
    uproject = Path(ue["mod_project"])
    platform = "Windows" if major >= 5 else "WindowsNoEditor"
    editor = engine / "Engine/Binaries/Win64" / ("UnrealEditor-Cmd.exe" if major >= 5 else "UE4Editor-Cmd.exe")
    unrealpak = engine / "Engine/Binaries/Win64/UnrealPak.exe"
    uat = engine / "Engine/Build/BatchFiles/RunUAT.bat"
    cooked = uproject.parent / "Saved/Cooked" / platform / uproject.stem / "Content"
    return engine, major, uproject, platform, editor, unrealpak, uat, cooked


def run(cmd, log, dry):
    log.info("> %s", " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd))
    if not dry:
        subprocess.run([str(c) for c in cmd], check=True)


def rows():
    with open(MAP, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_rows(data):
    shutil.copy(MAP, MAP.with_suffix(".csv.bak"))
    with open(MAP, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        w.writeheader()
        w.writerows(data)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["cook", "pak", "iostore-cmd", "iostore-collect"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    log = get_logger(f"pak_{a.step}")
    cfg = load_config()
    engine, major, uproject, platform, editor, unrealpak, uat, cooked = cfg_paths(cfg)
    game_project = cfg["game"]["project_name"]
    mod = cfg.get("mod", {}).get("pak_name", "zzz_OneasPort")
    out = ROOT / "out"
    out.mkdir(exist_ok=True)

    if a.step == "cook":
        extra = cfg["ue"].get("extra_cook_args", [])
        run([editor, uproject, "-run=cook", f"-targetplatform={platform}", "-iterate", *extra], log, a.dry_run)
        return

    if a.step == "pak":
        data = rows()
        resp, missing, packed = [], [], []
        for r in data:
            if r["status"] not in PACK_STATUSES or not r["target_package"]:
                continue
            rel = r["target_package"].split(".", 1)[0]
            if not rel.startswith("/Game/"):
                missing.append(f"{r['id']}: путь не начинается с /Game/")
                continue
            rel = rel[len("/Game/"):]
            found = [cooked / f"{rel}{e}" for e in EXTS if (cooked / f"{rel}{e}").exists()]
            if not found:
                missing.append(f"{r['id']}: нет cooked-файлов для {rel} (сначала cook)")
                continue
            for p in found:
                mount = f"../../../{game_project}/Content/{p.relative_to(cooked).as_posix()}"
                resp.append(f'"{p}" "{mount}"')
            packed.append(r)
        for m in missing:
            log.warning(m)
        if not resp:
            raise SystemExit("Нечего паковать: нет ассетов со статусом imported и cooked-файлами.")
        resp_file = out / f"{mod}_filelist.txt"
        resp_file.write_text("\n".join(resp) + "\n", encoding="utf-8")
        pak = out / f"{mod}_P.pak"
        run([unrealpak, pak, f"-create={resp_file}", "-compress"], log, a.dry_run)
        if not a.dry_run:
            for r in packed:
                r["status"] = "packed"
            write_rows(data)
        log.info("Ассетов в паке: %d, файлов: %d → %s", len(packed), len(resp), pak)
        return

    chunk = int(cfg.get("mod", {}).get("chunk_id", 100))
    if a.step == "iostore-cmd":
        cmd = [uat, "BuildCookRun", f"-project={uproject}", "-platform=Win64", "-clientconfig=Shipping",
               "-cook", "-stage", "-pak", "-iostore", "-nocompileeditor", "-skipbuild", "-nodebuginfo",
               f"-stagingdirectory={out / 'staging'}"]
        log.info("Перед запуском: в проекте мода Project Settings → Packaging → Generate Chunks = ON, "
                 "PrimaryAssetLabel с Chunk ID = %d на папки с ассетами мода (подробно: skill package-pak).", chunk)
        run(cmd, log, True)
        return

    if a.step == "iostore-collect":
        found = list((out / "staging").rglob(f"pakchunk{chunk}-*"))
        if not found:
            raise SystemExit(f"Не найден pakchunk{chunk}-* в out/staging. Проверь chunk_id и сборку.")
        for p in found:
            dst = out / f"{mod}_P{p.suffix}"
            shutil.copy(p, dst)
            log.info("%s → %s", p.name, dst.name)


if __name__ == "__main__":
    main()
