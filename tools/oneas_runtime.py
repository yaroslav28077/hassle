"""Сборка «переключаемого» Hud.js: родной HASSLE и вариант ONEAS живут в одном файле.

Идея (без поломки Vue 3 PatchFlags, на которой споткнулся прошлый пилот):
- Оригинальные render-функции НЕ меняются, только переименовываются: NAME -> NAME$o.
- Версия ONEAS (v5) той же функции добавляется рядом как NAME$n.
- Новая NAME(...) — диспетчер oaR(): выбирает $o или $n по настройке группы,
  даёт каждому варианту свой кэш рендера и свой key корневого VNode, чтобы Vue
  при переключении пересоздал поддерево, а не сшивал блоки разной структуры.
- Состояние настроек — реактивный объект в window.App.$data.__oneas: рендеры,
  читающие его, перерисовываются сами. Сохранение — localStorage (с try/catch).
- CSS ONEAS ограничен классами на <html>: oa-on / oa-top / oa-radar / oa-speed.

Ничего не обращается к сети, не читает и не меняет игровые данные, не вешает keydown.
"""
from __future__ import annotations

import json
import re

# ---------------------------------------------------------------- JS-утилиты


def _skip_string(s: str, i: int) -> int:
    """i указывает на открывающую кавычку; вернуть индекс после закрывающей."""
    q = s[i]
    i += 1
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "\\":
            i += 2
            continue
        if q == "`" and ch == "$" and i + 1 < n and s[i + 1] == "{":
            i = _match_brace(s, i + 1) + 1
            continue
        if ch == q:
            return i + 1
        i += 1
    raise ValueError("Незакрытая строка")


def _match_brace(s: str, i: int) -> int:
    """s[i] in '({['; вернуть индекс парной закрывающей скобки (строки/шаблоны учитываются)."""
    pairs = {"(": ")", "{": "}", "[": "]"}
    stack = [pairs[s[i]]]
    i += 1
    n = len(s)
    while i < n:
        ch = s[i]
        if ch in "'\"`":
            i = _skip_string(s, i)
            continue
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in ")}]":
            if ch != stack[-1]:
                raise ValueError(f"Несогласованная скобка на {i}")
            stack.pop()
            if not stack:
                return i
        i += 1
    raise ValueError("Не найдена парная скобка")


def function_span(s: str, name: str) -> tuple[int, int]:
    """(start, end) текста `function NAME(...){...}` (end — после '}'). Ровно одно вхождение."""
    pat = re.compile(r"(?<![\w$])function " + re.escape(name) + r"\(")
    hits = [m.start() for m in pat.finditer(s)]
    if len(hits) != 1:
        raise RuntimeError(f"function {name}: найдено {len(hits)} объявлений, ожидалось 1")
    st = hits[0]
    p = s.index("(", st)
    p_end = _match_brace(s, p)
    b = s.index("{", p_end)
    return st, _match_brace(s, b) + 1


def decl_value(s: str, name: str) -> str:
    """Текст выражения в объявлении `NAME=<expr>` внутри const-цепочки (до верхнеуровневой , или ;)."""
    pat = re.compile(r"(?<![\w$.])" + re.escape(name) + r"=(?!=)")
    hits = [m for m in pat.finditer(s)]
    # отбрасываем вхождения внутри выражений вида a.NAME= (уже исключено) и сравнения
    if not hits:
        raise RuntimeError(f"Объявление {name}= не найдено")
    m = hits[0]
    i = m.end()
    n = len(s)
    st = i
    while i < n:
        ch = s[i]
        if ch in "'\"`":
            i = _skip_string(s, i)
            continue
        if ch in "({[":
            i = _match_brace(s, i) + 1
            continue
        if ch in ",;":
            return s[st:i]
        i += 1
    raise RuntimeError(f"Конец объявления {name} не найден")


def rename_ids(code: str, mapping: dict[str, str]) -> str:
    """Переименовать идентификаторы (не свойства после '.' и не ключи объекта '{X:' / ',X:')."""
    for old, new in mapping.items():
        code = re.sub(r"(?<![\w$.])" + re.escape(old) + r"(?![\w$])", new, code)
        code = re.sub(r"([{,])" + re.escape(new) + r":", r"\1" + old + ":", code)
    return code


# ---------------------------------------------------------------- сборка Hud.js

DUAL = [
    # (имя функции, группа настроек)
    ("qi", "top"), ("xn", "top"), ("ao", "top"),
    ("or", "speed"), ("Ql", "speed"), ("Bl", "speed"),
    ("Qd", "radar"), ("tc", "radar"), ("Vc", "radar"), ("yu", "radar"),
]
# константы, которые v5 изменил: в $n-копиях ссылаемся на oa-версии
CHANGED_CONSTS = {"He": "oaHe", "Le": "oaLe", "Pe": "oaPe", "Ue": "oaUe", "Mn": "oaMn", "Il": "oaIl", "Ml": "oaMl"}
V5_ONLY_DECLS = ["GdOneas", "ZdOneas", "jdOneas", "ecOneas"]


