"""Фаза 3. Создаёт/дополняет mapping/asset_map.csv из манифестов конвертации и инвентаря.

python tools/map_init.py

Уже заполненные строки (target_package, status, notes) не перезаписываются: добавляются только новые.
"""
from __future__ import annotations

import csv
from pathlib import Path

from common import ROOT, get_logger

FIELDS = ["id", "category", "variant", "source_file", "converted_file", "target_package",
          "asset_type", "texture_group", "width", "height", "status", "notes"]
MAP = ROOT / "mapping" / "asset_map.csv"
W = ROOT / "work"


def read(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def guess_group(path: str) -> str:
    s = path.lower()
    if any(k in s for k in ("hud", "radar", "interface", "ui", "menu", "inventory", "dialog", "auth", "icon", "font")):
        return "UI"
    if any(k in s for k in ("cross", "sight", "aim", "pricel", "прицел")):
        return "UI"
    return "World"


def guess_variant(path: str) -> str:
    s = path.lower()
    for v in ("basic", "maximum", "max", "lite", "base"):
        if v in s:
            return v
    return ""


def main() -> None:
    log = get_logger("map_init")
    existing = read(MAP)
    known = {r["converted_file"] or r["source_file"] for r in existing}
    rows = list(existing)
    n0 = len(rows)

    def add(category, src, conv, atype, group="", w="", h="", notes=""):
        key = conv or src
        if key in known:
            return
        known.add(key)
        rows.append({"id": f"A{len(rows) + 1:05d}", "category": category, "variant": guess_variant(src),
                     "source_file": src, "converted_file": conv, "target_package": "",
                     "asset_type": atype, "texture_group": group, "width": w, "height": h,
                     "status": "todo" if conv else "todo_convert", "notes": notes})

    for r in read(W / "textures" / "manifest.csv"):
        add("texture", f"{r['txd']}::{r['texture']}", r["png"], "Texture2D", guess_group(r["txd"] + r["texture"]),
            r["width"], r["height"], f"format {r['format']}, alpha {r['has_alpha']}")
    for r in read(W / "fbx" / "manifest.csv"):
        if r["status"] == "ok":
            add("model", r["dff"], r["fbx"], "StaticMesh", notes=f"slots: {r.get('material_slots', '')}")
    for r in read(W / "audio" / "manifest.csv"):
        if r["status"] == "ok":
            add("audio", r["source"], r["wav"], "SoundWave", notes=f"{r.get('channels')}ch {r.get('duration_s')}s")
    for r in read(W / "inventory" / "inventory.csv"):
        if r["category"] == "image":
            add("image", f"source/{r['path']}", "", "Texture2D", guess_group(r["path"]))
        elif r["category"] in ("code_plugin", "collision", "map_def", "animation"):
            add(r["category"], f"source/{r['path']}", "", "", notes="skip по умолчанию (см. inventory summary)")

    for r in rows[n0:]:
        if r["category"] in ("code_plugin", "collision", "map_def", "animation"):
            r["status"] = "skip"
    MAP.parent.mkdir(exist_ok=True)
    with open(MAP, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    log.info("asset_map.csv: было %d, добавлено %d, всего %d", n0, len(rows) - n0, len(rows))


if __name__ == "__main__":
    main()
