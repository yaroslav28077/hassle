# Конвейер переноса

```
source/ (ONEAS, GTA SA)
  │  inventory.py ─────────────► work/inventory/summary.md
  │  img_extract.py ───────────► work/extracted/
  ├─ .txd ── txd_extract.py ───► work/textures/*.png ── fit (Pillow) ──► work/textures_fit/
  ├─ .dff ── blender_dff_to_fbx ► work/fbx/*.fbx
  ├─ звуки ─ audio_convert.py ─► work/audio/*.wav
  └─ UI (png/svg/html/css) ────► work/ui/*.png
                     │
          map_init.py + ручное сопоставление
                     ▼
           mapping/asset_map.csv  (target_package = путь ассета HASSLE)
                     │
           ue_import.py (внутри UE той же версии, проект с именем как у игры)
                     ▼
           UE-проект мода: ассеты по путям оригиналов
                     │
           pak_build.py cook → pak  (или BuildCookRun + iostore-collect)
                     ▼
           out/zzz_OneasPort_P.pak(.utoc/.ucas)
                     │
           make_installer.py → out/release/… (install.bat / uninstall.bat)
```

## Почему именно так

- Unreal грузит паки по алфавиту и с приоритетом у `_P`. Ассет с тем же путём в паке с большим приоритетом заменяет оригинал. Поэтому мод = набор ассетов **по путям оригиналов**.
- Cooked-формат зависит от версии движка, поэтому проект мода должен быть той же версии.
- Mount point пака `../../../<Project>/Content/` должен совпасть с игрой, отсюда требование к имени проекта.
- Заглушки нужны, чтобы наши ассеты могли ссылаться на ассеты игры, не перетаскивая их в пак.

## Статусы в asset_map.csv

`todo_convert` → `todo` → `imported` → `packed` → `verified`; боковые: `skip` (сознательно не переносим, с причиной), `blocked` (не получилось, с описанием).
