# -*- coding: utf-8 -*-
"""国策树本地编辑器 MVP（Python 本地服务 + 浏览器 UI）

启动：
  python work/focus_editor.py
  python work/focus_editor.py --mod "<mod根目录>" [--mod "..."] [--port 8765]

功能：
- 选择/指定 mod 文件夹（多个 = 按加载顺序覆盖）；
- 可视化查看国策树（图标、前置、互斥、统计）；
- 拖动节点改 x/y、表单改前置/互斥、保存写回原文件（自动 .bak 备份）；
- 导出“覆盖包”ZIP（只含改动文件，解压覆盖到 mod 目录即可）。
"""
import io, os, re, json, zipfile, shutil, time, argparse, threading, webbrowser, sys, string, hashlib
import urllib.request, urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import editor_i18n as i18n

FROZEN = getattr(sys, "frozen", False)
_HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.dirname(_HERE) if os.path.basename(_HERE).lower() == "work" else _HERE
DEFAULT_MOD = None
def _detect_game():
    cands = []
    env = os.environ.get("HOI4_GAME")
    if env:
        cands.append(env)
    for d in "CDEFGH":
        cands += [
            d + r":\SteamLibrary\steamapps\common\Hearts of Iron IV",
            d + r":\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV",
            d + r":\Steam\steamapps\common\Hearts of Iron IV",
        ]
    for c in cands:
        if os.path.isdir(c):
            return c
    return ""

