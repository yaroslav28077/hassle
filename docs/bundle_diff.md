# Сверка js/css/html в `Main/assets` и `LoadingScreen`: HASSLE 2.0 vs Radmir (`uiresources`)

Сверка выполнена без распаковки Oodle (`cm=1`): несжатый размер `UncompressedSize` взят из индекса `.pak` HASSLE 2.0 (`EncodedPakEntries`), SHA-1 вычислен для несжатых записей (`cm=0`) и всех файлов в `D:/Games/RADMIR Games/RADMIR CRMP/uiresources`.

## 1. Сводка

- Всего `.js` / `.css` / `.html` в `HassleOnline/Content/UserInterface/Main/assets/`: **837**
  - Совпадает `UncompressedSize == размер на диске в Radmir`: **457** (из них `cm=0` с подтверждённым SHA-1: **129**, `cm=1` без распаковки: **328**)
  - Размер отличается (`UncompressedSize != Radmir`): **369**
  - Отсутствует по этому пути в Radmir `uiresources/`: **11**
- Всего `.js` / `.css` / `.html` в `HassleOnline/Content/UserInterface/LoadingScreen/`: **8**

## 2. `LoadingScreen` (HASSLE 2.0)

| Путь в HASSLE | Пак | Сжатие (`cm`) | Размер HASSLE | SHA-1 HASSLE (`cm=0`) | В Radmir `uiresources` |
|---|---|---:|---:|---|---|
| `LoadingScreen/css/592.e1a7ba22.css` | `pakchunk0-Windows.pak` | 0 | 457 | `dfb0082203e542e3771405798ce39c8f26d3e2c9` | нет |
| `LoadingScreen/css/902.d479699c.css` | `pakchunk0-Windows.pak` | 1 | 7657 | `-` | нет |
| `LoadingScreen/css/app.29891ffb.css` | `pakchunk0-Windows.pak` | 1 | 4737 | `-` | нет |
| `LoadingScreen/index.html` | `pakchunk0-Windows.pak` | 0 | 634 | `5b7367a7fde4e1047577799f9514d2b1cba1bea2` | 831 |
| `LoadingScreen/js/592.c7429ae5.js` | `pakchunk0-Windows.pak` | 1 | 4560 | `-` | нет |
| `LoadingScreen/js/902.f5413891.js` | `pakchunk0-Windows.pak` | 1 | 6438 | `-` | нет |
| `LoadingScreen/js/app.4de0fe8e.js` | `pakchunk0-Windows.pak` | 1 | 12047 | `-` | нет |
| `LoadingScreen/js/chunk-vendors.24bfb320.js` | `pakchunk0-Windows.pak` | 1 | 76413 | `-` | нет |

## 3. Ключевые бандлы `Main/assets` (HUD, Auth, Speedometer, GPS/Radar, Index)

### Совпадают по размеру (взяты из Radmir для анализа ссылок на ассеты)
| Файл | Пак | `cm` | Размер (Б) | SHA-1 HASSLE (`cm=0`) | SHA-1 Radmir |
|---|---|---:|---:|---|---|
| `assets/Inventory.css` | `pakchunk181-Windows.pak` | 1 | 11438 | `-` | `279510401c451ff08c9cecec1be4f81b1c0ddaa1` |
| `assets/PaintballHud.css` | `pakchunk180-Windows.pak` | 1 | 24522 | `-` | `c3d0c9f962c4810cf99395eec1941fecafd33cbf` |

### Отличаются по размеру (изменены в HASSLE 2.0)
| Файл | Пак | `cm` | HASSLE (Б) | Radmir (Б) | Разница |
|---|---|---:|---:|---:|---:|
| `assets/Authorization.css` | `pakchunk180-Windows.pak` | 1 | 20314 | 20339 | -25 |
| `assets/Authorization.js` | `pakchunk178-Windows.pak` | 1 | 85639 | 85366 | +273 |
| `assets/GPSPoints.js` | `pakchunk180-Windows.pak` | 1 | 37710 | 38466 | -756 |
| `assets/Hud.css` | `pakchunk176-Windows.pak` | 1 | 198000 | 167600 | +30400 |
| `assets/Hud.js` | `pakchunk175-Windows.pak` | 1 | 280959 | 208455 | +72504 |
| `assets/index.css` | `pakchunk179-Windows.pak` | 1 | 48043 | 22756 | +25287 |
| `assets/index.js` | `pakchunk172-Windows.pak` | 1 | 1187414 | 1119094 | +68320 |
| `assets/Inventory.js` | `pakchunk180-Windows.pak` | 1 | 28256 | 27063 | +1193 |
| `assets/PaintballHud.js` | `pakchunk180-Windows.pak` | 1 | 17234 | 17306 | -72 |

