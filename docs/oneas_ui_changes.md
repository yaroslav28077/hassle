# Изменения интерфейса в сборке ONEAS STUDIO (Radmir RP) и перенос на HASSLE 2.0

Документ фиксирует, что именно сборка ONEAS изменяет в Cohtml/CEF-интерфейсе Radmir RP и какие части допустимо переносить на HASSLE 2.0 по правилам `.agents/rules/00-guardrails.md` и `.agents/rules/30-asset-quality.md`.

## 1. Как устроены изменения в исходной сборке ONEAS

По итогам аудита `work/build_only/` и сравнения с оригиналом `D:/Games/RADMIR Games/RADMIR CRMP/manifest.json`:

1. **Прямые замены в `uiresources/` (52 файла)**:
   - `uiresources/images/gps/*.png` — **48** перерисованных иконок карты/GPS (`65×64` и `65×65`).
   - `uiresources/sounds/*` — **4** заменённых UI/клиентских звука (`car/siren/sound_0.mp3`, `car/start_engine_car.wav`, `inventory/open.mp3`, `inventory/close.mp3`).
   - Изменённых `.css`, `.js` или `.html` файлов на диске в `uiresources/` нет (размеры и состав остальных файлов совпадают с `manifest.json`).

2. **Дополнительные ресурсы сборки ONEAS (124 файла в `uiresources/` + 9 текстур в `MobileHud/mobilescs.txd`)**:
   - `uiresources/oneas-img/weapon/*.png` — **44** иконки оружия (`0.png` и `44.png` — `1×1` пустая заглушка; `1..43` — `2000×2000`; `45.png` — `1×1`).
   - `uiresources/oneas-img/hud/*` — **17** элементов HUD (`bg-server.png`, `bonus-2.png`, `bonus-3.png`, `icon-armour.png`, `icon-breath.png`, `icon-data.svg`, `icon-fish.svg`, `icon-freeze.png`, `icon-health.png`, `icon-hunger.png`, `icon-id.svg`, `icon-online.svg`, `icon-time.svg`, `icon-zz.svg`, `radar.png`, `wanted-active.svg`, `wanted-inactive.svg`).
   - `uiresources/oneas-img/interfaces/*` — **39** ресурсов экранов/контролов:
     - 4 SVG-контрола меню/диалогов (`layer_option_active.svg`, `layer_option_hover.svg`, `option_active.svg`, `option_hover.svg`), совпадающих по именам с `Main/assets/`;
     - 31 фон авторизации `bg-auth-0.png` .. `bg-auth-30.png` (`1920×1080`, `bg-auth-1.png` `1920×1079`);
     - 4 элемента (`bg.info-card.png`, `free.svg`, `line_top.png`, `noise.gif`).
   - `uiresources/oneas-img/speed/*` — **8** SVG-иконок спидометра (`fuel-active.svg`, `fuel-active_danger.svg`, `fuel-bg.svg`, `fuel-bg_danger.svg`, `wash-active.svg`, `wash-active_danger.svg`, `wash-bg.svg`, `wash-bg_danger.svg`).
   - `uiresources/fonts/*` — **16** шрифтов (`Akrobat-*` OTF `fsType=8`, `ALSRubl.ttf` `fsType=0`, `GothamPro*` TTF `fsType=4`; коммерческих запретов `fsType=2` нет).
   - `MobileHud/mobilescs.txd` (извлечено в `work/textures/mobilescs/`) — 8 фонов `3840×2160` (`bglegal.png`, `mobilesc0.png`..`mobilesc6.png`) и логотип `rockstar.png` (`300×300`).

