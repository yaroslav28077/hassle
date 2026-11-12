"""Фаза 5. Импорт сконвертированных ассетов в UE-проект мода по target_package из asset_map.csv.

Запускается ВНУТРИ Unreal Editor (включи плагин "Python Editor Script Plugin"):
  - из консоли редактора:   py "C:/path/hassle-port/tools/ue_import.py"
  - или без окна:
    UnrealEditor-Cmd.exe "<proj>.uproject" -run=pythonscript -script="C:/path/hassle-port/tools/ue_import.py"

Берёт строки со статусом todo/converted и заполненными converted_file + target_package.
После успешного импорта ставит статус imported. Перед записью делает копию asset_map.csv.bak
Переменная окружения HASSLE_PORT_ONLY=A00001,A00002 — импортировать только эти id (пилот).
"""
import csv
import os
import shutil
from pathlib import Path

import unreal  # доступен только внутри редактора

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "mapping" / "asset_map.csv"
ONLY = {s.strip() for s in os.environ.get("HASSLE_PORT_ONLY", "").split(",") if s.strip()}

TC = unreal.TextureCompressionSettings
TG = unreal.TextureGroup


def split_package(pkg):
    pkg = pkg.strip().rstrip("/")
    if "." in pkg.rsplit("/", 1)[-1]:
        pkg = pkg.rsplit(".", 1)[0]
    folder, name = pkg.rsplit("/", 1)
    return folder, name


def configure_texture(asset, row):
    group = (row.get("texture_group") or "World").lower()
    if group == "ui":
        asset.set_editor_property("lod_group", TG.TEXTUREGROUP_UI)
        asset.set_editor_property("compression_settings", TC.TC_EDITOR_ICON)
        asset.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        asset.set_editor_property("srgb", True)
    elif group == "normal":
        asset.set_editor_property("compression_settings", TC.TC_NORMALMAP)
        asset.set_editor_property("srgb", False)
    else:
        asset.set_editor_property("lod_group", TG.TEXTUREGROUP_WORLD)
        asset.set_editor_property("compression_settings", TC.TC_DEFAULT)


def fbx_options(row):
    ui = unreal.FbxImportUI()
    skeletal = row.get("asset_type") == "SkeletalMesh"
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", skeletal)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("import_animations", False)
    ui.set_editor_property("automated_import_should_detect_type", False)
    ui.set_editor_property("mesh_type_to_import",
                           unreal.FBXImportType.FBXIT_SKELETAL_MESH if skeletal else unreal.FBXImportType.FBXIT_STATIC_MESH)
    if skeletal and row.get("notes", "").startswith("skeleton="):
        ui.set_editor_property("skeleton", unreal.load_asset(row["notes"].split("=", 1)[1].split()[0]))
    sm = ui.get_editor_property("static_mesh_import_data")
    sm.set_editor_property("combine_meshes", True)
    sm.set_editor_property("generate_lightmap_u_vs", True)
    return ui


def main():
    with open(MAP, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    fields = list(rows[0].keys()) if rows else []
    todo = [r for r in rows if r["status"] in ("todo", "converted") and r["converted_file"] and r["target_package"]
            and (not ONLY or r["id"] in ONLY)]
    unreal.log(f"[hassle-port] к импорту: {len(todo)}")
    tasks = []
    for r in todo:
        src = Path(r["converted_file"])
        if not src.is_absolute():
            src = ROOT / src
        if not src.exists():
            r["status"], r["notes"] = "blocked", f"нет файла {src}"
            continue
        folder, name = split_package(r["target_package"])
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", str(src))
        t.set_editor_property("destination_path", folder)
        t.set_editor_property("destination_name", name)
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("automated", True)
        t.set_editor_property("save", False)
        if src.suffix.lower() == ".fbx":
            t.set_editor_property("options", fbx_options(r))
        tasks.append((t, r))

    if tasks:
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t for t, _ in tasks])
    for t, r in tasks:
        paths = list(t.get_editor_property("imported_object_paths") or [])
        if not paths:
            r["status"] = "blocked"
            r["notes"] = (r["notes"] + " | импорт не удался, см. Output Log").strip(" |")
            continue
        asset = unreal.load_asset(paths[0])
        if isinstance(asset, unreal.Texture2D):
            configure_texture(asset, r)
        unreal.EditorAssetLibrary.save_loaded_asset(asset)
        r["status"] = "imported"

    shutil.copy(MAP, MAP.with_suffix(".csv.bak"))
    with open(MAP, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    ok = sum(r["status"] == "imported" for _, r in tasks)
    unreal.log(f"[hassle-port] импортировано: {ok} из {len(todo)}")


main()
