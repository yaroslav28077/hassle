"""Фаза 4 (Дорожка A): Hud.js / Hud.css / Authorization.css / PauseMenu.js под стиль ONEAS STUDIO.

v6: варианты ONEAS и родной HASSLE в одном файле, переключение в игре (панель «Настройки ONEAS»,
кнопка в меню ESC). Логика переключения — tools/oneas_runtime.py.

Читает (только чтение):
- Exports/**/Content/UserInterface/Main/assets/{Hud.js,Hud.css,Authorization.css}
- work/build_only/uiresources/oneas-img/{hud,speed,interfaces}/*

Пишет:
- work/ui/patched/UserInterface/Main/assets/{Hud.js,Hud.css,Authorization.css}
- work/ui/patched/UserInterface/Main/assets/oneas_*.* (дополнительные SVG/PNG/GIF ONEAS)

Запуск:
    python tools/patch_ui.py
"""
from __future__ import annotations

import base64
import re
import shutil
from pathlib import Path

from common import ROOT, get_logger
from oneas_runtime import PANEL_CSS, PANEL_OPTIONS, build_switchable_hud_js, panel_js, scope_css

EXPORTS_DIR = ROOT / "Exports"
ONEAS_IMG = ROOT / "work" / "build_only" / "uiresources" / "oneas-img"
OUT_ASSETS = ROOT / "work" / "ui" / "patched" / "UserInterface" / "Main" / "assets"


def find_export_file(filename: str) -> Path:
    """Найти первый несжатый файл Main/assets/<filename> в папке Exports/."""
    matches = sorted(EXPORTS_DIR.glob(f"*/Content/UserInterface/Main/assets/{filename}"))
    if not matches:
        raise FileNotFoundError(f"Не найден '{filename}' в {EXPORTS_DIR}/*/Content/UserInterface/Main/assets/")
    return matches[0]


def png_data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    cnt = text.count(old)
    if cnt != 1:
        raise RuntimeError(f"Якорь '{label}' найден {cnt} раз(а), ожидалось ровно 1")
    return text.replace(old, new, 1)


def replace_regex_once(text: str, pattern: str, repl: str, label: str) -> str:
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise RuntimeError(f"Regex-якорь '{label}' найден {len(matches)} раз(а), ожидалось ровно 1")
    m = matches[0]
    return text[: m.start()] + repl + text[m.end() :]


def build_svg_inner_override(svg_text: str, fill_color: str) -> list[tuple[str, str]]:
    """Извлечь d-атрибуты <path> из простого SVG-файла ONEAS."""
    paths = []
    for m in re.finditer(r'<path[^>]*\bd="([^"]+)"[^>]*>', svg_text):
        tag = m.group(0)
        rule = ',"fill-rule":"evenodd","clip-rule":"evenodd"' if "evenodd" in tag else ""
        paths.append((m.group(1), f'{{"fill":"{fill_color}"{rule},d:"{m.group(1)}"}}'))
    return paths


def copy_oneas_assets() -> list[str]:
    """Скопировать вспомогательные SVG/PNG/GIF ONEAS в work/ui/patched/UserInterface/Main/assets/."""
    OUT_ASSETS.mkdir(parents=True, exist_ok=True)
    copies = {
        "hud/bg-server.png": "oneas_bg_server.png",
        "hud/radar.png": "oneas_radar.png",
        "hud/wanted-active.svg": "oneas_wanted_active.svg",
        "hud/wanted-inactive.svg": "oneas_wanted_inactive.svg",
        "hud/icon-online.svg": "oneas_icon_online.svg",
        "hud/icon-id.svg": "oneas_icon_id.svg",
        "hud/icon-time.svg": "oneas_icon_time.svg",
        "hud/icon-data.svg": "oneas_icon_data.svg",
        "speed/fuel-bg.svg": "oneas_fuel_bg.svg",
        "speed/fuel-bg_danger.svg": "oneas_fuel_bg_danger.svg",
        "speed/fuel-active.svg": "oneas_fuel_active.svg",
        "speed/fuel-active_danger.svg": "oneas_fuel_active_danger.svg",
        "speed/wash-bg.svg": "oneas_wash_bg.svg",
        "speed/wash-bg_danger.svg": "oneas_wash_bg_danger.svg",
        "speed/wash-active.svg": "oneas_wash_active.svg",
        "speed/wash-active_danger.svg": "oneas_wash_active_danger.svg",
        "interfaces/noise.gif": "oneas_noise.gif",
    }
    copied = []
    for src_rel, dst_name in copies.items():
        src = ONEAS_IMG / src_rel
        if not src.is_file():
            raise FileNotFoundError(f"Отсутствует ресурс ONEAS: {src}")
        shutil.copy2(src, OUT_ASSETS / dst_name)
        copied.append(dst_name)
    return copied


