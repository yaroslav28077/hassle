"""Фаза 0. Проверка окружения: пути из config.yaml, инструменты, Python-пакеты.

python tools/env_check.py
"""
from __future__ import annotations

import importlib
import shutil
import subprocess
from pathlib import Path

from common import ROOT, load_config, source_dir


def ok(flag: bool, text: str) -> bool:
    print(("  [OK]   " if flag else "  [FAIL] ") + text)
    return flag


def main() -> None:
    cfg = load_config()
    good = True
    print("Python-пакеты:")
    for mod in ("PIL", "yaml"):
        try:
            importlib.import_module(mod)
            ok(True, mod)
        except ImportError:
            good &= ok(False, f"{mod} (pip install -r requirements.txt)")

    print("Папки:")
    src = source_dir()
    good &= ok(src.is_dir() and any(src.iterdir()), f"папка сборки ONEAS: {src}")
    rd = (cfg.get("source") or {}).get("radmir_dir")
    if rd:
        ok(Path(rd).is_dir(), f"Radmir RP (для сравнения): {rd}")
    game = Path(cfg.get("game", {}).get("install_dir", ""))
    good &= ok(game.is_dir(), f"папка игры: {game}")

    print("Инструменты:")
    tools = cfg.get("tools", {})
    ff = tools.get("ffmpeg") or shutil.which("ffmpeg")
    good &= ok(bool(ff) and (Path(ff).exists() or shutil.which(ff)), f"ffmpeg: {ff}")
    bl = tools.get("blender")
    good &= ok(bool(bl) and Path(bl).exists(), f"blender: {bl}")
    if bl and Path(bl).exists():
        r = subprocess.run([bl, "-b", "--python-expr",
                            "import bpy,sys; print('DRAGONFF', hasattr(bpy.ops.import_scene,'dff'))"],
                           capture_output=True, text=True, timeout=180)
        good &= ok("DRAGONFF True" in r.stdout, "аддон DragonFF включён в Blender")

    ue = cfg.get("ue", {})
    engine = Path(ue.get("engine_dir", ""))
    major = int(ue.get("engine_major", 5))
    editor = engine / "Engine/Binaries/Win64" / ("UnrealEditor-Cmd.exe" if major >= 5 else "UE4Editor-Cmd.exe")
    good &= ok(editor.exists(), f"Unreal Editor: {editor}")
    good &= ok((engine / "Engine/Binaries/Win64/UnrealPak.exe").exists(), "UnrealPak.exe")
    up = Path(ue.get("mod_project", ""))
    proj_ok = up.exists()
    ok(proj_ok, f"UE-проект мода: {up} (можно создать на фазе 5)")
    gp = cfg.get("game", {}).get("project_name")
    if proj_ok and gp:
        good &= ok(up.stem == gp, f"имя проекта мода совпадает с проектом игры ({gp})")

    print("\nИтог:", "всё готово" if good else "есть проблемы, см. [FAIL]")


if __name__ == "__main__":
    main()