# Доработки v6 поверх v5 (общие для «ONEAS» и «v5»; отличия видны только через CSS html.oa-*-x)
POLISH = {
    "ao": [
        ('i("div",to,y(t.info.ammoInClip),1),V(" / "+y(t.info.totalAmmo),1)',
         'i("div",to,y(t.info.ammoInClip),1),i("span",{class:"oa-ammo-total"},"/"+y(t.info.totalAmmo),1)',
         "ammo_split"),
        ('t.info.weapon?(n(),l("div",qn,[i("div",Jn,[',
         't.info.weapon?(n(),l("div",qn,[i("div",{class:"oa-weapon-name"},y(oaWeaponName(t.info.weapon)),1),i("div",Jn,[',
         "weapon_name"),
    ],
    "qi": [
        ('{class:"hud-radmir-info-wanted oneas-wanted"}',
         '{class:b(["hud-radmir-info-wanted oneas-wanted",{"oa-wanted-zero":t.value===0}])}', "wanted_zero_cls"),
        ('128))])}', '128))],2)}', "wanted_class_flag"),
    ],
    "yu": [
        ('i("span",null,y(e.oneasDateStr),1)])])):h("",!0)])}',
         'i("span",null,y(e.oneasDateStr),1)]),'
         't.radar.greenZone&&!t.radar.fishingZone?(n(),l("div",{key:0,class:"oneas-radar-meta__row oa-zone-row"},[i("span",{class:"oa-zone-badge"},"ZZ"),i("span",{class:"oa-zone-text"},"Безопасная зона")])):h("",!0),'
         't.radar.fishingZone?(n(),l("div",{key:1,class:"oneas-radar-meta__row oa-zone-row oa-zone-row_fish"},[i("span",{class:"oa-zone-badge oa-zone-badge_fish"},[i("img",{class:"oa-zone-badge__img",src:oaIconFish})]),i("span",{class:"oa-zone-text"},"Зона для рыбалки")])):h("",!0)'
         '])):h("",!0),c(oaRadarBars,{info:oaInfoFrom(e)},null,8,["info"])])}',
         "meta_zone_and_bars"),
    ],
    "Vc": [
        ('{class:"oneas-immortality__svg",viewBox:"0 0 370 272",fill:"none",',
         '{class:"oneas-immortality__svg",viewBox:"0 0 370 272",preserveAspectRatio:"none",fill:"none",', "frame_stretch"),
    ],
    "Bl": [
        ('stroke:t.isNewYear?"#FFD786":"#FFFFFF","stroke-width":"12"',
         'stroke:t.isNewYear?"#FFD786":(oaX("speed")?"#1F9D55":"#FFFFFF"),"stroke-width":"12"', "progress_color"),
        ('i("div",{class:"hud-radmir-speedometer-main__data-value",',
         'oaX("speed")?(n(),l("div",{key:0,class:"oa-speed-pad","data-bind-value":`window.oaSpeedPad(window.hudSpeedometer.formatSpeed({{Speedometer.speed}}, ${t.speedometer.measuring}))`},"00",8,["data-bind-value"])):h("",!0),'
         'i("div",{class:"hud-radmir-speedometer-main__data-value",',
         "speed_pad"),
    ],
}


