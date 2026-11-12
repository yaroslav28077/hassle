# Справка по форматам

## RenderWare (GTA SA)
Чанк: `u32 type, u32 size, u32 libraryStamp`. Версия SA: stamp `0x1803FFFF` → 3.6.0.3.

| type | чанк |
|---|---|
| 0x01 | Struct |
| 0x03 | Extension |
| 0x10 | Clump (DFF) |
| 0x15 | Texture Native |
| 0x16 | Texture Dictionary (TXD) |

**Texture Native (ПК)**, содержимое Struct:
`u32 platform (9 = D3D9/SA, 8 = D3D8/III-VC)`, `u32 filter/addressing`, `char name[32]`, `char mask[32]`,
`u32 rasterFormat`, `u32 d3dFormat (SA: FourCC 'DXT1'/'DXT3'/'DXT5' или D3DFMT) | hasAlpha (D3D8)`,
`u16 w, u16 h, u8 depth, u8 mipLevels, u8 rasterType, u8 flags (SA: bit0 alpha, bit3 compressed | D3D8: DXT-тип)`,
`[палитра 1024 или 64 байт]`, затем на каждый мип `u32 size + данные`.

rasterFormat & 0x0F00: `0x100` 1555, `0x200` 565, `0x300` 4444, `0x400` LUM8, `0x500` 8888 (BGRA), `0x600` 888 (BGRX), `0xA00` 555. Флаги: `0x2000` PAL8, `0x4000` PAL4, `0x8000` мипы.

**IMG v2**: `"VER2"`, `u32 count`, записи по 32 байта: `u32 offset (сектора по 2048)`, `u16 streamingSize`, `u16 sizeInArchive`, `char name[24]`.

Единицы: метры, Z вверх. В UE сантиметры, Z вверх.

## Unreal Engine
- **.pak**: footer в конце файла, магия `0x5A6F12E1`; перед магией байт `bEncryptedIndex` и 16 байт GUID ключа; после магии версия пака.
- **IoStore**: `.utoc` (оглавление, магия `-==--==--==--==-`, байт флагов на смещении 80: 1 Compressed, 2 Encrypted, 4 Signed, 8 Indexed) + `.ucas` (данные) + маленький `.pak`.
- **.sig**: подпись пака, игра с подписью отвергнет чужие паки.
- Cooked-ассет: `.uasset` (заголовок) + `.uexp` (данные) + иногда `.ubulk` (большие данные, мипы).
- Приоритет: паки с суффиксом `_P` грузятся позже и перекрывают остальные; внутри одного приоритета по алфавиту.

## Инструменты
- FModel: просмотр/экспорт ассетов из незашифрованных паков (выбрать версию UE игры).
- UnrealPak (в комплекте движка): `-List`, `-Extract`, `-create=<filelist>`.
- repak / retoc (open-source): альтернатива UnrealPak для pak и IoStore.
- DragonFF (Blender): импорт/экспорт DFF, TXD, COL.
