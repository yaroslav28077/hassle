---
name: ue-import
description: "Фаза 5. Создание UE-проекта мода нужной версии и импорт ТОЛЬКО тех сконвертированных ассетов, которые в игре являются реальными UE-ассетами (uasset в IoStore: 3D-модели, текстуры материалов/мира, SoundWave), по target_package из asset_map.csv скриптом tools/ue_import.py. Не используется для Cohtml UI и обычных файлов из .pak (html/css/js/png/svg/шрифты)."
---

# Фаза 5: импорт в Unreal Engine (только `uasset`)

> **Важно:** файлы Cohtml UI (`HassleOnline/Content/UserInterface/...`) и прочие обычные файлы в `.pak` через UE **не импортируются** и не проходят cook — для них эта фаза пропускается. Фаза 5 нужна только если в `mapping/asset_map.csv` есть ассеты, которые в HASSLE 2.0 хранятся как cooked `uasset` (в `.utoc/.ucas`).

## Проект мода (один раз)
1. Unreal Engine той же версии, что игра. Новый проект: Blank, C++ не нужен, без Starter Content.
2. **Имя проекта = `game.project_name`** из config. Путь проекта запиши в `ue.mod_project`.
3. Plugins: включи **Python Editor Script Plugin** (и Editor Scripting Utilities для UE4), перезапусти.
4. Project Settings → Packaging: `Use Pak File = ON`; для IoStore-игры `Use Io Store = ON`, `Generate Chunks = ON`.

## Заглушки
Если модели нужны материалы или скелет игры, создай пустые ассеты по тем же путям (материал с тем же именем, скелет из FBX оригинала). В карту их **не добавляй**, чтобы они не попали в пак.

## Импорт
1. Пилот: в PowerShell `$env:HASSLE_PORT_ONLY="A00001,A00002"`, затем
   `& "<UnrealEditor-Cmd.exe>" "<proj>.uproject" -run=pythonscript -script="<abs>/tools/ue_import.py"`
   или в консоли редактора: `py "<abs>/tools/ue_import.py"`.
2. Проверь в Content Browser: путь и имя совпадают с `target_package`, у UI-текстур группа UI без мипов.
3. Массово: тот же запуск без `HASSLE_PORT_ONLY`.
4. Строки с `blocked` разбери по Output Log (фильтр `[hassle-port]`, `LogFbx`, `LogTexture`).