def build_switchable_hud_js(orig: str, v5: str, defaults: dict, panel_js: str) -> str:
    out = orig
    appendix: list[str] = []

    # 1. константы v5 под новыми именами
    for old, new in CHANGED_CONSTS.items():
        appendix.append(f"const {new}={decl_value(v5, old)};")
    appendix.append(f"const oaRnN={decl_value(v5, 'Rn')};")
    for name in V5_ONLY_DECLS:
        appendix.append(f"const {name}={decl_value(v5, name)};")
    # const oaXxx=""+new URL(...).href,... ; (новые ресурсы v5)
    for m in re.finditer(r"const (oa\w+=\"\"\+new URL\(\"[^\"]+\",import\.meta\.url\)\.href(?:,oa\w+=\"\"\+new URL\(\"[^\"]+\",import\.meta\.url\)\.href)*);", v5):
        appendix.append(f"const {m.group(1)};")

    # 2. функции: оригинал -> NAME$o, v5 -> NAME$n, диспетчер NAME
    for name, group in DUAL:
        s0, e0 = function_span(out, name)
        orig_fn = out[s0:e0]
        s1, e1 = function_span(v5, name)
        new_fn = v5[s1:e1]
        if new_fn == orig_fn:
            raise RuntimeError(f"{name}: v5 не отличается от оригинала, проверь DUAL")
        new_fn = rename_ids(new_fn, CHANGED_CONSTS).replace("r.STYLES.", "oaRnN.")
        for o_, n_, lbl in POLISH.get(name, []):
            if new_fn.count(o_) != 1:
                raise RuntimeError(f"polish {name}/{lbl}: якорь найден {new_fn.count(o_)} раз(а), ожидалось 1")
            new_fn = new_fn.replace(o_, n_, 1)
        new_fn = new_fn.replace(f"function {name}(", f"function {name}$n(", 1)
        orig_ren = orig_fn.replace(f"function {name}(", f"function {name}$o(", 1)
        out = out[:s0] + orig_ren + out[e0:]
        appendix.append(new_fn)
        appendix.append(f'function {name}(){{return oaR("{group}",{name}$o,{name}$n,this,arguments)}}')

    # 3. computed карты: размеры v5 только при включённом радаре ONEAS
    def methods_from(src: str, anchor: str, end_name: str) -> tuple[int, int, dict[str, str]]:
        st = src.find(anchor)
        if st < 0 or src.count(anchor) != 1:
            raise RuntimeError(f"HudMap computed: якорь {anchor!r} не найден однозначно")
        res: dict[str, str] = {}
        i = st
        while True:
            m = re.match(r"(\w+)\(\)\{", src[i:])
            if not m:
                raise RuntimeError(f"HudMap computed: не разобран метод на {i}")
            b = i + m.end() - 1
            e = _match_brace(src, b)
            res[m.group(1)] = src[b + 1:e]
            i = e + 1
            if m.group(1) == end_name:
                return st, i, res
            if src[i] != ",":
                raise RuntimeError("HudMap computed: ожидалась запятая между методами")
            i += 1
    os_, oe_, om = methods_from(out, "mapWidth(){return this.isMobile?bt:Ct}", "markerStyle")
    _, _, nm = methods_from(v5, "mapWidth(){return this.isMobile?bt:39.5}", "markerStyle")
    if list(om) != list(nm):
        raise RuntimeError(f"HudMap computed: разные наборы методов {list(om)} / {list(nm)}")
    merged = ",".join(
        (f'{k}(){{if(oaOn("radar")){{{nm[k]}}}{om[k]}}}' if nm[k] != om[k] else f"{k}(){{{om[k]}}}") for k in om
    )
    out = out[:os_] + merged + out[oe_:]

    # 4. опции радара (часы/дата для ONEAS) — из v5 целиком, на родной вариант не влияют
    o_cu = "const Cu=" + decl_value(out, "Cu")
    n_cu = "const Cu=" + decl_value(v5, "Cu")
    out = out.replace(o_cu, n_cu, 1)

    # 5. панель настроек: монтируется в корне HUD (Rg), когда открыта
    anchor = 'i("div",{id:r.TOAST_LAYER_ID.HUD},null,8,xg)],2)}'
    if out.count(anchor) != 1:
        raise RuntimeError("Корень HUD (Rg): якорь TOAST_LAYER не найден")
    out = out.replace(
        anchor,
        'i("div",{id:r.TOAST_LAYER_ID.HUD},null,8,xg),oaS().open?(n(),w(oaPanel,{key:"oa-panel"})):(n(),w(oaGear,{key:"oa-gear"}))],2)}',
        1,
    )

    # 6. рантайм + панель
    runtime = RUNTIME_JS.replace("__OA_DEFAULTS__", json.dumps(defaults, ensure_ascii=False))
    appendix.append(runtime)
    appendix.append(panel_js)

    exp = "export{af as default};"
    if out.count(exp) != 1:
        raise RuntimeError("Не найден export{af as default}")
    return out.replace(exp, "\n/* === ONEAS runtime (switchable) === */\n" + "\n".join(appendix) + "\n" + exp, 1)