def patch_hud_js(src_text: str) -> str:
    txt = src_text

    # 1. Иконки голода, заморозки и дыхания ONEAS (вшитые PNG data URI)
    hunger_uri = png_data_uri(ONEAS_IMG / "hud" / "icon-hunger.png")
    freeze_uri = png_data_uri(ONEAS_IMG / "hud" / "icon-freeze.png")
    breath_uri = png_data_uri(ONEAS_IMG / "hud" / "icon-breath.png")

    txt = replace_regex_once(txt, r',He="data:image/png;base64,[^"]+"', f',He="{freeze_uri}"', "InfoData_He")
    txt = replace_regex_once(txt, r',Le="data:image/png;base64,[^"]+"', f',Le="{freeze_uri}"', "InfoData_Le")
    txt = replace_regex_once(txt, r',Pe="data:image/png;base64,[^"]+"', f',Pe="{hunger_uri}"', "InfoData_Pe")
    txt = replace_regex_once(txt, r',Ue=""\+new URL\("lungs\.png",import\.meta\.url\)\.href', f',Ue="{breath_uri}"', "HudRadmirInfo_Ue")

    # 2. InfoWanted (qi): звёзды ONEAS (всегда видны 5 звёзд, активная/неактивная)
    old_wanted_render = (
        'function qi(e,s,t,d,r,a){return n(),l("div",{class:b(["hud-radmir-info-wanted",{"hud-radmir-info-wanted_hidden":t.value===0}])},'
        '[(n(!0),l(T,null,D(r.MAX_STARS_COUNT,o=>(n(),l("img",{class:b(["hud-radmir-info-wanted__star",{"hud-radmir-info-wanted__star_active":r.MAX_STARS_COUNT-o<t.value}]),'
        'key:o,src:r.icons[`/src/assets/images/hud/info/${t.isNewYear?"new-year-star":"star"}.png`]},null,10,zi))),128))],2)}'
    )
    new_wanted_render = (
        'const oaWantedActive=""+new URL("oneas_wanted_active.svg",import.meta.url).href,'
        'oaWantedInactive=""+new URL("oneas_wanted_inactive.svg",import.meta.url).href;'
        'function qi(e,s,t,d,r,a){return n(),l("div",{class:"hud-radmir-info-wanted oneas-wanted"},'
        '[(n(!0),l(T,null,D(r.MAX_STARS_COUNT,o=>(n(),l("img",{class:b(["hud-radmir-info-wanted__star",{"hud-radmir-info-wanted__star_active":r.MAX_STARS_COUNT-o<t.value}]),'
        'key:o,src:r.MAX_STARS_COUNT-o<t.value?oaWantedActive:oaWantedInactive},null,10,zi))),128))])}'
    )
    txt = replace_once(txt, old_wanted_render, new_wanted_render, "InfoWanted_qi")

    # 3. InfoData: знак рубля ₽, размеры полос и стили Rn под ONEAS
    txt = replace_once(
        txt,
        'Mn=ue(()=>i("img",{src:qt},null,-1))',
        'Mn=ue(()=>i("span",{class:"oneas-ruble"},"₽",-1))',
        "InfoData_ruble_Mn",
    )
    txt = replace_once(
        txt,
        'width:`${t.info.armour}%`,...r.STYLES.ARMOUR.bar',
        'width:`${7.2*(Math.min(t.info.armour,100)/100)}vh`,...r.STYLES.ARMOUR.bar',
        "InfoData_armour_width",
    )
    txt = replace_once(
        txt,
        'width:`${17.31*(Math.min(t.info.health,100)/100)}vh`',
        'width:`${13.5*(Math.min(t.info.health,100)/100)}vh`',
        "InfoData_health_width",
    )
    txt = replace_once(
        txt,
        'marginLeft:`${11.67*(1-t.info.freeze/100)}vh`,width:`${11.67*(t.info.freeze/100)}vh`',
        'marginLeft:`${13.5*(1-t.info.freeze/100)}vh`,width:`${13.5*(t.info.freeze/100)}vh`',
        "InfoData_freeze_width",
    )
    txt = replace_once(
        txt,
        'marginLeft:`${6.67*(1-t.info.hunger/100)}vh`,width:`${6.67*(t.info.hunger/100)}vh`',
        'marginLeft:`${8.5*(1-t.info.hunger/100)}vh`,width:`${8.5*(t.info.hunger/100)}vh`',
        "InfoData_hunger_width",
    )
    old_rn = (
        'const Rn={ARMOUR:{icon:{right:"-0.93vh"},img:{width:"2.41vh",height:"2.96vh"},bar:{height:"1.11vh",background:"#2e87ff"}},'
        'HEALTH:{img:{width:"4.3vh",height:"3.56vh"},newYearImg:{width:"3.24vh",height:"3.8vh",marginTop:"0.93vh"},bar:{height:"1.11vh",background:"#EAD57C"},barBg:{width:"17.31vh",height:"1.11vh",background:"#beb58c"}},'
        'FREEZE:{bar:{height:"0.56vh",background:"#71CCDF"},barBg:{width:"11.67vh",height:"0.56vh",background:"#81a5ab"}},'
        'HUNGER:{icon:{right:"-1.85vh"},img:{width:"3.06vh",height:"2.78vh"},bar:{height:"1.11vh",background:"#F8F6ED"},barBg:{width:"6.67vh",height:"1.11vh",background:"#b5b5b2"}}}'
    )
    new_rn = (
        'const Rn={ARMOUR:{icon:{right:"0.5vh"},img:{width:"1.65vh",height:"1.8vh"},bar:{height:"0.75vh",background:"#3a8dff"}},'
        'HEALTH:{icon:{right:"0.5vh"},img:{width:"1.85vh",height:"1.85vh"},newYearImg:{width:"1.85vh",height:"1.85vh"},bar:{height:"0.75vh",background:"#EAD57C"},barBg:{width:"13.5vh",height:"0.75vh",background:"rgba(255,255,255,0.22)"}},'
        'FREEZE:{bar:{height:"0.45vh",background:"#71CCDF"},barBg:{width:"13.5vh",height:"0.45vh",background:"rgba(113,204,223,0.28)"}},'
        'HUNGER:{icon:{right:"0.5vh"},img:{width:"1.8vh",height:"1.8vh"},bar:{height:"0.75vh",background:"#F8F6ED"},barBg:{width:"8.5vh",height:"0.75vh",background:"rgba(255,255,255,0.22)"}}}'
    )
    txt = replace_once(txt, old_rn, new_rn, "InfoData_Rn")

    # 4. HudRadmirInfo (ao): верхняя правая панель ONEAS (HASSLE ONLINE + сервер, онлайн + ID, полосы, оружие)
    old_ao_start = 'function ao(e,s,t,d,r,a){const o=m("InfoData"),u=m("IconBreathFill");return n(),l("div",{class:b(["hud-radmir-info",{"hud-radmir-info_helloween":t.isHelloween,"hud-radmir-info_new-year":t.isNewYear,"hud-radmir-info_easter":t.isEaster}])},['
    old_ao_end = 't.info.weapon?(n(),l("div",qn,[i("img",{class:"hud-radmir-info__patrons-bg",src:a.patronsBackground},null,8,jn),i("div",Jn,[$n,i("div",eo,[i("div",to,y(t.info.ammoInClip),1),t.isHelloween?(n(),l("img",so)):(n(),l(T,{key:1},[V("|")],64)),V(y(t.info.totalAmmo),1)])])])):h("",!0)])],2)}'
    s_ao = txt.find(old_ao_start)
    e_ao = txt.find(old_ao_end, s_ao)
    if s_ao == -1 or e_ao == -1:
        raise RuntimeError("Не найден блок HudRadmirInfo ao")
    e_ao += len(old_ao_end)
    new_ao = (
        'const oaIconOnline=""+new URL("oneas_icon_online.svg",import.meta.url).href,'
        'oaIconId=""+new URL("oneas_icon_id.svg",import.meta.url).href;'
        'function ao(e,s,t,d,r,a){const o=m("InfoData"),u=m("IconBreathFill");return n(),l("div",{class:b(["hud-radmir-info",{"hud-radmir-info_helloween":t.isHelloween,"hud-radmir-info_new-year":t.isNewYear,"hud-radmir-info_easter":t.isEaster}])},['
        'i("div",{class:"oneas-info-top"},['
        't.bonus>1?(n(),l("div",{key:0,class:"hud-radmir-info__bonus",style:p({backgroundImage:`url(\'${e.bonuseImage[`/src/assets/images/hud/bonus/${t.bonus}.png`]}\')`})},null,4)):h("",!0),'
        'i("div",{class:"oneas-info-brand"},[i("div",{class:"oneas-info-brand__title"},"HASSLE"),i("div",{class:"oneas-info-brand__sub"},"ONLINE")]),'
        'i("div",{class:"hud-radmir-info__server"},[i("div",{class:"hud-radmir-info__server-value"},y(t.server),1)])'
        ']),'
        '(t.info.online>1||t.info.id>0)?(n(),l("div",{key:1,class:"oneas-info-meta"},['
        'i("div",{class:"oneas-info-meta__item"},[i("img",{class:"oneas-info-meta__icon",src:oaIconOnline},null,8,["src"]),V(y(t.info.online),1)]),'
        'i("div",{class:"oneas-info-meta__item"},[i("img",{class:"oneas-info-meta__icon",src:oaIconId},null,8,["src"]),V("ID "+y(t.info.id),1)])'
        '])):h("",!0),'
        'Fn,'
        'c(S,{name:"fade"},{default:_(()=>[t.info.showBars?(n(),l("div",Yn,[c(o,{info:t.info,isHelloween:t.isHelloween,isNewYear:t.isNewYear},null,8,["info","isHelloween","isNewYear"])])):h("",!0)]),_:1}),'
        '(t.info.weapon||t.info.breath<99)?(n(),l("div",{key:2,class:"hud-radmir-info__fist oneas-info-weapon-box"},['
        'i("div",Gn,['
        'c(S,{name:"fade"},{default:_(()=>[t.info.breath<99?(n(),l("div",Wn,[i("img",{src:Ue},null,8,["src"]),i("div",{class:"hud-radmir-info__breath-fill",style:p({top:`${100-t.info.breath}%`})},[c(u)],4)])):h("",!0)]),_:1}),'
        't.info.weapon&&t.info.breath>=99?(n(),l("div",{key:1,class:"hud-radmir-info__fist-weapon",style:p({backgroundImage:`url(\'/images/hud/${t.info.weapon}.png\')`})},null,4)):h("",!0)'
        ']),'
        't.info.weapon?(n(),l("div",qn,[i("div",Jn,[$n,i("div",eo,[i("div",to,y(t.info.ammoInClip),1),V(" / "+y(t.info.totalAmmo),1)])])])):h("",!0)'
        '])):h("",!0)'
        '],2)}'
    )
    txt = txt[:s_ao] + new_ao + txt[e_ao:]

    # 5. SpeedometerSecondary (or): вогнутые датчики чистоты и топлива ONEAS справа от спидометра
    old_or_start = 'function or(e,s,t,d,r,a){const o=m("IconFuel"),u=m("IconWash");return n(),l("div",{class:b(["hud-radmir-speedometer-secondary"'
    old_or_end = 'const rr={props:{speedometer:{type:Object,required:!0}'
    s_or = txt.find(old_or_start)
    e_or = txt.find(old_or_end, s_or)
    if s_or == -1 or e_or == -1:
        raise RuntimeError("Не найден блок SpeedometerSecondary or")
    new_or = (
        'const oaFuelBg=""+new URL("oneas_fuel_bg.svg",import.meta.url).href,'
        'oaFuelBgDanger=""+new URL("oneas_fuel_bg_danger.svg",import.meta.url).href,'
        'oaFuelAct=""+new URL("oneas_fuel_active.svg",import.meta.url).href,'
        'oaFuelActDanger=""+new URL("oneas_fuel_active_danger.svg",import.meta.url).href,'
        'oaWashBg=""+new URL("oneas_wash_bg.svg",import.meta.url).href,'
        'oaWashBgDanger=""+new URL("oneas_wash_bg_danger.svg",import.meta.url).href,'
        'oaWashAct=""+new URL("oneas_wash_active.svg",import.meta.url).href,'
        'oaWashActDanger=""+new URL("oneas_wash_active_danger.svg",import.meta.url).href;'
        'function or(e,s,t,d,r,a){'
        'const o=m("IconFuel"),u=m("IconWash"),'
        'fuelPct=Math.max(0,Math.min(100,(t.speedometer.fuel/Math.max(1,t.speedometer.maxFuel))*100)),'
        'washPct=Math.max(0,Math.min(100,Math.round(t.speedometer.params.wash*100)));'
        'return n(),l("div",{class:"hud-radmir-speedometer-secondary oneas-speed-secondary"},['
        'i("div",{class:b(["oneas-gauge oneas-gauge_wash",{"oneas-gauge_danger":a.isWashDanger}])},['
        'i("img",{class:"oneas-gauge__bg",src:a.isWashDanger?oaWashBgDanger:oaWashBg},null,8,["src"]),'
        'i("div",{class:"oneas-gauge__clip",style:p({height:`${washPct}%`})},['
        'i("img",{class:"oneas-gauge__active oneas-gauge__active_wash",src:a.isWashDanger?oaWashActDanger:oaWashAct},null,8,["src"])'
        '],4),'
        'i("div",{class:"oneas-gauge__content oneas-gauge__content_wash"},[c(u),i("span",{class:"oneas-gauge__val"},y(washPct)+"%",1)])'
        '],2),'
        'i("div",{class:b(["oneas-gauge oneas-gauge_fuel",{"oneas-gauge_danger":a.isFuelDanger}])},['
        'i("img",{class:"oneas-gauge__bg",src:a.isFuelDanger?oaFuelBgDanger:oaFuelBg},null,8,["src"]),'
        'i("div",{class:"oneas-gauge__clip",style:p({height:`${fuelPct}%`})},['
        'i("img",{class:"oneas-gauge__active oneas-gauge__active_fuel",src:a.isFuelDanger?oaFuelActDanger:oaFuelAct},null,8,["src"])'
        '],4),'
        'i("div",{class:"oneas-gauge__content oneas-gauge__content_fuel"},[c(o),i("span",{class:"oneas-gauge__val"},y((t.speedometer.fuel>0?t.speedometer.fuel:0)+(t.speedometer.isElectro?"%":" л")),1)])'
        '],2)'
        '])}'
    )
    txt = txt[:s_or] + new_or + txt[e_or:]

    # 5б. HudRadmirSpeedometer (Ql): Main перед Secondary (датчики справа от круга ONEAS)
    old_ql_pair = (
        'c(u,{speedometer:t.speedometer,isHelloween:t.isHelloween,isNewYear:t.isNewYear},null,8,["speedometer","isHelloween","isNewYear"]),'
        'c(A,{speedometer:t.speedometer,isHelloween:t.isHelloween,isNewYear:t.isNewYear},null,8,["speedometer","isHelloween","isNewYear"])'
    )
    new_ql_pair = (
        'c(A,{speedometer:t.speedometer,isHelloween:t.isHelloween,isNewYear:t.isNewYear},null,8,["speedometer","isHelloween","isNewYear"]),'
        'c(u,{speedometer:t.speedometer,isHelloween:t.isHelloween,isNewYear:t.isNewYear},null,8,["speedometer","isHelloween","isNewYear"])'
    )
    txt = replace_once(txt, old_ql_pair, new_ql_pair, "HudRadmirSpeedometer_order")

    # 5в. SpeedometerMain (Il/Ml/Bl): концентрическая шкала скорости ONEAS
    old_speed_svg = (
        'Il={class:"hud-radmir-speedometer-main__speed-fill",viewBox:"0 0 277 292",fill:"none",xmlns:"http://www.w3.org/2000/svg"},'
        'Ml=ks(()=>i("path",{d:"M163.888 327C73.9277 327 1 253.98 1 163.906C1 76.4798 69.7028 5.12014 156 1M276 45.5886C248.739 19.6833 212.532 3.12391 172.5 1.03611",stroke:"#F4F1E1","stroke-opacity":"0.7","stroke-width":"2","stroke-linecap":"round","stroke-dasharray":"0.1 8"},null,-1)),'
        'kl=["stroke","data-bind-hud-stroke-dashoffset"],xl={key:0,class:"hud-radmir-speedometer-main__data-bg",src:El},Rl=["data-bind-value"],Ol=ks(()=>i("div",{class:"hud-radmir-speedometer-main__data-text"},"км/ч",-1));'
        'function Bl(e,s,t,d,r,a){const o=m("SnowflakesAnimation"),u=m("SpeedometerMileage"),A=m("IconKey"),f=m("SpeedometerHint"),E=m("IconEngine"),I=m("SpeedometerIndicators");'
        'return n(),l("div",Sl,[i("div",{class:b(["hud-radmir-speedometer-main__speed",{"hud-radmir-speedometer-main__speed_helloween":t.isHelloween,"hud-radmir-speedometer-main__speed_new-year":t.isNewYear}])},'
        '[t.isNewYear?(n(),l("div",Tl,[c(o,{smallArea:"",quantity:50})])):h("",!0),'
        '(n(),l("svg",Il,[Ml,i("path",{d:"M163.888 327C73.9277 327 1 253.98 1 163.906C1 76.4798 69.7028 5.12014 156 1L172.5 1.03611C212.532 3.12391 248.739 19.6833 276 45.5886",stroke:t.isNewYear?"#FFD786":"#F4F1E1","stroke-width":"4","stroke-dasharray":"800","stroke-dashoffset":"695","data-bind-hud-stroke-dashoffset":`695 - 535 * window.hudSpeedometer.getSpeedRatio({{Speedometer.speed}}, ${t.speedometer.maxSpeed})`},null,8,kl)])),'
    )
    new_speed_svg = (
        'Il={class:"hud-radmir-speedometer-main__speed-fill",viewBox:"0 0 320 320",fill:"none",xmlns:"http://www.w3.org/2000/svg"},'
        'Ml=ks(()=>i("g",null,['
        'i("path",{d:"M 84.00 291.64 A 152 152 0 1 1 279.78 66.42",stroke:"rgba(255,255,255,0.20)","stroke-width":"12","stroke-linecap":"round"},null,-1),'
        'i("path",{d:"M 87.93 275.33 A 136 136 0 1 1 267.17 243.73",stroke:"rgba(255,255,255,0.42)","stroke-width":"1.5"},null,-1)'
        '],-1)),'
        'kl=["stroke","data-bind-hud-stroke-dashoffset"],xl={key:0,class:"hud-radmir-speedometer-main__data-bg",src:El},Rl=["data-bind-value"],Ol=ks(()=>i("div",{class:"hud-radmir-speedometer-main__data-text"},"км/ч",-1));'
        'function Bl(e,s,t,d,r,a){const o=m("SnowflakesAnimation"),u=m("SpeedometerMileage"),A=m("IconKey"),f=m("SpeedometerHint"),E=m("IconEngine"),I=m("SpeedometerIndicators");'
        'return n(),l("div",Sl,[i("div",{class:b(["hud-radmir-speedometer-main__speed",{"hud-radmir-speedometer-main__speed_helloween":t.isHelloween,"hud-radmir-speedometer-main__speed_new-year":t.isNewYear}])},'
        '[t.isNewYear?(n(),l("div",Tl,[c(o,{smallArea:"",quantity:50})])):h("",!0),'
        '(n(),l("svg",Il,[Ml,i("path",{d:"M 84.00 291.64 A 152 152 0 1 1 279.78 66.42",stroke:t.isNewYear?"#FFD786":"#FFFFFF","stroke-width":"12","stroke-linecap":"round","stroke-dasharray":"695","stroke-dashoffset":"695","data-bind-hud-stroke-dashoffset":`695 - 535 * window.hudSpeedometer.getSpeedRatio({{Speedometer.speed}}, ${t.speedometer.maxSpeed})`},null,8,kl)])),'
    )
    txt = replace_once(txt, old_speed_svg, new_speed_svg, "SpeedometerMain_svg")

    # 6. IconSafeZone (zd/Qd) & IconFishingZone (sc/tc): иконки ONEAS
    zz_paths = build_svg_inner_override((ONEAS_IMG / "hud" / "icon-zz.svg").read_text(encoding="utf-8"), "#65C466")
    fish_paths = build_svg_inner_override((ONEAS_IMG / "hud" / "icon-fish.svg").read_text(encoding="utf-8"), "#F4F1E1")
    txt = replace_once(
        txt,
        'Zd=[Wd,Xd];function Qd(e,s){return n(),l("svg",Gd,Zd)}',
        f'Zd=[Wd,Xd],GdOneas={{width:"25",height:"25",viewBox:"0 0 25 25",fill:"none",xmlns:"http://www.w3.org/2000/svg"}},'
        f'ZdOneas=[i("path",{zz_paths[0][1]},null,-1)];'
        'function Qd(e,s){return n(),l("svg",GdOneas,ZdOneas)}',
        "IconSafeZone_Qd",
    )
    txt = replace_once(
        txt,
        'ec=[Jd,$d];function tc(e,s){return n(),l("svg",jd,ec)}',
        f'ec=[Jd,$d],jdOneas={{width:"25",height:"25",viewBox:"0 0 25 25",fill:"none",xmlns:"http://www.w3.org/2000/svg"}},'
        f'ecOneas=[i("path",{fish_paths[0][1]},null,-1)];'
        'function tc(e,s){return n(),l("svg",jdOneas,ecOneas)}',
        "IconFishingZone_tc",
    )

    # 7. HudMap (kc): карта 39.5x39.5 vh (как в v5, иконки пропорционально 20 vh)
    old_map_styles = (
        'mapWidth(){return this.isMobile?bt:Ct},mapHeight(){return this.isMobile?bt:Ct},mapStyle(){return{width:`${this.mapWidth}vh`,height:`${this.mapHeight}vh`}},'
        'tilesContainerStyle(){return{...this.playerIsInInterior&&{display:"none"}}},gangZonesContainerStyle(){return{...this.playerIsInInterior&&{display:"none"}}},'
        'markerToMapSizeRelation(){return this.isMobile?bc:Cc},'
        'markerImageStyle(){return{width:`${this.mapWidth*this.markerToMapSizeRelation}vh`,height:`${this.mapHeight*this.markerToMapSizeRelation}vh`}},'
        'markerCheckpointStyle(){return{width:`${this.mapWidth*Ye}vh`,height:`${this.mapHeight*Ye}vh`,borderWidth:`${this.mapHeight*Ye*Ec}vh`}},'
        'nearbyPlayerStyle(){return{width:`${this.mapWidth*Ke}vh`,height:`${this.mapHeight*Ke}vh`,borderWidth:`${this.mapHeight*Ke*Sc}vh`}},'
        'playerIconStyle(){return{width:`${this.mapWidth*yt}vh`,height:`${this.mapHeight*yt}vh`}},'
        'markerStyle(){return{width:`${this.mapWidth*this.markerToMapSizeRelation}vh`,height:`${this.mapHeight*this.markerToMapSizeRelation}vh`}}'
    )
    new_map_styles = (
        'mapWidth(){return this.isMobile?bt:39.5},mapHeight(){return this.isMobile?bt:39.5},mapStyle(){return{width:`${this.mapWidth}vh`,height:`${this.mapHeight}vh`}},'
        'tilesContainerStyle(){return{...this.playerIsInInterior&&{display:"none"}}},gangZonesContainerStyle(){return{...this.playerIsInInterior&&{display:"none"}}},'
        'markerToMapSizeRelation(){return this.isMobile?bc:Cc},'
        'markerImageStyle(){const e=this.isMobile?this.mapWidth:20;return{width:`${e*this.markerToMapSizeRelation}vh`,height:`${e*this.markerToMapSizeRelation}vh`}},'
        'markerCheckpointStyle(){const e=this.isMobile?this.mapWidth:20;return{width:`${e*Ye}vh`,height:`${e*Ye}vh`,borderWidth:`${e*Ye*Ec}vh`}},'
        'nearbyPlayerStyle(){const e=this.isMobile?this.mapWidth:20;return{width:`${e*Ke}vh`,height:`${e*Ke}vh`,borderWidth:`${e*Ke*Sc}vh`}},'
        'playerIconStyle(){const e=this.isMobile?this.mapWidth:20;return{width:`${e*yt}vh`,height:`${e*yt}vh`}},'
        'markerStyle(){const e=this.isMobile?this.mapWidth:20;return{width:`${e*this.markerToMapSizeRelation}vh`,height:`${e*this.markerToMapSizeRelation}vh`}}'
    )
    txt = replace_once(txt, old_map_styles, new_map_styles, "HudMap_rect_sizes")

    # 7б. ImmortalityProgressBar (Vc): прямоугольный периметр вокруг радара
    old_vc = (
        'function Vc(e,s,t,d,r,a){const o=m("ShieldIcon");return n(),l("div",{class:b(["immortality-progress-bar",{immortality_mobile:t.isMobile}])},'
        '[Pc,(n(),l("svg",Uc,[i("path",{class:"circle-progress__bg",d:a.path,stroke:"rgba(0, 42, 79, 1)","stroke-width":a.currentStroke,fill:"none"},null,8,Fc),'
        'i("path",{class:"circle-progress__animated",d:a.path,stroke:"rgba(9, 127, 232, 1)","stroke-width":a.currentStroke,fill:"none","stroke-dasharray":a.dasharray,"stroke-dashoffset":a.dashoffset},null,8,Yc)])),'
        'i("div",Kc,[c(o,{class:"immortality-progress-bar__icon--image"})])],2)}'
    )
    new_vc = (
        'function Vc(e,s,t,d,r,a){const o=m("ShieldIcon");return n(),l("div",{class:"immortality-progress-bar oneas-immortality"},['
        '(n(),l("svg",{class:"oneas-immortality__svg",viewBox:"0 0 370 272",fill:"none",xmlns:"http://www.w3.org/2000/svg"},['
        'i("rect",{x:"2",y:"2",width:"366",height:"268",rx:"5",stroke:"rgba(0,42,79,0.55)","stroke-width":"3.5",fill:"none"}), '
        'i("rect",{x:"2",y:"2",width:"366",height:"268",rx:"5",stroke:"#097FE8","stroke-width":"3.5",fill:"none","stroke-dasharray":"1256","stroke-dashoffset":1256*(1-Math.min(Math.max(t.progress,0),100)/100)},null,8,["stroke-dashoffset"])'
        '])),'
        'i("div",{class:"oneas-immortality__icon"},[c(o,{class:"immortality-progress-bar__icon--image"})])'
        '])}'
    )
    txt = replace_once(txt, old_vc, new_vc, "ImmortalityProgressBar_Vc")

    # 8. HudRadmirRadar (yu + Cu): прямоугольный радар без внутренней рамки + часы/дата
    old_radar_start = 'function yu(e,s,t,d,r,a){const o=m("IconSafeZone"),u=m("IconFishingZone"),A=m("ImmortalityProgressBar"),f=m("HudMap"),E=m("TaxiEventNotice");return n(),l("div",cu,['
    old_radar_end = 'const Cu={props:{isHelloween:{type:Boolean,default:!1},isNewYear:{type:Boolean,default:!1},radar:{type:Object,required:!0},immortality:{type:Object,required:!0},isInterior:{type:Boolean,default:!1}},components:{HudMap:xs,IconSafeZone:zd,IconFishingZone:sc,ImmortalityProgressBar:Rs,TaxiEventNotice:Os},data:()=>({borderIcons:Object.assign({"/src/assets/images/hud/radar/border-helloween.png":Ld,"/src/assets/images/hud/radar/border-new-year.png":Pd,"/src/assets/images/hud/radar/border.png":Ud,"/src/assets/images/hud/radar/radar-bg-taxi-activity.png":Fd,"/src/assets/images/hud/radar/radar-bg-taxi-danger.png":Yd,"/src/assets/images/hud/radar/safe-zone-bg.png":Kd}),TAXI_EVENT_VARIANT:oe}),'
    s_r = txt.find(old_radar_start)
    e_r = txt.find(old_radar_end, s_r)
    if s_r == -1 or e_r == -1:
        raise RuntimeError("Не найден блок HudRadmirRadar yu/Cu")
    e_r += len(old_radar_end)

    new_radar = (
        'const oaIconTime=""+new URL("oneas_icon_time.svg",import.meta.url).href,'
        'oaIconDate=""+new URL("oneas_icon_data.svg",import.meta.url).href;'
        'function yu(e,s,t,d,r,a){const o=m("IconSafeZone"),u=m("IconFishingZone"),A=m("ImmortalityProgressBar"),f=m("HudMap"),E=m("TaxiEventNotice");'
        'return n(),l("div",cu,['
        'c(S,{name:"hud-greenzone"},{default:_(()=>[t.radar.greenZone&&!t.radar.fishingZone?(n(),l("div",uu,[hu,c(o),V("Вы в безопасности")])):h("",!0)]),_:1}),'
        'c(S,{name:"hud-greenzone"},{default:_(()=>[t.radar.fishingZone?(n(),l("div",_u,[mu,c(u),V("Зона для рыбалки")])):h("",!0)]),_:1}),'
        'i("div",Au,['
        't.immortality.show?(n(),w(A,{key:1,class:"hud-radmir-radar__radar-border_progress-bar",progress:a.immortalityProgress,style:p({opacity:a.immortalityOpacity})},null,8,["progress","style"])):h("",!0),'
        'i("div",{class:b(["hud-radmir-radar__map",a.mapClasses])},[c(f,null,{default:_(()=>['
        'c(S,{name:"radar-event-border"},{default:_(()=>[t.radar.taxiEvent.show&&t.radar.taxiEvent.variant===e.TAXI_EVENT_VARIANT.DANGER?(n(),l("img",{key:0,class:"hud-radmir-radar__radar-border_event-danger",src:e.borderIcons["/src/assets/images/hud/radar/radar-bg-taxi-danger.png"]},null,8,pu)):h("",!0)]),_:1}),'
        'c(S,{name:"radar-event-border"},{default:_(()=>[t.radar.taxiEvent.show&&t.radar.taxiEvent.variant===e.TAXI_EVENT_VARIANT.ACTIVITY?(n(),l("img",{key:0,class:"hud-radmir-radar__radar-border_event-activity",src:e.borderIcons["/src/assets/images/hud/radar/radar-bg-taxi-activity.png"]},null,8,vu)):h("",!0)]),_:1})'
        ']),_:1})],2),'
        'c(S,{name:"taxi-event-notice",duration:200},{default:_(()=>[t.radar.taxiEvent.show?(n(),w(E,{class:"hud-radmir-radar__event",variant:t.radar.taxiEvent.variant,duration:t.radar.taxiEvent.duration,text:t.radar.taxiEvent.text,isAddition:t.radar.taxiEvent.isAddition,key:t.radar.taxiEvent.triggeredAt},null,8,["variant","duration","text","isAddition"])):h("",!0)]),_:1})'
        ']),'
        't.radar.show?(n(),l("div",{key:2,class:"oneas-radar-meta"},['
        'i("div",{class:"oneas-radar-meta__row"},[i("img",{class:"oneas-radar-meta__icon",src:oaIconTime},null,8,["src"]),i("span",null,y(e.oneasTimeStr),1)]),'
        'i("div",{class:"oneas-radar-meta__row"},[i("img",{class:"oneas-radar-meta__icon",src:oaIconDate},null,8,["src"]),i("span",null,y(e.oneasDateStr),1)])'
        '])):h("",!0)'
        '])}'
        'const Cu={props:{isHelloween:{type:Boolean,default:!1},isNewYear:{type:Boolean,default:!1},radar:{type:Object,required:!0},immortality:{type:Object,required:!0},isInterior:{type:Boolean,default:!1}},'
        'components:{HudMap:xs,IconSafeZone:zd,IconFishingZone:sc,ImmortalityProgressBar:Rs,TaxiEventNotice:Os},'
        'data:()=>({borderIcons:Object.assign({"/src/assets/images/hud/radar/border-helloween.png":Ld,"/src/assets/images/hud/radar/border-new-year.png":Pd,"/src/assets/images/hud/radar/border.png":Ud,"/src/assets/images/hud/radar/radar-bg-taxi-activity.png":Fd,"/src/assets/images/hud/radar/radar-bg-taxi-danger.png":Yd,"/src/assets/images/hud/radar/safe-zone-bg.png":Kd}),TAXI_EVENT_VARIANT:oe,oneasTimeStr:"",oneasDateStr:"",oneasClockTimer:null}),'
        'mounted(){this.updateOneasClock(),this.oneasClockTimer=setInterval(this.updateOneasClock,1e3)},'
        'unmounted(){this.oneasClockTimer&&clearInterval(this.oneasClockTimer)},'
        'methods:{updateOneasClock(){const d=new Date,p2=n=>String(n).padStart(2,"0"),rt=this.$root&&this.$root.time&&this.$root.time.string;this.oneasTimeStr=rt&&rt.trim()?rt.trim():`${p2(d.getHours())}:${p2(d.getMinutes())}:${p2(d.getSeconds())}`;this.oneasDateStr=`${p2(d.getDate())}/${p2(d.getMonth()+1)}/${String(d.getFullYear()).slice(-2)}`}},'
    )
    txt = txt[:s_r] + new_radar + txt[e_r:]
    return txt


