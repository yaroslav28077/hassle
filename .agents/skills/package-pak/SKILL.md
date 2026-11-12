---
name: package-pak
description: "Фаза 6. Cook и упаковка мода в pak (zzz_OneasPort_P.pak) или IoStore (.pak/.utoc/.ucas) только из ассетов asset_map.csv, с правильным mount point. Использовать после импорта в UE."
---

# Фаза 6: упаковка

Сначала: в `game_ref/target_report.md` вердикт 🟢. Иначе не пакуем.

## Режим pak (нет .utoc у игры)
1. `python tools/pak_build.py cook`
2. `python tools/pak_build.py pak` → `out/zzz_OneasPort_P.pak`, список файлов `out/zzz_OneasPort_filelist.txt`.
3. Проверка содержимого: `"<Engine>/Engine/Binaries/Win64/UnrealPak.exe" out/zzz_OneasPort_P.pak -List`. Mount point должен быть `../../../<Project>/Content/`.

## Режим iostore (у игры .utoc/.ucas)
1. В проекте мода создай `PrimaryAssetLabel` в каждой папке с ассетами мода: `Chunk ID = mod.chunk_id` (100), `Label Assets In My Directory = ON`, `Cook Rule = Always Cook`.
   Заглушки держи в отдельной папке **без** метки, чтобы они ушли в chunk 0, который мы не берём.
2. `python tools/pak_build.py iostore-cmd` печатает команду BuildCookRun. Запусти её.
3. `python tools/pak_build.py iostore-collect` → `out/zzz_OneasPort_P.pak/.utoc/.ucas`.

## Частые проблемы
- Игра не видит мод: не та папка (`~mods` vs корень Paks), не совпадает имя проекта (mount point), другая версия UE.
- Вылет при загрузке: версия движка отличается или ассет ссылается на то, чего нет в игре (заглушка с другим классом).
- Текстура чёрная или розовая: неверный формат сжатия или пропали мипы у world-текстуры.
