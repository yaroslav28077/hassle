"""Фаза 7. Собирает out/release/<mod>/ с install.bat, configure.bat, uninstall.bat и README.

python tools/make_installer.py

install.bat: читает build_manifest.json, даёт выбор «установить всё / выбрать модули»,
делает бэкап перезаписываемых файлов и копирует выбранные паки в <игра>/<Project>/Content/Paks/<mods_subdir>/.
configure.bat: открывает оффлайн-конфигуратор configurator.html для настройки build_options.yaml.
uninstall.bat: удаляет все паки мода ({mod}*.pak/.utoc/.ucas/.sig) и возвращает бэкап.
"""
# fix: поддержка модульных паков из out/build_manifest.json, выбор «всё / выбрать модули», configure.bat и полный uninstall.bat
from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

from common import ROOT, get_logger, load_config

INSTALL = r"""@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
if not exist "%~dp0paks\" (
  echo ОШИБКА: папка "paks" не найдена рядом с install.bat.
  echo Если вы открыли ZIP-архив без распаковки — сначала извлеките все файлы в любую папку и запустите install.bat оттуда.
  pause & exit /b 1
)
set "GAME={game}"
set /p "GAME=Папка HASSLE 2.0 [%GAME%]: "
set "DEST=!GAME!\{project}\Content\Paks\{subdir}"
set "BACKUP=!GAME!\{project}\Content\Paks\_oneasport_backup"
if exist "!GAME!\{project}\Content\Paks\" goto :paks_ok
echo Не найдена папка "!GAME!\{project}\Content\Paks". Проверьте путь к игре.
pause & exit /b 1

:paks_ok
mkdir "!DEST!" 2>nul
mkdir "!BACKUP!" 2>nul

echo.
echo === Модули мода в пакете ===
{module_list_echo}
echo.
echo [1] Установить ВСЕ доступные модули
echo [2] Выбрать модули по одному
set "MODE=1"
set /p "MODE=Режим установки [1]: "

if "%MODE%"=="2" goto :selective

for %%F in ("%~dp0paks\*.pak" "%~dp0paks\*.utoc" "%~dp0paks\*.ucas" "%~dp0paks\*.sig") do (
  if exist "%%F" (
    if exist "!DEST!\%%~nxF" copy /y "!DEST!\%%~nxF" "!BACKUP!\" >nul
    copy /y "%%F" "!DEST!\" >nul
    if errorlevel 1 (
      echo [ОШИБКА] Не удалось скопировать %%~nxF. Запустите install.bat от имени администратора!
      pause & exit /b 1
    )
    echo + %%~nxF
  )
)
goto :done

:selective
{selective_blocks}

:done
echo.
echo Готово. Выбранные модули установлены в "!DEST!"
echo ВАЖНО: модификация файлов онлайн-игры выполняется на ваш страх и риск. Проверьте правила проекта HASSLE.
pause
"""

CONFIGURE = r"""@echo off
chcp 65001 >nul
setlocal
echo Открытие оффлайн-конфигуратора configurator.html...
if exist "%~dp0configurator.html" (
  start "" "%~dp0configurator.html"
  echo Скачайте настроенный build_options.yaml и выполните:
  echo   python tools\build_mod.py --options build_options.yaml
) else (
  echo Файл configurator.html не найден рядом с configure.bat.
)
pause
"""

UNINSTALL = r"""@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
set "GAME={game}"
set /p "GAME=Папка HASSLE 2.0 [%GAME%]: "
set "DEST=!GAME!\{project}\Content\Paks\{subdir}"
set "BACKUP=!GAME!\{project}\Content\Paks\_oneasport_backup"
if exist "!DEST!\" goto :dest_ok
echo Папка "!DEST!" не найдена.
pause & exit /b 0

:dest_ok
for %%F in ("!DEST!\{mod}*.pak" "!DEST!\{mod}*.utoc" "!DEST!\{mod}*.ucas" "!DEST!\{mod}*.sig") do (
  if exist "%%F" (
    del /q "%%F" 2>nul
    echo - удалён %%~nxF
  )
)
if exist "!BACKUP!\" (
  for %%B in ("!BACKUP!\*") do (
    if exist "%%B" (
      copy /y "%%B" "!DEST!\" >nul
      echo ~ восстановлен из бэкапа %%~nxB
    )
  )
)
echo Все паки мода удалены.
pause
"""