ONEAS_HUD_CSS = """
/* === ONEAS STUDIO HUD OVERRIDES (Cohtml 3.1.4.1 safe, v5) === */
/* 1. Top-right ONEAS Info & Bars */
.hud-radmir-info[data-v-a8f87ee2]{position:absolute;top:2.2vh;right:2.2vw;display:flex;flex-direction:column;align-items:flex-end;transform-origin:top right}
.hud-radmir-info__bg[data-v-a8f87ee2],.hud-radmir-info_helloween .hud-radmir-info__bg[data-v-a8f87ee2]{display:none}
.oneas-info-top{display:flex;align-items:center;justify-content:flex-end}
.hud-radmir-info__bonus[data-v-a8f87ee2]{position:static;width:3.8vh;height:3.8vh;margin-right:1.1vh;background-size:contain;background-repeat:no-repeat;background-position:50%}
.oneas-info-brand{display:flex;flex-direction:column;align-items:flex-end;margin-right:0.95vh;text-shadow:0 0.14vh 0.35vh rgba(0,0,0,0.75)}
.oneas-info-brand__title{color:#ffffff;font-size:2.35vh;font-weight:800;line-height:2.4vh;letter-spacing:0.06em;font-style:italic}
.oneas-info-brand__sub{color:rgba(255,255,255,0.82);font-size:1.08vh;font-weight:700;line-height:1.2vh;letter-spacing:0.24em}
.hud-radmir-info__server[data-v-a8f87ee2],.hud-radmir-info_helloween .hud-radmir-info__server[data-v-a8f87ee2],.hud-radmir-info_new-year .hud-radmir-info__server[data-v-a8f87ee2]{position:static;margin:0;width:5.1vh;height:5.6vh;background-image:url(./oneas_bg_server.png);background-position:50%;background-repeat:no-repeat;background-size:100% 100%;display:flex;align-items:center;justify-content:center}
.hud-radmir-info__server-value[data-v-a8f87ee2],.hud-radmir-info_helloween .hud-radmir-info__server-value[data-v-a8f87ee2],.hud-radmir-info_new-year .hud-radmir-info__server-value[data-v-a8f87ee2]{color:#ffffff;font-size:2.15vh;font-weight:800;font-style:italic;line-height:2.3vh;margin:0;text-align:center;text-shadow:0 0.14vh 0.28vh rgba(0,0,0,0.45)}
.oneas-info-meta{display:flex;align-items:center;justify-content:flex-end;margin-top:0.65vh}
.oneas-info-meta__item{display:flex;align-items:center;color:#ffffff;font-size:1.6vh;font-weight:600;line-height:1.8vh;margin-left:1.35vh;text-shadow:0 0.14vh 0.35vh rgba(0,0,0,0.75)}
.oneas-info-meta__icon{width:1.8vh;height:1.8vh;margin-right:0.5vh}
.hud-radmir-info-data[data-v-80aa7272]{display:flex;flex-direction:column;align-items:flex-end;margin-top:0.65vh}
.hud-radmir-info-data__wanted[data-v-80aa7272]{order:1;margin:0.15vh 0 0 0}
.hud-radmir-info-wanted.oneas-wanted{display:flex;align-items:center;justify-content:flex-end;opacity:1}
.hud-radmir-info-wanted__star[data-v-d743764b]{width:2.15vh;height:2.15vh;margin-left:0.5vh;opacity:1}
.hud-radmir-info-wanted__star[data-v-d743764b]:first-child{margin-left:0}
.hud-radmir-info-data__money[data-v-80aa7272]{order:2;margin:0.6vh 0 0 0;font-size:2.75vh;font-weight:700;line-height:3.0vh;color:#ffffff;text-shadow:0 0.14vh 0.45vh rgba(0,0,0,0.78)}
.oneas-ruble{margin-right:0.55vh;font-weight:700;color:#ffffff}
.hud-radmir-info-data__money-underline[data-v-80aa7272]{display:none}
.hud-radmir-info-data__bars[data-v-80aa7272]{order:3;margin:0.75vh 0 0 0;display:flex;flex-direction:column;align-items:flex-end}
.hud-radmir-info-data__bar[data-v-80aa7272]:first-child,.hud-radmir-info-data__bar[data-v-80aa7272]:nth-child(2){margin:0}
.hud-radmir-info-data_with-values .hud-radmir-info-data__bar_two[data-v-80aa7272],.hud-radmir-info-data_with-values .hud-radmir-info-data__bar_hunger[data-v-80aa7272],.hud-radmir-info-data_with-values .hud-radmir-info-data__bar_armour[data-v-80aa7272]{margin-right:0!important}
.hud-radmir-info-data__bar_two[data-v-80aa7272]{width:auto;display:flex;align-items:center;justify-content:flex-end}
.hud-radmir-info-data__bar_health[data-v-80aa7272],.hud-radmir-info-data__bar_armour[data-v-80aa7272],.hud-radmir-info-data__bar_hunger[data-v-80aa7272]{position:relative;height:2.55vh;padding:0;background:rgba(14,16,20,0.62);border:0.12vh solid rgba(255,255,255,0.2);border-radius:0.42vh}
.hud-radmir-info-data__bar_health[data-v-80aa7272]{width:21.2vh}
.hud-radmir-info-data__bar_armour[data-v-80aa7272]{width:14.5vh;margin:0 0.8vh 0 0!important}
.hud-radmir-info-data__bar_hunger[data-v-80aa7272]{width:16.2vh;margin:0.48vh 0 0 0!important}
.hud-radmir-info-data__bar__before[data-v-80aa7272],.hud-radmir-info-data_helloween .hud-radmir-info-data__bar_health .hud-radmir-info-data__bar__before[data-v-80aa7272],.hud-radmir-info-data_helloween .hud-radmir-info-data__bar_armour .hud-radmir-info-data__bar__before[data-v-80aa7272],.hud-radmir-info-data_helloween .hud-radmir-info-data__bar_hunger .hud-radmir-info-data__bar__before[data-v-80aa7272],.hud-radmir-info-data__bar_armour .hud-radmir-info-data__bar__after[data-v-80aa7272]{display:none;background-image:none}
.hud-radmir-info-data__progress-bar[data-v-80aa7272],.hud-radmir-info-data__progress-bar__bg[data-v-80aa7272]{position:absolute;right:2.9vh;top:50%;margin-top:-0.37vh;clip-path:none;border-radius:0.25vh}
.hud-radmir-info-data__progress-bar__bg[data-v-80aa7272]{opacity:1;z-index:0}
.hud-radmir-info-data__progress-bar[data-v-80aa7272]{z-index:1}
.hud-radmir-info-data__progress-bar_armour[data-v-80aa7272],.hud-radmir-info-data__progress-bar_hunger[data-v-80aa7272]{right:2.9vh}
.hud-radmir-info-data__bar-icon[data-v-80aa7272]{position:absolute;right:0.5vh;top:50%;margin-top:-0.95vh;width:1.95vh;height:1.95vh;z-index:2}
.hud-radmir-info-data__bar_health .hud-radmir-info-data__bar-value[data-v-80aa7272],.hud-radmir-info-data__bar_hunger .hud-radmir-info-data__bar-value[data-v-80aa7272],.hud-radmir-info-data__bar_armour .hud-radmir-info-data__bar-value[data-v-80aa7272]{position:absolute;left:0.75vh;right:auto;top:0;margin:0;height:2.55vh;line-height:2.4vh;color:#ffffff;font-size:1.5vh;font-weight:700;text-align:left;z-index:2}
.hud-radmir-info-data__bar_freeze[data-v-80aa7272]{position:absolute;bottom:-0.75vh;right:2.9vh;width:13.5vh}
.hud-radmir-info__fist.oneas-info-weapon-box{background:rgba(14,16,20,0.62);border:0.12vh solid rgba(255,255,255,0.2);border-radius:0.56vh;width:auto;height:auto;padding:0.65vh 1.0vh;margin-top:0.65vh;background-image:none;display:flex;align-items:center}
.hud-radmir-info_helloween .hud-radmir-info__fist.oneas-info-weapon-box{background:rgba(14,16,20,0.62);background-image:none}
.hud-radmir-info__fist.oneas-info-weapon-box .hud-radmir-info__fist-content[data-v-a8f87ee2]{width:7.2vh;height:4.4vh;border:0;border-radius:0}
.hud-radmir-info__fist-weapon[data-v-a8f87ee2]{width:7.0vh;height:4.4vh;background-size:contain}
.hud-radmir-info__breath img[data-v-a8f87ee2]{width:2.6vh;height:2.6vh;margin-bottom:0}
.hud-radmir-info__patrons[data-v-a8f87ee2],.hud-radmir-info_helloween .hud-radmir-info__patrons[data-v-a8f87ee2]{position:static;height:auto;margin-left:0.9vh}

/* 2. Bottom-left ONEAS Rectangular Radar + Time/Date */
.hud-radmir-radar[data-v-232fa212]{bottom:2.4vh;left:2.0vw;width:auto;height:auto;align-items:flex-end;justify-content:flex-start}
.hud-radmir-radar__radar[data-v-232fa212]{width:30.61vh;height:22.5vh;border-radius:0.55vh;overflow:hidden;border:0.12vh solid rgba(0,0,0,0.72);background:rgba(12,14,18,0.85);box-shadow:0 0.45vh 1.8vh rgba(0,0,0,0.55);display:flex;align-items:center;justify-content:center;position:relative}
.hud-radmir-radar__map[data-v-232fa212]{display:flex;align-items:center;justify-content:center;width:100%;height:100%;transform:none}
.hud-hassle-map[data-v-2bfcdd69]{flex-shrink:0;border-radius:0}
.hud-hassle-map .map-mask[data-v-2bfcdd69]{border-radius:0}
.immortality-progress-bar.oneas-immortality[data-v-5166031c],.immortality-progress-bar.oneas-immortality{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:155}
.oneas-immortality__svg{position:absolute;top:0;left:0;width:100%;height:100%;display:block}
.oneas-immortality__icon{position:absolute;top:0.75vh;right:0.75vh;width:2.25vh;height:2.25vh;z-index:2}
.oneas-immortality__icon svg{width:100%;height:100%;display:block}
.hud-radmir-radar__safe-zone[data-v-232fa212],.hud-radmir-radar__fishing-zone[data-v-232fa212]{top:-3.0vh;left:0;width:30.61vh;justify-content:flex-start}
.hud-radmir-radar__safe-zone svg[data-v-232fa212],.hud-radmir-radar__fishing-zone svg[data-v-232fa212]{width:2.1vh;height:2.1vh;margin-right:0.65vh}
.oneas-radar-meta{display:flex;flex-direction:column;align-items:flex-start;margin-left:1.0vh;margin-bottom:0.2vh}
.oneas-radar-meta__row{display:flex;align-items:center;color:#ffffff;font-size:1.58vh;font-weight:600;line-height:2.1vh;margin-top:0.55vh;text-shadow:0 0.14vh 0.35vh rgba(0,0,0,0.85)}
.oneas-radar-meta__icon{width:2.1vh;height:2.1vh;margin-right:0.6vh}

/* 3. Bottom-right ONEAS Speedometer & Curved Wash/Fuel Gauges */
.hud-radmir-speedometer[data-v-fb579311]{bottom:5.2vh;right:2.0vw;padding-right:0;align-items:flex-end}
.hud-radmir-speedometer__after[data-v-fb579311],.hud-radmir-speedometer_helloween .hud-radmir-speedometer__after[data-v-fb579311]{display:none}
.hud-radmir-speedometer-main[data-v-4b583b08]{position:relative;display:flex;flex-direction:column;align-items:center}
.hud-radmir-speedometer-main__speed[data-v-4b583b08],.hud-radmir-speedometer-main__speed_helloween[data-v-4b583b08]{background-image:none;background-color:rgba(18,20,24,0.40);border:none;border-radius:50%;box-shadow:0 0.35vh 1.4vh rgba(0,0,0,0.32);height:25.0vh;width:25.0vh}
.hud-radmir-speedometer-main__data-bg[data-v-4b583b08]{display:none}
.hud-radmir-speedometer-main__speed-fill[data-v-4b583b08]{width:25.0vh;height:25.0vh;left:0;top:0;bottom:auto}
.hud-radmir-speedometer-main__data[data-v-4b583b08]{padding-left:0;margin-top:2.2vh}
.hud-radmir-speedometer-main__data-value[data-v-4b583b08]{font-size:6.8vh;line-height:7.0vh;font-weight:700;color:rgba(255,255,255,0.72)}
.hud-radmir-speedometer-main__data-text[data-v-4b583b08]{margin-top:-0.25vh;font-size:1.35vh;color:rgba(255,255,255,0.55)}
.hud-radmir-speedometer-main__mileage[data-v-4b583b08]{top:4.9vh;bottom:auto;padding-left:0;transform:scale(0.88)}
.hud-radmir-speedometer-main__turns[data-v-4b583b08]{padding-left:0;padding-top:0;top:54%;margin-top:-1.1vh;width:19.6vh}
.hud-radmir-speedometer-hint{background-image:none;width:100%;height:100%}
.hud-radmir-speedometer-hint__content{margin-left:0;margin-top:2.8vh}
.hud-radmir-speedometer-indicators{position:absolute;top:100%;left:50%;transform:translateX(-50%);display:flex;flex-direction:row;align-items:center;justify-content:center;width:auto;margin:0.6vh 0 0 0;padding:0;background:transparent;border:0;z-index:4}
.hud-radmir-speedometer-indicators__item,.hud-radmir-speedometer-indicators__item:first-child,.hud-radmir-speedometer-indicators__item:nth-child(2),.hud-radmir-speedometer-indicators__item:nth-child(3),.hud-radmir-speedometer-indicators__item:nth-child(4){margin:0 0.35vh;padding:0.4vh 0.72vh;background:rgba(16,18,22,0.52);border-radius:0.5vh;display:flex;align-items:center;justify-content:center}
.hud-radmir-speedometer-secondary.oneas-speed-secondary{background-image:none;width:auto;height:auto;margin:0 0 2.88vh -2.7vh;display:flex;flex-direction:column;align-items:flex-end;z-index:3}
.oneas-gauge{position:relative;overflow:visible}
.oneas-gauge_wash{width:6.88vh;height:6.75vh;margin-bottom:0.22vh}
.oneas-gauge_fuel{width:8.13vh;height:10.13vh}
.oneas-gauge__bg{display:block;width:100%;height:100%}
.oneas-gauge__clip{position:absolute;bottom:0;left:0;right:0;overflow:hidden}
.oneas-gauge__active{position:absolute;bottom:0;left:0;display:block}
.oneas-gauge__active_wash{width:6.88vh;height:6.75vh}
.oneas-gauge__active_fuel{width:8.13vh;height:10.13vh}
.oneas-gauge__content{position:absolute;top:0;left:0;right:0;bottom:0;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#ffffff;text-shadow:0 0.14vh 0.28vh rgba(0,0,0,0.85);z-index:2}
.oneas-gauge__content_wash{padding-left:0.85vh}
.oneas-gauge__content_fuel{padding-left:1.55vh}
.oneas-gauge__content svg{width:1.68vh;height:1.68vh;margin-bottom:0.22vh}
.oneas-gauge__val{font-size:1.42vh;font-weight:700;line-height:1.55vh}
"""

