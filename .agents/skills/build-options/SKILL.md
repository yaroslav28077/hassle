---
name: build-options
description: Управление опциями модульной сборки (build_options.yaml), генерация оффлайн-конфигуратора (out/configurator.html) и сборка выборочных .pak (tools/build_mod.py). Использовать в Фазах 3–6 при настройке вариантов сборки ONEAS -> HASSLE 2.0.
---

# Опции сборки и оффлайн-конфигуратор

1. Открой `build_options.yaml` и сверь группы с `mapping/asset_map.csv` (`option_group`, `option_value`).
   - Выдумывать опции запрещено: каждая опция соответствует реальным файлам/вариантам из `work/build_only/` или `work/textures/`.
   - Опции без доступного слота или ожидающие FModel (`patch_text`, `no_slot`) отмечены `available: false` с понятной `unavailable_reason`.
2. Сгенерируй/обнови оффлайн-конфигуратор:
   `python tools/configurator.py --options build_options.yaml --out out/configurator.html`
   - HTML полностью автономен (без CDN), содержит миниатюры из `work/previews/`, пресеты (`basic`, `maximum`, `custom`), кнопку скачивания `build_options.yaml` и список недоступных слотов.
3. Проверь состав без записи на диск:
   `python tools/build_mod.py --options build_options.yaml --preset maximum --dry-run`
4. Собери модульные `.pak` и `out/build_manifest.json`:
   `python tools/build_mod.py --options build_options.yaml`
   - Базовая часть (`option_group == ""`) пакуется в `out/zzz_OneasPort_core_P.pak`, каждая включённая группа — в `out/zzz_OneasPort_<group>_P.pak`.
   - Если у выбранной опции отсутствует исходник или есть конфликт `target_package`, скрипт завершается с явной ошибкой.
5. Собери установщик с выбором модулей:
   `python tools/make_installer.py` (после утверждения релизного пакета).