RUNTIME_JS = r"""
const OA_VERSION="0.1.0",OA_KEY="oneas.hassle.settings.v1",OA_DEFAULTS=__OA_DEFAULTS__,OA_GROUPS=["top","radar","speed"];
let oaStateObj=null;
function oaLoad(){try{const v=JSON.parse(window.localStorage.getItem(OA_KEY)||"null");return v&&typeof v==="object"?v:{}}catch(e){return{}}}
function oaValid(k,v){const opt=(OA_DEFAULTS.__choices||{})[k];return opt?opt.indexOf(v)>=0:typeof v===typeof OA_DEFAULTS[k]}
function oaS(){if(oaStateObj)return oaStateObj;const init={open:!1};for(const k of Object.keys(OA_DEFAULTS))k!=="__choices"&&(init[k]=OA_DEFAULTS[k]);const saved=oaLoad();for(const k of Object.keys(saved))k in init&&k!=="open"&&oaValid(k,saved[k])&&(init[k]=saved[k]);const A=window.App;try{A&&A.$data?(A.$data.__oneas=init,oaStateObj=A.$data.__oneas):oaStateObj=init}catch(e){oaStateObj=init}oaApply();return oaStateObj}
function oaOn(g){const s=oaS();return!s.safe&&s[g]!=="native"}
function oaX(g){const s=oaS();return!s.safe&&s[g]==="oneas"}
function oaApply(){try{const s=oaStateObj;if(!s)return;const c=document.documentElement.classList,on=!s.safe;c.toggle("oa-on",on);for(const g of OA_GROUPS){c.toggle("oa-"+g,on&&s[g]!=="native");c.toggle("oa-"+g+"-x",on&&s[g]==="oneas")}
 c.toggle("oa-bars-radar",on&&s.bars==="radar"&&s.top!=="native"&&s.radar!=="native");c.toggle("oa-noclock",on&&s.clock===!1);c.toggle("oa-noprotect",on&&s.protect==="off");
 c.toggle("oa-nobadges",on&&s.badges===!1);c.toggle("oa-nologo",on&&s.logo===!1);c.toggle("oa-nometa",on&&s.meta===!1);c.toggle("oa-stars-game",on&&s.stars==="game")}catch(e){}}
function oaSave(){try{const s=oaS(),o={};for(const k of Object.keys(OA_DEFAULTS))k!=="__choices"&&(o[k]=s[k]);window.localStorage.setItem(OA_KEY,JSON.stringify(o))}catch(e){}}
function oaSet(k,v){const s=oaS();s[k]=v;oaSave();oaApply()}
function oaReset(){const s=oaS();for(const k of Object.keys(OA_DEFAULTS))k!=="__choices"&&(s[k]=OA_DEFAULTS[k]);oaSave();oaApply()}
function oaPreset(p){const s=oaS(),pr=(OA_DEFAULTS.__presets||{})[p];if(!pr)return;for(const k of Object.keys(pr))k in s&&oaValid(k,pr[k])&&(s[k]=pr[k]);oaSave();oaApply()}
function oaR(g,fo,fn,self,args){const use=oaOn(g),f=use?fn:fo,a=Array.prototype.slice.call(args);if(use&&a[1]){a[1]=a[1].__oaN||(a[1].__oaN=[])}const v=f.apply(self,a);if(v&&typeof v==="object"){try{const k=(v.key==null?"":String(v.key))+(use?"|oaN":"|oaO");v.key=k;v.props=Object.assign({},v.props,{key:k})}catch(e){}}return v}
function oaInfoFrom(ctx){try{let p=ctx&&ctx.$parent;for(let k=0;k<6&&p;k++,p=p.$parent){if(p.data&&p.data.info)return p.data.info;if(p.$data&&p.$data.info)return p.$data.info}}catch(e){}return oaInfo()}
function oaInfo(){try{const H=window.getInterface&&window.getInterface("Hud");return H&&H.$data?H.$data.info:null}catch(e){return null}}
const OA_WEAPONS={1:"Кастет",2:"Клюшка",3:"Дубинка",4:"Нож",5:"Бита",6:"Лопата",7:"Кий",8:"Катана",9:"Бензопила",14:"Цветы",15:"Трость",16:"Граната",17:"Газ",18:"Молотов",22:"Pistol",23:"Silenced",24:"Desert Eagle",25:"Shotgun",26:"Sawn-off",27:"Combat Shotgun",28:"Micro Uzi",29:"MP5",30:"AK-47",31:"M4",32:"Tec-9",33:"Rifle",34:"Sniper",35:"RPG",36:"HS Rocket",37:"Огнемёт",38:"Minigun",41:"Баллончик",42:"Огнетушитель",43:"Камера",46:"Парашют"};
function oaWeaponName(id){return OA_WEAPONS[id]||""}
window.oaSpeedPad=function(v){try{const t=String(v==null?"":v);return/^\d{1,2}$/.test(t)?"000".slice(t.length):""}catch(e){return""}};
window.oneasOpenSettings=function(){const s=oaS();s.open=!0;try{window.setCursorStatus&&window.setCursorStatus("OneasSettings",!0)}catch(e){}};
window.oneasCloseSettings=function(){const s=oaS();s.open=!1;try{window.setCursorStatus&&window.setCursorStatus("OneasSettings",!1)}catch(e){}};
window.oneasSettings=function(){return JSON.parse(JSON.stringify(oaS()))};
const oaIconFish=""+new URL("oneas_icon_fish.svg",import.meta.url).href,oaIconHp=""+new URL("oneas_icon_health.png",import.meta.url).href,oaIconArm=""+new URL("oneas_icon_armour.png",import.meta.url).href,oaIconHun=""+new URL("oneas_icon_hunger.png",import.meta.url).href;
const oaChip=(cls,val,icon)=>{const v=Math.max(0,Math.min(100,Math.round(Number(val)||0)));return c("div",{class:["oa-chip",cls]},[c("div",{class:"oa-chip__fill",style:{width:v+"%"}}),c("img",{class:"oa-chip__icon",src:icon}),c("span",{class:"oa-chip__val"},String(v))])};
const oaRadarBars={name:"OneasRadarBars",props:{info:{type:Object,default:null}},render(){const f=this.info||oaInfo();if(!f)return c("div",{class:"oa-radar-bars"});return c("div",{class:"oa-radar-bars"},[oaChip("oa-chip_hp",f.health,oaIconHp),oaChip("oa-chip_arm",f.armour,oaIconArm),oaChip("oa-chip_hun",f.hunger,oaIconHun)])}};
setTimeout(oaS,0);
"""


# ---------------------------------------------------------------- панель «Настройки ONEAS»
# Рендер без PatchFlags (полный diff) — так безопаснее для внедрённого компонента.
# Имена из импорта Hud.js: i=createElementVNode, c=createVNode, h=createCommentVNode.
PANEL_OPTIONS = [
    {"section": "Вид"},
    {"key": "top", "label": "Верхний HUD", "choices": [["oneas", "ONEAS"], ["v5", "v5"], ["native", "Родной"]]},
    {"key": "radar", "label": "Радар", "choices": [["oneas", "ONEAS"], ["v5", "v5"], ["native", "Родной"]]},
    {"key": "speed", "label": "Спидометр", "choices": [["oneas", "ONEAS"], ["v5", "v5"], ["native", "Родной"]]},
    {"section": "Детали"},
    {"key": "bars", "label": "Полоски HP / броня / голод", "choices": [["radar", "Под радаром"], ["top", "Сверху"]], "needs": ["top", "radar"]},
    {"key": "stars", "label": "Звёзды розыска", "choices": [["always", "Всегда"], ["game", "При розыске"]], "needs": ["top"]},
    {"key": "logo", "label": "Логотип и сервер", "choices": [[True, "Вкл"], [False, "Выкл"]], "needs": ["top"]},
    {"key": "meta", "label": "Онлайн и ID", "choices": [[True, "Вкл"], [False, "Выкл"]], "needs": ["top"]},
    {"key": "clock", "label": "Часы и дата у радара", "choices": [[True, "Вкл"], [False, "Выкл"]], "needs": ["radar"]},
    {"key": "protect", "label": "Рамка защиты от убийства", "choices": [["frame", "Вкл"], ["off", "Выкл"]], "needs": ["radar"]},
    {"key": "badges", "label": "Значки авто (замок, фары…)", "choices": [[True, "Вкл"], [False, "Выкл"]], "needs": ["speed"]},
]

