# Сверка формата `.pak` HASSLE 2.0 (UE 5.8) и `tools/pak_v12.py`

Дата проверки: `2026-11-12` (только чтение файлов игры и исполняемого файла).

## 1. Вывод (почему пилот не сработал)

Найдены **три** конкретные причины, объясняющие, почему пилот не применился в игре ни в `~mods`, ни с копиями `global.utoc`/`.ucas`:

1. **Ошибка сериализации в `tools/pak_v12.py` (критичная, найдена при побайтной сверке):**
   - В реальных `.pak` HASSLE 2.0 (проверено на `pakchunk82-Windows.pak`, `pakchunk165-Windows.pak`, `pakchunk166-Windows.pak`, `pakchunk181-Windows.pak`) `MountPoint` и имена папок в `FullDirectoryIndex` пишутся как null-terminated `FString` (`len+1` и завершающий `\x00`), а **`FileName` в `FullDirectoryIndex` пишется БЕЗ `\x00`** (`len` без нуль-терминатора).
   - Старая версия `pak_v12.py` вызывала `_fstring(fn)` с `\x00`, из-за чего в индексе пилота имена хранились с лишним байтом `0x00` на конце (`'0.png\x00'`, `'24.png\x00'` и т.д.).
   - Кроме того, в `FullDirectoryIndex` реальных паков всегда присутствуют корень `'/'` (даже с `0` файлами, см. `pakchunk166`) и все промежуточные родительские каталоги (`pakchunk0`, `pakchunk165`), чего не было в старом пилоте.
2. **IoStore и ошибка `utoc not found` (`pak.AllowMissingUToc`) + неверная пара `global.utoc/.ucas`:**
   - В `HassleOnline-Win64-Shipping.exe` рядом со строкой `_P.pak` находится строка `utoc not found`, а также CVar `pak.AllowMissingUToc` (*«Enables mounting a .pak file without the corresponding .utoc file even if the I/O dispatcher is enabled»*), по умолчанию выключенный.
   - Копии `global.utoc` (842 Б) / `global.ucas` (3 531 376 Б) не подходят в качестве пары для чанк-пака: `global.*` — глобальный IoStore-контейнер (`IoGlobalData`), а все реальные UI-чанки без `.uasset` (`pakchunk166..181-Windows.*`) имеют пустой парный контейнер размером **240 Б (`.utoc`) + 64 Б (`.ucas`)** (1 запись `ContainerHeader`, `ver=8`, magic `IoCn` v5).
3. **Папка `~mods` не найдена в строках `Shipping.exe`:**
   - Поиск по всему `HassleOnline-Win64-Shipping.exe` (182 231 472 Б) дал **0 совпадений** для `~mods` (ни ASCII, ни UTF-16LE). В строках путей присутствуют `%sPaks/` и `%sPaks/%s-`. Все штатные 238 `.pak` игры лежат напрямую в `HassleOnline/Content/Paks/`.

---

## 2. Побайтная сверка `pakchunk82-Windows.pak` (и других реальных паков) со старым пилотом

Эталонный малый пак с файлами: `pakchunk82-Windows.pak` (`1 310` байт, 3 файла `.stinfo`, `cm=0` без сжатия). Дополнительно сверены `pakchunk1-Windows.pak` (`339` байт, 0 файлов), `pakchunk166-Windows.pak` (`95 004 254` байт, 5 файлов UI), `pakchunk165-Windows.pak` (`RawData`, 153 файла), `pakchunk181-Windows.pak` (`UI`, 7 607 файлов), `pakchunk0-Windows.pak` (1 827 файлов).