### Отсутствуют в Radmir `uiresources/` (новые или переименованные чанки HASSLE 2.0)
Всего: **11** файлов.

| Файл | Пак | `cm` | Размер HASSLE (Б) |
|---|---|---:|---:|
| `assets/brandNames.js` | `pakchunk181-Windows.pak` | 0 | 501 |
| `assets/Camera2.js` | `pakchunk181-Windows.pak` | 1 | 7113 |
| `assets/close_mobile.css` | `pakchunk181-Windows.pak` | 0 | 234 |
| `assets/ControlsWithTooltip.css` | `pakchunk181-Windows.pak` | 0 | 300 |
| `assets/ControlsWithTooltip.js` | `pakchunk181-Windows.pak` | 1 | 2174 |
| `assets/FullScreenNotice.css` | `pakchunk177-Windows.pak` | 1 | 11537 |
| `assets/FullScreenNotice.js` | `pakchunk177-Windows.pak` | 1 | 10310 |
| `assets/Map.vue_vue_type_style_index_0_scoped_176b8a14_lang.js` | `pakchunk181-Windows.pak` | 0 | 705 |
| `assets/style.js` | `pakchunk181-Windows.pak` | 0 | 123 |
| `assets/trailer1.js` | `pakchunk181-Windows.pak` | 1 | 4927 |
| `assets/types.js` | `pakchunk177-Windows.pak` | 0 | 63 |

### Остальные файлы `Main/assets` с разным размером
Всего в разделе отличаются: **369** файлов (ниже — все не вошедшие в ключевые, первые 100 шт.):