DEFAULT_GAME = _detect_game()
# exe 模式：可写目录 = exe 所在目录；资源目录 = 打包解压目录
APP_DIR = os.path.dirname(sys.executable) if FROZEN else _HERE
RES_DIR = getattr(sys, "_MEIPASS", APP_DIR)
WORK = APP_DIR
BACKUP_DIR = os.path.join(WORK, "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)
ICON_DIR = os.path.join(WORK, "icons")
os.makedirs(ICON_DIR, exist_ok=True)
ICONS = {}
EQUIP_ICONS = {}
TECH_ICONS = {}
SPRITE_MAP = {}
GAME = DEFAULT_GAME
MASCOTS = [
    {"id": "card", "name": "经典", "file": "mascot_card.png", "thumb": "mascot_face.png"},
    {"id": "winter", "name": "冬装", "file": "mascot/winter.png", "thumb": "mascot/winter_thumb.png"},
    {"id": "running", "name": "运动", "file": "mascot/running.png", "thumb": "mascot/running_thumb.png"},
    {"id": "flowers", "name": "花田", "file": "mascot/flowers.png", "thumb": "mascot/flowers_thumb.png"},
    {"id": "classroom", "name": "教室", "file": "mascot/classroom.png", "thumb": "mascot/classroom_thumb.png"},
    {"id": "charm", "name": "邻桌小绒", "file": "mascot/charm.png", "thumb": "mascot/charm_thumb.png"},
    {"id": "cafe", "name": "咖啡店", "file": "mascot/cafe.png", "thumb": "mascot/cafe_thumb.png"},
    {"id": "snow", "name": "雪天", "file": "mascot/snow.png", "thumb": "mascot/snow_thumb.png"},
]
LANGS = ("zh", "en", "ja")
LANG_NAMES = {"zh": "中文", "en": "English", "ja": "日本語"}

# ---------------- HOI4 脚本工具 ----------------
def strip_comments(text):
    out = []
    for line in text.splitlines():
        buf, instr = [], False
        for c in line:
            if c == '"':
                instr = not instr
            if c == '#' and not instr:
                break
            buf.append(c)
        out.append("".join(buf))
    return "\n".join(out)

def brace_match(s, i):
    depth = 0
    instr = False
    while i < len(s):
        c = s[i]
        if c == '"':
            instr = not instr
        elif not instr:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return i

def unq(v):
    v = (v or "").strip()
    return v[1:-1] if len(v) >= 2 and v[0] == '"' and v[-1] == '"' else v

def top_items(body):
    items = []
    i, n = 0, len(body)
    while i < n:
        if body[i] in " \t\r\n":
            i += 1
            continue
        m = re.match(r'([A-Za-z0-9_.\-]+)\s*=\s*', body[i:])
        if not m:
            i += 1
            continue
        key = m.group(1)
        j = i + m.end()
        if j < n and body[j] == '{':
            end = brace_match(body, j)
            items.append((key, body[j + 1:end - 1], True))
            i = end
        else:
            k, instr = j, False
            while k < n:
                c = body[k]
                if c == '"':
                    instr = not instr
                if c == '\n' and not instr:
                    break
                k += 1
            items.append((key, unq(body[j:k]), False))
            i = k
    return items

def find_blocks(text, key):
    out = []
    for m in re.finditer(r'(?m)^\s*%s\s*=\s*\{' % key, text):
        start = text.find('{', m.start())
        if start < 0:
            continue
        end = brace_match(text, start)
        out.append((start, end, text[start + 1:end - 1]))
    return out

def parse_simple_fx(effect):
    """提取常见的一行效果，供面板快捷编辑"""
    out = {}
    pats = [
        ("pp", r"add_political_power\s*=\s*(-?\d+(?:\.\d+)?)"),
        ("stab", r"add_stability\s*=\s*(-?\d+(?:\.\d+)?)"),
        ("ws", r"add_war_support\s*=\s*(-?\d+(?:\.\d+)?)"),
        ("mp", r"add_manpower\s*=\s*(-?\d+(?:\.\d+)?)"),
        ("cp", r"add_command_power\s*=\s*(-?\d+(?:\.\d+)?)"),
        ("army", r"add_army_experience\s*=\s*(-?\d+(?:\.\d+)?)"),
        ("air", r"add_air_experience\s*=\s*(-?\d+(?:\.\d+)?)"),
        ("navy", r"add_navy_experience\s*=\s*(-?\d+(?:\.\d+)?)"),
    ]
    for key, pat in pats:
        m = re.search(r'(?m)^\s*' + pat, effect or "")
        if m:
            try:
                out[key] = float(m.group(1))
            except Exception:
                pass
    return out

def parse_focus_like(body, file="", source=""):
    items = top_items(body)
    def fval(key):
        for k, v, b in items:
            if k == key and not b:
                return v
        return ""
    fid = fval("id")
    if not fid:
        return None
    def fnum(key):
        try:
            return float(fval(key))
        except Exception:
            return None
    prereq, mutex = [], []
    effect, select_effect = "", ""
    for k, v, b in items:
        if k == "prerequisite" and b:
            g = [m.group(1) for m in re.finditer(r'focus\s*=\s*"?([A-Za-z0-9_]+)"?', strip_comments(v))]
            if g:
                prereq.append(g)
        elif k == "mutually_exclusive" and b:
            mutex += [m.group(1) for m in re.finditer(r'focus\s*=\s*"?([A-Za-z0-9_]+)"?', strip_comments(v))]
        elif k == "completion_reward" and b:
            effect = v.strip()
        elif k == "select_effect" and b:
            select_effect = v.strip()
    return {"id": fid, "x": fnum("x"), "y": fnum("y"), "cost": fval("cost"),
            "icon": fval("icon"), "prereq": prereq, "mutex": mutex,
            "effect": effect, "select_effect": select_effect,
            "fx": parse_simple_fx(effect),
            "rel": fval("relative_position_id"), "file": file, "source": source}

# ---------------- 加载 mod 数据 ----------------
ROOTS = []
TREES = {}
TREE_ORDER = []
LOC = {}
CHANGED = {}   # abs file path -> rel path
SHARED_FOCUSES = []
EQUIPMENTS = {}
TECHS = {}
EVENTS = {}
MODULES = {}
ORGS = {}
HISTORY = {}   # abs file path -> {"undo": [snapshot], "redo": [snapshot]}
LAST_FILE = None
HIST_DIR = os.path.join(WORK, "history")
os.makedirs(HIST_DIR, exist_ok=True)

def snapshot(path):
    global LAST_FILE
    try:
        if not os.path.exists(path):
            return
        h = HISTORY.setdefault(path, {"undo": [], "redo": []})
        fn = os.path.join(HIST_DIR, hashlib.sha1(path.encode("utf-8")).hexdigest()[:10]
                          + "_%d.txt" % int(time.time() * 1000))
        shutil.copyfile(path, fn)
        h["undo"].append(fn)
        h["redo"] = []
        LAST_FILE = path
    except Exception as e:
        print("snapshot fail:", e)

def undo_last():
    global LAST_FILE
    if not LAST_FILE or LAST_FILE not in HISTORY:
        return False, "没有可撤销的操作"
    h = HISTORY[LAST_FILE]
    if not h["undo"]:
        return False, "没有可撤销的操作"
    fn = h["undo"].pop()
    cur = os.path.join(HIST_DIR, "redo_%d.txt" % int(time.time() * 1000))
    shutil.copyfile(LAST_FILE, cur)
    h["redo"].append(cur)
    shutil.copyfile(fn, LAST_FILE)
    reload_data()
    return True, "已撤销：%s" % os.path.basename(LAST_FILE)

def redo_last():
    global LAST_FILE
    if not LAST_FILE or LAST_FILE not in HISTORY:
        return False, "没有可重做的操作"
    h = HISTORY[LAST_FILE]
    if not h["redo"]:
        return False, "没有可重做的操作"
    fn = h["redo"].pop()
    cur = os.path.join(HIST_DIR, "undo_%d.txt" % int(time.time() * 1000))
    shutil.copyfile(LAST_FILE, cur)
    h["undo"].append(cur)
    shutil.copyfile(fn, LAST_FILE)
    reload_data()
    return True, "已重做：%s" % os.path.basename(LAST_FILE)

def load_game_loc():
    for lang in ("english", "simp_chinese"):
        d = os.path.join(GAME, "localisation", lang)
        if not os.path.isdir(d):
            continue
        line_re = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"(.*)"\s*$')
        for dirpath, _, files in os.walk(d):
            for fn in files:
                if not fn.endswith(".yml"):
                    continue
                try:
                    for ln in io.open(os.path.join(dirpath, fn), encoding="utf-8-sig", errors="replace").read().splitlines():
                        m = line_re.match(ln)
                        if m:
                            LOC[m.group(1)] = m.group(2)
                except Exception:
                    pass

def load_mod(root):
    root = os.path.abspath(root)
    name = os.path.basename(root.rstrip("\\/")) or root
    nf = os.path.join(root, "common", "national_focus")
    count = 0
    for fn in (sorted(f for f in os.listdir(nf) if f.endswith(".txt")) if os.path.isdir(nf) else []):
        text = strip_comments(io.open(os.path.join(nf, fn), encoding="utf-8", errors="replace").read())
        rel = os.path.join("common", "national_focus", fn)
        for start, end, body in find_blocks(text, "shared_focus"):
            node = parse_focus_like(body, rel, name)
            if node:
                node["shared"] = True
                SHARED_FOCUSES.append(node)
        for start, end, body in find_blocks(text, "focus_tree"):
            items = top_items(body)
            tid, shared_refs, focuses = "", [], []
            t_default, t_country = "", ""
            for k, v, b in items:
                if k == "id":
                    tid = v
                elif k == "default":
                    t_default = v
                elif k == "country" and b:
                    t_country = v.strip()
                elif k == "shared_focus" and not b:
                    shared_refs.append(v)
                elif k == "focus" and b:
                    node = parse_focus_like(v, os.path.join("common","national_focus",fn), name)
                    if node:
                        focuses.append(node)
            if tid:
                if tid in TREES:
                    TREE_ORDER.remove(tid)
                TREES[tid] = {"id": tid, "file": os.path.join("common","national_focus",fn), "source": name, "root": root,
                              "focuses": focuses, "shared": shared_refs,
                              "default": t_default, "country_raw": t_country}
                TREE_ORDER.append(tid)
                count += 1
    # 本地化
    # 先英文后中文：显示优先使用中文
    for lang in ("english", "simp_chinese"):
        d = os.path.join(root, "localisation", lang)
        if not os.path.isdir(d):
            continue
        line_re = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"(.*)"\s*$')
        for dirpath, _, files in os.walk(d):
            for fn in files:
                if not fn.endswith(".yml"):
                    continue
                for ln in io.open(os.path.join(dirpath, fn), encoding="utf-8-sig", errors="replace").read().splitlines():
                    m = line_re.match(ln)
                    if m:
                        LOC[m.group(1)] = m.group(2)
    load_ideas(root)
    load_equipment(root)
    load_modules(root)
    load_orgs(root)
    load_techs(root)
    load_events(root)
    load_countries(root)
    load_states(root)
    return count

def analyze(tree):
    ids = {f["id"] for f in tree["focuses"]}
    edges, missing = [], []
    graph = {f["id"]: [] for f in tree["focuses"]}
    for f in tree["focuses"]:
        for grp in f["prereq"]:
            for p in grp:
                if p in ids:
                    edges.append((p, f["id"]))
                    graph[p].append(f["id"])
                else:
                    missing.append([f["id"], p])
    color = {i: 0 for i in ids}
    cycles = []
    def dfs(u, stack):
        color[u] = 1
        stack.append(u)
        for v in graph[u]:
            if color[v] == 0:
                dfs(v, stack)
            elif color[v] == 1:
                cycles.append(stack[stack.index(v):] + [v])
        stack.pop()
        color[u] = 2
    for i in ids:
        if color[i] == 0:
            dfs(i, [])
    pos, overlaps = {}, []
    for f in tree["focuses"]:
        fx = f.get("ax", f.get("x"))
        fy = f.get("ay", f.get("y"))
        if fx is None:
            continue
        key = (fx, fy)
        if key in pos:
            overlaps.append([pos[key], f["id"]])
        else:
            pos[key] = f["id"]
    return {"edges": edges, "missing": missing, "cycles": cycles, "overlaps": overlaps}

def resolve_positions(tree):
    by = {f["id"]: f for f in tree["focuses"]}
    memo = {}
    def ap(fid, seen=()):
        if fid in memo:
            return memo[fid]
        f = by.get(fid)
        if not f or f["x"] is None:
            return (0.0, 0.0)
        if f.get("rel") and f["rel"] in by and f["rel"] not in seen:
            bx, byy = ap(f["rel"], seen + (fid,))
            r = (bx + f["x"], byy + f["y"])
        else:
            r = (f["x"], f["y"])
        memo[fid] = r
        return r
    for f in tree["focuses"]:
        f["rel_x"], f["rel_y"] = f["x"], f["y"]
        ax, ay = ap(f["id"])
        f["ax"], f["ay"] = ax, ay

def reload_data():
    """重新读取所有 mod，保证保存后界面数据是最新的"""
    global TREES, TREE_ORDER, LOC, IDEAS, SHARED_FOCUSES, EQUIPMENTS, TECHS, EVENTS, MODULES, ORGS
    TREES = {}
    TREE_ORDER = []
    LOC = {}
    IDEAS = {}
    SHARED_FOCUSES = []
    EQUIPMENTS = {}
    TECHS = {}
    EVENTS = {}
    MODULES = {}
    ORGS = {}
    global COUNTRIES, STATES
    COUNTRIES = {}
    STATES = {}
    total = 0
    for r in ROOTS:
        total += load_mod(r)
    link_countries()
    return total

IDEAS = {}

def _looks_like_idea(body):
    keys = {"picture", "modifier", "allowed", "research_bonus", "equivalency",
            "rule", "targeted_modifier", "name", "cancel", "on_add", "on_remove"}
    for k, v, b in top_items(body):
        if k in keys:
            return True
    return False

def _add_idea(key, body, file, source):
    if not re.match(r'^[A-Za-z0-9_]+$', key or ""):
        return
    props = {}
    for s, e, inner in find_blocks(body or "", "modifier"):
        for pm in re.finditer(r'(?m)^\s*([A-Za-z0-9_]+)\s*=\s*([^\s#]+)\s*$', inner):
            props[pm.group(1)] = pm.group(2)
    pic = re.search(r'(?m)^\s*picture\s*=\s*"?([A-Za-z0-9_]+)"?', body or "")
    IDEAS[key] = {"id": key, "file": file, "source": source,
                  "name": LOC.get(key, key),
                  "desc": LOC.get(key + "_desc", ""),
                  "picture": pic.group(1) if pic else "",
                  "props": props,
                  "raw": "%s = {\n%s\n}" % (key, (body or "").strip())}

def load_ideas(root):
    name = os.path.basename(root.rstrip("\\/")) or root
    d = os.path.join(root, "common", "ideas")
    if not os.path.isdir(d):
        return 0
    n = 0
    for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
        rel = os.path.join("common", "ideas", fn)
        raw = io.open(os.path.join(d, fn), encoding="utf-8", errors="replace", newline="").read()
        text = strip_comments(raw)
        for s, e, body in find_blocks(text, "ideas"):
            for k, v, b in top_items(body):
                if not b:
                    continue
                if _looks_like_idea(v):
                    _add_idea(k, v, rel, name); n += 1
                else:
                    for k2, v2, b2 in top_items(v):
                        if b2 and _looks_like_idea(v2):
                            _add_idea(k2, v2, rel, name); n += 1
    return n

def missing_loc():
    out = []
    for tid in TREE_ORDER:
        t = TREES.get(tid)
        if not t:
            continue
        for f in t["focuses"]:
            if f["id"] not in LOC or not LOC.get(f["id"], "").strip():
                out.append({"tree": tid, "id": f["id"], "key": f["id"], "file": t["file"]})
    return out

def error_log(limit=120):
    p = os.path.join(os.path.expanduser("~"), "Documents", "Paradox Interactive",
                     "Hearts of Iron IV", "logs", "error.log")
    lines = []
    if os.path.exists(p):
        try:
            raw = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
            keep = [ln for ln in raw if re.search(r'focus|national_focus|idea|mod/|Error', ln, re.I)]
            lines = keep[-limit:]
        except Exception as e:
            lines = ["读取失败: %s" % e]
    return {"path": p, "lines": lines}

def load_equipment(root):
    name = os.path.basename(root.rstrip("\\/")) or root
    d = os.path.join(root, "common", "units", "equipment")
    if not os.path.isdir(d):
        return 0
    n = 0
    for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
        rel = os.path.join("common", "units", "equipment", fn)
        text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
        for s, e, body in find_blocks(text, "equipments"):
            for k, v, b in top_items(body):
                if not b:
                    continue
                yr = re.search(r'(?m)^\s*year\s*=\s*(\d+)', v)
                bd = re.search(r'(?m)^\s*is_buildable\s*=\s*(\w+)', v)
                props = {}
                for pk in ("year", "is_buildable", "type", "reliability", "maximum_speed",
                           "defense", "breakthrough", "hardness", "soft_attack", "hard_attack",
                           "air_attack", "armor", "piercing", "build_cost_ic",
                           "is_archetype", "archetype", "can_be_produced", "group_by",
                           "interface_category"):
                    m2 = re.search(r'(?m)^\s*%s\s*=\s*([^\s#]+)' % pk, v)
                    if m2 and not m2.group(1).startswith("{"):
                        props[pk] = m2.group(1)
                slots = []
                for sm in re.finditer(r'module_slots\s*=\s*\{', v):
                    sb = v.find('{', sm.start())
                    se = brace_match(v, sb)
                    sbody = v[sb + 1:se - 1]
                    for sk, sv, sbb in top_items(sbody):
                        if not sbb:
                            continue
                        req = re.search(r'(?m)^\s*required\s*=\s*(\w+)', sv)
                        cats = []
                        cmm = re.search(r'allowed_module_categories\s*=\s*\{', sv)
                        if cmm:
                            cb = sv.find('{', cmm.start())
                            ce = brace_match(sv, cb)
                            cats = re.findall(r'[A-Za-z0-9_]+', sv[cb + 1:ce - 1])
                        slots.append({"slot": sk,
                                      "required": (req.group(1).lower() == "yes") if req else False,
                                      "categories": cats})
                EQUIPMENTS[k] = {"id": k, "file": rel, "source": name,
                                 "name": LOC.get(k, k),
                                 "year": yr.group(1) if yr else "",
                                 "buildable": bd.group(1) if bd else "",
                                 "slots": slots,
                                 "picture": (re.search(r'(?m)^\s*picture\s*=\s*"?([A-Za-z0-9_]+)"?', v) or [None, ""])[1],
                                 "props": props,
                                 "raw": "%s = {\n%s\n}" % (k, v.strip())}
                n += 1
    return n

def _looks_tech(body):
    keys = {"research_cost", "start_year", "year", "folder", "path", "xp_research",
            "enable_equipments", "research_cost", "categories"}
    return any(k in keys for k, v, b in top_items(body))

def load_techs(root):
    name = os.path.basename(root.rstrip("\\/")) or root
    d = os.path.join(root, "common", "technologies")
    if not os.path.isdir(d):
        return 0
    n = 0
    for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
        rel = os.path.join("common", "technologies", fn)
        text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
        macros = {}
        for mm in re.finditer(r'(?m)^\s*@([A-Za-z0-9_]+)\s*=\s*(-?[0-9.]+)', text):
            macros[mm.group(1)] = mm.group(2)
        def _num(tok, _m=macros):
            tok = (tok or "").strip()
            if tok.startswith("@"):
                tok = _m.get(tok[1:], "")
            try:
                return float(tok)
            except Exception:
                return None
        for s, e, body in find_blocks(text, "technologies"):
            for k, v, b in top_items(body):
                if not b:
                    continue
                if _looks_tech(v):
                    cand = [(k, v)]
                else:
                    cand = [(k2, v2) for k2, v2, b2 in top_items(v) if b2 and _looks_tech(v2)]
                for tid, tv in cand:
                    yr = re.search(r'(?m)^\s*(?:start_year|year)\s*=\s*(\d+)', tv)
                    fname = "其他"
                    fpx = fpy = None
                    fb = re.search(r'folder\s*=\s*\{', tv)
                    if fb:
                        fstart = tv.find('{', fb.start())
                        fend = brace_match(tv, fstart)
                        finner = tv[fstart + 1:fend - 1]
                        nm = re.search(r'name\s*=\s*"?([A-Za-z0-9_]+)"?', finner)
                        if nm:
                            fname = nm.group(1)
                        pos = re.search(r'position\s*=\s*\{([^}]*)\}', finner)
                        if pos:
                            px = re.search(r'x\s*=\s*([^\s]+)', pos.group(1))
                            py = re.search(r'y\s*=\s*([^\s]+)', pos.group(1))
                            if px:
                                fpx = _num(px.group(1))
                            if py:
                                fpy = _num(py.group(1))
                    fold = re.search(r'name\s*=\s*"?%s"?' % re.escape(fname), tv) if fname != "其他" else None
                    cost = re.search(r'(?m)^\s*research_cost\s*=\s*([0-9.]+)', tv)
                    leads = re.findall(r'leads_to_tech\s*=\s*"?([A-Za-z0-9_]+)"?', tv)
                    pre = []
                    for pm in re.finditer(r'prerequisite\s*=\s*\{', tv):
                        pb = tv.find('{', pm.start())
                        pe = brace_match(tv, pb)
                        pre += re.findall(r'[A-Za-z][A-Za-z0-9_]*', tv[pb + 1:pe - 1])
                    TECHS[tid] = {"id": tid, "file": rel, "source": name,
                                  "name": LOC.get(tid, tid),
                                  "year": yr.group(1) if yr else "",
                                  "path": fname,
                                  "fx": fpx,
                                  "fy": fpy,
                                  "cost": cost.group(1) if cost else "",
                                  "prereq": pre, "leads": leads,
                                  "raw": "%s = {\n%s\n}" % (tid, tv.strip())}
                    n += 1
    for t in TECHS.values():
        t["leads"] = [x for x in t.get("leads", []) if x in TECHS and x != t["id"]]
        t["prereq"] = [p for p in t.get("prereq", []) if p in TECHS and p != t["id"]]
    for tid, t in TECHS.items():
        pre = set(t["prereq"])
        for other in TECHS.values():
            if tid in other.get("leads", []):
                pre.add(other["id"])
        t["prereq"] = sorted(pre)
    return n

# ---------------- 国家 / 州 / 项目体检（v0.55） ----------------
COUNTRIES = {}
STATES = {}


def _first(text, pat, default=""):
    m = re.search(pat, text)
    return m.group(1) if m else default


def _prefer(existing, root):
    """同一个 tag/state 谁说了算：mod 优先于游戏目录（原版参考是只读层）"""
    if not existing:
        return True
    return is_under_game(existing.get("root", ""))


def _read_text(path):
    return strip_comments(io.open(path, encoding="utf-8-sig", errors="replace").read())


def load_countries(root):
    """common/country_tags + common/countries + history/countries"""
    root = os.path.abspath(root)
    name = os.path.basename(root.rstrip("\\/")) or root

    d = os.path.join(root, "common", "country_tags")
    if os.path.isdir(d):
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            rel = os.path.join("common", "country_tags", fn)
            for m in re.finditer(r'(?m)^\s*([A-Z0-9]{2,4})\s*=\s*"([^"]+)"', _read_text(os.path.join(d, fn))):
                tag, defrel = m.group(1), m.group(2)
                cur = COUNTRIES.get(tag)
                if not _prefer(cur, root):
                    continue
                COUNTRIES[tag] = {"tag": tag, "def_file": defrel, "tag_file": rel,
                                  "root": root, "source": name, "color": None,
                                  "history_file": "", "capital": "", "political_power": "",
                                  "stability": "", "war_support": "", "ruling_party": "",
                                  "ideas": [], "techs": [], "focus_trees": [], "oob": "",
                                  "states_owned": [], "states_core": [], "has_def": False}

    # 国家定义文件（颜色 / graphical_culture）
    for tag, c in list(COUNTRIES.items()):
        if c.get("source") != name:
            continue
        rel = (c.get("def_file") or "").replace("/", os.sep)
        for base in (root, GAME):
            p = os.path.join(base, "common", rel) if rel else ""
            if p and os.path.exists(p):
                text = _read_text(p)
                c["has_def"] = True
                c["def_path"] = os.path.join(base, rel)
                cm = re.search(r'(?m)^\s*color\s*=\s*(?:\{)?\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)', text)
                if cm:
                    rgb = [float(cm.group(1)), float(cm.group(2)), float(cm.group(3))]
                    if max(rgb) > 1.0:
                        rgb = [round(v / 255.0, 4) for v in rgb]
                    c["color"] = rgb
                c["graphical_culture"] = _first(text, r'(?m)^\s*graphical_culture\s*=\s*(\w+)')
                break

    # 开局历史
    d = os.path.join(root, "history", "countries")
    if os.path.isdir(d):
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            m = re.match(r'([A-Z0-9]{2,4})\s*-\s*(.+)\.txt$', fn, re.I)
            tag = m.group(1).upper() if m else fn[:-4].strip().upper()[:4]
            text = _read_text(os.path.join(d, fn))
            cur = COUNTRIES.get(tag)
            if not cur:
                # 有历史文件但 country_tags 里没登记：孤儿，体检会报
                COUNTRIES[tag] = {"tag": tag, "def_file": "", "tag_file": "", "root": root,
                                  "source": name, "color": None, "orphan_history": True,
                                  "history_file": "", "capital": "", "political_power": "",
                                  "stability": "", "war_support": "", "ruling_party": "",
                                  "ideas": [], "techs": [], "focus_trees": [], "oob": "",
                                  "states_owned": [], "states_core": [], "has_def": False}
                cur = COUNTRIES[tag]
            elif not (cur.get("root") == root or is_under_game(cur.get("root", ""))):
                continue
            cur["root"] = root
            cur["source"] = name
            cur["history_file"] = os.path.join("history", "countries", fn)
            cur["history_display"] = m.group(2).strip() if m else tag
            cur["capital"] = _first(text, r'(?m)^\s*capital\s*=\s*(\d+)')
            cur["political_power"] = _first(text, r'(?m)^\s*add_political_power\s*=\s*(-?[\d.]+)')
            cur["stability"] = _first(text, r'(?m)^\s*add_stability\s*=\s*(-?[\d.]+)')
            cur["war_support"] = _first(text, r'(?m)^\s*add_war_support\s*=\s*(-?[\d.]+)')
            cur["ruling_party"] = _first(text, r'ruling_party\s*=\s*(\w+)')
            cur["oob"] = _first(text, r'(?m)^\s*oob\s*=\s*"?([^"\n]+)"?')

            ideas = []
            for im in re.finditer(r'add_ideas\s*=\s*\{', text):
                b = text.find('{', im.start())
                e = brace_match(text, b)
                ideas += [x for x in re.findall(r'[A-Za-z0-9_]+', text[b + 1:e - 1])]
            for im in re.finditer(r'(?m)^\s*add_ideas\s*=\s*([A-Za-z0-9_]+)', text):
                ideas.append(im.group(1))
            cur["ideas"] = sorted(set(ideas))

            techs = []
            for tm in re.finditer(r'set_technology\s*=\s*\{', text):
                b = text.find('{', tm.start())
                e = brace_match(text, b)
                for k, v, has_block in top_items(text[b + 1:e - 1]):
                    if not has_block:
                        techs.append(k)
            cur["techs"] = sorted(set(techs))

            trees = []
            for fm in re.finditer(r'load_focus_tree\s*=\s*\{', text):
                b = text.find('{', fm.start())
                e = brace_match(text, b)
                for k, v, has_block in top_items(text[b + 1:e - 1]):
                    if k == "tree" and not has_block:
                        trees.append(v)
            for fm in re.finditer(r'(?m)^\s*load_focus_tree\s*=\s*([A-Za-z0-9_]+)', text):
                trees.append(fm.group(1))
            cur["focus_trees"] = sorted(set(trees))
    return len(COUNTRIES)


def load_states(root):
    """history/states：id / 名称 / 人力 / 类别 / owner / cores / 省份 / 建筑 / 胜利点"""
    root = os.path.abspath(root)
    name = os.path.basename(root.rstrip("\\/")) or root
    d = os.path.join(root, "history", "states")
    if not os.path.isdir(d):
        return 0
    n = 0
    for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
        rel = os.path.join("history", "states", fn)
        text = _read_text(os.path.join(d, fn))
        for s, e, body in find_blocks(text, "state"):
            sid = _first(body, r'(?m)^\s*id\s*=\s*(-?\d+)')
            if not sid:
                continue
            sid = int(sid)
            cur = STATES.get(sid)
            if not _prefer(cur, root):
                continue

            dep = _hist_depths(body)
            hb = he = -1
            hm = re.search(r'(?m)^[ \t]*history\s*=\s*\{', body)
            if hm:
                hb = body.find('{', hm.end() - 1)
                he = brace_match(body, hb)

            def first_at(pat, want, lo=0, hi=None):
                hi = len(body) if hi is None else hi
                for m in re.finditer(pat, body[lo:hi]):
                    pos = lo + m.start()
                    if pos < len(dep) and dep[pos] == want:
                        return m.group(1).strip()
                return ""

            owner = ""
            if hb > 0:
                owner = first_at(r'(?m)^[ \t]*owner\s*=\s*([A-Z0-9]{2,4})', 1, hb, he)
                if not owner:
                    owner = first_at(r'(?m)^[ \t]*owner\s*=\s*([A-Z0-9]{2,4})', 2, hb, he)
            if not owner:
                owner = first_at(r'(?m)^[ \t]*owner\s*=\s*([A-Z0-9]{2,4})', 0)

            cores = []
            for m in re.finditer(r'(?m)^[ \t]*add_core_of\s*=\s*([A-Z0-9]{2,4})', body):
                pos = m.start()
                if pos < len(dep) and dep[pos] in (0, 1, 2):
                    cores.append(m.group(1))

            blds, prov_blds = {}, {}
            bm = re.search(r'(?m)^[ \t]*buildings\s*=\s*\{', body)
            if bm:
                bb = body.find('{', bm.end() - 1)
                be = brace_match(body, bb)
                for bk, bv, has_block in top_items(body[bb + 1:be - 1]):
                    if has_block:
                        sub = {}
                        for sk, sv, sb in top_items(bv):
                            if not sb and sv.strip().isdigit():
                                sub[sk] = int(sv.strip())
                        prov_blds[bk] = sub
                    elif bv.strip().isdigit():
                        blds[bk] = int(bv.strip())

            vps = []
            vm = re.search(r'victory_points\s*=\s*\{([^}]*)\}', body)
            if vm:
                nums = re.findall(r'\d+', vm.group(1))
                for i in range(0, len(nums) - 1, 2):
                    vps.append((int(nums[i]), int(nums[i + 1])))

            pm = re.search(r'provinces\s*=\s*\{([^}]*)\}', body)
            provs = [int(x) for x in re.findall(r'\d+', pm.group(1))] if pm else []
            hist_date = _first(body, r'(?m)^[ \t]*(\d{3,4}\.\d{1,2}\.\d{1,2})\s*=\s*\{')

            STATES[sid] = {
                "id": sid, "file": rel, "root": root, "source": name,
                "name": _first(body, r'(?m)^\s*name\s*=\s*"?([A-Za-z0-9_]+)"?'),
                "manpower": _first(body, r'(?m)^\s*manpower\s*=\s*(\d+)'),
                "category": _first(body, r'(?m)^\s*state_category\s*=\s*(\w+)'),
                "owner": owner, "cores": sorted(set(cores)),
                "provinces": provs, "province_count": len(provs),
                "buildings": blds, "province_buildings": prov_blds,
                "victory_points": vps,
                "history_date": hist_date,
                "has_history": hb > 0,
            }
            n += 1
    return n


STATE_CATEGORIES = ("wasteland", "enclave", "tiny_island", "small_island", "pastoral",
                    "rural", "town", "large_city", "metropolis", "megalopolis")
STATE_BUILDINGS = ("infrastructure", "arms_factory", "industrial_complex", "dockyard",
                   "air_base", "anti_air_building", "radar_station", "synthetic_refinery",
                   "fuel_silo", "rocket_site", "nuclear_reactor")


def states_payload():
    items = []
    for sid in sorted(STATES):
        s = STATES[sid]
        ow = s.get("owner", "") or ""
        items.append({
            "id": sid,
            "name": LOC.get(s.get("name", ""), s.get("name", "")),
            "raw_name": s.get("name", ""),
            "owner": ow,
            "owner_name": LOC.get(ow, ""),
            "cores": len(s.get("cores", [])),
            "manpower": s.get("manpower", ""),
            "category": s.get("category", ""),
            "provinces": s.get("province_count", 0),
            "buildings": sum(s.get("buildings", {}).values()),
        })
    return {"count": len(items), "list": items}


def _state_locate(text):
    m = _hist_find_top(text, re.compile(r'(?m)^[ \t]*state\s*=\s*\{'))
    if not m:
        return None
    b = text.find('{', m.end() - 1)
    return b, brace_match(text, b)


def _state_history_range(body):
    m = re.search(r'(?m)^[ \t]*history\s*=\s*\{', body)
    if not m:
        return None
    b = body.find('{', m.end() - 1)
    return b, brace_match(body, b)


def _insert_pos(body, lo, hi):
    """在块内末尾插入：跳过 `}` 本身与尾部空白"""
    pos = hi - 1 if hi - 1 > lo and body[hi - 1] == '}' else hi
    while pos > lo and body[pos - 1] in " \t\r\n":
        pos -= 1
    return pos


def _set_in_scope(body, key, value, want_depth, lo, hi, insert=False):
    pat = re.compile(r'(?m)^([ \t]*)%s\s*=\s*[^\s#\r\n]+' % re.escape(key))
    dep = _hist_depths(body)
    for m in pat.finditer(body, lo, hi):
        if m.start() < len(dep) and dep[m.start()] == want_depth:
            return body[:m.start()] + (m.group(1) or "") + "%s = %s" % (key, value) + body[m.end():]
    if not insert:
        return body
    indent = "\t" * want_depth
    pos = _insert_pos(body, lo, hi)
    return body[:pos] + "\n" + indent + "%s = %s" % (key, value) + "\n" + body[pos:]


def _drop_in_scope(body, key, depths, lo, hi):
    pat = re.compile(r'(?m)^[ \t]*%s\s*=\s*[^\s#\r\n]*[ \t]*\r?\n?' % re.escape(key))
    dep = _hist_depths(body)
    out, last = [], 0
    hit = False
    for m in pat.finditer(body, lo, hi):
        if m.start() < len(dep) and dep[m.start()] in depths:
            out.append(body[last:m.start()])
            last = m.end()
            hit = True
    if not hit:
        return body
    out.append(body[last:])
    return "".join(out)


def _set_building(body, key, value):
    m = re.search(r'(?m)^[ \t]*buildings\s*=\s*\{', body)
    if not m:
        return body.rstrip() + "\n\t\tbuildings = {\n\t\t\t%s = %d\n\t\t}\n" % (key, value)
    b = body.find('{', m.end() - 1)
    e = brace_match(body, b)
    inner = body[b + 1:e - 1]
    pat = re.compile(r'(?m)^([ \t]*)%s\s*=\s*\d+' % re.escape(key))
    if pat.search(inner):
        inner2 = pat.sub(lambda mm: (mm.group(1) or "\t") + "%s = %d" % (key, value), inner, count=1)
    else:
        inner2 = "\n\t\t\t%s = %d\n" % (key, value) + inner.lstrip("\r\n")
    return body[:b + 1] + inner2 + body[e - 1:]


def _set_prov_building(body, pid, values):
    """省份建筑：values 为 {key: int}，全 0 表示删掉这个省块"""
    positive = {k: v for k, v in values.items() if v and int(v) > 0}
    m = re.search(r'(?m)^[ \t]*buildings\s*=\s*\{', body)
    if not m:
        if not positive:
            return body
        block = "buildings = {\n\t\t%s = {\n" % pid
        block += "".join("\t\t\t%s = %d\n" % (k, v) for k, v in sorted(positive.items()))
        block += "\t\t}\n\t}"
        hist = _state_history_range(body)
        if hist:
            pos = _insert_pos(body, hist[0], hist[1])
            return body[:pos] + "\n" + block + body[pos:]
        return body.rstrip() + "\n" + block + "\n"
    b = body.find('{', m.end() - 1)
    e = brace_match(body, b)
    inner = body[b + 1:e - 1]
    pm = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(str(pid)), inner)
    if pm:
        pb = inner.find('{', pm.end() - 1)
        pe = brace_match(inner, pb)
        line_start = inner.rfind("\n", 0, pm.start()) + 1
        if positive:
            blk = "%s = {\n" % pid
            blk += "".join("\t\t\t\t%s = %d\n" % (k, v) for k, v in sorted(positive.items()))
            blk += "\t\t\t}"
            inner = inner[:line_start] + "\t\t\t" + blk + inner[pe:]
        else:
            inner = inner[:line_start] + inner[pe:]
    elif positive:
        blk = "\t\t\t%s = {\n" % pid
        blk += "".join("\t\t\t\t%s = %d\n" % (k, v) for k, v in sorted(positive.items()))
        blk += "\t\t\t}\n"
        inner = blk + inner.lstrip("\r\n")
    return body[:b + 1] + inner + body[e - 1:]


