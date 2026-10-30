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
import io, os, re, json, zipfile, shutil, time, argparse, threading, webbrowser, sys, string, hashlib, colorsys, zlib
import subprocess
import urllib.request, urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import editor_i18n as i18n

FROZEN = getattr(sys, "frozen", False)
_HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.dirname(_HERE) if os.path.basename(_HERE).lower() == "work" else _HERE

# 版本号：打包时由 make_release.py 生成 _build_version.py 注入；源码运行则回退到 git tag
def _read_app_version():
    """打包时 make_release.py 生成 _version.txt 并用 --add-data 塞进 exe；
    源码运行时读同目录的文件，都没有则回退到 git tag。"""
    for _b in (getattr(sys, "_MEIPASS", ""), _HERE, os.getcwd()):
        try:
            _p = os.path.join(_b, "_version.txt") if _b else ""
            if _p and os.path.exists(_p):
                v = io.open(_p, encoding="utf-8").read().strip()
                if v:
                    return v
        except Exception:
            pass
    try:
        import subprocess as _sp
        return (_sp.run(["git", "describe", "--tags", "--abbrev=0"], cwd=_HERE,
                        capture_output=True, text=True, timeout=3).stdout.strip().lstrip("v")) or "dev"
    except Exception:
        return "dev"


APP_VERSION = _read_app_version()

REPO = "XueRongHua123/xuerong-editor"
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
def _strip_keep_len(text):
    """去注释但**保持字符长度不变**：注释内容替换成空格。

    需要「在去注释文本里定位、再回到原文改写」的场景必须用它，
    否则 strip_comments 截断注释会让偏移全错。"""
    out = []
    for line in text.splitlines(True):
        buf, instr, hit = [], False, False
        for c in line:
            if c == '"':
                instr = not instr
            if c == '#' and not instr:
                hit = True
            buf.append(' ' if (hit and c not in '\r\n') else c)
        out.append("".join(buf))
    return "".join(out)


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

def _layer_dirs(sub, root):
    """某类资源在叠加链里的目录列表（子 mod 在前，便于后加载覆盖前）。

    老的 loader 都是「扫 root 下一个目录」，加载纯 submod 时父 mod 的同类文件读不到。
    全部改用它之后，即使 ROOTS 只有 submod，也能沿 mod_layers 读到父 mod 与原版。"""
    out = []
    seen = set()
    for base in reversed(mod_layers(root) or []):
        if not base:
            continue
        d = os.path.join(base, sub.replace("/", os.sep))
        if not os.path.isdir(d):
            continue
        ab = os.path.abspath(d)
        if ab in seen:
            continue
        seen.add(ab)
        out.append((base, d))
    return out


def load_mod(root):
    root = os.path.abspath(root)
    name = os.path.basename(root.rstrip("\\/")) or root
    count = 0
    _nf_pairs = []
    for _b, _d in _layer_dirs("common/national_focus", root):
        _src = os.path.basename(_b.rstrip("\\/")) or _b
        for _f in (sorted(f for f in os.listdir(_d) if f.endswith(".txt")) if os.path.isdir(_d) else []):
            _nf_pairs.append((_src, _d, _f))
    for name, nf, fn in _nf_pairs:
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
    # 逐层加载会把 load_states / load_countries 这类内部已经走 _layer_files 的
    # 函数重复执行（它们每次都处理整条链），州数会从 818 涨到 1081。
    # 所以这里保持只遍历 ROOTS；「父 mod 的 ideas/techs/equipment 读不到」这件事
    # 记在 BACKLOG，等把这批 loader 改成走 _layer_files 之后再统一改。
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
    n = 0
    for base, d in _layer_dirs("common/ideas", root):
        src = os.path.basename(base.rstrip("\\/")) or base
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            rel = os.path.join("common", "ideas", fn)
            try:
                raw = io.open(os.path.join(d, fn), encoding="utf-8",
                              errors="replace", newline="").read()
            except Exception:
                continue
            text = strip_comments(raw)
            for _s, _e, body in find_blocks(text, "ideas"):
                for k, v, b in top_items(body):
                    if not b:
                        continue
                    if _looks_like_idea(v):
                        _add_idea(k, v, rel, src); n += 1
                    else:
                        for k2, v2, b2 in top_items(v):
                            if b2 and _looks_like_idea(v2):
                                _add_idea(k2, v2, rel, src); n += 1
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

def _log_loc(ln):
    """从一行日志里抠出「文件 + 行号」。HOI4 常见两种写法：
        ... in file events/xxx.txt line 42
        ... at events/xxx.txt:42
    引擎自己的 cpp 位置（script_persistent.cpp:123）不是 mod 文件，忽略。"""
    m = re.search(r'in file\s+"?([\w./\\-]+\.(?:txt|yml|gfx|gui))"?\s+line\s+(\d+)', ln, re.I)
    if not m:
        m = re.search(r'([\w./\\-]+\.(?:txt|yml|gfx|gui)):(\d+)', ln)
    if m:
        return {"file": m.group(1).replace(chr(92), "/"), "line": int(m.group(2))}
    return None


def error_log(limit=120):
    """返回错误行 + 每行解析出的文件位置（用于跳转）"""
    p = os.path.join(os.path.expanduser("~"), "Documents", "Paradox Interactive",
                     "Hearts of Iron IV", "logs", "error.log")
    items = []
    if os.path.exists(p):
        try:
            raw = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
            keep = [(i, ln) for i, ln in enumerate(raw, 1)
                    if re.search(r'focus|national_focus|idea|mod/|Error', ln, re.I)]
            for i, ln in keep[-limit:]:
                items.append({"n": i, "text": ln, "loc": _log_loc(ln)})
        except Exception as e:
            items = [{"n": 0, "text": "读取失败: %s" % e, "loc": None}]
    return {"path": p, "items": items,
            "lines": [x["text"] for x in items],
            "withLoc": sum(1 for x in items if x.get("loc"))}


def file_excerpt(rel, line, root=None, span=6):
    """取某个文件第 line 行前后 span 行，供日志跳转预览"""
    rel = (rel or "").replace(chr(92), "/").strip("/")
    if not rel:
        return {"ok": False, "msg": "没有文件路径"}
    cands = []
    for base in mod_layers(_map_pick(root)) or [GAME]:
        if base:
            cands.append(os.path.join(base, rel.replace("/", os.sep)))
    for c in cands:
        if os.path.exists(c):
            try:
                lines = io.open(c, encoding="utf-8-sig", errors="replace").read().splitlines()
            except Exception as e:
                return {"ok": False, "msg": "读取失败：%s" % e}
            line = max(1, min(int(line or 1), len(lines) or 1))
            a = max(0, line - 1 - span)
            b = min(len(lines), line + span)
            return {"ok": True, "file": rel, "line": line, "total": len(lines),
                    "from": a + 1, "to": b, "path": c,
                    "excerpt": [{"n": a + i + 1, "text": lines[a + i],
                                 "hit": (a + i + 1) == line} for i in range(b - a)]}
    return {"ok": False, "msg": "在任何 mod 层与原版里都找不到 %s" % rel}

def load_equipment(root):
    name = os.path.basename(root.rstrip("\\/")) or root
    n = 0
    for base, d in _layer_dirs("common/units/equipment", root):
      name = os.path.basename(base.rstrip("\\/")) or base
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
    n = 0
    _tech_files = []
    for _b, _d in _layer_dirs("common/technologies", root):
        if not os.path.isdir(_d):
            continue
        for _f in sorted(f for f in os.listdir(_d) if f.endswith(".txt")):
            _tech_files.append((_d, _f))
    for d, fn in _tech_files:
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
    """同一个 tag/state 谁说了算。

    HOI4 语义：后加载的覆盖先加载的。所以：
      1. 没有记录 → 收
      2. 现有记录来自原版 → 覆盖（原版是只读参考层）
      3. 现有记录来自同一层 → 覆盖（重复加载要幂等）
      4. 都在叠加链里 → 位置更靠后的优先
      5. 现有记录的层不在链里（游离目录）→ 覆盖

    原来只判断「现有是否来自原版」，导致父 mod 的记录挡住了子 mod，
    加载 submod 时它的州文件永远被跳过、state_save 会报「州文件不存在」。"""
    if not existing:
        return True
    old_root = existing.get("root", "") or ""
    # 原版记录可以被任何 mod 覆盖
    if is_under_game(old_root):
        return True
    # 原版不能覆盖 mod 记录（mod_layers(GAME) 只有一层，index 会抛错并误判为可覆盖）
    if is_under_game(root):
        return False
    if os.path.abspath(old_root) == os.path.abspath(root or ""):
        return True
    # 两个都是 mod：按 ROOTS 展开的完整叠加链判断谁更靠后
    bases = []
    for _r in (ROOTS or []):
        for _b in (mod_layers(_r) or [_r]):
            if _b and os.path.abspath(_b) not in [os.path.abspath(x) for x in bases]:
                bases.append(_b)
    try:
        return bases.index(os.path.abspath(root or "")) >= bases.index(os.path.abspath(old_root))
    except ValueError:
        return True


def _read_text(path):
    return strip_comments(io.open(path, encoding="utf-8-sig", errors="replace").read())


def load_countries(root):
    """common/country_tags + common/countries + history/countries"""
    root = os.path.abspath(root)
    name = os.path.basename(root.rstrip("\\/")) or root

    _layers_c = mod_layers(root)
    tag_files, _tag_replaced = _layer_files("common/country_tags", _layers_c)
    for path in tag_files:
        fn = os.path.basename(path)
        rel = os.path.join("common", "country_tags", fn)
        for m in re.finditer(r'(?m)^\s*([A-Z0-9]{2,4})\s*=\s*"([^"]+)"', _read_text(path)):
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
    # mod 的覆盖文件可能只写 graphical_culture 而没有 color，这时要继续往原版找
    for tag, c in list(COUNTRIES.items()):
        if c.get("source") != name:
            continue
        rel = (c.get("def_file") or "").replace("/", os.sep)
        for base in (root, GAME):
            p = os.path.join(base, "common", rel) if rel else ""
            if not (p and os.path.exists(p)):
                continue
            text = _read_text(p)
            if not c.get("has_def"):
                c["has_def"] = True
                c["def_path"] = p
                c["graphical_culture"] = _first(text, r'(?m)^\s*graphical_culture\s*=\s*(\w+)')
            cm = re.search(r'(?m)^\s*color\s*=\s*(rgb|hsv)?\s*\{?\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)', text)
            if cm:
                mode = (cm.group(1) or "").lower()
                a, b2, c3 = float(cm.group(2)), float(cm.group(3)), float(cm.group(4))
                if mode == "hsv":
                    r, g, bl = colorsys.hsv_to_rgb(a, b2, c3)
                    c["color"] = [round(r, 4), round(g, 4), round(bl, 4)]
                else:
                    rgb = [a, b2, c3]
                    if max(rgb) > 1.0:
                        rgb = [round(v / 255.0, 4) for v in rgb]
                    c["color"] = rgb
                c["color_from"] = p
                break

    # 没写 color 的国家：按 tag 派生一个稳定色（游戏里也用引擎兜底色，这里保证不灰、不撞色）
    for tag, c in list(COUNTRIES.items()):
        if c.get("source") != name or c.get("color"):
            continue
        try:
            hue = (zlib.crc32(tag.encode("utf-8")) % 1000) / 1000.0
            r, g, b = colorsys.hsv_to_rgb(hue, 0.45, 0.78)
            c["color"] = [round(r, 4), round(g, 4), round(b, 4)]
            c["color_derived"] = True
        except Exception:
            c["color"] = [0.52, 0.52, 0.52]
            c["color_derived"] = True

    # 开局历史
    _hist_pairs = []
    for _b, _d in _layer_dirs("history/countries", root):
        for _f in sorted(f for f in os.listdir(_d) if f.endswith(".txt")):
            _hist_pairs.append((_b, _d, _f))
    for _hb, d, fn in _hist_pairs:
        if True:
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


START_DATE = (1936, 1, 1)      # 开局日期，load 时从 bookmarks 刷新
START_DATE_TEXT = "1936.1.1"


_START_DATE_CACHE = {}


def _start_date_for(root):
    """读某个 mod（或原版）的 bookmarks 得到开局日期；读不到回退 1936.1.1"""
    key = os.path.abspath(root or "")
    if key in _START_DATE_CACHE:
        return _START_DATE_CACHE[key]
    dates = []
    for base in (root, GAME):
        d = os.path.join(base or "", "common", "bookmarks")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = _read_text(os.path.join(d, fn))
            except Exception:
                continue
            for m in re.finditer(r'(?m)^[ \t]*date\s*=\s*"?(\d{4})\.(\d{1,2})\.(\d{1,2})', text):
                dates.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
        if dates:
            break
    val = min(dates) if dates else (1936, 1, 1)
    _START_DATE_CACHE[key] = val
    print("开局日期 %s -> %d.%d.%d" % (os.path.basename(key), val[0], val[1], val[2]))
    return val


def refresh_start_date(roots):
    """从 bookmarks 找最早的开局日期（mod 常用 1999.8.7 这种）"""
    global START_DATE, START_DATE_TEXT
    dates = []
    for base in list(roots) + [GAME]:
        d = os.path.join(base or "", "common", "bookmarks")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = _read_text(os.path.join(d, fn))
            except Exception:
                continue
            for m in re.finditer(r'(?m)^[ \t]*date\s*=\s*"?(\d{4})\.(\d{1,2})\.(\d{1,2})', text):
                dates.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    if dates:
        START_DATE = min(dates)
        START_DATE_TEXT = "%d.%d.%d" % START_DATE
    return START_DATE


def _state_owner_effective(body, hb, he, dep, start=None):
    """按游戏语义取生效的 owner：日期块（<= 开局，最晚者）优先，否则 history 里的直接子级"""
    owner = ""
    if hb > 0:
        dated = []
        for m in re.finditer(r'(?m)^[ \t]*(\d{4})\.(\d{1,2})\.(\d{1,2})\s*=\s*\{', body[hb:he]):
            bpos = body.find('{', hb + m.end() - 1)
            epos = brace_match(body, bpos)
            if epos <= bpos:
                continue
            dm = re.search(r'(?m)^[ \t]*owner\s*=\s*([A-Z0-9]{2,4})', body[bpos + 1:epos - 1])
            if dm:
                dated.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), dm.group(1).strip()))
        dated.sort()
        _sd = start or START_DATE
        eff = [d for d in dated if (d[0], d[1], d[2]) <= _sd]
        if eff:
            owner = eff[-1][3]
        if not owner:
            for m in re.finditer(r'(?m)^[ \t]*owner\s*=\s*([A-Z0-9]{2,4})', body[hb:he]):
                pos = hb + m.start()
                if pos < len(dep) and dep[pos] == 1:
                    owner = m.group(1).strip()
                    break
    if not owner:
        for m in re.finditer(r'(?m)^[ \t]*owner\s*=\s*([A-Z0-9]{2,4})', body):
            pos = m.start()
            if pos < len(dep) and dep[pos] == 0:
                owner = m.group(1).strip()
                break
    return owner


def load_states(root):
    """history/states：id / 名称 / 人力 / 类别 / owner / cores / 省份 / 建筑 / 胜利点"""
    root = os.path.abspath(root)
    name = os.path.basename(root.rstrip("\\/")) or root
    layers = mod_layers(root)
    files, _replaced = _layer_files("history/states", layers)
    if not files:
        return 0
    n = 0
    _start = _start_date_for(root)
    for path in files:
        fn = os.path.basename(path)
        rel = os.path.join("history", "states", fn)
        # 文件来自叠加链的哪一层：必须按实际路径反推，不能一律用函数参数 root，
        # 否则原版的 1-France.txt 会被记成「子 mod 的文件」，state_save 就会报文件不存在。
        file_root = None
        _ap = os.path.abspath(path)
        for _b in (layers or []):
            if _b and _ap.startswith(os.path.abspath(_b) + os.sep):
                file_root = _b
                break
        if not file_root:
            continue
        src_name = os.path.basename(file_root.rstrip("\\/")) or file_root
        text = _read_text(path)
        for s, e, body in find_blocks(text, "state"):
            sid = _first(body, r'(?m)^\s*id\s*=\s*(-?\d+)')
            if not sid:
                continue
            sid = int(sid)
            cur = STATES.get(sid)
            if not _prefer(cur, file_root):
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

            owner = _state_owner_effective(body, hb, he, dep, _start)

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
                "id": sid, "file": rel, "root": file_root, "source": src_name,
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


# HOI4 1.19 的 state_category 全集（缺 large_town / city 会让这两类州保存失败）
STATE_CATEGORIES = ("wasteland", "enclave", "tiny_island", "small_island", "pastoral",
                    "rural", "town", "large_town", "city", "large_city",
                    "metropolis", "megalopolis")
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


def state_detail(sid, full=False):
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
        "provinces": s.get("provinces", []) if full else s.get("provinces", [])[:300],
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
    refresh_start_date(ROOTS)
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
            "capital": c.get("capital", ""),
            "political_power": c.get("political_power", ""),
            "ruling_party": c.get("ruling_party", ""),
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
    path = _out_read_path(path)          # 输出模式下读到的是「改过的版本」
    raw = io.open(path, "rb").read()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    return raw.decode("utf-8-sig", "replace"), has_bom


def _write_bom_text(path, text, has_bom):
    data = text.encode("utf-8")
    if has_bom:
        data = b"\xef\xbb\xbf" + data
    target = _out_path(path)             # 输出模式下写到 output/，源文件不动
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    io.open(target, "wb").write(data)


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


