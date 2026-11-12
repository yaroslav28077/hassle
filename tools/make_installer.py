"""Фаза 7. Релиз: out/release/<mod>_<версия>/ + zip.

python tools/make_installer.py

v6: один пак (все варианты внутри, переключение в игре через «Настройки ONEAS»), поэтому
установщик без выбора модулей. install.bat:
- сам ищет папку игры (путь из config + стандартные пути), иначе спрашивает;
- просит права администратора, если игра в Program Files;
- не ставит мод при запущенной игре;
- сверяет manifest.json лаунчера с update_guard.txt (не обновилась ли игра после сборки мода);
- бэкапит совпадающие файлы, убирает паки старых версий мода и кладёт zzz_OneasPort_P.pak/.utoc/.ucas в ~mods.
uninstall.bat удаляет все zzz_OneasPort* и возвращает бэкап. Файлов игры в релизе нет.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

from common import ROOT, get_logger, load_config

FIND_GAME = r"""set "GAME="
for %%G in ("{game}" "C:\Program Files (x86)\HASSLE GAMES\Hassle Online" "C:\Program Files\HASSLE GAMES\Hassle Online" "D:\HASSLE GAMES\Hassle Online" "D:\Games\HASSLE GAMES\Hassle Online") do (
  if not defined GAME if exist "%%~G\{project}\Content\Paks\" set "GAME=%%~G"
)
if not defined GAME (
  echo Папка HASSLE 2.0 не найдена автоматически.
  set /p "GAME=Вставьте путь к папке игры (где лежит папка {project}): "
)
set "GAME=%GAME:"=%"
if not exist "%GAME%\{project}\Content\Paks\" (
  echo [ОШИБКА] Не найдена папка "%GAME%\{project}\Content\Paks". Проверьте путь.
  pause & exit /b 1
)
echo Игра: %GAME%
"""

ELEVATE = r"""net session >nul 2>&1
if errorlevel 1 (
  echo Нужны права администратора для записи в папку игры. Сейчас появится запрос Windows...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
"""

INSTALL = r"""@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title ONEAS -> HASSLE {version}: установка
if not exist "%~dp0paks\{mod}_P.pak" (
  echo [ОШИБКА] Рядом с install.bat нет папки paks. Сначала распакуйте архив целиком, потом запускайте install.bat.
  pause & exit /b 1
)
""" + ELEVATE + FIND_GAME + r"""
tasklist /FI "IMAGENAME eq {exe}" 2>nul | find /I "{exe}" >nul
if not errorlevel 1 (
  echo [СТОП] Игра запущена. Закройте HASSLE и запустите install.bat ещё раз.
  pause & exit /b 1
)

set "MANIFEST=%GAME%\manifest.json"
if not exist "%MANIFEST%" (
  echo manifest.json лаунчера не найден, проверка обновлений пропущена.
  goto :copy
)
powershell -NoProfile -Command "$m=Get-Content -Raw -LiteralPath $env:MANIFEST | ConvertFrom-Json; $h=@{{}}; foreach($f in $m.files){{$h[[IO.Path]::GetFileName($f.path)]=$f.hash}}; $bad=@(); foreach($l in Get-Content -LiteralPath '%~dp0update_guard.txt'){{ $p=$l.Split('='); if($p.Length -eq 2 -and $h[$p[0]] -ne $p[1]){{$bad+=$p[0]}} }}; Write-Output ('Сборка игры: '+$m.build+', мод собран для {game_build}'); if($bad.Count){{Write-Output ('Изменились паки интерфейса: '+($bad -join ', ')); exit 1}} else {{exit 0}}"
if not errorlevel 1 goto :copy
echo.
echo [ВНИМАНИЕ] После сборки мода игра обновила файлы интерфейса.
echo Мод может перекрыть новые файлы и сломать HUD. Лучше дождаться новой версии мода.
set "GO=n"
set /p "GO=Всё равно установить? [y/N]: "
if /i not "%GO%"=="y" exit /b 1

:copy
set "DEST=%GAME%\{project}\Content\Paks\{subdir}"
set "BACKUP=%GAME%\{project}\Content\Paks\_oneasport_backup"
mkdir "%DEST%" 2>nul
mkdir "%BACKUP%" 2>nul
rem паки прошлых версий мода (модульные v5 и др.) убираем, чтобы не конфликтовали
for %%F in ("%DEST%\{mod}_*_P.pak" "%DEST%\{mod}_*_P.utoc" "%DEST%\{mod}_*_P.ucas") do if exist "%%~F" del /q "%%~F"
for %%E in (pak utoc ucas) do (
  if exist "%DEST%\{mod}_P.%%E" copy /y "%DEST%\{mod}_P.%%E" "%BACKUP%\" >nul
  copy /y "%~dp0paks\{mod}_P.%%E" "%DEST%\" >nul
  if errorlevel 1 (
    echo [ОШИБКА] Не удалось скопировать {mod}_P.%%E в "%DEST%".
    pause & exit /b 1
  )
  echo + {mod}_P.%%E
)
echo.
echo Готово. Мод ONEAS {version} установлен в "%DEST%".
echo Настройки: в игре ESC -^> «Настройки ONEAS». Если HUD ведёт себя странно, включите там «Безопасный режим» или запустите uninstall.bat.
echo ВАЖНО: модификация файлов онлайн-игры выполняется на ваш страх и риск. Проверьте правила проекта HASSLE.
pause
"""

UNINSTALL = r"""@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title ONEAS -> HASSLE: удаление
""" + ELEVATE + FIND_GAME + r"""
set "DEST=%GAME%\{project}\Content\Paks\{subdir}"
set "BACKUP=%GAME%\{project}\Content\Paks\_oneasport_backup"
for %%F in ("%DEST%\{mod}*.pak" "%DEST%\{mod}*.utoc" "%DEST%\{mod}*.ucas" "%DEST%\{mod}*.sig") do (
  if exist "%%~F" (
    del /q "%%~F" 2>nul
    echo - удалён %%~nxF
  )
)
if exist "%BACKUP%\" rmdir /s /q "%BACKUP%"
echo Мод удалён, игра вернулась к оригиналу.
pause
"""

README = """ONEAS STUDIO -> HASSLE 2.0, версия {version} ({today})
Собрано для сборки игры {game_build}.

УСТАНОВКА
1. Распакуйте архив целиком в любую папку.
2. Закройте игру и запустите install.bat (попросит права администратора, если игра в Program Files).
3. Установщик сам найдёт игру, проверит, не обновилась ли она, и положит мод в {project}\\Content\\Paks\\{subdir}.

НАСТРОЙКИ В ИГРЕ
ESC -> «Настройки ONEAS» (или маленькая шестерёнка в правом верхнем углу, когда виден курсор).
Можно переключать верхний HUD, радар и спидометр между вариантом ONEAS и родным HASSLE.
«Безопасный режим» выключает все правки мода без удаления.

ЕСЛИ ИГРА ОБНОВИЛАСЬ
Если после обновления HASSLE интерфейс выглядит сломанным: включите «Безопасный режим» или запустите uninstall.bat
и дождитесь новой версии мода.

УДАЛЕНИЕ
uninstall.bat удаляет все файлы мода.

Перенос выполнен с разрешения ONEAS STUDIO. Модификация файлов онлайн-игры выполняется на ваш страх и риск:
проверьте правила проекта HASSLE.
"""


def main() -> None:
    log = get_logger("make_installer")
    cfg = load_config()
    game = str(cfg["game"].get("install_dir", "")).replace("/", "\\")
    project = cfg["game"]["project_name"]
    subdir = cfg["game"].get("mods_subdir", "~mods")
    mod = cfg.get("mod", {}).get("pak_name", "zzz_OneasPort")
    version = cfg.get("mod", {}).get("version", "0.1.0")
    exe = f"{project}-Win64-Shipping.exe"

    out_dir = ROOT / "out"
    paks = [out_dir / f"{mod}_P{ext}" for ext in (".pak", ".utoc", ".ucas")]
    missing = [p.name for p in paks if not p.is_file()]
    if missing:
        raise SystemExit(f"Нет файлов {missing}. Сначала: python tools/build_mod.py --single-pak")

    guard_path = out_dir / "update_guard.json"
    guard = json.loads(guard_path.read_text(encoding="utf-8")) if guard_path.is_file() else {"files": [], "game_build": "?"}
    guard_lines = sorted({f"{f['pak']}={f['pak_md5']}" for f in guard["files"] if f.get("pak") and f.get("pak_md5")})

    rel = out_dir / "release" / f"{mod}_{version}"
    if rel.exists():
        shutil.rmtree(rel)
    (rel / "paks").mkdir(parents=True)
    for p in paks:
        shutil.copy(p, rel / "paks" / p.name)
    for extra in ("build_manifest.json", "configurator.html"):
        if (out_dir / extra).is_file():
            shutil.copy(out_dir / extra, rel / extra)
    (rel / "update_guard.txt").write_text("\n".join(guard_lines) + "\n", encoding="utf-8")

    fmt = dict(game=game, project=project, subdir=subdir, mod=mod, version=version, exe=exe,
               game_build=guard.get("game_build") or "?")

    def bat(text: str) -> str:
        # одинарные фигурные скобки в PowerShell-строке записаны как {{ }}
        return text.format(**fmt)

    for name, tpl in (("install.bat", INSTALL), ("uninstall.bat", UNINSTALL)):
        (rel / name).write_text(bat(tpl).replace("\r\n", "\n"), encoding="utf-8", newline="\r\n")
    (rel / "README.txt").write_text(
        README.format(today=dt.date.today().isoformat(), **fmt), encoding="utf-8", newline="\r\n")
    changelog = ROOT / "CHANGELOG.md"
    if changelog.is_file():
        shutil.copy(changelog, rel / "CHANGELOG.md")
    zip_path = shutil.make_archive(str(rel), "zip", rel.parent, rel.name)
    log.info("Релиз: %s (%d байт)", zip_path, Path(zip_path).stat().st_size)


if __name__ == "__main__":
    main()