PRESETS = {
    "maximum": {"top": "oneas", "radar": "oneas", "speed": "oneas", "bars": "radar", "stars": "always", "logo": True,
                "meta": True, "clock": True, "protect": "frame", "badges": True},
    "basic": {"top": "oneas", "radar": "oneas", "speed": "native", "bars": "radar", "stars": "game", "logo": True,
              "meta": True, "clock": False, "protect": "frame", "badges": True},
}

PANEL_JS_TEMPLATE = r"""
const OA_PANEL_OPTIONS=__OA_PANEL_OPTIONS__;
const oaSvgGear=()=>c("svg",{class:"oa-gear__svg",viewBox:"0 0 24 24",fill:"none",xmlns:"http://www.w3.org/2000/svg"},[c("path",{d:"M12 8.6a3.4 3.4 0 1 0 0 6.8 3.4 3.4 0 0 0 0-6.8Zm8.1 4.6-1.6 1 .2 1.9-1.4 1.4-1.9-.2-1 1.6h-2l-.9-1.7-1.9-.5-1.6 1-1.7-1 .3-1.9-1.4-1.4L3 13.6v-2l1.7-.9.5-1.9-1-1.6 1-1.7 1.9.3 1.4-1.4L8.4 3h2l1 1.7 1.9.5 1.6-1 1.7 1-.3 1.9 1.4 1.4 1.9-.3 1 1.7-1 1.6.5 1.9 1.7 1v1.7Z",fill:"#FFFFFF"})]);
const oaPanel={name:"OneasSettingsPanel",
 render(){const s=oaS();
  const rowFor=o=>{if(o.section)return c("div",{class:"oa-section",key:"sec-"+o.section},o.section);
   const off=s.safe||(o.needs||[]).some(g=>s[g]==="native");
   return c("div",{class:["oa-row",{"oa-row_disabled":off}],key:o.key},[
    c("div",{class:"oa-row__label"},o.label),
    c("div",{class:"oa-seg"},o.choices.map(ch=>c("div",{key:String(ch[0]),class:["oa-seg__btn",{"oa-seg__btn_active":s[o.key]===ch[0]}],onClick:()=>{off||oaSet(o.key,ch[0])}},ch[1])))])};
  const presets=c("div",{class:"oa-row oa-row_presets",key:"presets"},[c("div",{class:"oa-row__label"},"Пресет"),
    c("div",{class:"oa-seg"},[c("div",{class:"oa-seg__btn",onClick:()=>{s.safe||oaPreset("maximum")}},"Maximum"),c("div",{class:"oa-seg__btn",onClick:()=>{s.safe||oaPreset("basic")}},"Basic")])]);
  const safe=c("div",{class:["oa-row","oa-row_safe"],key:"safe"},[
    c("div",{class:"oa-row__text"},[c("div",{class:"oa-row__label"},"Безопасный режим"),c("div",{class:"oa-row__hint"},"Выключает все правки мода: игра выглядит как оригинал HASSLE")]),
    c("div",{class:"oa-seg"},[c("div",{class:["oa-seg__btn",{"oa-seg__btn_active":s.safe}],onClick:()=>oaSet("safe",!0)},"Вкл"),c("div",{class:["oa-seg__btn",{"oa-seg__btn_active":!s.safe}],onClick:()=>oaSet("safe",!1)},"Выкл")])]);
  return c("div",{class:"oa-panel-wrap"},[c("div",{class:"oa-panel"},[
    c("div",{class:"oa-panel__head"},[c("div",{class:"oa-panel__title"},"Настройки ONEAS"),c("div",{class:"oa-panel__close",onClick:()=>window.oneasCloseSettings()},"×")]),
    (()=>{const di=OA_PANEL_OPTIONS.findIndex((o,i)=>i>0&&o.section);const left=OA_PANEL_OPTIONS.slice(0,di<0?OA_PANEL_OPTIONS.length:di),right=di<0?[]:OA_PANEL_OPTIONS.slice(di);
      return c("div",{class:"oa-panel__body"},[c("div",{class:"oa-col"},[presets].concat(left.map(rowFor)).concat([safe])),c("div",{class:"oa-col"},right.map(rowFor))])})(),
    c("div",{class:"oa-panel__foot"},[c("div",{class:"oa-btn oa-btn_ghost",onClick:()=>oaReset()},"Сбросить"),c("div",{class:"oa-btn",onClick:()=>window.oneasCloseSettings()},"Закрыть")]),
    c("div",{class:"oa-panel__note"},"ONEAS -> HASSLE v"+OA_VERSION+" · спасибо ONEAS STUDIO"),
    c("div",{class:"oa-panel__note oa-panel__note_dim"},"Фон входа, экран загрузки, иконки оружия и GPS задаются при сборке мода")])])}};
const oaGear={name:"OneasSettingsGear",render(){return c("div",{class:"oa-gear",title:"Настройки ONEAS",onClick:()=>window.oneasOpenSettings()},[oaSvgGear()])}};
"""

