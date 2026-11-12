"""Генератор оффлайн-конфигуратора сборки ONEAS -> HASSLE 2.0 (без CDN).

Читает build_options.yaml, mapping/asset_map.csv и миниатюры из work/previews/.
Пишет один автономный HTML-файл: out/configurator.html.
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import json
from pathlib import Path

import yaml

from common import ROOT, get_logger


def encode_preview_data_uri(rel_path: str | None) -> str:
    if not rel_path:
        return ""
    p = ROOT / rel_path
    if not p.is_file():
        return ""
    ext = p.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".gif": "image/gif",
    }.get(ext, "application/octet-stream")
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def collect_no_slot_notes(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.is_file():
        return []
    out: list[dict[str, str]] = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("action") == "no_slot" and r.get("option_group") != "ui_fonts":
                out.append(
                    {
                        "id": r["id"],
                        "group": r["option_group"],
                        "source": Path(r["source_file"]).name,
                        "notes": r["notes"],
                    }
                )
    return out


def generate_html(opt_cfg: dict, no_slot_items: list[dict[str, str]]) -> str:
    payload = {
        "version": opt_cfg.get("version", 1),
        "mod_prefix": opt_cfg.get("mod_prefix", "zzz_OneasPort"),
        "core_pak": opt_cfg.get("core_pak", "zzz_OneasPort_core_P"),
        "active_preset": opt_cfg.get("active_preset", "maximum"),
        "presets": opt_cfg.get("presets", {}),
        "options": [],
        "no_slot_items": no_slot_items,
    }

    for g in opt_cfg.get("options", []):
        g_copy = dict(g)
        new_vars = []
        for v in g.get("variants", []):
            vc = dict(v)
            vc["data_uri"] = encode_preview_data_uri(v.get("preview"))
            new_vars.append(vc)
        g_copy["variants"] = new_vars
        payload["options"].append(g_copy)

    data_json = json.dumps(payload, ensure_ascii=False)
    # Экранируем закрывающий тег внутри JSON на всякий случай
    data_json = data_json.replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ONEAS → HASSLE 2.0 — Конфигуратор сборки</title>
<style>
  :root {{
    --bg: #0f131a;
    --panel: #171d27;
    --card: #1d2431;
    --border: #2c3648;
    --text: #e6ecf5;
    --muted: #93a1b8;
    --accent: #3b82f6;
    --accent-soft: rgba(59, 130, 246, 0.16);
    --warn: #f59e0b;
    --disabled: #232a36;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.45;
  }}
  header {{
    position: sticky;
    top: 0;
    z-index: 10;
    background: rgba(15, 19, 26, 0.94);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--border);
    padding: 14px 24px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }}
  h1 {{ margin: 0; font-size: 18px; font-weight: 700; }}
  .sub {{ font-size: 12px; color: var(--muted); }}
  .toolbar {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }}
  .preset-btn {{
    background: var(--card);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 14px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
  }}
  .preset-btn.active {{
    background: var(--accent-soft);
    border-color: var(--accent);
    color: #93c5fd;
  }}
  .download-btn {{
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 9px 16px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 700;
  }}
  .download-btn:hover {{ filter: brightness(1.1); }}
  main {{
    max-width: 1180px;
    margin: 20px auto 48px;
    padding: 0 20px;
    display: grid;
    gap: 16px;
  }}
  .summary-bar {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 13px;
    color: var(--muted);
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 10px;
  }}
  .option-card {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 18px;
  }}
  .option-card.unavailable {{
    background: var(--disabled);
    opacity: 0.78;
    border-style: dashed;
  }}
  .opt-head {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 10px;
  }}
  .opt-title {{ font-size: 15px; font-weight: 700; }}
  .opt-id {{ font-family: Consolas, monospace; font-size: 11px; color: var(--muted); margin-left: 8px; }}
  .opt-desc {{ font-size: 13px; color: var(--muted); margin-top: 2px; }}
  .reason {{
    margin-top: 8px;
    padding: 8px 10px;
    border-radius: 8px;
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.35);
    color: #fcd34d;
    font-size: 12px;
  }}
  .variants-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 10px;
    margin-top: 10px;
  }}
  .var-item {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 6px;
    align-items: center;
    text-align: center;
    font-size: 12px;
  }}
  .var-item.selected {{
    border-color: var(--accent);
    background: var(--accent-soft);
  }}
  .var-item img {{
    max-width: 100%;
    height: 72px;
    object-fit: contain;
    border-radius: 4px;
    background: repeating-conic-gradient(#262d3a 0% 25%, #1d222c 0% 50%) 50% / 12px 12px;
    padding: 3px;
  }}
  .toggle-row {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px; }}
  .pill {{
    padding: 6px 12px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--card);
    color: var(--text);
    cursor: pointer;
    font-size: 13px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }}
  .pill.selected {{
    border-color: var(--accent);
    background: var(--accent-soft);
  }}
  .pill img {{ width: 28px; height: 28px; object-fit: contain; }}
  .pill:disabled, .var-item.disabled {{
    cursor: not-allowed;
    opacity: 0.55;
  }}
  .noslot-box {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 18px;
    font-size: 12px;
    color: var(--muted);
  }}
  .noslot-list {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 6px 14px;
    margin-top: 8px;
  }}
  code {{ font-family: Consolas, monospace; color: #cbd5e1; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>ONEAS STUDIO → HASSLE 2.0 (Дорожка A: Cohtml UI)</h1>
    <div class="sub">Оффлайн-конфигуратор модулей: выберите пресет или нужные модули и скачайте <code>build_options.yaml</code></div>
  </div>
  <div class="toolbar">
    <div id="preset-buttons"></div>
    <button class="download-btn" id="btn-download">Скачать build_options.yaml</button>
  </div>
</header>
<main>
  <div class="summary-bar" id="summary-bar"></div>
  <div id="options-root"></div>
  <div class="noslot-box" id="noslot-root"></div>
</main>
<script>
const CFG = {data_json};
let activePreset = CFG.active_preset || "maximum";
const state = {{}};

function initFromPreset(presetName) {{
  activePreset = presetName;
  for (const g of CFG.options) {{
    state[g.id] = g.default;
  }}
  const pOpts = (CFG.presets[presetName] && CFG.presets[presetName].options) || {{}};
  for (const [k, v] of Object.entries(pOpts)) {{
    state[k] = v;
  }}
  render();
}}

function setOption(gid, val) {{
  state[gid] = val;
  activePreset = "custom";
  render();
}}

function render() {{
  // Presets
  const pb = document.getElementById("preset-buttons");
  pb.innerHTML = "";
  for (const [pid, p] of Object.entries(CFG.presets)) {{
    const btn = document.createElement("button");
    btn.className = "preset-btn" + (activePreset === pid ? " active" : "");
    btn.textContent = p.label || pid;
    btn.title = p.description || "";
    btn.onclick = () => {{
      if (pid === "custom") {{
        activePreset = "custom";
        render();
      }} else {{
        initFromPreset(pid);
      }}
    }};
    pb.appendChild(btn);
  }}

  // Summary
  let activeCount = 0;
  for (const g of CFG.options) {{
    if (!g.available) continue;
    const v = state[g.id];
    if (v === true || (typeof v === "string" && v !== "none" && v !== "")) activeCount++;
  }}
  document.getElementById("summary-bar").innerHTML =
    `<span>Пресет: <b>${{activePreset}}</b> | Активных модулей: <b>${{activeCount}}</b> (плюс базовый <code>${{CFG.core_pak}}</code>)</span>` +
    `<span>Сборка: <code>python tools/build_mod.py --options build_options.yaml</code></span>`;

  // Options
  const root = document.getElementById("options-root");
  root.innerHTML = "";
  for (const g of CFG.options) {{
    const card = document.createElement("section");
    card.className = "option-card" + (g.available ? "" : " unavailable");
    const head = document.createElement("div");
    head.className = "opt-head";
    head.innerHTML = `<div><div class="opt-title">${{g.name}}<span class="opt-id">[${{g.id}}]</span></div><div class="opt-desc">${{g.description || ""}}</div></div>`;
    card.appendChild(head);

    if (!g.available) {{
      const rsn = document.createElement("div");
      rsn.className = "reason";
      rsn.textContent = "Недоступно: " + (g.unavailable_reason || "нет совместимого слота / требуется FModel");
      card.appendChild(rsn);
    }} else if (g.variants.length > 4) {{
      const grid = document.createElement("div");
      grid.className = "variants-grid";
      for (const v of g.variants) {{
        const item = document.createElement("div");
        item.className = "var-item" + (state[g.id] === v.value ? " selected" : "");
        item.onclick = () => setOption(g.id, v.value);
        if (v.data_uri) {{
          const img = document.createElement("img");
          img.src = v.data_uri;
          img.alt = v.label;
          item.appendChild(img);
        }}
        const lbl = document.createElement("div");
        lbl.textContent = v.label;
        item.appendChild(lbl);
        grid.appendChild(item);
      }}
      card.appendChild(grid);
    }} else {{
      const row = document.createElement("div");
      row.className = "toggle-row";
      for (const v of g.variants) {{
        const btn = document.createElement("button");
        btn.className = "pill" + (state[g.id] === v.value ? " selected" : "");
        btn.onclick = () => setOption(g.id, v.value);
        if (v.data_uri) {{
          const img = document.createElement("img");
          img.src = v.data_uri;
          img.alt = v.label;
          btn.appendChild(img);
        }}
        const sp = document.createElement("span");
        sp.textContent = v.label;
        btn.appendChild(sp);
        row.appendChild(btn);
      }}
      card.appendChild(row);
    }}
    root.appendChild(card);
  }}

  // No slot details
  const nsRoot = document.getElementById("noslot-root");
  if (CFG.no_slot_items && CFG.no_slot_items.length) {{
    nsRoot.innerHTML = `<b>Недоступные отдельные файлы без слота в HASSLE 2.0 (${{CFG.no_slot_items.length}}):</b><div class="noslot-list">` +
      CFG.no_slot_items.map(x => `<div><code>${{x.source}}</code> (${{x.group}}): ${{x.notes}}</div>`).join("") + `</div>`;
  }} else {{
    nsRoot.style.display = "none";
  }}
}}

function yamlScalar(v) {{
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") return String(v);
  return JSON.stringify(String(v));
}}

function buildYamlText() {{
  const out = [];
  out.push(`version: ${{CFG.version}}`);
  out.push(`mod_prefix: ${{CFG.mod_prefix}}`);
  out.push(`core_pak: ${{CFG.core_pak}}`);
  out.push("");
  out.push("presets:");
  for (const [pid, p] of Object.entries(CFG.presets)) {{
    out.push(`  ${{pid}}:`);
    out.push(`    label: ${{yamlScalar(p.label || pid)}}`);
    out.push(`    description: ${{yamlScalar(p.description || "")}}`);
    const opts = (pid === "custom") ? state : (p.options || {{}});
    if (Object.keys(opts).length === 0) {{
      out.push("    options: {{}}");
    }} else {{
      out.push("    options:");
      for (const [ok, ov] of Object.entries(opts)) {{
        out.push(`      ${{ok}}: ${{yamlScalar(ov)}}`);
      }}
    }}
  }}
  out.push("");
  out.push(`active_preset: ${{activePreset}}`);
  out.push("");
  out.push("options:");
  for (const g of CFG.options) {{
    out.push(`  - id: ${{g.id}}`);
    out.push(`    name: ${{yamlScalar(g.name)}}`);
    out.push(`    type: ${{g.type}}`);
    out.push(`    default: ${{yamlScalar(state[g.id])}}`);
    out.push(`    available: ${{yamlScalar(!!g.available)}}`);
    if (g.unavailable_reason) {{
      out.push(`    unavailable_reason: ${{yamlScalar(g.unavailable_reason)}}`);
    }}
    out.push(`    description: ${{yamlScalar(g.description || "")}}`);
    out.push("    variants:");
    for (const v of g.variants) {{
      out.push(`      - value: ${{yamlScalar(v.value)}}`);
      out.push(`        label: ${{yamlScalar(v.label)}}`);
      if (v.preview) out.push(`        preview: ${{yamlScalar(v.preview)}}`);
    }}
  }}
  return out.join("\\n") + "\\n";
}}

document.getElementById("btn-download").onclick = () => {{
  const blob = new Blob([buildYamlText()], {{ type: "text/yaml;charset=utf-8" }});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "build_options.yaml";
  a.click();
  URL.revokeObjectURL(a.href);
}};

initFromPreset(activePreset);
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--options", default="build_options.yaml")
    ap.add_argument("--out", default="out/configurator.html")
    a = ap.parse_args()

    log = get_logger("configurator")
    opt_path = Path(a.options)
    if not opt_path.is_absolute():
        opt_path = ROOT / opt_path
    out_path = Path(a.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path

    opt_cfg = yaml.safe_load(opt_path.read_text(encoding="utf-8"))
    no_slot = collect_no_slot_notes(ROOT / "mapping" / "asset_map.csv")
    html_text = generate_html(opt_cfg, no_slot)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_text, encoding="utf-8")
    log.info("Сгенерирован оффлайн-конфигуратор: %s (%d байт)", out_path, len(html_text.encode("utf-8")))


if __name__ == "__main__":
    main()
