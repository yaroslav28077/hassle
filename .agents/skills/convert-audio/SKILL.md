---
name: convert-audio
description: "Фаза 4. Конвертация звуков сборки (выстрелы, попадания, UI-звуки) в WAV 48 кГц с подгонкой громкости и длины под оригинальные звуки HASSLE 2.0."
---

# Фаза 4: звуки

1. Замерь громкость 2–3 оригинальных звуков HASSLE того же типа (из `game_ref/originals/`):
   `ffmpeg -i <файл> -af loudnorm=print_format=summary -f null -` → `Input Integrated` (LUFS).
2. Конвертация:
   - 3D (выстрелы, попадания, шаги): `python tools/audio_convert.py source/<папка_звуков> work/audio --mono --loudnorm <LUFS>`
   - UI и музыка: без `--mono`.
3. Сверь длительности в `work/audio/manifest.csv` с оригиналами. Если звук выстрела заметно длиннее слота (автоматический огонь), обрежь хвост с fade-out (`ffmpeg -af afade=t=out:st=<t>:d=0.05`).
4. Убедись, что атака в начале (без тишины): `ffmpeg -af silenceremove=start_periods=1:start_threshold=-50dB`.
5. Если в HASSLE звук оружия это SoundCue/MetaSound из нескольких WAV, заменяй сами SoundWave внутри (их пути в FModel), а не Cue.
6. Статусы → `todo`.