def _set_victory_points(body, vps):
    """胜利点：vps 为 [[prov, value], ...]，空列表表示删除整块"""
    pairs = [(int(p), int(v)) for p, v in vps if str(p).strip() and str(v).strip()]
    m = re.search(r'(?m)^[ \t]*victory_points\s*=\s*\{', body)
    if m:
        b = body.find('{', m.end() - 1)
        e = brace_match(body, b)
        line_start = body.rfind("\n", 0, m.start()) + 1
        if not pairs:
            return body[:line_start] + body[e:]
        inner = "".join("\n\t\t\t\t%d %d" % (p, v) for p, v in pairs)
        return body[:b + 1] + inner + "\n\t\t\t" + body[e - 1:]
    if not pairs:
        return body
    block = "victory_points = {\n"
    block += "".join("\t\t\t\t%d %d\n" % (p, v) for p, v in pairs)
    block += "\t\t\t}"
    hist = _state_history_range(body)
    if hist:
        pos = _insert_pos(body, hist[0], hist[1])
        return body[:pos] + "\n" + block + body[pos:]
    return body.rstrip() + "\n" + block + "\n"


def _tech_block_range(text, tid):
    """定位科技块：优先顶层，其次嵌套在 folder/分组块里的同名键"""
    pats = [re.compile(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(tid))]
    for pat in pats:
        for m in pat.finditer(text):
            b = text.find('{', m.end() - 1)
            if b < 0:
                continue
            e = brace_match(text, b)
            body = text[b + 1:e - 1]
            # 看起来像科技块：有 folder / path / enable_* / research_cost 之一
            if re.search(r'(?m)^[ \t]*(folder|path|enable_equipments|research_cost|start_year|year)\s*=', body):
                return b, e
    return None


def _tech_coord_token(tok, value, macros):
    """原写法是 @宏 且宏当前值等于新值 → 保持宏名；否则写数字"""
    tok = (tok or "").strip()
    if tok.startswith("@"):
        name = tok[1:]
        mv = macros.get(name)
        try:
            if mv is not None and float(mv) == float(value):
                return tok
        except Exception:
            pass
    return str(int(value))


def tech_move(root, rel, tid, x, y):
    """把科技在树上的位置写回 folder.position 的 x/y（游戏读的就是这两个数）。

    原来写的是 @宏（如 y = @1936）且宏值仍然等于新值时，保留宏名，不会把宏拍平成数字。
    """
    if not root or not rel or not tid:
        return {"ok": False, "msg": "参数不完整"}
    if is_under_game(root):
        return {"ok": False, "msg": "原版目录只读：请先复制到自己的模组再修改"}
    p = os.path.join(root, rel)
    if not os.path.exists(p):
        return {"ok": False, "msg": "找不到文件：" + rel}
    try:
        x = int(round(float(x)))
        y = int(round(float(y)))
    except Exception:
        return {"ok": False, "msg": "坐标必须是整数"}

    text, has_bom = _read_bom_text(p)
    macros = {}
    for mm in re.finditer(r'(?m)^[ \t]*@([A-Za-z0-9_]+)\s*=\s*(-?[0-9.]+)', text):
        macros[mm.group(1)] = mm.group(2)

    loc = _tech_block_range(text, tid)
    if not loc:
        return {"ok": False, "msg": "找不到科技块：" + tid}
    b, e = loc
    block = text[b + 1:e - 1]

    fm = re.search(r'(?m)^[ \t]*folder\s*=\s*\{', block)
    if not fm:
        return {"ok": False, "msg": "这个科技没有 folder 块，先在文件里给它加 folder = { name = ... } 再拖"}
    fb = block.find('{', fm.end() - 1)
    fe = brace_match(block, fb)
    finner = block[fb + 1:fe - 1]

    pm = re.search(r'(?m)^[ \t]*position\s*=\s*\{', finner)
    if pm:
        pb = finner.find('{', pm.end() - 1)
        pe = brace_match(finner, pb)
        pinner = finner[pb + 1:pe - 1]
        px = re.compile(r'(?m)(^|[ \t{])x\s*=\s*([^\s\r\n}]+)')
        py = re.compile(r'(?m)(^|[ \t{])y\s*=\s*([^\s\r\n}]+)')
        mx = px.search(pinner)
        if mx:
            tok = _tech_coord_token(mx.group(2), x, macros)
            pinner2 = pinner[:mx.start()] + mx.group(1) + "x = " + tok + pinner[mx.end():]
        else:
            pinner2 = " x = %d" % x + pinner
        my = py.search(pinner2)
        if my:
            tok = _tech_coord_token(my.group(2), y, macros)
            pinner2 = pinner2[:my.start()] + my.group(1) + "y = " + tok + pinner2[my.end():]
        else:
            pinner2 = pinner2.rstrip() + " y = %d" % y
        finner2 = finner[:pb + 1] + pinner2 + finner[pe - 1:]
    else:
        nm = re.search(r'(?m)^([ \t]*)name\s*=\s*[^\s\r\n]+', finner)
        line = "position = { x = %d y = %d }" % (x, y)
        if nm:
            indent = nm.group(1) or "\t\t\t"
            finner2 = finner[:nm.end()] + "\n" + indent + line + finner[nm.end():]
        else:
            indent = "\t\t\t"
            finner2 = finner.rstrip() + "\n" + indent + line + "\n\t\t"

    block2 = block[:fb + 1] + finner2 + block[fe - 1:]
    new_text = text[:b + 1] + block2 + text[e - 1:]
    if new_text == text:
        return {"ok": True, "msg": "坐标没变"}
    snapshot(p)
    _write_bom_text(p, new_text, has_bom)
    if tid in TECHS:
        TECHS[tid]["fx"] = x
        TECHS[tid]["fy"] = y
    return {"ok": True, "msg": "%s → x=%d y=%d" % (tid, x, y), "x": x, "y": y}


def state_detail(sid):
    try:
        sid = int(sid)
    except Exception:
        return {"ok": False, "msg": "州 id 必须是数字"}
    s = STATES.get(sid)
    if not s:
        return {"ok": False, "msg": "没有这个州"}
    root = s.get("root") or ""
    owner = s.get("owner", "") or ""
    return {
        "ok": True, "id": sid,
        "name": LOC.get(s.get("name", ""), s.get("name", "")),
        "raw_name": s.get("name", ""),
        "file": s.get("file", ""), "root": root,
        "writable": bool(root) and not is_under_game(root),
        "owner": owner,
        "owner_name": LOC.get(owner, ""),
        "cores": s.get("cores", []),
        "core_names": {c: LOC.get(c, c) for c in s.get("cores", [])},
        "manpower": s.get("manpower", ""),
        "category": s.get("category", ""),
        "history_date": s.get("history_date", ""),
        "provinces": s.get("provinces", [])[:300],
        "province_count": s.get("province_count", 0),
        "buildings": s.get("buildings", {}),
        "province_buildings": s.get("province_buildings", {}),
        "victory_points": s.get("victory_points", [])[:20],
        "categories": list(STATE_CATEGORIES),
        "building_keys": list(STATE_BUILDINGS),
        "owners": sorted(COUNTRIES.keys()),
    }


def state_save(sid, fields):
    try:
        sid = int(sid)
    except Exception:
        return {"ok": False, "msg": "州 id 必须是数字"}
    s = STATES.get(sid)
    if not s:
        return {"ok": False, "msg": "没有这个州"}
    root = s.get("root") or ""
    rel = s.get("file") or ""
    if not rel:
        return {"ok": False, "msg": "这个州没有来源文件"}
    if is_under_game(root):
        return {"ok": False, "msg": "原版目录只读：请先复制到自己的模组再修改"}
    p = os.path.join(root, rel)
    if not os.path.exists(p):
        return {"ok": False, "msg": "州文件不存在：" + rel}

    owner = (fields.get("owner") or "").strip().upper()
    if owner and owner not in COUNTRIES:
        return {"ok": False, "msg": "owner 不是有效 tag：" + owner}
    cores = [x.strip().upper() for x in (fields.get("cores") or []) if x and x.strip()]
    bad = [c for c in cores if c not in COUNTRIES]
    if bad:
        return {"ok": False, "msg": "核心不是有效 tag：" + ", ".join(bad[:3])}
    cat = (fields.get("category") or "").strip()
    if cat and cat not in STATE_CATEGORIES:
        return {"ok": False, "msg": "state_category 只能是 " + " / ".join(STATE_CATEGORIES)}
    man = (fields.get("manpower") or "").strip()
    if man and not man.isdigit():
        return {"ok": False, "msg": "人力必须是整数"}
    blds = {}
    for k, v in (fields.get("buildings") or {}).items():
        if k not in STATE_BUILDINGS:
            continue
        try:
            iv = int(v)
        except Exception:
            continue
        if iv >= 0:
            blds[k] = iv

    text, has_bom = _read_bom_text(p)
    loc = _state_locate(text)
    if not loc:
        return {"ok": False, "msg": "文件里找不到 state = { } 块"}
    b, e = loc
    body = text[b + 1:e - 1]

    diff = []
    old_owner = s.get("owner", "")
    old_cores = list(s.get("cores", []))
    old_man = s.get("manpower", "")
    old_cat = s.get("category", "")
    old_blds = dict(s.get("buildings", {}))

    hist = _state_history_range(body)
    hb, he = hist if hist else (0, len(body))

    if owner and owner != old_owner:
        before = body
        if hist:
            body = _set_in_scope(body, "owner", owner, 1, hb, he)
            if body == before:
                body = _set_in_scope(body, "owner", owner, 2, hb, he)
            if body == before:
                body = _set_in_scope(body, "owner", owner, 1, hb, he, insert=True)
        else:
            body = _set_in_scope(body, "owner", owner, 0, 0, len(body), insert=True)
        if body != before:
            diff.append({"key": "owner", "label": "所属国家", "old": old_owner, "new": owner})

    if fields.get("cores") is not None and cores != old_cores:
        if hist:
            body = _drop_in_scope(body, "add_core_of", (1, 2), hb, he)
            if cores:
                # 删过行后原来的 hb/he 已失效，重新定位 history 块再插
                hist2 = _state_history_range(body)
                ins = "\n".join("\t\tadd_core_of = %s" % c for c in cores)
                if hist2:
                    hb2, he2 = hist2
                    pos = _insert_pos(body, hb2, he2)
                    body = body[:pos] + "\n" + ins + body[pos:]
                else:
                    body = body.rstrip() + "\n" + ins + "\n"
        else:
            body = _drop_in_scope(body, "add_core_of", (0,), 0, len(body))
            if cores:
                ins = "\n".join("\tadd_core_of = %s" % c for c in cores)
                body = body.rstrip() + "\n" + ins + "\n"
        diff.append({"key": "cores", "label": "核心", "old": ",".join(old_cores), "new": ",".join(cores)})

    if man and man != old_man:
        body = _set_in_scope(body, "manpower", man, 0, 0, len(body), insert=True)
        diff.append({"key": "manpower", "label": "人力", "old": old_man, "new": man})

    if cat and cat != old_cat:
        body = _set_in_scope(body, "state_category", cat, 0, 0, len(body), insert=True)
        diff.append({"key": "category", "label": "州类别", "old": old_cat, "new": cat})

    for k in sorted(blds):
        v = blds[k]
        if old_blds.get(k, None) == v:
            continue
        body = _set_building(body, k, v)
        diff.append({"key": "b_" + k, "label": "建筑 " + k,
                     "old": str(old_blds.get(k, "")), "new": str(v)})

    # v0.58 省份编辑
    pb = fields.get("province_buildings")
    if pb:
        old_pb = s.get("province_buildings", {}) or {}
        for pid, vals in pb.items():
            vals = vals or {}
            want = {}
            for k, v in vals.items():
                try:
                    iv = int(v)
                except Exception:
                    continue
                if iv >= 0:
                    want[k] = iv
            before = old_pb.get(str(pid), {}) or {}
            if want == before:
                continue
            body = _set_prov_building(body, str(pid), want)
            diff.append({"key": "pb_" + str(pid), "label": "省份 %s 建筑" % pid,
                         "old": ", ".join("%s=%d" % (k, v) for k, v in sorted(before.items())) or "无",
                         "new": ", ".join("%s=%d" % (k, v) for k, v in sorted(want.items())) or "无"})

    if fields.get("victory_points") is not None:
        want_vp = [[int(p), int(v)] for p, v in (fields.get("victory_points") or [])
                   if str(p).strip() and str(v).strip()]
        old_vp = [[int(p), int(v)] for p, v in s.get("victory_points", [])]
        if sorted(want_vp) != sorted(old_vp):
            body = _set_victory_points(body, want_vp)
            diff.append({"key": "vp", "label": "胜利点",
                         "old": ", ".join("%d:%d" % (p, v) for p, v in old_vp) or "无",
                         "new": ", ".join("%d:%d" % (p, v) for p, v in want_vp) or "无"})

    if not diff:
        return {"ok": True, "msg": "没有改动", "diff": []}
    new_text = text[:b + 1] + body + text[e - 1:]
    snapshot(p)
    _write_bom_text(p, new_text, has_bom)
    reload_data()
    link_countries()
    return {"ok": True, "msg": "已写入 " + rel, "diff": diff}


def link_countries():
    """把州、国策树挂到国家上（每轮 reload 后重建）"""
    for c in COUNTRIES.values():
        c["states_owned"] = []
        c["states_core"] = []
    for sid, s in STATES.items():
        o = s.get("owner") or ""
        if o in COUNTRIES:
            COUNTRIES[o]["states_owned"].append(sid)
        for t in s.get("cores", []):
            if t in COUNTRIES and sid not in COUNTRIES[t]["states_core"]:
                COUNTRIES[t]["states_core"].append(sid)
    for tid, t in TREES.items():
        tags = re.findall(r'tag\s*=\s*([A-Z0-9]{2,4})', t.get("country_raw") or "")
        t["country_tags"] = sorted(set(tags))
        for tag in t["country_tags"]:
            if tag in COUNTRIES and tid not in COUNTRIES[tag]["focus_trees"]:
                COUNTRIES[tag]["focus_trees"].append(tid)
    for c in COUNTRIES.values():
        c["states_owned"].sort()
        c["states_core"].sort()
        c["focus_trees"] = sorted(set(c["focus_trees"]))


def _country_issues(c):
    out = []

    def add(level, text, goto=None):
        out.append({"level": level, "text": text, "goto": goto or {}})

    tag = c["tag"]
    if c.get("orphan_history"):
        add("error", "有 history 文件，但 common/country_tags 里没有 %s" % tag)
    if not c.get("has_def"):
        add("warn", "找不到国家定义文件（%s）" % (c.get("def_file") or "未登记"))
    if not c.get("history_file"):
        add("warn", "没有 history/countries 文件，进游戏会是白板国家")
    if not c.get("capital"):
        add("warn", "没有设置首都 capital")
    if not c.get("focus_trees"):
        add("warn", "没有挂任何国策树（country = { tag } 或 load_focus_tree）")
    for t in c.get("focus_trees", []):
        if t not in TREES:
            add("error", "挂载的国策树 %s 不存在" % t, {"type": "country", "id": tag})
    bad_ideas = [i for i in c.get("ideas", []) if i not in IDEAS]
    if bad_ideas:
        add("warn", "add_ideas 引用了 %d 个不存在的国家精神（如 %s）" % (len(bad_ideas), bad_ideas[0]),
            {"type": "country", "id": tag})
    party = (c.get("ruling_party") or "").lower()
    has_base = bool(LOC.get(tag))
    has_party = bool(party and LOC.get("%s_%s" % (tag, party)))
    if not has_base and not has_party:
        add("warn", "国家名没有本地化：%s 与 %s_<政体> 都缺" % (tag, tag))
    elif party and not has_party:
        add("info", "有国家名但没有 %s_%s，政体一变就会掉回默认名" % (tag, party))
    if not LOC.get(tag + "_ADJ"):
        add("info", "缺少形容词键 %s_ADJ" % tag)
    if not c.get("states_owned"):
        add("warn", "没有任何州把它设为 owner")
    return out


def countries_payload():
    items = []
    for tag in sorted(COUNTRIES):
        c = COUNTRIES[tag]
        items.append({
            "tag": tag,
            "name": (LOC.get("%s_%s" % (tag, (c.get("ruling_party") or "").lower()))
                 or LOC.get(tag) or c.get("history_display") or tag),
            "history_file": c.get("history_file", ""),
            "trees": c.get("focus_trees", []),
            "owned": len(c.get("states_owned", [])),
            "cores": len(c.get("states_core", [])),
            "ideas": len(c.get("ideas", [])),
            "issues": len(_country_issues(c)),
            "orphan": bool(c.get("orphan_history")),
        })
    return {"count": len(items), "list": items}


def country_detail(tag):
    c = COUNTRIES.get(tag)
    if not c:
        return {"ok": False, "msg": "没有这个国家 tag"}
    states = []
    for sid in c.get("states_owned", []):
        s = STATES.get(sid) or {}
        states.append({"id": sid, "name": s.get("name", ""),
                       "loc": LOC.get(s.get("name", ""), ""),
                       "manpower": s.get("manpower", ""), "category": s.get("category", ""),
                       "core": sid in c.get("states_core", [])})
    cores_only = [sid for sid in c.get("states_core", []) if sid not in c.get("states_owned", [])]
    trees = []
    for tid in c.get("focus_trees", []):
        t = TREES.get(tid)
        trees.append({"id": tid, "exists": bool(t),
                      "focuses": len(t.get("focuses", [])) if t else 0,
                      "file": t.get("file", "") if t else "",
                      "default": (t or {}).get("default", ""),
                      "country_raw": (t or {}).get("country_raw", "")[:120]})
    return {
        "ok": True,
        "tag": tag,
        "name": (LOC.get("%s_%s" % (tag, (c.get("ruling_party") or "").lower()))
                 or LOC.get(tag) or c.get("history_display") or tag),
        "adj": LOC.get(tag + "_ADJ", ""),
        "source": c.get("source", ""),
        "color": c.get("color"),
        "graphical_culture": c.get("graphical_culture", ""),
        "def_file": c.get("def_file", ""),
        "def_found": bool(c.get("has_def")),
        "history_file": c.get("history_file", ""),
        "capital": c.get("capital", ""),
        "political_power": c.get("political_power", ""),
        "stability": c.get("stability", ""),
        "war_support": c.get("war_support", ""),
        "ruling_party": c.get("ruling_party", ""),
        "oob": c.get("oob", ""),
        "ideas": c.get("ideas", []),
        "techs": c.get("techs", []),
        "trees": trees,
        "states": states,
        "cores_only": cores_only,
        "issues": _country_issues(c),
    }


# ---------------- 国家历史写回（v0.56） ----------------
PARTIES = ("democratic", "fascism", "communism", "neutrality")