| Поле / секция | Эталон `pakchunk82-Windows.pak` | Старый `zzz_OneasPort_pilot_P.pak` | Исправленный `pak_v12.py` | Статус |
|---|---|---|---|---|
| `FPakInfo` размер футера | `221` байт (без `bFrozenIndex`) | `221` байт | `221` байт | Совпадало |
| `EncryptionKeyGuid` | `00 * 16` | `00 * 16` | `00 * 16` | Совпадало |
| `bEncryptedIndex` | `0` | `0` | `0` | Совпадало |
| `Magic` / `Version` | `0x5A6F12E1` / `12` | `0x5A6F12E1` / `12` | `0x5A6F12E1` / `12` | Совпадало |
| `IndexOffset` / `IndexSize` | `647` / `171` | `1625383` / `183` | Точно совпадает | Совпадало |
| `IndexHash` (SHA-1 `PrimaryIndex`) | SHA-1 точный | SHA-1 точный | SHA-1 точный | Совпадало |
| `CompressionMethods` | `5 × 32` нуля (итого 160 Б) | `5 × 32` нуля | `5 × 32` нуля | Совпадало |
| `MountPoint` | `'../../../HassleOnline/Content/'` (`null=True`, 31 Б + `\x00`) | `'../../../HassleOnline/Content/'` (`null=True`) | `null=True` | Совпадало |
| `PathHashSeed` | `0x00000000ca35c30c` (uint64) | `0x00000000f47fb12c` (CRC32 имени) | uint64 | Совпадало |
| `PrimaryIndex` (PH/FD мета, `EncodedPakEntries`, `FilesCount=0`) | `bHasPH=1`, `bHasFD=1`, `EncSz=36`, `FilesCount=0` (4 Б) | Тот же макет, `EncSz=48`, `FilesCount=0` | Идентично | Совпадало |
| Inline `FPakEntry` перед данными | `53` байта (`0, sz, usz, cm=0, sha1, flags=0, blk=0`), без padding между записями (`0`, `253`, `426`, `647`) | `53` байта, без padding | `53` байта, без padding | Совпадало |
| Encoded `FPakEntry` (`cm=0`) | `12` байт (`0xE0000000 \| flags`, `uint32(off)`, `uint32(usz)`) | `12` байт | `12` байт | Совпадало |
| `PathHashIndex` порядок и хэш | Порядок обхода, `FNV-1a 64-bit` по **lower UTF-16LE** (`0xCBF29CE484222325 + seed`), хвост `00000000` (4 Б) | Тот же алгоритм | Тот же алгоритм | Совпадало |
| `FullDirectoryIndex`: `DirName` | `FString` с `\x00` (`null=True`), включает `'/'` и родительские папки (`pakchunk166`, `pakchunk165`, `pakchunk0`) | `null=True`, но **без `'/'` и без промежуточных папок** | Добавлены `'/'` и промежуточные папки | **Исправлено** |
| **`FullDirectoryIndex`: `FileName`** | **`FString` БЕЗ `\x00` (`null=False`)** | **С лишним `\x00` (`null=True`)** | **`null=False` (без `\x00`)** | **Исправлено (критично)** |

### Проверка воспроизведения байт в байт

После правки `tools/pak_v12.py` выполнена прямая проверка на исходных файлах из эталонных паков игры:
- **`pakchunk82-Windows.pak` (3 файла, `1 310` Б):** воспроизведённый через `pak_v12.build_pak_v12` архив совпал **100% байт в байт** (`1310 == 1310`, `EXACT_MATCH=True`).
- **`pakchunk1-Windows.pak` (0 файлов, `MountPoint='/'`, `339` Б):** воспроизведён **100% байт в байт** (`339 == 339`, `EXACT_MATCH=True`).
- **`pakchunk166-Windows.pak` (5 файлов UI, 4 директории в `FD`):** размеры `PathHashIndex` (`68` Б) и `FullDirectoryIndex` (`195` Б) и порядок директорий/файлов совпадают полностью.

---

## 3. Точки монтирования (`MountPoint`), регистр и хэширование путей

Проверка всех **238 `.pak`** в `HassleOnline/Content/Paks/`:
- `'../../../'` — 1 пак (`pakchunk0-Windows.pak`, 1 827 файлов, в т.ч. `HassleOnline/Content/UserInterface/LoadingScreen/...`).
- `'/'` — 86 пустых паков (0 файлов внутри `.pak`, ресурсы в `.utoc/.ucas`).
- `'../../../HassleOnline/Content/'` — 134 пака (`pakchunk2..164` не пустые, по 3 `.stinfo`).
- `'../../../HassleOnline/Content/RawData/'` — 1 пак (`pakchunk165-Windows.pak`, 153 JSON).
- `'../../../HassleOnline/Content/UserInterface/Main/'` — **16 паков (`pakchunk166..181-Windows.pak`)**, весь UI `Main`.

**Правило регистра и хэша пути (`pak_path_hash`):**
- В `pakchunk166-Windows.pak` присутствует файл со смешанным регистром `videos/helloween/HasslehalloweenCut1.mp4`. Его реальный хэш в `PathHashIndex` при `seed=0xafd21759` равен `0x6ec8709b98534ff4`, что точно совпадает с `FNV-1a 64-bit` по **`rel_path.lower()` в UTF-16LE** с начальным значением `(0xCBF29CE484222325 + seed) & 0xFFFFFFFFFFFFFFFF`.
- Для единого пилота, объединяющего и `UserInterface/LoadingScreen/...`, и `UserInterface/Main/...`, `MountPoint = "../../../HassleOnline/Content/"` разрешается в те же виртуальные пути UE (`../../../HassleOnline/Content/UserInterface/...`), что и `pakchunk82..164`.

---

