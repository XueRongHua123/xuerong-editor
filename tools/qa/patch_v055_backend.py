# -*- coding: utf-8 -*-
"""把国家/州解析与项目体检注入 focus_editor.py（v0.55）。

用法：python work/qa/patch_v055_backend.py
幂等：检测到已注入的标记就直接退出。
"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor.py')
MARK = "# ---------------- 国家 / 州 / 项目体检（v0.55） ----------------"

BLOCK = r'''# ---------------- 国家 / 州 / 项目体检（v0.55） ----------------
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
    return strip_comments(io.open(path, encoding="utf-8", errors="replace").read())


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
            p = os.path.join(base, rel) if rel else ""
            if p and os.path.exists(p):
                text = _read_text(p)
                c["has_def"] = True
                c["def_path"] = os.path.join(base, rel)
                cm = re.search(r'(?m)^\s*color\s*=\s*(?:\{)?\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)', text)
                if cm:
                    c["color"] = [float(cm.group(1)), float(cm.group(2)), float(cm.group(3))]
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
            elif not _prefer(cur, root):
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
    """history/states：id / 名称 / 人力 / 类别 / owner / cores / 省份数"""
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
            hist = ""
            hm = re.search(r'history\s*=\s*\{', body)
            if hm:
                hb = body.find('{', hm.start())
                he = brace_match(body, hb)
                hist = body[hb + 1:he - 1]
            owner = _first(body, r'(?m)^\s*owner\s*=\s*([A-Z0-9]{2,4})')
            if not owner:
                owner = _first(hist, r'(?m)^\s*owner\s*=\s*([A-Z0-9]{2,4})')
            cores = re.findall(r'(?m)^\s*add_core_of\s*=\s*([A-Z0-9]{2,4})', hist or body)
            pm = re.search(r'provinces\s*=\s*\{([^}]*)\}', body)
            STATES[sid] = {
                "id": sid, "file": rel, "root": root, "source": name,
                "name": _first(body, r'(?m)^\s*name\s*=\s*"?([A-Za-z0-9_]+)"?'),
                "manpower": _first(body, r'(?m)^\s*manpower\s*=\s*(\d+)'),
                "category": _first(body, r'(?m)^\s*state_category\s*=\s*(\w+)'),
                "owner": owner, "cores": sorted(set(cores)),
                "provinces": len(re.findall(r'\d+', pm.group(1))) if pm else 0,
                "has_history": bool(hist),
            }
            n += 1
    return n


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
    if not LOC.get(tag):
        add("warn", "缺少本地化键 %s（国家名会显示成 tag）" % tag)
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
            "name": LOC.get(tag, c.get("history_display") or tag),
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
        "name": LOC.get(tag, c.get("history_display") or tag),
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
            add("warn", "tree", "国策树 %s 的 country 块里解析不出 tag" % tid, raw[:120],
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

'''

def main():
    s = io.open(P, encoding='utf-8').read()
    if MARK in s:
        print('已注入，跳过')
        return 0
    anchor = "def load_events(root):"
    assert s.count(anchor) == 1
    s = s.replace(anchor, BLOCK + anchor, 1)

    # load_mod: 国家/州也要跟着加载，并放宽"必须有 national_focus"的限制
    old = '''    nf = os.path.join(root, "common", "national_focus")
    if not os.path.isdir(nf):
        return 0
    count = 0
    for fn in sorted(f for f in os.listdir(nf) if f.endswith(".txt")):'''
    new = '''    nf = os.path.join(root, "common", "national_focus")
    count = 0
    for fn in (sorted(f for f in os.listdir(nf) if f.endswith(".txt")) if os.path.isdir(nf) else []):'''
    assert s.count(old) == 1, 'load_mod 结构与预期不符'
    s = s.replace(old, new, 1)

    old2 = '''    load_techs(root)
    load_events(root)
    return count'''
    new2 = '''    load_techs(root)
    load_events(root)
    load_countries(root)
    load_states(root)
    return count'''
    assert s.count(old2) == 1
    s = s.replace(old2, new2, 1)

    # reload_data 清空 + 末尾重建关联
    old3 = '''    MODULES = {}
    ORGS = {}
    total = 0
    for r in ROOTS:
        total += load_mod(r)
    return total'''
    new3 = '''    MODULES = {}
    ORGS = {}
    global COUNTRIES, STATES
    COUNTRIES = {}
    STATES = {}
    total = 0
    for r in ROOTS:
        total += load_mod(r)
    link_countries()
    return total'''
    assert s.count(old3) == 1
    s = s.replace(old3, new3, 1)

    # 路由
    old4 = '''        elif path_only == "/api/missing_loc":'''
    new4 = '''        elif path_only == "/api/countries":
            self._send(countries_payload())
        elif path_only == "/api/country":
            qs = parse_qs(urlparse(self.path).query)
            self._send(country_detail(qs.get("tag", [""])[0]))
        elif path_only == "/api/lint":
            self._send(lint_project())
        elif path_only == "/api/missing_loc":'''
    assert s.count(old4) == 1
    s = s.replace(old4, new4, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(s)
    print('注入完成：', P)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