HIST_KEYS = {
    "capital": "capital",
    "political_power": "add_political_power",
    "stability": "add_stability",
    "war_support": "add_war_support",
}


def _hist_path(tag):
    c = COUNTRIES.get(tag)
    if not c:
        return None, None, None
    root = c.get("root") or ""
    rel = c.get("history_file") or ""
    p = os.path.join(root, rel) if rel else ""
    return c, root, p


def _read_bom_text(path):
    raw = io.open(path, "rb").read()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    return raw.decode("utf-8-sig", "replace"), has_bom


def _write_bom_text(path, text, has_bom):
    data = text.encode("utf-8")
    if has_bom:
        data = b"\xef\xbb\xbf" + data
    io.open(path, "wb").write(data)


def _first_in(text, pat):
    m = re.search(pat, text, re.M)
    return m.group(1).strip() if m else ""



def _hist_block_body(text, key):
    """取顶层 key = { ... } 的块内文本，没有返回空串"""
    m = _hist_find_top(text, re.compile(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(key)))
    if not m:
        return ""
    b = text.find('{', m.end() - 1)
    return text[b + 1:brace_match(text, b) - 1]


def _hist_popularities(text):
    out = {}
    for k, v, hb in top_items(_hist_block_body(text, "set_popularities")):
        if hb:
            continue
        try:
            out[k] = int(float(v.strip()))
        except Exception:
            pass
    return out


def _hist_party_of(text):
    """ruling_party 一般在 set_politics 块里，先看顶层再看块内"""
    m = _hist_find_top(text, re.compile(r'(?m)^[ 	]*ruling_party\s*=\s*(\w+)'))
    if m:
        return m.group(1).strip()
    sm = re.search(r'(?m)^[ 	]*set_politics\s*=\s*\{', text)
    if not sm:
        return ""
    b = text.find('{', sm.end() - 1)
    e = brace_match(text, b)
    mm = re.search(r'(?m)^[ 	]*ruling_party\s*=\s*(\w+)', text[b + 1:e - 1])
    return mm.group(1).strip() if mm else ""


# v0.59 初始外交
def _hist_opinions(text):
    """读取 add_opinion 块，返回 [[tag, value], ...]"""
    out = []
    for m in re.finditer(r'(?m)^[ \t]*add_opinion\s*=\s*\{', text):
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        t = _first(body, r'(?m)^[ \t]*target\s*=\s*([A-Z0-9]{2,4})')
        v = _first(body, r'(?m)^[ \t]*(?:value|opinion)\s*=\s*(-?\d+)')
        if t:
            out.append([t, int(v or 0)])
    return out


def _hist_set_opinions(text, pairs):
    """删掉所有 add_opinion 块再按 pairs 重建（顶层）"""
    for _ in range(40):
        m = _hist_find_top(text, re.compile(r'(?m)^[ \t]*add_opinion\s*=\s*\{'))
        if not m:
            break
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        line_start = text.rfind("\n", 0, m.start()) + 1
        text = text[:line_start] + text[e:]
    for tag, val in pairs:
        text = text.rstrip() + "\nadd_opinion = {\n\ttarget = %s\n\tvalue = %d\n}\n" % (tag, val)
    return text


# v0.64 开局装备变体
def _hist_variants(text):
    """读取 create_equipment_variant 块（只读展示用）"""
    out = []
    for m in re.finditer(r'(?m)^[ \t]*create_equipment_variant\s*=\s*\{', text):
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        nm = _first(body, r'(?m)^[ \t]*name\s*=\s*"?([^"\r\n]+)"?')
        ty = _first(body, r'(?m)^[ \t]*type\s*=\s*"?([^\s"\r\n]+)"?')
        ic = _first(body, r'(?m)^[ \t]*icon\s*=\s*"?([^\s"\r\n]+)"?')
        mods = 0
        mm = re.search(r'(?m)^[ \t]*modules\s*=\s*\{', body)
        if mm:
            mb = body.find('{', mm.end() - 1)
            me = brace_match(body, mb)
            if me > mb:
                mods = len([1 for k, v, hb in top_items(body[mb + 1:me - 1]) if not hb])
        out.append({"name": nm or "(未命名)", "type": ty, "icon": ic, "modules": mods})
    return out


def country_history_raw(tag):
    c, root, p = _hist_path(tag)
    if not c:
        return {"ok": False, "msg": "没有这个国家 tag"}
    writable = bool(root) and not is_under_game(root)
    if not p or not os.path.exists(p):
        return {"ok": True, "exists": False, "writable": writable, "file": c.get("history_file", ""),
                "root": root, "text": "", "fields": {}}
    text, _ = _read_bom_text(p)
    body = strip_comments(text)

    def top_val(pat):
        m = _hist_find_top(body, re.compile(pat))
        return m.group(1).strip() if m else ""

    fields = {
        "capital": top_val(r'(?m)^[ 	]*capital\s*=\s*(\d+)'),
        "ruling_party": _hist_party_of(body),
        "political_power": top_val(r'(?m)^[ 	]*add_political_power\s*=\s*(-?[\d.]+)'),
        "stability": top_val(r'(?m)^[ 	]*add_stability\s*=\s*(-?[\d.]+)'),
        "war_support": top_val(r'(?m)^[ 	]*add_war_support\s*=\s*(-?[\d.]+)'),
        "ideas": (COUNTRIES.get(tag) or {}).get("ideas", []),
        "focus_tree": ((COUNTRIES.get(tag) or {}).get("focus_trees") or [""])[0],
        "oob": top_val(r'(?m)^[ \t]*oob\s*=\s*"([^"]+)"'),
        "techs": [k for k, v, hb in top_items(_hist_block_body(body, "set_technology")) if not hb],
        "popularities": _hist_popularities(body),
        "opinions": _hist_opinions(body),
        "variants": _hist_variants(body),
    }
    return {"ok": True, "exists": True, "writable": writable, "file": c.get("history_file", ""),
            "root": root, "text": text[:60000], "fields": fields}


def _hist_depths(text):
    """每个字符位置的花括号深度（字符串内的括号不计）"""
    depth = 0
    out = []
    instr = False
    for ch in text:
        if ch == '"':
            instr = not instr
            out.append(depth)
            continue
        if instr:
            out.append(depth)
            continue
        if ch == '{':
            out.append(depth)
            depth += 1
        elif ch == '}':
            depth = max(0, depth - 1)
            out.append(depth)
        else:
            out.append(depth)
    return out


def _hist_find_top(text, pat):
    """只返回深度 0 的匹配（块内同名键不算）"""
    d = _hist_depths(text)
    for m in pat.finditer(text):
        if m.start() < len(d) and d[m.start()] == 0:
            return m
    return None


def _hist_set_scalar(text, key, value, at_end=False):
    """只在顶层替换（条件块里的同名键不动）；没有就插到开头或末尾"""
    pat = re.compile(r'(?m)^([ \t]*)%s\s*=\s*[^\s#\r\n]+' % re.escape(key))
    m = _hist_find_top(text, pat)
    if m:
        repl = (m.group(1) or "") + "%s = %s" % (key, value)
        return text[:m.start()] + repl + text[m.end():]
    line = "%s = %s\n" % (key, value)
    return (text.rstrip() + "\n" + line) if at_end else (line + text.lstrip("\r\n"))


def _hist_strip_key(text, key):
    """只删顶层的 key 块与单值行（条件分支里的同名键保留）"""
    block_pat = re.compile(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(key))
    for _ in range(8):
        m = _hist_find_top(text, block_pat)
        if not m:
            break
        b = text.find('{', m.end() - 1)
        end = brace_match(text, b)
        line_start = text.rfind('\n', 0, m.start()) + 1
        text = text[:line_start] + text[end:]
    single = re.compile(r'(?m)^[ \t]*%s\s*=\s*[^{\s#][^\r\n]*\r?\n?' % re.escape(key))
    for _ in range(8):
        m = _hist_find_top(text, single)
        if not m:
            break
        text = text[:m.start()] + text[m.end():]
    return text


def _hist_put_block(text, key, inner_lines):
    """整体替换顶层的 key 块（先删旧块/旧单值行，再追加新块）"""
    text = _hist_strip_key(text, key)
    if not inner_lines:
        return text
    body = "\n".join("\t" + x for x in inner_lines)
    return text.rstrip() + "\n" + "%s = {\n%s\n}\n" % (key, body)


def _hist_set_party(text, party):
    m = re.search(r'(?m)^([ 	]{0,4})set_politics\s*=\s*\{', text)
    if not m:
        return "set_politics = {\n\truling_party = %s\n}\n" % party + text.lstrip("\r\n")
    b = text.find('{', m.end() - 1)
    e = brace_match(text, b)
    body = text[b + 1:e - 1]
    pat = re.compile(r'(?m)^(\s*)ruling_party\s*=\s*[^\s#\r\n]+')
    if pat.search(body):
        body2 = pat.sub(lambda mm: (mm.group(1) or "\t") + "ruling_party = " + party, body, count=1)
    else:
        body2 = body.rstrip() + "\n\truling_party = %s\n" % party
    return text[:b + 1] + body2 + text[e - 1:]


def country_history_save(tag, fields):
    """只改 fields 里给出的键，其余原文一律保留；写前 snapshot()"""
    c, root, p = _hist_path(tag)
    if not c:
        return {"ok": False, "msg": "没有这个国家 tag"}
    if not root:
        return {"ok": False, "msg": "这个国家没有来源目录"}
    if is_under_game(root):
        return {"ok": False, "msg": "原版目录只读：请先复制到自己的模组再修改"}

    warnings = []
    party = (fields.get("ruling_party") or "").strip().lower()
    if party and party not in PARTIES:
        return {"ok": False, "msg": "执政党只能是 " + " / ".join(PARTIES)}
    capital = (fields.get("capital") or "").strip()
    if capital and not capital.isdigit():
        return {"ok": False, "msg": "首都必须是州数字 id"}

    ideas = [x.strip() for x in (fields.get("ideas") or []) if x and x.strip()]
    for i in ideas:
        if i not in IDEAS:
            warnings.append("国家精神 %s 目前不存在（先写进去也可以，记得后面补定义）" % i)
    tree = (fields.get("focus_tree") or "").strip()
    if tree and tree not in TREES:
        warnings.append("国策树 %s 目前不存在" % tree)

    diff = []
    exists = bool(p) and os.path.exists(p)
    if exists:
        text, has_bom = _read_bom_text(p)
        before = strip_comments(text)
        def top_old(pat):
            m = _hist_find_top(before, re.compile(pat))
            return m.group(1).strip() if m else ""

        old = {
            "capital": top_old(r'(?m)^[ 	]*capital\s*=\s*(\d+)'),
            "ruling_party": _hist_party_of(before),
            "political_power": top_old(r'(?m)^[ 	]*add_political_power\s*=\s*(-?[\d.]+)'),
            "stability": top_old(r'(?m)^[ 	]*add_stability\s*=\s*(-?[\d.]+)'),
            "war_support": top_old(r'(?m)^[ 	]*add_war_support\s*=\s*(-?[\d.]+)'),
            "ideas": ",".join(c.get("ideas", [])),
            "focus_tree": (c.get("focus_trees") or [""])[0],
            "techs": ",".join(c.get("techs", [])),
            "oob": c.get("oob", ""),
            "popularities": ",".join("%s=%d" % (k, v) for k, v in
                                     sorted(_hist_popularities(before).items())),
            "opinions": ",".join("%s:%d" % (t4, v4) for t4, v4 in _hist_opinions(before)),
        }
        new = dict(old)
        for key, mlkey in HIST_KEYS.items():
            val = (fields.get(key) or "").strip()
            if not val:
                continue
            text = _hist_set_scalar(text, mlkey, val, at_end=(key != "capital"))
            new[key] = val
        if party:
            text = _hist_set_party(text, party)
            new["ruling_party"] = party
        if fields.get("ideas") is not None:
            text = _hist_put_block(text, "add_ideas", ideas)
            new["ideas"] = ",".join(ideas)
        if fields.get("focus_tree") is not None:
            text = _hist_put_block(text, "load_focus_tree", ["tree = " + tree] if tree else [])
            new["focus_tree"] = tree
        # v0.58 历史编辑器补全
        if fields.get("techs") is not None:
            techs = [x.strip() for x in fields.get("techs") or [] if x and x.strip()]
            text = _hist_put_block(text, "set_technology", ["%s = 1" % t for t in techs])
            new["techs"] = ",".join(techs)
        if fields.get("oob") is not None:
            oob = (fields.get("oob") or "").strip()
            if oob:
                text = _hist_set_scalar(text, "oob", '"%s"' % oob)
            new["oob"] = oob
        if fields.get("opinions") is not None:
            pairs = []
            for pair in fields.get("opinions") or []:
                try:
                    tag2, val2 = pair[0], int(pair[1])
                except Exception:
                    continue
                if tag2 in COUNTRIES:
                    pairs.append((tag2, val2))
            old_pairs = _hist_opinions(before)
            if pairs != old_pairs:
                text = _hist_set_opinions(text, pairs)
                new["opinions"] = ",".join("%s:%d" % (t3, v3) for t3, v3 in pairs)
        if fields.get("popularities") is not None:
            pops = {}
            for k, v in (fields.get("popularities") or {}).items():
                if k in PARTIES and str(v).strip():
                    try:
                        pops[k] = int(float(v))
                    except Exception:
                        pass
            if pops:
                text = _hist_put_block(text, "set_popularities",
                                       ["%s = %d" % (k, pops[k]) for k in PARTIES if k in pops])
                new["popularities"] = ",".join("%s=%d" % (k, pops[k]) for k in PARTIES if k in pops)
        shown = {"capital": "首都", "ruling_party": "执政党", "political_power": "政治点",
                 "stability": "稳定度修正", "war_support": "战争支持修正", "ideas": "开局精神",
                 "focus_tree": "国策树", "techs": "开局科技", "oob": "部队编成 oob",
                 "popularities": "政党支持度", "opinions": "初始外交"}
        for k, label in shown.items():
            if old.get(k, "") != new.get(k, ""):
                diff.append({"key": k, "label": label, "old": old.get(k, ""), "new": new.get(k, "")})
        if not diff:
            return {"ok": True, "msg": "没有改动", "diff": [], "warnings": warnings}
        snapshot(p)
        _write_bom_text(p, text, has_bom)
    else:
        name = c.get("history_display") or tag
        rel = os.path.join("history", "countries", "%s - %s.txt" % (tag, name))
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lines = []
        if capital:
            lines.append("capital = " + capital)
        if party:
            lines.append("set_politics = {\n\truling_party = %s\n}" % party)
        for key, mlkey in HIST_KEYS.items():
            if key == "capital":
                continue
            val = (fields.get(key) or "").strip()
            if val:
                lines.append("%s = %s" % (mlkey, val))
        if ideas:
            lines.append("add_ideas = {\n" + "\n".join("\t" + x for x in ideas) + "\n}")
        if tree:
            lines.append("load_focus_tree = {\n\ttree = %s\n}" % tree)
        if not lines:
            return {"ok": False, "msg": "没有任何要写入的字段"}
        text = "\n".join(lines) + "\n"
        io.open(path, "w", encoding="utf-8", newline="\r\n").write(text)
        diff = [{"key": "create", "label": "新建文件", "old": "", "new": rel}]

    reload_data()
    link_countries()
    return {"ok": True, "msg": "已写入 " + (c.get("history_file") or tag), "diff": diff, "warnings": warnings}


# v0.59 国策引用体检
def _focus_refs():
    """从 national_focus 原文里收集 add_ideas / has_idea / country_event 引用"""
    ideas, events = [], []
    for root in ROOTS:
        d = os.path.join(root, "common", "national_focus")
        if not os.path.isdir(d):
            continue
        name = os.path.basename(root.rstrip("\\/")) or root
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            rel = os.path.join("common", "national_focus", fn)
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'(?m)^[ \t]*(?:focus|shared_focus)\s*=\s*\{', text):
                b = text.find('{', m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                fid = _first(body, r'(?m)^[ \t]*id\s*=\s*"?([A-Za-z0-9_.\-]+)')
                if not fid:
                    continue
                tree = ""
                for tid, t in TREES.items():
                    if t.get("file") == rel and t.get("source") == name:
                        tree = tid
                        break
                for im in re.finditer(r'(?m)^[ \t]*add_ideas\s*=\s*([A-Za-z0-9_]+)', body):
                    ideas.append({"focus": fid, "id": im.group(1), "where": "add_ideas",
                                  "file": rel, "tree": tree})
                for im in re.finditer(r'add_ideas\s*=\s*\{([^}]*)\}', body):
                    for iid in re.findall(r'[A-Za-z0-9_]+', im.group(1)):
                        ideas.append({"focus": fid, "id": iid, "where": "add_ideas",
                                      "file": rel, "tree": tree})
                for im in re.finditer(r'(?m)^[ \t]*has_idea\s*=\s*([A-Za-z0-9_]+)', body):
                    ideas.append({"focus": fid, "id": im.group(1), "where": "has_idea",
                                  "file": rel, "tree": tree})
                for im in re.finditer(r'(?:country_event|news_event|state_event)\s*=\s*\{\s*id\s*=\s*"?([A-Za-z0-9_.\-]+)', body):
                    events.append({"focus": fid, "id": im.group(1), "file": rel, "tree": tree})
    return {"ideas": ideas, "events": events}


def lint_project(limit=1500):
    """跨系统引用检查：树↔国家、历史↔树、州↔国家、事件↔事件、本地化"""
    items = []

    def add(level, kind, title, detail="", goto=None):
        if len(items) < limit:
            items.append({"level": level, "kind": kind, "title": title,
                          "detail": detail, "goto": goto or {}})

    for tid, t in TREES.items():
        raw = t.get("country_raw") or ""
        tags = re.findall(r'tag\s*=\s*([A-Z0-9]{2,4})', raw)
        if raw.strip() and not tags:
            add("info", "tree", "国策树 %s 的 country 块里没有 tag（按条件或默认挂载）" % tid, raw[:120],
                {"type": "tree", "id": tid})
        for tag in sorted(set(tags)):
            if tag not in COUNTRIES:
                add("error", "tree", "国策树 %s 挂了不存在的国家 %s" % (tid, tag), "",
                    {"type": "tree", "id": tid})

    for tag, c in COUNTRIES.items():
        if c.get("orphan_history"):
            add("error", "country", "%s 有 history 文件但没有 country_tags 登记" % tag,
                c.get("history_file", ""), {"type": "country", "id": tag})
        for t in c.get("focus_trees", []):
            if t not in TREES:
                add("error", "country", "%s 的 load_focus_tree 引用了不存在的树 %s" % (tag, t),
                    c.get("history_file", ""), {"type": "country", "id": tag})
        for i in c.get("ideas", []):
            if i not in IDEAS:
                add("warn", "idea", "%s 的 add_ideas 引用了不存在的国家精神 %s" % (tag, i),
                    c.get("history_file", ""), {"type": "country", "id": tag})

    for sid, s in STATES.items():
        o = s.get("owner")
        if o and o not in COUNTRIES:
            add("error", "state", "州 %s 的 owner = %s 不是有效 tag" % (sid, o), s.get("file", ""),
                {"type": "state", "id": str(sid)})
        for t in s.get("cores", []):
            if t not in COUNTRIES:
                add("error", "state", "州 %s 的 add_core_of = %s 不是有效 tag" % (sid, t), s.get("file", ""),
                    {"type": "state", "id": str(sid)})
        if not s.get("owner"):
            add("info", "state", "州 %s 没有设置 owner" % sid, s.get("file", ""),
                {"type": "state", "id": str(sid)})

    for eid, ev in EVENTS.items():
        raw = ev.get("raw", "")
        for m in re.finditer(r'(?:country_event|news_event|state_event)\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.\-]+)', raw):
            ref = m.group(1)
            if ref not in EVENTS:
                add("warn", "event", "事件 %s 触发了不存在的事件 %s" % (eid, ref), ev.get("file", ""),
                    {"type": "event", "id": eid})

    # v0.59：国策里的引用
    try:
        refs = _focus_refs()
    except Exception as e:
        refs = {"ideas": [], "events": []}
        print("focus refs fail:", e)
    for r in refs["ideas"]:
        if r["id"] not in IDEAS:
            add("warn", "focus", "国策 %s 的 %s 引用了不存在的国家精神 %s" % (r["focus"], r["where"], r["id"]),
                r["file"], {"type": "tree", "id": r["tree"]})
    for r in refs["events"]:
        if r["id"] not in EVENTS:
            add("warn", "focus", "国策 %s 触发了不存在的事件 %s" % (r["focus"], r["id"]),
                r["file"], {"type": "tree", "id": r["tree"]})

    for it in missing_loc()[:limit]:
        add("warn", "loc", "缺本地化：%s" % it.get("key", ""), it.get("file", ""),
            {"type": "loc", "id": it.get("key", "")})

    order = {"error": 0, "warn": 1, "info": 2}
    items.sort(key=lambda x: (order.get(x["level"], 3), x["kind"]))
    stats = {"error": 0, "warn": 0, "info": 0}
    for it in items:
        stats[it["level"]] = stats.get(it["level"], 0) + 1
    return {"items": items, "stats": stats, "truncated": len(items) >= limit,
            "scope": {"trees": len(TREES), "countries": len(COUNTRIES), "states": len(STATES),
                      "ideas": len(IDEAS), "events": len(EVENTS), "techs": len(TECHS)}}

def load_events(root):
    name = os.path.basename(root.rstrip("\\/")) or root
    d = os.path.join(root, "events")
    if not os.path.isdir(d):
        return 0
    n = 0
    for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
        rel = os.path.join("events", fn)
        text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
        nsm = re.search(r'add_namespace\s*=\s*(\w+)', text)
        ns = nsm.group(1) if nsm else ""
        for k, v, b in top_items(text):
            if not b or not k.endswith("_event"):
                continue
            m = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_.\-]+)"?', v)
            if not m:
                continue
            eid = m.group(1)
            EVENTS[eid] = {"id": eid, "file": rel, "source": name, "type": k, "ns": ns,
                           "title": LOC.get(eid + ".t", ""),
                           "raw": "%s = {\n%s\n}" % (k, v.strip())}
            n += 1
    return n