PANEL_CSS = """
/* === ONEAS settings panel (Cohtml 3.1.4.1: явные шрифты, border-box, без inherit) === */
.oa-panel-wrap{position:absolute;left:0;top:0;width:100vw;height:100vh;display:flex;align-items:center;justify-content:center;background-color:rgba(0,0,0,0.35);z-index:1000;box-sizing:border-box}
.oa-panel{width:104vh;box-sizing:border-box;padding:2.6vh 3.0vh 2.2vh 3.0vh;border-radius:2.0vh;border:0.14vh solid #1fa45b;background-color:rgba(22,24,26,0.94);box-shadow:0 0.6vh 3vh rgba(0,0,0,0.55);font-family:"Hassle Open Sans","Open Sans",var(--fallback-font),sans-serif;color:#ffffff}
.oa-panel__head{display:flex;align-items:center;justify-content:center;position:relative;margin-bottom:1.6vh}
.oa-panel__title{font-family:"Hassle Open Sans Condensed","Open Sans Condensed","Hassle Open Sans",var(--fallback-font),sans-serif;font-weight:700;font-size:3.0vh;line-height:3.4vh;text-transform:uppercase;letter-spacing:0.03em;color:#ffffff}
.oa-panel__close{position:absolute;right:0;top:50%;margin-top:-1.7vh;width:3.4vh;height:3.4vh;line-height:3.2vh;text-align:center;font-family:"Hassle Open Sans","Open Sans",var(--fallback-font),sans-serif;font-size:2.8vh;color:rgba(255,255,255,0.7);border-radius:0.8vh;background-color:rgba(255,255,255,0.08)}
.oa-panel__close:hover{background-color:rgba(255,255,255,0.16);color:#ffffff}
.oa-panel__body{display:flex;flex-direction:row;align-items:flex-start}
.oa-col{display:flex;flex-direction:column;flex:1 1 0;min-width:0;margin-left:1.6vh}
.oa-col:first-child{margin-left:0}
.oa-section{margin-top:1.4vh;margin-bottom:0.1vh;padding-left:0.4vh;font-family:"Hassle Open Sans Condensed","Open Sans Condensed","Hassle Open Sans",var(--fallback-font),sans-serif;font-size:1.45vh;line-height:1.8vh;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#27b864}
.oa-col .oa-section:first-child{margin-top:0}
.oa-row{display:flex;align-items:center;justify-content:space-between;box-sizing:border-box;padding:0.85vh 1.2vh;margin-top:0.7vh;border-radius:0.9vh;background-color:rgba(255,255,255,0.06)}
.oa-row_disabled{opacity:0.45}
.oa-row_safe{margin-top:1.6vh;border:0.12vh solid rgba(31,164,91,0.55)}
.oa-row__text{display:flex;flex-direction:column;flex:1 1 auto;min-width:0}
.oa-row__label{flex:1 1 auto;min-width:0;font-family:"Hassle Open Sans","Open Sans",var(--fallback-font),sans-serif;font-size:1.7vh;line-height:2.1vh;font-weight:600;color:#ffffff}
.oa-row__hint{margin-top:0.3vh;font-family:"Hassle Open Sans","Open Sans",var(--fallback-font),sans-serif;font-size:1.25vh;line-height:1.55vh;color:rgba(255,255,255,0.55)}
.oa-seg{display:flex;flex:0 0 auto;margin-left:1.2vh}
.oa-seg__btn{box-sizing:border-box;min-width:8.2vh;padding:0.7vh 1.1vh;margin-left:0.6vh;border-radius:0.7vh;text-align:center;font-family:"Hassle Open Sans Condensed","Open Sans Condensed","Hassle Open Sans",var(--fallback-font),sans-serif;font-size:1.55vh;line-height:1.9vh;font-weight:700;text-transform:uppercase;color:rgba(255,255,255,0.75);background-color:rgba(255,255,255,0.10)}
.oa-seg__btn:hover{background-color:rgba(255,255,255,0.18)}
.oa-seg__btn_active,.oa-seg__btn_active:hover{color:#ffffff;background-image:linear-gradient(90deg,#1c9a54,#27b864)}
.oa-panel__foot{display:flex;justify-content:center;margin-top:2.2vh}
.oa-btn{box-sizing:border-box;min-width:14vh;padding:1.0vh 2.2vh;margin:0 0.6vh;border-radius:0.8vh;text-align:center;font-family:"Hassle Open Sans Condensed","Open Sans Condensed","Hassle Open Sans",var(--fallback-font),sans-serif;font-size:1.8vh;line-height:2.2vh;font-weight:700;text-transform:uppercase;color:#ffffff;background-image:linear-gradient(90deg,#1c9a54,#27b864)}
.oa-btn_ghost{background-image:none;background-color:rgba(255,255,255,0.10);color:rgba(255,255,255,0.8)}
.oa-panel__note{margin-top:1.5vh;text-align:center;font-family:"Hassle Open Sans","Open Sans",var(--fallback-font),sans-serif;font-size:1.25vh;line-height:1.6vh;color:rgba(255,255,255,0.55)}
.oa-panel__note_dim{margin-top:0.4vh;color:rgba(255,255,255,0.35)}
.oa-gear{position:absolute;top:0.7vh;right:0.7vh;width:2.0vh;height:2.0vh;opacity:0.28;z-index:999}
.oa-gear:hover{opacity:0.9}
.oa-gear__svg{display:block;width:100%;height:100%}
"""