## 4. Имена файлов в `Content/Paks/` и `manifest.json` лаунчера

По `Hassle Online/manifest.json` (`build: 2.1.0.8`, 755 записей):
- В `HassleOnline/Content/Paks/` перечислено **716 файлов**: `global.utoc` (842 Б), `global.ucas` (3 531 376 Б) и **238** троек `.pak/.utoc/.ucas`.
- Чанки пронумерованы непрерывно **`pakchunk0-Windows` .. `pakchunk182-Windows`** (183 основных чанка) + **55** сплитов **`pakchunk<N>_s1-Windows`** / **`_s2-Windows`** (например, `pakchunk106_s1-Windows.pak`, `pakchunk141_s2-Windows.pak`).
- Не-`pakchunk` `.pak`-файлов в штатной поставке **нет** (`0`).

---

## 5. Ограничения загрузки по строкам `HassleOnline-Win64-Shipping.exe`

Проверены UTF-16LE и ASCII строки бинарника (`182 231 472` Б, только чтение):
- `~mods`: **0 совпадений**.
- Пути сканирования паков (`0x7fcf1b8`–`0x7fcfa60`): `%sPaks/`, `%sPaks/global.utoc`, `%sPaks/%s-`, а также `_P.pak` (`0x7fcf790`) и `Mounting pak file: %s `.
- Проверка IoStore (`0x7f1b1a8`–`0x7fcf800`): `utoc not found` (идёт сразу после `_P.pak`), `Failed to open IoStore container file '`, `Failed to open IoStore TOC file '`.
- Консольная переменная (`0x7fcaf20`–`0x7fcaff8`): `pak.AllowMissingUToc` (*«Enables mounting a .pak file without the corresponding .utoc file even if the I/O dispatcher is enabled»*).
- Сетевой флаг UI (обнаружен в разведке EXE ранее): `bUseRemoteUserInterface` / `RemoteUserInterfaceAddress` / `coui://LoadingScreen/index.html` / `coui://Main/index.html`.
- Файлов подписи `.sig` в `Content/Paks/` нет (`0`).

---

## 6. Генератор пустого IoStore-контейнера (`tools/iostore_empty.py`) vs `pakchunk166-Windows`

После подтверждения **Варианта A2** реализован автономный генератор `tools/iostore_empty.py` (без копирования файлов игры).

### Побайтное сравнение `.utoc` (240 Б) и `.ucas` (64 Б)

Проверено против всех `16` пустых UI-контейнеров игры (`pakchunk166-Windows` .. `pakchunk181-Windows`): при подстановке оригинального `ContainerId` генератор `build_empty_iostore_bytes(cid)` даёт **100% совпадение байт в байт** со всеми `16` парами `.utoc/.ucas`.

Для наших паков (`zzz_OneasPort_loading_screen_P`, `cid=0x5ae2b8902ac6fc10`; `zzz_OneasPort_ui_sounds_P`, `cid=0xe80dc8e2a3ea8346`) единственные отличия от `pakchunk166-Windows.{utoc,ucas}` (`cid=0x82c07d140e3d3d80`):

| Файл | Смещение (байты) | Поле структуры UE 5.8 | Зачем отличается |
|---|---|---|---|
| `.ucas` (64 Б) | `8..15` (8 Б) | `FIoContainerHeader.ContainerId` (`uint64`) | Уникальный стабильный ID нашего мод-контейнера (SHA-256 от `"oneas_iostore:<pak_stem>"`, первые 8 байт LE) |
| `.utoc` (240 Б) | `56..63` (8 Б) | `FIoStoreTocHeader.ContainerId` (`uint64`) | Тот же уникальный `ContainerId` в заголовке TOC (`v8`) |
| `.utoc` (240 Б) | `144..151` (8 Б) | `ChunkIds[0]` (`FIoChunkId`, 12 Б) | `ContainerId` внутри `FIoChunkId` единственной записи `EIoChunkType::ContainerHeader` (`type=6`) |
| `.utoc` (240 Б) | `216..235` (20 Б) | `ChunkMetas[0].ChunkHash` (`FIoChunkHash`) | Первые `20` байт **BLAKE3-256** от нашего 64-байтного `.ucas` (меняется, т.к. внутри `.ucas` лежит наш `ContainerId`) |

Все остальные `56` байт `.ucas` (`nCoI`, `ver=5`, нулевые списки пакетов и смещение редиректов `0x3C`) и `204` байта `.utoc` (magic `-==--==--==--==-`, `Version=8`, `TocHeaderSize=144`, `TocEntryCount=1`, `DirectoryIndexSize=34`, `ContainerFlags=Indexed`, `PartitionSize=MAX_uint64`) полностью идентичны `pakchunk166..181-Windows`.