def item_raw(kind, iid):
    m = {"idea": IDEAS, "equip": EQUIPMENTS, "tech": TECHS, "event": EVENTS}.get(kind) or {}
    return {"raw": m.get(iid, {}).get("raw", "")}

def all_goal_icons():
    out = []
    for g, (tex, frames) in SPRITE_MAP.items():
        tl = tex.lower().replace("\\", "/")
        if "/interface/goals/" in tl:
            out.append(g)
    return sorted(out)

def icon_png(gfx):
    ent = SPRITE_MAP.get(gfx)
    if not ent:
        return None
    tex, frames = ent
    rel = tex.replace("/", os.sep)
    cands = [os.path.join(r, rel) for r in ROOTS] + [os.path.join(GAME, rel)]
    dlc = os.path.join(GAME, "dlc")
    if os.path.isdir(dlc):
        for x in os.listdir(dlc):
            cands.append(os.path.join(dlc, x, rel))
    src = next((c for c in cands if os.path.exists(c)), None)
    if not src:
        return None
    png_name = re.sub(r'[^A-Za-z0-9_.-]', '_', gfx) + "_" + \
        hashlib.md5((os.path.abspath(src) + str(os.path.getmtime(src))).encode("utf-8")).hexdigest()[:8] + ".png"
    png = os.path.join(ICON_DIR, png_name)
    try:
        if not os.path.exists(png):
            from PIL import Image
            im = Image.open(src)
            if frames > 1:
                w, h = im.size
                im = im.crop((0, 0, w // frames, h))
            im = im.convert("RGBA")
            im.thumbnail((64, 64))
            im.save(png)
        return png
    except Exception:
        return None

def expand_shared_trees():
    byid = {}
    for n in SHARED_FOCUSES:
        byid[n["id"]] = n
    for t in TREES.values():
        ids = {f["id"] for f in t.get("focuses", [])}
        for sid in t.get("shared", []):
            if sid in byid and sid not in ids:
                node = dict(byid[sid])
                node["shared"] = True
                t["focuses"].append(node)
                ids.add(sid)

def find_usages(iid):
    out = []
    pat = re.compile(r'(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])' % re.escape(iid or ""))
    for tid in TREE_ORDER:
        t = TREES.get(tid)
        if not t:
            continue
        for f in t.get("focuses", []):
            txt = (f.get("effect") or "") + "\n" + (f.get("select_effect") or "")
            if pat.search(txt):
                out.append({"type": "国策", "id": f["id"], "where": tid, "file": t["file"]})
    for eid, e in EVENTS.items():
        if pat.search(e.get("raw", "")):
            out.append({"type": "事件", "id": eid, "where": eid, "file": e.get("file", "")})
    for tid, t in TECHS.items():
        if iid in (t.get("prereq") or []) or iid in (t.get("leads") or []):
            out.append({"type": "科技", "id": tid, "where": t.get("path", ""), "file": t.get("file", "")})
    return out[:500]

def load_orgs(root):
    bases = [root] if os.path.abspath(root) == os.path.abspath(GAME) else [root, GAME]
    n = 0
    for base in bases:
        d = os.path.join(base, "common", "military_industrial_organization", "organizations")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
            for k, v, b in top_items(text):
                if b and re.match(r'^[A-Za-z0-9_]+$', k):
                    ORGS[k] = LOC.get(k, k)
                    n += 1
    return n

def load_modules(root):
    bases = [root] if os.path.abspath(root) == os.path.abspath(GAME) else [root, GAME]
    n = 0
    for base_root in bases:
        d = os.path.join(base_root, "common", "units", "equipment", "modules")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
            for s, e, body in find_blocks(text, "equipment_modules"):
                for k, v, b in top_items(body):
                    if not b or k in ("limit", "template"):
                        continue
                    if "category" not in v:
                        continue
                    cm = re.search(r'(?m)^\s*category\s*=\s*"?([A-Za-z0-9_]+)"?', v)
                    if not cm:
                        continue
                    gm = re.search(r'(?m)^\s*gfx\s*=\s*"?([A-Za-z0-9_]+)"?', v)
                    stats = {}
                    for am in re.finditer(r'add_stats\s*=\s*\{', v):
                        ab = v.find('{', am.start())
                        ae = brace_match(v, ab)
                        inner = v[ab + 1:ae - 1]
                        for sm in re.finditer(r'(?m)^\s*([A-Za-z0-9_]+)\s*=\s*(-?[0-9.]+)', inner):
                            try:
                                stats[sm.group(1)] = float(sm.group(2))
                            except Exception:
                                pass
                    MODULES[k] = {"id": k, "category": cm.group(1),
                                  "gfx": gm.group(1) if gm else "",
                                  "stats": stats,
                                  "file": os.path.join("common", "units", "equipment", "modules", fn)}
                    n += 1
    return n

def _eq_view(e):
    d = {k: v for k, v in e.items() if k != "raw"}
    d["slots"] = [dict(s, name=(LOC.get("EQ_MOD_SLOT_" + s["slot"] + "_TITLE")
                                 or LOC.get(s["slot"], s["slot"]))) for s in e.get("slots", [])]
    return d

def data_payload():
    expand_shared_trees()
    trees = []
    for tid in TREE_ORDER:
        t = TREES[tid]
        resolve_positions(t)
        for f in t["focuses"]:
            f["name"] = LOC.get(f["id"], f["id"])
            f.pop("desc", None)
            f.pop("effect", None)
            f.pop("select_effect", None)
            f.pop("iconPng", None)
        trees.append({"id": tid, "file": t["file"], "source": t["source"],
                      "default": t.get("default", ""), "country_raw": t.get("country_raw", ""),
                      "focuses": t["focuses"], "shared": t["shared"],
                      "analysis": analyze(t)})
    if SHARED_FOCUSES:
        trees.append({"id": "shared_focuses", "file": "", "source": "shared",
                      "default": "", "country_raw": "",
                      "focuses": SHARED_FOCUSES, "shared": [],
                      "analysis": analyze({"focuses": SHARED_FOCUSES})})
    return {"trees": trees,
            "ideas": [{k: v for k, v in IDEAS[k].items() if k != "raw"} for k in sorted(IDEAS)],
            "equipment": [_eq_view(EQUIPMENTS[k]) for k in sorted(EQUIPMENTS)],
            "techs": [{k: v for k, v in TECHS[k].items() if k != "raw"} for k in sorted(TECHS)],
            "events": [{k: v for k, v in EVENTS[k].items() if k != "raw"} for k in sorted(EVENTS)],
            "modules": [dict(m, name=LOC.get(m["id"], m["id"])) for m in (MODULES[k] for k in sorted(MODULES))],
            "orgs": [{"id": k, "name": LOC.get(k, k)} for k in sorted(ORGS)],
            "mascots": MASCOTS,
            "mod_home": mod_home(),
            "roots": [{"name": os.path.basename(r.rstrip("\\/")) or r, "path": r,
                       "readonly": is_under_game(r)} for r in ROOTS]}

# ---------------- 写回 ----------------
def backup(path):
    try:
        if not os.path.exists(path + ".bak"):
            shutil.copyfile(path, path + ".bak")
    except Exception:
        pass

def set_scalar(block, key, value):
    pat = re.compile(r'(?m)^(\s*)%s\s*=\s*[^\s#]+' % key)
    if pat.search(block):
        return pat.sub(lambda m: "%s%s = %s" % (m.group(1), key, value), block, count=1)
    # 插入到 id 行后
    m = re.search(r'(?m)^(\s*)id\s*=\s*[^\n]+', block)
    if not m:
        return block
    indent = m.group(1)
    return block[:m.end()] + "\n" + indent + "%s = %s" % (key, value) + block[m.end():]

def remove_block(block, key):
    # 删除 block 顶层 key = { ... }（不处理嵌套同名，MVP 足够）
    out = []
    i = 0
    while True:
        m = re.search(r'(?m)^\s*%s\s*=\s*\{' % key, block[i:])
        if not m:
            out.append(block[i:])
            break
        s = i + m.start()
        out.append(block[i:s])
        b = block.find('{', s)
        e = brace_match(block, b)
        i = e
    return "".join(out)

def build_blocks(key, groups):
    lines = []
    for grp in groups or []:
        if isinstance(grp, str):
            grp = [grp]
        grp = [str(x) for x in grp if x]
        if not grp:
            continue
        lines.append("\t\t%s = {" % key)
        for g in grp:
            lines.append('\t\t\tfocus = "%s"' % g)
        lines.append("\t\t}")
    return "\n".join(lines)

def braces_balanced(text):
    depth = 0
    instr = False
    for c in text or "":
        if c == '"':
            instr = not instr
        elif not instr:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth < 0:
                    return False
    return depth == 0 and not instr

def set_raw_block(block, key, content):
    """替换/删除 focus 内的原始脚本块（如 completion_reward）"""
    content = (content or "").strip("\n")
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % key, block)
    if not content.strip():
        if m:
            start = m.start()
            b = block.find('{', m.start())
            e = brace_match(block, b)
            return block[:start] + block[e + 1:]
        return block
    lines = []
    for ln in content.splitlines():
        lines.append("\t\t\t" + ln.rstrip() if ln.strip() else "")
    newb = "\t\t%s = {\n%s\n\t\t}" % (key, "\n".join(lines))
    if m:
        start = m.start()
        b = block.find('{', start)
        e = brace_match(block, b)
        return block[:start] + newb + block[e + 1:]
    return block.rstrip() + "\n\t" + newb + "\n"

def save_focus(root, rel, fid, fields):
    path = os.path.join(root, rel)
    raw = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    text = raw
    # 找 focus 块
    spans = []
    for m in re.finditer(r'(?m)^\s*(?:focus|shared_focus)\s*=\s*\{', text):
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        spans.append((m.start(), b, e))
    target = None
    for s, b, e in spans:
        body = text[b + 1:e - 1]
        if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(fid), body):
            target = (s, b, e)
            break
    if not target:
        return False, "未找到焦点 " + fid
    s, b, e = target
    block = text[b + 1:e - 1]
    if "x" in fields and fields["x"] is not None:
        block = set_scalar(block, "x", fields["x"])
    if "y" in fields and fields["y"] is not None:
        block = set_scalar(block, "y", fields["y"])
    if "cost" in fields and fields["cost"] not in (None, ""):
        block = set_scalar(block, "cost", fields["cost"])
    if "icon" in fields and fields["icon"]:
        block = set_scalar(block, "icon", fields["icon"])
    if "prereq" in fields and fields["prereq"] is not None:
        block = remove_block(block, "prerequisite")
        if fields["prereq"]:
            block = block.rstrip() + "\n" + build_blocks("prerequisite", fields["prereq"]) + "\n\t"
    if "mutex" in fields and fields["mutex"] is not None:
        block = remove_block(block, "mutually_exclusive")
        mx = []
        for x in fields["mutex"] or []:
            if isinstance(x, (list, tuple)):
                mx += [str(y) for y in x if y]
            elif x:
                mx.append(str(x))
        if mx:
            block = block.rstrip() + "\n\t\tmutually_exclusive = {\n" + "\n".join(
                '\t\t\tfocus = "%s"' % x for x in mx) + "\n\t\t}\n\t"
    for key, fk in (("completion_reward", "effect"), ("select_effect", "select_effect")):
        if fk in fields and fields[fk] is not None:
            eff = fields[fk] if isinstance(fields[fk], str) else str(fields[fk])
            if not braces_balanced(eff):
                return False, "效果花括号不匹配，未保存"
            block = set_raw_block(block, key, eff)
    newtext = text[:b + 1] + block + text[e - 1:]
    # 校验：重新解析该 focus
    try:
        spans2 = []
        for m in re.finditer(r'(?m)^\s*focus\s*=\s*\{', newtext):
            b2 = newtext.find('{', m.end() - 1)
            e2 = brace_match(newtext, b2)
            spans2.append((b2, e2))
        ok = False
        for b2, e2 in spans2:
            body = newtext[b2 + 1:e2 - 1]
            if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(fid), body):
                ok = True
                break
        if not ok:
            return False, "写回后校验失败"
    except Exception as ex:
        return False, "写回后解析异常: %s" % ex
    backup(path)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(newtext)
    CHANGED[path] = rel
    reload_data()
    return True, "已保存"

def export_zip():
    if not CHANGED:
        return None, "没有改动"
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(WORK, "focus_editor_exports", "mvlv_focus_patch_%s.zip" % ts)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path, rel in CHANGED.items():
            z.write(path, rel)
        z.writestr("README_覆盖说明.txt",
                   "把压缩包内文件按相同相对路径覆盖到对应 mod 根目录即可。\n"
                   "本包只包含本次编辑的国策文件。\n"
                   "覆盖前建议备份原文件。\n")
    return out, "已导出"

# ---------------- 本地化 / 树级操作 ----------------
LOC_EDITS = {}   # lang -> {key: text}

def _write_loc(root, lang):
    d = os.path.join(root, "localisation", lang, "replace")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "zz_focus_editor_l_%s.yml" % lang)
    header = {"simp_chinese": "l_simp_chinese:", "english": "l_english:",
              "japanese": "l_japanese:"}.get(lang, "l_" + lang + ":")
    lines = [header]
    for k, v in sorted(LOC_EDITS.get(lang, {}).items()):
        v = (v or "").replace("\\", "\\\\").replace('"', '\\"')
        lines.append(' %s:0 "%s"' % (k, v))
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="\n").write("\ufeff" + "\n".join(lines) + "\n")
    return path

def save_loc(root, entries):
    for lang, kv in entries.items():
        LOC_EDITS.setdefault(lang, {}).update(kv)
        _write_loc(root, lang)
        LOC.update(kv)
    return True, "本地化已保存"

def add_tree(root, tree_id):
    d = os.path.join(root, "common", "national_focus")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "zz_focus_editor_trees.txt")
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else ""
    if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(tree_id), text):
        return False, "树已存在: " + tree_id
    block = "\nfocus_tree = {\n\tid = %s\n\n\tcountry = {\n\t\tfactor = 0\n\t}\n}\n" % tree_id
    backup(path)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text + block)
    CHANGED[path] = os.path.join("common", "national_focus", "zz_focus_editor_trees.txt")
    reload_data()
    return True, "已新建树 " + tree_id

def delete_tree(root, file, tree_id):
    path = os.path.join(root, file)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    for m in re.finditer(r'(?m)^\s*focus_tree\s*=\s*\{', text):
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        body = text[b + 1:e - 1]
        mid = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_]+)"?', body)
        if mid and mid.group(1) == tree_id:
            newtext = text[:m.start()] + text[e:]
            backup(path)
            snapshot(path)
            io.open(path, "w", encoding="utf-8", newline="").write(newtext)
            CHANGED[path] = file
            reload_data()
            return True, "已删除树 " + tree_id
    return False, "未找到树 " + tree_id

# ---------------- 图标 ----------------
def parse_gfx_file(path):
    s = io.open(path, encoding="utf-8-sig", errors="replace").read()
    out = {}
    for m in re.finditer(r'spriteType\s*=\s*\{', s, re.I):
        b = m.end() - 1
        e = brace_match(s, b)
        body = s[b + 1:e - 1]
        name = re.search(r'name\s*=\s*"?([^"\s]+)"?', body, re.I)
        tex = re.search(r'texturefile\s*=\s*"?([^"\s]+)"?', body, re.I)
        frames = re.search(r'noOfFrames\s*=\s*(\d+)', body, re.I)
        if name and tex:
            out[name.group(1)] = (tex.group(1), int(frames.group(1)) if frames else 1)
    return out

