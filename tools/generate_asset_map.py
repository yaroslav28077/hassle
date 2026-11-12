"""Фаза 3 (Дорожка A): построение mapping/asset_map.csv, подгонка размеров UI PNG и генерация миниатюр.

Читает:
- work/build_only/ и work/textures/mobilescs/
- D:/Games/RADMIR Games/RADMIR CRMP/manifest.json (только чтение)
- game_ref/ui_files.txt и .pak HASSLE 2.0 (только чтение)

Пишет:
- mapping/asset_map.csv
- work/ui/... (подогнанные без растягивания PNG по .agents/rules/30-asset-quality.md)
- work/previews/... (миниатюры для configurator.html)
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import struct
from pathlib import Path

from PIL import Image

from common import ROOT, get_logger, load_config

FIELDS = [
    "id",
    "category",
    "variant",
    "option_group",
    "option_value",
    "source_file",
    "converted_file",
    "target_package",
    "asset_type",
    "texture_group",
    "width",
    "height",
    "radmir_hash",
    "hassle_hash",
    "source_hash",
    "action",
    "status",
    "notes",
]


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_radmir_manifest(radmir_dir: Path) -> dict[str, dict]:
    mp = radmir_dir / "manifest.json"
    if not mp.is_file():
        return {}
    data = json.loads(mp.read_text(encoding="utf-8", errors="replace"))
    return {
        it["path"].replace("\\", "/").lstrip("/").lower(): it
        for it in data.get("files", [])
        if "path" in it
    }


def load_hassle_ui_index(ui_txt: Path) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for line in ui_txt.read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        vp, pn = line.split("\t", 1)
        out[vp.lower()] = (vp, pn)
    return out


def index_pak_meta(pak_path: Path) -> dict[str, tuple[str, int, int, int, int]]:
    entries: dict[str, tuple[str, int, int, int, int]] = {}
    with open(pak_path, "rb") as f:
        f.seek(0, 2)
        sz = f.tell()
        f.seek(max(0, sz - 221))
        footer = f.read(221)
        idx_off, idx_sz = struct.unpack_from("<QQ", footer, 25)
        f.seek(idx_off)
        idx = f.read(idx_sz)

        def r_fstr(buf: bytes, p: int) -> tuple[str, int]:
            n, = struct.unpack_from("<i", buf, p)
            p += 4
            if n >= 0:
                return buf[p:p + n].rstrip(b"\x00").decode("utf-8", "replace"), p + n
            return buf[p:p + (-n) * 2].decode("utf-16-le", "replace").rstrip("\x00"), p + (-n) * 2

        mp, pos = r_fstr(idx, 0)
        while mp.startswith("../"):
            mp = mp[3:]
        mp = mp.lstrip("/")
        _num, _seed, has_ph = struct.unpack_from("<IQi", idx, pos)
        pos += 16
        if has_ph:
            pos += 36
        _has_fd, = struct.unpack_from("<i", idx, pos)
        pos += 4
        fd_off, fd_sz = struct.unpack_from("<QQ", idx, pos)
        pos += 36
        enc_sz, = struct.unpack_from("<i", idx, pos)
        enc = idx[pos + 4:pos + 4 + enc_sz]
        f.seek(fd_off)
        fd = f.read(fd_sz)
        dc, = struct.unpack_from("<i", fd, 0)
        fp = 4
        for _ in range(dc):
            d, fp = r_fstr(fd, fp)
            if d == "/":
                d = ""
            fc, = struct.unpack_from("<i", fd, fp)
            fp += 4
            for _ in range(fc):
                fn, fp = r_fstr(fd, fp)
                eoff, = struct.unpack_from("<i", fd, fp)
                fp += 4
                rel = f"{d}{fn}".lstrip("/")
                vpath = f"{mp}{rel}" if mp else rel
                flags, = struct.unpack_from("<I", enc, eoff)
                ep = eoff + 4
                off_fmt = "<I" if (flags & 0x80000000) else "<Q"
                usz_fmt = "<I" if (flags & 0x40000000) else "<Q"
                off = struct.unpack_from(off_fmt, enc, ep)[0]
                ep += struct.calcsize(off_fmt)
                usz = struct.unpack_from(usz_fmt, enc, ep)[0]
                ep += struct.calcsize(usz_fmt)
                cm = (flags >> 23) & 0x3F
                if cm != 0:
                    csz_fmt = "<I" if (flags & 0x20000000) else "<Q"
                    csz = struct.unpack_from(csz_fmt, enc, ep)[0]
                else:
                    csz = usz
                entries[vpath.lower()] = (vpath, off, csz, usz, cm)
    return entries


def svg_dims(path: Path) -> tuple[int | None, int | None]:
    txt = path.read_bytes()[:1024].decode("utf-8", "ignore")
    mw = re.search(r'width=["\'](\d+(?:\.\d+)?)', txt)
    mh = re.search(r'height=["\'](\d+(?:\.\d+)?)', txt)
    if mw and mh:
        return int(float(mw.group(1))), int(float(mh.group(1)))
    mv = re.search(r'viewBox=["\'][\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+([\d.]+)', txt)
    if mv:
        return int(float(mv.group(1))), int(float(mv.group(2)))
    return None, None


def img_dims(path: Path) -> tuple[int | None, int | None]:
    ext = path.suffix.lower()
    if ext == ".svg":
        return svg_dims(path)
    if ext in (".png", ".jpg", ".jpeg", ".gif"):
        with Image.open(path) as im:
            return im.size
    return None, None


def fit_png_to_slot(src: Path, dst: Path, tw: int, th: int) -> str:
    """Подогнать PNG в целевой размер (tw, th) без растягивания (пропорционально + прозрачный padding)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        rgba = im.convert("RGBA")
        sw, sh = rgba.size
        if sw == 1 and sh == 1 and rgba.getpixel((0, 0))[3] == 0:
            canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
            canvas.save(dst, "PNG")
            return f"1x1 transparent -> {tw}x{th} transparent slot"
        if (sw, sh) == (tw, th):
            rgba.save(dst, "PNG")
            return f"exact {tw}x{th}"
        scale = min(tw / sw, th / sh)
        nw = max(1, round(sw * scale))
        nh = max(1, round(sh * scale))
        resized = rgba if (nw, nh) == (sw, sh) else rgba.resize((nw, nh), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ox = (tw - nw) // 2
        oy = (th - nh) // 2
        canvas.paste(resized, (ox, oy))
        canvas.save(dst, "PNG")
        warn = "; низкое разрешение исходника (>2x upscale)" if scale > 2.0 else ""
        pad_note = "; padding прозрачный" if (nw, nh) != (tw, th) else ""
        return f"{sw}x{sh} -> {nw}x{nh} in {tw}x{th} (scale={scale:.2f}x{pad_note}{warn})"


def make_preview(src: Path, dst: Path, max_side: int = 160) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".svg":
        dst.write_bytes(src.read_bytes())
        return
    with Image.open(src) as im:
        rgba = im.convert("RGBA")
        rgba.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        rgba.save(dst, "PNG")


def font_fstype(path: Path) -> int | None:
    d = path.read_bytes()
    if len(d) < 12:
        return None
    num_tables, = struct.unpack_from(">H", d, 4)
    for i in range(num_tables):
        base = 12 + i * 16
        if base + 16 > len(d):
            break
        if d[base:base + 4] == b"OS/2":
            off, length = struct.unpack_from(">II", d, base + 8)
            if length >= 10 and off + 10 <= len(d):
                return struct.unpack_from(">H", d, off + 8)[0]
    return None


def main() -> None:
    log = get_logger("map_track_a")
    cfg = load_config()
    radmir_dir = Path(cfg["source"]["build_dir"])
    paks_dir = Path(cfg["game"]["install_dir"]) / cfg["game"]["project_name"] / "Content" / "Paks"
    build_only = ROOT / "work" / "build_only"
    mobilescs_dir = ROOT / "work" / "textures" / "mobilescs"
    orig_dir = ROOT / "game_ref" / "originals"
    work_ui = ROOT / "work" / "ui"
    previews_dir = ROOT / "work" / "previews"

    rad_manifest = load_radmir_manifest(radmir_dir)
    hassle_ui = load_hassle_ui_index(ROOT / "game_ref" / "ui_files.txt")

    pak_cache: dict[str, dict[str, tuple[str, int, int, int, int]]] = {}

    def get_hassle_meta(vpath_low: str) -> tuple[str, str, int | None, int | None, str]:
        """Вернуть (hassle_hash_label, note, tw, th, vpath_exact)."""
        hit = hassle_ui.get(vpath_low)
        if not hit:
            return "", "no_slot_in_hassle", None, None, ""
        vp, pn = hit
        if pn not in pak_cache:
            pak_cache[pn] = index_pak_meta(paks_dir / pn)
        meta = pak_cache[pn].get(vpath_low)
        if not meta:
            return "", "missing_in_pak_index", None, None, vp
        _, _off, _csz, usz, cm = meta
        orig_p = orig_dir / vp
        if cm == 0 and orig_p.is_file():
            h_hash = md5_file(orig_p)
            tw, th = img_dims(orig_p)
            return h_hash, f"cm=0 usz={usz}", tw, th, vp
        # cm=1 (Oodle v9): проверяем совпадение размера с Radmir manifest.json
        rad_rel = ""
        if "/main/" in vpath_low:
            rad_rel = "uiresources/" + vpath_low.split("/main/", 1)[1]
        rit = rad_manifest.get(rad_rel)
        tw, th = (None, None)
        rad_local = radmir_dir / rad_rel if rad_rel else None
        if rit and usz == rit.get("size"):
            if rad_local and rad_local.is_file() and md5_file(rad_local) == rit.get("hash"):
                tw, th = img_dims(rad_local)
            return f"cm1:usz={usz}(=radmir)", f"cm=1 usz={usz}==radmir_sz", tw, th, vp
        return f"cm1:usz={usz}", f"cm=1 usz={usz}!=radmir_sz", tw, th, vp

    rows: list[dict[str, str | int]] = []
    idx = 0

    def next_id(prefix: str) -> str:
        nonlocal idx
        idx += 1
        return f"{prefix}_{idx:04d}"

    def add_row(**kw: str | int) -> None:
        r = {k: kw.get(k, "") for k in FIELDS}
        rows.append(r)

    def resolve_radmir(rad_rel: str) -> str:
        it = rad_manifest.get(rad_rel.lower())
        return it["hash"] if it else ""

    # A. Все файлы в work/build_only/
    all_build = sorted(p for p in build_only.rglob("*") if p.is_file())
    for p in all_build:
        rel = p.relative_to(build_only).as_posix()
        low = rel.lower()
        src_hash = md5_file(p)
        ext = p.suffix.lower()

        # 1. GPS icons (uiresources/images/gps/*)
        if low.startswith("uiresources/images/gps/"):
            target = f"HassleOnline/Content/UserInterface/Main/images/gps/{p.name}"
            rad_h = resolve_radmir(rel)
            h_h, h_note, tw, th, vp = get_hassle_meta(target.lower())
            sw, sh = img_dims(p)
            tw = tw or sw or 80
            th = th or sh or 80
            conv = work_ui / "gps" / p.name
            fit_note = fit_png_to_slot(p, conv, tw, th)
            make_preview(conv, previews_dir / "gps" / f"{p.stem}.png", 96)
            same_base = (h_h == rad_h) or ("=radmir" in h_h)
            add_row(
                id=next_id("gps"),
                category="gps_icons",
                variant="oneas",
                option_group="gps_icons",
                option_value="true",
                source_file=f"work/build_only/{rel}",
                converted_file=conv.relative_to(ROOT).as_posix(),
                target_package=vp or target,
                asset_type="cohtml_image",
                texture_group="UI",
                width=tw,
                height=th,
                radmir_hash=rad_h,
                hassle_hash=h_h,
                source_hash=src_hash,
                action="replace_file" if same_base else "conflict",
                status="converted",
                notes=f"{fit_note}; {h_note}",
            )
            continue

        # 2. Weapon icons (uiresources/oneas-img/weapon/*)
        if low.startswith("uiresources/oneas-img/weapon/"):
            target = f"HassleOnline/Content/UserInterface/Main/images/hud/{p.name}"
            rad_rel = f"uiresources/images/hud/{p.name}"
            rad_h = resolve_radmir(rad_rel)
            h_h, h_note, tw, th, vp = get_hassle_meta(target.lower())
            sw, sh = img_dims(p)
            if not vp:
                make_preview(p, previews_dir / "weapon" / f"{p.stem}.png", 96)
                add_row(
                    id=next_id("wpn"),
                    category="weapon_icons",
                    variant="oneas",
                    option_group="weapon_icons",
                    option_value="true",
                    source_file=f"work/build_only/{rel}",
                    converted_file="",
                    target_package=target,
                    asset_type="cohtml_image",
                    texture_group="UI",
                    width=sw or 0,
                    height=sh or 0,
                    radmir_hash=rad_h,
                    hassle_hash="",
                    source_hash=src_hash,
                    action="no_slot",
                    status="skip",
                    notes=f"В HASSLE 2.0 отсутствует слот {target}",
                )
                continue
            tw = tw or 500
            th = th or 500
            conv = work_ui / "weapon" / p.name
            fit_note = fit_png_to_slot(p, conv, tw, th)
            make_preview(conv, previews_dir / "weapon" / f"{p.stem}.png", 96)
            same_base = (h_h == rad_h) or ("=radmir" in h_h)
            add_row(
                id=next_id("wpn"),
                category="weapon_icons",
                variant="oneas",
                option_group="weapon_icons",
                option_value="true",
                source_file=f"work/build_only/{rel}",
                converted_file=conv.relative_to(ROOT).as_posix(),
                target_package=vp,
                asset_type="cohtml_image",
                texture_group="UI",
                width=tw,
                height=th,
                radmir_hash=rad_h,
                hassle_hash=h_h,
                source_hash=src_hash,
                action="replace_file" if same_base else "conflict",
                status="converted",
                notes=f"{fit_note}; {h_note}",
            )
            # fix: при weapon==0 (кулак) Hud.js рендерит a.logoImage (hassle-logo2/hassle-logo-helloween/hassle-logo-new-year), а не images/hud/0.png
            if p.name == "0.png":
                logo_slots = [
                    ("hassle-logo2.png", 321, 321, "oneas_fist_logo", "Кулак при !weapon (обычный)"),
                    ("hassle-logo-helloween.png", 406, 406, "oneas_fist_logo_hw", "Кулак при !weapon (Хэллоуин)"),
                    ("hassle-logo-new-year.png", 512, 512, "oneas_fist_logo_ny", "Кулак при !weapon (Новый год)"),
                ]
                for fname, def_w, def_h, var_name, desc_note in logo_slots:
                    t_logo = f"HassleOnline/Content/UserInterface/Main/assets/{fname}"
                    lh_h, lh_note, ltw, lth, lvp = get_hassle_meta(t_logo.lower())
                    ltw, lth = ltw or def_w, lth or def_h
                    conv_logo = work_ui / "weapon" / fname
                    lfit = fit_png_to_slot(p, conv_logo, ltw, lth)
                    add_row(
                        id=next_id("wpn"),
                        category="weapon_icons",
                        variant=var_name,
                        option_group="weapon_icons",
                        option_value="true",
                        source_file=f"work/build_only/{rel}",
                        converted_file=conv_logo.relative_to(ROOT).as_posix(),
                        target_package=lvp or t_logo,
                        asset_type="cohtml_image",
                        texture_group="UI",
                        width=ltw,
                        height=lth,
                        radmir_hash=resolve_radmir(f"uiresources/assets/{fname}"),
                        hassle_hash=lh_h,
                        source_hash=src_hash,
                        action="replace_file",
                        status="converted",
                        notes=f"{desc_note}; {lfit}; {lh_note}",
                    )
            continue

        # 3. UI Sounds (uiresources/sounds/*)
        if low.startswith("uiresources/sounds/"):
            sub = rel[len("uiresources/"):]
            target = f"HassleOnline/Content/UserInterface/Main/{sub}"
            rad_h = resolve_radmir(rel)
            h_h, h_note, _, _, vp = get_hassle_meta(target.lower())
            same_base = (h_h == rad_h) or ("=radmir" in h_h)
            add_row(
                id=next_id("snd"),
                category="ui_sounds",
                variant="oneas",
                option_group="ui_sounds",
                option_value="true",
                source_file=f"work/build_only/{rel}",
                converted_file=f"work/build_only/{rel}",
                target_package=vp or target,
                asset_type="cohtml_audio",
                texture_group="",
                width=0,
                height=0,
                radmir_hash=rad_h,
                hassle_hash=h_h,
                source_hash=src_hash,
                action="replace_file" if same_base else "conflict",
                status="converted",
                notes=f"Прямая замена UI-звука ({p.stat().st_size}B); {h_note}",
            )
            continue

        # 4. Interfaces (uiresources/oneas-img/interfaces/*)
        if low.startswith("uiresources/oneas-img/interfaces/"):
            name = p.name
            sw, sh = img_dims(p)
            if name in ("layer_option_active.svg", "layer_option_hover.svg", "option_active.svg", "option_hover.svg"):
                target = f"HassleOnline/Content/UserInterface/Main/assets/{name}"
                rad_h = resolve_radmir(f"uiresources/assets/{name}")
                h_h, h_note, tw, th, vp = get_hassle_meta(target.lower())
                make_preview(p, previews_dir / "interfaces" / name, 128)
                add_row(
                    id=next_id("ui"),
                    category="ui_controls",
                    variant="oneas",
                    option_group="",
                    option_value="",
                    source_file=f"work/build_only/{rel}",
                    converted_file=f"work/build_only/{rel}",
                    target_package=vp or target,
                    asset_type="cohtml_svg",
                    texture_group="UI",
                    width=tw or sw or 0,
                    height=th or sh or 0,
                    radmir_hash=rad_h,
                    hassle_hash=h_h,
                    source_hash=src_hash,
                    action="replace_file" if ("=radmir" in h_h or h_h == rad_h) else "conflict",
                    status="converted",
                    notes=f"Core SVG-контрол ({sw}x{sh} vs HASSLE {tw}x{th}); {h_note}",
                )
            elif name.startswith("bg-auth-") and name.endswith(".png"):
                idx_num = p.stem.split("-")[-1]
                opt_val = f"bg_auth_{idx_num}"
                make_preview(p, previews_dir / "auth_bg" / name, 180)
                # fix: в Authorization.css основной экран входа (.authorization) использует background3.png (1920x1080)
                t_login = "HassleOnline/Content/UserInterface/Main/assets/background3.png"
                lh_h, lh_note, ltw, lth, lvp = get_hassle_meta(t_login.lower())
                ltw, lth = ltw or 1920, lth or 1080
                conv_login = work_ui / "auth_bg_login" / name
                lfit = fit_png_to_slot(p, conv_login, ltw, lth)
                add_row(
                    id=next_id("auth"),
                    category="auth_bg",
                    variant=opt_val,
                    option_group="auth_bg",
                    option_value=opt_val,
                    source_file=f"work/build_only/{rel}",
                    converted_file=conv_login.relative_to(ROOT).as_posix(),
                    target_package=lvp or t_login,
                    asset_type="cohtml_image",
                    texture_group="UI",
                    width=ltw,
                    height=lth,
                    radmir_hash=resolve_radmir("uiresources/assets/background3.png"),
                    hassle_hash=lh_h,
                    source_hash=src_hash,
                    action="replace_file",
                    status="converted",
                    notes=f"Экран входа (.authorization -> background3.png 1:1); {lfit}; {lh_note}",
                )
                target = "HassleOnline/Content/UserInterface/Main/assets/bg-register.png"
                rad_h = resolve_radmir("uiresources/assets/bg-register.png")
                h_h, h_note, tw, th, vp = get_hassle_meta(target.lower())
                tw, th = tw or 2340, th or 1080
                conv = work_ui / "auth_bg" / name
                fit_note = fit_png_to_slot(p, conv, tw, th)
                add_row(
                    id=next_id("auth"),
                    category="auth_bg",
                    variant=f"{opt_val}_register",
                    option_group="auth_bg",
                    option_value=opt_val,
                    source_file=f"work/build_only/{rel}",
                    converted_file=conv.relative_to(ROOT).as_posix(),
                    target_package=vp or target,
                    asset_type="cohtml_image",
                    texture_group="UI",
                    width=tw,
                    height=th,
                    radmir_hash=rad_h,
                    hassle_hash=h_h,
                    source_hash=src_hash,
                    action="replace_file",
                    status="converted",
                    notes=f"Экран регистрации (.authorization_register -> bg-register.png); {fit_note}; {h_note}",
                )
            else:
                # bg.info-card.png, free.svg, line_top.png, noise.gif
                if ext in (".png", ".gif", ".svg"):
                    make_preview(p, previews_dir / "interfaces" / f"{p.stem}{'.svg' if ext == '.svg' else '.png'}", 128)
                add_row(
                    id=next_id("ui"),
                    category="css_hud_patches",
                    variant="oneas",
                    option_group="css_hud_patches",
                    option_value="true",
                    source_file=f"work/build_only/{rel}",
                    converted_file="",
                    target_package="HassleOnline/Content/UserInterface/Main/assets/Authorization.css",
                    asset_type="cohtml_patch_asset",
                    texture_group="UI",
                    width=sw or 0,
                    height=sh or 0,
                    radmir_hash=resolve_radmir("uiresources/assets/Authorization.css"),
                    hassle_hash=get_hassle_meta("hassleonline/content/userinterface/main/assets/authorization.css")[0],
                    source_hash=src_hash,
                    action="patch_text",
                    status="blocked",
                    notes=f"Оверлей ONEAS ({name}, {sw}x{sh}) требует патча Authorization.css/Hud.css (cm=1 в HASSLE — нужен FModel)",
                )
            continue

        # 5. Speedometer SVGs (uiresources/oneas-img/speed/*)
        if low.startswith("uiresources/oneas-img/speed/"):
            name = p.name
            sw, sh = img_dims(p)
            make_preview(p, previews_dir / "speed" / name, 96)
            if name in ("fuel-bg.svg", "wash-bg.svg"):
                target = f"HassleOnline/Content/UserInterface/Main/assets/{name}"
                rad_h = resolve_radmir(f"uiresources/assets/{name}")
                h_h, h_note, tw, th, vp = get_hassle_meta(target.lower())
                add_row(
                    id=next_id("spd"),
                    category="speedometer_bg",
                    variant="oneas",
                    option_group="speedometer_bg",
                    option_value="true",
                    source_file=f"work/build_only/{rel}",
                    converted_file=f"work/build_only/{rel}",
                    target_package=vp or target,
                    asset_type="cohtml_svg",
                    texture_group="UI",
                    width=tw or sw or 0,
                    height=th or sh or 0,
                    radmir_hash=rad_h,
                    hassle_hash=h_h,
                    source_hash=src_hash,
                    action="replace_file",
                    status="converted",
                    notes=f"SVG спидометра ({sw}x{sh} vs viewBox {tw}x{th}); {h_note}",
                )
            else:
                # fix: активные шкалы спидометра вшиты как inline <svg> в Hud.js, а _danger-состояния — в Hud.css -> patch_text
                is_active = "active" in name
                t_pkg = (
                    "HassleOnline/Content/UserInterface/Main/assets/Hud.js"
                    if is_active
                    else "HassleOnline/Content/UserInterface/Main/assets/Hud.css"
                )
                rad_k = "uiresources/assets/" + Path(t_pkg).name
                h_h, h_note, _, _, _ = get_hassle_meta(t_pkg.lower())
                add_row(
                    id=next_id("spd"),
                    category="css_hud_patches",
                    variant="oneas",
                    option_group="css_hud_patches",
                    option_value="true",
                    source_file=f"work/build_only/{rel}",
                    converted_file="",
                    target_package=t_pkg,
                    asset_type="cohtml_patch_asset",
                    texture_group="UI",
                    width=sw or 0,
                    height=sh or 0,
                    radmir_hash=resolve_radmir(rad_k),
                    hassle_hash=h_h,
                    source_hash=src_hash,
                    action="patch_text",
                    status="blocked",
                    notes=(
                        "Активная шкала спидометра вшита как inline <svg> в Hud.js (нужен FModel + patch_text); "
                        if is_active
                        else "Danger-состояние шкалы спидометра задаётся CSS в Hud.css (нужен FModel + patch_text); "
                    )
                    + h_note,
                )
            continue

        # 6. HUD icons (uiresources/oneas-img/hud/*)
        if low.startswith("uiresources/oneas-img/hud/"):
            name = p.name
            sw, sh = img_dims(p)
            make_preview(p, previews_dir / "hud" / name, 96)
            # fix: реальные имена Vite-ассетов HASSLE из ui_asset_refs.md:
            # bonus-2 -> 278.png (60x48, Radmir 252.png), bonus-3 -> 373.png (53x46, Radmir 352.png),
            # icon-health -> health2.png (72x59), icon-armour -> armour2.png (161x198)
            direct_hud = {
                "bonus-2.png": ("278.png", "252.png", "hud_bonus_badge", "bonus_x2", ""),
                "bonus-3.png": ("373.png", "352.png", "hud_bonus_badge", "bonus_x3", ""),
                "icon-armour.png": ("armour2.png", "armour2.png", "hud_status_icons", "true", "низкое разрешение исходника (50x51 -> 161x198, 3.2x)"),
                "icon-health.png": ("health2.png", "health2.png", "hud_status_icons", "true", ""),
            }
            if name in direct_hud:
                t_name, rad_name, og, ov, extra_note = direct_hud[name]
                target = f"HassleOnline/Content/UserInterface/Main/assets/{t_name}"
                rad_h = resolve_radmir(f"uiresources/assets/{rad_name}")
                h_h, h_note, tw, th, vp = get_hassle_meta(target.lower())
                tw, th = tw or sw or 32, th or sh or 32
                conv = work_ui / "hud" / f"{p.stem}_for_{t_name}"
                fit_note = fit_png_to_slot(p, conv, tw, th)
                full_note = f"{extra_note}; {fit_note}; {h_note}" if extra_note else f"{fit_note}; {h_note}"
                add_row(
                    id=next_id("hud"),
                    category=og,
                    variant=ov if og == "hud_bonus_badge" else "oneas",
                    option_group=og,
                    option_value=ov,
                    source_file=f"work/build_only/{rel}",
                    converted_file=conv.relative_to(ROOT).as_posix(),
                    target_package=vp or target,
                    asset_type="cohtml_image",
                    texture_group="UI",
                    width=tw,
                    height=th,
                    radmir_hash=rad_h,
                    hassle_hash=h_h,
                    source_hash=src_hash,
                    action="replace_file",
                    status="converted",
                    notes=full_note,
                )
            elif name in ("icon-freeze.png", "icon-hunger.png", "icon-online.svg", "icon-breath.png"):
                # fix: icon-hunger (He/Ne), icon-freeze (De), icon-online (ia) вшиты как inline data:image/png;base64 в Hud.js
                if name == "icon-breath.png":
                    t_pkg = "HassleOnline/Content/UserInterface/Main/assets/lungs.png"
                    rad_k = "uiresources/assets/lungs.png"
                    h_h, h_note, tw, th, vp = get_hassle_meta(t_pkg.lower())
                    reason = f"Несовпадение масштаба (20x20 -> lungs.png {tw}x{th}, апскейл 10.7x) — нужен CSS-патч размера"
                else:
                    t_pkg = "HassleOnline/Content/UserInterface/Main/assets/Hud.js"
                    rad_k = "uiresources/assets/Hud.js"
                    h_h, h_note, tw, th, vp = get_hassle_meta(t_pkg.lower())
                    reason = f"Картинка вшита как inline data:image/png;base64 в Hud.js — нужен FModel + patch_text"
                add_row(
                    id=next_id("hud"),
                    category="css_hud_patches",
                    variant="oneas",
                    option_group="css_hud_patches",
                    option_value="true",
                    source_file=f"work/build_only/{rel}",
                    converted_file="",
                    target_package=vp or t_pkg,
                    asset_type="cohtml_patch_asset",
                    texture_group="UI",
                    width=tw or sw or 0,
                    height=th or sh or 0,
                    radmir_hash=resolve_radmir(rad_k),
                    hassle_hash=h_h,
                    source_hash=src_hash,
                    action="patch_text",
                    status="blocked",
                    notes=f"{reason}; {h_note}",
                )
            else:
                # wanted-active/inactive.svg, radar.png, bg-server.png, icon-data/fish/id/time/zz.svg
                t_map = {
                    "wanted-active.svg": "HassleOnline/Content/UserInterface/Main/assets/wanted_active.png",
                    "wanted-inactive.svg": "HassleOnline/Content/UserInterface/Main/assets/wanted_inactive.png",
                }
                t_pkg = t_map.get(name, "HassleOnline/Content/UserInterface/Main/assets/Hud.css")
                rad_k = f"uiresources/assets/{Path(t_pkg).name}"
                h_h, h_note, tw, th, _ = get_hassle_meta(t_pkg.lower())
                add_row(
                    id=next_id("hud"),
                    category="css_hud_patches",
                    variant="oneas",
                    option_group="css_hud_patches",
                    option_value="true",
                    source_file=f"work/build_only/{rel}",
                    converted_file="",
                    target_package=t_pkg,
                    asset_type="cohtml_patch_asset",
                    texture_group="UI",
                    width=sw or 0,
                    height=sh or 0,
                    radmir_hash=resolve_radmir(rad_k),
                    hassle_hash=h_h,
                    source_hash=src_hash,
                    action="patch_text",
                    status="blocked",
                    notes=f"Требует патча Hud.css (cm=1 Oodle v9 в HASSLE — нужен FModel); {h_note}",
                )
            continue

        # 7. Fonts (uiresources/fonts/*)
        if low.startswith("uiresources/fonts/"):
            fst = font_fstype(p)
            lic_ok = fst is not None and (fst & 0x0002) == 0
            add_row(
                id=next_id("fnt"),
                category="ui_fonts",
                variant="oneas",
                option_group="ui_fonts",
                option_value="true",
                source_file=f"work/build_only/{rel}",
                converted_file="",
                target_package=f"HassleOnline/Content/UserInterface/Main/assets/{p.name}",
                asset_type="cohtml_font",
                texture_group="",
                width=0,
                height=0,
                radmir_hash="",
                hassle_hash="",
                source_hash=src_hash,
                action="no_slot",
                status="skip",
                notes=f"В HASSLE нет одноимённого слота шрифта (используются OpenSans/HassleOpenSans); OS/2 fsType={fst} ({'встраивание разрешено' if lic_ok else 'ограничено'})",
            )
            continue

        # 8. Track B assets -> pending_B
        is_track_b = (
            low in ("models/hud.txd", "models/effectspc.txd", "models/particle.txd", "customsaa2/vehicle.txd", "cleo/p1_bell.mp3")
            or low.startswith("modloader/sound/genrl/")
            or low.startswith("oneasdata/txd_editor/")
        )
        if is_track_b:
            add_row(
                id=next_id("trb"),
                category="track_b",
                variant="oneas",
                option_group="",
                option_value="",
                source_file=f"work/build_only/{rel}",
                converted_file="",
                target_package="",
                asset_type="ue_pending",
                texture_group="",
                width=0,
                height=0,
                radmir_hash="",
                hassle_hash="",
                source_hash=src_hash,
                action="pending_B",
                status="todo",
                notes="Дорожка B (прицелы hud.txd, звуки GENRL, VEHICLE.TXD, эффекты — нужен FModel и UE-импорт)",
            )
            continue

        # 9. MobileHud/mobilescs.txd itself (контейнер, сами PNG мапятся ниже из work/textures/mobilescs)
        if low == "mobilehud/mobilescs.txd":
            add_row(
                id=next_id("skp"),
                category="container_txd",
                variant="",
                option_group="",
                option_value="",
                source_file=f"work/build_only/{rel}",
                converted_file="",
                target_package="",
                asset_type="txd_container",
                texture_group="",
                width=0,
                height=0,
                radmir_hash="",
                hassle_hash="",
                source_hash=src_hash,
                action="skip",
                status="skip",
                notes="Контейнер TXD: извлечённые фоны загрузки размечены построчно из work/textures/mobilescs/",
            )
            continue

        # 10. All code / plugins / CLEO / configs / effects.fxp -> skip
        if p.name.lower() == "jsloader.asi":
            reason = "Нативный WebSocket++/GTA-мост (18 функций игры/файлов, без встроенного CSS/JS — см. docs/oneas_ui_changes.md)"
        elif ext in (".asi", ".cs", ".cleo", ".dll"):
            reason = f"Нативный код/скрипт GTA SA ({ext}) не переносится на UE"
        elif ext in (".ini", ".cfg", ".dat", ".md", ".txt", ".0") or ext == "" or low.endswith("license"):
            reason = "Конфиг/документация/данные GTA SA-modloader не используются в HASSLE 2.0"
        elif low == "models/effects.fxp":
            reason = "Формат эффектов GTA SA RenderWare (.fxp) не переносится"
        elif low == "mouse.png":
            reason = "Курсор GTA SA (отдельный PNG не используется в Cohtml HASSLE без CSS)"
        else:
            reason = "Не входит в Дорожку A"
        add_row(
            id=next_id("skp"),
            category="code_or_cfg",
            variant="",
            option_group="",
            option_value="",
            source_file=f"work/build_only/{rel}",
            converted_file="",
            target_package="",
            asset_type="skip",
            texture_group="",
            width=0,
            height=0,
            radmir_hash="",
            hassle_hash="",
            source_hash=src_hash,
            action="skip",
            status="skip",
            notes=reason,
        )

    # B. Извлечённые экраны загрузки из work/textures/mobilescs/*.png
    if mobilescs_dir.is_dir():
        target_ls = "HassleOnline/Content/UserInterface/LoadingScreen/img/background.2fc2a64f.png"
        h_h, h_note, tw, th, vp = get_hassle_meta(target_ls.lower())
        tw, th = tw or 1920, th or 1080
        for p in sorted(mobilescs_dir.glob("*.png")):
            src_hash = md5_file(p)
            sw, sh = img_dims(p)
            if p.stem == "rockstar":
                make_preview(p, previews_dir / "loading_screen" / p.name, 128)
                add_row(
                    id=next_id("lds"),
                    category="loading_screen",
                    variant=p.stem,
                    option_group="loading_screen",
                    option_value=p.stem,
                    source_file=p.relative_to(ROOT).as_posix(),
                    converted_file="",
                    target_package="",
                    asset_type="cohtml_image",
                    texture_group="UI",
                    width=sw or 0,
                    height=sh or 0,
                    radmir_hash="",
                    hassle_hash="",
                    source_hash=src_hash,
                    action="no_slot",
                    status="skip",
                    notes="Логотип 300x300 из mobilescs.txd: в HASSLE LoadingScreen логотип в формате logo.9eeca9a6.webm",
                )
            else:
                conv = work_ui / "loading_screen" / p.name
                fit_note = fit_png_to_slot(p, conv, tw, th)
                make_preview(conv, previews_dir / "loading_screen" / p.name, 180)
                add_row(
                    id=next_id("lds"),
                    category="loading_screen",
                    variant=p.stem,
                    option_group="loading_screen",
                    option_value=p.stem,
                    source_file=p.relative_to(ROOT).as_posix(),
                    converted_file=conv.relative_to(ROOT).as_posix(),
                    target_package=vp or target_ls,
                    asset_type="cohtml_image",
                    texture_group="UI",
                    width=tw,
                    height=th,
                    radmir_hash="",
                    hassle_hash=h_h,
                    source_hash=src_hash,
                    action="replace_file",
                    status="converted",
                    notes=f"Экран загрузки ONEAS (из MobileHud/mobilescs.txd); {fit_note}; {h_note}",
                )

    out_csv = ROOT / "mapping" / "asset_map.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    act_cnt = Counter(r["action"] for r in rows)
    cat_cnt = Counter(r["category"] for r in rows)
    log.info("Записано строк в asset_map.csv: %d | actions=%s | categories=%s", len(rows), dict(act_cnt), dict(cat_cnt))


if __name__ == "__main__":
    main()