# v0.68 开局装备变体写入
def _variant_blocks(text):
    """返回 [(start, end, name, body)]，覆盖所有 create_equipment_variant 块"""
    out = []
    for m in re.finditer(r'(?m)^[ \t]*create_equipment_variant\s*=\s*\{', text):
        b = text.find('{', m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        nm = _first(body, r'(?m)^[ \t]*name\s*=\s*"?([^"\r\n]+)"?')
        out.append((m.start(), e, (nm or "").strip(), body))
    return out


def _hist_append_top(text, block):
    """把 block 插到最后一个顶层块之后（深度 0 处），保证不落进别的块里"""
    depth = 0
    last = 0
    for i, ch in enumerate(text):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                last = i + 1
    if last == 0:
        return text.rstrip() + "\n\n" + block + "\n"
    return text[:last] + "\n\n" + block + text[last:]


def country_variant_add(tag, spec):
    """新增一个开局变体：spec = {name, type, icon, modules:{slot:module}}"""
    name = (spec.get("name") or "").strip()
    etype = (spec.get("type") or "").strip()
    if not name:
        return {"ok": False, "msg": "变体名称不能为空"}
    if not re.match(r'^[A-Za-z0-9_\- ]{1,60}$', name):
        return {"ok": False, "msg": "名称只能用字母数字、空格、下划线和连字符"}
    if not etype:
        return {"ok": False, "msg": "请选择底盘（type）"}
    if not re.match(r'^[A-Za-z0-9_]+$', etype):
        return {"ok": False, "msg": "底盘 id 只能用字母数字下划线"}
    if EQUIPMENTS and etype not in EQUIPMENTS:
        return {"ok": False, "msg": "底盘 %s 不在装备列表里" % etype}
    mods = spec.get("modules") or {}
    if not isinstance(mods, dict) or not mods:
        return {"ok": False, "msg": "至少要填一个模块（槽位 = 模块）"}
    c, root, path = _hist_path(tag)
    if not path or is_under_game(root):
        return {"ok": False, "msg": "这个国家没有可写的历史文件"}
    text, has_bom = _read_bom_text(path)
    if any(n == name for (_, _, n, _) in _variant_blocks(text)):
        return {"ok": False, "msg": "已经有同名变体 %s" % name}
    lines = ['create_equipment_variant = {', '\tname = "%s"' % name, '\ttype = %s' % etype]
    icon = (spec.get("icon") or "").strip()
    if icon:
        lines.append('\ticon = %s' % icon)
    lines.append('\tmodules = {')
    for slot, mod in mods.items():
        if not re.match(r'^[A-Za-z0-9_]+$', str(slot)) or not re.match(r'^[A-Za-z0-9_]+$', str(mod)):
            return {"ok": False, "msg": "槽位/模块 id 只能用字母数字下划线：%s = %s" % (slot, mod)}
        lines.append('\t\t%s = %s' % (slot, mod))
    lines.append('\t}')
    lines.append('}')
    block = "\n".join(lines)
    new_text = _hist_append_top(text, block)
    snapshot(path)
    _write_bom_text(path, new_text, has_bom)
    CHANGED[path] = os.path.relpath(path, root)
    reload_data()
    link_countries()
    return {"ok": True, "msg": "已新增变体 %s（%d 个模块）" % (name, len(mods)),
            "variants": _hist_variants(_read_bom_text(path)[0])}


def country_variant_del(tag, name):
    """按 name 删除一个开局变体块"""
    name = (name or "").strip()
    if not name:
        return {"ok": False, "msg": "缺少变体名称"}
    c, root, path = _hist_path(tag)
    if not path or is_under_game(root):
        return {"ok": False, "msg": "这个国家没有可写的历史文件"}
    text, has_bom = _read_bom_text(path)
    target = None
    for (s, e, nm, body) in _variant_blocks(text):
        if nm == name:
            target = (s, e)
            break
    if not target:
        return {"ok": False, "msg": "找不到变体 %s" % name}
    s, e = target
    line_start = text.rfind("\n", 0, s)
    if line_start < 0:
        line_start = 0
    new_text = text[:line_start] + text[e:]
    snapshot(path)
    _write_bom_text(path, new_text, has_bom)
    CHANGED[path] = os.path.relpath(path, root)
    reload_data()
    link_countries()
    return {"ok": True, "msg": "已删除变体 %s" % name,
            "variants": _hist_variants(_read_bom_text(path)[0])}


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


# v0.66 全局 flag 配对
def _flag_usage():
    """扫描事件 / 国策原文 / 精神原文里的 set_global_flag 与 has_global_flag"""
    sets, haves = {}, {}

    def scan(raw, where):
        if not raw:
            return
        for m in re.finditer(r'set_global_flag\s*=\s*([A-Za-z0-9_]+)', raw):
            sets.setdefault(m.group(1), where)
        for m in re.finditer(r'(?:has_global_flag|clr_global_flag)\s*=\s*([A-Za-z0-9_]+)', raw):
            haves.setdefault(m.group(1), where)

    for eid, ev in EVENTS.items():
        scan(ev.get("raw", ""), "事件 " + eid)
    for iid, idea in IDEAS.items():
        scan(idea.get("raw", ""), "精神 " + iid)
    for root in ROOTS:
        d = os.path.join(root, "common", "national_focus")
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.endswith(".txt"):
                continue
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
            except Exception:
                continue
            scan(text, "国策 " + fn)
    return sets, haves


# v0.67 脚本检查：定义清单 + 全项目引用计数
LOGIC_WORDS = {"OR", "AND", "NOT", "NOR", "NAND", "XOR", "IF", "ELSE", "LIMIT", "ELSE_IF"}
SCRIPT_CACHE = {"stamp": None, "payload": None}


def _is_logic_word(name):
    return name in LOGIC_WORDS or (name.isupper() and len(name) <= 4)


def _scripted_defs():
    """只扫 mod 的 scripted_triggers / scripted_effects，只认顶格定义（支持中文名）"""
    out = []
    def_re = re.compile(r'(?m)^([^\W\d][\w]*)\s*=\s*\{')
    for root in ROOTS:
        if is_under_game(root):
            continue
        for kind, sub in (("trigger", "scripted_triggers"), ("effect", "scripted_effects")):
            d = os.path.join(root, "common", sub)
            if not os.path.isdir(d):
                continue
            for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
                try:
                    text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
                except Exception:
                    continue
                for m in def_re.finditer(text):
                    k = m.group(1)
                    if _is_logic_word(k) or k in ("scripted_triggers", "scripted_effects"):
                        continue
                    b = text.find('{', m.end() - 1)
                    e = brace_match(text, b)
                    body = text[b + 1:e - 1].strip() if e > b else ""
                    out.append({"kind": kind, "name": k, "file": fn, "empty": not body})
    return out


def _script_ref_counts(names):
    """全项目扫 `名字 =` 形式的键出现次数（含定义本身）"""
    counts = dict((n, 0) for n in names)
    if not names:
        return counts
    key_re = re.compile(r'(?<!\w)([^\W\d][\w]*)\s*=')
    for root in ROOTS:
        if is_under_game(root):
            continue
        for base in ("common", "events", "history"):
            base_dir = os.path.join(root, base)
            if not os.path.isdir(base_dir):
                continue
            for dirpath, _, files in os.walk(base_dir):
                for fn in files:
                    if not fn.endswith(".txt"):
                        continue
                    try:
                        text = strip_comments(io.open(os.path.join(dirpath, fn), encoding="utf-8",
                                                     errors="replace").read())
                    except Exception:
                        continue
                    for m in key_re.finditer(text):
                        n = m.group(1)
                        if n in counts:
                            counts[n] += 1
    return counts


def scripted_payload():
    """返回脚本清单（带缓存，数据变了才重扫）"""
    stamp = (tuple(ROOTS), len(TREES), len(EVENTS), len(IDEAS), len(TECHS))
    if SCRIPT_CACHE["stamp"] == stamp and SCRIPT_CACHE["payload"]:
        hit = dict(SCRIPT_CACHE["payload"])
        hit["cached"] = True
        return hit
    defs = _scripted_defs()
    counts = _script_ref_counts(set(d["name"] for d in defs))
    items = []
    for d in defs:
        items.append({"name": d["name"], "kind": d["kind"], "file": d["file"],
                      "refs": counts.get(d["name"], 0), "empty": d["empty"]})
    items.sort(key=lambda x: (x["refs"], x["name"]))
    unused = len([i for i in items if i["refs"] <= 1])
    payload = {"ok": True, "items": items, "total": len(items), "unused": unused, "cached": False}
    SCRIPT_CACHE["stamp"] = stamp
    SCRIPT_CACHE["payload"] = payload
    return payload


# v0.71 地图图层构建（Pillow，无需 numpy）
MAP_CACHE_DIR = os.path.join(WORK, "cache", "map")
MAP_ASSETS = ("base.png", "province.png", "edges.png", "state.png", "political.png", "political_strict.png", "region.png", "terrain.png", "continent.png", "prov_id.png", "rivers.png",
              "prov_index.json", "centers.json", "regions.json", "meta.json")


def _map_files(root):
    """沿叠加链找地图（子 mod → 父 mod → 原版），返回 (bmp, csv, 提供者)"""
    if root:
        b, d, provider, _layers = _map_files_layered(root)
        if b and d:
            return b, d, (provider or root)
    if GAME:
        b = os.path.join(GAME, "map", "provinces.bmp")
        d = os.path.join(GAME, "map", "definition.csv")
        if os.path.exists(b) and os.path.exists(d):
            return b, d, GAME
    return None, None, None


def _dir_mtime(p):
    """目录下所有 .txt 的最大 mtime（文件内容变动也会反映出来）"""
    if not os.path.isdir(p):
        return 0
    mt = 0
    try:
        for fn in os.listdir(p):
            if fn.endswith(".txt"):
                try:
                    mt = max(mt, int(os.path.getmtime(os.path.join(p, fn))))
                except Exception:
                    pass
    except Exception:
        pass
    return mt


def _map_key(root):
    """缓存键必须覆盖所有会影响图层的输入：
    省位图、definition.csv、州 history、战略区定义。
    少一项就会出现"改了数据但地图没变"的错觉。"""
    b, d, base = _map_files(root)
    if not b:
        return None, None
    layers = mod_layers(root)
    layer_sig = "|".join("%s:%d:%d" % (os.path.abspath(x), _dir_mtime(os.path.join(x, "history", "states")),
                                       _dir_mtime(os.path.join(x, "map", "strategicregions")))
                         for x in layers)
    key = "%s|%d|%d|%d|%s" % (
        os.path.abspath(base), os.path.getmtime(b), os.path.getsize(b), os.path.getmtime(d), layer_sig)
    return key, base


def _map_dir(root):
    key, base = _map_key(root)
    if not key:
        return None, None, None
    return os.path.join(MAP_CACHE_DIR, hashlib.md5(key.encode("utf-8")).hexdigest()[:12]), key, base


# v0.73 地图多来源
# -*- coding: utf-8 -*-
"""更新检查：查 GitHub 最新 Release，与本地版本比较。

设计要点：
- 只查一次 /releases/latest，GitHub 未认证配额 60 次/小时，缓存 6 小时后足够
- 任何网络失败都静默返回「检查不了」，不打扰用户
- 版本比较按数字段，忽略前缀 v 与后缀
"""
import json
import os
import re
import time

UPDATE_CACHE = os.path.join(WORK, "cache", "update.json")
UPDATE_TTL = 6 * 3600          # 6 小时内不重复请求
UPDATE_STATE = {"last": 0, "result": None}


def _ver_tuple(v):
    """1.2.3 → (1,2,3)；解析不出来的段按 0"""
    parts = re.findall(r"\d+", str(v or ""))
    return tuple(int(x) for x in parts[:4]) if parts else (0,)


def _ver_newer(a, b):
    ta, tb = _ver_tuple(a), _ver_tuple(b)
    n = max(len(ta), len(tb))
    ta = ta + (0,) * (n - len(ta))
    tb = tb + (0,) * (n - len(tb))
    return ta > tb


def check_update(force=False, timeout=6):
    """返回 {ok, current, latest, newer, url, notes, published, checked, msg}"""
    now = time.time()
    if not force:
        # 内存缓存
        if UPDATE_STATE["result"] and now - UPDATE_STATE["last"] < UPDATE_TTL:
            return dict(UPDATE_STATE["result"])
        # 磁盘缓存
        try:
            if os.path.exists(UPDATE_CACHE) and now - os.path.getmtime(UPDATE_CACHE) < UPDATE_TTL:
                cached = json.loads(io.open(UPDATE_CACHE, encoding="utf-8").read())
                UPDATE_STATE["result"] = cached
                UPDATE_STATE["last"] = os.path.getmtime(UPDATE_CACHE)
                return dict(cached)
        except Exception:
            pass

    out = {"ok": False, "current": APP_VERSION, "latest": "", "newer": False,
           "url": "https://github.com/%s/releases/latest" % REPO,
           "notes": "", "published": "", "checked": time.strftime("%Y-%m-%d %H:%M:%S"),
           "msg": ""}
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/%s/releases/latest" % REPO,
            headers={"User-Agent": "xuerong-editor/%s" % APP_VERSION,
                     "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
        out["ok"] = True
        out["latest"] = (d.get("tag_name") or "").lstrip("v")
        out["url"] = d.get("html_url") or out["url"]
        out["published"] = (d.get("published_at") or "")[:10]
        body = d.get("body") or ""
        out["notes"] = body[:1200]
        out["assets"] = [{"name": a.get("name"), "size": a.get("size"),
                          "url": a.get("browser_download_url")}
                         for a in (d.get("assets") or [])]
        out["newer"] = _ver_newer(out["latest"], APP_VERSION)
    except Exception as e:
        out["msg"] = "检查失败：%s" % str(e)[:120]

    try:
        os.makedirs(os.path.dirname(UPDATE_CACHE), exist_ok=True)
        io.open(UPDATE_CACHE, "w", encoding="utf-8", newline="").write(json.dumps(out, ensure_ascii=False))
    except Exception:
        pass
    UPDATE_STATE["result"] = out
    UPDATE_STATE["last"] = now
    return out


def app_info():
    return {"version": APP_VERSION, "repo": REPO, "frozen": FROZEN,
            "exe": sys.executable if FROZEN else ""}


# v1.0.3 一键更新
UPDATE_PKG_DIR = os.path.join(WORK, "cache", "update_pkg")


def update_download(asset_url=None, expect_size=0, timeout=180):
    """下载新版 exe 到缓存目录并校验（MZ 头 + 体积）。返回 {ok, path, size, msg}"""
    if not asset_url:
        info = check_update(force=True)
        exe_asset = None
        for a in (info.get("assets") or []):
            if str(a.get("name") or "").lower().endswith(".exe"):
                exe_asset = a
                break
        if not exe_asset:
            return {"ok": False, "msg": "最新版本里没有 exe 附件"}
        asset_url = exe_asset["url"]
        expect_size = exe_asset.get("size") or 0
    try:
        os.makedirs(UPDATE_PKG_DIR, exist_ok=True)
        dst = os.path.join(UPDATE_PKG_DIR, "xuerong_new.exe")
        tmp = dst + ".part"
        req = urllib.request.Request(asset_url, headers={"User-Agent": "xuerong-editor/%s" % APP_VERSION})
        got = 0
        with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if got > 300 * 1024 * 1024:
                    return {"ok": False, "msg": "下载体积异常，已中止"}
        size = os.path.getsize(tmp)
        with open(tmp, "rb") as f:
            magic = f.read(2)
        if magic != b"MZ":
            os.remove(tmp)
            return {"ok": False, "msg": "下载到的不是 exe（缺少 MZ 头）"}
        if expect_size and abs(size - int(expect_size)) > 2048:
            os.remove(tmp)
            return {"ok": False, "msg": "体积不符（期望 %d，实际 %d）" % (int(expect_size), size)}
        os.replace(tmp, dst)
        return {"ok": True, "path": dst, "size": size,
                "msg": "已下载 %.1f MB，校验通过" % (size / 1048576)}
    except Exception as e:
        return {"ok": False, "msg": "下载失败：%s" % str(e)[:160]}


def update_apply(launch=False):
    """把新版 zip 解压到 exe 旁边的独立目录，不改动正在运行的文件。
    零风险：解压失败不影响当前版本；用户从新目录启动即可。"""
    info = check_update(force=True)
    latest = info.get("latest") or ""
    zip_asset = None
    for a in (info.get("assets") or []):
        if str(a.get("name") or "").lower().endswith(".zip"):
            zip_asset = a
            break
    if not zip_asset:
        return {"ok": False, "msg": "最新版本里没有 zip 附件，请到 Release 页手动下载"}

    base_dir = os.path.dirname(sys.executable) if FROZEN else WORK
    out_dir = os.path.join(base_dir, "_update_%s" % (latest or "latest"))
    try:
        os.makedirs(os.path.dirname(out_dir), exist_ok=True)
    except Exception:
        pass

    zpath = os.path.join(UPDATE_PKG_DIR, "update.zip")
    try:
        os.makedirs(UPDATE_PKG_DIR, exist_ok=True)
        req = urllib.request.Request(zip_asset["url"],
                                     headers={"User-Agent": "xuerong-editor/%s" % APP_VERSION})
        got = 0
        with urllib.request.urlopen(req, timeout=300) as r, open(zpath, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
        if got < 1024 * 1024:
            return {"ok": False, "msg": "下载不完整（%.1f KB）" % (got / 1024)}
    except Exception as e:
        return {"ok": False, "msg": "下载失败：%s" % str(e)[:160]}

    try:
        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir, ignore_errors=True)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(out_dir)
        # zip 里通常多一层同名目录，找到真正的 exe
        real_exe = None
        for dp, _dn, fs in os.walk(out_dir):
            for fn in fs:
                if fn.lower().endswith(".exe"):
                    real_exe = os.path.join(dp, fn)
                    break
            if real_exe:
                break
        if not real_exe:
            return {"ok": False, "msg": "解压后没找到 exe"}
        if launch:
            try:
                os.startfile(os.path.dirname(real_exe))      # 打开所在文件夹
            except Exception:
                pass
        return {"ok": True, "version": latest, "dir": out_dir, "exe": real_exe,
                "size": round(got / 1048576, 1),
                "msg": "新版已解压到：%s（当前窗口可以关闭，从新目录启动即可，旧版本不改动）"
                       % os.path.dirname(real_exe)}
    except Exception as e:
        return {"ok": False, "msg": "解压失败：%s" % str(e)[:160]}


def _csv_path_for(root):
    layers = mod_layers(root)
    csvp, prov = _layers_find("map/definition.csv", layers)
    return csvp, prov


def _save_point_undo(bmp, changes):
    """把「像素索引 → 原 RGB」存成紧凑二进制（4 字节索引 + 3 字节 RGB）。

    散布型改动（十字交叉修复）用包围盒备份会长到几十 MB，实际只改了几百个像素。"""
    import struct
    os.makedirs(MAP_UNDO_DIR, exist_ok=True)
    seq = int(time.time() * 1000)
    fn = os.path.join(MAP_UNDO_DIR, "pt%d.bin" % seq)
    buf = bytearray()
    buf += struct.pack("<I", len(changes))
    for idx, rgb in changes:
        buf += struct.pack("<I", idx)
        buf += bytes((rgb[0], rgb[1], rgb[2]))
    io.open(fn, "wb").write(bytes(buf))
    return fn


def _load_point_undo(fn):
    """读回点级备份 → [(idx, (r,g,b)), ...]"""
    import struct
    raw = io.open(fn, "rb").read()
    if len(raw) < 4:
        return []
    n = struct.unpack("<I", raw[:4])[0]
    out = []
    off = 4
    for _ in range(n):
        if off + 7 > len(raw):
            break
        idx = struct.unpack("<I", raw[off:off + 4])[0]
        r, g, b = raw[off + 4], raw[off + 5], raw[off + 6]
        out.append((idx, (r, g, b)))
        off += 7
    return out


def _apply_point_undo(entry):
    """把点级备份写回 bmp（按行分组批量写，减少 IO）"""
    bmp = entry.get("bmp")
    pts = _load_point_undo(entry.get("file") or "")
    if not bmp or not pts:
        return 0
    info = bmp_info(bmp)
    if not info:
        return 0
    w, h = info["w"], info["h"]
    # 按包围盒一次读、逐点改、一次写
    xs = [i % w for i, _ in pts]
    ys = [i // w for i, _ in pts]
    bx, by = min(xs), min(ys)
    bw, bh = max(xs) - bx + 1, max(ys) - by + 1
    rect = bmp_read_rect(bmp, bx, by, bw, bh)
    if rect is None:
        return 0
    for idx, rgb in pts:
        o = (idx // w - by) * bw + (idx % w - bx)
        if 0 <= o < len(rect):
            rect[o] = rgb
    bmp_write_rect(bmp, bx, by, bw, bh, rect)
    return len(pts)


def _scan_cross(allpx, w, h):
    """找出所有 2x2 十字模式：左上==右下 且 右上==左下 且 A!=B。返回 [(x, y, A, B)]"""
    out = []
    for y in range(h - 1):
        base = y * w
        nxt = base + w
        for x in range(w - 1):
            a = allpx[base + x]
            b = allpx[base + x + 1]
            c = allpx[nxt + x]
            d = allpx[nxt + x + 1]
            if a == d and b == c and a != b:
                out.append((x, y, a, b))
    return out


_REFINE_IDS_CACHE = {}


def _refine_load_ids(root):
    """载入 省号数组（按 provinces.bmp + definition.csv 的 mtime 缓存）"""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    layers = mod_layers(root)
    bmp, _ = _layers_find("map/provinces.bmp", layers)
    csvp, _ = _layers_find("map/definition.csv", layers)
    if not bmp or not csvp:
        return None, 0, 0
    key = (bmp, os.path.getmtime(bmp), csvp, os.path.getmtime(csvp))
    hit = _REFINE_IDS_CACHE.get("cur")
    if hit and hit[0] == key:
        return hit[1], hit[2], hit[3]
    with Image.open(bmp) as im:
        w, h = im.size
        raw = im.convert("RGB").tobytes()
    rgb2pid = {}
    with io.open(csvp, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.strip().split(";")
            if len(p) >= 8 and p[0].isdigit():
                rgb2pid[(int(p[1]), int(p[2]), int(p[3]))] = int(p[0])
    ids = [0] * (w * h)
    for i in range(w * h):
        ids[i] = rgb2pid.get((raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2]), 0)
    _REFINE_IDS_CACHE["cur"] = (key, ids, w, h)
    return ids, w, h


def _refine_grow_units(unit_ids, neighbors, k, coord=None):
    """通用水位生长：把一组单元分成 k 组，每组尽量等量，组内连通。

    unit_ids: 单元 id 列表
    neighbors: {unit_id: [相邻 unit_id, ...]}
    k: 分成几组
    coord: {unit_id: (x, y)} —— 用于选种子；缺省则按 unit_ids 顺序取

    返回 {group_i: [unit_id, ...]}
    """
    from collections import deque
    units = list(unit_ids)
    if not units:
        return {}
    k = max(1, min(k, len(units)))
    c = coord or {u: (i, 0) for i, u in enumerate(units)}

    # 最远点采样选种子
    cx = sum(c[u][0] for u in units) / len(units)
    cy = sum(c[u][1] for u in units) / len(units)
    first = min(units, key=lambda u: (c[u][0] - cx) ** 2 + (c[u][1] - cy) ** 2)
    seeds = [first]
    dist = {u: (c[u][0] - c[first][0]) ** 2 + (c[u][1] - c[first][1]) ** 2 for u in units}
    guard = 0
    while len(seeds) < k and guard < 2000:
        guard += 1
        nxt = max(dist, key=dist.get)
        if dist[nxt] <= 0:
            break
        seeds.append(nxt)
        for u in units:
            d = (c[u][0] - c[nxt][0]) ** 2 + (c[u][1] - c[nxt][1]) ** 2
            if d < dist[u]:
                dist[u] = d

    K = len(seeds)
    total = len(units)
    budget = [total // K + (1 if i < total % K else 0) for i in range(K)]
    owner = {}
    grown = [0] * K
    fronts = []
    for i, s in enumerate(seeds):
        owner[s] = i
        grown[i] = 1
        fronts.append([s])
    active = True
    guard = 0
    while active and guard < 200000:
        guard += 1
        active = False
        for i in range(K):
            if grown[i] >= budget[i] or not fronts[i]:
                continue
            nxt = []
            for u in fronts[i]:
                for nb in (neighbors.get(u) or []):
                    if nb not in owner:
                        owner[nb] = i
                        grown[i] += 1
                        nxt.append(nb)
                        if grown[i] >= budget[i]:
                            break
                if grown[i] >= budget[i]:
                    break
            fronts[i] = nxt
            if grown[i] < budget[i] and nxt:
                active = True
    # 剩余单元归最近的已分配邻居
    rest = [u for u in units if u not in owner]
    if rest:
        q = deque(rest)
        while q:
            u = q.popleft()
            if u in owner:
                continue
            best = None
            for nb in (neighbors.get(u) or []):
                if nb in owner:
                    best = owner[nb]
                    break
            if best is None:
                continue
            owner[u] = best
            for nb in (neighbors.get(u) or []):
                if nb not in owner:
                    q.append(nb)

    groups = {}
    for u, g in owner.items():
        groups.setdefault(g, []).append(u)
    return groups


def _refine_split(ids, w, h, pid, k):
    """省细化：像素为单元（保留原接口，内部走通用逻辑）"""
    px = [i for i in range(len(ids)) if ids[i] == pid]
    if not px:
        return None
    # 像素邻居按 4 邻域现算太慢，直接用座标构造邻居（只在同省内）
    pxset = set(px)
    nb = {}
    for i in px:
        x, y = i % w, i // w
        lst = []
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                j = ny * w + nx
                if j in pxset:
                    lst.append(j)
        nb[i] = lst
    coord = {i: (i % w, i // w) for i in px}
    groups = _refine_grow_units(px, nb, k, coord)
    owner = {}
    for g, members in groups.items():
        for i in members:
            owner[i] = g
    return {"owner": owner, "seeds": [], "px": px}


def refine_preview(pid, k=2, root=None):
    """预览切分：不写盘，返回每块的像素数与包围盒"""
    pid = int(pid or 0)
    k = max(2, min(64, int(k or 2)))
    if pid <= 0:
        return {"ok": False, "msg": "先选一个省"}
    root = _map_pick(root)
    ids, w, h = _refine_load_ids(root)
    if not ids:
        return {"ok": False, "msg": "读不到 provinces.bmp / definition.csv"}
    res = _refine_split(ids, w, h, pid, k)
    if not res:
        return {"ok": False, "msg": "省 %d 没有像素" % pid}
    from collections import Counter
    owner = res["owner"]
    cnt = Counter(owner.values())
    parts = []
    for kk in sorted(cnt):
        pts = [i for i, v in owner.items() if v == kk]
        xs = [p % w for p in pts]
        ys = [p // w for p in pts]
        parts.append({"i": kk, "px": cnt[kk],
                      "bbox": [min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1],
                      # 描边用：只回包围盒内的相对坐标，前端按比例画
                      "pts": [(p % w - min(xs)) * 100000 + (p // w - min(ys)) for p in pts][:20000]})
    # 细化前把风险讲清楚：VP 会移动、首都会偏、新省要不要进州
    _p2s, _dups = _prov_state_map()
    _warn, _sid = _refine_state_warnings(pid, _p2s)
    if pid in _dups:
        _warn.insert(0, "省 %d 同时被州 %s 声明（数据冲突），本次按第一个州处理，建议先修正" % (
            pid, " / ".join(str(x) for x in _dups[pid])))
    return {"ok": True, "pid": pid, "k": len(cnt), "total": len(res["px"]),
            "state": _sid, "warnings": _warn,
            "parts": parts, "msg": "切成 %d 块，面积 %s" % (
                len(cnt), sorted(cnt.values(), reverse=True))}


def refine_apply(pid, k=2, root=None, base_pid=None):
    """应用切分：分配新省号 → 写 bmp + definition.csv"""
    pid = int(pid or 0)
    k = max(2, min(64, int(k or 2)))
    if pid <= 0:
        return {"ok": False, "msg": "先选一个省"}
    root = _map_pick(root)
    layers = mod_layers(root)
    bmp, _ = _layers_find("map/provinces.bmp", layers)
    csvp, _ = _layers_find("map/definition.csv", layers)
    if not bmp or not csvp:
        return {"ok": False, "msg": "找不到地图文件"}
    if is_under_game(bmp):
        return {"ok": False, "msg": "地图来自原版，只读"}
    ids, w, h = _refine_load_ids(root)
    if not ids:
        return {"ok": False, "msg": "读不到省数据"}
    res = _refine_split(ids, w, h, pid, k)
    if not res:
        return {"ok": False, "msg": "省 %d 没有像素" % pid}
    owner = res["owner"]

    # 读 definition.csv：拿省号上限与已用 RGB
    rows = []
    used_rgb = set()
    max_pid = 0
    with io.open(csvp, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.rstrip("\r\n")
            rows.append(s)
            p = s.split(";")
            if len(p) >= 8 and p[0].isdigit():
                n = int(p[0])
                max_pid = max(max_pid, n)
                used_rgb.add((int(p[1]), int(p[2]), int(p[3])))
    # 原省信息（地形/洲等沿用）
    src = None
    for s in rows:
        p = s.split(";")
        if len(p) >= 8 and p[0].isdigit() and int(p[0]) == pid:
            src = p
            break
    if not src:
        return {"ok": False, "msg": "definition.csv 里没有省 %d" % pid}

    from collections import Counter
    cnt = Counter(owner.values())
    keys = sorted(cnt)
    # 第一块沿用原省号，其余分配新号
    assign = {keys[0]: pid}
    nid = max_pid + 1
    for kk in keys[1:]:
        while nid in used_rgb_ids(rows) or nid == pid:
            nid += 1
        assign[kk] = nid
        nid += 1

    # 新 RGB
    new_rows = []
    rgb_map = {keys[0]: (int(src[1]), int(src[2]), int(src[3]))}
    for kk in keys[1:]:
        rgb = _refine_free_rgb(used_rgb)
        used_rgb.add(rgb)
        rgb_map[kk] = rgb
        row = list(src)
        row[0] = str(assign[kk])
        row[1], row[2], row[3] = str(rgb[0]), str(rgb[1]), str(rgb[2])
        new_rows.append(";".join(row))

    if not new_rows:
        return {"ok": False, "msg": "只有一块，不需要新增"}

    # 写 definition.csv
    snapshot(csvp)
    body = chr(10).join(rows + new_rows) + chr(10)
    io.open(csvp, "wb").write(body.encode("utf-8"))

    # 写 bmp：只改这块区域内像素
    xs = [p % w for p in owner]
    ys = [p // w for p in owner]
    bx, by = min(xs), min(ys)
    bw, bh = max(xs) - bx + 1, max(ys) - by + 1
    before = bmp_read_rect(bmp, bx, by, bw, bh)
    if before is None:
        return {"ok": False, "msg": "读 bmp 区域失败"}
    after = list(before)
    for i, kk in owner.items():
        if assign[kk] == pid:
            continue
        _o = (i // w - by) * bw + (i % w - bx)
        if 0 <= _o < len(after):
            after[_o] = rgb_map[kk]
    _lay_ws = _refine_out_bmp(bmp)
    if _lay_ws != bmp:
        os.makedirs(os.path.dirname(_lay_ws) or ".", exist_ok=True)
        shutil.copyfile(bmp, _lay_ws)
        snapshot(_lay_ws)
        bmp = _lay_ws
    bmp_write_rect(bmp, bx, by, bw, bh, after)
    _REFINE_IDS_CACHE.pop("cur", None)

    # 新省必须进州，否则是孤儿地块（没有 owner / 建筑槽 / 人口）
    _new_ids = [assign[kk] for kk in keys[1:]]
    _p2s2, _ = _prov_state_map()
    _sid2 = _p2s2.get(pid, 0)
    _state_rel = _refine_attach_to_state(root, _sid2, _new_ids, pid)
    reload_data()

    _m = "已切成 %d 块，新增省号 %s" % (len(keys), _new_ids)
    if _state_rel:
        _m += "；已加入州 %d（%s）" % (_sid2, _state_rel)
    elif _sid2:
        _m += "；加入州 %d 失败，需手动处理" % _sid2
    else:
        _m += "；原省无州归属，新省也未归属"
    return {"ok": True, "pid": pid, "new_ids": _new_ids, "state": _sid2,
            "stateFile": _state_rel,
            "parts": len(keys), "pixels": len(owner), "rect": [bx, by, bw, bh],
            "msg": _m}


def used_rgb_ids(rows):
    out = set()
    for s in rows:
        p = s.split(";")
        if len(p) >= 8 and p[0].isdigit():
            out.add(int(p[0]))
    return out


def _refine_free_rgb(used):
    """找一个未被使用的省色（避开 0,0,0 与已有色）"""
    for r in range(1, 256):
        for g in range(1, 256, 3):
            for b in range(1, 256, 7):
                if (r, g, b) not in used:
                    return (r, g, b)
    return (250, 250, 250)


def _refine_out_bmp(path):
    """输出模式下把源 bmp 映射到 output/ 的副本"""
    return _out_path(path)


def map_repair_cross(root=None, apply_fix=False, limit=2000):
    """修十字交叉像素：把 2x2 的 `A B / B A` 解成 `A A / B B` 或 `A B / A B`。
    选择依据：看 A 在上方还是左方的邻域更多，优先保持那个方向的连通。"""
    root = _map_pick(root)
    layers = mod_layers(root)
    bmp, prov = _layers_find("map/provinces.bmp", layers)
    if not bmp:
        return {"ok": False, "msg": "找不到 provinces.bmp"}
    if apply_fix and is_under_game(bmp):
        return {"ok": False, "msg": "provinces.bmp 来自原版，只读"}
    info = bmp_info(bmp)
    if not info or info["bpp"] != 24:
        return {"ok": False, "msg": "只支持 24 位 BMP"}
    w, h = info["w"], info["h"]
    allpx = bmp_read_rect(bmp, 0, 0, w, h)
    if allpx is None:
        return {"ok": False, "msg": "读图失败"}
    crosses = _scan_cross(allpx, w, h)
    if not crosses:
        return {"ok": True, "found": 0, "fixed": 0, "msg": "没有十字交叉"}

    # 决定每处怎么解
    changes = []      # [(x, y, new_rgb)]
    plan = {"h": 0, "v": 0, "tie": 0}
    for (x, y, a, b) in crosses[:limit]:
        up = allpx[(y - 1) * w + x] if y > 0 else None
        left = allpx[y * w + (x - 1)] if x > 0 else None
        a_up = (up == a)
        a_left = (left == a)
        if a_up and not a_left:
            # A 在上方更连贯 → 纵向切：把 (x, y+1) 的 B 改成 A
            changes.append((x, y + 1, a))
            plan["v"] += 1
        elif a_left and not a_up:
            # A 在左方更连贯 → 横向切：把 (x+1, y) 的 B 改成 A
            changes.append((x + 1, y, a))
            plan["h"] += 1
        else:
            # 无法判断：默认横向（改动更集中在上方）
            changes.append((x + 1, y, a))
            plan["tie"] += 1

    result = {"ok": True, "found": len(crosses), "planned": len(changes),
              "plan": plan, "applied": 0}
    if not apply_fix:
        result["msg"] = "发现 %d 处十字交叉（横向 %d / 纵向 %d / 默认 %d），未改动" % (
            len(crosses), plan["h"], plan["v"], plan["tie"])
        result["sample"] = [{"x": x, "y": y} for (x, y, _c) in changes[:20]]
        return result

    # 应用：点级备份（散布改动用包围盒会备份整幅图，30+ MB，实际只改几百个像素）
    # 多轮迭代只记「第一次遇到该像素时的原值」，最后统一存成一个 undo 条目，
    # 否则撤销只能退回到上一轮，而不是修复前的状态。
    xs = [c[0] for c in changes]
    ys = [c[1] for c in changes]
    x0, x1 = max(0, min(xs)), min(w - 1, max(xs))
    y0, y1 = max(0, min(ys)), min(h - 1, max(ys))
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    before = bmp_read_rect(bmp, x0, y0, bw, bh)
    if before is None:
        return {"ok": False, "msg": "读 bmp 区域失败"}
    after = list(before)
    orig_vals = {}
    for (cx, cy, rgb) in changes:
        o = (cy - y0) * bw + (cx - x0)
        if 0 <= o < len(after):
            gi = cy * w + cx
            if gi not in orig_vals:
                orig_vals[gi] = tuple(before[o])
            after[o] = rgb
    bmp_write_rect(bmp, x0, y0, bw, bh, after)
    result["applied"] = len(changes)

    # 改像素会产生新的交叉，迭代几轮直到不再减少
    rounds = 1
    prev = len(crosses)
    while rounds < 4:
        allpx2 = bmp_read_rect(bmp, 0, 0, w, h)
        cs2 = _scan_cross(allpx2, w, h) if allpx2 else []
        if not cs2 or len(cs2) >= prev:
            break
        prev = len(cs2)
        ch2 = []
        for (x, y, a, b) in cs2:
            up = allpx2[(y - 1) * w + x] if y > 0 else None
            left = allpx2[y * w + (x - 1)] if x > 0 else None
            ch2.append((x + 1 if (left == a or up != a) else x,
                        y if (left == a or up != a) else y + 1, a))
        xs2 = [c[0] for c in ch2]
        ys2 = [c[1] for c in ch2]
        ax0, ax1 = max(0, min(xs2)), min(w - 1, max(xs2))
        ay0, ay1 = max(0, min(ys2)), min(h - 1, max(ys2))
        aw, ah = ax1 - ax0 + 1, ay1 - ay0 + 1
        bef2 = bmp_read_rect(bmp, ax0, ay0, aw, ah)
        if bef2 is None:
            break
        aft2 = list(bef2)
        for (cx, cy, rgb) in ch2:
            _i = (cy - ay0) * aw + (cx - ax0)
            if 0 <= _i < len(aft2):
                gi2 = cy * w + cx
                if gi2 not in orig_vals:
                    orig_vals[gi2] = tuple(bef2[_i])
                aft2[_i] = rgb
        bmp_write_rect(bmp, ax0, ay0, aw, ah, aft2)
        result["applied"] += len(ch2)
        rounds += 1

    # 所有轮次合成一个 undo 条目
    _pts = [(gi, rgb) for gi, rgb in orig_vals.items()]
    _fn = _save_point_undo(bmp, _pts)
    MAP_EDIT["undo"].append({"file": _fn, "bmp": bmp, "kind": "points",
                             "count": len(_pts), "rect": [x0, y0, bw, bh]})
    MAP_EDIT["redo"] = []

    result["rounds"] = rounds
    result["remaining"] = prev
    result["msg"] = "已修复 %d 处十字交叉（%d 轮），剩余约 %d 处（图层需要重建）" % (
        result["applied"], rounds, prev)
    return result


def map_repair_preview(root=None):
    """列出能自动修的问题及其影响面（不改文件）"""
    root = _map_pick(root)
    dirp, key, base = _map_dir(root)
    idx_path = os.path.join(dirp or "", "prov_index.json")
    if not os.path.exists(idx_path):
        return {"ok": False, "msg": "请先构建图层"}
    try:
        idx = json.loads(io.open(idx_path, encoding="utf-8").read())
    except Exception as e:
        return {"ok": False, "msg": "读取索引失败：%s" % e}
    have = set()
    for k, v in idx.items():
        try:
            if int(v.get("px") or 0) > 0:
                have.add(int(k))
        except Exception:
            continue
    csvp, prov = _csv_path_for(root)
    if not csvp:
        return {"ok": False, "msg": "找不到 definition.csv"}
    ghost = []
    total = 0
    try:
        for line in io.open(csvp, encoding="utf-8", errors="replace"):
            parts = line.strip().split(";")
            if len(parts) < 4 or not parts[0].isdigit():
                continue
            total += 1
            pid = int(parts[0])
            if pid == 0:
                continue
            if pid not in have:
                ghost.append(pid)
    except Exception as e:
        return {"ok": False, "msg": "读 csv 失败：%s" % e}
    return {"ok": True, "csv": csvp, "csv_from": prov, "csv_rows": total,
            "ghost": sorted(ghost)[:500], "ghost_count": len(ghost),
            "repairable": {"ghost": len(ghost)}}


def map_repair_ghost(root=None):
    """删除 definition.csv 里在地图上没有像素的省（省 0 保留）。
    改的是链顶 mod 的 csv；原版只读时拒绝。"""
    pv = map_repair_preview(root)
    if not pv.get("ok"):
        return pv
    csvp = pv["csv"]
    if is_under_game(csvp):
        return {"ok": False, "msg": "definition.csv 来自原版，只读，不能修"}
    ghost = set(pv["ghost"])
    if not ghost:
        return {"ok": True, "removed": 0, "msg": "没有幽灵省，不需要修"}
    try:
        raw = io.open(csvp, "rb").read()
        has_bom = raw[:3] == bytes((0xEF, 0xBB, 0xBF))
        text = raw.decode("utf-8-sig", errors="replace")
    except Exception as e:
        return {"ok": False, "msg": "读 csv 失败：%s" % e}
    keep = []
    removed = []
    for line in text.splitlines():
        parts = line.strip().split(";")
        if len(parts) >= 4 and parts[0].isdigit():
            pid = int(parts[0])
            if pid in ghost:
                removed.append(pid)
                continue
        keep.append(line)
    new_text = chr(10).join(keep)
    if text.endswith(chr(10)):
        new_text += chr(10)
    snapshot(csvp)
    try:
        with io.open(csvp, "w", encoding="utf-8-sig" if has_bom else "utf-8", newline="") as f:
            f.write(new_text)
    except Exception as e:
        return {"ok": False, "msg": "写 csv 失败：%s" % e}
    CHANGED[csvp] = os.path.relpath(csvp, os.path.dirname(os.path.dirname(csvp)))
    PROV_RGB.clear()
    return {"ok": True, "removed": len(removed), "ids": removed[:30], "csv": csvp,
            "msg": "已删除 %d 个幽灵省，图层需要重建" % len(removed)}


# v1.0.9 playset 编辑器
PLAYSET_FILE = os.path.join(WORK, "playset.json")


# v1.1.1 输出目录模式
OUTPUT_MODE = False
OUTPUT_ROOT = os.path.join(WORK, "output")


def output_state():
    """输出模式状态与统计"""
    files = 0
    size = 0
    if os.path.isdir(OUTPUT_ROOT):
        for dp, _dn, fs in os.walk(OUTPUT_ROOT):
            for fn in fs:
                files += 1
                try:
                    size += os.path.getsize(os.path.join(dp, fn))
                except Exception:
                    pass
    return {"ok": True, "on": OUTPUT_MODE, "root": OUTPUT_ROOT,
            "files": files, "size": size}


def output_toggle(on=None):
    global OUTPUT_MODE
    OUTPUT_MODE = bool(on) if on is not None else (not OUTPUT_MODE)
    return {"ok": True, "on": OUTPUT_MODE,
            "msg": "输出模式已开启：改动写到 %s，源 mod 不动" % OUTPUT_ROOT if OUTPUT_MODE
                   else "输出模式已关闭：改动直接写 mod 目录（仍有备份）"}


def _out_path(path):
    """输出模式下把 mod 内的路径映射到 output/<mod名>/<相对路径>。
    不在任何 mod 内的路径（新建文件等）保持原样。"""
    if not OUTPUT_MODE:
        return path
    try:
        ab = os.path.abspath(path)
        for r in ROOTS:
            rab = os.path.abspath(r)
            if ab == rab:
                continue
            if ab.startswith(rab + os.sep):
                rel = os.path.relpath(ab, rab)
                dst = os.path.join(OUTPUT_ROOT, os.path.basename(rab.rstrip("\\/")), rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                return dst
    except Exception:
        pass
    return path


def _out_read_path(path):
    """读取时优先看输出目录：这样开了输出模式改完立刻能看到效果，源文件依然不动。"""
    if not OUTPUT_MODE:
        return path
    try:
        ab = os.path.abspath(path)
        for r in ROOTS:
            rab = os.path.abspath(r)
            if ab == rab:
                continue
            if ab.startswith(rab + os.sep):
                rel = os.path.relpath(ab, rab)
                cand = os.path.join(OUTPUT_ROOT, os.path.basename(rab.rstrip("\\/")), rel)
                if os.path.exists(cand):
                    return cand
    except Exception:
        pass
    return path


def output_apply_back(paths=None):
    """把输出目录里的文件复制回对应 mod（复制前给源文件做快照备份）"""
    if not os.path.isdir(OUTPUT_ROOT):
        return {"ok": False, "msg": "输出目录为空，没有可回源的文件"}
    done, skipped = [], []
    for modname in os.listdir(OUTPUT_ROOT):
        src_mod_dir = os.path.join(OUTPUT_ROOT, modname)
        if not os.path.isdir(src_mod_dir):
            continue
        target_root = None
        for r in ROOTS:
            if os.path.basename(os.path.abspath(r).rstrip("\\/")) == modname:
                target_root = os.path.abspath(r)
                break
        if not target_root:
            skipped.append({"mod": modname, "why": "当前没有加载同名的 mod"})
            continue
        for dp, _dn, fs in os.walk(src_mod_dir):
            for fn in fs:
                src = os.path.join(dp, fn)
                rel = os.path.relpath(src, src_mod_dir)
                dst = os.path.join(target_root, rel)
                try:
                    if os.path.exists(dst):
                        snapshot(dst)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    CHANGED[dst] = rel
                    done.append(rel)
                except Exception as e:
                    skipped.append({"file": rel, "why": str(e)[:80]})
    return {"ok": True, "applied": len(done), "files": done[:40], "skipped": skipped,
            "msg": "已把 %d 个文件复制回 mod（原文件已备份）" % len(done)}


def output_clear():
    """清空输出目录（不动 mod）"""
    try:
        if os.path.isdir(OUTPUT_ROOT):
            shutil.rmtree(OUTPUT_ROOT, ignore_errors=True)
        return {"ok": True, "msg": "输出目录已清空"}
    except Exception as e:
        return {"ok": False, "msg": "清空失败：%s" % e}


def playset_get():


    """返回当前叠加链（按启动器加载顺序）"""
    layers = []
    for r in ROOTS:
        ab = os.path.abspath(r)
        desc = _mod_descriptor(ab)
        layers.append({
            "path": ab,
            "name": desc["name"] or os.path.basename(ab),
            "has_descriptor": os.path.exists(os.path.join(ab, "descriptor.mod")),
            "has_map": os.path.exists(os.path.join(ab, "map", "provinces.bmp")),
            "replace_count": len(desc["replace"]),
            "deps": desc["deps"],
        })
    return {"ok": True, "layers": layers, "game": GAME or "",
            "saved": os.path.exists(PLAYSET_FILE),
            "order": "列表从下往上覆盖：越靠下加载越晚，优先级越高"}


def playset_validate(paths):
    """校验一组 mod 路径，返回 (可用列表, 问题列表)"""
    good, bad = [], []
    for p in paths or []:
        ab = os.path.abspath(str(p or ""))
        if not os.path.isdir(ab):
            bad.append({"path": ab, "why": "目录不存在"})
            continue
        has_desc = os.path.exists(os.path.join(ab, "descriptor.mod"))
        has_nf = os.path.isdir(os.path.join(ab, "common", "national_focus"))
        has_any = os.path.isdir(os.path.join(ab, "common")) or os.path.isdir(os.path.join(ab, "map"))
        if not (has_desc or has_nf or has_any):
            bad.append({"path": ab, "why": "不像 mod 根目录（无 descriptor.mod / common / map）"})
            continue
        good.append(ab)
    return good, bad


def playset_save(paths):
    """保存播放集到 work/playset.json。重启后生效（运行中切换会打乱已加载的状态）。"""
    good, bad = playset_validate(paths)
    try:
        os.makedirs(WORK, exist_ok=True)
        io.open(PLAYSET_FILE, "w", encoding="utf-8", newline="").write(
            json.dumps({"order": good, "saved": time.strftime("%Y-%m-%d %H:%M:%S")},
                       ensure_ascii=False, indent=1))
    except Exception as e:
        return {"ok": False, "msg": "保存失败：%s" % e}
    _LAYERS_CACHE.clear()
    return {"ok": True, "count": len(good), "bad": bad,
            "msg": "已保存 %d 个 mod（顺序：越靠下优先级越高）。重启编辑器后生效。" % len(good)}


def playset_load_saved():
    """启动时读 playset.json（没有 --mod 参数时使用）"""
    try:
        if not os.path.exists(PLAYSET_FILE):
            return []
        d = json.loads(io.open(PLAYSET_FILE, encoding="utf-8").read())
        out = []
        for p in (d.get("order") or []):
            if p and os.path.isdir(p) and p not in out:
                out.append(p)
        return out
    except Exception:
        return []


def map_analysis(root=None, limit=60, min_px=800, only_land=True):


    """省份排名：按面积（像素数）列出大省，附州/战略区/地形。
    数据直接来自图层缓存的 prov_index.json，不重新扫像素。"""
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "还没有加载 mod"}
    dirp, key, base = _map_dir(root)
    idx_path = os.path.join(dirp or "", "prov_index.json")
    if not os.path.exists(idx_path):
        return {"ok": False, "msg": "请先构建图层（缺少 prov_index.json）"}
    try:
        idx = json.loads(io.open(idx_path, encoding="utf-8").read())
    except Exception as e:
        return {"ok": False, "msg": "读取索引失败：%s" % e}

    rows = []
    total_px = 0
    for pid_s, rec in idx.items():
        try:
            px = int(rec.get("px") or 0)
            pid = int(pid_s)
        except Exception:
            continue
        if pid <= 0 or px <= 0:
            continue
        _type = rec.get("type") or ""
        if only_land and _type and _type != "land":
            continue          # 海省湖省不需要细化，默认排除
        total_px += px
        rows.append({"pid": pid, "px": px, "state": rec.get("state") or 0,
                     "region": rec.get("region") or 0, "terrain": rec.get("terrain") or "",
                     "continent": rec.get("continent") or 0, "type": rec.get("type") or ""})
    if not rows:
        return {"ok": False, "msg": "索引里没有有效省份"}
    rows.sort(key=lambda r: -r["px"])
    px_all = sorted(r["px"] for r in rows)
    n = len(px_all)
    median = px_all[n // 2] if n else 0
    mean = total_px / n if n else 0
    big = [r for r in rows if r["px"] >= min_px]
    st_agg = {}
    for r in rows:
        sid = r["state"]
        a = st_agg.setdefault(sid, {"state": sid, "n": 0, "px": 0, "max": 0})
        a["n"] += 1
        a["px"] += r["px"]
        a["max"] = max(a["max"], r["px"])
    st_rows = sorted(st_agg.values(), key=lambda a: -(a["px"] / max(1, a["n"])))[:20]
    for a in st_rows:
        a["avg"] = round(a["px"] / max(1, a["n"]))
    return {"ok": True, "count": n, "total_px": total_px, "mean": round(mean),
            "median": median, "min_px": min_px, "big_count": len(big),
            "top": rows[:limit], "big": big[:limit], "states": st_rows, "source": base}


def map_sources():
    """列出所有可用于地图的来源：已加载的 mod（有无 map 都列出）+ 原版"""
    out = []
    seen = set()
    for r in ROOTS:
        p = os.path.abspath(r)
        if p in seen:
            continue
        seen.add(p)
        # 用叠加链判断：submod 自己没有 bmp，但父 mod 有
        try:
            _b, _d, _prov, _layers = _map_files_layered(p)
        except Exception:
            _b = _d = _prov = None
        has = bool(_b and _d)
        prov_name = ""
        if _prov and os.path.abspath(_prov) != os.path.abspath(p):
            prov_name = os.path.basename(_prov.replace(chr(92), "/").rstrip("/"))
        out.append({"path": p, "name": os.path.basename(p.replace(chr(92), "/").rstrip("/")) or p,
                    "has_map": has, "map_from": prov_name,
                    "readonly": is_under_game(p), "is_game": False})
    if GAME:
        g = os.path.abspath(GAME)
        out.append({"path": g, "name": "原版（游戏本体）",
                    "has_map": os.path.exists(os.path.join(g, "map", "provinces.bmp")),
                    "readonly": True, "is_game": True})
    return out


def _map_pick(root=None):
    """指定 root 就用它；否则第一个在叠加链里能找到地图的 mod；最后原版。
    注意：submod 自己可能没有 provinces.bmp（由父 mod 提供），所以判断要走整条链。"""
    if root:
        return root
    for r in ROOTS:
        try:
            b, d, _provider, _layers = _map_files_layered(r)
        except Exception:
            b = d = None
        if b and d:
            return r
    return GAME


# v0.91 mod 叠加链（submod 支持）
_DESC_CACHE = {}


def _mod_descriptor(root):
    """读 mod 根目录的 descriptor.mod，返回 name / dependencies / replace_path。
    带 mtime 缓存：这个函数会被叠加链、图层查找反复调用，不缓存会拖慢所有接口。"""
    try:
        _abs = os.path.abspath(root or "")
        _dp = os.path.join(_abs, "descriptor.mod")
        _sig = None
        if os.path.exists(_dp):
            _st = os.stat(_dp)
            _sig = (_st.st_mtime, _st.st_size)
        _hit = _DESC_CACHE.get(_abs)
        if _hit is not None and _hit[0] == _sig:
            return dict(_hit[1])
    except Exception:
        _abs, _sig = "", None
    info = {"name": "", "deps": [], "replace": [], "path": ""}
    for fn in ("descriptor.mod",):
        p = os.path.join(root, fn)
        if not os.path.exists(p):
            continue
        try:
            text = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        m = re.search(r'(?m)^\s*name\s*=\s*"([^"]*)"', text)
        if m:
            info["name"] = m.group(1)
        m = re.search(r'dependencies\s*=\s*\{([^}]*)\}', text, re.S)
        if m:
            info["deps"] = re.findall(r'"([^"]+)"', m.group(1))
        info["replace"] = re.findall(r'replace_path\s*=\s*"([^"]*)"', text)
        break
    try:
        if _abs:
            _DESC_CACHE[_abs] = (_sig, dict(info))
    except Exception:
        pass
    return info


def _find_mod_by_name(name, extra_roots=()):
    """按 mod 名（descriptor 里的 name）在已知位置找目录"""
    cands = []
    # 1) 已加载的 roots
    for r in list(ROOTS) + list(extra_roots):
        if not r:
            continue
        cands.append(os.path.abspath(r))
    # 2) workshop 目录
    ws = r"E:\SteamLibrary\steamapps\workshop\content\394360"
    if os.path.isdir(ws):
        for d in os.listdir(ws):
            p = os.path.join(ws, d)
            if os.path.isdir(p):
                cands.append(p)
    # 3) 常见 mod 目录
    for base in (r"E:\HOI4\mod", os.path.join(os.path.expanduser("~"), "Documents", "Paradox Interactive",
                                                 "Hearts of Iron IV", "mod")):
        if os.path.isdir(base):
            for d in os.listdir(base):
                p = os.path.join(base, d)
                if os.path.isdir(p):
                    cands.append(p)
    for p in cands:
        d = _mod_descriptor(p)
        if d["name"] and d["name"].lower() == name.lower():
            return p
        # 也允许目录名直接等于 mod 名
        if os.path.basename(p.rstrip("\\/")).lower() == name.lower():
            return p
    return None


_LAYERS_CACHE = {}


def mod_layers(root=None, depth=3):
    """返回叠加链，从最父到最子：[原版, 父 mod, 子 mod]
    HOI4 语义：后加载的覆盖先加载的；replace_path 的目录是整体替换。"""
    root = _map_pick(root)
    try:
        _ck = (os.path.abspath(root or ""), tuple(os.path.abspath(r) for r in ROOTS))
        _hit = _LAYERS_CACHE.get(_ck)
        if _hit:
            return list(_hit)
    except Exception:
        _ck = None
    # playset 语义：启动时给了多个 --mod（按启动器里的加载顺序），就按它们的顺序叠加，
    # 后面的覆盖前面的。这比只靠 descriptor 的 dependencies 更忠实于启动器的实际行为
    # （很多 mod 根本不写 dependencies）。
    if len(ROOTS) > 1:
        chain = []
        for _r in ROOTS:
            _ab = os.path.abspath(_r)
            if _ab not in chain:
                chain.append(_ab)
        if root and os.path.abspath(root) not in chain:
            chain.append(os.path.abspath(root))
        if GAME and os.path.abspath(GAME) not in chain:
            chain.insert(0, os.path.abspath(GAME))
        try:
            if _ck:
                _LAYERS_CACHE[_ck] = list(chain)
        except Exception:
            pass
        return chain

    chain = []
    cur = root
    guard = 0
    while cur and guard < depth:
        guard += 1
        ab = os.path.abspath(cur)
        if ab not in chain:
            chain.append(ab)
        desc = _mod_descriptor(ab)
        if not desc["deps"]:
            break
        # 取第一个能定位到的父依赖
        nxt = None
        for dep in desc["deps"]:
            p = _find_mod_by_name(dep, extra_roots=[root] if root else [])
            if p and os.path.abspath(p) not in chain:
                nxt = p
                break
        cur = nxt
    chain.reverse()          # 父在前
    if GAME and os.path.abspath(GAME) not in chain:
        chain.insert(0, os.path.abspath(GAME))
    try:
        if _ck:
            _LAYERS_CACHE[_ck] = list(chain)
    except Exception:
        pass
    return chain


def _layers_find(rel, layers):
    """按 HOI4 语义在叠加链里找文件：replace_path 的目录整体替换，其余逐文件覆盖。
    返回 (绝对路径 or None, 来源 root)。"""
    if not layers:
        return None, None
    rel_n = rel.replace(chr(92), "/").lstrip("/")
    # 判断这条路径是否落在某个 mod 的 replace_path 目录下
    replace_at = None
    for r in reversed(layers):
        for rp in _mod_descriptor(r)["replace"]:
            rp_n = rp.replace("\\", "/").strip("/")
            if rp_n and (rel_n == rp_n or rel_n.startswith(rp_n + "/")):
                replace_at = r
                break
        if replace_at:
            break
    search = [replace_at] if replace_at else list(reversed(layers))
    for r in search:
        p = os.path.join(r, rel_n.replace("/", os.sep))
        if os.path.exists(p):
            return p, r
    return None, None


def _layer_files(rel_dir, layers, exts=(".txt",)):
    """按叠加链收集某个目录下的文件。
    - 某层声明了 replace_path 覆盖该目录时：只看那一层（整目录替换，不合并）
    - 否则从链尾往链首收集，同名文件子层优先
    返回 (文件路径列表, 是否被 replace_path 接管)"""
    from collections import OrderedDict
    rel_n = rel_dir.replace(chr(92), "/").strip("/")
    repl = None
    for r in reversed(layers or []):
        for rp in _mod_descriptor(r)["replace"]:
            if rp.replace(chr(92), "/").strip("/") == rel_n:
                repl = r
                break
        if repl:
            break
    scan = [repl] if repl else list(reversed(layers or []))
    seen = OrderedDict()
    for r in scan:
        dpath = os.path.join(r, rel_n.replace("/", os.sep))
        if not os.path.isdir(dpath):
            continue
        try:
            names = sorted(os.listdir(dpath))
        except Exception:
            continue
        for fn in names:
            if fn.lower().endswith(exts) and fn not in seen:
                seen[fn] = os.path.join(dpath, fn)
    return list(seen.values()), bool(repl)


def _map_files_layered(root):
    """在叠加链里找 provinces.bmp / definition.csv，返回 (bmp, csv, 提供地图的 root, layers)"""
    layers = mod_layers(root)
    b, rb = _layers_find("map/provinces.bmp", layers)
    d, rd = _layers_find("map/definition.csv", layers)
    if b and d:
        return b, d, (rb or rd), layers
    return None, None, None, layers


# v0.94 地图像素编辑地基：原位写 bmp + 区块撤销
import struct


def bmp_info(path):
    """读 BMP 头，返回 (width, height, bpp, data_offset, row_size, top_down)"""
    with open(path, "rb") as f:
        head = f.read(54)
        if len(head) < 54 or head[:2] != b"BM":
            return None
        data_off = struct.unpack("<I", head[10:14])[0]
        w = struct.unpack("<i", head[18:22])[0]
        h = struct.unpack("<i", head[22:26])[0]
        bpp = struct.unpack("<H", head[28:30])[0]
        top_down = h < 0
        h = abs(h)
        row_size = ((w * bpp // 8) + 3) // 4 * 4
        return {"w": w, "h": h, "bpp": bpp, "offset": data_off,
                "row": row_size, "top_down": top_down, "bytes_pp": bpp // 8}


def bmp_read_rect(path, x0, y0, w, h):
    path = _out_read_path(path)          # 输出模式下读改过的副本
    """读矩形区域的原始像素（RGB 三元组列表，行优先）。
    走 Pillow 的 C 实现；逐行手工解析在 1100 万像素时要 7 秒以上。"""
    info = bmp_info(path)
    if not info or info["bpp"] != 24:
        return None
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(path) as im:
            box = im.convert("RGB").crop((x0, y0, x0 + w, y0 + h))
            raw = box.tobytes()
        return [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]
    except Exception:
        pass
    out = []
    with open(path, "rb") as f:
        for y in range(y0, y0 + h):
            row_idx = y if info["top_down"] else (info["h"] - 1 - y)
            f.seek(info["offset"] + row_idx * info["row"] + x0 * 3)
            data = f.read(w * 3)
            for i in range(0, len(data), 3):
                out.append((data[i + 2], data[i + 1], data[i]))
    return out


def bmp_write_rect(path, x0, y0, w, h, pixels):
    """把 RGB 像素列表原位写回 bmp（不重存文件，保持原有结构）。
    输出模式下：先把源 bmp 复制到 output/ 再改副本，源文件不动。"""
    if OUTPUT_MODE:
        _dst = _out_path(path)
        if os.path.abspath(_dst) != os.path.abspath(path):
            if not os.path.exists(_dst):
                os.makedirs(os.path.dirname(_dst) or ".", exist_ok=True)
                shutil.copyfile(path, _dst)
            path = _dst
    info = bmp_info(path)
    if not info or info["bpp"] != 24:
        return False
    buf = bytearray()
    if pixels and isinstance(pixels[0], (list, tuple)) and len(pixels[0]) == 3:
        for (r, g, b) in pixels:
            buf += bytes((b, g, r))
    else:
        buf = bytearray(pixels)
    with open(path, "r+b") as f:
        stride = w * 3
        for row in range(h):
            row_idx = (y0 + row) if info["top_down"] else (info["h"] - 1 - (y0 + row))
            f.seek(info["offset"] + row_idx * info["row"] + x0 * 3)
            f.write(bytes(buf[row * stride:(row + 1) * stride]))
    return True


PROV_RGB = {}   # 省 id -> (r,g,b)，来自 definition.csv


_PROV_RGB_CACHE = {}


def _ensure_prov_rgb(root=None):
    """按需从 definition.csv 加载省颜色，**按 mod 缓存**。

    原来用全局单例：第一个 mod 加载完就再也不更新，换 mod 后它的省号全部「不存在」。
    实测后果：跑回归时先测 CN 再测京都，京都的 17214/17217 被判为不存在，州细化失败。"""
    _root = _map_pick(root or None)
    key = os.path.abspath(_root or "")
    if key in _PROV_RGB_CACHE:
        PROV_RGB.clear()
        PROV_RGB.update(_PROV_RGB_CACHE[key])
        return PROV_RGB
    PROV_RGB.clear()
    try:
        _layers = mod_layers(_root)
        csvp, _prov = _layers_find("map/definition.csv", _layers)
        if not csvp or not os.path.exists(csvp):
            return PROV_RGB
        with io.open(csvp, encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.strip().split(";")
                if len(parts) < 4:
                    continue
                try:
                    PROV_RGB[int(parts[0])] = (int(parts[1]), int(parts[2]), int(parts[3]))
                except Exception:
                    continue
    except Exception as e:
        print("加载 definition.csv 颜色失败:", e)
    _PROV_RGB_CACHE[key] = dict(PROV_RGB)
    return PROV_RGB
MAP_EDIT = {"pending": [], "undo": [], "redo": [], "file": "", "touched": set()}
MAP_UNDO_DIR = os.path.join(WORK, "mapundo")


def map_edit_begin(bmp_path):
    """开始一次地图编辑事务：清空待提交队列"""
    MAP_EDIT["pending"] = []
    MAP_EDIT["file"] = bmp_path
    MAP_EDIT["touched"] = set()
    return True


def map_edit_dab(bmp_path, x, y, radius, rgb):
    """在事务里画一笔（圆），记录待写像素；返回实际影响的像素数"""
    info = bmp_info(bmp_path)
    if not info:
        return 0
    w, h = info["w"], info["h"]
    n = 0
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy > radius * radius:
                continue
            px, py = x + dx, y + dy
            if 0 <= px < w and 0 <= py < h:
                MAP_EDIT["pending"].append((px, py, rgb))
                MAP_EDIT["touched"].add((px, py))
                n += 1
    return n


def map_edit_commit(bmp_path=None):
    """提交事务：先保存受影响区域的原始像素（供撤销），再原位写入"""
    bmp_path = bmp_path or MAP_EDIT.get("file")
    pend = MAP_EDIT.get("pending") or []
    if not bmp_path or not pend:
        return {"ok": False, "msg": "没有待写入的像素"}
    info = bmp_info(bmp_path)
    if not info:
        return {"ok": False, "msg": "读不到 bmp 头"}
    xs = [p[0] for p in pend]
    ys = [p[1] for p in pend]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    w, h = x1 - x0 + 1, y1 - y0 + 1
    before = bmp_read_rect(bmp_path, x0, y0, w, h)
    if before is None:
        return {"ok": False, "msg": "只支持 24 位 BMP"}
    # 组装新像素
    grid = {(px - x0, py - y0): rgb for (px, py, rgb) in pend}
    after = list(before)
    for (gx, gy), rgb in grid.items():
        after[gy * w + gx] = rgb
    bmp_write_rect(bmp_path, x0, y0, w, h, after)
    # 存撤销区块
    os.makedirs(MAP_UNDO_DIR, exist_ok=True)
    seq = int(time.time() * 1000)
    fn = os.path.join(MAP_UNDO_DIR, "u%d_%d_%d_%d_%d.bin" % (seq, x0, y0, w, h))
    with open(fn, "wb") as f:
        for (r, g, b) in before:
            f.write(bytes((r, g, b)))
    MAP_EDIT["undo"].append({"file": fn, "bmp": bmp_path, "x": x0, "y": y0, "w": w, "h": h,
                             "count": len(pend)})
    MAP_EDIT["redo"] = []
    MAP_EDIT["pending"] = []
    MAP_EDIT["touched"] = set()
    return {"ok": True, "pixels": len(pend), "rect": [x0, y0, w, h], "undo_depth": len(MAP_EDIT["undo"])}


def map_edit_undo():
    if not MAP_EDIT["undo"]:
        return {"ok": False, "msg": "没有可撤销的地图编辑"}
    u = MAP_EDIT["undo"].pop()
    # 点级备份（十字交叉修复等散布型改动）：逐点写回，不记录 redo
    if u.get("kind") == "points":
        n = _apply_point_undo(u)
        MAP_EDIT["redo"] = []
        return {"ok": True, "restored": n, "kind": "points",
                "msg": "已撤销 %d 个像素的改动（点级备份，不支持重做）" % n}
    cur = bmp_read_rect(u["bmp"], u["x"], u["y"], u["w"], u["h"])
    prev = []
    with open(u["file"], "rb") as f:
        data = f.read()
    for i in range(0, len(data), 3):
        prev.append((data[i], data[i + 1], data[i + 2]))
    bmp_write_rect(u["bmp"], u["x"], u["y"], u["w"], u["h"], prev)
    MAP_EDIT["redo"].append({"file": u["file"], "bmp": u["bmp"], "x": u["x"], "y": u["y"],
                             "w": u["w"], "h": u["h"], "current": cur, "count": u["count"]})
    return {"ok": True, "restored": u["count"], "undo_depth": len(MAP_EDIT["undo"])}


def map_edit_redo():
    if not MAP_EDIT["redo"]:
        return {"ok": False, "msg": "没有可重做的地图编辑"}
    r = MAP_EDIT["redo"].pop()
    # 用当前值回写，再压回 undo
    bmp_write_rect(r["bmp"], r["x"], r["y"], r["w"], r["h"], r["current"])
    MAP_EDIT["undo"].append({"file": r["file"], "bmp": r["bmp"], "x": r["x"], "y": r["y"],
                             "w": r["w"], "h": r["h"], "count": r["count"]})
    return {"ok": True, "undo_depth": len(MAP_EDIT["undo"])}


# v0.99 省份合并 / 删除
def map_merge_preview(src, dst, root=None):
    """预览合并：返回源省像素数、受影响的州/战略区，不写盘"""
    src, dst = int(src), int(dst)
    if src == dst:
        return {"ok": False, "msg": "源省和目标省相同"}
    root = _map_pick(root)
    _ensure_prov_rgb(root)
    if src not in PROV_RGB:
        return {"ok": False, "msg": "省 %d 在 definition.csv 里没有定义" % src}
    if dst not in PROV_RGB:
        return {"ok": False, "msg": "省 %d 在 definition.csv 里没有定义" % dst}
    layers = mod_layers(root)
    bmp, _prov = _layers_find("map/provinces.bmp", layers)
    if not bmp:
        return {"ok": False, "msg": "找不到 provinces.bmp"}
    info = bmp_info(bmp)
    if not info:
        return {"ok": False, "msg": "只支持 24 位 BMP"}
    src_rgb = PROV_RGB[src]
    # 预览只需计数：优先读图层缓存里的 prov_index.json（构建时已算好每省像素数），零遍历成本
    _n = 0
    try:
        _d, _key, _b = _map_dir(root)
        _idx = os.path.join(_d or "", "prov_index.json")
        if os.path.exists(_idx):
            _j = json.loads(io.open(_idx, encoding="utf-8").read())
            _n = int((_j.get(str(src)) or {}).get("px") or 0)
    except Exception:
        _n = 0
    if not _n:
        try:
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None
            with Image.open(bmp) as _im:
                _cols = _im.convert("RGB").getcolors(maxcolors=200000) or []
            _n = next((c for c, col in _cols if tuple(col) == tuple(src_rgb)), 0)
        except Exception:
            allpx = bmp_read_rect(bmp, 0, 0, info["w"], info["h"])
            _n = sum(1 for px in allpx if px == src_rgb)
    hit = [0] * _n
    states_hit = []
    for sid, st in STATES.items():
        if src in (st.get("provinces") or []):
            states_hit.append(sid)
    prov2region, _rl = _strategic_regions(root)
    region_hit = [prov2region.get(src)] if prov2region.get(src) else []
    # 合并后源省的州会不会变空
    empty_after = []
    for sid in states_hit:
        st = STATES.get(sid) or {}
        rest = [p for p in (st.get("provinces") or []) if p != src]
        if not rest:
            empty_after.append(sid)
    return {"ok": True, "src": src, "dst": dst, "pixels": len(hit),
            "src_rgb": list(src_rgb), "dst_rgb": list(PROV_RGB[dst]),
            "states": states_hit, "states_empty_after": empty_after,
            "regions": region_hit, "bmp": bmp, "w": info["w"], "h": info["h"]}


def map_merge_apply(src, dst, root=None):
    """合并：把 src 的所有像素涂成 dst 的颜色，并把 src 从州列表里改成 dst"""
    pv = map_merge_preview(src, dst, root)
    if not pv.get("ok"):
        return pv
    src, dst = pv["src"], pv["dst"]
    root = _map_pick(root)
    layers = mod_layers(root)
    bmp = pv["bmp"]
    if is_under_game(bmp):
        return {"ok": False, "msg": "原版目录只读"}
    src_rgb = tuple(pv["src_rgb"])
    dst_rgb = tuple(pv["dst_rgb"])
    w, h = pv["w"], pv["h"]
    allpx = bmp_read_rect(bmp, 0, 0, w, h)
    changed = 0
    newpx = list(allpx)
    for i, px in enumerate(allpx):
        if px == src_rgb:
            newpx[i] = dst_rgb
            changed += 1
    if not changed:
        return {"ok": False, "msg": "省 %d 在地图上没有像素" % src}
    # 备份整幅原像素（合并影响面可能很大，用整幅更稳，33MB 一次性）
    os.makedirs(MAP_UNDO_DIR, exist_ok=True)
    seq = int(time.time() * 1000)
    fn = os.path.join(MAP_UNDO_DIR, "merge%d.bin" % seq)
    with open(fn, "wb") as f:
        for (r, g, b) in allpx:
            f.write(bytes((r, g, b)))
    bmp_write_rect(bmp, 0, 0, w, h, newpx)
    # 州：src → dst
    touched_states = []
    for sid in pv["states"]:
        st = STATES.get(sid) or {}
        fpath = st.get("path") or st.get("file")
        if not fpath or not os.path.exists(fpath):
            continue
        try:
            _text, _bom = _read_bom_text(fpath)
            _loc = _state_locate(_text)
            if not _loc:
                continue
            _b, _e = _loc
            _body = _text[_b + 1:_e - 1]
            _old = _parse_state_provinces(_body)
            _new = [p for p in _old if p != src]
            if dst not in _new:
                _new.append(dst)
            _new_text = _text[:_b + 1] + _set_state_provinces(_body, _new) + _text[_e - 1:]
            snapshot(fpath)
            _write_bom_text(fpath, _new_text, _bom)
            CHANGED[fpath] = os.path.relpath(fpath, root)
            touched_states.append(os.path.relpath(fpath, root))
        except Exception as _e2:
            print("合并时写州失败:", fpath, _e2)
    # 内存里的 STATES 也更新
    for sid in pv["states"]:
        st = STATES.get(sid)
        if not st:
            continue
        lst = [p for p in (st.get("provinces") or []) if p != src]
        if dst not in lst:
            lst.append(dst)
        st["provinces"] = sorted(lst)
    MAP_EDIT["undo"].append({"file": fn, "bmp": bmp, "x": 0, "y": 0, "w": w, "h": h,
                             "count": changed, "kind": "merge", "src": src, "dst": dst,
                             "states": touched_states})
    MAP_EDIT["redo"] = []
    return {"ok": True, "src": src, "dst": dst, "pixels": changed,
            "states": touched_states, "undo_depth": len(MAP_EDIT["undo"]),
            "note": "definition.csv 未改动（省 %d 仍保留定义，可后续手工清理或用「删除省」）" % src}


_NB_CACHE = {}


_ALL_NB_CACHE = {}


def _all_prov_neighbors(root):
    """一次扫描算全图省的邻接关系（共用边即邻接）。

    map_prov_neighbors 是按单个省算的、每次整幅扫描 5 秒；
    铁路检查要考虑几千段，必须一次性建表。结果按 bmp mtime 缓存。"""
    root = _map_pick(root)
    layers = mod_layers(root)
    bmp, _ = _layers_find("map/provinces.bmp", layers)
    csvp, _ = _layers_find("map/definition.csv", layers)
    if not bmp or not csvp:
        return {}
    key = (os.path.abspath(bmp), os.path.getmtime(bmp),
           os.path.abspath(csvp), os.path.getmtime(csvp))
    if key in _ALL_NB_CACHE:
        return _ALL_NB_CACHE[key]

    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    rgb2pid = {}
    with io.open(csvp, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.strip().split(";")
            if len(p) >= 8 and p[0].isdigit():
                rgb2pid[(int(p[1]), int(p[2]), int(p[3]))] = int(p[0])
    with Image.open(bmp) as im:
        w, h = im.size
        raw = im.convert("RGB").tobytes()
    # RGB 直接比较比先转省号快
    nb = {}
    for y in range(h):
        row = y * w * 3
        nrow = row + w * 3
        for x in range(w):
            o = row + x * 3
            a = raw[o:o + 3]
            if x + 1 < w:
                b = raw[o + 3:o + 6]
                if a != b:
                    pa = rgb2pid.get((a[0], a[1], a[2]), 0)
                    pb = rgb2pid.get((b[0], b[1], b[2]), 0)
                    if pa and pb:
                        nb.setdefault(pa, set()).add(pb)
                        nb.setdefault(pb, set()).add(pa)
            if y + 1 < h:
                b = raw[nrow + x * 3:nrow + x * 3 + 3]
                if a != b:
                    pa = rgb2pid.get((a[0], a[1], a[2]), 0)
                    pb = rgb2pid.get((b[0], b[1], b[2]), 0)
                    if pa and pb:
                        nb.setdefault(pa, set()).add(pb)
                        nb.setdefault(pb, set()).add(pa)
    out = {k: v for k, v in nb.items()}
    _ALL_NB_CACHE.clear()
    _ALL_NB_CACHE[key] = out
    return out


def map_prov_neighbors(pid, root=None):
    """返回某省的相邻省（按共享边像素数排序）。整幅扫描约 5 秒，按 bmp mtime 缓存结果。"""
    root = _map_pick(root)
    try:
        _layers0 = mod_layers(root)
        _b0, _p0 = _layers_find("map/provinces.bmp", _layers0)
        _sig = (os.path.abspath(_b0 or ""), int(os.path.getmtime(_b0)) if _b0 and os.path.exists(_b0) else 0, int(pid))
        if _sig in _NB_CACHE:
            return dict(_NB_CACHE[_sig])
    except Exception:
        _sig = None
    _ensure_prov_rgb(root)
    layers = mod_layers(root)
    bmp, _prov = _layers_find("map/provinces.bmp", layers)
    if not bmp:
        return {"ok": False, "msg": "找不到 provinces.bmp"}
    info = bmp_info(bmp)
    w, h = info["w"], info["h"]
    if pid not in PROV_RGB:
        return {"ok": False, "msg": "省 %d 没有颜色定义" % pid}
    rgb = PROV_RGB[pid]
    allpx = bmp_read_rect(bmp, 0, 0, w, h)
    idx = {v: k for k, v in PROV_RGB.items()}
    nb = {}
    for i, px in enumerate(allpx):
        if px != rgb:
            continue
        x, y = i % w, i // w
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                other = allpx[ny * w + nx]
                if other != rgb:
                    npid = idx.get(other)
                    if npid:
                        nb[npid] = nb.get(npid, 0) + 1
    out = sorted(nb.items(), key=lambda kv: -kv[1])[:12]
    res = {"ok": True, "pid": pid, "neighbors": [{"pid": p, "share": c} for p, c in out]}
    try:
        if _sig:
            _NB_CACHE[_sig] = dict(res)
    except Exception:
        pass
    return res


def map_edit_state():

    return {"ok": True, "undo": len(MAP_EDIT["undo"]), "redo": len(MAP_EDIT["redo"]),
            "pending": len(MAP_EDIT.get("pending") or []), "file": MAP_EDIT.get("file") or ""}


# v1.0 新建州（把若干省组织成一个州）
def _states_dir_for_write(root):
    """新建州文件应该写到的目录：链顶 mod（跳过原版）；原版只读"""
    layers = mod_layers(root)
    for lay in reversed(layers or []):
        if lay and not is_under_game(lay):
            d = os.path.join(lay, "history", "states")
            return lay, d
    return None, None


def _free_state_id():
    used = set()
    for sid in STATES.keys():
        try:
            used.add(int(sid))
        except Exception:
            pass
    n = 1
    while n in used:
        n += 1
    return n


def state_create(provinces, root=None, name=None, category="rural", manpower=100000, sid=None):
    """用给定省份新建一个州。
    - 这些省若已属于别的州，会从原州移出（HOI4 里一个省只能属于一个州）
    - 文件写到链顶 mod 的 history/states/，原版与父 mod 不写
    """
    root = _map_pick(root)
    try:
        pids = sorted({int(p) for p in (provinces or [])})
    except Exception:
        return {"ok": False, "msg": "省份列表不合法"}
    if not pids:
        return {"ok": False, "msg": "至少要给一个省"}

    top, states_dir = _states_dir_for_write(root)
    if not top or not states_dir:
        return {"ok": False, "msg": "找不到可写的 mod 目录（原版只读）"}

    # 省份必须存在于地图上
    _ensure_prov_rgb(root)
    known = set(PROV_RGB)
    missing = [p for p in pids if p not in known]
    if missing:
        return {"ok": False, "msg": "这些省在地图上不存在：%s" % ", ".join(map(str, missing[:8]))}

    # 目标州 id
    if sid in (None, "", 0):
        new_id = _free_state_id()
    else:
        try:
            new_id = int(sid)
        except Exception:
            return {"ok": False, "msg": "州 id 不合法"}
        if str(new_id) in STATES or new_id in STATES:
            return {"ok": False, "msg": "州 %d 已经存在" % new_id}

    # 从原州移出
    moved_from = []
    for pid in pids:
        cur = _find_state_of_prov(pid)
        if cur is None:
            continue
        _r, _rel, fpath = _state_file_for(cur)
        if not fpath or is_under_game(_r or ""):
            continue
        try:
            text, has_bom = _read_bom_text(fpath)
            loc = _state_locate(text)
            if not loc:
                continue
            b, e = loc
            body = text[b + 1:e - 1]
            old = _parse_state_provinces(body)
            new = [p for p in old if p != pid]
            new_text = text[:b + 1] + _set_state_provinces(body, new) + text[e - 1:]
            snapshot(fpath)
            _write_bom_text(fpath, new_text, has_bom)
            CHANGED[fpath] = _rel or os.path.relpath(fpath, _r or root)
            if cur not in moved_from:
                moved_from.append(cur)
        except Exception as e2:
            print("移出原州失败:", pid, e2)

    # HOI4 里 state 的 name 是本地化键，不能直接写中文；显示名写进 loc 文件
    display_name = (name or "").strip()
    st_name = "STATE_%d" % new_id
    cat = (category or "rural").strip()
    try:
        mp = int(manpower)
    except Exception:
        mp = 100000
    body_lines = [
        "state = {",
        "\tid = %d" % new_id,
        '\tname = "%s"' % st_name,
        "\tmanpower = %d" % mp,
        "\tstate_category = %s" % cat,
        "\tprovinces = {",
    ]
    body_lines += ["\t\t%d" % p for p in pids]
    body_lines += ["\t}", "\tlocal_supplies = 0.0", "}", ""]
    content = "\n".join(body_lines)

    os.makedirs(states_dir, exist_ok=True)
    _fname_base = re.sub(r'[^\w\u4e00-\u9fa5-]+', "_", (display_name or st_name))[:40]
    fname = "%d - %s.txt" % (new_id, _fname_base)
    fpath = os.path.join(states_dir, fname)
    if os.path.exists(fpath):
        return {"ok": False, "msg": "文件已存在：%s" % fname}
    try:
        io.open(fpath, "w", encoding="utf-8", newline="").write(content)
    except Exception as e:
        return {"ok": False, "msg": "写文件失败：%s" % e}

    # 内存里也建一条，界面立刻能用
    STATES[new_id] = {
        "id": new_id, "name": st_name, "manpower": str(mp), "category": cat,
        "provinces": pids, "owner": "", "cores": [], "victory_points": {},
        "buildings": {}, "path": fpath, "file": fpath, "source": os.path.basename(top),
        "root": top, "rel": os.path.relpath(fpath, top), "created": True,
    }
    CHANGED[fpath] = os.path.relpath(fpath, top)

    # 本地化：把显示名写进 loc（yml 必须带 BOM，否则游戏读不到）
    loc_written = ""
    if display_name:
        try:
            loc_dir = os.path.join(top, "localisation", "simp_chinese")
            os.makedirs(loc_dir, exist_ok=True)
            loc_path = os.path.join(loc_dir, "zz_xuerong_state_names_l_simp_chinese.yml")
            line = ' %s:0 "%s"' % (st_name, display_name.replace('"', "'"))
            if os.path.exists(loc_path):
                old_txt = io.open(loc_path, encoding="utf-8-sig", errors="replace").read()
                if st_name not in old_txt:
                    body = old_txt.rstrip()
                    if not body.endswith("}"):
                        body = body.rstrip() + chr(10)
                    new_txt = body + line + chr(10)
                else:
                    new_txt = None
            else:
                new_txt = "l_simp_chinese:" + chr(10) + line + chr(10)
            if new_txt:
                snapshot(loc_path) if os.path.exists(loc_path) else None
                with io.open(loc_path, "w", encoding="utf-8-sig", newline="") as f:
                    f.write(new_txt)
                loc_written = os.path.relpath(loc_path, top)
                CHANGED[loc_path] = loc_written
        except Exception as e3:
            print("写本地化失败:", e3)

    return {"ok": True, "id": new_id, "name": st_name, "display": display_name,
            "loc": loc_written, "provinces": pids,
            "file": os.path.relpath(fpath, top), "moved_from": moved_from,
            "note": ("已写入本地化 %s" % loc_written) if loc_written else ("未填显示名，游戏里会显示 %s" % st_name)}


def _map_files_strict(root):


    """严格模式：沿叠加链找地图（子 mod 没有地图时用父 mod 的），整条链都没有才返回 None。
    返回的地图 bmp 可能来自父 mod，但 base 仍报请求的 root，便于界面区分"数据来自哪里"。"""
    if not root:
        return None, None, None
    b, d, provider, layers = _map_files_layered(root)
    if not b or not d:
        return None, None, None
    return b, d, provider


def map_meta(root=None):
    root = _map_pick(root)
    b, d, base = _map_files_strict(root)
    if not b:
        return {"ok": False, "msg": "这个来源没有 map/provinces.bmp 或 definition.csv",
                "sources": map_sources(), "picked": root}
    dirp, key, base = _map_dir(root)
    built = bool(dirp and os.path.exists(os.path.join(dirp, "meta.json")))
    meta = {}
    if built:
        try:
            meta = json.loads(io.open(os.path.join(dirp, "meta.json"), encoding="utf-8").read())
        except Exception:
            meta = {}
    # 缓存过期：同一来源以前构建过，但缓存键变了（数据或版本改动）
    stale = False
    prev = {}
    lastp = os.path.join(MAP_CACHE_DIR, "_last.json")
    if os.path.exists(lastp):
        try:
            prev = json.loads(io.open(lastp, encoding="utf-8").read())
        except Exception:
            prev = {}
    if not built and prev.get("root") and os.path.abspath(prev.get("root")) == os.path.abspath(base or ""):
        stale = prev.get("key") != key
    layers = mod_layers(root)
    return {"ok": True, "built": built, "stale": stale, "dir": dirp, "source": base, "stamp": key,
            "prev_built": prev.get("built"), "meta": meta, "picked": root,
            "layers": [{"path": x,
                        "name": os.path.basename(x.replace("\\", "/").rstrip("/")) or x,
                        "is_game": os.path.abspath(x) == os.path.abspath(GAME or ""),
                        "descriptor_file": os.path.join(x, "descriptor.mod"),
                        "has_descriptor": os.path.exists(os.path.join(x, "descriptor.mod")),
                        "mod_name": _mod_descriptor(x)["name"],
                        "deps": _mod_descriptor(x)["deps"],
                        "replace_count": len(_mod_descriptor(x)["replace"])}
                       for x in layers],
            "sources": map_sources()}


MAP_PALETTE = ((196, 112, 92), (96, 138, 186), (150, 158, 96),
               (188, 150, 84), (118, 132, 168), (168, 120, 148))


def _hsv_hex(i, sat=0.52, val=0.88):
    """6 色循环 + 按 id 的轻微明度扰动：相邻省不撞色，整体也不花"""
    i = int(i)
    base = MAP_PALETTE[i % len(MAP_PALETTE)]
    d = ((i * 37) % 44) - 22
    return bytes(max(10, min(246, c + d)) for c in base)


def map_build(force=False, root=None):
    """生成地图图层（首次约 13 秒），返回 meta。可按 root 指定来源。"""
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "还没有加载任何 mod"}
    bmp, csv, base = _map_files_strict(root)
    if not bmp:
        return {"ok": False, "msg": "这个来源没有 map/provinces.bmp 或 definition.csv",
                "sources": map_sources(), "picked": root}
    dirp, key, base = _map_dir(root)
    if not dirp:
        return {"ok": False, "msg": "无法创建缓存目录"}
    os.makedirs(dirp, exist_ok=True)
    meta_path = os.path.join(dirp, "meta.json")
    try:
        os.makedirs(MAP_CACHE_DIR, exist_ok=True)
        io.open(os.path.join(MAP_CACHE_DIR, "_last.json"), "w", encoding="utf-8", newline="").write(
            json.dumps({"root": os.path.abspath(base or ""), "key": key,
                        "built": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False))
    except Exception:
        pass
    if not force and os.path.exists(meta_path):
        try:
            return {"ok": True, "cached": True,
                    "meta": json.loads(io.open(meta_path, encoding="utf-8").read())}
        except Exception:
            pass

    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    t_all = time.time()

    # 1) definition.csv：颜色 -> 省 id
    color2prov = {}
    prov2type = {}
    prov2terrain = {}
    prov2continent = {}
    with io.open(csv, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split(";")
            if len(parts) < 5:
                continue
            try:
                pid = int(parts[0])
                rgb = (int(parts[1]), int(parts[2]), int(parts[3]))
            except Exception:
                continue
            color2prov[rgb] = pid
            prov2type[pid] = parts[4] or "land"
            if len(parts) > 6:
                prov2terrain[pid] = (parts[6] or "").strip()
            if len(parts) > 7:
                try:
                    prov2continent[pid] = int(parts[7])
                except Exception:
                    pass

    # 2) 读图
    im = Image.open(bmp).convert("RGB")
    w, h = im.size
    raw = im.tobytes()

    # 3) 省 -> 州
    prov2state = {}
    for sid, st in STATES.items():
        try:
            sid_int = int(st.get("id") or sid)
        except Exception:
            continue
        for p in (st.get("provinces") or []):
            try:
                prov2state[int(p)] = sid_int
            except Exception:
                pass

    # 3.5) 政治视图：省 -> owner -> 国家颜色
    prov2owner = {}
    for sid, st in STATES.items():
        ow = (st.get("owner") or "").strip()
        if not ow:
            continue
        for p in (st.get("provinces") or []):
            try:
                prov2owner[int(p)] = ow
            except Exception:
                pass
    tag_color = {}
    tag_color_real = {}
    for tag, c in COUNTRIES.items():
        col = c.get("color") or []
        if len(col) >= 3:
            _c = bytes((max(0, min(255, int(col[0] * 255))),
                        max(0, min(255, int(col[1] * 255))),
                        max(0, min(255, int(col[2] * 255)))))
            tag_color[tag] = _c
            tag_color_real[tag] = _c
        else:
            tag_color[tag] = bytes((132, 132, 132))
    neutral = bytes((46, 50, 46))
    oceanc = bytes((26, 42, 74))          # 海色：比无主陆地明显的蓝
    ptypes = _prov_type_map(root)

    # 3.6) 战略区
    prov2region, region_list = _strategic_regions(root)

    # 3.7) 地形：用游戏自己的配色，再叠 terrain.bmp 的明暗做出纹理感
    _tcols = {}
    try:
        _tcols = _terrain_colors(root)
    except Exception as _e:
        print("读地形配色失败:", _e)
    # 旧的「terrain.bmp 灰度明暗」已弃用：现在统一用 heightmap 的真实山体阴影
    # （_apply_hillshade）。两套叠一起会把颜色压暗一倍。
    _shade = None

    # 4) 一遍像素：ids、质心累加
    n = w * h
    ids = [0] * n
    sumx = {}
    sumy = {}
    cnts = {}
    lookup = color2prov
    unset_px = 0          # 颜色在 definition.csv 里找不到的像素
    for i in range(n):
        o = i * 3
        pid = lookup.get((raw[o], raw[o + 1], raw[o + 2]))
        if pid is None:
            pid = 0
            unset_px += 1
        ids[i] = pid
        if pid:
            sumx[pid] = sumx.get(pid, 0) + (i % w)
            sumy[pid] = sumy.get(pid, 0) + (i // w)
            cnts[pid] = cnts.get(pid, 0) + 1

    # 4.5) 地图定义一致性（definition.csv ↔ provinces.bmp）
    try:
        PROV_RGB.clear()
        for _rgb, _pid in color2prov.items():
            PROV_RGB[int(_pid)] = _rgb
    except Exception:
        pass
    csv_ids = set(color2prov.values())
    bmp_ids = set(cnts)
    ghost = sorted(csv_ids - bmp_ids)          # 定义了但地图上没有像素
    # 同色多个省（后写覆盖前写，前面的 id 永远不会出现）
    rgb_count = {}
    for _rgb, _pid in color2prov.items():
        rgb_count.setdefault(_rgb, []).append(_pid)
    dup_rgb = {k: v for k, v in rgb_count.items() if len(v) > 1}
    consistency = {
        "csv_ids": len(csv_ids),
        "bmp_ids": len(bmp_ids),
        "ghost": len(ghost),
        "ghost_sample": ghost[:20],
        "unset_pixels": unset_px,
        "unset_ratio": round(unset_px * 100.0 / max(1, n), 3),
        "dup_rgb": len(dup_rgb),
        "dup_rgb_sample": [{"rgb": list(k), "ids": v[:5]} for k, v in list(dup_rgb.items())[:10]],
    }

    # 5) 图层缓冲
    provbuf = bytearray(n * 3)
    statebuf = bytearray(n * 3)
    polbuf = bytearray(n * 3)
    regbuf = bytearray(n * 3)
    terrbuf = bytearray(n * 3)
    contbuf = bytearray(n * 3)
    edgebuf = bytearray(n * 3)
    idbuf = bytearray(n * 3)
    prov_color = {}
    state_color = {}
    reg_color = {}
    terr_color = {}
    cont_color = {}
    for i in range(n):
        pid = ids[i]
        c = prov_color.get(pid)
        if c is None:
            c = _hsv_hex(pid, 0.72, 0.96) if pid else bytes((24, 28, 26))
            prov_color[pid] = c
        sid = prov2state.get(pid, 0)
        sc = state_color.get(sid)
        if sc is None:
            sc = _hsv_hex(sid + 7, 0.62, 0.92) if sid else bytes((30, 34, 32))
            state_color[sid] = sc
        o = i * 3
        provbuf[o:o + 3] = c
        statebuf[o:o + 3] = sc
        ow = prov2owner.get(pid, "")
        if ow:
            pcb = tag_color.get(ow)
            if pcb is None:
                # 国家表里没有这个 tag（mod 改了国家但州还引用旧 tag），
                # 按 tag 生成稳定色，而不是画成无主灰
                pcb = _tag_fallback_color(ow)
                tag_color[ow] = pcb
        else:
            # 没有归属国的省分两种：海洋给海色，无主陆地给中性灰
            ptype = ptypes.get(pid, "")
            pcb = oceanc if ptype in ("sea", "ocean", "lake") else neutral
        polbuf[o:o + 3] = pcb
        # 地形：按 definition.csv 的 terrain 名字取稳定色
        tname = prov2terrain.get(pid, "")
        tc = terr_color.get(tname)
        if tc is None:
            _base = _tcols.get(tname)
            if _base:
                tc = bytes(_base)
            elif tname:
                tc = _hsv_hex(zlib.crc32(tname.encode("utf-8")) % 997, 0.35, 0.72)
            else:
                tc = bytes((26, 30, 28))
            terr_color[tname] = tc
        if _shade is not None:
            # 明暗系数 0.72~1.18，让同一种地形也有起伏感
            _f = 0.72 + (_shade[i] / 255.0) * 0.46
            terrbuf[o] = min(255, int(tc[0] * _f))
            terrbuf[o + 1] = min(255, int(tc[1] * _f))
            terrbuf[o + 2] = min(255, int(tc[2] * _f))
        else:
            terrbuf[o:o + 3] = tc
        # 大洲
        con = prov2continent.get(pid, 0)
        cc2 = cont_color.get(con)
        if cc2 is None:
            cc2 = _hsv_hex(con * 7 + 11, 0.40, 0.78) if con else bytes((30, 34, 32))
            cont_color[con] = cc2
        contbuf[o:o + 3] = cc2
        rid = prov2region.get(pid, 0)
        rc = reg_color.get(rid)
        if rc is None:
            rc = _hsv_hex(rid + 3, 0.38, 0.72) if rid else bytes((28, 32, 30))
            reg_color[rid] = rc
        regbuf[o:o + 3] = rc
        idbuf[o] = (pid >> 16) & 0xFF
        idbuf[o + 1] = (pid >> 8) & 0xFF
        idbuf[o + 2] = pid & 0xFF

    # 6) 省界（4 邻域不同即标白）
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            pid = ids[i]
            edge = False
            if x + 1 < w and ids[i + 1] != pid:
                edge = True
            elif y + 1 < h and ids[i + w] != pid:
                edge = True
            elif x > 0 and ids[i - 1] != pid:
                edge = True
            elif y > 0 and ids[i - w] != pid:
                edge = True
            if edge:
                o = i * 3
                # 淡灰而不是纯白：放大后边界线仍然可见但不会压过色块
                edgebuf[o] = 205
                edgebuf[o + 1] = 209
                edgebuf[o + 2] = 203

    # 6.5) 国家边界：相邻省属于不同 owner 的地方压深一档
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            pid = ids[i]
            ow = prov2owner.get(pid, "")
            border = False
            if x + 1 < w:
                ow2 = prov2owner.get(ids[i + 1], "")
                if ow2 != ow:
                    border = True
            elif y + 1 < h:
                ow3 = prov2owner.get(ids[i + w], "")
                if ow3 != ow:
                    border = True
            if border:
                o = i * 3
                polbuf[o] = min(255, int(polbuf[o] * 0.45))
                polbuf[o + 1] = min(255, int(polbuf[o + 1] * 0.45))
                polbuf[o + 2] = min(255, int(polbuf[o + 2] * 0.45))

    # 7) 写资产
    Image.frombytes("RGB", (w, h), bytes(provbuf)).save(os.path.join(dirp, "province.png"))
    Image.frombytes("RGB", (w, h), bytes(statebuf)).save(os.path.join(dirp, "state.png"))
    # 省界存成 RGBA：白线不透明、其余全透明。
    # 之前存 RGB（黑底白线），前端按 opacity 叠上去时黑色背景会把地形压暗一大截。
    _edge_img = Image.frombytes("RGB", (w, h), bytes(edgebuf)).convert("RGBA")
    _edge_img.putalpha(_edge_img.convert("L"))
    _edge_img.save(os.path.join(dirp, "edges.png"))
    Image.frombytes("RGB", (w, h), bytes(polbuf)).save(os.path.join(dirp, "political.png"))
    # 严格版：国家表里查不到的 tag 不参与着色，落到无主色（还原游戏里的真实政治图）
    try:
        stbuf = bytearray(polbuf)
        for i in range(n):
            pid = ids[i]
            ow = prov2owner.get(pid, "")
            if not ow or ow in tag_color_real:
                continue
            o = i * 3
            ptype = ptypes.get(pid, "")
            stbuf[o:o + 3] = oceanc if ptype in ("sea", "ocean", "lake") else neutral
        Image.frombytes("RGB", (w, h), bytes(stbuf)).save(
            os.path.join(dirp, "political_strict.png"))
    except Exception as _e:
        print("  严格版政治图跳过:", _e)
    Image.frombytes("RGB", (w, h), bytes(regbuf)).save(os.path.join(dirp, "region.png"))
    _terr_img = _render_terrain(root, w, h, prov2terrain)
    if _terr_img is None:
        # 省级地形色（来自 definition.csv，永远可信）+ 高度阴影
        _terr_img = Image.frombytes("RGB", (w, h), bytes(terrbuf))
        try:
            _terr_img = _apply_hillshade(_terr_img, root, w, h, None)
        except Exception as _e:
            print("  高度阴影失败，保留纯色:", _e)
    _terr_img.save(os.path.join(dirp, "terrain.png"))
    Image.frombytes("RGB", (w, h), bytes(contbuf)).save(os.path.join(dirp, "continent.png"))
    try:
        _build_rivers_png(root, w, h, dirp)
    except Exception as _e:
        print("  河流图层跳过:", _e)
    Image.frombytes("RGB", (w, h), bytes(idbuf)).save(os.path.join(dirp, "prov_id.png"))
    # 底图用全分辨率：缩进一半的话放大后是糊的（游戏地图本来就只有这个尺寸，没得再高）
    im.save(os.path.join(dirp, "base.png"))

    centers = {}
    counts = cnts
    for pid, cnt in counts.items():
        centers[str(pid)] = [round(sumx[pid] / cnt, 1), round(sumy[pid] / cnt, 1)]

    index = {}
    for pid, cnt in counts.items():
        _rgb = None
        try:
            _rgb = list(color2prov and next((k for k, v in color2prov.items() if v == pid), None) or ()) or None
        except Exception:
            _rgb = None
        index[str(pid)] = {"state": prov2state.get(pid, 0), "type": prov2type.get(pid, ""),
                           "region": prov2region.get(pid, 0), "terrain": prov2terrain.get(pid, ""),
                           "continent": prov2continent.get(pid, 0), "px": cnt,
                           "rgb": _rgb}

    io.open(os.path.join(dirp, "centers.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(centers, ensure_ascii=False))
    io.open(os.path.join(dirp, "prov_index.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(index, ensure_ascii=False))
    io.open(os.path.join(dirp, "regions.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(region_list, ensure_ascii=False))

    meta = {"w": w, "h": h, "provinces": len(counts), "source": base,
            "ms": int((time.time() - t_all) * 1000), "built": time.strftime("%Y-%m-%d %H:%M:%S"),
            "consistency": consistency,
            "assets": {a: os.path.getsize(os.path.join(dirp, a)) for a in MAP_ASSETS
                       if os.path.exists(os.path.join(dirp, a))}}
    io.open(meta_path, "w", encoding="utf-8", newline="").write(json.dumps(meta, ensure_ascii=False))
    return {"ok": True, "cached": False, "meta": meta}


def map_cache_clear():
    """清空所有地图图层缓存（源文件不动，下次打开自动重建）"""
    total = 0
    n = 0
    if os.path.isdir(MAP_CACHE_DIR):
        for name in sorted(os.listdir(MAP_CACHE_DIR)):
            p = os.path.join(MAP_CACHE_DIR, name)
            if not os.path.isdir(p):
                continue
            size = 0
            for dp, _, fs in os.walk(p):
                for f in fs:
                    try:
                        size += os.path.getsize(os.path.join(dp, f))
                    except Exception:
                        pass
            shutil.rmtree(p, ignore_errors=True)
            total += size
            n += 1
    return {"ok": True, "dirs": n, "bytes": total,
            "msg": "已清理 %d 个来源的缓存，释放 %.1f MB" % (n, total / 1e6)}


def _set_state_provinces(body, pids):
    """重建 state 文件里的 provinces = { ... } 列表"""
    pids = sorted(set(int(p) for p in pids))
    inner = "\n" + "".join("\t\t%d\n" % p for p in pids) + "\t"
    m = re.search(r'(?m)^[ \t]*provinces\s*=\s*\{', body)
    if m:
        b = body.find('{', m.end() - 1)
        e = brace_match(body, b)
        if e > b:
            return body[:b + 1] + inner + body[e - 1:]
    line = "provinces={\n" + "".join("\t\t%d\n" % p for p in pids) + "\t}"
    nm = re.search(r'(?m)^[ \t]*name\s*=\s*"[^"]*"', body)
    if nm:
        return body[:nm.end()] + "\n\t" + line + body[nm.end():]
    return body.rstrip() + "\n\t" + line + "\n"


def _parse_state_provinces(body):
    """从 state 块文本里读出 provinces 列表（不依赖内存 STATES）"""
    m = re.search(r'(?m)^[ \t]*provinces\s*=\s*\{', body)
    if not m:
        return []
    b = body.find('{', m.end() - 1)
    e = brace_match(body, b)
    if e <= b:
        return []
    return [int(x) for x in re.findall(r'\d+', body[b + 1:e - 1])]


def _find_state_of_prov(pid):
    """扫 state 文件，找出哪个州包含这个省"""
    for root in ROOTS:
        d = os.path.join(root, "history", "states")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            p = os.path.join(d, fn)
            try:
                text = _read_text(p)
            except Exception:
                continue
            m = re.search(r'(?m)^[ \t]*id\s*=\s*(\d+)', text)
            if not m:
                continue
            loc = _state_locate(text)
            if not loc:
                continue
            b, e = loc
            if int(pid) in _parse_state_provinces(text[b + 1:e - 1]):
                return int(m.group(1))
    return None


def _state_file_for(sid):
    """按州 id 找文件路径：(root, rel, path)。

    优先用 STATES 里已经定下来的那条记录 —— 同一个 id 在多个文件里出现时
    （比如原版有 1-France.txt、mod 又加了 1-Corsica.txt），
    按文件名遍历会挑到和 STATES 不一致的那一个，后续写入就落到错误文件。"""
    try:
        _s = STATES.get(int(sid)) if isinstance(STATES, dict) else None
    except Exception:
        _s = None
    if _s and _s.get("root") and _s.get("file"):
        _p = os.path.join(_s["root"], _s["file"])
        if os.path.exists(_p):
            return _s["root"], _s["file"], _p

    _bases = []
    for _r in (ROOTS or []):
        for _b in (mod_layers(_r) or [_r]):
            if _b and os.path.abspath(_b) not in [os.path.abspath(x) for x in _bases]:
                _bases.append(_b)
    for root in reversed(_bases):
        d = os.path.join(root, "history", "states")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            p = os.path.join(d, fn)
            try:
                text = _read_text(p)
            except Exception:
                continue
            m = re.search(r'(?m)^[ \t]*id\s*=\s*(\d+)', text)
            if m and int(m.group(1)) == int(sid):
                return root, os.path.join("history", "states", fn), p
    return None, None, None


def state_province_edit(pid, target_sid=None):
    """把省 pid 移到 target_sid 州；target_sid 为空表示移出当前州"""
    try:
        pid = int(pid)
    except Exception:
        return {"ok": False, "msg": "省 id 不合法"}
    if pid <= 0:
        return {"ok": False, "msg": "省 id 不合法"}
    target = None
    if target_sid not in (None, "", 0, "0"):
        try:
            target = int(target_sid)
        except Exception:
            return {"ok": False, "msg": "目标州 id 不合法"}

    cur_sid = _find_state_of_prov(pid)
    if target is not None and cur_sid == target:
        return {"ok": True, "msg": "省 %d 已经在州 %d 里了" % (pid, target), "noop": True}

    diff = []
    if cur_sid is not None:
        root, rel, path = _state_file_for(cur_sid)
        if not path:
            return {"ok": False, "msg": "找不到州 %s 的文件" % cur_sid}
        if is_under_game(root):
            return {"ok": False, "msg": "州 %d 在原版目录里，只读" % cur_sid}
        text, has_bom = _read_bom_text(path)
        loc = _state_locate(text)
        if not loc:
            return {"ok": False, "msg": "州 %d 文件里找不到 state 块" % cur_sid}
        _b, _e = loc
        body = text[_b + 1:_e - 1]
        old = _parse_state_provinces(body)
        new = [p for p in old if p != pid]
        new_text = text[:_b + 1] + _set_state_provinces(body, new) + text[_e - 1:]
        snapshot(path)
        _write_bom_text(path, new_text, has_bom)
        diff.append({"key": "st_%d" % cur_sid, "label": "州 %d 省份" % cur_sid,
                     "old": "%d 个省" % len(old), "new": "%d 个省" % len(new)})
        CHANGED[path] = rel

    if target is not None:
        root, rel, path = _state_file_for(target)
        if not path:
            return {"ok": False, "msg": "找不到州 %d 的文件" % target}
        if is_under_game(root):
            return {"ok": False, "msg": "州 %d 在原版目录里，只读" % target}
        text, has_bom = _read_bom_text(path)
        loc = _state_locate(text)
        if not loc:
            return {"ok": False, "msg": "州 %d 文件里找不到 state 块" % target}
        _b, _e = loc
        body = text[_b + 1:_e - 1]
        old = _parse_state_provinces(body)
        new = sorted(set(old) | {pid})
        new_text = text[:_b + 1] + _set_state_provinces(body, new) + text[_e - 1:]
        snapshot(path)
        _write_bom_text(path, new_text, has_bom)
        diff.append({"key": "st_%d" % target, "label": "州 %d 省份" % target,
                     "old": "%d 个省" % len(old), "new": "%d 个省" % len(new)})
        CHANGED[path] = rel

    reload_data()
    link_countries()
    if target is None:
        msg = "省 %d 已从州 %s 移出" % (pid, cur_sid)
    elif cur_sid:
        msg = "省 %d：州 %s → 州 %d" % (pid, cur_sid, target)
    else:
        msg = "省 %d 已加入州 %d" % (pid, target)
    return {"ok": True, "msg": msg, "diff": diff, "from": cur_sid, "to": target}


# v0.80 战略区图层
_REGION_CACHE = {}


def _strategic_regions(root):
    """读 map/strategicregions/*.txt，返回 {province: region_id} 与 region 列表。
    带 mtime 缓存：合并预览/涂色都要用，不缓存每次白花 1.5 秒。"""
    try:
        _sig = None
        for _b in (root, GAME):
            _d = os.path.join(_b or "", "map", "strategicregions")
            if os.path.isdir(_d):
                _mt = 0
                try:
                    for _fn in os.listdir(_d):
                        _mt = max(_mt, int(os.path.getmtime(os.path.join(_d, _fn))))
                except Exception:
                    pass
                _sig = (os.path.abspath(_b or ""), _mt)
                break
        _hit = _REGION_CACHE.get(_sig)
        if _hit:
            return dict(_hit[0]), list(_hit[1])
    except Exception:
        _sig = None
    _orig_note = None
    prov2region = {}
    regions = []
    for base in (root, GAME):
        d = os.path.join(base or "", "map", "strategicregions")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'strategic_region\s*=\s*\{', text):
                b = text.find('{', m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                rid = _first(body, r'(?m)^[ \t]*id\s*=\s*(\d+)')
                if not rid:
                    continue
                rid = int(rid)
                nm = _first(body, r'(?m)^[ \t]*name\s*=\s*"?([^"\r\n]+)"?') or ("地区 %d" % rid)
                pm = re.search(r'(?m)^[ \t]*provinces\s*=\s*\{', body)
                pids = []
                if pm:
                    pb = body.find('{', pm.end() - 1)
                    pe = brace_match(body, pb)
                    if pe > pb:
                        pids = [int(x) for x in re.findall(r'\d+', body[pb + 1:pe - 1])]
                for p in pids:
                    prov2region[p] = rid
                regions.append({"id": rid, "name": nm, "count": len(pids)})
        if regions:
            break
    try:
        if _sig:
            _REGION_CACHE[_sig] = (dict(prov2region), list(regions))
    except Exception:
        pass
    return prov2region, regions


# v0.85 地图完整性检查
# v1.2 地形层：游戏配色 + 高度图山体阴影（全 Pillow，快 70 倍）
def _terrain_index_map(root):
    """解析 common/terrain/*.txt：地形索引 → 类别名"""
    idx2type = {}
    for base in reversed(mod_layers(root)):
        d = os.path.join(base or "", "common", "terrain")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8-sig",
                                              errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'(?m)^\s*([A-Za-z_][\w]*)\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                typ = re.search(r'type\s*=\s*(\w+)', body)
                col = re.search(r'color\s*=\s*\{\s*(\d+)\s*\}', body)
                if typ and col:
                    idx2type[int(col.group(1))] = typ.group(1)
    return idx2type


def _hillshade_mask(root, w, h):
    """高度图 → 明暗 mask（L 模式，255=全亮）。没有高度图或尺寸不符返回 None。"""
    try:
        from PIL import Image, ImageChops
        Image.MAX_IMAGE_PIXELS = None
        hbmp, _ = _layers_find("map/heightmap.bmp", mod_layers(root))
        if not hbmp:
            return None
        with Image.open(hbmp) as him:
            if him.size != (w, h):
                return None
            hh = him.convert("L")
        gx = ImageChops.subtract(ImageChops.offset(hh, 1, 0),
                                 ImageChops.offset(hh, -1, 0), 1.0, 128)
        gy = ImageChops.subtract(ImageChops.offset(hh, 0, 1),
                                 ImageChops.offset(hh, 0, -1), 1.0, 128)

        def lit(v):
            # 西北光：东侧高、南侧高的地形变暗。系数小一点，避免山地整片压黑
            return max(0, min(255, int(128 - (v - 128) * 0.70)))
        shade = ImageChops.add(gx.point(lit), gy.point(lit), 1.0, -128)
        # 下限 108：最暗处也保留约 42% 亮度，当作环境光，不让背光坡变成黑块
        return shade.point(lambda v: max(108, min(255, int(v * 1.28))))
    except Exception:
        return None


def _apply_hillshade(img, root, w, h, ocean_mask=None):
    """给地形色图叠高度阴影。ocean_mask 为 L 模式，255 = 海洋（用弱阴影）。

    用乘法光照而不是 composite（后者会把背光面压到接近黑）：
      先把底色提亮 1.35 倍，再乘一个 0.72~1.27 的系数，
      最终亮度 = 底色 × (0.97 ~ 1.71)，中间值约 1.32 倍，暗部仍有 0.97 倍。"""
    from PIL import Image, ImageChops
    Image.MAX_IMAGE_PIXELS = None
    shade = _hillshade_mask(root, w, h)
    if shade is None:
        return img
    bright = img.point(lambda v: min(255, int(v * 1.35)))
    # m/255 = (0.72 + 0.55*s) / 1.35
    factor = shade.point(lambda v: max(1, min(255, int(189 * (0.72 + 0.55 * (v / 255.0))))))
    out = ImageChops.multiply(bright, factor.convert("RGB"))
    if ocean_mask is not None:
        # 海洋/湖泊只用很弱的起伏
        soft = ImageChops.multiply(img.point(lambda v: min(255, int(v * 1.06))),
                                   shade.point(lambda v: max(150, min(255, int(v * 1.6)))).convert("RGB"))
        out = Image.composite(soft, out, ocean_mask)
    return out


def _terrain_tex_map(root):
    """terrain.txt 的 terrain_N -> {color索引: (type, texture编号)}"""
    idx2type, idx2tex = {}, {}
    for base in reversed(mod_layers(root)):
        d = os.path.join(base or "", "common", "terrain")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8-sig",
                                              errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'(?m)^\s*([A-Za-z_][\w]*)\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                typ = re.search(r'type\s*=\s*(\w+)', body)
                col = re.search(r'color\s*=\s*\{\s*(\d+)\s*\}', body)
                tex = re.search(r'texture\s*=\s*(\d+)', body)
                if typ and col and tex:
                    k = int(col.group(1))
                    idx2type[k] = typ.group(1)
                    idx2tex[k] = int(tex.group(1))
    return idx2type, idx2tex


def _apply_terrain_texture(img, root, w, h, tmap, ids):
    """用 map/terrain/atlas0.dds 的贴图亮度调制地形色明暗。

    只调亮度不混色：贴图本身是灰色调细节层，直接 alpha 混合会把地形色洗掉。
    海洋/湖泊跳过——atlas 里没有水面贴图（借用 desert 的），会把海面弄成斑块。
    纹理起点按省号哈希偏移，相邻省的花纹不会对齐。"""
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        atlas_path, _ = _layers_find("map/terrain/atlas0.dds", mod_layers(root))
        if not atlas_path:
            _g = os.path.join(GAME or "", "map", "terrain", "atlas0.dds")
            atlas_path = _g if os.path.exists(_g) else None
        if not atlas_path or not tmap:
            return img
        with Image.open(atlas_path) as aim:
            atlas = aim.convert("RGBA")
        TILE = atlas.width // 8
        if TILE <= 0:
            return img
        idx2type, idx2tex = _terrain_tex_map(root)
        if not idx2tex:
            return img
        apx = atlas.load()
        traw = tmap.tobytes()
        src = img.tobytes()
        out = bytearray(src)
        cache = {}
        water = ("ocean", "lakes")
        n = w * h
        for i in range(n):
            ti = traw[i]
            typ = idx2type.get(ti)
            m = idx2tex.get(ti)
            if m is None or m > 63 or typ in water:
                continue
            pid = ids[i] if ids else 0
            ax = (i % w + (pid * 37)) % TILE
            ay = (i // w + (pid * 71)) % TILE
            key = (m, ax, ay)
            tc = cache.get(key)
            if tc is None:
                tc = apx[(m % 8) * TILE + ax, (m // 8) * TILE + ay]
                if len(cache) < 300000:
                    cache[key] = tc
            luma = tc[0] * 0.30 + tc[1] * 0.59 + tc[2] * 0.11
            f = 0.74 + (luma / 255.0) * 0.56
            a = tc[3] / 255.0
            f = 1.0 + (f - 1.0) * (0.50 + a * 0.50)
            o = i * 3
            r = src[o] * f
            g = src[o + 1] * f
            b = src[o + 2] * f
            out[o] = 255 if r > 255 else int(r)
            out[o + 1] = 255 if g > 255 else int(g)
            out[o + 2] = 255 if b > 255 else int(b)
        return Image.frombytes("RGB", (w, h), bytes(out))
    except Exception as e:
        print("地形贴图失败，保留纯色:", e)
        return img


def _terrain_index_trusted(root, layers):
    """terrain.bmp 是否与 provinces.bmp 同源。
    不同源说明 mod 换了地图却没换地形索引图，用它着色会得到与地图无关的分布。"""
    try:
        _t, tbase = _layers_find("map/terrain.bmp", layers)
        _p, pbase = _layers_find("map/provinces.bmp", layers)
        if not _t or not _p:
            return False
        return os.path.abspath(tbase or "") == os.path.abspath(pbase or "")
    except Exception:
        return False


def _render_terrain(root, w, h, prov2terrain):
    """像素级地形图（terrain.bmp 可信时用）。返回 RGB Image，不可信或失败返回 None。"""
    try:
        from PIL import Image, ImageChops
        Image.MAX_IMAGE_PIXELS = None
        layers = mod_layers(root)
        if not _terrain_index_trusted(root, layers):
            print("  terrain.bmp 与 provinces.bmp 不同源，改用省级地形着色")
            return None
        tbmp, _ = _layers_find("map/terrain.bmp", layers)
        if not tbmp:
            return None
        cats = _terrain_colors(root)
        idx2type = _terrain_index_map(root)
        if not idx2type:
            return None
        with Image.open(tbmp) as tim:
            if tim.size != (w, h):
                return None
            tmap = tim.convert("P") if tim.mode != "P" else tim.copy()
        pal = [0] * (256 * 3)
        default = (60, 70, 60)
        for i in range(256):
            typ = idx2type.get(i)
            col = cats.get(typ, default) if typ else default
            pal[i * 3] = col[0]
            pal[i * 3 + 1] = col[1]
            pal[i * 3 + 2] = col[2]
        tmap.putpalette(pal)
        base_rgb = tmap.convert("RGB")

        ocean_mask = tmap.convert("L").point(
            lambda v: 255 if idx2type.get(v) in ("ocean", "lakes") else 0)
        base_rgb = _apply_terrain_texture(base_rgb, root, w, h, tmap, None)
        return _apply_hillshade(base_rgb, root, w, h, ocean_mask)
    except Exception as e:
        print("地形渲染失败，回退纯色:", e)
        return None


def _map_ids_from_cache(dirp):


    """从缓存的 prov_id.png 还原 ids 数组（省 id 按 RGB 编码）"""
    from array import array
    from PIL import Image
    p = os.path.join(dirp, "prov_id.png")
    if not os.path.exists(p):
        return None, 0, 0, None
    im = Image.open(p).convert("RGB")
    w, h = im.size
    raw = im.tobytes()
    n = w * h
    ids = array("I", bytes(4 * n))
    a = ids
    for i in range(n):
        o = i * 3
        a[i] = (raw[o] << 16) | (raw[o + 1] << 8) | raw[o + 2]
    return ids, w, h, raw


# ref: CWTools "Code actions to generate .yml for missing localisation"
def _loc_need_keys(root, layers):
    """扫 mod 脚本，收集「应该存在」的本地化键 → {key: 类型}

    只收有明确命名规则的三类：
      focus id = X            → X, X_desc
      country_event id = X    → X.title, X.desc, X.a/.b... 的 option 名不猜
      ideas 里的 X = { }      → X, X_desc
    """
    need = {}
    # 只查 mod 自己写的脚本：原版的几千个事件文件不该算进来
    # （原版本地化本来就不全，查它只会得到一屏无意义的报缺）
    for rel_dir in ("common/national_focus", "events", "common/ideas"):
        _d = os.path.join(root, rel_dir)
        if not os.path.isdir(_d):
            continue
        _files = []
        for _dp, _dn, _fs in os.walk(_d):
            for _fn in _fs:
                if _fn.endswith(".txt"):
                    _files.append(os.path.join(_dp, _fn))
        for f in _files:
            try:
                text = strip_comments(io.open(f, encoding="utf-8-sig", errors="replace").read())
            except Exception:
                continue
            # 文件可能来自别的盘（原版在 E:、mod 在 D:），不能按相对目录算
            rel = os.path.basename(f)
            for _b in layers:
                if _b and os.path.abspath(f).startswith(os.path.abspath(_b) + os.sep):
                    try:
                        rel = os.path.relpath(f, _b)
                    except Exception:
                        rel = os.path.basename(f)
                    break
            # 国策
            for m in re.finditer(r'(?m)^\s*focus\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                fid = re.search(r'(?m)^\s*id\s*=\s*([A-Za-z0-9_.\-]+)', body)
                if not fid:
                    continue
                k = fid.group(1)
                need.setdefault(k, ("focus", rel))
                need.setdefault(k + "_desc", ("focus", rel))
            # 事件
            for m in re.finditer(r'(?m)^\s*(?:country_event|news_event|state_event)\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                eid = re.search(r'(?m)^\s*id\s*=\s*([A-Za-z0-9_.\-]+)', body)
                if not eid:
                    continue
                k = eid.group(1)
                # 事件的本地化键由 title= / desc= 显式给出（常见写法 BETA.1.t / BETA.1.d），
                # 不是固定 id+".title"。没写才回退到默认命名。
                mt = re.search(r'(?m)^\s*title\s*=\s*"?([A-Za-z0-9_.\-]+)"?', body)
                md = re.search(r'(?m)^\s*desc\s*=\s*"?([A-Za-z0-9_.\-]+)"?', body)
                need.setdefault(mt.group(1) if mt else (k + ".title"), ("event", rel))
                need.setdefault(md.group(1) if md else (k + ".desc"), ("event", rel))
            # 国家精神（ideas 里的顶层键；跳过 country/character 这类容器）
            if rel_dir == "common/ideas":
                skip = {"country", "character", "hidden_ideas", "law", "mio", "use_list_view"}
                for m in re.finditer(r'(?m)^\t([A-Za-z0-9_]+)\s*=\s*\{', text):
                    name = m.group(1)
                    if name in skip:
                        continue
                    need.setdefault(name, ("idea", rel))
                    need.setdefault(name + "_desc", ("idea", rel))
    return need


def _loc_defined_set(root):
    """已定义的本地化键 = 原版 LOC + 这个 mod（含所有语言与 replace 子目录）自己的 yml。

    LOC 里只有启动时载入的原版键，mod 的自定义键必须现扫，否则全部误报缺失。"""
    defined = set(LOC.keys())
    line_re = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"')
    for lang in ("simp_chinese", "english", "japanese", "korean", "russian", "french",
                 "german", "spanish", "polish", "portuguese", "braz_por", "turkish"):
        d = os.path.join(root, "localisation", lang)
        if not os.path.isdir(d):
            continue
        for dirpath, _dn, files in os.walk(d):
            for fn in files:
                if not fn.endswith(".yml"):
                    continue
                try:
                    for ln in io.open(os.path.join(dirpath, fn), encoding="utf-8-sig",
                                      errors="replace").read().splitlines():
                        m = line_re.match(ln)
                        if m:
                            defined.add(m.group(1))
                except Exception:
                    pass
    return defined


def loc_missing(root=None, limit=800):
    """列出缺失的本地化键（引用存在但没有任何 yml 定义）"""
    root = _map_pick(root)
    layers = mod_layers(root)
    _defined = _loc_defined_set(root) if root else set(LOC.keys())
    need = _loc_need_keys(root, layers)
    if not need:
        return {"ok": True, "total": 0, "missing": [],
                "msg": "没有找到需要本地化的脚本引用"}
    miss = []
    by_kind = {}
    for k, (kind, src) in need.items():
        if k in _defined:
            continue
        miss.append({"key": k, "kind": kind, "file": src})
        by_kind[kind] = by_kind.get(kind, 0) + 1
    miss.sort(key=lambda x: (x["kind"], x["key"]))
    return {"ok": True, "total": len(miss), "by_kind": by_kind,
            "need": len(need), "defined": len(need) - len(miss),
            "missing": miss[:limit],
            "truncated": len(miss) > limit,
            "msg": "引用 %d 个本地化键，缺 %d 个" % (len(need), len(miss))}


def loc_generate(root=None, keys=None, lang="simp_chinese", dry=False):
    """把缺失的键写进 zz_xuerong_autogen_l_<lang>.yml（占位文本，带 BOM）

    参考 CWTools：只补键不猜内容，占位值用键名本身，方便一眼认出还没翻译。
    """
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "没有加载 mod"}
    layers = mod_layers(root)
    if keys is None:
        r = loc_missing(root, limit=100000)
        keys = [x["key"] for x in r.get("missing") or []]
    _defined2 = _loc_defined_set(root)
    keys = [k for k in (keys or []) if k and k not in _defined2]
    if not keys:
        return {"ok": True, "written": 0, "msg": "没有需要生成的键"}

    lang_dir = os.path.join(root, "localisation", lang)
    fn = os.path.join(lang_dir, "zz_xuerong_autogen_l_%s.yml" % lang)
    if dry:
        return {"ok": True, "dry": True, "count": len(keys), "path": fn,
                "msg": "将写入 %d 个键到 %s" % (len(keys), os.path.basename(fn))}

    # 已有的自动生成文件：保留用户改过的行，只追加新键
    existing = {}
    if os.path.exists(fn):
        try:
            line_re = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"(.*)"\s*$')
            for ln in io.open(fn, encoding="utf-8-sig", errors="replace").read().splitlines():
                m = line_re.match(ln)
                if m:
                    existing[m.group(1)] = m.group(2)
        except Exception:
            pass

    added = 0
    for k in keys:
        if k in existing:
            continue
        existing[k] = k        # 占位值 = 键名
        added += 1
    if not added:
        return {"ok": True, "written": 0, "msg": "这些键都已在自动生成文件里"}

    os.makedirs(lang_dir, exist_ok=True)
    lines = ["l_%s:" % lang]
    for k in sorted(existing):
        v = str(existing[k]).replace('"', "'")
        lines.append(' %s:0 "%s"' % (k, v))
    body = chr(10).join(lines) + chr(10)
    snapshot(fn) if os.path.exists(fn) else None
    io.open(fn, "wb").write(b"\xef\xbb\xbf" + body.encode("utf-8"))
    reload_data()
    return {"ok": True, "written": added, "total": len(existing), "path": fn,
            "msg": "已写入 %d 个键到 %s（占位值=键名，改完重新加载本地化）" % (
                added, os.path.basename(fn))}


# ref: CWTools validator "referenced sprites and graphics files exist"
_GFX_CACHE = {}


def _gfx_collect(root, layers, include_vanilla=True):
    """收集 sprite 定义 → {spriteName: texturefile}，以及 texture 文件集合

    原版的 interface/*.gfx 有 145 个文件、几万个 sprite，只在第一次调用时扫一遍。"""
    key = (os.path.abspath(root or ""), include_vanilla)
    hit = _GFX_CACHE.get(key)
    if hit:
        return hit

    sprites = {}
    textures = set()

    def _scan(base):
        d = os.path.join(base or "", "interface")
        if not os.path.isdir(d):
            return
        for _dp, _dn, files in os.walk(d):
            for fn in files:
                if not fn.endswith(".gfx"):
                    continue
                p = os.path.join(_dp, fn)
                try:
                    text = strip_comments(io.open(p, encoding="utf-8-sig",
                                                  errors="replace").read())
                except Exception:
                    continue
                # 用 brace 配对取每个 spriteType 块：块内还有 frames/instances 等嵌套，
                # 非贪婪正则会在第一个 } 处截断，导致大量 sprite 漏收。
                # 变体：spriteType / corneredTileSpriteType / frameAnimatedSpriteType / progressbartype
                for m in re.finditer(r'(?m)^\s*([A-Za-z_]*[Ss]priteType|progressbartype)\s*=\s*\{',
                                     text):
                    b = text.find("{", m.end() - 1)
                    e = brace_match(text, b)
                    if e <= b:
                        continue
                    body = text[b + 1:e - 1]
                    # name 可以带引号也可以不带（name = GFX_xxx）
                    nm = re.search(r'(?m)^\s*name\s*=\s*"?([^"\s\}]+)"?', body)
                    if not nm:
                        continue
                    name = nm.group(1)
                    tx = re.search(r'(?m)^\s*texturefile\s*=\s*"?([^"\s\}]+)"?', body)
                    sprites[name] = tx.group(1) if tx else ""
                    if tx:
                        textures.add(tx.group(1).replace(chr(92), "/").lower())

    if include_vanilla and GAME:
        _scan(GAME)
    for b in (layers or []):
        if b:
            _scan(b)
    _GFX_CACHE[key] = (sprites, textures)
    return sprites, textures


def _gfx_refs(root, layers):
    """扫 mod 脚本里的 sprite 引用 → {spriteName: (位置描述, 文件)}"""
    refs = {}

    def _note(name, where, f):
        name = (name or "").strip()
        if len(name) <= 4 or not name.startswith("GFX_"):
            return          # icon = aluminium / generic 这种不是 sprite；GFX_ 空名也跳过
        if name not in refs:
            refs[name] = [where, f]

    # 国策 icon / 精神 picture / 事件 picture / 决议 icon / 装备 picture
    # sprite 名可能带非 ASCII（GFX_94式戦車 这种），[A-Za-z0-9_.-] 会把名字截断
    patterns = [
        (r'icon\s*=\s*"?([^"\s\}]+)"?', "icon"),
        (r'picture\s*=\s*"?([^"\s\}]+)"?', "picture"),
    ]
    for rel_dir in ("common/national_focus", "common/ideas", "common/decisions",
                    "common/decisions/categories", "events", "common/units/equipment"):
        d = os.path.join(root, rel_dir)
        if not os.path.isdir(d):
            continue
        for _dp, _dn, files in os.walk(d):
            for fn in files:
                if not fn.endswith(".txt"):
                    continue
                p = os.path.join(_dp, fn)
                try:
                    text = strip_comments(io.open(p, encoding="utf-8-sig",
                                                  errors="replace").read())
                except Exception:
                    continue
                for pat, where in patterns:
                    for m in re.finditer(pat, text):
                        _note(m.group(1), where, os.path.basename(p))
    return refs


def gfx_missing(root=None, limit=600):
    """列出引用了但没定义的 sprite，以及定义了但贴图文件不存在的 sprite"""
    root = _map_pick(root)
    layers = mod_layers(root)
    sprites, textures = _gfx_collect(root, layers)
    refs = _gfx_refs(root, layers)
    if not refs:
        return {"ok": True, "total": 0, "missing": [],
                "msg": "脚本里没有找到 sprite 引用"}

    missing = []
    by_kind = {}
    for name, (where, f) in refs.items():
        if name in sprites:
            continue
        # 纯色/文字类的值不是 sprite（比如 icon = 3 已被正则过滤，这里防空）
        missing.append({"name": name, "where": where, "file": f})
        by_kind[where] = by_kind.get(where, 0) + 1
    missing.sort(key=lambda x: (x["where"], x["name"]))

    # 顺带查：mod 自己定义的 sprite，贴图文件是否真的存在
    mod_sprites = {}
    for b in (layers or []):
        if not b or os.path.abspath(b) == os.path.abspath(GAME or ""):
            continue
        s2, _t2 = _gfx_collect(b, [], include_vanilla=False)
        mod_sprites.update(s2)
    bad_texture = []
    for name, tx in mod_sprites.items():
        if not tx:
            continue
        if not _gfx_texture_exists(tx, layers):
            bad_texture.append({"name": name, "texture": tx})

    return {"ok": True, "total": len(missing), "by_kind": by_kind,
            "refs": len(refs), "defined": len(sprites),
            "missing": missing[:limit], "truncated": len(missing) > limit,
            "bad_texture": bad_texture[:limit],
            "bad_texture_total": len(bad_texture),
            "msg": "引用 %d 个 sprite，缺 %d 个；贴图文件缺失 %d 个" % (
                len(refs), len(missing), len(bad_texture))}


def _gfx_texture_exists(rel, layers):
    """贴图文件是否存在于某一层（忽略大小写，游戏在 Windows 上不区分）"""
    rel = (rel or "").replace(chr(92), "/").strip("/")
    if not rel:
        return True
    low = rel.lower()
    for base in (layers or []):
        if not base:
            continue
        cand = os.path.join(base, rel.replace("/", os.sep))
        if os.path.exists(cand):
            return True
        # 大小写不一致时按目录列举比对
        d = os.path.dirname(cand)
        if os.path.isdir(d):
            try:
                for fn in os.listdir(d):
                    if fn.lower() == os.path.basename(cand).lower():
                        return True
            except Exception:
                pass
    return False


# ref: HOI4 Mod Utilities "Focus tree preview"
def focus_tree_graph(tid):
    """返回一棵国策树的节点与连线（只读，供预览渲染）"""
    tid = (tid or "").strip()
    t = TREES.get(tid)
    if not t:
        return {"ok": False, "msg": "没有这棵国策树：%s" % tid}
    nodes = []
    known = set()
    for f in t.get("focuses") or []:
        fid = f.get("id")
        if not fid:
            continue
        known.add(fid)
    for f in t.get("focuses") or []:
        fid = f.get("id")
        if not fid:
            continue
        try:
            x = int(float(f.get("x") or 0))
        except Exception:
            x = 0
        try:
            y = int(float(f.get("y") or 0))
        except Exception:
            y = 0
        node = {
            "id": fid, "x": x, "y": y,
            "icon": f.get("icon") or "",
            "cost": f.get("cost") or "",
            "name": LOC.get(fid, ""),
            "desc": LOC.get(fid + "_desc", ""),
            # prereq 是「组的列表」：组内 OR、组间 AND
            "prereq": [g for g in (f.get("prereq") or []) if g],
            "mutex": [m for m in (f.get("mutex") or []) if m],
        }
        nodes.append(node)
    # 连线只在两边都存在于本树时才有意义（跨树前置指向别的树时略过）
    edges = []
    for n in nodes:
        for grp in n["prereq"]:
            for src in grp:
                if src in known:
                    edges.append({"from": src, "to": n["id"], "kind": "prereq"})
        for src in n["mutex"]:
            if src in known:
                edges.append({"from": src, "to": n["id"], "kind": "mutex"})
    return {"ok": True, "tree": tid, "count": len(nodes),
            "nodes": nodes, "edges": edges,
            "file": os.path.basename(t.get("file") or ""),
            "msg": "%s：%d 个节点，%d 条连线" % (tid, len(nodes), len(edges))}


def focus_tree_list():
    """所有国策树（供下拉选择）"""
    out = []
    for tid in TREE_ORDER:
        t = TREES.get(tid) or {}
        out.append({"id": tid, "count": len(t.get("focuses") or []),
                    "file": os.path.basename(t.get("file") or "")})
    return {"ok": True, "trees": out, "count": len(out)}


# ref: HOI4 Mod Utilities "Event tree preview"
_EVENT_GRAPH_CACHE = {}


def _event_block(text, kind_kw):
    """取出所有 xxx_event = { ... } 块：(id, body)"""
    out = []
    for m in re.finditer(r'(?m)^\s*([a-z_]*_event)\s*=\s*\{', text):
        b = text.find("{", m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        eid = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_.\-]+)"?', body)
        if not eid:
            continue
        out.append((eid.group(1), body, m.group(1)))
    return out


def _event_fire_targets(body):
    """事件体里触发的其它事件 → [(target, where)]，where ∈ option / after / immediate"""
    res = []
    KINDS = r'(?:country_event|news_event|state_event)'
    # 先按块归类：option / after / immediate
    zones = []
    for key in ("option", "after", "immediate"):
        for m in re.finditer(r'(?m)^\s*' + key + r'\s*=\s*\{', body):
            b = body.find("{", m.end() - 1)
            e = brace_match(body, b)
            if e > b:
                zones.append((b, e, key))
    zones.sort()

    def zone_of(pos):
        for b, e, k in zones:
            if b <= pos < e:
                return k
        return "other"

    # 两种写法：块式 { id = X } 与简写 = X
    for m in re.finditer(KINDS + r'\s*=\s*\{', body):
        b = body.find("{", m.end() - 1)
        e = brace_match(body, b)
        if e <= b:
            continue
        sub = body[b + 1:e - 1]
        tid = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_.\-]+)"?', sub)
        if tid:
            res.append((tid.group(1), zone_of(m.start())))
    for m in re.finditer(KINDS + r'\s*=\s*"?([A-Za-z0-9_.\-]+)"?', body):
        tid = m.group(1)
        if tid in ("yes", "no"):
            continue
        res.append((tid, zone_of(m.start())))
    return res


def event_graph(ns="", root=None):
    """某个事件命名空间的树。ns 为空时返回所有命名空间概览。"""
    root = _map_pick(root)
    ns = (ns or "").strip()
    key = (os.path.abspath(root or ""), ns)
    hit = _EVENT_GRAPH_CACHE.get(key)
    if hit:
        return hit

    events = {}
    d = os.path.join(root or "", "events")
    if os.path.isdir(d):
        for _dp, _dn, files in os.walk(d):
            for fn in sorted(files):
                if not fn.endswith(".txt"):
                    continue
                try:
                    text = strip_comments(io.open(os.path.join(_dp, fn), encoding="utf-8-sig",
                                                  errors="replace").read())
                except Exception:
                    continue
                for eid, body, kind in _event_block(text, "event"):
                    events[eid] = {"id": eid, "kind": kind, "body": body,
                                   "file": os.path.relpath(os.path.join(_dp, fn), root)}

    # 命名空间：优先 ns 前缀（X.1 里的 X），没有点号的按整个 id 算
    spaces = {}
    for eid in events:
        s = eid.split(".")[0] if "." in eid else eid
        spaces.setdefault(s, []).append(eid)

    if not ns:
        out = {"ok": True, "spaces": [{"id": k, "count": len(v)} for k, v in
                                      sorted(spaces.items(), key=lambda kv: -len(kv[1]))],
               "count": len(spaces), "events": len(events),
               "msg": "%d 个事件，分属 %d 个命名空间" % (len(events), len(spaces))}
        _EVENT_GRAPH_CACHE[key] = out
        return out

    ids = set(spaces.get(ns) or [])
    if not ids:
        return {"ok": False, "msg": "没有命名空间 %s 的事件" % ns}

    nodes, edges = [], []
    for eid in sorted(ids):
        ev = events[eid]
        nodes.append({"id": eid, "kind": ev["kind"], "file": ev["file"],
                      "name": LOC.get(eid + ".t", "") or LOC.get(eid + ".title", ""),
                      "text": "#" + str(len(nodes) + 1)})
        for tid, where in _event_fire_targets(ev["body"]):
            edges.append({"from": eid, "to": tid, "where": where,
                          "external": tid not in ids})
    # 外部引用也画成节点（灰色），方便看出跳到别处
    ext = sorted({e["to"] for e in edges if e["external"]})
    for tid in ext:
        nodes.append({"id": tid, "kind": "external", "file": "",
                      "name": LOC.get(tid + ".t", ""), "text": ""})
    out = {"ok": True, "ns": ns, "count": len(nodes), "edges": len(edges),
           "nodes": nodes, "edges": edges,
           "msg": "%s：%d 个事件，%d 条触发，%d 个外部引用" % (
               ns, len(ids), len(edges), len(ext))}
    _EVENT_GRAPH_CACHE[key] = out
    return out


def event_space_create(ns, root=None):
    """新建一个事件命名空间：写 events/zz_xuerong_<ns>.txt，含一个样板事件"""
    import re as _re
    ns = (ns or "").strip()
    if not _re.match(r'^[A-Za-z][A-Za-z0-9_]*$', ns):
        return {"ok": False, "msg": "命名空间只能用字母、数字、下划线，且字母开头：%s" % ns}
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "没有加载 mod"}
    if is_under_game(root):
        return {"ok": False, "msg": "这是原版目录，只读"}
    d = os.path.join(root, "events")
    os.makedirs(d, exist_ok=True)
    fn = os.path.join(d, "zz_xuerong_%s.txt" % ns)
    if os.path.exists(fn):
        return {"ok": False, "msg": "文件已存在：events/zz_xuerong_%s.txt" % ns}
    # 避免和已有命名空间撞名
    existing = event_graph("", root)
    for sp in existing.get("spaces") or []:
        if sp["id"] == ns:
            return {"ok": False, "msg": "命名空间 %s 已经有事件了" % ns}
    body = (
        "add_namespace = %s\n\n"
        "country_event = {\n"
        "\tid = %s.1\n"
        "\ttitle = %s.1.t\n"
        "\tdesc = %s.1.d\n"
        "\tis_triggered_only = yes\n"
        "\n"
        "\toption = {\n"
        "\t\tname = %s.1.a\n"
        "\t}\n"
        "}\n"
    ) % (ns, ns, ns, ns, ns)
    snapshot(fn) if os.path.exists(fn) else None
    io.open(fn, "wb").write(b"\xef\xbb\xbf" + body.encode("utf-8"))
    _EVENT_GRAPH_CACHE.clear()

    # 同时生成本地化，省得再手动补键
    loc_dir = os.path.join(root, "localisation", "simp_chinese")
    loc_fn = os.path.join(loc_dir, "zz_xuerong_%s_l_simp_chinese.yml" % ns)
    loc_msg = ""
    try:
        os.makedirs(loc_dir, exist_ok=True)
        lines = ["l_simp_chinese:",
                 ' %s.1.t:0 "【未命名事件】"' % ns,
                 ' %s.1.d:0 "（在这里写事件描述）"' % ns,
                 ' %s.1.a:0 "确定"' % ns]
        io.open(loc_fn, "wb").write(b"\xef\xbb\xbf" + (chr(10).join(lines) + chr(10)).encode("utf-8"))
        loc_msg = "，本地化已写到 localisation/simp_chinese/%s" % os.path.basename(loc_fn)
    except Exception as _e:
        loc_msg = "，本地化生成失败（%s）" % _e

    return {"ok": True, "ns": ns, "file": "events/zz_xuerong_%s.txt" % ns,
            "locFile": os.path.basename(loc_fn) if os.path.exists(loc_fn) else "",
            "msg": "已创建命名空间 %s（events/zz_xuerong_%s.txt）%s" % (ns, ns, loc_msg)}


def event_space_delete(ns, root=None):
    """删除某个命名空间的事件：从各 events/*.txt 里摘掉这些块，文件空了就删"""
    ns = (ns or "").strip()
    if not ns:
        return {"ok": False, "msg": "没有指定命名空间"}
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "没有加载 mod"}
    if is_under_game(root):
        return {"ok": False, "msg": "这是原版目录，只读"}
    d = os.path.join(root, "events")
    if not os.path.isdir(d):
        return {"ok": False, "msg": "没有 events 目录"}

    prefix = ns + "."
    removed = 0
    touched = []
    for _dp, _dn, files in os.walk(d):
        for fn in sorted(files):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(_dp, fn)
            try:
                raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
            except Exception:
                continue
            text = strip_comments(raw)
            spans = []
            for m in re.finditer(r'(?m)^\s*[a-z_]*_event\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                eid = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_.\-]+)"?', body)
                if eid and eid.group(1).startswith(prefix):
                    # 用原文（去注释后的坐标）回到原始文本里删：按行号范围删更稳
                    spans.append((m.start(), e))
            lines = raw.splitlines(True)
            # 即使事件块已经删过，只要还有 add_namespace = ns 也要处理（否则残留声明）
            _ns_re = re.compile(r'^\s*add_namespace\s*=\s*' + re.escape(ns) + r'\s*$')
            _has_ns = any(_ns_re.match(ln.strip()) for ln in lines)
            if not spans and not _has_ns:
                continue
            offsets = []
            acc = 0
            for ln in lines:
                offsets.append(acc)
                acc += len(ln)
            drop = set()
            for (b, e) in spans:
                for i, off in enumerate(offsets):
                    if off >= b and off < e:
                        drop.add(i)
                    elif off < b and off + len(lines[i]) > b:
                        drop.add(i)
            # 命名空间声明本身也要删（add_namespace = ns）
            for i, ln in enumerate(lines):
                if re.match(r'^\s*add_namespace\s*=\s*' + re.escape(ns) + r'\s*$', ln.strip()):
                    drop.add(i)
            if not drop:
                continue
            keep = [ln for i, ln in enumerate(lines) if i not in drop]
            new_text = "".join(keep)
            if new_text.strip() in ("", "l_english:", "l_simp_chinese:"):
                snapshot(p)
                os.remove(p)
                touched.append("%s（已删空，文件移除）" % os.path.relpath(p, root))
            else:
                snapshot(p)
                io.open(p, "wb").write(b"\xef\xbb\xbf" + new_text.encode("utf-8"))
                touched.append("%s（删 %d 个块）" % (os.path.relpath(p, root), len(spans)))
            removed += max(1, len(spans))     # 只剩 add_namespace 声明时也算删过
    if not removed:
        return {"ok": False, "msg": "没有找到 %s.* 的事件" % ns}
    _EVENT_GRAPH_CACHE.clear()
    reload_data()
    return {"ok": True, "ns": ns, "removed": removed, "files": touched,
            "msg": "已删除命名空间 %s 的 %d 个事件" % (ns, removed)}


def _loc_write_pairs(root, pairs, lang="simp_chinese"):
    """把 {key: text} 写进 zz_xuerong_evtext_l_<lang>.yml（只覆盖这些键）"""
    if not pairs:
        return ""
    d = os.path.join(root, "localisation", lang)
    os.makedirs(d, exist_ok=True)
    fn = os.path.join(d, "zz_xuerong_evtext_l_%s.yml" % lang)
    existing = {}
    if os.path.exists(fn):
        try:
            line_re = re.compile(r'^\s*([A-Za-z0-9_.\-]+):\d*\s+"(.*)"\s*$')
            for ln in io.open(fn, encoding="utf-8-sig", errors="replace").read().splitlines():
                m = line_re.match(ln)
                if m:
                    existing[m.group(1)] = m.group(2)
        except Exception:
            pass
    for k, v in pairs.items():
        existing[k] = str(v).replace('"', "'").replace(chr(10), "\\n")
    lines = ["l_%s:" % lang]
    for k in sorted(existing):
        lines.append(' %s:0 "%s"' % (k, existing[k]))
    io.open(fn, "wb").write(b"\xef\xbb\xbf" + (chr(10).join(lines) + chr(10)).encode("utf-8"))
    return os.path.basename(fn)


def _prov_state_map():
    """省 → 州 的映射。

    同一省被多个州声明时（原版和 mod 都有这个省，mod 的州覆盖原版的州），
    按 ROOTS 的加载顺序取优先级最高的那一层 —— 后面的 mod 覆盖前面的。
    只有在同一层内部冲突时才记为真实数据问题。"""
    layers = {}
    for i, r in enumerate(ROOTS or []):
        layers[os.path.abspath(r)] = i
    best = {}      # pid -> (priority, sid)
    dups = {}
    for _s in (STATES.values() if isinstance(STATES, dict) else []):
        try:
            sid = int(_s.get("id") or 0)
        except Exception:
            continue
        pri = layers.get(os.path.abspath(_s.get("root") or ""), 0)
        for _p in (_s.get("provinces") or []):
            try:
                pid = int(_p)
            except Exception:
                continue
            cur = best.get(pid)
            if cur is None or pri > cur[0]:
                best[pid] = (pri, sid)
            elif pri == cur[0] and cur[1] != sid:
                # 同一层里两个州都声明了这个省 —— 这才是真冲突
                dups.setdefault(pid, [cur[1]]).append(sid)
    return {k: v[1] for k, v in best.items()}, dups


def _refine_state_warnings(pid, prov2state):
    """细化前的风险提示：VP / 首都 / 州归属"""
    warn = []
    sid = prov2state.get(pid, 0)
    if not sid:
        warn.append("省 %d 不属于任何州，细化出来的新省也不会有归属" % pid)
        return warn, 0

    st = None
    for s in (STATES.values() if isinstance(STATES, dict) else []):
        try:
            if int(s.get("id") or 0) == int(sid):
                st = s
                break
        except Exception:
            continue
    if not st:
        return warn, sid

    provs = st.get("provinces") or []
    if len(provs) <= 1:
        warn.append("州 %d 只有这一个省，细化后新省需要单独建州或并入邻州" % sid)
    else:
        warn.append("新省会加入州 %d（共 %d 省）" % (sid, len(provs)))

    for vp in (st.get("victory_points") or []):
        try:
            if int(vp.get("province") or -1) == int(pid):
                warn.append("省 %d 有 %s 点胜利点，细化后图标会随质心移到原省残留块" % (
                    pid, vp.get("points")))
        except Exception:
            pass

    # 首都：只查已加载的国家，命中就提示
    try:
        for c in (COUNTRIES.values() if isinstance(COUNTRIES, dict) else []):
            if str(c.get("capital") or "") == str(pid):
                warn.append("省 %d 是 %s 的首都，细化后首都位置会落在原省残留块" % (
                    pid, c.get("tag") or c.get("name") or "某国"))
    except Exception:
        pass
    return warn, sid


def _refine_attach_to_state(root, sid, new_ids, pid):
    """把细化出来的新省加进原州（改 history/states/*.txt 的 provinces 列表）"""
    if not sid or not new_ids:
        return ""
    _r, rel, path = _state_file_for(sid)
    if not path:
        return ""
    try:
        text = _read_text(path)
        m = re.search(r'(?m)^[ \t]*provinces\s*=\s*\{', text)
        cur = []
        if m:
            b = text.find("{", m.end() - 1)
            e = brace_match(text, b)
            if e > b:
                cur = [int(x) for x in re.findall(r'\d+', text[b + 1:e - 1])]
        if not cur:
            cur = [pid]
        merged = sorted(set(cur) | set(int(x) for x in new_ids))
        if merged == sorted(set(cur)):
            return ""
        body = _set_state_provinces(text, merged)
        snapshot(path)
        _write_bom_text(path, body, text.startswith("\ufeff") or True)
        return rel
    except Exception as e:
        print("写州归属失败:", e)
        return ""


def event_detail(eid, root=None):
    """读一个事件的 title / desc / 各 option 的名称与触发目标，供就地编辑"""
    eid = (eid or "").strip()
    root = _map_pick(root)
    if not eid:
        return {"ok": False, "msg": "没有事件 id"}
    d = os.path.join(root or "", "events")
    if not os.path.isdir(d):
        return {"ok": False, "msg": "没有 events 目录"}
    for _dp, _dn, files in os.walk(d):
        for fn in files:
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(_dp, fn)
            try:
                text = strip_comments(io.open(p, encoding="utf-8-sig", errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'(?m)^\s*[a-z_]*_event\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                got = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_.\-]+)"?', body)
                if not got or got.group(1) != eid:
                    continue
                tit = re.search(r'(?m)^\s*title\s*=\s*"?([A-Za-z0-9_.\-]+)"?', body)
                dsc = re.search(r'(?m)^\s*desc\s*=\s*"?([A-Za-z0-9_.\-]+)"?', body)
                opts = []
                for om in re.finditer(r'(?m)^\s*option\s*=\s*\{', body):
                    ob = body.find("{", om.end() - 1)
                    oe = brace_match(body, ob)
                    if oe <= ob:
                        continue
                    sub = body[ob + 1:oe - 1]
                    nm = re.search(r'(?m)^\s*name\s*=\s*"?([A-Za-z0-9_.\-]+)"?', sub)
                    tg = re.search(r'(?m)^\s*(?:country_event|news_event|state_event)\s*=\s*(?:\{\s*)?id\s*=\s*"?([A-Za-z0-9_.\-]+)"?', sub)
                    if not tg:
                        tg = re.search(r'(?m)^\s*(?:country_event|news_event|state_event)\s*=\s*"?([A-Za-z0-9_.\-]+)"?', sub)
                    opts.append({"name": nm.group(1) if nm else "",
                                 "target": tg.group(1) if tg else ""})
                return {"ok": True, "id": eid, "file": os.path.relpath(p, root),
                        "title": tit.group(1) if tit else "",
                        "desc": dsc.group(1) if dsc else "",
                        "titleText": LOC.get(tit.group(1), "") if tit else "",
                        "descText": LOC.get(dsc.group(1), "") if dsc else "",
                        "options": opts}
    return {"ok": False, "msg": "找不到事件 %s（可能不在本 mod 里）" % eid}


def event_edit(eid, title=None, desc=None, options=None, root=None,
               title_text=None, desc_text=None):
    """就地改事件的 title / desc / 各 option 的名称与触发目标。

    只替换匹配到的行，不动其它内容；改前 snapshot。"""
    eid = (eid or "").strip()
    root = _map_pick(root)
    if not eid:
        return {"ok": False, "msg": "没有事件 id"}
    if is_under_game(root):
        return {"ok": False, "msg": "这是原版目录，只读"}
    d = os.path.join(root or "", "events")
    if not os.path.isdir(d):
        return {"ok": False, "msg": "没有 events 目录"}

    changed = []
    for _dp, _dn, files in os.walk(d):
        for fn in files:
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(_dp, fn)
            try:
                raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
            except Exception:
                continue
            text = strip_comments(raw)
            hit = None
            for m in re.finditer(r'(?m)^\s*[a-z_]*_event\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                got = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_.\-]+)"?', body)
                if got and got.group(1) == eid:
                    hit = (m.start(), e, body)
                    break
            if not hit:
                continue
            # 用「去注释后的坐标」定位到原文：按行替换更安全
            lines = raw.splitlines(True)
            out = []
            state = {"in_event": False, "depth": 0, "opt_i": -1,
                     "title_done": False, "desc_done": False}
            for ln in lines:
                st = ln.strip()
                if re.match(r'^[a-z_]*_event\s*=\s*\{', st):
                    state["in_event"] = True
                    state["depth"] = 0
                    state["title_done"] = False
                    state["desc_done"] = False
                    state["opt_i"] = -1
                if state["in_event"]:
                    is_this = False
                    mid = re.match(r'^id\s*=\s*"?([A-Za-z0-9_.\-]+)"?', st)
                    if mid and mid.group(1) == eid:
                        is_this = True
                    if is_this:
                        state["this"] = True
                    if state.get("this"):
                        if title and not state["title_done"]:
                            nt = re.sub(r'^(\s*title\s*=\s*)"?[A-Za-z0-9_.\-]+"?.*$',
                                        lambda mm: mm.group(1) + title, ln)
                            if nt != ln:
                                ln = nt
                                state["title_done"] = True
                                changed.append("title")
                        if desc and not state["desc_done"]:
                            nd = re.sub(r'^(\s*desc\s*=\s*)"?[A-Za-z0-9_.\-]+"?.*$',
                                        lambda mm: mm.group(1) + desc, ln)
                            if nd != ln:
                                ln = nd
                                state["desc_done"] = True
                                changed.append("desc")
                        if re.match(r'^option\s*=\s*\{', st):
                            state["opt_i"] += 1
                        if options and 0 <= state["opt_i"] < len(options):
                            o = options[state["opt_i"]] or {}
                            if o.get("name"):
                                nn = re.sub(r'^(\s*name\s*=\s*)"?[A-Za-z0-9_.\-]+"?.*$',
                                            lambda mm: mm.group(1) + o["name"], ln)
                                if nn != ln:
                                    ln = nn
                                    changed.append("option%d.name" % state["opt_i"])
                            if o.get("target"):
                                nt2 = re.sub(r'^((\s*)(?:country_event|news_event|state_event)\s*=\s*)"?[A-Za-z0-9_.\-]+"?.*$',
                                             lambda mm: mm.group(1) + o["target"], ln)
                                if nt2 != ln:
                                    ln = nt2
                                    changed.append("option%d.target" % state["opt_i"])
                    # 花括号深度
                    state["depth"] += ln.count("{") - ln.count("}")
                    if state["depth"] <= 0:
                        state["in_event"] = False
                        state["this"] = False
                out.append(ln)
            if not changed:
                # 键名没变，但可能只改了中文文本 —— 那也要写进 yml
                _p2 = {}
                if title_text and title:
                    _p2[title] = title_text
                if desc_text and desc:
                    _p2[desc] = desc_text
                if _p2:
                    _lf = _loc_write_pairs(root, _p2)
                    reload_data()
                    return {"ok": True, "id": eid, "file": os.path.relpath(p, root),
                            "locFile": _lf, "changed": ["文本"],
                            "msg": "已更新 %s 的文本（写进 %s）" % (eid, _lf)}
                return {"ok": False, "msg": "没有实际改动（参数为空或未匹配到字段）"}
            snapshot(p)
            io.open(p, "wb").write(b"\xef\xbb\xbf" + "".join(out).encode("utf-8"))
            # 中文文本写进本地化，不塞回事件文件
            _pairs = {}
            if title_text and title:
                _pairs[title] = title_text
            if desc_text and desc:
                _pairs[desc] = desc_text
            _locfn = _loc_write_pairs(root, _pairs) if _pairs else ""
            if _pairs:
                changed.append("文本")
            reload_data()
            _msg = "已更新 %s 的 %s" % (eid, "、".join(sorted(set(changed))))
            if _locfn:
                _msg += "（文本写进 %s）" % _locfn
            return {"ok": True, "id": eid, "file": os.path.relpath(p, root),
                    "locFile": _locfn, "changed": changed, "msg": _msg}
    return {"ok": False, "msg": "找不到事件 %s" % eid}


def _railway_file(root):
    """找 railways.txt（先 mod 后原版），返回 (path, base)"""
    for base in reversed(mod_layers(root) or []):
        if not base:
            continue
        p = os.path.join(base, "map", "railways.txt")
        if os.path.exists(p):
            return p, base
    if GAME:
        p = os.path.join(GAME, "map", "railways.txt")
        if os.path.exists(p):
            return p, GAME
    return None, None


def _railway_parse(path):
    """解析 railways.txt。

    行式：   <level> <count> p1 p2 p3 ...
    块式：   railway = { level = N provinces = { p1 p2 ... } }
    两种都收，返回 [{"level": N, "provs": [...], "raw_i": 行号}]"""
    out = []
    if not path or not os.path.exists(path):
        return out
    try:
        raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return out
    text = strip_comments(raw)
    # 块式
    for m in re.finditer(r'(?m)^\s*railway\s*=\s*\{', text):
        b = text.find("{", m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        lv = re.search(r'level\s*=\s*(\d+)', body)
        pr = re.search(r'provinces\s*=\s*\{([^}]*)\}', body)
        if pr:
            provs = [int(x) for x in re.findall(r'\d+', pr.group(1))]
            if provs:
                out.append({"level": int(lv.group(1)) if lv else 1,
                            "provs": provs, "form": "block"})
    # 行式
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) < 3 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        try:
            level = int(parts[0])
            n = int(parts[1])
        except Exception:
            continue
        provs = []
        for tok in parts[2:2 + n]:
            try:
                provs.append(int(tok))
            except Exception:
                break
        if len(provs) == n and provs:
            out.append({"level": level, "provs": provs, "form": "line"})
    return out


def railways_list(root=None):
    """铁路列表 + 每条的状态（断连 / 等级越界）"""
    root = _map_pick(root)
    path, base = _railway_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/railways.txt"}
    rails = _railway_parse(path)
    # 一次算全图邻接，再逐条查表（逐段调 map_prov_neighbors 会把几千段算成几小时）
    allnb = _all_prov_neighbors(root)
    items = []
    broken = 0
    over = 0
    for i2, r in enumerate(rails):
        provs = r["provs"]
        bad = []
        for a, b in zip(provs, provs[1:]):
            if b not in (allnb.get(a) or ()):
                bad.append([a, b])
        if bad:
            broken += 1
        if r["level"] > 5:
            over += 1
        items.append({"i": i2, "level": r["level"], "provs": provs,
                      "len": len(provs), "broken": bad,
                      "over": r["level"] > 5, "form": r["form"]})
    return {"ok": True, "count": len(items), "broken": broken, "over": over,
            "file": os.path.relpath(path, base) if base else path,
            "fromMod": bool(root and base and os.path.abspath(base) == os.path.abspath(root)),
            "items": items,
            "msg": "共 %d 条铁路，%d 条断连，%d 条等级超 5" % (len(items), broken, over)}


def railway_set_level(index, level, root=None):
    """改某条铁路的等级（行式直接改第一个数字，块式改 level = N）"""
    root = _map_pick(root)
    path, base = _railway_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/railways.txt"}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "railways.txt 来自原版，只读"}
    try:
        level = max(1, min(10, int(level)))
        index = int(index)
    except Exception:
        return {"ok": False, "msg": "参数不合法"}
    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    lines = raw.splitlines(True)
    # 收集行式铁路的行号
    line_rows = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        parts = s.split()
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
            try:
                n = int(parts[1])
                if len(parts[2:2 + n]) == n:
                    line_rows.append(i)
            except Exception:
                pass
    rails = _railway_parse(path)
    if index < 0 or index >= len(rails):
        return {"ok": False, "msg": "没有第 %d 条铁路" % index}
    target = rails[index]
    if target.get("form") == "line" and index < len(line_rows):
        i = line_rows[index]
        parts = lines[i].split(None, 2)
        rest = parts[2] if len(parts) > 2 else ""
        lines[i] = "%d %s %s" % (level, parts[1] if len(parts) > 1 else str(len(target["provs"])), rest)
        if not lines[i].endswith(chr(10)):
            lines[i] += chr(10)
        snapshot(path)
        io.open(path, "wb").write(b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
        return {"ok": True, "index": index, "level": level,
                "msg": "第 %d 条铁路等级改为 %d" % (index, level)}
    return {"ok": False, "msg": "这条铁路是块式写法，暂不支持改等级"}


def railway_edit(index, level=None, provs=None, root=None):
    """改某条铁路：等级 / 省份序列（行式直接改该行，块式重建块）"""
    root = _map_pick(root)
    path, base = _railway_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/railways.txt"}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "railways.txt 来自原版，只读"}
    try:
        index = int(index)
    except Exception:
        return {"ok": False, "msg": "铁路序号不合法"}

    rails = _railway_parse(path)
    if index < 0 or index >= len(rails):
        return {"ok": False, "msg": "没有第 %d 条铁路" % index}
    cur = rails[index]

    new_level = int(level) if level not in (None, "") else cur["level"]
    new_level = max(1, min(10, new_level))
    new_provs = cur["provs"]
    if provs:
        try:
            cand = [int(x) for x in provs]
        except Exception:
            return {"ok": False, "msg": "省份列表不合法"}
        if len(cand) < 2:
            return {"ok": False, "msg": "铁路至少要有 2 个省"}
        # 邻接校验：相邻两省必须接壤，否则游戏里会断
        allnb = _all_prov_neighbors(root)
        bad = [[a, b] for a, b in zip(cand, cand[1:]) if b not in (allnb.get(a) or ())]
        if bad:
            return {"ok": False,
                    "msg": "这些相邻省不接壤，会断连：%s" % bad[:3]}
        new_provs = cand

    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    lines = raw.splitlines(True)

    if cur.get("form") == "line":
        # 行式在原文里的行号
        rows = []
        for i, ln in enumerate(lines):
            parts = ln.strip().split()
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                try:
                    n = int(parts[1])
                    if len(parts[2:2 + n]) == n:
                        rows.append(i)
                except Exception:
                    pass
        if index >= len(rows):
            return {"ok": False, "msg": "定位不到这一行"}
        i = rows[index]
        tail = chr(10) if lines[i].endswith(chr(10)) else ""
        lines[i] = "%d %d %s%s" % (new_level, len(new_provs),
                                   " ".join(str(p) for p in new_provs), tail)
        snapshot(path)
        io.open(path, "wb").write(b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
        return {"ok": True, "index": index, "level": new_level, "provs": new_provs,
                "msg": "第 %d 条铁路已更新：等级 %d，%d 个省" % (
                    index, new_level, len(new_provs))}

    # 块式：整条重建
    text = strip_comments(raw)
    blocks = []
    for m in re.finditer(r'(?m)^\s*railway\s*=\s*\{', text):
        b = text.find("{", m.end() - 1)
        e = brace_match(text, b)
        if e > b:
            blocks.append((b, e))
    if index >= len(blocks):
        return {"ok": False, "msg": "定位不到这个块"}
    b, e = blocks[index]
    body = ("\n\tlevel = %d\n\tprovinces = {\n\t\t%s\n\t}\n" % (
        new_level, "\n\t\t".join(str(p) for p in new_provs)))
    new_raw = raw[:b + 1] + body + raw[e - 1:]
    snapshot(path)
    io.open(path, "wb").write(b"\xef\xbb\xbf" + new_raw.encode("utf-8"))
    return {"ok": True, "index": index, "level": new_level, "provs": new_provs,
            "msg": "第 %d 条铁路（块式）已重建" % index}


def railway_delete(index, root=None):
    """删除一条铁路（行式删行，块式删块）"""
    root = _map_pick(root)
    path, base = _railway_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/railways.txt"}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "railways.txt 来自原版，只读"}
    try:
        index = int(index)
    except Exception:
        return {"ok": False, "msg": "序号不合法"}
    rails = _railway_parse(path)
    if index < 0 or index >= len(rails):
        return {"ok": False, "msg": "没有第 %d 条铁路" % index}
    cur = rails[index]
    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    lines = raw.splitlines(True)
    if cur.get("form") == "line":
        rows = []
        for i, ln in enumerate(lines):
            parts = ln.strip().split()
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                try:
                    n = int(parts[1])
                    if len(parts[2:2 + n]) == n:
                        rows.append(i)
                except Exception:
                    pass
        if index >= len(rows):
            return {"ok": False, "msg": "定位不到这一行"}
        del lines[rows[index]]
        snapshot(path)
        io.open(path, "wb").write(b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
        return {"ok": True, "msg": "已删除第 %d 条铁路（%d 个省）" % (index, len(cur["provs"]))}
    return {"ok": False, "msg": "块式铁路暂不支持删除"}


def supply_areas(root=None):
    """列出补给区：id、价值、覆盖的州"""
    root = _map_pick(root)
    out = []
    seen_ids = set()
    for base in reversed(mod_layers(root) or []):
        if not base:
            continue
        d = os.path.join(base, "map", "supplyareas")
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(d, fn)
            try:
                text = strip_comments(io.open(p, encoding="utf-8-sig", errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'supply_area\s*=\s*\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                sid = re.search(r'(?m)^\s*id\s*=\s*(\d+)', body)
                if not sid:
                    continue
                sid = int(sid.group(1))
                val = re.search(r'(?m)^\s*value\s*=\s*(\d+)', body)
                st = re.search(r'states\s*=\s*\{([^}]*)\}', body)
                states = [int(x) for x in re.findall(r'\d+', st.group(1))] if st else []
                out.append({"id": sid, "value": int(val.group(1)) if val else 0,
                            "states": states, "count": len(states),
                            "file": os.path.relpath(p, base),
                            "root": os.path.abspath(base)})
                seen_ids.add(sid)
    # 同名 id 以最后一层（mod）为准
    merged = {}
    for a in out:
        merged[a["id"]] = a
    items = sorted(merged.values(), key=lambda x: x["id"])
    return {"ok": True, "count": len(items), "items": items,
            "msg": "共 %d 个补给区" % len(items)}


def bmp_write_rect_8(path, x0, y0, w, h, values):
    """8 位索引图（terrain.bmp 这类）的矩形写入，每像素 1 字节。

    bmp_write_rect 只处理 24 位；索引图必须单独写，否则会把 P 模式 bmp 改成 RGB，
    HOI4 就读不出来了。"""
    info = bmp_info(path)
    if not info or info.get("bpp") != 8:
        return False
    bpp_bytes = info.get("bytes_pp") or 1
    if bpp_bytes != 1:
        return False
    row_bytes = info["row"]
    W, H = info["w"], info["h"]
    if x0 < 0 or y0 < 0 or x0 + w > W or y0 + h > H:
        return False
    with open(path, "r+b") as f:
        for r in range(h):
            y = y0 + r
            fy = y if info.get("top_down") else (H - 1 - y)
            off = info["offset"] + fy * row_bytes + x0
            f.seek(off)
            f.write(bytes(values[r * w:(r + 1) * w]))
    return True


def _terrain_type_to_index(root):
    """类型名 → terrain.bmp 里的索引（同一类型有多个索引时取第一个）"""
    idx2type, _tex = _terrain_tex_map(root)
    out = {}
    for i in sorted(idx2type):
        t = idx2type[i]
        if t not in out:
            out[t] = i
    return out, idx2type


def terrain_types(root=None):
    """列出可用的地形类型（按 definition.csv 里实际出现的 + terrain.txt 定义的）"""
    root = _map_pick(root)
    t2i, idx2type = _terrain_type_to_index(root)
    # 统计每个类型有多少省
    cnt = {}
    csvp, _ = _layers_find("map/definition.csv", mod_layers(root))
    if csvp:
        try:
            with io.open(csvp, encoding="utf-8", errors="replace") as f:
                for line in f:
                    p = line.strip().split(";")
                    if len(p) >= 8 and p[0].isdigit():
                        cnt[p[6]] = cnt.get(p[6], 0) + 1
        except Exception:
            pass
    items = []
    for t in sorted(set(list(t2i.keys()) + list(cnt.keys()))):
        items.append({"type": t, "index": t2i.get(t), "count": cnt.get(t, 0),
                      "writable": t2i.get(t) is not None})
    return {"ok": True, "items": items, "count": len(items),
            "msg": "共 %d 种地形类型" % len(items)}


def prov_terrain_set(pid, terrain, root=None):
    """把某个省的地形改成指定类型。

    同时做两件事：
      1. definition.csv 第 7 列（地形名）
      2. terrain.bmp 里该省所有像素的索引改成该类型对应的索引
    只改 definition.csv 不改 bmp 的话，游戏读的是 bmp，改了等于没改。
    """
    pid = int(pid or 0)
    terrain = (terrain or "").strip()
    if pid <= 0 or not terrain:
        return {"ok": False, "msg": "参数不完整"}
    root = _map_pick(root)
    layers = mod_layers(root)
    csvp, csvbase = _layers_find("map/definition.csv", layers)
    tbmp, tbase = _layers_find("map/terrain.bmp", layers)
    if not csvp:
        return {"ok": False, "msg": "找不到 definition.csv"}
    if not tbmp:
        return {"ok": False, "msg": "找不到 terrain.bmp"}
    # terrain.bmp 与 provinces.bmp 必须同源，否则改 bmp 没有意义（会画出错误的地形）
    pbmp, pbase = _layers_find("map/provinces.bmp", layers)
    if os.path.abspath(tbase or "") != os.path.abspath(pbase or ""):
        return {"ok": False,
                "msg": "terrain.bmp 与 provinces.bmp 不同源（mod 换了地图没换地形图），改地形会错位"}

    t2i, idx2type = _terrain_type_to_index(root)
    if terrain not in t2i:
        return {"ok": False, "msg": "terrain.txt 里没有类型 %s（可选：%s）" % (
            terrain, "、".join(sorted(t2i.keys())[:8]))}
    new_idx = t2i[terrain]

    # 1) 改 definition.csv
    raw = io.open(csvp, encoding="utf-8", errors="replace").read()
    lines = raw.splitlines(True)
    old_type = None
    hit = False
    for i, ln in enumerate(lines):
        p = ln.rstrip("\r\n").split(";")
        if len(p) >= 8 and p[0].isdigit() and int(p[0]) == pid:
            old_type = p[6]
            if old_type == terrain:
                return {"ok": True, "changed": False,
                        "msg": "省 %d 已经是 %s，无需改动" % (pid, terrain)}
            p[6] = terrain
            tail = chr(10) if ln.endswith(chr(10)) else ""
            lines[i] = ";".join(p) + tail
            hit = True
            break
    if not hit:
        return {"ok": False, "msg": "definition.csv 里没有省 %d" % pid}

    # 2) 改 terrain.bmp 里该省的像素
    ids, w, h = _refine_load_ids(root)
    if not ids:
        return {"ok": False, "msg": "读不到省号数组"}
    px = [i for i in range(len(ids)) if ids[i] == pid]
    if not px:
        return {"ok": False, "msg": "省 %d 在地图上没有像素" % pid}
    xs = [p % w for p in px]
    ys = [p // w for p in px]
    bx, by = min(xs), min(ys)
    bw, bh = max(xs) - bx + 1, max(ys) - by + 1
    # 读原索引（用 Pillow 读整块更稳）
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(tbmp) as im:
        if im.size != (w, h):
            return {"ok": False, "msg": "terrain.bmp 尺寸与地图不符"}
        crop = im.crop((bx, by, bx + bw, by + bh))
        buf = list(crop.tobytes())
    for p in px:
        o = (p // w - by) * bw + (p % w - bx)
        if 0 <= o < len(buf):
            buf[o] = new_idx

    snapshot(csvp)
    snapshot(tbmp)
    io.open(csvp, "wb").write(b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
    if not bmp_write_rect_8(tbmp, bx, by, bw, bh, buf):
        return {"ok": False, "msg": "terrain.bmp 写入失败（不是 8 位索引图）"}

    # 地形变了，缓存与图层都要失效
    try:
        _REFINE_IDS_CACHE.pop("cur", None)
    except Exception:
        pass
    return {"ok": True, "changed": True, "pid": pid,
            "from": old_type, "to": terrain, "index": new_idx,
            "pixels": len(px), "rect": [bx, by, bw, bh],
            "msg": "省 %d 地形 %s → %s（%d 像素，索引 %d），需重建图层" % (
                pid, old_type, terrain, len(px), new_idx)}


def _terrain_common(root, terrain):
    """批量改地形的公共准备：找文件、查索引、验同源。
    返回 (csvp, tbmp, new_idx, ids, w, h, err)"""
    root = _map_pick(root)
    layers = mod_layers(root)
    csvp, csvbase = _layers_find("map/definition.csv", layers)
    tbmp, tbase = _layers_find("map/terrain.bmp", layers)
    pbmp, pbase = _layers_find("map/provinces.bmp", layers)
    if not csvp:
        return None, None, None, None, 0, 0, "找不到 definition.csv"
    if not tbmp:
        return None, None, None, None, 0, 0, "找不到 terrain.bmp"
    if os.path.abspath(tbase or "") != os.path.abspath(pbase or ""):
        return None, None, None, None, 0, 0, "terrain.bmp 与 provinces.bmp 不同源，改地形会错位"
    t2i, _idx2type = _terrain_type_to_index(root)
    if terrain not in t2i:
        return None, None, None, None, 0, 0, "terrain.txt 里没有类型 %s" % terrain
    ids, w, h = _refine_load_ids(root)
    if not ids:
        return None, None, None, None, 0, 0, "读不到省号数组"
    return csvp, tbmp, t2i[terrain], ids, w, h, None


def _terrain_apply(csvp, tbmp, ids, w, h, pid_set, new_idx, renumber_from=None):
    """把 pid_set 里所有省在 terrain.bmp 里改成 new_idx，同时改 definition.csv。
    一次读全图、一次写全图 —— 批量改几百个省也不会变成几百次磁盘 IO。
    返回 (改动省数, 像素数, 旧类型统计)"""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None

    raw = io.open(csvp, encoding="utf-8", errors="replace").read()
    lines = raw.splitlines(True)
    old_types = {}
    changed_pids = set()
    for i, ln in enumerate(lines):
        p = ln.rstrip("\r\n").split(";")
        if len(p) >= 8 and p[0].isdigit():
            pid = int(p[0])
            if pid in pid_set:
                old_types[p[6]] = old_types.get(p[6], 0) + 1
                if p[6] != renumber_from:
                    p[6] = renumber_from if renumber_from else p[6]
                changed_pids.add(pid)
    # 上面只是统计；真正写入在下面统一做
    if not changed_pids:
        return 0, 0, {}

    idset = changed_pids
    pxmap = [p for p in range(len(ids)) if ids[p] in idset]
    if not pxmap:
        return 0, 0, old_types

    xs = [p % w for p in pxmap]
    ys = [p // w for p in pxmap]
    bx, by = min(xs), min(ys)
    bw, bh = max(xs) - bx + 1, max(ys) - by + 1

    with Image.open(tbmp) as im:
        if im.size != (w, h):
            return 0, 0, old_types
        crop = im.crop((bx, by, bx + bw, by + bh))
        buf = list(crop.tobytes())
    for p in pxmap:
        o = (p // w - by) * bw + (p % w - bx)
        if 0 <= o < len(buf):
            buf[o] = new_idx

    snapshot(csvp)
    snapshot(tbmp)
    io.open(csvp, "wb").write(b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
    if not bmp_write_rect_8(tbmp, bx, by, bw, bh, buf):
        return 0, 0, old_types
    try:
        _REFINE_IDS_CACHE.pop("cur", None)
    except Exception:
        pass
    return len(changed_pids), len(pxmap), old_types


def prov_terrain_batch(pids, terrain, root=None):
    """批量改多个省的地形（一次读写）"""
    terrain = (terrain or "").strip()
    if not pids or not terrain:
        return {"ok": False, "msg": "参数不完整"}
    try:
        want = set(int(x) for x in pids if int(x) > 0)
    except Exception:
        return {"ok": False, "msg": "省号列表不合法"}
    if not want:
        return {"ok": False, "msg": "没有有效的省号"}

    csvp, tbmp, new_idx, ids, w, h, err = _terrain_common(root, terrain)
    if err:
        return {"ok": False, "msg": err}

    # 找出真正要改的（已经是指定类型的跳过）
    raw = io.open(csvp, encoding="utf-8", errors="replace").read()
    lines = raw.splitlines(True)
    todo = set()
    old_types = {}
    for ln in lines:
        p = ln.rstrip("\r\n").split(";")
        if len(p) >= 8 and p[0].isdigit() and int(p[0]) in want:
            if p[6] != terrain:
                todo.add(int(p[0]))
                old_types[p[6]] = old_types.get(p[6], 0) + 1
    if not todo:
        return {"ok": True, "changed": 0, "msg": "这 %d 个省已经是 %s" % (len(want), terrain)}

    n_pid, n_px, _ = _terrain_apply(csvp, tbmp, ids, w, h, todo, new_idx, terrain)
    return {"ok": True, "changed": n_pid, "pixels": n_px, "to": terrain,
            "from": old_types, "skipped": len(want) - n_pid,
            "msg": "%d 个省改成 %s（%d 像素），%d 个已是该类型跳过 · 需重建图层" % (
                n_pid, terrain, n_px, len(want) - n_pid)}


def prov_terrain_by_type(from_type, to_type, root=None):
    """把某一地形的所有省改成另一种（先从 csv 查，再批量改）"""
    from_type = (from_type or "").strip()
    to_type = (to_type or "").strip()
    if not from_type or not to_type or from_type == to_type:
        return {"ok": False, "msg": "参数不合法（源类型与目标类型不能相同）"}
    root = _map_pick(root)
    layers = mod_layers(root)
    csvp, _ = _layers_find("map/definition.csv", layers)
    if not csvp:
        return {"ok": False, "msg": "找不到 definition.csv"}
    pids = []
    for ln in io.open(csvp, encoding="utf-8", errors="replace"):
        p = ln.rstrip("\r\n").split(";")
        if len(p) >= 8 and p[0].isdigit() and p[6] == from_type:
            pids.append(int(p[0]))
    if not pids:
        return {"ok": False, "msg": "没有地形为 %s 的省" % from_type}
    r = prov_terrain_batch(pids, to_type, root)
    if r.get("ok"):
        r["msg"] = "把 %d 个 %s 改成了 %s · 需重建图层" % (
            r.get("changed", 0), from_type, to_type)
    return r


def terrain_paint(points, terrain, brush=3, root=None):
    """画笔式刷地形：直接改 terrain.bmp 的像素索引，不动 definition.csv。

    points: [[x, y], ...]（地图坐标），brush: 笔刷半径（像素）
    """
    terrain = (terrain or "").strip()
    try:
        brush = max(1, min(30, int(brush or 1)))
    except Exception:
        brush = 1
    if not points or not terrain:
        return {"ok": False, "msg": "参数不完整"}
    root = _map_pick(root)
    layers = mod_layers(root)
    tbmp, tbase = _layers_find("map/terrain.bmp", layers)
    pbmp, pbase = _layers_find("map/provinces.bmp", layers)
    if not tbmp:
        return {"ok": False, "msg": "找不到 terrain.bmp"}
    if os.path.abspath(tbase or "") != os.path.abspath(pbase or ""):
        return {"ok": False, "msg": "terrain.bmp 与 provinces.bmp 不同源，刷地形会错位"}
    t2i, _ = _terrain_type_to_index(root)
    if terrain not in t2i:
        return {"ok": False, "msg": "terrain.txt 里没有类型 %s" % terrain}
    new_idx = t2i[terrain]

    info = bmp_info(tbmp)
    if not info or info.get("bpp") != 8:
        return {"ok": False, "msg": "terrain.bmp 不是 8 位索引图，无法按像素刷"}
    W, H = info["w"], info["h"]
    off0, rowb = info["offset"], info["row"]
    top_down = bool(info.get("top_down"))

    # 收集要刷的像素（去重）
    hit = set()
    for pt in points:
        try:
            cx, cy = int(pt[0]), int(pt[1])
        except Exception:
            continue
        for dy in range(-brush, brush + 1):
            for dx in range(-brush, brush + 1):
                if dx * dx + dy * dy > brush * brush:
                    continue
                x, y = cx + dx, cy + dy
                if 0 <= x < W and 0 <= y < H:
                    hit.add((x, y))
    if not hit:
        return {"ok": False, "msg": "笔刷没落在图内"}

    # 原地 seek 写单字节：Image.save 会用 "w+b" 重开文件，在某些路径上直接 EINVAL
    snapshot(tbmp)
    with open(tbmp, "r+b") as f:
        for (x, y) in hit:
            fy = y if top_down else (H - 1 - y)
            f.seek(off0 + fy * rowb + x)
            f.write(bytes((new_idx,)))
    n = len(hit)
    try:
        _REFINE_IDS_CACHE.pop("cur", None)
    except Exception:
        pass
    return {"ok": True, "painted": n, "to": terrain,
            "msg": "刷了 %d 个像素为 %s · 需重建图层" % (n, terrain)}


def _sr_dirs(root):
    """战略区目录（先 mod 后原版），返回 [(base, dir)]"""
    out = []
    for base in reversed(mod_layers(root) or []):
        if not base:
            continue
        d = os.path.join(base, "map", "strategicregions")
        if os.path.isdir(d):
            out.append((base, d))
    if GAME:
        d = os.path.join(GAME, "map", "strategicregions")
        if os.path.isdir(d):
            out.append((GAME, d))
    return out


def _sr_parse_file(path):
    """一个文件里可能有多个 strategic_region 块"""
    out = []
    try:
        text = strip_comments(io.open(path, encoding="utf-8-sig", errors="replace").read())
    except Exception:
        return out
    for m in re.finditer(r'strategic_region\s*=\s*\{', text):
        b = text.find("{", m.end() - 1)
        e = brace_match(text, b)
        if e <= b:
            continue
        body = text[b + 1:e - 1]
        sid = re.search(r'(?m)^\s*id\s*=\s*(\d+)', body)
        if not sid:
            continue
        nm = re.search(r'(?m)^\s*name\s*=\s*"([^"]*)"', body)
        pr = re.search(r'provinces\s*=\s*\{([^}]*)\}', body)
        provs = [int(x) for x in re.findall(r'\d+', pr.group(1))] if pr else []
        out.append({"id": int(sid.group(1)),
                    "name": nm.group(1) if nm else "",
                    "provinces": provs,
                    "span": [b, e]})
    return out


def strategic_regions_list(root=None):
    """列出全部战略区；同 id 以最后一层（mod）为准"""
    root = _map_pick(root)
    seen = {}
    for base, d in _sr_dirs(root):
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            p = os.path.join(d, fn)
            for r in _sr_parse_file(p):
                if r["id"] in seen and os.path.abspath(base) == os.path.abspath(GAME or ""):
                    continue   # 原版的被 mod 覆盖
                seen[r["id"]] = {
                    "id": r["id"], "name": r["name"],
                    "count": len(r["provinces"]),
                    "provinces": r["provinces"][:400],
                    "file": os.path.relpath(p, base),
                    "base": os.path.abspath(base),
                    "fromMod": os.path.abspath(base) != os.path.abspath(GAME or ""),
                }
    items = sorted(seen.values(), key=lambda x: x["id"])
    return {"ok": True, "count": len(items), "items": items,
            "msg": "共 %d 个战略区" % len(items)}


def _sr_weather_template(root):
    """从任意一个现有战略区里抠出 weather 块，新建时作为模板"""
    for base, d in _sr_dirs(root):
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(d, fn)
            try:
                text = strip_comments(io.open(p, encoding="utf-8-sig", errors="replace").read())
            except Exception:
                continue
            m = re.search(r'weather\s*=\s*\{', text)
            if not m:
                continue
            b = text.find("{", m.end() - 1)
            e = brace_match(text, b)
            if e > b:
                return text[b:e]
    return ""


def _sr_write_dir(root):
    """新建战略区写到 mod 目录（输出模式下写到 output）"""
    root = _map_pick(root)
    base = root if root else (mod_layers(None) or [""])[0]
    d = _out_path(base, os.path.join("map", "strategicregions")) if OUTPUT_MODE else \
        os.path.join(base, "map", "strategicregions")
    os.makedirs(d, exist_ok=True)
    return base, d


def strategic_region_create(root=None, sid=None, name=None, provinces=None):
    """新建战略区。id 不给就取现有最大值 +1；weather 从现有区复制"""
    root = _map_pick(root)
    existing = strategic_regions_list(root)
    used = set(x["id"] for x in existing["items"])
    try:
        sid = int(sid) if sid not in (None, "") else (max(used) + 1 if used else 1)
    except Exception:
        return {"ok": False, "msg": "id 不合法"}
    if sid in used:
        return {"ok": False, "msg": "战略区 %d 已存在" % sid}
    provs = []
    if provinces:
        try:
            provs = sorted(set(int(x) for x in provinces if int(x) > 0))
        except Exception:
            return {"ok": False, "msg": "省份列表不合法"}
    if not provs:
        return {"ok": False, "msg": "至少要指定一个省"}

    # 一个省只能属于一个战略区，先检查
    owner = {}
    for it in existing["items"]:
        for p in it.get("provinces") or []:
            owner[p] = it["id"]
    clash = [(p, owner[p]) for p in provs if p in owner]
    if clash:
        return {"ok": False,
                "msg": "这些省已属于别的战略区：%s" % clash[:3]}

    b, d = _sr_write_dir(root)
    fn = "%d-New Strategic Region.txt" % sid
    path = os.path.join(d, fn)
    weather = _sr_weather_template(root)
    body = "strategic_region={\n\tid=%d\n\tname=\"%s\"\n\tprovinces={\n" % (
        sid, (name or ("STRATEGICREGION_%d" % sid)))
    for i in range(0, len(provs), 12):
        body += "\t\t" + " ".join(str(x) for x in provs[i:i + 12]) + "\n"
    body += "\t}\n"
    if weather:
        body += "\tweather=" + weather + "\n"
    body += "}\n"
    io.open(path, "wb").write(b"\xef\xbb\xbf" + body.encode("utf-8"))
    reload_data()
    return {"ok": True, "id": sid, "file": os.path.relpath(path, b),
            "provinces": len(provs), "weatherCopied": bool(weather),
            "msg": "已新建战略区 %d（%d 个省）%s" % (
                sid, len(provs), "，天气块已复制" if weather else "，没有找到天气模板")}


def _sr_find(root, sid):
    """按 id 找文件与块位置"""
    for base, d in _sr_dirs(root):
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            p = os.path.join(d, fn)
            for r in _sr_parse_file(p):
                if r["id"] == int(sid):
                    return base, p, r
    return None, None, None


def strategic_region_set_provinces(sid, provinces, root=None):
    """改某战略区覆盖的省份（整块替换 provinces = { }）"""
    root = _map_pick(root)
    try:
        sid = int(sid)
        provs = sorted(set(int(x) for x in (provinces or []) if int(x) > 0))
    except Exception:
        return {"ok": False, "msg": "参数不合法"}
    if not provs:
        return {"ok": False, "msg": "至少要有一个省"}
    base, path, rec = _sr_find(root, sid)
    if not path:
        return {"ok": False, "msg": "没有战略区 %d" % sid}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "这个战略区来自原版，只读"}
    text = io.open(path, encoding="utf-8-sig", errors="replace").read()
    b, e = rec["span"]
    body = text[b + 1:e - 1]
    inner = "\n" + "".join("\t\t" + " ".join(str(x) for x in provs[i:i + 12]) + "\n"
                            for i in range(0, len(provs), 12)) + "\t"
    m = re.search(r'provinces\s*=\s*\{', body)
    if m:
        pb = body.find("{", m.end() - 1)
        pe = brace_match(body, pb)
        if pe > pb:
            body2 = body[:pb] + "{" + inner + "}" + body[pe:]
        else:
            body2 = body
    else:
        body2 = body + "\n\tprovinces={" + inner + "}"
    new_text = text[:b + 1] + body2 + text[e - 1:]
    snapshot(path)
    io.open(path, "wb").write(b"\xef\xbb\xbf" + new_text.encode("utf-8"))
    return {"ok": True, "id": sid, "provinces": len(provs),
            "msg": "战略区 %d 现在覆盖 %d 个省" % (sid, len(provs))}


def strategic_region_delete(sid, root=None):
    """删除战略区：整个块从文件里摘掉；文件里没有其它块就删文件"""
    root = _map_pick(root)
    try:
        sid = int(sid)
    except Exception:
        return {"ok": False, "msg": "id 不合法"}
    base, path, rec = _sr_find(root, sid)
    if not path:
        return {"ok": False, "msg": "没有战略区 %d" % sid}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "这个战略区来自原版，只读"}
    text = io.open(path, encoding="utf-8-sig", errors="replace").read()
    others = [r for r in _sr_parse_file(path) if r["id"] != sid]
    if not others:
        snapshot(path)
        try:
            os.remove(path)
        except Exception as e:
            return {"ok": False, "msg": "删文件失败：%s" % e}
        return {"ok": True, "id": sid, "removedFile": True,
                "msg": "已删除战略区 %d 及其文件" % sid}
    b, e = rec["span"]
    # 连同前面的 strategic_region = { 一起摘掉
    start = text.rfind("strategic_region", 0, b)
    if start < 0:
        start = b
    new_text = text[:start] + text[e:]
    snapshot(path)
    io.open(path, "wb").write(b"\xef\xbb\xbf" + new_text.encode("utf-8"))
    return {"ok": True, "id": sid, "removedFile": False,
            "msg": "已从文件里移除战略区 %d（文件里还有 %d 个）" % (sid, len(others))}


def _build_rivers_png(root, w, h, dirp):
    """把 rivers.bmp 转成 RGBA 叠层：背景索引透明，河流保留原色。

    rivers.bmp 是调色板图，背景用 254/255，其余索引才是河。"""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    rp, _ = _layers_find("map/rivers.bmp", mod_layers(root))
    if not rp:
        return 0
    try:
        with Image.open(rp) as im:
            if im.size != (w, h):
                return 0
            pal = im.getpalette() or []
            src = im.convert("P")
            raw = src.tobytes()
            # 找出背景索引（出现最多的两个，通常是 254/255）
            from collections import Counter
            cnt = Counter(raw)
            bg = set([idx for idx, _c in cnt.most_common(2)])
            out = bytearray(w * h * 4)
            for i, v in enumerate(raw):
                o = i * 4
                if v in bg:
                    continue
                r = pal[v * 3] if len(pal) > v * 3 else 80
                g = pal[v * 3 + 1] if len(pal) > v * 3 + 1 else 120
                b = pal[v * 3 + 2] if len(pal) > v * 3 + 2 else 200
                out[o] = r
                out[o + 1] = g
                out[o + 2] = b
                out[o + 3] = 220
            img = Image.frombytes("RGBA", (w, h), bytes(out))
            img.save(os.path.join(dirp, "rivers.png"))
            return len(cnt) - len(bg)
    except Exception as e:
        print("  河流图层失败:", e)
        return 0


def _adj_file(root):
    for base in reversed(mod_layers(root) or []):
        if not base:
            continue
        p = os.path.join(base, "map", "adjacencies.csv")
        if os.path.exists(p):
            return p, base
    if GAME:
        p = os.path.join(GAME, "map", "adjacencies.csv")
        if os.path.exists(p):
            return p, GAME
    return None, None


def adjacencies_list(root=None):
    """海峡 / 陆地连接列表。坐标 -1 表示不画线，用省质心代替"""
    root = _map_pick(root)
    path, base = _adj_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/adjacencies.csv"}
    items = []
    try:
        raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    except Exception as e:
        return {"ok": False, "msg": "读取失败：%s" % e}
    lines = raw.splitlines()
    header = lines[0] if lines else ""
    for i, ln in enumerate(lines[1:], start=2):
        if not ln.strip() or ln.strip().startswith("#"):
            continue
        c = ln.split(";")
        if len(c) < 4:
            continue
        try:
            frm, to = int(c[0]), int(c[1])
        except Exception:
            continue
        through = c[3] if len(c) > 3 else ""
        coords = []
        if len(c) >= 8:
            try:
                sx, sy, ex, ey = int(c[4]), int(c[5]), int(c[6]), int(c[7])
                if sx >= 0 and sy >= 0:
                    coords = [sx, sy, ex, ey]
            except Exception:
                pass
        items.append({"line": i, "from": frm, "to": to,
                      "type": c[2] if len(c) > 2 else "",
                      "through": through, "coords": coords,
                      "rule": c[8] if len(c) > 8 else "",
                      "comment": c[9] if len(c) > 9 else ""})
    types = {}
    for a in items:
        types[a["type"]] = types.get(a["type"], 0) + 1
    return {"ok": True, "count": len(items), "types": types,
            "file": os.path.relpath(path, base) if base else path,
            "fromMod": bool(root and base and os.path.abspath(base) == os.path.abspath(root)),
            "items": items,
            "msg": "共 %d 条连接（%s）" % (
                len(items), "，".join("%s %d" % (k, v) for k, v in sorted(types.items())))}


def adjacency_edit(line, adj_type=None, root=None):
    """改某一条连接的类型（sea / land / lake 等）"""
    root = _map_pick(root)
    path, base = _adj_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/adjacencies.csv"}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "adjacencies.csv 来自原版，只读"}
    try:
        line = int(line)
    except Exception:
        return {"ok": False, "msg": "行号不合法"}
    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    lines = raw.splitlines(True)
    idx = line - 1
    if idx < 0 or idx >= len(lines):
        return {"ok": False, "msg": "没有第 %d 行" % line}
    c = lines[idx].rstrip("\r\n").split(";")
    if len(c) < 4:
        return {"ok": False, "msg": "这一行格式不对"}
    old = c[2]
    if adj_type:
        c[2] = adj_type
    tail = chr(10) if lines[idx].endswith(chr(10)) else ""
    lines[idx] = ";".join(c) + tail
    snapshot(path)
    io.open(path, "wb").write(b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
    return {"ok": True, "line": line, "from": old, "to": c[2],
            "msg": "第 %d 行的类型 %s → %s" % (line, old, c[2])}


def adjacency_delete(line, root=None):
    """删除一条连接"""
    root = _map_pick(root)
    path, base = _adj_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/adjacencies.csv"}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "adjacencies.csv 来自原版，只读"}
    try:
        line = int(line)
    except Exception:
        return {"ok": False, "msg": "行号不合法"}
    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    lines = raw.splitlines(True)
    idx = line - 1
    if idx < 0 or idx >= len(lines):
        return {"ok": False, "msg": "没有第 %d 行" % line}
    gone = lines[idx].rstrip("\r\n")
    del lines[idx]
    snapshot(path)
    io.open(path, "wb").write(b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
    return {"ok": True, "line": line, "removed": gone[:60],
            "msg": "已删除第 %d 行连接" % line}


def adjacency_add(frm, to, adj_type="sea", through="", root=None):
    """新增一条连接（追加到文件末尾）"""
    root = _map_pick(root)
    path, base = _adj_file(root)
    if not path:
        return {"ok": False, "msg": "找不到 map/adjacencies.csv"}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "adjacencies.csv 来自原版，只读"}
    try:
        frm, to = int(frm), int(to)
    except Exception:
        return {"ok": False, "msg": "省号不合法"}
    if frm == to:
        return {"ok": False, "msg": "两端不能是同一个省"}
    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    lines = raw.splitlines(True)
    for ln in lines[1:]:
        c = ln.split(";")
        if len(c) >= 2:
            try:
                a, b = int(c[0]), int(c[1])
            except Exception:
                continue
            if (a == frm and b == to) or (a == to and b == frm):
                return {"ok": False, "msg": "这两省之间已经有连接了"}
    row = "%d;%d;%s;%s;-1;-1;-1;-1;;" % (frm, to, adj_type or "sea", through or "")
    if not raw.endswith(chr(10)):
        lines[-1] = lines[-1] + chr(10)
    lines.append(row + chr(10))
    snapshot(path)
    io.open(path, "wb").write(b"\xef\xbb\xbf" + "".join(lines).encode("utf-8"))
    return {"ok": True, "from": frm, "to": to, "type": adj_type,
            "msg": "已新增连接 %d ↔ %d（%s）" % (frm, to, adj_type or "sea")}


def _equip_locate(root, eid):
    """找某个装备定义所在的文件与字符区间。

    装备都写在 equipments = { ... } 里，一个文件可以有多个 equipments 块。
    返回 (base, path, block_start, block_end, block_body)"""
    for base in reversed(mod_layers(root) or []):
        if not base:
            continue
        d = os.path.join(base, "common", "units", "equipment")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            p = os.path.join(d, fn)
            try:
                raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
            except Exception:
                continue
            # 必须用保长版本：下面算出的偏移要能直接切 raw
            text = _strip_keep_len(raw)
            for _s, _e, body in find_blocks(text, "equipments"):
                # top_items 的第三项是「有没有 {} 块」的布尔值，不是偏移，
                # 所以这里自己按 key 在 body 里定位 '{'，再换算到 text 坐标系。
                for k, _v, has_body in top_items(body):
                    if k != eid or not has_body:
                        continue
                    blk = find_blocks(body, None) if False else None
                    m = re.search(r'(?m)^[ \t]*' + re.escape(eid) + r'[ \t]*=[ \t]*\{', body)
                    if not m:
                        continue
                    rel_b = m.end() - 1                       # body 内 '{' 的位置
                    body_start = text.find("{", _s) + 1       # body 在 text 中的起点
                    b_abs = body_start + rel_b
                    e_abs = brace_match(text, b_abs)
                    if e_abs <= b_abs:
                        continue
                    return base, p, b_abs, e_abs, text[b_abs + 1:e_abs - 1]
    return None, None, None, None, None


def equipment_detail(eid, root=None):
    """某个装备的完整信息：属性、模块槽、来源文件、是否可编辑"""
    root = _map_pick(root)
    base, path, b, e, body = _equip_locate(root, eid)
    if not path:
        return {"ok": False, "msg": "找不到装备 %s" % eid}
    readonly = os.path.abspath(base) == os.path.abspath(GAME or "")

    # 标量属性（跳过块）
    scalars = {}
    for m in re.finditer(r'(?m)^[ \t]*([a-z_0-9]+)[ \t]*=[ \t]*([^\s{#]+)', body):
        k, v = m.group(1), m.group(2)
        scalars[k] = v

    # 模块槽
    slots = []
    for sm in re.finditer(r'module_slots\s*=\s*\{', body):
        sb = body.find("{", sm.end() - 1)
        se = brace_match(body, sb)
        if se <= sb:
            continue
        for sk, sv, sbb in top_items(body[sb + 1:se - 1]):
            if not sbb:
                continue
            req = re.search(r'(?m)^\s*required\s*=\s*(\w+)', sv)
            cats = []
            cm = re.search(r'allowed_module_categories\s*=\s*\{', sv)
            if cm:
                cb = sv.find("{", cm.end() - 1)
                ce = brace_match(sv, cb)
                cats = re.findall(r'[A-Za-z0-9_]+', sv[cb + 1:ce - 1])
            slots.append({"slot": sk,
                          "required": (req.group(1).lower() == "yes") if req else False,
                          "categories": cats})

    # 该 id 出现在哪些地方（引用）
    refs = []
    for rel_dir in ("common", "history", "events"):
        d = os.path.join(root, rel_dir)
        if not os.path.isdir(d):
            continue
        for dp, _dn, fs in os.walk(d):
            for f in fs:
                if not f.endswith(".txt"):
                    continue
                p2 = os.path.join(dp, f)
                try:
                    t2 = io.open(p2, encoding="utf-8-sig", errors="replace").read()
                except Exception:
                    continue
                if re.search(r'\b%s\b' % re.escape(eid), t2):
                    refs.append(os.path.relpath(p2, root))
                    if len(refs) >= 20:
                        break

    return {"ok": True, "id": eid,
            "file": os.path.relpath(path, base) if base else path,
            "readonly": readonly,
            "archetype": scalars.get("archetype", ""),
            "year": scalars.get("year", ""),
            "buildable": scalars.get("is_buildable", ""),
            "name": LOC.get(eid, eid),
            "scalars": scalars, "slots": slots, "refs": refs,
            "msg": "%s（%d 个属性，%d 个槽）" % (eid, len(scalars), len(slots))}


def equipment_edit(eid, props, root=None):
    """改装备的标量属性。

    props: {key: value}。key 已存在就改值，不存在就插入。
    块结构（module_slots / resources 等）不在这个接口的范围内，避免把嵌套写坏。"""
    root = _map_pick(root)
    if not isinstance(props, dict) or not props:
        return {"ok": False, "msg": "没有要改的属性"}
    base, path, b, e, body = _equip_locate(root, eid)
    if not path:
        return {"ok": False, "msg": "找不到装备 %s" % eid}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "这个装备来自原版，只读"}

    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    new_body = body
    changed = []
    for k, v in props.items():
        k = str(k).strip()
        v = str(v).strip()
        if not re.match(r'^[a-z_0-9]+$', k):
            return {"ok": False, "msg": "属性名不合法：%s" % k}
        if not v:
            continue
        pat = re.compile(r'(?m)^([ \t]*)%s([ \t]*=[ \t]*)([^\s{#\n]+)' % re.escape(k))
        m = pat.search(new_body)
        if m:
            if m.group(3) == v:
                continue
            new_body = new_body[:m.start(3)] + v + new_body[m.end(3):]
            changed.append("%s %s→%s" % (k, m.group(3), v))
        else:
            # 插到 body 末尾（前一个缩进对齐）
            indent = "\t\t"
            new_body = new_body.rstrip() + "\n" + indent + "%s = %s\n" % (k, v)
            changed.append("%s=%s（新增）" % (k, v))
    if not changed:
        return {"ok": True, "changed": [], "msg": "没有实际改动"}

    new_raw = raw[:b + 1] + new_body + raw[e - 1:]
    snapshot(path)
    io.open(path, "wb").write(b"\xef\xbb\xbf" + new_raw.encode("utf-8"))
    reload_data()
    return {"ok": True, "id": eid, "changed": changed,
            "msg": "已更新 %s：%s" % (eid, "，".join(changed))}


def equipment_delete(eid, root=None):
    """删除一个装备定义（摘掉整个块）"""
    root = _map_pick(root)
    base, path, b, e, body = _equip_locate(root, eid)
    if not path:
        return {"ok": False, "msg": "找不到装备 %s" % eid}
    if os.path.abspath(base) == os.path.abspath(GAME or ""):
        return {"ok": False, "msg": "这个装备来自原版，只读"}
    # 引用检查：还有别的地方用就不让删
    det = equipment_detail(eid, root)
    refs = [r for r in (det.get("refs") or []) if not r.endswith(os.path.basename(path))]
    if refs:
        return {"ok": False,
                "msg": "还有 %d 处引用这个装备，先改掉再删：%s" % (len(refs), refs[:3])}
    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    start = raw.rfind("\n", 0, b)
    if start < 0:
        start = b
    new_raw = raw[:start] + raw[e:]
    snapshot(path)
    io.open(path, "wb").write(b"\xef\xbb\xbf" + new_raw.encode("utf-8"))
    reload_data()
    return {"ok": True, "id": eid,
            "msg": "已删除装备 %s" % eid}


def equipment_list(root=None, query=None):
    """装备列表（可按 id 或名字过滤）"""
    root = _map_pick(root)
    items = []
    q = (query or "").strip().lower()
    for k, v in sorted(EQUIPMENTS.items()):
        nm = v.get("name") or k
        if q and q not in k.lower() and q not in str(nm).lower():
            continue
        items.append({"id": k, "name": nm, "file": v.get("file", ""),
                      "year": v.get("year", ""), "buildable": v.get("buildable", ""),
                      "archetype": (v.get("props") or {}).get("archetype", "")})
    return {"ok": True, "count": len(items), "items": items[:400],
            "total": len(items), "msg": "共 %d 个装备%s" % (
                len(items), ("（含 %s）" % query) if q else "")}


def _state_prov_list(sid):
    """某个州的省列表"""
    s = STATES.get(int(sid)) if isinstance(STATES, dict) else None
    if not s:
        for v in (STATES.values() if isinstance(STATES, dict) else []):
            if int(v.get("id") or 0) == int(sid):
                s = v
                break
    if not s:
        return []
    return [int(x) for x in (s.get("provinces") or [])]


def state_refine_preview(sid, k=2, root=None):
    """预览：把州 sid 的省分成 k 组。

    用的是和省份细化同一套算法 _refine_grow_units：
    单元 = 省，邻居 = 省邻接图，坐标 = 省质心。
    """
    root = _map_pick(root)
    try:
        sid = int(sid)
        k = max(2, min(8, int(k or 2)))
    except Exception:
        return {"ok": False, "msg": "参数不合法"}
    provs = _state_prov_list(sid)
    if len(provs) < k:
        return {"ok": False,
                "msg": "州 %d 只有 %d 个省，拆不成 %d 份" % (sid, len(provs), k)}

    allnb = _all_prov_neighbors(root)
    pset = set(provs)
    nb = {p: [x for x in (allnb.get(p) or []) if x in pset] for p in provs}

    # 质心：从省号数组现算（前端才有 centers.json，后端用像素均值）
    ids, w, h = _refine_load_ids(root)
    sums = {}
    if ids:
        for i, pid in enumerate(ids):
            if pid in pset:
                acc = sums.get(pid)
                x, y = i % w, i // w
                if acc is None:
                    sums[pid] = [x, y, 1]
                else:
                    acc[0] += x
                    acc[1] += y
                    acc[2] += 1
    centers = {}
    for p in provs:
        a = sums.get(p)
        if a and a[2]:
            centers[p] = (a[0] / a[2], a[1] / a[2])
        else:
            centers[p] = (0.0, 0.0)

    groups = _refine_grow_units(provs, nb, k, centers)
    parts = []
    for gi in sorted(groups):
        mem = sorted(groups[gi])
        parts.append({"i": gi, "count": len(mem), "provs": mem})

    # 警告
    warn = []
    s = STATES.get(sid) or {}
    owner = s.get("owner") or s.get("owner_tag") or ""
    if owner:
        warn.append("新州会继承归属国 %s 与 cores" % owner)
    vps = s.get("victory_points") or []
    if vps:
        warn.append("原州有 %d 个胜利点，拆分后只留在第 1 组" % len(vps))
    if s.get("category"):
        warn.append("新州类别沿用 %s，人力沿用原值（不会按面积重算）" % s.get("category"))

    return {"ok": True, "sid": sid, "k": len(parts), "total": len(provs),
            "parts": parts, "warnings": warn,
            "msg": "州 %d 的 %d 个省拆成 %d 份：%s" % (
                sid, len(provs), len(parts),
                " / ".join(str(p["count"]) for p in parts))}


def _state_fields_from(sid):
    """从原州提取要继承的字段"""
    s = STATES.get(sid) or {}
    return {
        "owner": s.get("owner") or s.get("owner_tag") or "",
        "cores": list(s.get("cores") or s.get("states_core") or []),
        "category": s.get("category") or "rural",
        "manpower": str(s.get("manpower") or ""),
    }


def state_refine_apply(sid, k=2, root=None):
    """应用：第 1 组留在原州，其余各组建成新州（继承归属国/核心/类别/人力）。"""
    pv = state_refine_preview(sid, k, root)
    if not pv.get("ok"):
        return pv
    root = _map_pick(root)
    sid = pv["sid"]
    parts = pv["parts"]
    base = _state_fields_from(sid)

    # 1) 原州只留第一组
    first = parts[0]["provs"]
    _r, _rel, fpath = _state_file_for(sid)
    if not fpath:
        return {"ok": False, "msg": "找不到州 %d 的文件" % sid}
    if is_under_game(_r or ""):
        return {"ok": False, "msg": "州 %d 来自原版，只读" % sid}
    try:
        text, has_bom = _read_bom_text(fpath)
        loc = _state_locate(text)
        b, e = loc
        body = text[b + 1:e - 1]
        new_body = _set_state_provinces(body, first)
        snapshot(fpath)
        _write_bom_text(fpath, text[:b + 1] + new_body + text[e - 1:], has_bom)
    except Exception as ex:
        return {"ok": False, "msg": "改原州失败：%s" % ex}

    # 2) 其余组各建一个新州
    created = []
    failed = []
    for p in parts[1:]:
        r = state_create(p["provs"], root, None, base["category"],
                         int(base["manpower"]) if base["manpower"].isdigit() else 100000)
        if not r.get("ok"):
            failed.append({"provs": p["provs"][:3], "msg": r.get("msg")})
            continue
        nid = r.get("id") or r.get("sid")
        created.append({"id": nid, "count": p["count"]})
        # 继承字段
        if nid and base["owner"]:
            try:
                state_save(nid, {"owner": base["owner"], "cores": base["cores"]})
            except Exception:
                pass
    reload_data()
    msg = "州 %d 拆成 %d 份：原州留 %d 省" % (sid, len(parts), len(first))
    if created:
        msg += "，新建 " + "、".join("%s(%d省)" % (c["id"], c["count"]) for c in created)
    if failed:
        msg += "；%d 份失败：%s" % (len(failed), failed[0].get("msg"))
    return {"ok": True, "sid": sid, "kept": first, "created": created,
            "failed": failed, "parts": len(parts), "msg": msg}


def orphan_tags(root=None):
    """州里引用了 owner，但国家表（COUNTRIES）里不存在的 tag。

    mod 换了国家表但没跟着改 history/states 时会出现这种不一致；
    游戏里这些省会指向不存在的国家，政治图上没法给它们上色。"""
    root = _map_pick(root)
    by_tag = {}
    for sid, st in (STATES.items() if isinstance(STATES, dict) else []):
        ow = (st.get("owner") or "").strip().upper()
        if not ow or ow in COUNTRIES:
            continue
        rec = by_tag.setdefault(ow, {"tag": ow, "states": 0, "provinces": 0,
                                     "sample_states": [], "files": []})
        rec["states"] += 1
        rec["provinces"] += len(st.get("provinces") or [])
        if len(rec["sample_states"]) < 6:
            rec["sample_states"].append(st.get("id"))
        f = st.get("file") or ""
        if f and f not in rec["files"] and len(rec["files"]) < 4:
            rec["files"].append(f)

    items = sorted(by_tag.values(), key=lambda x: -x["provinces"])
    used = set()
    for st in (STATES.values() if isinstance(STATES, dict) else []):
        ow = (st.get("owner") or "").strip().upper()
        if ow:
            used.add(ow)
    unused = sorted(t for t in COUNTRIES if t not in used)
    total_states = sum(x["states"] for x in items)
    total_prov = sum(x["provinces"] for x in items)
    msg = ("%d 个 tag 在国家表里不存在，涉及 %d 个州 / %d 个省" % (
        len(items), total_states, total_prov)) if items else \
        "没有孤儿 tag，州引用的 owner 都在国家表里"
    return {"ok": True, "count": len(items),
            "total_states": total_states, "total_provinces": total_prov,
            "states_all": len(STATES), "countries_all": len(COUNTRIES),
            "items": items, "unused_tags": unused[:40],
            "unused_count": len(unused), "msg": msg}


def _tag_fallback_color(tag):
    """没有定义颜色的 tag（mod 里州引用了不存在的国家）按 tag 哈希生成稳定色。

    比直接落到中性灰好：至少能看出边界和政治区划，
    不会让整片大陆看起来像数据缺失。"""
    import hashlib
    # 预定义调色板：20 种区分度足够的颜色，按哈希取模。
    # 用 HSV 现算会在某些色相区间退化成相近的 RGB（红区都变成 R=191），
    # 调色板能保证任意两个 tag 落在视觉上不同的色块。
    palette = (
        (230, 90, 90), (90, 160, 230), (110, 200, 120), (240, 190, 90),
        (180, 120, 220), (90, 200, 200), (230, 140, 200), (150, 190, 90),
        (200, 110, 80), (120, 140, 220), (200, 200, 100), (140, 100, 180),
        (100, 180, 160), (220, 160, 120), (160, 200, 200), (200, 130, 130),
        (130, 170, 220), (180, 200, 120), (220, 170, 200), (140, 160, 120),
    )
    h = int(hashlib.md5(str(tag or '').encode('utf-8')).hexdigest()[:8], 16)
    return bytes(palette[h % len(palette)])


def _prov_type_map(root):
    """省号 → definition.csv 第 5 列（land / sea / lake 等）。

    政治图层要区分「海洋」和「无主陆地」：前者给海色，后者给中性灰，
    否则大片海洋会被画成深色，看起来像地图缺了一块。"""
    cache = getattr(_prov_type_map, "_cache", None)
    layers = mod_layers(root or None)
    csvp, _ = _layers_find("map/definition.csv", layers)
    if not csvp:
        return {}
    key = (os.path.abspath(csvp), int(os.path.getmtime(csvp)))
    if cache and cache[0] == key:
        return cache[1]
    out = {}
    try:
        with io.open(csvp, encoding="utf-8", errors="replace") as f:
            for line in f:
                p = line.strip().split(";")
                if len(p) >= 5 and p[0].isdigit():
                    out[int(p[0])] = (p[4] or "").strip().lower()
    except Exception:
        pass
    _prov_type_map._cache = (key, out)
    return out


def _supply_dir_write(root):
    """补给区写到哪：链顶 mod 的 map/supplyareas"""
    root = _map_pick(root)
    base = root if root else (ROOTS[-1] if ROOTS else "")
    if not base:
        return None, None
    d = _out_path(base, os.path.join("map", "supplyareas")) if OUTPUT_MODE else \
        os.path.join(base, "map", "supplyareas")
    os.makedirs(d, exist_ok=True)
    return base, d


def supply_area_save(sid, value=None, states=None, name=None, root=None):
    """新建或修改一个补给区。

    sid 已存在就改（value / states / name），不存在就新建文件。
    写法沿用 HOI4 的 supply_area={ id name value states }。"""
    root = _map_pick(root)
    try:
        sid = int(sid)
    except Exception:
        return {"ok": False, "msg": "补给区 id 不合法"}
    base, d = _supply_dir_write(root)
    if not d:
        return {"ok": False, "msg": "找不到可写的 mod 目录"}

    # 找现有文件
    exist_path = None
    for _b, _d in _layer_dirs("map/supplyareas", root):
        for fn in sorted(os.listdir(_d)):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(_d, fn)
            try:
                t = strip_comments(io.open(p, encoding="utf-8-sig", errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'supply_area\s*=\s*\{', t):
                b = t.find("{", m.end() - 1)
                e = brace_match(t, b)
                if e <= b:
                    continue
                body = t[b + 1:e - 1]
                mm = re.search(r'(?m)^\s*id\s*=\s*(\d+)', body)
                if mm and int(mm.group(1)) == sid:
                    exist_path = p
                    break
            if exist_path:
                break
        if exist_path:
            break

    # 现有值（改的时候保留没传的字段）
    cur_value, cur_states, cur_name = 12, [], "SUPPLYAREA_%d" % sid
    if exist_path:
        try:
            t = strip_comments(io.open(exist_path, encoding="utf-8-sig", errors="replace").read())
            b = t.find("{", t.find("supply_area"))
            e = brace_match(t, b)
            body = t[b + 1:e - 1]
            mv = re.search(r'(?m)^\s*value\s*=\s*(\d+)', body)
            if mv:
                cur_value = int(mv.group(1))
            mn = re.search(r'(?m)^\s*name\s*=\s*"([^"]*)"', body)
            if mn:
                cur_name = mn.group(1)
            ms = re.search(r'states\s*=\s*\{([^}]*)\}', body)
            if ms:
                cur_states = [int(x) for x in re.findall(r'\d+', ms.group(1))]
        except Exception:
            pass

    if value not in (None, ""):
        try:
            cur_value = int(value)
        except Exception:
            return {"ok": False, "msg": "value 必须是整数"}
    if name:
        cur_name = str(name)
    if states:
        try:
            cur_states = sorted({int(x) for x in states})
        except Exception:
            return {"ok": False, "msg": "states 列表不合法"}
    if not cur_states:
        return {"ok": False, "msg": "至少要给一个州"}

    # 州必须存在
    bad = [x for x in cur_states if str(x) not in STATES and x not in STATES]
    if bad:
        return {"ok": False, "msg": "这些州不存在：%s" % bad[:5]}

    fn = os.path.basename(exist_path) if exist_path else ("%d-SupplyArea.txt" % sid)
    path = os.path.join(d, fn)
    inner = "\n" + "".join("\t\t%d\n" % x for x in cur_states) + "\t"
    body = ('supply_area={\n\tid=%d\n\tname="%s"\n\tvalue=%d\n\tstates={%s}\n}\n'
            % (sid, cur_name, cur_value, inner))
    io.open(path, "wb").write(b"\xef\xbb\xbf" + body.encode("utf-8"))
    reload_data()
    return {"ok": True, "id": sid, "file": os.path.basename(path),
            "value": cur_value, "states": cur_states,
            "created": not bool(exist_path),
            "msg": "%s补给区 %d（value=%d，%d 个州）" % (
                "已新建" if not exist_path else "已更新", sid, cur_value, len(cur_states))}


def supply_area_delete(sid, root=None):
    """删除一个补给区：只从当前 mod 层的文件里摘，原版不动"""
    root = _map_pick(root)
    try:
        sid = int(sid)
    except Exception:
        return {"ok": False, "msg": "id 不合法"}
    base, d = _supply_dir_write(root)
    if not d:
        return {"ok": False, "msg": "找不到可写的 mod 目录"}
    # 只处理自己目录里的文件
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".txt"):
            continue
        p = os.path.join(d, fn)
        try:
            t = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        ct = strip_comments(t)
        found = False
        for m in re.finditer(r'supply_area\s*=\s*\{', ct):
            b = ct.find("{", m.end() - 1)
            e = brace_match(ct, b)
            if e <= b:
                continue
            mm = re.search(r'(?m)^\s*id\s*=\s*(\d+)', ct[b + 1:e - 1])
            if mm and int(mm.group(1)) == sid:
                found = True
                break
        if not found:
            continue
        try:
            snapshot(p)
            os.remove(p)
        except Exception as ex:
            return {"ok": False, "msg": "删除失败：%s" % ex}
        reload_data()
        return {"ok": True, "id": sid, "msg": "已删除补给区 %d（%s）" % (sid, fn)}
    return {"ok": False,
            "msg": "补给区 %d 不在当前 mod 层里（可能来自原版或父 mod，只读）" % sid}


def _terrain_colors(root):
    """从 common/terrain/*.txt 读各地形类别的游戏内配色 {name: (r,g,b)}。
    mod 定义了同名类别就覆盖原版；读不到就返回空字典。"""
    out = {}
    for base in reversed(mod_layers(root)):      # 原版 → ... → mod（后覆盖前）
        d = os.path.join(base or "", "common", "terrain")
        if not os.path.isdir(d):
            continue
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8-sig",
                                              errors="replace").read())
            except Exception:
                continue
            m = re.search(r'(?m)^categories\s*=\s*\{', text)
            if not m:
                continue
            b = text.find("{", m.end() - 1)
            e = brace_match(text, b)
            if e <= b:
                continue
            body = text[b + 1:e - 1]
            # 只取一级子块：行首单个 tab 缩进的 name = {
            for cm in re.finditer(r'(?m)^\t([a-zA-Z_][\w]*)\s*=\s*\{', body):
                name = cm.group(1)
                cb = body.find("{", cm.end() - 1)
                ce = brace_match(body, cb)
                if ce <= cb:
                    continue
                sub = body[cb + 1:ce - 1]
                col = re.search(r'color\s*=\s*\{\s*(\d+)\s+(\d+)\s+(\d+)\s*\}', sub)
                if col:
                    out[name] = [int(col.group(1)), int(col.group(2)), int(col.group(3))]
    # 亮度归一化：游戏里地形色差异很大（marsh 76,96,35 与 plains 255,129,66 差 3 倍），
    # 直接铺到 2D 地图上会显得一半发黑。把陆地的最大分量抬到 210 左右，色相不变；
    # 海洋/湖泊保持原值（水本来就该深）。
    for name, c in list(out.items()):
        if name in ("ocean", "lakes", "unknown"):
            out[name] = tuple(c)
            continue
        mx = max(c) or 1
        target = 210
        if mx < target:
            f = target / float(mx)
            out[name] = tuple(min(255, int(v * f)) for v in c)
        else:
            out[name] = tuple(c)
    return out


def map_integrity(root=None, limit=200):
    """地图完整性检查：连通性、州/战略区连续、无效 ID、十字交叉、铁路断连、无主/超大省"""
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "还没有加载 mod"}
    dirp, _, base = _map_dir(root)
    if not dirp or not os.path.exists(os.path.join(dirp, "prov_id.png")):
        return {"ok": False, "msg": "请先构建图层（缺少 prov_id.png）"}
    t0 = time.time()
    ids, w, h, raw = _map_ids_from_cache(dirp)
    if not ids:
        return {"ok": False, "msg": "读取图层缓存失败"}
    n = w * h
    items = []

    def add(level, title, detail, provs=None):
        items.append({"level": level, "kind": "map", "title": title,
                      "detail": detail or "", "provinces": provs or []})

    # 省集合与像素数
    px = {}
    for i in range(n):
        pid = ids[i]
        if pid:
            px[pid] = px.get(pid, 0) + 1
    known = set(px)

    # 4-邻接 + 十字交叉
    adj = {}
    cross = 0
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            a = ids[i]
            if x + 1 < w:
                b = ids[i + 1]
                if a != b:
                    if a and b:
                        adj.setdefault(a, set()).add(b)
                        adj.setdefault(b, set()).add(a)
            if y + 1 < h:
                b = ids[i + w]
                if a != b:
                    if a and b:
                        adj.setdefault(a, set()).add(b)
                        adj.setdefault(b, set()).add(a)
                # 2x2 十字：左上==右下 且 右上==左下 且 两两不同
                if x + 1 < w:
                    c = ids[i + 1]
                    d = ids[i + w]
                    e = ids[i + w + 1]
                    if a == e and c == d and a != c and a and c:
                        cross += 1

    # 省份像素连通（BFS）
    seen = bytearray(n)
    comp = {}
    for i in range(n):
        if seen[i]:
            continue
        pid = ids[i]
        if not pid:
            seen[i] = 1
            continue
        stack = [i]
        seen[i] = 1
        cnt = 0
        while stack:
            cur = stack.pop()
            cnt += 1
            cy, cx = divmod(cur, w)
            for nb in (cur - 1 if cx > 0 else -1,
                       cur + 1 if cx + 1 < w else -1,
                       cur - w if cy > 0 else -1,
                       cur + w if cy + 1 < h else -1):
                if nb < 0 or seen[nb]:
                    continue
                if ids[nb] == pid:
                    seen[nb] = 1
                    stack.append(nb)
        comp[pid] = comp.get(pid, 0) + 1

    bad_comp = [(pid, c) for pid, c in comp.items() if c > 1]

    # 州 / 战略区归属
    prov2state = {}
    prov2state_one = {}
    for sid, st in STATES.items():
        try:
            sid_int = int(st.get("id") or sid)
        except Exception:
            continue
        for p in (st.get("provinces") or []):
            try:
                pid_i = int(p)
            except Exception:
                continue
            prov2state.setdefault(pid_i, []).append(sid_int)
            if pid_i not in prov2state_one:
                prov2state_one[pid_i] = sid_int
    prov2region, region_list = _strategic_regions(root)

    # 一省多州 / 无效 ID
    multi = [(pid, sids) for pid, sids in prov2state.items() if len(sids) > 1]
    dead_state = [pid for pid in prov2state if pid not in known]
    dead_region = [pid for pid in prov2region if pid not in known]

    def group_split(mapping, label):
        """按州/地区分组，用省邻接图判断每组是否连通"""
        groups = {}
        for pid, v in mapping.items():
            groups.setdefault(v, set()).add(pid)
        bad = []
        for gid, members in groups.items():
            members = set(m for m in members if m in known)
            if len(members) < 2:
                continue
            start = next(iter(members))
            stack = [start]
            visited = {start}
            while stack:
                cur = stack.pop()
                for nb in adj.get(cur, ()):
                    if nb in members and nb not in visited:
                        visited.add(nb)
                        stack.append(nb)
            if len(visited) != len(members):
                bad.append((gid, len(members), len(visited)))
        return bad

    split_state = group_split(prov2state_one, "州")
    split_region = group_split(prov2region, "战略区")

    # 铁路
    rail_bad = 0
    rail_check = 0
    rp = None
    for b in (root, GAME):
        cand = os.path.join(b or "", "map", "railways.txt")
        if os.path.exists(cand):
            rp = cand
            break
    if rp:
        try:
            text = strip_comments(io.open(rp, encoding="utf-8", errors="replace").read())
            for m in re.finditer(r'railway\s*=\s*\{([^{}]*)\}', text):
                body = m.group(1)
                pm = re.search(r'provinces\s*=\s*\{([^}]*)\}', body)
                if not pm:
                    continue
                chain = [int(x) for x in re.findall(r'\d+', pm.group(1))]
                for a, b2 in zip(chain, chain[1:]):
                    rail_check += 1
                    if b2 not in adj.get(a, set()):
                        rail_bad += 1
        except Exception:
            pass

    # 无主省 / 超大省
    no_state = [pid for pid in known if pid not in prov2state and px.get(pid, 0) > 0]
    big = sorted(((pid, c) for pid, c in px.items() if c > 2000), key=lambda x: -x[1])[:30]

    # 地图定义一致性（读缓存里的 meta）
    try:
        _mp = os.path.join(dirp, "meta.json")
        if os.path.exists(_mp):
            _m = json.loads(io.open(_mp, encoding="utf-8").read())
            _c = _m.get("consistency") or {}
            if _c.get("ghost"):
                add("warn", "definition.csv 里有 %d 个省在地图上没有像素" % _c["ghost"],
                    "例如省 " + ", ".join(str(x) for x in (_c.get("ghost_sample") or [])[:12]) +
                    "；可能是删省后没清 definition.csv", (_c.get("ghost_sample") or [])[:20])
            if _c.get("unset_pixels"):
                add("warn", "%.2f%% 的像素颜色在 definition.csv 里找不到（%d 像素）" %
                    (_c.get("unset_ratio", 0), _c["unset_pixels"]),
                    "这些像素会被当成无主地；通常是 bmp 与 csv 不同步，或父子 mod 的 csv/bmp 混用", [])
            if _c.get("dup_rgb"):
                add("error", "%d 组省在 definition.csv 里用了同一个 RGB" % _c["dup_rgb"],
                    "同色会让后定义的省永远不出现；例如 " + json.dumps(
                        (_c.get("dup_rgb_sample") or [])[:3], ensure_ascii=False)[:160], [])
    except Exception as _e:
        print("一致性检查读取失败:", _e)

    # 汇总条目
    if bad_comp:
        items.append({"level": "warn", "kind": "map",
                      "title": "%d 个省份由多块不相连的区域组成（岛屿/飞地或碎片）" % len(bad_comp),
                      "detail": "例如省 " + ", ".join("%d（%d 块）" % (p, c) for p, c in bad_comp[:8]),
                      "provinces": [p for p, c in bad_comp[:20]]})
    if multi:
        add("error", "%d 个省份同时属于多个州" % len(multi),
            "例如省 %s" % ", ".join("%d→州%s" % (p, s) for p, s in multi[:5]),
            [p for p, s in multi[:20]])
    if split_state:
        add("warn", "%d 个州在图上不连续（多为岛屿/飞地，需逐个人工确认）" % len(split_state),
            "例如州 " + ", ".join("%d（%d 省，最大连通 %d）" % g for g in split_state[:6]),
            [])
    if split_region:
        add("warn", "%d 个战略区不连续（多为跨海区域）" % len(split_region),
            "例如地区 " + ", ".join("%d（%d 省，最大连通 %d）" % g for g in split_region[:6]),
            [])
    if dead_state:
        add("error", "州里引用了 %d 个不存在的省" % len(dead_state),
            "例如 " + ", ".join(str(x) for x in dead_state[:10]), dead_state[:20])
    if dead_region:
        add("error", "战略区里引用了 %d 个不存在的省" % len(dead_region),
            "例如 " + ", ".join(str(x) for x in dead_region[:10]), dead_region[:20])
    if cross:
        add("warn", "%d 处十字交叉像素（2×2 对角线歧义）" % cross,
            "会在地图上产生斜角接缝，可用「检查」后手动修或跑修复", [])
    if rail_check and rail_bad:
        add("warn", "铁路有 %d 段两端省份不相邻（共检查 %d 段）" % (rail_bad, rail_check),
            "可能是拆分/删除省份后遗留", [])
    if no_state:
        add("info", "%d 块陆地省份不属于任何州" % len(no_state),
            "例如 " + ", ".join(str(x) for x in no_state[:10]), no_state[:20])
    if big:
        add("info", "%d 个省份面积超过 2000 像素（细化候选）" % len(big),
            "最大：" + ", ".join("%d（%d px）" % (p, c) for p, c in big[:6]), [p for p, c in big[:10]])

    counts = {"error": 0, "warn": 0, "info": 0}
    for it in items:
        counts[it["level"]] = counts.get(it["level"], 0) + 1
    return {"ok": True, "items": items[:limit], "stats": counts,
            "sizes": {"w": w, "h": h, "provinces": len(known)},
            "ms": int((time.time() - t0) * 1000), "source": base}


def map_asset(name, root=None):


    """返回缓存目录里的资产路径（白名单，防路径穿越）"""
    if name not in MAP_ASSETS:
        return None
    root = _map_pick(root)
    dirp, _, _ = _map_dir(root) if root else (None, None, None)
    if not dirp:
        return None
    p = os.path.join(dirp, name)
    return p if os.path.exists(p) else None



# v0.86 游戏日志检查（error.log）
LOG_PATTERNS = [
    ("railway", "warn", r"Railway level .*MAX_RAILWAY_LEVEL", "铁路等级超过上限",
     "把 railways.txt 里对应线路的 level 降到 5 以内"),
    ("trigger", "warn", r"Invalid trigger", "无效的 trigger",
     "多为拼错或 1.19 已改名的 trigger，对照语法参考改"),
    ("deprecated", "warn", r"Using deprecated property", "使用了已弃用的属性",
     "旧写法仍能跑但会在日志刷屏，建议按提示改名"),
    ("gfx", "info", r"GFX referenced .* does not exist", "引用了不存在的 GFX",
     "装备/单位图标缺图，检查 gfx 定义或图标名拼写"),
    ("entity", "info", r"Failed to find entity", "缺少 3D 实体（模型）",
     "多为模型文件缺失，纯视觉问题，不影响逻辑"),
    ("sound", "info", r"Could not load sound file|already added", "音效缺失或重复",
     "声音定义文件里有重复项或文件不存在"),
    ("version", "info", r"Invalid supported_version", "descriptor 的 supported_version 写法不对",
     "改成 \"1.19.*\" 或与玩家版本一致"),
    ("loc", "warn", r"Unknown loc key|Missing localisation|Localisation key", "本地化缺失",
     "补 loc key，注意 .yml 必须是 UTF-8 带 BOM"),
    ("syntax", "error", r"Unexpected token|Expecting .* but got|Error parsing", "脚本语法错误",
     "括号/引号/赋值写错，按日志里的 file:line 定位"),
]


def _log_paths():
    """候选 error.log 位置"""
    out = []
    home = os.path.expanduser("~")
    for p in (os.path.join(home, "Documents", "Paradox Interactive", "Hearts of Iron IV", "logs", "error.log"),
              os.path.join(home, "OneDrive", "Documents", "Paradox Interactive", "Hearts of Iron IV", "logs", "error.log")):
        if os.path.exists(p):
            out.append(p)
    return out


# v0.86 铁路等级静态检查
def _rail_over_level(root, max_level=5):
    """返回 level 超过上限的铁路条数（HOI4 默认上限 5，日志里会刷 Railway level > MAX）"""
    for base in (root, GAME):
        p = os.path.join(base or "", "map", "railways.txt")
        if not os.path.exists(p):
            continue
        try:
            text = strip_comments(io.open(p, encoding="utf-8", errors="replace").read())
        except Exception:
            return 0, 0
        over = 0
        total = 0
        # 格式一：railway = { level = N provinces = { ... } }
        for m in re.finditer(r'railway\s*=\s*\{', text):
            b = text.find('{', m.end() - 1)
            e = brace_match(text, b)
            if e <= b:
                continue
            total += 1
            lv = re.search(r'level\s*=\s*(\d+)', text[b + 1:e - 1])
            if lv and int(lv.group(1)) > max_level:
                over += 1
        # 格式二（MUVLUV 等老 mod）：每行 "level count p1 p2 ..."
        if not total:
            for ln in text.splitlines():
                parts = ln.split()
                if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                    total += 1
                    if int(parts[0]) > max_level:
                        over += 1
        return over, total
    return 0, 0


# v0.87 日志快照（防止 error.log 被下一次启动覆盖）
LOG_SNAP_DIR = os.path.join(WORK, "logs")
LOG_KEEP = 10


def _log_snapshot(src):
    """把当前 error.log 复制一份带时间戳的快照，返回 (快照路径, 快照时间, 是否新建)"""
    try:
        os.makedirs(LOG_SNAP_DIR, exist_ok=True)
        st = os.stat(src)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(st.st_mtime))
        dst = os.path.join(LOG_SNAP_DIR, "error_%s.log" % stamp)
        created = not os.path.exists(dst)
        if created:
            shutil.copy2(src, dst)
            # 只保留最近 N 份
            snaps = sorted(f for f in os.listdir(LOG_SNAP_DIR) if f.startswith("error_") and f.endswith(".log"))
            for old in snaps[:-LOG_KEEP]:
                try:
                    os.remove(os.path.join(LOG_SNAP_DIR, old))
                except Exception:
                    pass
        return dst, stamp, created
    except Exception:
        return src, "", False


def read_error_log(path=None, limit_files=40):
    """解析 error.log：按类别聚合，给出计数、样例与涉及文件"""
    cand = [path] if path else _log_paths()
    if not cand or not os.path.exists(cand[0]):
        return {"ok": False, "msg": "没找到 error.log（先运行一次游戏）"}
    p = cand[0]
    snap, stamp, created = _log_snapshot(p)
    try:
        text = io.open(snap if os.path.exists(snap) else p, encoding="utf-8", errors="replace").read()
    except Exception as e:
        return {"ok": False, "msg": "读取日志失败：%s" % e}
    lines = text.splitlines()
    pat = re.compile(r"^\[(\d\d:\d\d:\d\d)\]\[([^\]]*)\]\[([^\]]+)\]:\s*(.*)$")
    buckets = {}
    unmatched = 0
    files = {}
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        m = pat.match(ln)
        if not m:
            unmatched += 1
            continue
        _t, _d, where, msg = m.groups()
        hit = None
        for key, level, rx, title, hint in LOG_PATTERNS:
            if re.search(rx, msg):
                hit = (key, level, title, hint)
                break
        if not hit:
            continue
        key, level, title, hint = hit
        b = buckets.setdefault(key, {"key": key, "level": level, "title": title, "hint": hint,
                                     "count": 0, "samples": [], "files": {}})
        b["count"] += 1
        if len(b["samples"]) < 3:
            b["samples"].append(msg[:160])
        fm = re.search(r'file:\s*"?([^"\s]+)"?(?:\s+line:\s*(\d+))?', msg)
        if fm:
            f = fm.group(1).replace("\\", "/").lstrip("./")
            owner = "other"
            try:
                root0 = ROOTS[0] if ROOTS else GAME
                if os.path.exists(os.path.join(root0 or "", f)):
                    owner = "mine"
                elif os.path.exists(os.path.join(GAME or "", f)):
                    owner = "vanilla"
            except Exception:
                pass
            b.setdefault("owners", {})
            b["owners"][owner] = b["owners"].get(owner, 0) + 1
            if owner == "mine":
                b["files"][f] = b["files"].get(f, 0) + 1
                files[f] = files.get(f, 0) + 1
    items = []
    for key, b in sorted(buckets.items(), key=lambda kv: -kv[1]["count"]):
        top_files = sorted(b["files"].items(), key=lambda kv: -kv[1])[:4]
        own = b.get("owners") or {}
        mine_n = own.get("mine", 0)
        van_n = own.get("vanilla", 0)
        detail = "；".join("%s ×%d" % (f, n) for f, n in top_files) or "（日志未给出文件名）"
        if own:
            detail += "　[本 mod %d / 原版 %d / 其它 %d]" % (mine_n, van_n, own.get("other", 0))
        lvl = b["level"]
        if lvl == "error" and own and mine_n == 0:
            lvl = "info"   # 报错不来自本 mod，降级
        items.append({"level": lvl, "kind": "log",
                      "title": "%s（%d 条）" % (b["title"], b["count"]),
                      "detail": detail + "　建议：" + b["hint"],
                      "samples": b["samples"]})
    return {"ok": True, "path": p, "snapshot": snap, "snapshot_stamp": stamp,
            "snapshot_created": created, "lines": len(lines), "unmatched": unmatched,
            "items": items, "files": sorted(files.items(), key=lambda kv: -kv[1])[:limit_files]}


def _bom_issues(root, limit=40):
    """编码规范检查（HOI4 要求）：
    - localisation/*.yml 必须带 UTF-8 BOM（否则游戏读不到本地化）
    - common / history / events 下的 .txt 不应带 BOM
    返回 (问题列表 [(类型, 相对路径)], yml 总数, txt 总数)"""
    root = os.path.abspath(root)
    BOM3 = bytes((0xEF, 0xBB, 0xBF))
    issues = []
    yml_n = txt_n = 0
    locd = os.path.join(root, "localisation")
    if os.path.isdir(locd):
        for dp, _dn, fs in os.walk(locd):
            for fn in fs:
                if not fn.lower().endswith(".yml"):
                    continue
                yml_n += 1
                fp = os.path.join(dp, fn)
                try:
                    with open(fp, "rb") as f:
                        head = f.read(3)
                except Exception:
                    continue
                if head != BOM3:
                    issues.append(("缺 BOM", os.path.relpath(fp, root)))
    for sub in ("common", "history", "events"):
        d0 = os.path.join(root, sub)
        if not os.path.isdir(d0):
            continue
        for dp, _dn, fs in os.walk(d0):
            for fn in fs:
                if not fn.lower().endswith(".txt"):
                    continue
                txt_n += 1
                fp = os.path.join(dp, fn)
                try:
                    with open(fp, "rb") as f:
                        head = f.read(3)
                except Exception:
                    continue
                if head == BOM3:
                    issues.append(("多余 BOM", os.path.relpath(fp, root)))
                if len(issues) >= limit * 3:
                    break
    return issues[:limit], yml_n, txt_n, len(issues)


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

    # v0.97 科技前置引用闭环
    try:
        _KW = {"focus", "OR", "AND", "NOT", "has_dlc", "has_global_flag", "has_country_flag",
               "has_tech", "if", "else", "limit", "tooltip", "custom_effect_tooltip",
               "has_start_date", "date", "original_tag", "tag"}
        _dangling = []
        for _tid, _t in TECHS.items():
            for _p in (_t.get("prereq") or []):
                if _p in _KW or _p in TECHS:
                    continue
                _dangling.append((_tid, _p))
        if _dangling:
            add("warn", "tech", "%d 处科技前置引用了不存在的科技" % len(_dangling),
                "例如 " + "、".join("%s → %s" % (a, b) for a, b in _dangling[:6]) +
                "；可能是科技改名或删掉后没清 prerequisites", "",
                {"type": "log", "id": ""})
    except Exception as e:
        print("科技前置检查失败:", e)

    # v0.96 编码规范（BOM）
    try:
        _bom, _yml_n, _txt_n, _bom_total = _bom_issues(ROOTS[0] if ROOTS else GAME)
        if _bom_total:
            miss = sum(1 for k, _ in _bom if k == "缺 BOM")
            extra = _bom_total - miss
            parts = []
            if miss:
                parts.append("%d 个 .yml 缺 BOM（游戏会读不到本地化）" % miss)
            if extra:
                parts.append("%d 个 .txt 带多余 BOM" % extra)
            add("warn", "bom", "编码规范问题：" + "；".join(parts),
                "抽查 %d 个 yml / %d 个 txt；示例：" % (_yml_n, _txt_n) +
                "、".join("%s %s" % (k, v) for k, v in _bom[:5]), "", {"type": "log", "id": ""})
    except Exception as e:
        print("BOM 检查失败:", e)

    # v0.86 铁路等级（静态，不必跑游戏）
    try:
        _over, _total = _rail_over_level(ROOTS[0] if ROOTS else GAME)
        if _over:
            add("warn", "rail", "铁路有 %d 条等级超过上限（共 %d 条）" % (_over, _total),
                "游戏日志会刷 Railway level > MAX_RAILWAY_LEVEL，把 level 降到 5 以内", "",
                {"type": "log", "id": ""})
    except Exception as e:
        print("铁路检查失败:", e)

    # v0.86 游戏日志
    try:
        _log = read_error_log()
        if _log.get("ok"):
            for it in _log.get("items", []):
                add(it["level"], "log", it["title"], it["detail"], {"type": "log", "id": ""})
    except Exception as e:
        print("error.log 读取失败:", e)

    # v0.66 全局 flag 配对
    try:
        sets, haves = _flag_usage()
    except Exception as e:
        sets, haves = {}, {}
        print("flag scan fail:", e)
    for f, where in list(haves.items())[:120]:
        if f not in sets:
            add("warn", "flag", "全局 flag %s 只被读取（%s），没有任何 set_global_flag" % (f, where), "",
                {"type": "tree", "id": ""})
    for f, where in list(sets.items())[:120]:
        if f not in haves:
            add("info", "flag", "全局 flag %s 只被设置（%s），目前没人读取" % (f, where), "",
                {"type": "tree", "id": ""})

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

# v0.69 AI 流式输出
def _ai_messages(system, prompt, context, history, max_turns=12):
    """把历史消息 + 当前提问拼成 messages 数组。

    history: [{"role": "user"/"assistant", "content": "..."}]
    只保留最近 max_turns 轮，避免上下文过长把模型窗口挤爆。"""
    msgs = [{"role": "system", "content": system}]
    hist = list(history or [])
    if len(hist) > max_turns * 2:
        hist = hist[-max_turns * 2:]
    for h in hist:
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content})
    cur = prompt if not context else (context + "\n\n---\n\n" + prompt)
    msgs.append({"role": "user", "content": cur})
    return msgs


def ai_chat_stream(cfg, prompt, context, emit, history=None):
    """逐块把模型输出交给 emit(chunk)。返回 (ok, 错误信息)。

    OpenAI 兼容 / Ollama / Anthropic / Gemini 都支持；解析失败时退回一次性返回。
    """
    provider = (cfg.get("provider") or "openai").lower()
    base = (cfg.get("base_url") or "").rstrip("/")
    key = cfg.get("api_key") or ""
    model = cfg.get("model") or ""
    system = cfg.get("system") or DEFAULT_AI["system"]
    msgs = _ai_messages(system, prompt, context, history)
    text = msgs[-1]["content"]
    if not base:
        return False, "请填写 Base URL"

    def _open(url, payload, headers):
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers=dict({"Content-Type": "application/json"}, **headers))
        return urllib.request.urlopen(req, timeout=180)

    try:
        if provider in ("openai", "deepseek", "ollama", "custom"):
            body = {"model": model, "temperature": 0.3, "stream": True,
                    "messages": msgs}
            with _open(base + "/chat/completions", body,
                       {"Authorization": "Bearer " + key} if key else {}) as r:
                for raw in r:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except Exception:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content") or ""
                    if piece:
                        emit(piece)
            return True, ""

        if provider == "anthropic":
            body = {"model": model, "max_tokens": 2000, "system": system, "stream": True,
                    "messages": [{"role": "user", "content": text}]}
            with _open(base + "/messages", body,
                       {"x-api-key": key, "anthropic-version": "2023-06-01"}) as r:
                for raw in r:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    try:
                        obj = json.loads(line[5:].strip())
                    except Exception:
                        continue
                    if obj.get("type") == "content_block_delta":
                        piece = (obj.get("delta") or {}).get("text") or ""
                        if piece:
                            emit(piece)
            return True, ""

        if provider == "gemini":
            url = base + "/models/" + model + ":streamGenerateContent?alt=sse&key=" + key
            body = {"contents": [{"parts": [{"text": system + "\n\n" + text}]}]}
            with _open(url, body, {}) as r:
                for raw in r:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    try:
                        obj = json.loads(line[5:].strip())
                    except Exception:
                        continue
                    cands = obj.get("candidates") or []
                    if not cands:
                        continue
                    parts = (cands[0].get("content") or {}).get("parts") or []
                    piece = "".join(p.get("text", "") for p in parts)
                    if piece:
                        emit(piece)
            return True, ""

        return False, "未知的提供商: " + provider
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            detail = ""
        return False, "HTTP %s: %s" % (e.code, detail)
    except Exception as e:
        return False, "请求失败: %s" % e


def ai_chat(cfg, prompt, context="", history=None):

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

    def _ai_stream(self, cfg, prompt, context):
        """SSE 流式输出：每个片段一行 data: {"d": "..."}，结束时 data: {"end": true}"""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(piece):
            self.wfile.write(("data: " + json.dumps({"d": piece}, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()

        try:
            ok, err = ai_chat_stream(cfg, prompt, context, emit)
        except Exception as e:
            ok, err = False, "流式中断: %s" % e
        try:
            self.wfile.write(("data: " + json.dumps({"end": True, "ok": ok, "msg": err},
                                                    ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()
        except Exception:
            pass
        self.close_connection = True

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
            self._send(state_detail(qs.get("id", [""])[0], bool(qs.get("full", [""])[0])))
        elif path_only == "/api/country":
            qs = parse_qs(urlparse(self.path).query)
            self._send(country_detail(qs.get("tag", [""])[0]))
        elif path_only == "/api/country_history":
            qs = parse_qs(urlparse(self.path).query)
            self._send(country_history_raw(qs.get("tag", [""])[0]))
        elif path_only == "/api/map_meta":
            qs3 = parse_qs(urlparse(self.path).query)
            self._send(map_meta((qs3.get("root", [""])[0] or None)))
        elif path_only == "/api/map_asset":
            qs2 = parse_qs(urlparse(self.path).query)
            name = (qs2.get("name", [""])[0] or "")
            p = map_asset(name, (qs2.get("root", [""])[0] or None))
            if not p:
                self._send({"ok": False, "msg": "没有这个图块"}, 404)
            else:
                data = io.open(p, "rb").read()
                self._send(data, 200, "image/png" if p.endswith(".png") else
                           ("application/json; charset=utf-8" if p.endswith(".json") else "application/octet-stream"))
        elif path_only == "/api/scripted":
            self._send(scripted_payload())
        elif path_only == "/api/log":
            _q = parse_qs(urlparse(self.path).query)
            self._send(read_error_log((_q.get("path", [""])[0] or None)))
        elif path_only == "/api/orphan_tags":
            self._send(orphan_tags(_map_pick(None)))
        elif path_only == "/api/state_refine_preview":
            _q = parse_qs(urlparse(self.path).query)
            self._send(state_refine_preview(_q.get("sid", ["0"])[0],
                                            _q.get("k", ["2"])[0],
                                            _q.get("root", [None])[0]))
        elif path_only == "/api/equipment_list":
            _q = parse_qs(urlparse(self.path).query)
            self._send(equipment_list(_map_pick(None), _q.get("q", [""])[0]))
        elif path_only == "/api/equipment_detail":
            _q = parse_qs(urlparse(self.path).query)
            self._send(equipment_detail(_q.get("id", [""])[0], _q.get("root", [None])[0]))
        elif path_only == "/api/adjacencies":
            self._send(adjacencies_list(_map_pick(None)))
        elif path_only == "/api/strategic_regions":
            self._send(strategic_regions_list(_map_pick(None)))
        elif path_only == "/api/terrain_by_type":
            _q = parse_qs(urlparse(self.path).query)
            self._send(prov_terrain_by_type(_q.get("from", [""])[0],
                                            _q.get("to", [""])[0],
                                            _q.get("root", [None])[0]))
        elif path_only == "/api/terrain_types":
            self._send(terrain_types(_map_pick(None)))
        elif path_only == "/api/supply_areas":
            self._send(supply_areas(_map_pick(None)))
        elif path_only == "/api/railways":
            _q = parse_qs(urlparse(self.path).query)
            self._send(railways_list(_q.get("root", [None])[0]))
        elif path_only == "/api/gfx_missing":
            _q = parse_qs(urlparse(self.path).query)
            self._send(gfx_missing(_q.get("root", [None])[0],
                                   int(_q.get("limit", ["600"])[0])))
        elif path_only == "/api/loc_missing":
            _q = parse_qs(urlparse(self.path).query)
            self._send(loc_missing(_q.get("root", [None])[0],
                                   int(_q.get("limit", ["800"])[0])))
        elif path_only == "/api/refine_preview":
            _q = parse_qs(urlparse(self.path).query)
            self._send(refine_preview(_q.get("pid", ["0"])[0], _q.get("k", ["2"])[0],
                                      _q.get("root", [None])[0]))
        elif path_only == "/api/map_repair_cross":
            _q = parse_qs(urlparse(self.path).query)
            _ap = _q.get("apply", ["0"])[0] in ("1", "true", "yes")
            self._send(map_repair_cross(_q.get("root", [None])[0], _ap))
        elif path_only == "/api/map_repair":
            _q = parse_qs(urlparse(self.path).query)
            _act = _q.get("act", ["preview"])[0]
            if _act == "ghost":
                self._send(map_repair_ghost(_q.get("root", [None])[0]))
            else:
                self._send(map_repair_preview(_q.get("root", [None])[0]))
        elif path_only == "/api/output":
            _q = parse_qs(urlparse(self.path).query)
            _act = _q.get("act", [""])[0]
            if _act == "toggle":
                _on = _q.get("on", [""])[0]
                self._send(output_toggle(None if _on == "" else (_on in ("1", "true", "yes"))))
            elif _act == "clear":
                self._send(output_clear())
            else:
                self._send(output_state())
        elif path_only == "/api/playset":
            self._send(playset_get())
        elif path_only == "/api/map_analysis":
            _q = parse_qs(urlparse(self.path).query)
            try:
                _lim = int(_q.get("limit", ["60"])[0])
                _minpx = int(_q.get("min_px", ["800"])[0])
            except Exception:
                _lim, _minpx = 60, 800
            _ol = _q.get("only_land", ["1"])[0] not in ("0", "false", "")
            self._send(map_analysis(_q.get("root", [None])[0], _lim, _minpx, _ol))
        elif path_only == "/api/update":
            _f = parse_qs(urlparse(self.path).query).get("force", [""])[0]
            self._send(check_update(force=bool(_f)))
        elif path_only == "/api/app_info":
            self._send({"ok": True, **app_info()})
        elif path_only == "/api/lint":
            self._send(lint_project())
        elif path_only == "/api/missing_loc":
            self._send({"items": missing_loc()})
        elif path_only == "/api/file_excerpt":
            _q = parse_qs(urlparse(self.path).query)
            self._send(file_excerpt(_q.get("file", [""])[0], _q.get("line", ["1"])[0],
                                    _q.get("root", [None])[0]))
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
        elif path_only == "/api/event_space_create":
            _q = parse_qs(urlparse(self.path).query)
            self._send(event_space_create(_q.get("ns", [""])[0], _q.get("root", [None])[0]))
        elif path_only == "/api/event_space_delete":
            _q = parse_qs(urlparse(self.path).query)
            self._send(event_space_delete(_q.get("ns", [""])[0], _q.get("root", [None])[0]))
        elif path_only == "/api/event_detail":
            _q = parse_qs(urlparse(self.path).query)
            self._send(event_detail(_q.get("id", [""])[0], _q.get("root", [None])[0]))
        elif path_only == "/api/event_spaces":
            self._send(event_graph("", None))
        elif path_only == "/api/event_graph":
            _q = parse_qs(urlparse(self.path).query)
            self._send(event_graph(_q.get("ns", [""])[0], _q.get("root", [None])[0]))
        elif path_only == "/api/focus_trees":
            self._send(focus_tree_list())
        elif path_only == "/api/focus_graph":
            _q = parse_qs(urlparse(self.path).query)
            self._send(focus_tree_graph(_q.get("tree", [""])[0]))
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
        elif self.path == "/api/state_province":
            self._send(state_province_edit(body.get("pid"), body.get("target")))
        elif self.path == "/api/update_apply":
            act = body.get("act") or "prepare"
            if act == "download":
                self._send(update_download(body.get("url") or None, body.get("size") or 0))
            elif act == "launch":
                self._send(update_apply(launch=True))
            else:
                self._send(update_apply(launch=False))
        elif self.path == "/api/map_paint":
            act = body.get("act") or ""
            if act == "begin":
                _bp = body.get("bmp") or MAP_EDIT.get("file") or ""
                if not _bp:
                    _root = _map_pick(body.get("root") or None)
                    _layers = mod_layers(_root)
                    _top = _layers[-1] if _layers else ""
                    _bp = os.path.join(_top, "map", "provinces.bmp")
                    # 写操作只落链顶；链顶没 bmp 就不能涂（避免写到父 mod）
                    if not os.path.exists(_bp):
                        self._send({"ok": False,
                                    "msg": "链顶 mod 没有自己的 provinces.bmp（地图来自父 mod），"
                                           "不能直接涂色；请对提供地图的那个 mod 操作"})
                        return
                if is_under_game(_bp):
                    self._send({"ok": False, "msg": "原版目录只读，不能涂色"})
                    return
                r = {"ok": map_edit_begin(_bp), "bmp": _bp}
            elif act == "dab":
                _rgb = body.get("rgb")
                if not _rgb and body.get("pid") is not None:
                    _ensure_prov_rgb(body.get("root") or None)
                    _rgb = PROV_RGB.get(int(body.get("pid")))
                    if not _rgb:
                        self._send({"ok": False, "msg": "省 %s 没有颜色定义" % body.get("pid")})
                        return
                nx = map_edit_dab(MAP_EDIT.get("file") or body.get("bmp"), int(body.get("x", 0)),
                                  int(body.get("y", 0)), int(body.get("r", 2)),
                                  tuple(_rgb or (255, 0, 255)))
                r = {"ok": True, "pixels": nx}
            elif act == "commit":
                r = map_edit_commit()
            elif act == "undo":
                r = map_edit_undo()
            elif act == "redo":
                r = map_edit_redo()
            else:
                r = map_edit_state()
            self._send(r)
        elif self.path == "/api/state_create":
            self._send(state_create(body.get("provinces") or [], body.get("root") or None,
                                    body.get("name"), body.get("category"),
                                    body.get("manpower") or 100000, body.get("id")))
        elif self.path == "/api/map_merge":
            act = (body.get("act") or "preview")
            _src = int(body.get("src", 0))
            _dst = int(body.get("dst", 0))
            _rt = body.get("root") or None
            if act == "preview":
                self._send(map_merge_preview(_src, _dst, _rt))
            elif act == "neighbors":
                self._send(map_prov_neighbors(_src, _rt))
            else:
                self._send(map_merge_apply(_src, _dst, _rt))
        elif self.path == "/api/map_integrity":
            self._send(map_integrity(body.get("root") or None))
        elif self.path == "/api/map_cache_clear":
            self._send(map_cache_clear())
        elif self.path == "/api/map_build":
            self._send(map_build(bool(body.get("force")), (body.get("root") or None)))
        elif self.path == "/api/country_variant":
            act = (body.get("action") or "add").lower()
            if act == "del":
                self._send(country_variant_del(body.get("tag", ""), body.get("name", "")))
            else:
                self._send(country_variant_add(body.get("tag", ""), body))
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
        elif self.path == "/api/state_refine":
            self._send(state_refine_apply(body.get("sid"), body.get("k"),
                                          body.get("root")))
        elif self.path == "/api/equipment_edit":
            self._send(equipment_edit(body.get("id"), body.get("props"),
                                      body.get("root")))
        elif self.path == "/api/equipment_delete":
            self._send(equipment_delete(body.get("id"), body.get("root")))
        elif self.path == "/api/supply_save":
            self._send(supply_area_save(body.get("id"), body.get("value"),
                                        body.get("states"), body.get("name"),
                                        body.get("root")))
        elif self.path == "/api/supply_delete":
            self._send(supply_area_delete(body.get("id"), body.get("root")))
        elif self.path == "/api/adj_edit":
            self._send(adjacency_edit(body.get("line"), body.get("type"),
                                      body.get("root")))
        elif self.path == "/api/adj_delete":
            self._send(adjacency_delete(body.get("line"), body.get("root")))
        elif self.path == "/api/adj_add":
            self._send(adjacency_add(body.get("from"), body.get("to"),
                                     body.get("type"), body.get("through"),
                                     body.get("root")))
        elif self.path == "/api/sr_create":
            self._send(strategic_region_create(body.get("root"), body.get("id"),
                                               body.get("name"), body.get("provinces")))
        elif self.path == "/api/sr_set_provinces":
            self._send(strategic_region_set_provinces(body.get("id"),
                                                      body.get("provinces"),
                                                      body.get("root")))
        elif self.path == "/api/sr_delete":
            self._send(strategic_region_delete(body.get("id"), body.get("root")))
        elif self.path == "/api/terrain_batch":
            self._send(prov_terrain_batch(body.get("pids"), body.get("terrain"),
                                          body.get("root")))
        elif self.path == "/api/terrain_by_type":
            self._send(prov_terrain_by_type(body.get("from"), body.get("to"),
                                            body.get("root")))
        elif self.path == "/api/terrain_paint":
            self._send(terrain_paint(body.get("points"), body.get("terrain"),
                                     body.get("brush"), body.get("root")))
        elif self.path == "/api/terrain_set":
            self._send(prov_terrain_set(body.get("pid"), body.get("terrain"),
                                        body.get("root")))
        elif self.path == "/api/railway_edit":
            self._send(railway_edit(body.get("index"), body.get("level"),
                                    body.get("provs"), body.get("root")))
        elif self.path == "/api/railway_delete":
            self._send(railway_delete(body.get("index"), body.get("root")))
        elif self.path == "/api/railway_level":
            self._send(railway_set_level(body.get("index"), body.get("level"),
                                         body.get("root")))
        elif self.path == "/api/loc_generate":
            self._send(loc_generate(body.get("root"), body.get("keys"),
                                    body.get("lang") or "simp_chinese",
                                    bool(body.get("dry"))))
        elif self.path == "/api/event_edit":
            self._send(event_edit(body.get("id"), body.get("title"), body.get("desc"),
                                  body.get("options"), body.get("root"),
                                  body.get("titleText"), body.get("descText")))
        elif self.path == "/api/refine_apply":
            self._send(refine_apply(body.get("pid") or 0, body.get("k") or 2,
                                    body.get("root"), body.get("base_pid")))
        elif self.path == "/api/output_apply":
            self._send(output_apply_back())
        elif self.path == "/api/playset_save":
            self._send(playset_save(body.get("paths") or []))
        elif self.path == "/api/playset_pick":
            ds = detect_mods()
            self._send({"ok": bool(ds), "path": ds[0] if ds else "",
                        "msg": "" if ds else "没有选择目录"})
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
            _cfg = load_ai()
            if body.get("stream"):
                self._ai_stream(_cfg, body.get("prompt") or "", body.get("context") or "",
                                body.get("history") or [])
            else:
                ok, msg = ai_chat(_cfg, body.get("prompt") or "", body.get("context") or "",
                                  body.get("history") or [])
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
    roots = args.mod or playset_load_saved()   # 没传 --mod 时用上次保存的播放集
    load_game_loc()
    total = 0
    for r in roots:
        r = os.path.abspath(r)
        if r not in ROOTS:
            ROOTS.append(r)
            total += load_mod(r)
    refresh_start_date(ROOTS)
    reload_data()
    link_countries()
    print("开局日期:", START_DATE_TEXT, "| STATES:", len(STATES))
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