3. **Как ONEAS подключал `oneas-img`, `JsLoader.asi` и `localStorage.json` (аудит исходников Radmir)**:
   - Сквозная проверка всех файлов в `D:/Games/RADMIR Games/RADMIR CRMP/uiresources/` (`index.html`, все `.js`/`.css`/`.json`), `oneasData/`, `JsLoader.asi`, `Hooks.asi`, `MobileHud.asi`, `oneasTxdEditor.asi`, `cleo/*`, `SAMPFUNCS/*` и `modloader/*` дала **0 текстовых ссылок `oneas-img` и `oneas-plugins` на диске** (кроме `localStorage.json`). Все штатные `.html`, `.js` и `.css` внутри `uiresources/` байт-в-байт совпадают с оригинальным `manifest.json` Radmir (`0` модифицированных JS/CSS-файлов на диске).
   - `work/build_only/JsLoader.asi` (`652 288` Б, строка версии `"0.4.2"` в `.data`, секции `.text`/`.rdata`/`.data`/`.rsrc` без упаковщика) — нативный C++ WebSocket++/0.8.2 + Boost.Asio 1.82 локальный HTTP/WebSocket-мост между CEF и процессом GTA SA/SAMP. Встроенных JS/CSS-шаблонов темы или путей `oneas-img` внутри `JsLoader.asi` нет.
   - Зарегистрированные команды моста `JsLoader.asi`:
     - работа с файлами и ссылками: `readFile`, `writeFile`, `existsFile`, `openLink`, `getVersion`;
     - ввод и окно: `getKeyboardLayout`, `getKeyState`, `EmulateKeyPress`, `EmulateComboPress`, `isGtaActive`;
     - игровые состояния GTA/SAMP: `isSpawned`, `getPing`, `getRandomNumber`, `getPlayerId`, `getServerOnline`, `getPedState`, `getCurrentGear`, `getCurrentCarHP`.
   - Настройки визуальных плагинов хранятся в `D:/Games/RADMIR Games/RADMIR CRMP/localStorage.json`:
     - `"oneas-plugins"`: `{"classSelect":true,"classSwitch":true,"alocker":true,"oldInfoCard":true,"rakNetInfo":true,"screenTime":true}`;
     - косметические ключи: `"oneas.classSelect.miniMapShape": "shape-minimap-3"`, `"playerVitals": 1`, `"dialogStyle": 1`, `"oneas.screenTime.settings": {...}`;
     - геймплейные/SAMP-переключатели: `classSelect`, `classSwitch`, `alocker`, `rakNetInfo`.
   - **Механизм в Radmir и стратегия переноса на HASSLE 2.0:** на диске в сборке ONEAS лежат только ресурсы темы (`uiresources/oneas-img/*`, `uiresources/fonts/*`, заменённые `images/gps/*`, `sounds/*`) и профиль `localStorage.json`, а сам JS-рантайм плагинов (который считывал `oneas-plugins` и обращался к `oneas-img/...` через CEF/мост) на диск в открытом виде не выгружен. **Решение по `00-guardrails.md`**: `JsLoader.asi` и все `.asi` / `.cs` / `.cleo` / `.dll` плагины в мод **НЕ переносятся** (`action = skip`), а сами ресурсы `oneas-img` напрямую сопоставляются со штатными файлами бандла `HassleOnline/Content/UserInterface/Main/` (см. [ui_asset_refs.md](file:///d:/Hassle%20port/hassle-port/docs/ui_asset_refs.md)), либо — для зашитых в JS/CSS base64/SVG — переносятся патчем `patch_text` после распаковки через `FModel`.

## 2. Что переносится на HASSLE 2.0 (Дорожка A — только косметика Cohtml UI)

У HASSLE 2.0 интерфейс `Main` (`15 639` файлов) практически идентичен по структуре `uiresources/` Radmir (`15 558` общих относительных путей), а `LoadingScreen` лежит в `HassleOnline/Content/UserInterface/LoadingScreen/`. Однако важные CSS/JS файлы (`Hud.css`, `Hud.js`, `Authorization.css`, `Authorization.js`, `Inventory.js`) в HASSLE 2.0 отличаются от Radmir по `UncompressedSize` в `.pak`, а оригинальные `Manifest` MD5 сжатых (`cm=1`) файлов без `oo2core_9_win64.dll` / `FModel` недоступны для побайтового сравнения.

Поэтому стратегия переноса Дорожки A:

1. **`replace_file` (прямая подмена ассета по тому же пути внутри `.pak` без правки JS/CSS)**:
   - `images/gps/*.png` (`48` файлов) → `HassleOnline/Content/UserInterface/Main/images/gps/*.png` (подгонка `65×64`/`65×65` в слот `80×80` пропорционально с прозрачным padding по краям, без растягивания).
   - `oneas-img/weapon/0..44,46` (`43` файла, кроме `45.png`) → `HassleOnline/Content/UserInterface/Main/images/hud/<id>.png` + для пустых рук (`weapon=0`) дополнительно `HassleOnline/Content/UserInterface/Main/assets/hassle-logo2.png` (`321×321`, т.к. при `!t.info.weapon` в `Hud.js` рендерится `logoImage`).
   - `sounds/*` (`4` файла) → `HassleOnline/Content/UserInterface/Main/sounds/...` (размер в HASSLE `cm=1` совпадает с Radmir `manifest.json`).
   - `oneas-img/interfaces/` (4 SVG контрола: `layer_option_active.svg`, `layer_option_hover.svg`, `option_active.svg`, `option_hover.svg`) → `HassleOnline/Content/UserInterface/Main/assets/*.svg`.
   - `oneas-img/speed/` (`fuel-bg.svg`, `wash-bg.svg`) → `HassleOnline/Content/UserInterface/Main/assets/{fuel-bg,wash-bg}.svg`.
   - `oneas-img/hud/` по реальным ссылкам из `Hud.js` (см. [ui_asset_refs.md](file:///d:/Hassle%20port/hassle-port/docs/ui_asset_refs.md)): `bonus-2.png` → `Main/assets/278.png` (`60×48`), `bonus-3.png` → `Main/assets/373.png` (`53×46`), `icon-health.png` → `Main/assets/health2.png` (`72×59`), `icon-armour.png` → `Main/assets/armour2.png` (`161×198`, апскейл 3.2× отмечен в `notes`).
   - Фоны `bg-auth-0..30.png` → `Main/assets/background3.png` (`1920×1080` 1:1 для экрана входа `.authorization`) и `Main/assets/bg-register.png` (`2340×1080` с padding для `.authorization_register`); экраны `MobileHud/mobilescs.txd` (`bglegal`, `mobilesc0..6`) → `LoadingScreen/img/background.2fc2a64f.png` (`1920×1080`, `cm=0`).

2. **`patch_text` / `conflict` (требуют извлечения CSS/JS из HASSLE `cm=1` перед правкой)**:
   - В HASSLE `Hud.css` (`198 000` vs `167 600`), `Hud.js` (`280 959` vs `208 455`), `Authorization.css` (`20 314` vs `20 339`) изменены.
   - Вшитые в JS/CSS элементы (`icon-hunger.png`, `icon-freeze.png`, `icon-online.svg` — inline `data:image/png;base64` в `Hud.js`; 6 активных/danger SVG спидометра `fuel-active*` / `wash-active*` / `*_bg_danger` — inline `<svg>` в `Hud.js` и классы `_danger` в `Hud.css`), а также `radar.png`, `bg-server.png` (`server-bg.svg`), `icon-breath.png` (`lungs.png` `214×214`), `icon-data/fish/id/time/zz.svg`, `wanted-active/inactive.svg`, `line_top.png`, `noise.gif`, `bg.info-card.png`, `free.svg` и шрифты требуют косметического патча `Hud.js` / `Hud.css` / `Authorization.css` после распаковки в `FModel`.

3. **`no_slot` (нет слота в HASSLE)**:
   - `oneas-img/weapon/45.png` (в HASSLE `Main/images/hud/45.png` отсутствует).
   - `MobileHud/mobilescs.txd/rockstar.png` (`300×300`) — отдельного слота в `LoadingScreen` нет.

## 3. Что НЕ входит в Дорожку A

- **Дорожка B (`pending_B`)**: текстуры из `models/hud.txd` (прицелы, радар-кольцо), `CustomSAA2/VEHICLE.TXD` / `oneasData/txd_editor/...`, `models/effectsPC.txd`, `models/particle.txd`, звуки оружия/двигателей из `modloader/sound/GENRL/` и `cleo/p1_bell.mp3`.
- **`skip`**: `.asi`, `.cs`, `.cleo`, `.dll`, конфиги (`.ini`, `.cfg`, `.dat`), `modloader/.data/*`, `models/effects.fxp`, `SAMPFUNCS SDK` (удалён из `work/build_only`).