ONEAS_AUTH_CSS = """
/* === ONEAS STUDIO AUTHORIZATION OVERLAY (Cohtml safe) === */
.authorization__gradient[data-v-dc361ccd]{background-image:url(./oneas_noise.gif),linear-gradient(69.28deg,#141414eb 26.1%,#14141400 94.95%);background-repeat:repeat,no-repeat;background-size:240px 240px,100% 100%;opacity:0.95}
"""


PAUSE_BTN_OLD = '{icon:"Exit",label:"Выйти из игры",action:"openExitModal",topLine:!0,danger:!0}]'
PAUSE_BTN_NEW = '{icon:"Exit",label:"Выйти из игры",action:"openExitModal",topLine:!0,danger:!0},{icon:"Settings",label:"Настройки ONEAS",action:"openOneasSettings",topLine:!0}]'
PAUSE_M_OLD = 'openSettings(){this.onOpenMainMenu("settings")},'
PAUSE_M_NEW = ('openSettings(){this.onOpenMainMenu("settings")},'
               'openOneasSettings(){this.isMenuVisible=!1,setTimeout(()=>{window.closePauseMenu(),'
               'setTimeout(()=>{window.oneasOpenSettings&&window.oneasOpenSettings()},120)},250)},')


def patch_pause_menu(src_text: str) -> str:
    """Кнопка «Настройки ONEAS» в меню ESC. Добавляется В КОНЕЦ: setPatchButtonLabel пишет в buttons[2]."""
    txt = replace_once(src_text, PAUSE_BTN_OLD, PAUSE_BTN_NEW, "PauseMenu_buttons")
    return replace_once(txt, PAUSE_M_OLD, PAUSE_M_NEW, "PauseMenu_openOneasSettings")


