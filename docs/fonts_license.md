# Лицензии и метаданные шрифтов исходной сборки (`0.1.0` — не подключаются)

В версии `0.1.0` шрифты сборки ONEAS **не подключаются** (`status=skip`, `no_slot` в [asset_map.csv](../mapping/asset_map.csv)): в HASSLE 2.0 используются системные бандл-шрифты (`OpenSans`, `HassleOpenSans`, `Roboto`, `Caveat`). Ниже зафиксированы метаданные SFNT (`OS/2 fsType` и таблица `name`) всех 16 файлов из `uiresources/fonts/` на случай возможного подключения в будущих версиях.

| ID | Файл | Семейство / Начертание | `OS/2 fsType` | Правообладатель (из SFNT `name`) | Примечание для будущих версий |
|---|---|---|---:|---|---|
| `fnt_0426` | `Akrobat-Black.otf` | Akrobat / Black | `8` (Editable) | Copyright (c) 2016 by Fontfabric LLC | Семейство Fontfabric (бесплатное базовое распространение по EULA производителя; проверять условия редистрибуции в модах) |
| `fnt_0427` | `Akrobat-Bold.otf` | Akrobat / Bold | `8` (Editable) | Copyright (c) 2016 by Fontfabric LLC | То же |
| `fnt_0428` | `Akrobat-ExtraBold.otf` | Akrobat / ExtraBold | `8` (Editable) | Copyright (c) 2016 by Fontfabric LLC | То же |
| `fnt_0429` | `Akrobat-ExtraLight.otf` | Akrobat / ExtraLight | `8` (Editable) | Copyright (c) 2016 by Fontfabric LLC | То же |
| `fnt_0430` | `Akrobat-Light.otf` | Akrobat / Light | `8` (Editable) | Copyright (c) 2016 by Fontfabric LLC | То же |
| `fnt_0431` | `Akrobat-Regular.otf` | Akrobat / Regular | `8` (Editable) | Copyright (c) 2016 by Fontfabric LLC | То же |
| `fnt_0432` | `Akrobat-SemiBold.otf` | Akrobat / SemiBold | `8` (Editable) | Copyright (c) 2016 by Fontfabric LLC | То же |
| `fnt_0433` | `Akrobat-Thin.otf` | Akrobat / Thin | `8` (Editable) | Copyright (c) 2016 by Fontfabric LLC | То же |
| `fnt_0434` | `ALSRubl.ttf` | ALS Rubl / Regular | `0` (Installable) | Copyright (c) 2007 by ALS | Знак рубля (`₽`); в `0.1.0` используется Unicode `₽` штатным шрифтом HUD |
| `fnt_0435` | `GothamPro-Black.ttf` | Gotham Pro Black / Regular | `4` (Preview & Print) | Copyright (c) 2003 The Hoefler Type Foundry, Inc. | Коммерческая гарнитура (Hoefler & Co); перед публичным включением в открытый мод-пак рекомендуется замена на свободный геометрический гротеск (например, Montserrat / Inter) |
| `fnt_0436` | `GothamPro-BlackItalic.ttf` | Gotham Pro Black / Italic | `4` (Preview & Print) | Copyright (c) 2003 The Hoefler Type Foundry, Inc. | То же |
| `fnt_0437` | `GothamPro-Bold.ttf` | Gotham Pro / Bold | `4` (Preview & Print) | Copyright (c) 2000 The Hoefler Type Foundry, Inc. | То же |
| `fnt_0438` | `GothamPro-Light.ttf` | Gotham Pro Light / Regular | `4` (Preview & Print) | Copyright (c) 2000 The Hoefler Type Foundry, Inc. | То же |
| `fnt_0439` | `GothamPro-LightItalic.ttf` | Gotham Pro Light / Italic | `4` (Preview & Print) | Copyright (c) 2002 The Hoefler Type Foundry, Inc. | То же |
| `fnt_0440` | `GothamPro-Medium.ttf` | Gotham Pro Medium / Regular | `4` (Preview & Print) | Copyright (c) 2000 The Hoefler Type Foundry, Inc. | То же |
| `fnt_0441` | `GothamPro.ttf` | Gotham Pro / Regular | `4` (Preview & Print) | Copyright (c) 2000 The Hoefler Type Foundry, Inc. | То же |