def build_icons(roots, game):
    global ICONS, SPRITE_MAP, TECH_ICONS
    sprite_map = {}
    dirs = []
    for r in roots:
        d = os.path.join(r, "interface")
        if os.path.isdir(d):
            dirs.append(d)
    base = os.path.join(game, "interface")
    if os.path.isdir(base):
        dirs.append(base)
    dlc = os.path.join(game, "dlc")
    if os.path.isdir(dlc):
        for x in os.listdir(dlc):
            p = os.path.join(dlc, x, "interface")
            if os.path.isdir(p):
                dirs.append(p)
    for d in dirs:
        for fn in os.listdir(d):
            if fn.endswith(".gfx"):
                try:
                    sprite_map.update(parse_gfx_file(os.path.join(d, fn)))
                except Exception:
                    pass
    from PIL import Image
    SPRITE_MAP = sprite_map
    used = set()
    for tid in TREE_ORDER:
        for f in TREES[tid]["focuses"]:
            if f.get("icon"):
                used.add(f["icon"])
    langs = os.listdir(dlc) if os.path.isdir(dlc) else []
    for gfx in used:
        if gfx in sprite_map:
            ICONS[gfx] = "/api/icon?gfx=" + gfx
    print("icons:", len(ICONS), "/", len(used))
    global EQUIP_ICONS
    EQUIP_ICONS = {}
    for gfx, (tex, frames) in sprite_map.items():
        tl = tex.lower().replace("\\", "/")
        if "/interface/equipment/" in tl:
            EQUIP_ICONS[gfx] = "/api/icon?gfx=" + gfx
    print("equip icons:", len(EQUIP_ICONS))
    TECH_ICONS = {}
    for gfx, (tex, frames) in sprite_map.items():
        tl = tex.lower().replace("\\", "/")
        gl = gfx.lower()
        if ("/interface/technologies/" in tl or "/interface/tech/" in tl
                or gl.startswith("gfx_tech") or gl.endswith("_tab")
                or "_technology_" in gl):
            TECH_ICONS[gfx] = "/api/icon?gfx=" + gfx
    print("tech icons:", len(TECH_ICONS))

# ---------------- 新建 / 删除节点 ----------------
def _find_tree_span(text, tree_id):
    for m in re.finditer(r'(?m)^\s*focus_tree\s*=\s*\{', text):
        tb = text.find('{', m.end() - 1)
        te = brace_match(text, tb) - 1
        body = text[tb + 1:te]
        mid = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_]+)"?', body)
        if mid and mid.group(1) == tree_id:
            return tb, te
    return None

def add_focus(root, rel, tree_id, fid, x, y, cost=5, icon="GFX_goal_generic_national_unity"):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(fid), strip_comments(text)):
        return False, "ID 已存在: " + fid
    span = _find_tree_span(text, tree_id)
    if not span:
        return False, "未找到树: " + tree_id
    tb, te = span
    node = "\n\tfocus = {\n\t\tid = %s\n\t\ticon = %s\n\t\tx = %s\n\t\ty = %s\n\t\tcost = %s\n\t}\n" % (
        fid, icon, x, y, cost)
    newtext = text[:te] + node + text[te:]
    backup(path)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(newtext)
    CHANGED[path] = rel
    reload_data()
    return True, "已新建 " + fid

def delete_focus(root, rel, fid):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    spans = []
    for m in re.finditer(r'(?m)^\s*(?:focus|shared_focus)\s*=\s*\{', text):
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        body = text[b + 1:e - 1]
        if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(fid), body):
            spans.append((m.start(), e))
    if not spans:
        return False, "未找到焦点 " + fid
    s, e = spans[0]
    newtext = text[:s] + text[e:]
    backup(path)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(newtext)
    CHANGED[path] = rel
    reload_data()
    return True, "已删除 " + fid

# ---------------- 树级设置 ----------------
def save_tree(root, rel, tree_id, default=None, country_raw=None):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    for m in re.finditer(r'(?m)^\s*focus_tree\s*=\s*\{', text):
        b = text.find('{', m.start())
        e = brace_match(text, b)
        block = text[b + 1:e - 1]
        if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(tree_id), block):
            nb = block
            if default:
                nb = set_scalar(nb, "default", default)
            if country_raw:
                if not braces_balanced(country_raw):
                    return False, "country 块花括号不匹配"
                m2 = re.search(r'(?m)^[ \t]*country\s*=\s*\{', nb)
                if m2:
                    br = nb.find('{', m2.start())
                    en = brace_match(nb, br)
                    nb = nb[:m2.start()] + country_raw.strip() + "\n" + nb[en:]
                else:
                    nb = nb.rstrip() + "\n\t" + country_raw.strip() + "\n"
            snapshot(path)
            io.open(path, "w", encoding="utf-8", newline="").write(text[:b + 1] + nb + text[e - 1:])
            CHANGED[path] = rel
            reload_data()
            return True, "树设置已保存"
    return False, "未找到树 " + tree_id

# ---------------- 国家精神 ----------------
def apply_modifier_props(raw, props):
    if not props:
        return raw
    m = re.search(r'(?m)^[ \t]*modifier\s*=\s*\{', raw)
    if m:
        b = raw.find('{', m.start())
        e = brace_match(raw, b)
        inner = raw[b + 1:e - 1]
        for k, v in props.items():
            inner = set_scalar(inner, k, v)
        body = "\n".join("\t" + ln for ln in inner.strip("\n").splitlines())
        return raw[:m.start()] + "modifier = {\n" + body + "\n\t\t}" + raw[e:]
    lines = ["modifier = {"]
    for k, v in props.items():
        lines.append("\t%s = %s" % (k, v))
    lines.append("}")
    return raw.rstrip() + "\n\t\t" + "\n\t\t".join(lines) + "\n"

def save_idea(root, rel, oid, rawtext, props=None, picture=""):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(oid), text)
    if not m:
        return False, "未找到国家精神 " + oid
    b = text.find('{', m.start())
    e = brace_match(text, b)
    if picture:
        rawtext = set_scalar(rawtext, "picture", picture)
    rawtext = apply_modifier_props(rawtext, props or {})
    for key, bname in (("allowed_raw", "allowed"), ("trigger_raw", "trigger"),
                       ("possible_raw", "possible")):
        if (props or {}).get(key):
            rawtext = set_raw_block(rawtext, bname, props.get(key))
    if not braces_balanced(rawtext):
        return False, "花括号不匹配，未保存"
    backup(path)
    newtext = text[:m.start()] + rawtext.strip() + "\n" + text[e:]
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(newtext)
    CHANGED[path] = rel
    reload_data()
    return True, "国家精神已保存"

def add_idea(root, oid):
    if not re.match(r'^[A-Za-z0-9_]+$', oid or ""):
        return False, "id 只能包含字母数字下划线"
    d = os.path.join(root, "common", "ideas")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "zz_focus_editor_ideas.txt")
    if os.path.exists(path):
        text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    else:
        text = "ideas = {\n\tcountry = {\n\t}\n}\n"
    if re.search(r'(?m)^\s*%s\s*=\s*\{' % re.escape(oid), text):
        return False, "国家精神已存在: " + oid
    m = re.search(r'(?m)^\s*country\s*=\s*\{', text)
    if not m:
        text = "ideas = {\n\tcountry = {\n\t}\n}\n"
        m = re.search(r'(?m)^\s*country\s*=\s*\{', text)
    b = text.find('{', m.start())
    e = brace_match(text, b)
    block = "\n\t\t%s = {\n\t\t\tpicture = GFX_idea_generic\n\t\t\tmodifier = {\n\t\t\t}\n\t\t}\n" % oid
    prefix = text[:e - 1].rstrip(" \t")
    newtext = prefix + "\n" + block + "\t" + text[e - 1:]
    backup(path)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(newtext)
    CHANGED[path] = os.path.join("common", "ideas", "zz_focus_editor_ideas.txt")
    reload_data()
    return True, "已新建国家精神 " + oid

def delete_idea(root, rel, oid):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(oid), text)
    if not m:
        return False, "未找到国家精神 " + oid
    b = text.find('{', m.start())
    e = brace_match(text, b)
    newtext = text[:m.start()] + text[e:]
    backup(path)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(newtext)
    CHANGED[path] = rel
    reload_data()
    return True, "已删除国家精神 " + oid

# ---------------- 装备 ----------------
def save_equipment(root, rel, eid, raw, name="", desc="", name_ja="", desc_ja="", props=None,
                   name_en="", desc_en="", picture=""):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(eid), text)
    if not m:
        return False, "未找到装备 " + eid
    b = text.find('{', m.start())
    e = brace_match(text, b)
    if picture:
        raw = set_scalar(raw, "picture", picture)
    if props:
        for k, v in props.items():
            if k in ("upgrades_raw", "module_slots_raw"):
                continue
            if v not in (None, ""):
                raw = set_scalar(raw, k, v)
        if props.get("upgrades_raw"):
            raw = set_raw_block(raw, "upgrades", props.get("upgrades_raw"))
        if props.get("module_slots_raw"):
            raw = set_raw_block(raw, "module_slots", props.get("module_slots_raw"))
    if not braces_balanced(raw):
        return False, "花括号不匹配，未保存"
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text[:m.start()] + raw.strip() + "\n" + text[e:])
    CHANGED[path] = rel
    ents = {}
    if name: ents.setdefault("simp_chinese", {})[eid] = name
    if desc: ents.setdefault("simp_chinese", {})[eid + "_desc"] = desc
    if name_ja: ents.setdefault("japanese", {})[eid] = name_ja
    if desc_ja: ents.setdefault("japanese", {})[eid + "_desc"] = desc_ja
    if name_en: ents.setdefault("english", {})[eid] = name_en
    if desc_en: ents.setdefault("english", {})[eid + "_desc"] = desc_en
    if ents:
        save_loc(root, ents)
    reload_data()
    return True, "装备已保存"

# ---------------- 科技 ----------------
def validate_tech_script(raw, tid):
    if not braces_balanced(raw):
        return False, "花括号不匹配"
    for m in re.finditer(r'(?m)^\s*(research_cost|start_year|year)\s*=\s*([^\s#]+)', raw):
        if not re.match(r'^[0-9.]+$', m.group(2)):
            return False, "%s 必须是数字" % m.group(1)
    for m in re.finditer(r'leads_to_tech\s*=\s*"?([A-Za-z0-9_]+)"?', raw):
        t = m.group(1)
        if t != tid and t not in TECHS:
            return False, "leads_to_tech 指向不存在的科技: " + t
    if "research_cost" not in raw:
        return False, "缺少 research_cost"
    if "start_year" not in raw and "year" not in raw:
        return False, "缺少 start_year / year"
    return True, ""

def save_tech(root, rel, tid, raw, name="", desc="", name_ja="", desc_ja="", props=None,
              name_en="", desc_en=""):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(tid), text)
    if not m:
        return False, "未找到科技 " + tid
    b = text.find('{', m.start())
    e = brace_match(text, b)
    if props:
        for k in ("year", "start_year", "research_cost", "path"):
            if props.get(k) not in (None, ""):
                raw = set_scalar(raw, k, props.get(k))
        if props.get("prereq_raw"):
            raw = set_raw_block(raw, "prerequisite", props.get("prereq_raw"))
        for key, bname in (("enable_equipments_raw", "enable_equipments"),
                           ("sub_technologies_raw", "sub_technologies")):
            if props.get(key):
                raw = set_raw_block(raw, bname, props.get(key))
    okv, msgv = validate_tech_script(raw, tid)
    if not okv:
        return False, msgv + "，未保存"
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text[:m.start()] + raw.strip() + "\n" + text[e:])
    CHANGED[path] = rel
    ents = {}
    if name: ents.setdefault("simp_chinese", {})[tid] = name
    if desc: ents.setdefault("simp_chinese", {})[tid + "_desc"] = desc
    if name_ja: ents.setdefault("japanese", {})[tid] = name_ja
    if desc_ja: ents.setdefault("japanese", {})[tid + "_desc"] = desc_ja
    if name_en: ents.setdefault("english", {})[tid] = name_en
    if desc_en: ents.setdefault("english", {})[tid + "_desc"] = desc_en
    if ents:
        save_loc(root, ents)
    reload_data()
    return True, "科技已保存"

def add_tech(root, tid, folder, year="1936"):
    if not re.match(r'^[A-Za-z0-9_]+$', tid or ""):
        return False, "科技 id 只能字母数字下划线"
    folder = folder or "custom_folder"
    d = os.path.join(root, "common", "technologies")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "zz_focus_editor_technologies.txt")
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else "technologies = {\n}\n"
    if re.search(r'(?m)^\s*%s\s*=\s*\{' % re.escape(tid), text):
        return False, "科技已存在"
    block = ("\t\t%s = {\n\t\t\tresearch_cost = 1\n\t\t\tstart_year = %s\n"
             "\t\t\tfolder = {\n\t\t\t\tname = %s\n\t\t\t}\n\t\t}\n" % (tid, year, folder))
    fm = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(folder), text)
    if fm:
        fb = text.find('{', fm.start())
        fe = brace_match(text, fb)
        text = text[:fe - 1] + block + text[fe - 1:]
    else:
        tm = re.search(r'(?m)^\s*technologies\s*=\s*\{', text)
        tb = text.find('{', tm.start())
        te = brace_match(text, tb)
        text = text[:te - 1] + ("\t%s = {\n%s\t}\n" % (folder, block)) + text[te - 1:]
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text)
    CHANGED[path] = os.path.join("common", "technologies", "zz_focus_editor_technologies.txt")
    reload_data()
    return True, "已新建科技 " + tid

def delete_tech(root, rel, tid):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(tid), text)
    if not m:
        return False, "未找到科技 " + tid
    b = text.find('{', m.start())
    e = brace_match(text, b)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text[:m.start()] + text[e:])
    CHANGED[path] = rel
    reload_data()
    return True, "已删除科技 " + tid

# ---------------- 事件 ----------------
def save_event(root, rel, eid, raw, title="", desc="", title_ja="", desc_ja="",
               title_en="", desc_en="", options=None, trigger_raw="", immediate_raw="", picture=""):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    m = re.search(r'(?m)^[ \t]*id\s*=\s*"?%s"?' % re.escape(eid), text)
    if not m:
        return False, "未找到事件 " + eid
    if trigger_raw:
        raw = set_raw_block(raw, "trigger", trigger_raw)
    if immediate_raw:
        raw = set_raw_block(raw, "immediate", immediate_raw)
    if picture:
        raw = set_scalar(raw, "picture", picture)
    # 定位包含该 id 的事件块：向前找最近的 *_event = {
    start = text.rfind("_event", 0, m.start())
    brace = text.find('{', start)
    e = brace_match(text, brace)
    if not braces_balanced(raw):
        return False, "花括号不匹配，未保存"
    nsm = re.search(r'add_namespace\s*=\s*(\w+)', text)
    if nsm and "." in eid and not eid.startswith(nsm.group(1) + "."):
        return False, "事件 id 前缀与文件 namespace 不一致"
    if "option" not in raw:
        return False, "事件至少需要一个 option"
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text[:brace - 1] + raw.strip() + "\n" + text[e:])
    CHANGED[path] = rel
    ents = {}
    if title: ents.setdefault("simp_chinese", {})[eid + ".t"] = title
    if desc: ents.setdefault("simp_chinese", {})[eid + ".d"] = desc
    if title_ja: ents.setdefault("japanese", {})[eid + ".t"] = title_ja
    if desc_ja: ents.setdefault("japanese", {})[eid + ".d"] = desc_ja
    if title_en: ents.setdefault("english", {})[eid + ".t"] = title_en
    if desc_en: ents.setdefault("english", {})[eid + ".d"] = desc_en
    for o in (options or []):
        k = o.get("key")
        t = o.get("text")
        if k and t:
            ents.setdefault("simp_chinese", {})[k] = t
    if ents:
        save_loc(root, ents)
    reload_data()
    return True, "事件已保存"

def add_equipment(root, eid):
    if not re.match(r'^[A-Za-z0-9_]+$', eid or ""):
        return False, "id 只能字母数字下划线"
    d = os.path.join(root, "common", "units", "equipment")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "zz_focus_editor_equipment.txt")
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else "equipments = {\n}\n"
    if re.search(r'(?m)^\s*%s\s*=\s*\{' % re.escape(eid), text):
        return False, "装备已存在"
    brace = text.find('{', text.find("equipments"))
    end = brace_match(text, brace)
    block = ("\n\t%s = {\n\t\tyear = 1936\n\t\tis_buildable = yes\n\t\ttype = infantry\n"
             "\t\tbuild_cost_ic = 1.0\n\t}\n" % eid)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text[:end - 1] + block + text[end - 1:])
    CHANGED[path] = os.path.join("common", "units", "equipment", "zz_focus_editor_equipment.txt")
    reload_data()
    return True, "已新建装备 " + eid

def delete_equipment(root, rel, eid):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(eid), text)
    if not m:
        return False, "未找到装备 " + eid
    b = text.find('{', m.start())
    e = brace_match(text, b)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text[:m.start()] + text[e:])
    CHANGED[path] = rel
    reload_data()
    return True, "已删除装备 " + eid

def tech_link(root, rel, src, dst):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(src), text)
    if not m:
        return False, "未找到源科技 " + src
    b = text.find('{', m.start())
    e = brace_match(text, b)
    block = text[b + 1:e - 1]
    if re.search(r'leads_to_tech\s*=\s*"?%s"?' % re.escape(dst), block):
        return False, "这条前置已经存在"
    adj = {k: set(v.get("leads", [])) for k, v in TECHS.items()}
    stack, seen = [dst], set()
    while stack:
        n = stack.pop()
        if n == src:
            return False, "会形成循环前置，已拒绝"
        if n in seen:
            continue
        seen.add(n)
        stack += list(adj.get(n, []))
    pm = re.search(r'(?m)^[ \t]*path\s*=\s*\{', block)
    if pm:
        pb = block.find('{', pm.start())
        pe = brace_match(block, pb)
        nb = block[:pe - 1] + "\n\t\t\tleads_to_tech = %s\n\t\t\tresearch_cost_coeff = 1\n\t\t" % dst + block[pe - 1:]
    else:
        nb = block.rstrip() + "\n\t\tpath = {\n\t\t\tleads_to_tech = %s\n\t\t\tresearch_cost_coeff = 1\n\t\t}\n\t" % dst
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text[:b + 1] + nb + text[e - 1:])
    CHANGED[path] = rel
    reload_data()
    return True, "已添加前置：%s → %s" % (src, dst)

def brace_balance(text):
    depth = 0
    extras = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '#':
            j = text.find('\n', i)
            if j < 0:
                break
            i = j + 1
            continue
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == '\\':
                    i += 1
                i += 1
            i += 1
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            if depth == 0:
                extras.append(i)
            else:
                depth -= 1
        i += 1
    return depth, extras

def brace_scan_roots(root):
    out = []
    for sub in ("common", "events"):
        base = os.path.join(root, sub)
        if not os.path.isdir(base):
            continue
        for dp, dns, fns in os.walk(base):
            for fn in fns:
                if fn.endswith(".txt"):
                    p = os.path.join(dp, fn)
                    out.append(p)
    return out

def brace_issues():
    items = []
    for root in ROOTS:
        for p in brace_scan_roots(root):
            try:
                text = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            d, extras = brace_balance(text)
            if d or extras:
                rel = os.path.relpath(p, root)
                items.append({"kind": "文件花括号不平衡", "id": rel.replace(os.sep, "/"),
                              "file": rel.replace(os.sep, "/"), "root": root,
                              "where": "depth=%s extra=%s" % (d, len(extras))})
    return items

def repair_file_braces(rel):
    for root in ROOTS:
        p = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.exists(p):
            continue
        text = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        depth, extras = brace_balance(text)
        if not depth and not extras:
            return False, "这个文件花括号本来就是平衡的"
        chars = list(text)
        for pos in reversed(extras):
            del chars[pos]
        newtext = "".join(chars)
        d2, _ = brace_balance(newtext)
        if d2 > 0:
            newtext = newtext.rstrip() + "\n" + ("}\n" * d2)
        snapshot(p)
        io.open(p, "w", encoding="utf-8", newline="").write(newtext)
        CHANGED[p] = rel
        return True, "已修复 %s（补 %s 个 / 删 %s 个括号）" % (rel, d2, len(extras))
    return False, "没有找到文件"

