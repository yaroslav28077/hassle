"""Фаза 3/6 (Дорожка A): модульная сборка паков по build_options.yaml и mapping/asset_map.csv.

Использование:
    python tools/build_mod.py --options build_options.yaml
    python tools/build_mod.py --options build_options.yaml --preset basic
    python tools/build_mod.py --options build_options.yaml --preset maximum --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from common import ROOT, get_logger, load_config
from iostore_empty import build_empty_iostore, container_id_from_name
from pak_v12 import build_pak_v12


def detect_hassle_version(cfg: dict) -> str:
    """Прочитать версию HASSLE 2.0 из game_ref/target_report.md или папки игры (только чтение)."""
    install_dir = Path(cfg.get("game", {}).get("install_dir", ""))
    ver_file = install_dir / "version.txt"
    if ver_file.is_file():
        return ver_file.read_text(encoding="utf-8", errors="replace").strip()
    report = ROOT / "game_ref" / "target_report.md"
    if report.is_file():
        for line in report.read_text(encoding="utf-8", errors="replace").splitlines():
            if "UE" in line or "Unreal" in line:
                return line.strip("- #*")
    return f"{cfg.get('game', {}).get('project_name', 'HassleOnline')} (UE{cfg.get('ue', {}).get('engine_major', 5)})"


def resolve_options(opt_cfg: dict, preset_override: str | None) -> tuple[str, dict[str, object], dict[str, dict]]:
    """Вычислить итоговые значения всех опций и метаданные групп."""
    preset_name = preset_override or opt_cfg.get("active_preset") or "custom"
    presets = opt_cfg.get("presets") or {}
    if preset_name not in presets:
        raise SystemExit(f"Неизвестный пресет '{preset_name}'. Доступны: {', '.join(presets.keys())}")

    groups: dict[str, dict] = {}
    resolved: dict[str, object] = {}
    for g in opt_cfg.get("options", []):
        gid = str(g["id"])
        groups[gid] = g
        resolved[gid] = g.get("default")

    preset_opts = (presets[preset_name] or {}).get("options") or {}
    for gid, val in preset_opts.items():
        if gid not in groups:
            raise SystemExit(f"В пресете '{preset_name}' указана неизвестная опция '{gid}'")
        resolved[gid] = val

    # Валидация значений и доступности
    for gid, val in resolved.items():
        g = groups[gid]
        valid_vals = [v["value"] for v in g.get("variants", [])]
        if valid_vals and val not in valid_vals:
            raise SystemExit(f"Недопустимое значение '{val}' для опции '{gid}'. Допустимы: {valid_vals}")
        is_enabled = (val is True) or (isinstance(val, str) and val not in ("none", "false", ""))
        if is_enabled and not g.get("available", True):
            reason = g.get("unavailable_reason") or "опция отмечена как недоступная"
            raise SystemExit(f"Выбрана недоступная опция '{gid}={val}': {reason}")

    return preset_name, resolved, groups


def load_asset_map(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.is_file():
        raise SystemExit(f"Карта соответствий не найдена: {csv_path}")
    with open(csv_path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def select_rows(
    rows: list[dict[str, str]],
    resolved: dict[str, object],
    groups: dict[str, dict],
) -> tuple[dict[str, list[dict[str, str]]], dict[str, str], list[dict[str, str]]]:
    """Отобрать строки карты под активные опции и проверить конфликты и наличие исходников."""
    by_group: dict[str, list[dict[str, str]]] = {}
    matched_count: dict[str, int] = {gid: 0 for gid in groups}
    skipped_no_slot: list[dict[str, str]] = []

    for r in rows:
        og = (r.get("option_group") or "").strip()
        ov = (r.get("option_value") or "").strip()
        act = (r.get("action") or "").strip()
        st = (r.get("status") or "").strip()

        if og == "":
            # Базовая (core) часть Дорожки A
            # fix: пропускаем skip_user и строки со статусом skip/deferred
            if act in ("skip", "skip_user", "pending_B", "no_slot") or st in ("skip", "deferred"):
                continue
            by_group.setdefault("core", []).append(r)
            continue

        if og not in groups:
            raise SystemExit(f"Строка {r.get('id')} ссылается на неизвестную option_group='{og}' в asset_map.csv")

        sel = resolved[og]
        g_type = groups[og].get("type", "toggle")
        is_selected = False
        if g_type == "toggle":
            is_selected = sel is True and (ov in ("", "true"))
        elif g_type == "choice":
            is_selected = isinstance(sel, str) and sel not in ("none", "") and ov == sel
        elif g_type == "multi":
            is_selected = isinstance(sel, list) and ov in sel

        if not is_selected:
            continue

        # fix: допускаем documented no_slot внутри частично переносимых toggle-групп (weapon_icons, speedometer_bg)
        if act == "no_slot":
            skipped_no_slot.append(
                {
                    "id": r.get("id", ""),
                    "group": og,
                    "source_file": r.get("source_file", ""),
                    "notes": r.get("notes", ""),
                }
            )
            continue

        # fix: отложенные (deferred) и пропущенные (skip) строки (например 0.2 доп. окна или skip звуки) не пакуются
        if st in ("skip", "deferred"):
            continue

        matched_count[og] += 1
        # fix: разрешаем patch_text (пропатченные Hud.js/Hud.css/Authorization.css и доп. ресурсы ONEAS)
        if act not in ("replace_file", "patch_text"):
            raise SystemExit(
                f"Выбранный ассет '{r.get('id')}' ({og}={ov}) имеет action='{act}', а не 'replace_file'/'patch_text': {r.get('notes')}"
            )
        by_group.setdefault(og, []).append(r)

    # Проверяем, что ни одна включённая опция не осталась без строк/источников
    for gid, sel in resolved.items():
        g_type = groups[gid].get("type", "toggle")
        active = (sel is True) if g_type == "toggle" else (
            isinstance(sel, str) and sel not in ("none", "")
            if g_type == "choice"
            else bool(sel)
        )
        if active and matched_count.get(gid, 0) == 0:
            raise SystemExit(f"Для включённой опции '{gid}={sel}' не найдено ни одной строки в asset_map.csv")

    # Проверяем конфликты target_package между ВСЕМИ выбранными группами
    seen_targets: dict[str, tuple[str, str, str, str]] = {}
    for grp, grp_rows in by_group.items():
        for r in grp_rows:
            tp = (r.get("target_package") or "").strip()
            if not tp:
                raise SystemExit(f"Пустой target_package у строки {r.get('id')} (группа '{grp}')")
            low_tp = tp.lower()
            act = (r.get("action") or "").strip()
            rel_file = ((r.get("converted_file") or "").strip() or (r.get("source_file") or "").strip()).replace("\\", "/")
            if low_tp in seen_targets:
                prev_grp, prev_id, prev_act, prev_file = seen_targets[low_tp]
                if not (act == "patch_text" and prev_act == "patch_text" and rel_file.lower() == prev_file.lower()):
                    raise SystemExit(
                        f"Конфликт целевого пути '{tp}': строка {prev_id} (группа '{prev_grp}') "
                        f"и строка {r.get('id')} (группа '{grp}')"
                    )
            else:
                seen_targets[low_tp] = (grp, r.get("id", ""), act, rel_file)

            # Проверяем наличие локального файла для упаковки (converted_file или source_file)
            local_p = ROOT / rel_file
            if not local_p.is_file():
                raise SystemExit(
                    f"Нет исходного файла для выбранной опции '{grp}': строка {r.get('id')}, путь '{local_p}'"
                )

    unavailable = {
        gid: g.get("unavailable_reason", "недоступно")
        for gid, g in groups.items()
        if not g.get("available", True)
    }
    return by_group, unavailable, skipped_no_slot


def _collect_pack_items(rows: list[dict[str, str]]) -> tuple[list[tuple[str, Path]], list[dict[str, str]], int]:
    """Собрать уникальные записи (rel_under_mount, local_path) для упаковки в .pak."""
    pack_items: list[tuple[str, Path]] = []
    files_meta: list[dict[str, str]] = []
    seen_rel: set[str] = set()
    total_payload = 0
    prefix = "HassleOnline/Content/"
    for r in rows:
        tp = r["target_package"].strip()
        if not tp.lower().startswith(prefix.lower()):
            raise SystemExit(f"Неожиданный target_package вне Content/: {tp}")
        rel_under_mount = tp[len(prefix):]
        rel_file = (r.get("converted_file") or "").strip() or r["source_file"].strip()
        low_rel = rel_under_mount.lower()
        if low_rel not in seen_rel:
            seen_rel.add(low_rel)
            local_p = ROOT / rel_file
            total_payload += local_p.stat().st_size
            pack_items.append((rel_under_mount, local_p))
        files_meta.append(
            {
                "id": r["id"],
                "target_package": tp,
                "packed_from": rel_file,
                "source_file": r["source_file"],
            }
        )
    return pack_items, files_meta, total_payload


def build_all(
    options_path: Path,
    preset_override: str | None,
    dry_run: bool,
    only_groups: list[str] | None = None,
    single_pak: bool = False,
) -> dict:
    log = get_logger("build_mod")
    cfg = load_config()
    opt_cfg = yaml.safe_load(options_path.read_text(encoding="utf-8"))
    preset_name, resolved, groups = resolve_options(opt_cfg, preset_override)
    rows = load_asset_map(ROOT / "mapping" / "asset_map.csv")
    by_group, unavailable, skipped_no_slot = select_rows(rows, resolved, groups)

    if only_groups:
        unknown = [g for g in only_groups if g not in by_group]
        if unknown:
            raise SystemExit(f"Неизвестные или отключённые группы в --groups: {', '.join(unknown)}")
        by_group = {g: by_group[g] for g in only_groups}

    mod_prefix = opt_cfg.get("mod_prefix", "zzz_OneasPort")
    mount_point = "../../../HassleOnline/Content/"
    out_dir = ROOT / "out"

    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        for ext in (".pak", ".utoc", ".ucas"):
            for old_f in out_dir.glob(f"{mod_prefix}*_P{ext}"):
                if old_f.stem == f"{mod_prefix}_pilot_P":
                    continue
                old_f.unlink()

    paks_manifest: list[dict] = []
    if single_pak:
        ordered_rows = [
            r
            for grp in sorted(by_group.keys(), key=lambda g: (0 if g == "core" else 1, g))
            for r in by_group[grp]
        ]
        pack_items, files_meta, total_payload = _collect_pack_items(ordered_rows)
        pak_stem = f"{mod_prefix}_P"
        pak_name = f"{pak_stem}.pak"
        pak_path = out_dir / pak_name
        if dry_run:
            stats = {"files": len(pack_items), "payload_bytes": total_payload, "pak_bytes": 0}
            io_stats = {"container_id": f"0x{container_id_from_name(pak_stem):016x}", "utoc_bytes": 240, "ucas_bytes": 64}
            log.info("[DRY-RUN] %s (+ .utoc/.ucas cid=%s): %d файлов (%d байт)", pak_name, io_stats["container_id"], stats["files"], stats["payload_bytes"])
        else:
            stats = build_pak_v12(pak_path, pack_items, mount_point=mount_point)
            io_stats = build_empty_iostore(pak_path)
            log.info(
                "Собран единый %s: %d файлов, %d байт (+ .utoc %d Б, .ucas %d Б, cid=%s)",
                pak_name,
                stats["files"],
                stats["pak_bytes"],
                io_stats["utoc_bytes"],
                io_stats["ucas_bytes"],
                io_stats["container_id"],
            )
        paks_manifest.append(
            {
                "pak_file": pak_name,
                "utoc_file": f"{pak_stem}.utoc",
                "ucas_file": f"{pak_stem}.ucas",
                "container_id": io_stats["container_id"],
                "group": "core",
                "group_name": "Полная сборка (единый пак)",
                "mount_point": mount_point,
                "files_count": stats["files"],
                "payload_bytes": stats["payload_bytes"],
                "pak_bytes": stats["pak_bytes"],
                "files": files_meta,
            }
        )
    else:
        for grp in sorted(by_group.keys(), key=lambda g: (0 if g == "core" else 1, g)):
            grp_rows = by_group[grp]
            pak_stem = f"{mod_prefix}_{grp}_P"
            pak_name = f"{pak_stem}.pak"
            pak_path = out_dir / pak_name
            pack_items, files_meta, total_payload = _collect_pack_items(grp_rows)

            if dry_run:
                stats = {"files": len(pack_items), "payload_bytes": total_payload, "pak_bytes": 0}
                io_stats = {"container_id": f"0x{container_id_from_name(pak_stem):016x}", "utoc_bytes": 240, "ucas_bytes": 64}
                log.info("[DRY-RUN] %s (+ .utoc/.ucas cid=%s): %d файлов (%d байт)", pak_name, io_stats["container_id"], stats["files"], stats["payload_bytes"])
            else:
                stats = build_pak_v12(pak_path, pack_items, mount_point=mount_point)
                io_stats = build_empty_iostore(pak_path)
                log.info(
                    "Собран %s: %d файлов, %d байт (+ .utoc %d Б, .ucas %d Б, cid=%s)",
                    pak_name,
                    stats["files"],
                    stats["pak_bytes"],
                    io_stats["utoc_bytes"],
                    io_stats["ucas_bytes"],
                    io_stats["container_id"],
                )

            paks_manifest.append(
                {
                    "pak_file": pak_name,
                    "utoc_file": f"{pak_stem}.utoc",
                    "ucas_file": f"{pak_stem}.ucas",
                    "container_id": io_stats["container_id"],
                    "group": grp,
                    "group_name": "Базовая часть (core)" if grp == "core" else groups[grp]["name"],
                    "mount_point": mount_point,
                    "files_count": stats["files"],
                    "payload_bytes": stats["payload_bytes"],
                    "pak_bytes": stats["pak_bytes"],
                    "files": files_meta,
                }
            )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "preset": preset_name,
        "hassle_version": detect_hassle_version(cfg),
        "selected_options": resolved,
        "unavailable_options": unavailable,
        "skipped_no_slot": skipped_no_slot,
        "total_paks": len(paks_manifest),
        "total_files": sum(p["files_count"] for p in paks_manifest),
        "paks": paks_manifest,
    }

    if not dry_run:
        (out_dir / "build_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.info("Манифест сохранён: out/build_manifest.json (паков=%d, файлов=%d)", manifest["total_paks"], manifest["total_files"])
        # защита от обновлений: запоминаем версии пропатченных файлов игры (tools/check_update.py)
        from check_update import record  # noqa: PLC0415

        g = record()
        log.info("Защита от обновлений: out/update_guard.json (сборка игры %s, файлов %d)", g["game_build"], len(g["files"]))
    else:
        log.info("[DRY-RUN] Проверка успешна (паков к сборке=%d, файлов=%d); файлы не записывались.", manifest["total_paks"], manifest["total_files"])

    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--options", default="build_options.yaml", help="путь к build_options.yaml")
    ap.add_argument("--preset", default=None, help="переопределить пресет (basic / maximum / custom)")
    ap.add_argument("--groups", nargs="*", default=None, help="собрать только указанные группы модулей")
    ap.add_argument("--single-pak", action="store_true", help="собрать все выбранные группы в один zzz_OneasPort_P.pak")
    ap.add_argument("--dry-run", action="store_true", help="только проверить опции и конфликты, ничего не писать")
    a = ap.parse_args()

    opt_path = Path(a.options)
    if not opt_path.is_absolute():
        opt_path = ROOT / opt_path
    build_all(opt_path, a.preset, a.dry_run, a.groups, a.single_pak)


if __name__ == "__main__":
    main()