def panel_js(options: list | None = None) -> str:
    return PANEL_JS_TEMPLATE.replace("__OA_PANEL_OPTIONS__", json.dumps(options or PANEL_OPTIONS, ensure_ascii=False))


# ---------------------------------------------------------------- CSS: ограничение правил классом на <html>

def scope_css(css: str, scope: str) -> str:
    """Каждый селектор верхнего уровня -> `html.<scope> <селектор>`. @-правила оставляем как есть."""
    out, i, n = [], 0, len(css)
    while i < n:
        if css.startswith("/*", i):
            j = css.index("*/", i) + 2
            out.append(css[i:j])
            i = j
            continue
        if css[i].isspace():
            out.append(css[i])
            i += 1
            continue
        b = css.index("{", i)
        sel = css[i:b].strip()
        e = _match_brace(css, b)
        body = css[b:e + 1]
        if sel.startswith("@"):
            out.append(sel + body)
        else:
            parts = [p.strip() for p in sel.split(",")]
            out.append(",".join(f"html.{scope} {p}" for p in parts) + body)
        i = e + 1
    return "".join(out)


# ---------------------------------------------------------------- v6: точный вариант ONEAS (по 4K-референсу, Full HD vh)
COND = '"Hassle Open Sans Condensed","Open Sans Condensed","Hassle Open Sans",var(--fallback-font),sans-serif'

ONEAS_X_CSS = """
/* === v6: точный ONEAS — правый верх === */
html.oa-top-x .hud-radmir-info[data-v-a8f87ee2]{top:2.1vh;right:1.67vh}
html.oa-top-x .oneas-info-brand{text-shadow:0 0.12vh 0.4vh rgba(0,0,0,0.6)}
html.oa-top-x .oneas-info-brand__title{font-family:%(c)s;font-style:normal;font-weight:700;font-size:2.7vh;line-height:2.6vh;letter-spacing:0.02em}
html.oa-top-x .oneas-info-brand__sub{font-family:%(c)s;font-weight:400;font-size:1.3vh;line-height:1.5vh;letter-spacing:0.2em;color:rgba(255,255,255,0.85)}
html.oa-top-x .oneas-info-meta{margin-top:1.35vh}
html.oa-top-x .oneas-info-meta__item{font-family:%(c)s;font-weight:400;font-size:1.8vh;line-height:2.0vh;margin-left:1.2vh}
html.oa-top-x .oneas-info-meta__icon{width:1.7vh;height:1.7vh;margin-right:0.45vh}
html.oa-top-x .hud-radmir-info-data[data-v-80aa7272]{margin-top:1.5vh}
html.oa-top-x .hud-radmir-info-wanted__star[data-v-d743764b]{width:1.45vh;height:1.45vh;margin-left:0.42vh}
html.oa-top-x .hud-radmir-info-data__money[data-v-80aa7272]{font-family:%(c)s;font-weight:500;font-size:2.7vh;line-height:3.0vh;margin-top:0.45vh;text-shadow:0 0.15vh 0.5vh rgba(0,0,0,0.7)}
html.oa-top-x .oneas-ruble{font-family:%(c)s;margin-right:0.45vh}
html.oa-top-x .hud-radmir-info__fist.oneas-info-weapon-box{background:none;background-color:transparent;border:0;padding:0;margin-top:3.0vh;flex-direction:column;align-items:flex-end}
html.oa-top-x .hud-radmir-info__fist.oneas-info-weapon-box .hud-radmir-info__fist-content[data-v-a8f87ee2]{width:6.4vh;height:5.8vh}
html.oa-top-x .hud-radmir-info__fist-weapon[data-v-a8f87ee2]{width:6.4vh;height:5.8vh;background-position:100%% 50%%}
html.oa-top-x .hud-radmir-info__patrons[data-v-a8f87ee2]{margin-left:0;margin-top:0.35vh;display:flex;flex-direction:column;align-items:flex-end}
html.oa-top-x .hud-radmir-info__patrons-content img{display:none}
html.oa-top-x .hud-radmir-info__patrons-value[data-v-a8f87ee2],html.oa-top-x .hud-radmir-info__patrons-value__total[data-v-a8f87ee2]{font-family:%(c)s;font-size:1.75vh;line-height:2.0vh;color:#ffffff}
html.oa-top-x .hud-radmir-info__patrons-value__total[data-v-a8f87ee2]{font-weight:700;display:inline}
.oa-ammo-total{color:rgba(255,255,255,0.6)}
.oa-weapon-name{display:none}
html.oa-top-x .oa-weapon-name{display:block;font-family:%(c)s;font-weight:400;font-size:1.75vh;line-height:2.0vh;color:#ffffff;text-align:right;text-shadow:0 0.12vh 0.35vh rgba(0,0,0,0.7)}

/* === v6: точный ONEAS — радар 25x15.8vh, часы/дата/зона справа === */
html.oa-radar-x .hud-radmir-radar[data-v-232fa212]{left:3.43vh;bottom:2.45vh}
html.oa-radar-x .hud-radmir-radar__radar[data-v-232fa212]{width:24.95vh;height:15.8vh;border-radius:0;border:0;box-shadow:none;background-color:#0b0d10}
html.oa-radar-x .hud-radmir-radar__safe-zone[data-v-232fa212],html.oa-radar-x .hud-radmir-radar__fishing-zone[data-v-232fa212]{display:none}
html.oa-radar-x .oneas-radar-meta{margin-left:0.97vh;margin-bottom:0}
html.oa-radar-x .oneas-radar-meta__row{font-family:%(c)s;font-weight:400;font-size:1.65vh;line-height:2.3vh;margin-top:0.48vh;color:#ffffff;text-shadow:0 0.12vh 0.35vh rgba(0,0,0,0.8)}
html.oa-radar-x .oneas-radar-meta__icon{width:2.3vh;height:2.3vh;margin-right:0.5vh;padding:0.35vh;box-sizing:border-box;border-radius:0.45vh;background-color:rgba(190,195,200,0.55)}
.oa-zone-row{display:none}
html.oa-radar-x .oa-zone-row{display:flex}
.oa-zone-badge{display:flex;align-items:center;justify-content:center;flex:0 0 auto;width:2.3vh;height:2.3vh;margin-right:0.5vh;border-radius:0.45vh;background-color:#72f05e;color:#0b0b0b;font-family:%(c)s;font-weight:700;font-size:1.4vh;line-height:2.3vh;text-shadow:none}
.oa-zone-badge_fish{background-color:#3ba7ff}
.oa-zone-badge__img{width:1.6vh;height:1.6vh}
.oa-zone-text{text-transform:uppercase}

/* === v6: плашки HP/броня/голод под радаром === */
.oa-radar-bars{display:none}
html.oa-bars-radar .hud-radmir-info-data__bars[data-v-80aa7272]{display:none}
html.oa-bars-radar .hud-radmir-radar[data-v-232fa212]{bottom:4.8vh}
html.oa-bars-radar .oa-radar-bars{display:flex;position:absolute;left:0;top:100%%;margin-top:0.37vh;width:30.61vh;height:1.85vh}
html.oa-bars-radar.oa-radar-x .oa-radar-bars{width:24.95vh}
.oa-chip{position:relative;flex:1 1 0;height:100%%;margin-left:0.46vh;overflow:hidden;box-sizing:border-box;display:flex;align-items:center}
.oa-chip:first-child{margin-left:0}
.oa-chip_hp{flex-grow:2;background-color:#24502c}
.oa-chip_arm{background-color:#164866}
.oa-chip_hun{background-color:#51381c}
.oa-chip__fill{position:absolute;left:0;top:0;bottom:0}
.oa-chip_hp .oa-chip__fill{background-color:#4c9f57}
.oa-chip_arm .oa-chip__fill{background-color:#1f86c6}
.oa-chip_hun .oa-chip__fill{background-color:#b9782d}
.oa-chip__icon{position:relative;width:1.35vh;height:1.35vh;margin-left:0.75vh;margin-right:0.4vh}
.oa-chip__val{position:relative;font-family:%(c)s;font-weight:700;font-size:1.35vh;line-height:1.85vh;color:#ffffff;text-shadow:0 0.1vh 0.25vh rgba(0,0,0,0.6)}

/* === v6: опции === */
html.oa-noclock .oneas-radar-meta__row:first-child,html.oa-noclock .oneas-radar-meta__row:nth-child(2){display:none}
html.oa-noprotect .immortality-progress-bar.oneas-immortality{display:none}
html.oa-nobadges .hud-radmir-speedometer-indicators{display:none}
html.oa-nologo .oneas-info-top{display:none}
html.oa-nometa .oneas-info-meta{display:none}
html.oa-stars-game .oa-wanted-zero{display:none}
""" % {"c": COND}