def _build_module_prompts(manifest_path: Path, paks: list[Path]) -> tuple[str, str]:
    echo_lines: list[str] = []
    sel_lines: list[str] = []
    entries: list[tuple[str, str, str]] = []

    if manifest_path.is_file():
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        for p in m.get("paks", []):
            entries.append((p["pak_file"], p.get("group", ""), p.get("group_name", p["pak_file"])))
    if not entries:
        for p in paks:
            entries.append((p.name, p.stem, p.name))

    for i, (pak_file, grp, gname) in enumerate(entries, 1):
        pak_stem = Path(pak_file).stem
        safe_gname = gname.replace("(", "^(").replace(")", "^)")
        echo_lines.append(f'echo   - {pak_file} ^(+ .utoc/.ucas, {safe_gname}^)')
        copy_block = [
            f'    for %%E in (.pak .utoc .ucas .sig) do (',
            f'      if exist "%~dp0paks\\{pak_stem}%%E" (',
            f'        if exist "!DEST!\\{pak_stem}%%E" copy /y "!DEST!\\{pak_stem}%%E" "!BACKUP!\\" >nul',
            f'        copy /y "%~dp0paks\\{pak_stem}%%E" "!DEST!\\" >nul',
            f'      )',
            f'    )',
        ]
        if grp == "core":
            sel_lines.extend(
                [
                    f'if exist "%~dp0paks\\{pak_file}" (',
                    *[line[2:] for line in copy_block],
                    f'  echo + {pak_stem} ^(.pak/.utoc/.ucas^) [обязательный базовый пак]',
                    f')',
                ]
            )
        else:
            var = f"ANS_{i}"
            sel_lines.extend(
                [
                    f'set "{var}=y"',
                    f'set /p "{var}=Установить {safe_gname} ({pak_file})? [Y/n]: "',
                    f'if /i "!{var}!"=="y" (',
                    f'  if exist "%~dp0paks\\{pak_file}" (',
                    *copy_block,
                    f'    echo + {pak_stem} ^(.pak/.utoc/.ucas^)',
                    f'  )',
                    f')',
                ]
            )
    return "\n".join(echo_lines), "\n".join(sel_lines)


def main() -> None:
    log = get_logger("make_installer")
    cfg = load_config()
    game = cfg["game"].get("install_dir", "C:\\Games\\HASSLE")
    project = cfg["game"]["project_name"]
    subdir = cfg["game"].get("mods_subdir", "~mods")
    mod = cfg.get("mod", {}).get("pak_name", "zzz_OneasPort")
    version = cfg.get("mod", {}).get("version", "0.1.0")

    out_dir = ROOT / "out"
    manifest_path = out_dir / "build_manifest.json"
    # fix: брать точный список паков из build_manifest.json и исключать временные pilot/minitest паки
    paks: list[Path] = []
    if manifest_path.is_file():
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in m.get("paks", []):
            stem = Path(entry["pak_file"]).stem
            for ext in (".pak", ".utoc", ".ucas", ".sig"):
                cand = out_dir / f"{stem}{ext}"
                if cand.is_file():
                    paks.append(cand)
    if not paks:
        paks = [
            p
            for p in sorted(out_dir.glob(f"{mod}*_P.*"))
            if p.suffix in (".pak", ".utoc", ".ucas", ".sig")
            and not p.name.startswith(f"{mod}_pilot_P.")
            and "_minitest_" not in p.name
        ]
    if not paks:
        raise SystemExit("В out/ нет паков мода. Сначала запустите build_mod.py или pak_build.py.")

    rel = out_dir / "release" / f"{mod}_{version}"
    (rel / "paks").mkdir(parents=True, exist_ok=True)
    for old in (rel / "paks").glob("*"):
        old.unlink()
    for p in paks:
        shutil.copy(p, rel / "paks" / p.name)
    if manifest_path.is_file():
        shutil.copy(manifest_path, rel / "build_manifest.json")
    cfg_html = out_dir / "configurator.html"
    if cfg_html.is_file():
        shutil.copy(cfg_html, rel / "configurator.html")

    mod_echo, mod_sel = _build_module_prompts(manifest_path, paks)
    fmt = dict(
        game=str(game).replace("/", "\\"),
        project=project,
        subdir=subdir,
        mod=mod,
        module_list_echo=mod_echo,
        selective_blocks=mod_sel,
    )
    # fix: пишем с newline="\r\n" от нормализованного "\n", чтобы не возникали двойные \r\r\n на Windows
    (rel / "install.bat").write_text(INSTALL.format(**fmt).replace("\r\n", "\n"), encoding="utf-8", newline="\r\n")
    (rel / "configure.bat").write_text(CONFIGURE.replace("\r\n", "\n"), encoding="utf-8", newline="\r\n")
    (rel / "uninstall.bat").write_text(UNINSTALL.format(**fmt).replace("\r\n", "\n"), encoding="utf-8", newline="\r\n")

    today = dt.date.today().isoformat()
    (rel / "README.txt").write_text(
        f"ONEAS STUDIO -> HASSLE 2.0, версия {version} ({today})\r\n\r\n"
        "Установка: запусти install.bat (доступны режимы 'установить всё' и 'выбрать модули').\r\n"
        "Настройка состава: запусти configure.bat (откроет configurator.html).\r\n"
        "Удаление: запусти uninstall.bat (удаляет все паки мода и восстанавливает бэкап).\r\n"
        "Перенос выполнен с разрешения ONEAS STUDIO. Используйте на свой риск: проверьте правила проекта HASSLE.\r\n",
        encoding="utf-8",
    )
    changelog = out_dir / "release" / "CHANGELOG.md"
    if changelog.exists():
        shutil.copy(changelog, rel / "CHANGELOG.md")
    zip_path = shutil.make_archive(str(rel), "zip", rel.parent, rel.name)
    log.info("Релиз собран: %s (паков: %d)", zip_path, len(paks))


if __name__ == "__main__":
    main()
