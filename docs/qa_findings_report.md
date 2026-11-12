# Отчёт по результатам проверки сборки ONEAS → HASSLE 2.0 (`2026-11-12`)

## 1. Что реально подтверждено в игре

- **Механизм загрузки модов работает (`~mods` + `.pak` v12 + пустые `.utoc/.ucas`):**
  - **Экран загрузки** (`UserInterface/LoadingScreen/img/background.2fc2a64f.png`) сработал во всех запусках (Вариант A2, PILOT2, 9-паковая сборка).
  - **Звук инвентаря** (`UserInterface/Main/sounds/inventory/open.mp3`, оригинал из `pakchunk179-Windows.pak`) сработал в **Варианте A2** (`zzz_OneasPort_pilot_P.pak`, 4 файла) и в **PILOT2** (2 пака: `loading_screen_P` + `ui_sounds_P`).
  - **Установщик и откат** (`install.bat` / `uninstall.bat`) после правки пути `(x86)` корректно ставят файлы в `~mods\` с бэкапом и полностью их удаляют.

## 2. Что не применилось при массовом тесте (`maximum`)

- При установке **9 модульных паков (`106` файлов)** сработал только п. 1 (`loading_screen`), а пункты `2..9` (`auth_bg`, `hud_status_icons`, `hud_bonus_badge`, `weapon_icons`, `gps_icons`, `speedometer_bg`, `ui_sounds`, `core`) не проявились. На скриншоте HUD остались оригинальные белый кулак (`images/hud/0.png`, хотя у ONEAS он прозрачный) и жёлтый бейдж `X2`.
- При установке **единого пака `zzz_OneasPort_P`** (`106` файлов, `9 196 004` Б) изменения в HUD, фоне авторизации и GPS также не появились.

## 3. Установленные причины и факты (без домыслов)

### 3.1. Что точно исключено
- **Формат `.pak` и `.utoc/.ucas` исправен:** `tools/pak_v12.py` воспроизводит `pakchunk82-Windows.pak` (1 310 Б) и `pakchunk1-Windows.pak` (339 Б) на 100% байт в байт; `tools/iostore_empty.py` воспроизводит все 16 UI-контейнеров `pakchunk166..181` на 100% байт в байт; индексы и SHA-1 всех 106 записей в `out/zzz_OneasPort_P.pak` проверены.
- **Файлы реально попадали в `~mods\`:** проверено на диске — все 27 файлов (`maximum`) копировались в `HassleOnline/Content/Paks/~mods/`. Античита и `.sig` нет.

### 3.2. Что точно выявлено в качестве проблем
1. **Часть путей в `mapping/asset_map.csv` относится к неактивным/старым файлам HUD:**
   - В извлечённом оригинале `game_ref/originals/.../Main/assets/bonus.png` лежит **серый череп с костями**, а не жёлтый значок `X2` на экране HUD. При этом в `game_ref/ui_files.txt` есть `assets/x2.svg` и `assets/bonuses.svg`.
   - Для статусов HUD и спидометра в `game_ref/ui_files.txt` наряду с `health.png`, `armour.png`, `fuel-bg.svg`, `wash-bg.svg` есть `health-colored.png`, `health2.png`, `armour-colored.png`, `armour2.png`, `fuel2.svg`, `fuel3.svg`, `fuel-bg-helloween.svg`, `wash-bg-helloween.svg`. Какие именно файлы рендерит текущий Vite-бандл HASSLE 2.0 (`assets/index.js`, `assets/Hud.js`, `assets/Authorization.js`), сейчас скрыто сжатием Oodle v9 (`cm=1`).
2. **Почему не сработали даже `weapon/0.png`, `gps/`, `bg-register.png` и `ui_sounds` в 106-файловой сборке (что требует проверки):**
   - **Разный `MountPoint`:** все 16 штатных паков `UserInterface/Main/` (`pakchunk166..181-Windows.pak`) имеют `MountPoint = "../../../HassleOnline/Content/UserInterface/Main/"`, а наш пак — `"../../../HassleOnline/Content/"` (при этом для `open.mp3` в A2/PILOT2 общий `MountPoint` работал).
   - **Порядок/приоритет или удалённый UI:** в `HassleOnline-Win64-Shipping.exe` присутствуют настройки `bUseRemoteUserInterface` / `RemoteUserInterfaceAddress` и `coui://LoadingScreen/index.html`, `coui://Main/index.html`. Также не проверен runtime-лог движка `HassleOnline.log` (`%LOCALAPPDATA%\HassleOnline\Saved\Logs\`), где UE пишет точный `PakOrder` при монтировании и ошибки Cohtml/IoStore.

## 4. Варианты следующих шагов

1. **Распаковать `Main/assets/*.js` и `*.css` через `FModel` (`oo2core_9`):**
   - Позволит точно увидеть в коде интерфейса HASSLE 2.0, какие пути картинок/звуков реально используются на HUD, экране входа, карте и спидометре, и есть ли загрузка UI по сети (`bUseRemoteUserInterface`).
   - Одновременно закроет этап подготовки к `17` задачам `patch_text`.
2. **Проверить лог игры (`%LOCALAPPDATA%\HassleOnline\Saved\Logs\HassleOnline.log`):**
   - По строкам `Mounting pak file` сразу станет ясно, монтируется ли `zzz_OneasPort_P.pak` полностью и с каким `PakOrder` относительно `pakchunk172..181`.
3. **Изолированный мини-тест `Main` с родным `MountPoint`:**
   - Собрать пак только из 2–3 гарантированно проверяемых файлов (`sounds/inventory/open.mp3` + `images/hud/0.png` + `images/hud/24.png`) с точным `MountPoint = "../../../HassleOnline/Content/UserInterface/Main/"` (как у `pakchunk166..181`) и проверить без примеси других файлов.
