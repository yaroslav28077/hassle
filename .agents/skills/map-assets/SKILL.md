---
name: map-assets
description: "Фаза 3. Составление и заполнение mapping/asset_map.csv: какой файл сборки ONEAS заменяет какой ассет HASSLE 2.0 (target_package), тип ассета, группа текстуры, статус. Использовать после разведки обеих сторон и при добавлении новых ассетов."
---

# Фаза 3: карта соответствий

`mapping/asset_map.csv` единственный источник правды о том, что и куда переносится.

| колонка | что писать |
|---|---|
| id | A00001… (ставит map_init.py) |
| category | texture / image / model / audio / ui / font / code_plugin … |
| variant | basic / maximum / пусто |
| source_file | путь в сборке (для текстур `файл.txd::имя_текстуры`) |
| converted_file | PNG/FBX/WAV в work/ |
| target_package | путь ассета HASSLE, например `/Game/UI/HUD/Textures/T_Radar_Frame` |
| asset_type | Texture2D / StaticMesh / SkeletalMesh / SoundWave |
| texture_group | UI / World / Normal |
| width, height | размер исходника |
| status | todo_convert → todo → imported → packed → verified / skip / blocked |
| notes | причины, особенности, `skeleton=/Game/...` для skeletal |

Порядок:
1. Сначала конвертация превью (фаза 1 уже дала PNG), затем `python tools/map_init.py`.
2. Для каждой строки P1/P2 найди соответствие в `game_ref/asset_paths_*.txt`: по смыслу (радар → radar, прицел → crosshair/reticle, HP → health), по размеру и пропорциям, по сравнению картинок в `game_ref/originals/`.
3. Если для ассета сборки нет аналога в HASSLE, ставь `skip` с причиной «нет слота в HASSLE».
4. Если один ассет HASSLE претендуют заменить несколько файлов сборки (Basic и Maximum), оставь основной вариант, второй пометь `variant` и `skip` до решения пользователя.
5. Сводка: `python -c "import pandas as pd; d=pd.read_csv('mapping/asset_map.csv'); print(d.groupby(['category','status']).size())"`.

**СТОП**: покажи пользователю сводку и 10–15 примеров соответствий (особенно HUD и прицелы). Массовая конвертация только после подтверждения.
