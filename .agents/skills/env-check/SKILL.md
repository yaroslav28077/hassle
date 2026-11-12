---
name: env-check
description: "Фаза 0. Проверка окружения перед началом работы: config.yaml, Python-пакеты, ffmpeg, Blender + DragonFF, Unreal Engine нужной версии, UnrealPak. Использовать в начале проекта и после смены ПК или версии движка."
---

# Фаза 0: проверка окружения

1. Если нет `config.yaml`, скопируй `config.example.yaml` → `config.yaml` и попроси пользователя заполнить пути (игра, Blender, ffmpeg, Unreal Engine). Не угадывай пути.
2. `pip install -r requirements.txt`
3. `python tools/env_check.py`
4. По каждому `[FAIL]` дай пользователю одну конкретную инструкцию:
   - ffmpeg: скачать сборку для Windows (gyan.dev или BtbN), указать путь к `ffmpeg.exe` в `tools.ffmpeg`.
   - Blender 4.2+: установить, в Edit → Preferences → Get Extensions найти **DragonFF**, включить.
   - Unreal Engine: версия **строго как у игры** (узнаем на фазе 2). До фазы 2 этот пункт может быть FAIL, это нормально.
5. Запиши результат в `PROGRESS.md`.

Готово, когда все пункты кроме UE-проекта `[OK]`.