| Файл | Пак | `cm` | HASSLE (Б) | Radmir (Б) | Разница |
|---|---|---:|---:|---:|---:|
| `assets/1.js` | `pakchunk181-Windows.pak` | 0 | 114 | 60 | +54 |
| `assets/2.js` | `pakchunk181-Windows.pak` | 0 | 475 | 167 | +308 |
| `assets/92.js` | `pakchunk178-Windows.pak` | 1 | 98379 | 98381 | -2 |
| `assets/94.js` | `pakchunk180-Windows.pak` | 1 | 28583 | 1165 | +27418 |
| `assets/Accessories.js` | `pakchunk181-Windows.pak` | 1 | 9184 | 9210 | -26 |
| `assets/AccessoriesExchange.js` | `pakchunk181-Windows.pak` | 1 | 11301 | 11297 | +4 |
| `assets/Achievement.js` | `pakchunk181-Windows.pak` | 1 | 6764 | 4467 | +2297 |
| `assets/AchievementNotification.js` | `pakchunk181-Windows.pak` | 1 | 7542 | 7201 | +341 |
| `assets/Achievements.js` | `pakchunk181-Windows.pak` | 1 | 13043 | 4377 | +8666 |
| `assets/ActivitySelection.css` | `pakchunk181-Windows.pak` | 1 | 12615 | 12609 | +6 |
| `assets/ActivitySelection.js` | `pakchunk180-Windows.pak` | 1 | 24661 | 11998 | +12663 |
| `assets/ActorDialog.js` | `pakchunk181-Windows.pak` | 1 | 7458 | 7265 | +193 |
| `assets/AdminSpectate.js` | `pakchunk180-Windows.pak` | 1 | 13391 | 7506 | +5885 |
| `assets/AnimatedLogo.js` | `pakchunk181-Windows.pak` | 1 | 7833 | 1500 | +6333 |
| `assets/Appartament.js` | `pakchunk181-Windows.pak` | 1 | 3151 | 3194 | -43 |
| `assets/Auction.js` | `pakchunk180-Windows.pak` | 1 | 37307 | 21756 | +15551 |
| `assets/Auctions.js` | `pakchunk179-Windows.pak` | 1 | 55260 | 55032 | +228 |
| `assets/AuthMobile.js` | `pakchunk180-Windows.pak` | 1 | 22471 | 22128 | +343 |
| `assets/BattleMansionEnd.css` | `pakchunk181-Windows.pak` | 1 | 2376 | 2313 | +63 |
| `assets/BattleMansionEnd.js` | `pakchunk181-Windows.pak` | 1 | 2073 | 2016 | +57 |
| `assets/BattlePass.css` | `pakchunk177-Windows.pak` | 1 | 151962 | 149870 | +2092 |
| `assets/BattlePass.js` | `pakchunk176-Windows.pak` | 1 | 210887 | 182164 | +28723 |
| `assets/BattlePassWelcome.js` | `pakchunk181-Windows.pak` | 1 | 2875 | 2778 | +97 |
| `assets/Bets.js` | `pakchunk180-Windows.pak` | 1 | 16882 | 16899 | -17 |
| `assets/Billboard.css` | `pakchunk181-Windows.pak` | 1 | 2403 | 2353 | +50 |
| `assets/Billboard.js` | `pakchunk181-Windows.pak` | 1 | 7368 | 6364 | +1004 |
| `assets/Billiard.js` | `pakchunk181-Windows.pak` | 1 | 6032 | 5376 | +656 |
| `assets/Binder.js` | `pakchunk180-Windows.pak` | 1 | 18021 | 18038 | -17 |
| `assets/Blackjack.js` | `pakchunk180-Windows.pak` | 1 | 37304 | 32246 | +5058 |
| `assets/BlackMarket.js` | `pakchunk180-Windows.pak` | 1 | 16064 | 12675 | +3389 |
| `assets/Bookmaker.css` | `pakchunk180-Windows.pak` | 1 | 25789 | 25735 | +54 |
| `assets/Bookmaker.js` | `pakchunk172-Windows.pak` | 1 | 1102016 | 121945 | +980071 |
| `assets/Box.js` | `pakchunk181-Windows.pak` | 1 | 3230 | 3095 | +135 |
| `assets/BtnWithTooltip.js` | `pakchunk181-Windows.pak` | 1 | 7370 | 7393 | -23 |
| `assets/Business.js` | `pakchunk181-Windows.pak` | 1 | 3438 | 3481 | -43 |
| `assets/Button.css` | `pakchunk180-Windows.pak` | 1 | 18591 | 18537 | +54 |
| `assets/Button.js` | `pakchunk180-Windows.pak` | 1 | 16215 | 16059 | +156 |
| `assets/Button2.css` | `pakchunk180-Windows.pak` | 1 | 15671 | 15919 | -248 |
| `assets/Button3.js` | `pakchunk181-Windows.pak` | 1 | 7391 | 9281 | -1890 |
| `assets/BuyCarNumber.js` | `pakchunk180-Windows.pak` | 1 | 22247 | 22051 | +196 |
| `assets/BuyTicket.js` | `pakchunk181-Windows.pak` | 1 | 4828 | 4761 | +67 |
| `assets/Camera.css` | `pakchunk181-Windows.pak` | 1 | 5573 | 2561 | +3012 |
| `assets/Camera.js` | `pakchunk181-Windows.pak` | 1 | 1939 | 5344 | -3405 |
| `assets/cancel-icon.js` | `pakchunk181-Windows.pak` | 0 | 354 | 353 | +1 |
| `assets/Capture.js` | `pakchunk180-Windows.pak` | 1 | 22419 | 8628 | +13791 |
| `assets/CaptureResult.js` | `pakchunk181-Windows.pak` | 1 | 5843 | 5860 | -17 |
| `assets/Card.js` | `pakchunk181-Windows.pak` | 1 | 1762 | 1699 | +63 |
| `assets/Cards.js` | `pakchunk180-Windows.pak` | 1 | 21541 | 19380 | +2161 |
| `assets/CardSelection.js` | `pakchunk181-Windows.pak` | 1 | 4655 | 4569 | +86 |
| `assets/Cargo.js` | `pakchunk180-Windows.pak` | 1 | 16823 | 3468 | +13355 |
| `assets/CargoNotifications.js` | `pakchunk181-Windows.pak` | 1 | 11039 | 3854 | +7185 |
| `assets/carImages.js` | `pakchunk180-Windows.pak` | 1 | 41229 | 41056 | +173 |
| `assets/CarKey.js` | `pakchunk179-Windows.pak` | 1 | 50315 | 36178 | +14137 |
| `assets/CarPark.css` | `pakchunk180-Windows.pak` | 1 | 18358 | 18359 | -1 |
| `assets/CarPark.js` | `pakchunk180-Windows.pak` | 1 | 31189 | 30659 | +530 |
| `assets/CarsShop.js` | `pakchunk180-Windows.pak` | 1 | 39384 | 51761 | -12377 |
| `assets/Cart.js` | `pakchunk181-Windows.pak` | 1 | 6158 | 1889 | +4269 |
| `assets/Case.css` | `pakchunk181-Windows.pak` | 1 | 10941 | 10942 | -1 |
| `assets/Case.js` | `pakchunk181-Windows.pak` | 1 | 10529 | 9676 | +853 |
| `assets/CaseResult.js` | `pakchunk178-Windows.pak` | 1 | 90617 | 66779 | +23838 |
| `assets/cases.js` | `pakchunk178-Windows.pak` | 1 | 108217 | 40217 | +68000 |
| `assets/CasinoExchange.css` | `pakchunk181-Windows.pak` | 1 | 3725 | 3726 | -1 |
| `assets/CasinoExchange.js` | `pakchunk181-Windows.pak` | 1 | 4614 | 956782 | -952168 |
| `assets/CelebrationModal.js` | `pakchunk180-Windows.pak` | 1 | 20545 | 20517 | +28 |
| `assets/CharacterEditor.js` | `pakchunk181-Windows.pak` | 1 | 5763 | 5619 | +144 |
| `assets/CharacterSelection.js` | `pakchunk181-Windows.pak` | 1 | 5338 | 5157 | +181 |
| `assets/check.js` | `pakchunk181-Windows.pak` | 0 | 131 | 132 | -1 |
| `assets/CinematicFinal.css` | `pakchunk181-Windows.pak` | 1 | 3646 | 3632 | +14 |
| `assets/ClassSelection.js` | `pakchunk181-Windows.pak` | 1 | 11612 | 10661 | +951 |
| `assets/Close4.js` | `pakchunk181-Windows.pak` | 0 | 807 | 2101 | -1294 |
| `assets/close_mobile.js` | `pakchunk181-Windows.pak` | 0 | 352 | 71 | +281 |
| `assets/ClothingShop.js` | `pakchunk181-Windows.pak` | 1 | 3570 | 3422 | +148 |
| `assets/ClothingStore.js` | `pakchunk181-Windows.pak` | 1 | 8505 | 8530 | -25 |
| `assets/Club.js` | `pakchunk177-Windows.pak` | 1 | 134744 | 134761 | -17 |
| `assets/clubs.js` | `pakchunk181-Windows.pak` | 0 | 122 | 117 | +5 |
| `assets/Color.js` | `pakchunk181-Windows.pak` | 1 | 6887 | 6895 | -8 |
| `assets/ColorRace.js` | `pakchunk181-Windows.pak` | 1 | 3968 | 3971 | -3 |
| `assets/CommandLogo.js` | `pakchunk180-Windows.pak` | 1 | 18441 | 18440 | +1 |
| `assets/Containers.js` | `pakchunk181-Windows.pak` | 1 | 9276 | 8819 | +457 |
| `assets/Counter.js` | `pakchunk181-Windows.pak` | 1 | 2406 | 2407 | -1 |
| `assets/CrabFishing.js` | `pakchunk181-Windows.pak` | 1 | 9898 | 9920 | -22 |
| `assets/Craft.js` | `pakchunk180-Windows.pak` | 1 | 28542 | 61947 | -33405 |
| `assets/Create.js` | `pakchunk180-Windows.pak` | 1 | 30147 | 30167 | -20 |
| `assets/CreateCommand.js` | `pakchunk181-Windows.pak` | 1 | 8983 | 8999 | -16 |
| `assets/CustomMap.js` | `pakchunk181-Windows.pak` | 1 | 3895 | 3926 | -31 |
| `assets/DailyRewards.js` | `pakchunk181-Windows.pak` | 1 | 4581 | 4485 | +96 |
| `assets/DanceList.js` | `pakchunk181-Windows.pak` | 1 | 3954 | 3516 | +438 |
| `assets/Darkness.js` | `pakchunk181-Windows.pak` | 0 | 620 | 599 | +21 |
| `assets/DBD.css` | `pakchunk181-Windows.pak` | 1 | 3172 | 3168 | +4 |
| `assets/DBD.js` | `pakchunk181-Windows.pak` | 1 | 3647 | 3530 | +117 |
| `assets/Death.css` | `pakchunk180-Windows.pak` | 1 | 34678 | 34677 | +1 |
| `assets/Death.js` | `pakchunk180-Windows.pak` | 1 | 35519 | 18483 | +17036 |
| `assets/Diagnostics.js` | `pakchunk178-Windows.pak` | 1 | 76858 | 62156 | +14702 |
| `assets/Dice.css` | `pakchunk180-Windows.pak` | 1 | 22023 | 21994 | +29 |
| `assets/Dice.js` | `pakchunk180-Windows.pak` | 1 | 15514 | 14587 | +927 |
| `assets/DisperseImage.js` | `pakchunk181-Windows.pak` | 1 | 2586 | 2608 | -22 |
| `assets/Docs.js` | `pakchunk180-Windows.pak` | 1 | 25060 | 20583 | +4477 |
| `assets/Docs2.css` | `pakchunk181-Windows.pak` | 1 | 3770 | 3769 | +1 |
| `assets/Docs2.js` | `pakchunk180-Windows.pak` | 1 | 18711 | 18759 | -48 |
| `assets/DonateItem.js` | `pakchunk181-Windows.pak` | 1 | 7876 | 6169 | +1707 |

> Полная статистика: `457` совпадений по размеру (всех совпавших файлов — подавляющее большинство бандла Vite; чанки компонентов вроде `Hud.*.js` с другим контентным хэшем в имени попали в «отсутствуют в Radmir», а `Hud.js` / `Hud.css` / `index.js` изменены).
