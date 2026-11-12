"""Локальное превью UI HASSLE в обычном браузере (Chromium/Chrome) — проверка вёрстки и панели до игры.

    python tools/preview/make_preview.py                 # собрать work/preview/{native,mod}
    python tools/preview/make_preview.py --serve         # и запустить серверы :8765 (родной) и :8766 (мод)

Источники (только чтение):
- <Radmir>/uiresources (тот же Vite-бандл, но несжатый) — база общих модулей;
- Exports/*/Content/UserInterface/Main — версии HASSLE поверх (у кого есть);
- work/ui/patched/UserInterface/Main/assets — наши пропатченные файлы (только в mod).
Несовпадающие модули Radmir/HASSLE закрываются заглушками ТОЛЬКО для превью (в пак не идут).

Открыть: http://localhost:8766/frame.html?w=1920&h=1080, затем в консоли страницы
    f.contentWindow.openInterface('Hud'); f.contentWindow.__scene({immortality:true})
    f.contentWindow.oneasOpenSettings()
Ограничения: Chromium != Cohtml (шрифты, data-bind-*, часть CSS). Ультраширокие 21:9/32:9
в превью обрезаются и у родного HUD — проверять только в игре.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import ROOT, load_config  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = ROOT / "work" / "preview"
SHIMS = {
    "Mark.js": 'const M={name:"Mark",props:["count","status"],render(){return null}};export{M};\n',
    "ControlsWithTooltip.js": 'const C={name:"ControlsWithTooltip",render(){return null}};export{C};\n',
    "ControlsWithTooltip.css": "",
}


def build(radmir_ui: Path) -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    native = OUT / "native"
    shutil.copytree(radmir_ui, native, ignore=shutil.ignore_patterns("oneas-img", "fonts", "sounds", "videos"))
    for main in sorted((ROOT / "Exports").glob("*/Content/UserInterface/Main")):
        shutil.copytree(main, native, dirs_exist_ok=True)
    for name, text in SHIMS.items():
        if not (native / "assets" / name).exists():
            (native / "assets" / name).write_text(text, encoding="utf-8")
    tb = native / "assets" / "taxi-banner-icon.js"
    if tb.is_file() and "__preview_shim" not in (s := tb.read_text(encoding="utf-8")) and "export{A as _};" in s:
        tb.write_text(s.replace("export{A as _};", 'const __preview_shim=1,__p=()=>{},__s=()=>{},__a=()=>{},'
                                '__T={ACTIVITY_POINTS:"ACTIVITY_POINTS"};export{A as _,__p as p,__s as s,__a as a,__T as T};'),
                      encoding="utf-8")
    idx = native / "index.html"
    html = idx.read_text(encoding="utf-8")
    if "stub.js" not in html:
        idx.write_text(html.replace("<head>", '<head><script src="/stub.js"></script><script src="/scene.js"></script>', 1),
                       encoding="utf-8")
    for f in ("stub.js", "scene.js", "frame.html"):
        shutil.copy(HERE / f, native / f)
    mod = OUT / "mod"
    shutil.copytree(native, mod)
    for f in (ROOT / "work" / "ui" / "patched" / "UserInterface" / "Main" / "assets").glob("*"):
        shutil.copy(f, mod / "assets" / f.name)
    print(f"Готово: {native} и {mod}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--radmir-ui", help="папка uiresources Radmir (по умолчанию source.build_dir/uiresources)")
    ap.add_argument("--serve", action="store_true")
    a = ap.parse_args()
    ui = Path(a.radmir_ui) if a.radmir_ui else Path((load_config().get("source") or {}).get("build_dir", "")) / "uiresources"
    if not (ui / "index.html").is_file():
        raise SystemExit(f"Не найден {ui / 'index.html'}")
    build(ui)
    if a.serve:
        for port, d in ((8765, "native"), (8766, "mod")):
            subprocess.Popen([sys.executable, "-m", "http.server", str(port)], cwd=OUT / d)
        print("http://localhost:8765/frame.html (родной)  http://localhost:8766/frame.html (мод)")


if __name__ == "__main__":
    main()