def repair_all_braces():
    fixed = 0
    for it in brace_issues():
        try:
            ok, _ = repair_file_braces(it["file"])
            if ok:
                fixed += 1
        except Exception:
            pass
    reload_data()
    return True, "已修复 %s 个文件" % fixed

def mod_conflicts():
    roots = [(r, os.path.basename(r.rstrip("\\/")) or r) for r in ROOTS]
    rps = []
    for r, n in roots:
        rp = set()
        p = os.path.join(r, "descriptor.mod")
        if os.path.exists(p):
            try:
                txt = io.open(p, encoding="utf-8", errors="replace").read()
                rp = set(re.findall(r'replace_path\s*=\s*"([^"]+)"', txt))
            except Exception:
                pass
        rps.append(rp)
    out = []
    seen = set()
    for j, (r2, n2) in enumerate(roots):
        for i, (r1, n1) in enumerate(roots):
            if i == j:
                continue
            for path in rps[j]:
                key = (n2, path, n1)
                if key in seen:
                    continue
                d1 = os.path.join(r1, path.replace("/", os.sep))
                if os.path.isdir(d1):
                    try:
                        has = any(os.scandir(d1))
                    except Exception:
                        has = False
                    if has:
                        seen.add(key)
                        out.append({"kind": "模组路径冲突", "id": path,
                                    "where": n2 + " 的 replace_path 会覆盖/排除 " + n1,
                                    "file": "descriptor.mod", "root": r2})
    return out

def report_items():
    items = []
    for tid in TREE_ORDER:
        t = TREES.get(tid)
        if not t:
            continue
        ids = {f["id"] for f in t["focuses"]}
        for f in t["focuses"]:
            if f["id"] not in LOC or not LOC.get(f["id"], "").strip():
                items.append({"kind": "缺失本地化", "id": f["id"], "where": tid, "file": t["file"]})
            for g in f.get("prereq", []):
                for p in g:
                    if p not in ids:
                        items.append({"kind": "悬空前置", "id": f["id"], "where": p, "file": t["file"]})
    for tid, t in TECHS.items():
        for p in t.get("prereq", []):
            if p not in TECHS:
                items.append({"kind": "科技前置不存在", "id": tid, "where": p, "file": t["file"]})
        for l in t.get("leads", []):
            if l not in TECHS:
                items.append({"kind": "科技 leads 不存在", "id": tid, "where": l, "file": t["file"]})
    for eid, e in EVENTS.items():
        ns = e.get("ns", "")
        if ns and "." in eid and not eid.startswith(ns + "."):
            items.append({"kind": "事件 namespace 不匹配", "id": eid, "where": ns, "file": e.get("file", "")})
    items += brace_issues()
    items += mod_conflicts()
    return items

def unload_mod(root):
    p = os.path.abspath(root or "")
    before = len(ROOTS)
    ROOTS[:] = [r for r in ROOTS if os.path.abspath(r) != p]
    if len(ROOTS) == before:
        return False, "没有找到这个 mod"
    reload_data()
    build_icons(ROOTS, GAME)
    return True, "已卸载：%s" % (os.path.basename(p.rstrip("/").rstrip("\\")) or p)

def writable_root():
    for r in ROOTS:
        if not is_under_game(r):
            return r
    return None

def writable_target(target=""):
    if target:
        t = os.path.abspath(target)
        if t in [os.path.abspath(r) for r in ROOTS] and not is_under_game(t):
            return t
    return writable_root()

def _append_container(path, container, block):
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else (container + " = {\n}\n")
    m = re.search(r'(?m)^\s*%s\s*=\s*\{' % re.escape(container), text)
    if not m:
        text = text.rstrip() + "\n" + container + " = {\n}\n"
        m = re.search(r'(?m)^\s*%s\s*=\s*\{' % re.escape(container), text)
    b = text.find('{', m.start())
    e = brace_match(text, b)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text[:e - 1] + block + text[e - 1:])
    return os.path.relpath(path, os.path.dirname(path))

def copy_tree(tree_id, new_id):
    t = TREES.get(tree_id)
    if not t:
        return False, "没有找到这棵国策树"
    if not re.match(r'^[A-Za-z0-9_]+$', new_id or ""):
        return False, "新树 ID 只能包含字母数字下划线"
    if new_id in TREES:
        return False, "树 ID 已存在"
    dest = writable_root()
    if not dest:
        return False, "没有可写的模组，请先加载/新建一个模组"
    src = os.path.join(t.get("root") or dest, t["file"])
    if not os.path.exists(src):
        return False, "找不到源文件"
    text = io.open(src, encoding="utf-8", errors="replace", newline="").read()
    block = None
    for m in re.finditer(r'(?m)^\s*focus_tree\s*=\s*\{', text):
        b = text.find('{', m.start())
        e = brace_match(text, b)
        body = text[b + 1:e - 1]
        mid = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_]+)"?', body)
        if mid and mid.group(1) == tree_id:
            block = body
            break
    if block is None:
        return False, "源文件里找不到这棵树的结构"
    ids = []
    for s, e2, fb in find_blocks(block, "focus"):
        node = parse_focus_like(fb)
        if node:
            ids.append(node["id"])
    newblock = block
    for oid in ids:
        newblock = re.sub(r'\b%s\b' % re.escape(oid), new_id + "_" + oid, newblock)
    newblock = re.sub(r'(?m)^(\s*id\s*=\s*)"?%s"?' % re.escape(tree_id), r'\1' + new_id, newblock, count=1)
    path = os.path.join(dest, "common", "national_focus", "zz_focus_editor_copied.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        txt = io.open(path, encoding="utf-8", errors="replace", newline="").read()
        txt = txt.rstrip() + "\nfocus_tree = {\n" + newblock.strip() + "\n}\n"
    else:
        txt = "focus_tree = {\n" + newblock.strip() + "\n}\n"
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(txt)
    CHANGED[path] = os.path.join("common", "national_focus", "zz_focus_editor_copied.txt")
    ents = {"simp_chinese": {}}
    for oid in ids:
        nm = LOC.get(oid, "")
        ds = LOC.get(oid + "_desc", "")
        if nm:
            ents["simp_chinese"][new_id + "_" + oid] = nm
        if ds:
            ents["simp_chinese"][new_id + "_" + oid + "_desc"] = ds
    if ents["simp_chinese"]:
        save_loc(dest, ents)
    reload_data()
    return True, "已复制到你的模组：%s（%d 个焦点）" % (new_id, len(ids))

def copy_item(kind, item_id, new_id):
    dest = writable_root()
    if not dest:
        return False, "没有可写的模组，请先加载/新建一个模组"
    if kind == "idea":
        src = IDEAS.get(item_id)
    elif kind == "equip":
        src = EQUIPMENTS.get(item_id)
    elif kind == "tech":
        src = TECHS.get(item_id)
    elif kind == "event":
        src = EVENTS.get(item_id)
    else:
        src = None
    if not src:
        return False, "没有找到要复制的内容"
    if not re.match(r'^[A-Za-z0-9_]+$', new_id or ""):
        return False, "新 ID 只能包含字母数字下划线"
    raw = src.get("raw", "")
    raw = re.sub(r'(?m)^(\s*)%s(\s*=\s*\{)' % re.escape(item_id),
                 lambda m: m.group(1) + new_id + m.group(2), raw, count=1)
    ents = {}
    if kind == "idea":
        block = "\n" + raw.strip() + "\n"
        path = os.path.join(dest, "common", "ideas", "zz_focus_editor_copied.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _append_container(path, "ideas", block)
        rel = os.path.join("common", "ideas", "zz_focus_editor_copied.txt")
        ents.setdefault("simp_chinese", {})[new_id] = src.get("name", new_id)
        if src.get("desc"):
            ents["simp_chinese"][new_id + "_desc"] = src.get("desc")
    elif kind == "equip":
        block = "\n" + raw.strip() + "\n"
        path = os.path.join(dest, "common", "units", "equipment", "zz_focus_editor_copied.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _append_container(path, "equipments", block)
        rel = os.path.join("common", "units", "equipment", "zz_focus_editor_copied.txt")
        ents.setdefault("simp_chinese", {})[new_id] = src.get("name", new_id)
    elif kind == "tech":
        old_folder = src.get("path") or "copied_folder"
        raw = re.sub(r'(?m)^(\s*name\s*=\s*)"?%s"?' % re.escape(old_folder),
                     r'\1copied_folder', raw, count=1)
        block = "\n\tcopied_folder = {\n" + raw.strip() + "\n\t}\n"
        path = os.path.join(dest, "common", "technologies", "zz_focus_editor_copied.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _append_container(path, "technologies", block)
        rel = os.path.join("common", "technologies", "zz_focus_editor_copied.txt")
        ents.setdefault("simp_chinese", {})[new_id] = src.get("name", new_id)
    else:
        path = os.path.join(dest, "events", "zz_focus_editor_copied.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        txt = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else "add_namespace = zzfe_copied\n\n"
        if "add_namespace = zzfe_copied" not in txt:
            txt = "add_namespace = zzfe_copied\n\n" + txt
        txt = txt.rstrip() + "\n" + raw.strip() + "\n"
        snapshot(path)
        io.open(path, "w", encoding="utf-8", newline="").write(txt)
        rel = os.path.join("events", "zz_focus_editor_copied.txt")
        ents.setdefault("simp_chinese", {})[new_id + ".t"] = src.get("title", new_id)
    if ents:
        save_loc(dest, ents)
    reload_data()
    return True, "已复制到你的模组：%s" % new_id

def save_design(archetype, modules, org="", name="", target=""):
    dest = writable_target(target)
    if not dest:
        return False, "没有可写的模组"
    d = os.path.join(dest, "common", "units", "equipment")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "zz_focus_editor_designs.txt")
    old = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else ""
    lines = ["# 设计草稿（不会自动生效，供参考/复制）",
             "# archetype = %s" % archetype,
             "# org = %s" % (org or ""),
             "# name = %s" % (name or archetype)]
    for cat, mid in sorted((modules or {}).items()):
        lines.append("# %s = %s" % (cat, mid))
    block = "\n".join(lines) + "\n"
    if old and not old.endswith("\n"):
        old += "\n"
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(old + "\n" + block)
    CHANGED[path] = os.path.join("common", "units", "equipment", "zz_focus_editor_designs.txt")
    return True, "设计草稿已保存到模组"

def save_variant(arch, modules, name="", org="", target=""):
    dest = writable_target(target)
    if not dest:
        return False, "没有可写的模组"
    eq = EQUIPMENTS.get(arch)
    if not eq:
        return False, "没有找到底盘 " + str(arch)
    slots = eq.get("slots") or []
    if not slots:
        return False, "这个底盘没有 module_slots 定义，无法生成变体"
    lines = []
    missing = []
    for sl in slots:
        mid = (modules or {}).get(sl["slot"])
        if mid:
            lines.append("\t\t\t\t%s = %s" % (sl["slot"], mid))
        elif sl.get("required"):
            missing.append(sl["slot"])
    if missing:
        return False, "必装槽位未选择：%s" % "、".join(missing)
    if not lines:
        return False, "至少选择一个模块"
    nm = re.sub(r'[^A-Za-z0-9_]', '', (name or arch))[:40] or "design"
    effect_id = "zzfe_variant_" + nm
    effect = ("%s = {\n"
              "\tcreate_equipment_variant = {\n"
              "\t\tname = \"%s\"\n"
              "\t\ttype = %s\n"
              "\t\tparent_version = 0\n"
              "\t\tallow_without_tech = yes\n"
              "\t\tmodules = {\n%s\n\t\t}\n"
              "\t}\n}\n") % (effect_id, (name or arch).replace('"', ""), arch, "\n".join(lines))
    d = os.path.join(dest, "common", "scripted_effects")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "zz_focus_editor_variants.txt")
    old = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else ""
    m = re.search(r'(?m)^%s\s*=\s*\{' % re.escape(effect_id), old)
    if m:
        b = old.find('{', m.start())
        e = brace_match(old, b)
        newtext = old[:m.start()] + effect + old[e:]
    else:
        newtext = old.rstrip() + ("\n\n" if old.strip() else "") + effect
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(newtext)
    CHANGED[path] = os.path.join("common", "scripted_effects", "zz_focus_editor_variants.txt")
    return True, "已生成装备变体效果（%s），可插入国策/事件或直接调用" % effect_id

def is_under_game(p):
    try:
        p = os.path.abspath(p or "")
        g = os.path.abspath(GAME or "")
        return g and (p == g or p.startswith(g + os.sep))
    except Exception:
        return False

def load_vanilla():
    if not os.path.isdir(GAME):
        return False, "没有找到游戏目录"
    if GAME not in ROOTS:
        ROOTS.append(GAME)
    n = load_mod(GAME)
    try:
        build_icons(ROOTS, GAME)
    except Exception as e:
        print("图标构建失败:", e)
    return True, "已加载原版参考（只读），共 %d 棵树" % n

def list_backups(root, rel):
    path = os.path.abspath(os.path.join(root, rel)) if root else ""
    h = HISTORY.get(path)
    items = []
    if h:
        for i, fn in enumerate(h.get("undo", [])):
            try:
                ts = int(os.path.basename(fn).rsplit("_", 1)[-1].split(".")[0]) // 1000
                t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
            except Exception:
                t = "?"
            items.append({"index": i, "time": t, "name": os.path.basename(fn)})
    return items

def restore_backup(root, rel, index):
    path = os.path.abspath(os.path.join(root, rel))
    h = HISTORY.get(path)
    if not h or index < 0 or index >= len(h["undo"]):
        return False, "备份不存在"
    snapshot(path)
    shutil.copyfile(h["undo"][index], path)
    reload_data()
    return True, "已恢复备份"

# ---------------- AI ----------------
AI_CONFIG_PATH = os.path.join(WORK, "ai_config.json")
DEFAULT_AI = {
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-4o-mini",
    "system": "你是 HOI4 mod 脚本助手，回答要给出可直接使用的脚本片段。",
}

def load_ai():
    cfg = dict(DEFAULT_AI)
    try:
        if os.path.exists(AI_CONFIG_PATH):
            cfg.update(json.loads(io.open(AI_CONFIG_PATH, encoding="utf-8").read()))
    except Exception:
        pass
    return cfg

def save_ai(cfg):
    try:
        old = load_ai()
        data = {k: cfg.get(k, DEFAULT_AI.get(k, "")) for k in DEFAULT_AI}
        if not data.get("api_key"):
            data["api_key"] = old.get("api_key", "")
        io.open(AI_CONFIG_PATH, "w", encoding="utf-8", newline="").write(
            json.dumps(data, ensure_ascii=False, indent=2))
        return True, "AI 配置已保存"
    except Exception as e:
        return False, "保存失败: %s" % e

def _post_json(url, payload, headers, timeout=90):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=dict({"Content-Type": "application/json"}, **headers))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def ai_chat(cfg, prompt, context=""):
    provider = (cfg.get("provider") or "openai").lower()
    base = (cfg.get("base_url") or "").rstrip("/")
    key = cfg.get("api_key") or ""
    model = cfg.get("model") or ""
    system = cfg.get("system") or DEFAULT_AI["system"]
    text = prompt if not context else (context + "\n\n---\n\n" + prompt)
    try:
        if provider in ("openai", "deepseek", "ollama", "custom"):
            if not base:
                return False, "请填写 Base URL"
            data = _post_json(base + "/chat/completions", {
                "model": model, "temperature": 0.3,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": text}]},
                {"Authorization": "Bearer " + key} if key else {})
            return True, data["choices"][0]["message"]["content"]
        if provider == "anthropic":
            if not base:
                return False, "请填写 Base URL"
            data = _post_json(base + "/messages", {
                "model": model, "max_tokens": 2000, "system": system,
                "messages": [{"role": "user", "content": text}]},
                {"x-api-key": key, "anthropic-version": "2023-06-01"})
            return True, "".join(b.get("text", "") for b in data.get("content", []))
        if provider == "gemini":
            url = base + "/models/" + model + ":generateContent?key=" + key
            data = _post_json(url, {"contents": [{"parts": [{"text": system + "\n\n" + text}]}]}, {})
            return True, data["candidates"][0]["content"]["parts"][0]["text"]
        return False, "未知的提供商: " + provider
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            body = ""
        return False, "HTTP %s: %s" % (e.code, body)
    except Exception as e:
        return False, "请求失败: %s" % e

def add_shared_focus(root, sid):
    if not re.match(r'^[A-Za-z0-9_]+$', sid or ""):
        return False, "id 只能字母数字下划线"
    d = os.path.join(root, "common", "national_focus")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "zz_focus_editor_shared.txt")
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else ""
    if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(sid), text):
        return False, "共享焦点已存在"
    block = ("\nshared_focus = {\n\tid = %s\n\ticon = GFX_goal_generic_national_unity\n"
             "\tx = 0\n\ty = 0\n\tcost = 1\n}\n" % sid)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text + block)
    CHANGED[path] = os.path.join("common", "national_focus", "zz_focus_editor_shared.txt")
    reload_data()
    return True, "已新建共享焦点 " + sid

def delete_shared_focus(root, rel, sid):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    for m in re.finditer(r'(?m)^\s*shared_focus\s*=\s*\{', text):
        b = text.find('{', m.start())
        e = brace_match(text, b)
        if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(sid), text[b:e]):
            snapshot(path)
            io.open(path, "w", encoding="utf-8", newline="").write(text[:m.start()] + text[e:])
            CHANGED[path] = rel
            reload_data()
            return True, "已删除共享焦点 " + sid
    return False, "未找到共享焦点 " + sid

def add_event(root, eid):
    if not re.match(r'^[A-Za-z0-9_]+\.[A-Za-z0-9_]+$', eid or ""):
        return False, "事件 id 需要 namespace.member 格式"
    ns = eid.split(".")[0]
    d = os.path.join(root, "events")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "zz_focus_editor_events.txt")
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else ""
    if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(eid), text):
        return False, "事件已存在"
    if ("add_namespace = " + ns) not in text:
        text += "\nadd_namespace = %s\n" % ns
    text += ("\ncountry_event = {\n\tid = %s\n\ttitle = %s.t\n\tdesc = %s.d\n"
             "\tis_triggered_only = yes\n\toption = {\n\t\tname = %s.a\n\t}\n}\n" % (eid, eid, eid, eid))
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text)
    CHANGED[path] = os.path.join("events", "zz_focus_editor_events.txt")
    reload_data()
    return True, "已新建事件 " + eid

def delete_event(root, rel, eid):
    path = os.path.join(root, rel)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read()
    m = re.search(r'(?m)^[ \t]*id\s*=\s*"?%s"?' % re.escape(eid), text)
    if not m:
        return False, "未找到事件 " + eid
    start = text.rfind("_event", 0, m.start())
    brace = text.find('{', start)
    e = brace_match(text, brace)
    snapshot(path)
    io.open(path, "w", encoding="utf-8", newline="").write(text[:start - 1] + text[e:])
    CHANGED[path] = rel
    reload_data()
    return True, "已删除事件 " + eid

