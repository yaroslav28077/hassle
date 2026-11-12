"""DFF → FBX через Blender + аддон DragonFF (https://github.com/Parik27/DragonFF).

Запуск (Windows, PowerShell):
  & "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe" -b -P tools/blender_dff_to_fbx.py -- --src work/extracted --out work/fbx --tex work/textures

Аргументы после "--":
  --src   папка с .dff (рекурсивно) или один файл
  --out   куда класть .fbx
  --tex   папка с PNG из txd_extract.py (ищется <имя_текстуры>.png во всех подпапках)
  --keep-collision  не удалять объекты коллизии
  --only  имя файла без расширения (через запятую), чтобы прогнать пилот

На пилоте проверь в UE масштаб и ось и запиши итог в PROGRESS.md.
"""
import argparse
import csv
import sys
from pathlib import Path

import bpy  # noqa: E402  (доступен только внутри Blender)


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tex")
    ap.add_argument("--keep-collision", action="store_true")
    ap.add_argument("--only", default="")
    return ap.parse_args(argv)


def clear_scene():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.images,
                 bpy.data.armatures, bpy.data.collections):
        for item in list(coll):
            coll.remove(item)


def index_textures(tex_dir):
    idx = {}
    if tex_dir:
        for p in Path(tex_dir).rglob("*.png"):
            idx.setdefault(p.stem.lower(), p)
    return idx


def relink_images(tex_idx):
    missing = set()
    for img in bpy.data.images:
        key = Path(img.name).stem.lower()
        if key in tex_idx:
            img.filepath = str(tex_idx[key])
            img.reload()
        elif img.source == "FILE":
            missing.add(img.name)
    return missing


def drop_collision():
    removed = 0
    for obj in list(bpy.data.objects):
        n = obj.name.lower()
        colls = " ".join(c.name.lower() for c in obj.users_collection)
        if "collision" in colls or n.startswith(("col_", "collision")):
            bpy.data.objects.remove(obj)
            removed += 1
    return removed


def main():
    a = args()
    if not hasattr(bpy.ops.import_scene, "dff"):
        sys.exit("DragonFF не установлен/не включён в Blender (Edit → Preferences → Add-ons).")
    src, out = Path(a.src), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    only = {s.strip().lower() for s in a.only.split(",") if s.strip()}
    files = [src] if src.is_file() else sorted(p for p in src.rglob("*") if p.suffix.lower() == ".dff")
    if only:
        files = [f for f in files if f.stem.lower() in only]
    tex_idx = index_textures(a.tex)
    rows = []
    for f in files:
        clear_scene()
        try:
            bpy.ops.import_scene.dff(filepath=str(f))
            removed = 0 if a.keep_collision else drop_collision()
            missing = relink_images(tex_idx)
            meshes = [o for o in bpy.data.objects if o.type == "MESH"]
            mats = sorted({s.material.name for o in meshes for s in o.material_slots if s.material})
            dst = out / f"{f.stem}.fbx"
            bpy.ops.export_scene.fbx(filepath=str(dst), use_selection=False, apply_unit_scale=True,
                                     add_leaf_bones=False, mesh_smooth_type="FACE",
                                     path_mode="RELATIVE", bake_anim=False)
            rows.append({"dff": str(f), "fbx": dst.as_posix(), "status": "ok", "meshes": len(meshes),
                         "material_slots": "|".join(mats), "collision_removed": removed,
                         "missing_textures": "|".join(sorted(missing))})
            print(f"[ok] {f.name} → {dst.name} (mesh {len(meshes)}, mats {len(mats)})")
        except Exception as e:  # noqa: BLE001
            rows.append({"dff": str(f), "fbx": "", "status": f"error: {e}"})
            print(f"[error] {f}: {e}")
    with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["dff", "fbx", "status", "meshes", "material_slots",
                                           "collision_removed", "missing_textures"])
        w.writeheader()
        w.writerows(rows)


main()