def split_hud_css_sections(css: str) -> dict[str, str]:
    """Разбить ONEAS_HUD_CSS v5 на группы top / radar / speed по комментариям-заголовкам."""
    i1, i2, i3 = css.index("/* 1."), css.index("/* 2."), css.index("/* 3.")
    return {"top": css[i1:i2], "radar": css[i2:i3], "speed": css[i3:]}


def runtime_defaults() -> dict:
    """Значения по умолчанию для панели (build_options.yaml: runtime_defaults), с проверкой допустимых значений."""
    import yaml  # noqa: PLC0415

    d = {"safe": False, "top": "oneas", "radar": "oneas", "speed": "oneas"}
    p = ROOT / "build_options.yaml"
    if p.is_file():
        cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        d.update({k: v for k, v in (cfg.get("runtime_defaults") or {}).items() if k in d})
    choices = {o["key"]: [c[0] for c in o["choices"]] for o in PANEL_OPTIONS}
    for k, allowed in choices.items():
        if d[k] not in allowed:
            raise SystemExit(f"runtime_defaults.{k}={d[k]!r}: допустимо {allowed}")
    d["__choices"] = choices
    return d


def write_text_lf(path: Path, text: str) -> int:
    """Пишем с LF как в оригинале (на Windows write_text превращал \\n в \\r\\n внутри шаблонных строк JS)."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return len(text.encode("utf-8"))


def main() -> None:
    log = get_logger("patch_ui")
    copied = copy_oneas_assets()
    log.info("Скопировано вспомогательных ресурсов ONEAS: %d", len(copied))

    hud_js_src = find_export_file("Hud.js")
    hud_css_src = find_export_file("Hud.css")
    auth_css_src = find_export_file("Authorization.css")
    pause_src = find_export_file("PauseMenu.js")

    orig_js = hud_js_src.read_text(encoding="utf-8")
    v5_js = patch_hud_js(orig_js)  # v5 как «вариант ONEAS» каждой функции
    defaults = runtime_defaults()
    hud_js = build_switchable_hud_js(orig_js, v5_js, defaults, panel_js())
    log.info("Hud.js (переключаемый): %d байт, по умолчанию %s", write_text_lf(OUT_ASSETS / "Hud.js", hud_js),
             {k: v for k, v in defaults.items() if k != "__choices"})

    sections = split_hud_css_sections(ONEAS_HUD_CSS)
    scoped = "\n".join(scope_css(sections[g], f"oa-{g}") for g in ("top", "radar", "speed"))
    hud_css = hud_css_src.read_text(encoding="utf-8") + "\n" + scoped + "\n" + PANEL_CSS
    log.info("Hud.css: %d байт", write_text_lf(OUT_ASSETS / "Hud.css", hud_css))

    auth_css = auth_css_src.read_text(encoding="utf-8") + "\n" + scope_css(ONEAS_AUTH_CSS, "oa-on")
    log.info("Authorization.css: %d байт", write_text_lf(OUT_ASSETS / "Authorization.css", auth_css))

    pause_js = patch_pause_menu(pause_src.read_text(encoding="utf-8"))
    log.info("PauseMenu.js: %d байт", write_text_lf(OUT_ASSETS / "PauseMenu.js", pause_js))


if __name__ == "__main__":
    main()