# ---------------- HTTP 服务 ----------------
INDEX = os.path.join(RES_DIR, "focus_editor_index.html")

def _lang(path):
    m = re.search(r"[?&]lang=(zh|en|ja)\b", path or "")
    return m.group(1) if m else "zh"

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200, ctype="application/json; charset=utf-8"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        hdrs = []
        if len(body) > 50000 and "application/json" in ctype and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            try:
                import gzip
                body = gzip.compress(body, 5)
                hdrs.append(("Content-Encoding", "gzip"))
            except Exception:
                pass
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in hdrs:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path_only = self.path.split("?")[0]
        if path_only == "/" or path_only.startswith("/index"):
            lang = _lang(self.path)
            html = io.open(INDEX, encoding="utf-8", errors="replace").read()
            html = i18n.inject(html, lang)
            self._send(html.encode("utf-8"), ctype="text/html; charset=utf-8")
        elif path_only.startswith("/help"):
            html = i18n.help_html(_lang(self.path))
            self._send(html.encode("utf-8"), ctype="text/html; charset=utf-8")
        elif path_only.startswith("/api/data"):
            self._send(data_payload())
        elif path_only == "/api/fs":
            qs = parse_qs(urlparse(self.path).query)
            self._send(fs_list(qs.get("path", [""])[0]))
        elif path_only == "/api/countries":
            self._send(countries_payload())
        elif path_only == "/api/states":
            self._send(states_payload())
        elif path_only == "/api/state":
            qs = parse_qs(urlparse(self.path).query)
            self._send(state_detail(qs.get("id", [""])[0]))
        elif path_only == "/api/country":
            qs = parse_qs(urlparse(self.path).query)
            self._send(country_detail(qs.get("tag", [""])[0]))
        elif path_only == "/api/country_history":
            qs = parse_qs(urlparse(self.path).query)
            self._send(country_history_raw(qs.get("tag", [""])[0]))
        elif path_only == "/api/lint":
            self._send(lint_project())
        elif path_only == "/api/missing_loc":
            self._send({"items": missing_loc()})
        elif path_only == "/api/errorlog":
            self._send(error_log())
        elif path_only == "/api/report":
            self._send({"items": report_items()})
        elif path_only == "/api/usages":
            qs = parse_qs(urlparse(self.path).query)
            self._send({"items": find_usages(qs.get("id", [""])[0])})
        elif path_only == "/api/icons":
            qs = parse_qs(urlparse(self.path).query)
            kind = qs.get("kind", ["focus"])[0]
            if kind == "tech":
                self._send({"list": sorted(TECH_ICONS.keys()), "map": TECH_ICONS})
            elif kind == "equip":
                self._send({"list": sorted(EQUIP_ICONS.keys()), "map": EQUIP_ICONS})
            else:
                self._send({"list": all_goal_icons() or sorted(ICONS.keys()),
                            "map": {g: "/api/icon?gfx=" + g for g in (all_goal_icons() or sorted(ICONS.keys()))}})
        elif path_only == "/api/focus":
            qs = parse_qs(urlparse(self.path).query)
            tid = qs.get("tree", [""])[0]
            fid = qs.get("id", [""])[0]
            t = TREES.get(tid)
            node = None
            if t:
                for f in t.get("focuses", []):
                    if f.get("id") == fid:
                        node = f
                        break
            if node:
                self._send({"desc": LOC.get(fid + "_desc", ""),
                            "effect": node.get("effect", ""),
                            "select_effect": node.get("select_effect", "")})
            else:
                self._send({"err": "not found"}, 404)
        elif path_only == "/api/backups":
            qs = parse_qs(urlparse(self.path).query)
            root = unquote(qs.get("root", [""])[0])
            rel = unquote(qs.get("file", [""])[0])
            self._send({"items": list_backups(root, rel)})
        elif path_only == "/api/raw":
            qs = parse_qs(urlparse(self.path).query)
            self._send(item_raw(qs.get("kind", [""])[0], qs.get("id", [""])[0]))
        elif path_only == "/api/ai_config":
            cfg = load_ai()
            cfg["api_key"] = "" if cfg.get("api_key") else ""
            self._send({"config": cfg, "has_key": bool(load_ai().get("api_key"))})
        elif path_only.startswith("/icons/"):
            fn = os.path.basename(path_only)
            p = os.path.join(ICON_DIR, fn)
            if os.path.exists(p):
                self._send(io.open(p, "rb").read(), ctype="image/png")
            else:
                self._send({"err": "no icon"}, 404)
        elif path_only == "/api/icon":
            qs = parse_qs(urlparse(self.path).query)
            p = icon_png(qs.get("gfx", [""])[0])
            if p:
                self._send(io.open(p, "rb").read(), ctype="image/png")
            else:
                self._send({"err": "no icon"}, 404)
        elif path_only in ("/mascot_face.png", "/mascot_card.png", "/mascot.ico"):
            fn = os.path.basename(path_only)
            p = os.path.join(RES_DIR, fn)
            if os.path.exists(p):
                ctype = "image/x-icon" if fn.endswith(".ico") else "image/png"
                self._send(io.open(p, "rb").read(), ctype=ctype)
            else:
                self._send({"err": "no mascot"}, 404)
        elif path_only.startswith("/mascot/"):
            fn = os.path.basename(path_only)
            p = os.path.join(RES_DIR, "mascot", fn)
            if os.path.exists(p):
                self._send(io.open(p, "rb").read(), ctype="image/png")
            else:
                self._send({"err": "no mascot"}, 404)
        else:
            self._send({"err": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) or b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            try:
                body = json.loads(raw.decode("gbk", errors="replace"))
            except Exception:
                self._send({"ok": False, "msg": "请求体不是合法 JSON"}, 400)
                return
        ro = body.get("root") or body.get("base") or ""
        # 只读保护针对"写文件"的接口；加载/卸载原版参考不改磁盘，必须放行
        if ro and is_under_game(ro) and self.path not in ("/api/load_vanilla", "/api/unload_mod"):
            self._send({"ok": False, "msg": "原版目录只读：请先复制到自己的模组再修改"})
            return
        if self.path == "/api/save":
            root = body.get("root")
            rel = body.get("file")
            fid = body.get("id")
            fields = body.get("fields", {})
            ok, msg = save_focus(root, rel, fid, fields)
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/export":
            path, msg = export_zip()
            self._send({"path": path, "msg": msg})
        elif self.path == "/api/add_focus":
            ok, msg = add_focus(body.get("root"), body.get("file"), body.get("tree"),
                                body.get("id"), body.get("x", 0), body.get("y", 0),
                                body.get("cost", 5),
                                body.get("icon", "GFX_goal_generic_national_unity"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/delete_focus":
            ok, msg = delete_focus(body.get("root"), body.get("file"), body.get("id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/loc_save":
            ok, msg = save_loc(body.get("root"), body.get("entries", {}))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/add_tree":
            ok, msg = add_tree(body.get("root"), body.get("id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/delete_tree":
            ok, msg = delete_tree(body.get("root"), body.get("file"), body.get("id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/tech_move":
            self._send(tech_move(body.get("root", ""), body.get("rel", ""),
                                 body.get("tid", ""), body.get("x", 0), body.get("y", 0)))
        elif self.path == "/api/state_save":
            self._send(state_save(body.get("id", ""), body.get("fields") or {}))
        elif self.path == "/api/country_save":
            self._send(country_history_save(body.get("tag", ""), body.get("fields") or {}))
        elif self.path == "/api/idea_save":
            root = body.get("root")
            ok, msg = save_idea(root, body.get("file"), body.get("id"),
                                body.get("raw") or "", body.get("props") or {},
                                body.get("picture") or "")
            if ok:
                ents = {}
                if body.get("name"):
                    ents.setdefault("simp_chinese", {})[body.get("id")] = body.get("name")
                if body.get("desc"):
                    ents.setdefault("simp_chinese", {})[body.get("id") + "_desc"] = body.get("desc")
                if body.get("name_ja"):
                    ents.setdefault("japanese", {})[body.get("id")] = body.get("name_ja")
                if body.get("desc_ja"):
                    ents.setdefault("japanese", {})[body.get("id") + "_desc"] = body.get("desc_ja")
                if body.get("name_en"):
                    ents.setdefault("english", {})[body.get("id")] = body.get("name_en")
                if body.get("desc_en"):
                    ents.setdefault("english", {})[body.get("id") + "_desc"] = body.get("desc_en")
                if ents:
                    save_loc(root, ents)
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/add_idea":
            ok, msg = add_idea(body.get("root"), body.get("id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/delete_idea":
            ok, msg = delete_idea(body.get("root"), body.get("file"), body.get("id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/pick_mod":
            ds = detect_mods()
            if not ds:
                self._send({"ok": False, "msg": "未选择目录"})
            else:
                ok, msg = load_mod_root(ds[0])
                self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/load_mod":
            ok, msg = load_mod_root(body.get("path"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/load_vanilla":
            ok, msg = load_vanilla()
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/copy_tree":
            ok, msg = copy_tree(body.get("id"), body.get("new_id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/copy_item":
            ok, msg = copy_item(body.get("kind"), body.get("id"), body.get("new_id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/design_save":
            ok, msg = save_design(body.get("archetype"), body.get("modules") or {},
                                  body.get("org") or "", body.get("name") or "",
                                  body.get("target") or "")
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/variant_save":
            ok, msg = save_variant(body.get("archetype"), body.get("modules") or {},
                                   body.get("name") or "", body.get("org") or "",
                                   body.get("target") or "")
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/new_mod":
            base = body.get("base") or mod_home()
            ok, msg = create_mod(base, body.get("id"), body.get("name"),
                                 body.get("version", "0.1.0"),
                                 body.get("game_version", "1.19.*"),
                                 body.get("tree_id", ""), body.get("tag", ""),
                                 bool(body.get("create_tree", True)))
            root = os.path.join(os.path.abspath(base), body.get("id") or "")
            if ok:
                ok2, msg2 = load_mod_root(root)
                msg = msg + ("；" + msg2 if ok2 else "（加载失败: %s）" % msg2)
            self._send({"ok": ok, "msg": msg, "root": root})
        elif self.path == "/api/undo":
            ok, msg = undo_last()
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/redo":
            ok, msg = redo_last()
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/save_tree":
            ok, msg = save_tree(body.get("root"), body.get("file"), body.get("id"),
                                body.get("default"), body.get("country_raw"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/equip_save":
            ok, msg = save_equipment(body.get("root"), body.get("file"), body.get("id"),
                                     body.get("raw") or "", body.get("name") or "",
                                     body.get("desc") or "", body.get("name_ja") or "",
                                     body.get("desc_ja") or "", body.get("props") or {},
                                     body.get("name_en") or "", body.get("desc_en") or "",
                                     body.get("picture") or "")
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/tech_save":
            ok, msg = save_tech(body.get("root"), body.get("file"), body.get("id"),
                                body.get("raw") or "", body.get("name") or "",
                                body.get("desc") or "", body.get("name_ja") or "",
                                body.get("desc_ja") or "", body.get("props") or {},
                                body.get("name_en") or "", body.get("desc_en") or "")
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/tech_link":
            ok, msg = tech_link(body.get("root"), body.get("file"),
                                body.get("source"), body.get("target"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/tech_add":
            ok, msg = add_tech(body.get("root"), body.get("id"),
                               body.get("folder") or "", body.get("year") or "1936")
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/tech_delete":
            ok, msg = delete_tech(body.get("root"), body.get("file"), body.get("id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/event_save":
            ok, msg = save_event(body.get("root"), body.get("file"), body.get("id"),
                                 body.get("raw") or "", body.get("title") or "",
                                 body.get("desc") or "", body.get("title_ja") or "",
                                 body.get("desc_ja") or "", body.get("title_en") or "",
                                 body.get("desc_en") or "", body.get("options") or [],
                                 body.get("trigger_raw") or "", body.get("immediate_raw") or "",
                                 body.get("picture") or "")
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/equip_add":
            ok, msg = add_equipment(body.get("root"), body.get("id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/equip_delete":
            ok, msg = delete_equipment(body.get("root"), body.get("file"), body.get("id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/ai_config":
            ok, msg = save_ai(body)
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/ai_test":
            cfg = load_ai_config()
            t0 = time.time()
            ok, msg = ai_chat(cfg, "ping，只回复 ok", "")
            self._send({"ok": ok, "msg": (msg or "")[:200],
                        "ms": int((time.time() - t0) * 1000)})
        elif self.path == "/api/ai_chat":
            ok, msg = ai_chat(load_ai(), body.get("prompt") or "", body.get("context") or "")
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/shared_add":
            ok, msg = add_shared_focus(body.get("root"), body.get("id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/shared_delete":
            ok, msg = delete_shared_focus(body.get("root"), body.get("file"), body.get("id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/event_add":
            ok, msg = add_event(body.get("root"), body.get("id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/event_delete":
            ok, msg = delete_event(body.get("root"), body.get("file"), body.get("id"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/restore_backup":
            ok, msg = restore_backup(body.get("root"), body.get("file"), int(body.get("index", -1)))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/unload_mod":
            ok, msg = unload_mod(body.get("root"))
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/repair_braces":
            ok, msg = repair_file_braces(body.get("file") or "")
            self._send({"ok": ok, "msg": msg})
        elif self.path == "/api/repair_all":
            ok, msg = repair_all_braces()
            self._send({"ok": ok, "msg": msg})
        else:
            self._send({"err": "not found"}, 404)

def detect_mods():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        d = filedialog.askdirectory(title="选择 mod 根目录（含 descriptor.mod 的那一层）")
        root.destroy()
        return [d] if d else []
    except Exception as e:
        print("图形选择失败:", e)
        return []

def fs_list(path):
    path = (path or "").strip()
    if path:
        path = os.path.abspath(path)
    if not path or not os.path.isdir(path):
        drives = []
        for c in string.ascii_uppercase:
            d = c + ":\\"
            if os.path.isdir(d):
                drives.append({"name": c + ":", "path": d, "has_mod": False})
        return {"path": "", "parent": "", "dirs": drives}
    dirs = []
    try:
        with os.scandir(path) as it:
            for e in sorted(it, key=lambda x: x.name.lower()):
                if not e.is_dir():
                    continue
                p = e.path
                has = os.path.exists(os.path.join(p, "descriptor.mod")) or \
                      os.path.isdir(os.path.join(p, "common", "national_focus"))
                dirs.append({"name": e.name, "path": p, "has_mod": has})
    except Exception as ex:
        return {"path": path, "parent": "", "dirs": [], "error": str(ex)}
    parent = os.path.dirname(path.rstrip("\\/"))
    if parent == path.rstrip("\\/") or len(path.rstrip("\\/")) <= 2:
        parent = ""
    return {"path": path, "parent": parent, "dirs": dirs}

def mod_home():
    return os.path.join(os.path.expanduser("~"), "Documents", "Paradox Interactive", "Hearts of Iron IV", "mod")

def create_mod(base, mod_id, name, version="0.1.0", game_version="1.19.*",
               tree_id="", tag="", create_tree=True):
    if not re.match(r'^[A-Za-z0-9_]+$', mod_id or ""):
        return False, "模组文件夹名只能包含字母、数字、下划线"
    base = os.path.abspath(base or mod_home())
    if not os.path.isdir(base):
        try:
            os.makedirs(base)
        except Exception as e:
            return False, "无法创建目录: %s" % e
    root = os.path.join(base, mod_id)
    if os.path.exists(root):
        return False, "目标文件夹已存在: " + root
    if create_tree:
        if not re.match(r'^[A-Za-z0-9_]+$', tree_id or ""):
            return False, "国策树 ID 只能包含字母、数字、下划线"
        if not re.match(r'^[A-Z][A-Z0-9]{1,5}$', tag or ""):
            return False, "国家 TAG 格式不正确（例如 GER、UNI）"
    try:
        os.makedirs(root)
        desc = ['version="%s"' % version, 'tags={', '\t"Alternative History"', '}',
                'name="%s"' % name, 'supported_version="%s"' % game_version]
        io.open(os.path.join(root, "descriptor.mod"), "w", encoding="utf-8", newline="").write("\r\n".join(desc) + "\r\n")
        # 启动器 .mod 文件
        if os.path.abspath(base) == os.path.abspath(mod_home()):
            launcher = "\r\n".join(desc + ['path="%s"' % root.replace("\\", "/")]) + "\r\n"
            io.open(os.path.join(base, mod_id + ".mod"), "w", encoding="utf-8", newline="").write(launcher)
        if create_tree:
            nf = os.path.join(root, "common", "national_focus")
            os.makedirs(nf)
            tree = """focus_tree = {
	id = %s

	country = {
		factor = 0
		modifier = {
			add = 10
			tag = %s
		}
	}
	default = no

	focus = {
		id = %s_root
		icon = GFX_goal_generic_national_unity
		x = 0
		y = 0
		cost = 1
	}
}
""" % (tree_id, tag, tree_id)
            io.open(os.path.join(nf, "zz_%s_focus.txt" % mod_id), "w", encoding="utf-8", newline="").write(tree)
            for lang, header, text in (("simp_chinese", "l_simp_chinese", "新国策"), ("english", "l_english", "New Focus")):
                d = os.path.join(root, "localisation", lang, "replace")
                os.makedirs(d)
                io.open(os.path.join(d, "zz_%s_l_%s.yml" % (mod_id, lang)), "w",
                        encoding="utf-8", newline="").write(
                    "\ufeff%s:\r\n %s_root:0 \"%s\"\r\n" % (header, tree_id, text))
    except Exception as e:
        return False, "创建失败: %s" % e
    return True, "已创建模组: " + root

def load_mod_root(path):
    if not LOC:
        load_game_loc()
    path = os.path.abspath(path or "")
    if not os.path.isdir(path):
        return False, "目录不存在"
    has_nf = os.path.isdir(os.path.join(path, "common", "national_focus"))
    has_desc = os.path.exists(os.path.join(path, "descriptor.mod"))
    if not (has_nf or has_desc):
        return False, "不是 mod 根目录（缺少 descriptor.mod 或 common/national_focus）"
    if path in ROOTS:
        return False, "这个目录已经加载过了"
    ROOTS.append(path)
    n = load_mod(path)
    link_countries()
    try:
        build_icons(ROOTS, GAME)
    except Exception as e:
        print("图标构建失败:", e)
    return True, "已加载 %s（%d 棵树）" % (os.path.basename(path), n)

def main():
    global GAME
    ap = argparse.ArgumentParser()
    ap.add_argument("--mod", action="append", default=None)
    ap.add_argument("--game", default=DEFAULT_GAME)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    GAME = args.game
    roots = args.mod or []   # 不带参数：先打开页面，再在页面里选择 mod
    load_game_loc()
    total = 0
    for r in roots:
        r = os.path.abspath(r)
        if r not in ROOTS:
            ROOTS.append(r)
            total += load_mod(r)
    link_countries()
    if ROOTS:
        build_icons(ROOTS, GAME)
    else:
        print("未指定 mod：启动后请在网页里选择 mod 文件夹")
    print("已加载 mod:", len(ROOTS), " 树:", total)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = "http://127.0.0.1:%d/" % args.port
    print("打开:", url)
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    server.serve_forever()

if __name__ == "__main__":
    main()