ONEAS_X_SPEED_EXTRA = """
/* === v6: точный ONEAS — спидометр (v5 x0.79 + разомкнутая дуга, «028», без фона) === */
html.oa-speed-x .hud-radmir-speedometer[data-v-fb579311]{right:1.4vh;bottom:4.6vh}
html.oa-speed-x .hud-radmir-speedometer-main__speed[data-v-4b583b08],html.oa-speed-x .hud-radmir-speedometer-main__speed_helloween[data-v-4b583b08]{background-color:transparent;box-shadow:none}
html.oa-speed-x .hud-radmir-speedometer-main__data[data-v-4b583b08]{display:flex;flex-direction:row;flex-wrap:wrap;justify-content:center;align-items:flex-end}
html.oa-speed-x .oa-speed-pad,html.oa-speed-x .hud-radmir-speedometer-main__data-value[data-v-4b583b08]{font-family:%(c)s;font-weight:700;font-size:5.6vh;line-height:5.8vh}
.oa-speed-pad{color:rgba(255,255,255,0.32)}
html.oa-speed-x .hud-radmir-speedometer-main__data-value[data-v-4b583b08]{color:#f1ede3}
html.oa-speed-x .hud-radmir-speedometer-main__data-text[data-v-4b583b08]{flex-basis:100%%;width:100%%;margin-top:0;text-align:center;font-family:%(c)s;font-weight:400;font-size:1.55vh;line-height:1.8vh;color:#ffffff;text-transform:uppercase}
html.oa-speed-x .hud-radmir-speedometer-indicators__item{background:none;background-color:transparent;border:0;margin:0 0.9vh}
""" % {"c": COND}


def scale_vh(css: str, k: float) -> str:
    """Умножить все значения в vh на k (для уменьшенной копии v5-спидометра)."""
    return re.sub(r"(-?\d*\.?\d+)vh", lambda m: f"{float(m.group(1)) * k:.3f}".rstrip("0").rstrip(".") + "vh", css)
