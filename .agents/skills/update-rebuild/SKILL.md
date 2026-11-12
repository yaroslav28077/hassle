---
name: update-rebuild
description: "Что делать после обновления HASSLE 2.0: проверить, не изменились ли пропатченные файлы интерфейса (Hud.js, Hud.css, Authorization.css, PauseMenu.js), и пересобрать мод на новой версии. Использовать после каждого обновления игры или если игрок пишет, что HUD сломался."
---

# Пересборка после обновления игры

Мод кладёт в пак ЦЕЛИКОМ пропатченные `Hud.js`, `Hud.css`, `Authorization.css`, `PauseMenu.js`.
Если игра обновила их, старая копия из мода перекроет новую.

1. `python tools/check_update.py`
   - «Можно играть» (код 0): обновление не тронуло наши файлы, ничего не делаем.
   - «нужна пересборка» (код 1): идём дальше.
   - «проверить не удалось» (код 2): нет `out/update_guard.json` или `manifest.json` лаунчера; соберите мод заново.
2. Заново выгрузить из паков игры новые версии изменённых файлов в `Exports/<chunk>/Content/UserInterface/Main/assets/` (FModel, UE 5.8). Старые сохранить рядом как `*.prev` для сравнения.
3. `python tools/patch_ui.py`. Патчи накладываются по якорям: если игра поменяла код, скрипт упадёт с именем якоря
   (`InfoWanted_qi`, `HudMap computed`, `function ao: найдено 0 объявлений` и т.п.). Тогда:
   - найти новое место в новом бандле (поиск по классам `hud-radmir-*`);
   - поправить якорь в `tools/patch_ui.py` / `tools/oneas_runtime.py` (DUAL — список переключаемых функций);
   - не «чинить» молча: каждое изменение якоря записать в PROGRESS.md.
4. Превью: `python tools/preview/make_preview.py --serve`, открыть `http://localhost:8766/frame.html?w=1920&h=1080`,
   в консоли `f.contentWindow.openInterface('Hud'); f.contentWindow.__scene({immortality:true})`,
   переключить все варианты в панели (`f.contentWindow.oneasOpenSettings()`), ошибок в `f.contentWindow.__errors` быть не должно.
5. `python tools/build_mod.py --options build_options.yaml --preset maximum --single-pak` (сам обновит `out/update_guard.json`),
   затем `python tools/make_installer.py`, поднять `mod.version` в config.yaml и запись в CHANGELOG.md.
6. Проверка в игре по `out/QA_CHECKLIST.md`.

Игрокам: если после обновления HUD странный — ESC -> «Настройки ONEAS» -> «Безопасный режим» или `uninstall.bat`.
