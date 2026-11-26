# -*- coding: utf-8 -*-
"""国策树（focus）域（P2-rest 第 3 域，从 focus_editor.py 迁入）。

读：load_focus（从 load_mod 体内原样搬出的 87 行树解析）+ parse_focus_like / parse_simple_fx
写：save_focus / add_focus / delete_focus（改节点、加节点、删节点，写完 reload_data）
图：focus_tree_graph / focus_tree_list / resolve_positions（relative_position_id 展开成绝对坐标）
已完成国策：load_completed_focuses / focus_complete_add / focus_complete_delete

依赖边界：
  · TREES / TREE_ORDER / SHARED_FOCUSES / LOC / CHANGED / ROOTS → xuerong.state 访问器
  · 叠加链 _layer_dirs → core.paths；脚本改写工具 → core.text
  · _politics_write 在 model/country.py（它本质是「拿到可写的国家历史文件」，politics 域也用）
  · 写前备份 → model.history；选层 _pick → core.paths
  · 两个横切口由门面 bind()：reload_data（35 处调用，不可能搬）、lp（加载进度上报）
"""
import io
import os
import re

import xuerong.core.paths
from xuerong import state
from xuerong.core.paths import _layer_dirs, effective_layer_files
from xuerong.core.text import (_atomic_write, _bom_for, _first, _strip_keep_len, brace_match,
                               braces_balanced, find_blocks, remove_block, set_raw_block,
                               set_scalar, strip_comments, top_items)
from xuerong.model.country import (_country_hist_file, _country_hist_write_base, _politics_write)
from xuerong.model.history import backup, snapshot

# ---------------------------------------------------------------- 门面回注
_INJ = {}


def bind(**kw):
    _INJ.update(kw)


def _reload():
    f = _INJ.get("reload_data")
    if f:
        f()


def _lp(*a, **k):
    f = _INJ.get("lp")
    if f:
        f(*a, **k)



# ---------------------------------------------------------------- 编码（F7）
# HOI4 生态里大量国策文件是 UTF-8 BOM（Paradox 自己的工具就这样存）。
# 用 "utf-8" 解码时 BOM 会变成文本开头的 "\ufeff"，而这里所有解析都用
# r'(?m)^\s*focus_tree' 这类行首锚点——带 BOM 的第一行永远匹配不上，
# 于是整个文件里的树静默消失，界面上看不出任何异常。
def _read_focus_text(path):
    """读国策/国家历史文件，返回 (文本, 原本是否带 BOM)。换行符原样保留。"""
    with io.open(path, "rb") as f:
        raw = f.read()
    bom = raw[:3] == b"\xef\xbb\xbf"
    return raw.decode("utf-8-sig" if bom else "utf-8", "replace"), bom


def _write_focus_text(path, text, bom=False):
    """写回：原文带 BOM 就保留，没有就不擅自加。"""
    _atomic_write(path, (b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))



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



def load_focus(root):
    """解析 common/national_focus 下的 shared_focus / focus_tree，填 TREES / TREE_ORDER / SHARED_FOCUSES。

    从 load_mod 体内原样搬出来（P2-rest 第 3 域）。两个修过的地方**不要改**：

      · `_lay = os.path.dirname(os.path.dirname(os.path.abspath(nf)))`
        树要记住自己属于哪一层，不能直接用 root——多层叠加时同名文件来自不同层，
        记错层会导致保存写进错误的那层、找到的 id 也不对。
      · `_nf_pairs.reverse()`
        `_layer_dirs` 是「越靠前越优先」，但同名树是后赋值覆盖先赋值，
        所以要底层先读、顶层后读，顶层才盖得住底下那份。

    返回建了多少棵树。进度上报走 bind 进来的 _lp。
    """
    root = os.path.abspath(root)
    name = os.path.basename(root.rstrip("\\/")) or root
    count = 0
    _nf_pairs = []
    _lp("扫描文件", os.path.basename(root), 2)
    _nf_pairs = [
        (os.path.basename(_b.rstrip("\\/")) or _b, _d, _f)
        for _b, _d, _f in effective_layer_files("common/national_focus", root)
    ]
    _n_all = max(1, len(_nf_pairs))
    for _i, (_layer_name, nf, fn) in enumerate(_nf_pairs):
        if _i % 4 == 0:
            _lp("解析国策树", "%d / %d 个文件" % (_i + 1, _n_all), 4 + int(_i * 54.0 / _n_all))
        # 文件真正属于哪一层：nf 是 <层>/common/national_focus，去掉两级就是层根。
        # 不能直接用函数参数 root——多层叠加时同名的文件会从不同层读到，
        # 每棵树必须记住自己那一层，否则保存时会写进错的那层（找到的 id 也不对）。
        try:
            _lay = os.path.dirname(os.path.dirname(os.path.abspath(nf)))
        except Exception:
            _lay = root
        text = strip_comments(_read_focus_text(os.path.join(nf, fn))[0])
        rel = os.path.join("common", "national_focus", fn)
        for start, end, body in find_blocks(text, "shared_focus"):
            node = parse_focus_like(body, rel, _layer_name)
            if node:
                node["shared"] = True
                node["root"] = _lay
                _sfs = state.shared_focuses()
                _sf_idx = next((idx for idx, x in enumerate(_sfs) if x.get("id") == node.get("id")), -1)
                if _sf_idx >= 0:
                    _sfs[_sf_idx] = node
                else:
                    _sfs.append(node)
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
                    node = parse_focus_like(v, os.path.join("common","national_focus",fn), _layer_name)
                    if node:
                        node["root"] = _lay
                        focuses.append(node)
            if tid:
                if tid in state.trees():
                    state.tree_order().remove(tid)
                state.trees()[tid] = {"id": tid, "file": os.path.join("common","national_focus",fn), "source": _layer_name, "root": _lay,
                              "focuses": focuses, "shared": shared_refs,
                              "default": t_default, "country_raw": t_country}
                state.tree_order().append(tid)
                count += 1
    return count



def resolve_positions(tree):
    by = {f["id"]: f for f in tree["focuses"]}
    memo = {}
    def ap(fid, seen=()):
        if fid in memo:
            return memo[fid]
        f = by.get(fid)
        if not f:
            return (0.0, 0.0)
        fx = float(f["x"]) if f.get("x") is not None else 0.0
        fy = float(f["y"]) if f.get("y") is not None else 0.0
        if f.get("rel") and f["rel"] in by and f["rel"] not in seen:
            bx, byy = ap(f["rel"], seen + (fid,))
            r = (bx + fx, byy + fy)
        else:
            r = (fx, fy)
        memo[fid] = r
        return r
    for f in tree["focuses"]:
        f["rel_x"], f["rel_y"] = f["x"], f["y"]
        ax, ay = ap(f["id"])
        f["ax"], f["ay"] = ax, ay



# v0.59 国策引用体检
def _focus_refs():
    """从 national_focus 原文里收集 add_ideas / has_idea / country_event 引用

    走叠加链（原版 / 父 mod 的国策也算），只扫 root 那一层时加载纯 submod
    会把引用全漏掉（雪绒拓展自己没有 national_focus，输出是 0 条）。

    两级去重：
    - seen_dirs：不同 root 的链可能共享同一层（都含原版），同一目录不能扫两遍；
    - seen_files：同名的 national_focus 文件父层那份被子层整体覆盖、根本不进游戏，
      再扫一遍只会把死数据当成有效引用报出去（本机实测 881 -> 429 条）。
    _layer_dirs 是子 mod 在前，所以先遇到的那份就是生效的那份。"""
    ideas, events = [], []
    seen_dirs = set()
    seen_files = set()
    for root in state.roots():
        for base, d in _layer_dirs("common/national_focus", root):
            ab = os.path.abspath(d)
            if ab in seen_dirs:
                continue
            seen_dirs.add(ab)
            name = os.path.basename(base.rstrip("\\/")) or base
            for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
                rel = os.path.join("common", "national_focus", fn)
                if rel in seen_files:
                    continue
                seen_files.add(rel)
                try:
                    text = strip_comments(_read_focus_text(os.path.join(d, fn))[0])
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
                    for tid, t in state.trees().items():
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



def load_completed_focuses(root=None, tag=""):
    """读某国 history 里的 complete_national_focus / mark_focus_tree_completed。

    两种写法都认：
        complete_national_focus = { focus = xxx }
        complete_national_focus = xxx
        mark_focus_tree_completed = yes
    """
    root = xuerong.core.paths._pick(root)
    tag = (tag or "").upper()
    if not tag:
        return {"ok": False, "msg": "没给 tag", "items": []}
    p, rel = _country_hist_file(root, tag)
    if not p:
        return {"ok": False, "msg": "找不到 %s 的国家历史文件" % tag, "items": []}
    try:
        raw, _bom = _read_focus_text(p)
    except Exception as e:
        return {"ok": False, "msg": "读取失败：%s" % e, "items": []}
    text = _strip_keep_len(raw)
    items = []
    for a, b, body in find_blocks(text, "complete_national_focus"):
        f = _first(body, r'(?m)^\s*focus\s*=\s*([A-Za-z0-9_]+)')
        if f:
            items.append({"focus": f, "form": "block"})
    # 简写形式 complete_national_focus = xxx（不是 {）
    for m in re.finditer(r'(?m)^[ 	]*complete_national_focus[ 	]*=[ 	]*([A-Za-z0-9_]+)[ 	]*(?:#.*)?$', text):
        items.append({"focus": m.group(1), "form": "inline"})
    tree_done = bool(re.search(r'(?m)^[ 	]*mark_focus_tree_completed[ 	]*=[ 	]*yes', text))
    return {"ok": True, "tag": tag, "file": os.path.basename(p),
            "items": items, "count": len(items), "tree_completed": tree_done,
            "msg": "%s：%d 个已完成国策%s" % (
                tag, len(items), "，整树标记完成" if tree_done else "")}



def focus_complete_add(root, tag, focus_id):
    """给某国加一个「开局已完成」的国策。"""
    root = xuerong.core.paths._pick(root)
    tag = (tag or "").upper()
    focus_id = (focus_id or "").strip()
    if not tag or not focus_id:
        return {"ok": False, "msg": "tag 和国策 id 都要给"}
    if not re.match(r'^[A-Za-z][A-Za-z0-9_]*$', focus_id):
        return {"ok": False, "msg": "国策 id 格式不对"}
    cur = load_completed_focuses(root, tag)
    if not cur.get("ok"):
        return {"ok": False, "msg": cur.get("msg")}
    if any(x["focus"] == focus_id for x in cur["items"]):
        return {"ok": True, "msg": "已经有 %s 了" % focus_id}
    known = focus_id in (state.trees().get("") or {})
    found = any(focus_id in {f.get("id") for f in (t.get("focuses") or [])}
                for t in (state.trees() or {}).values())
    dst, rel, err = _politics_write(root, tag)
    if not dst:
        return {"ok": False, "msg": err}
    raw, _bom = _read_focus_text(dst)
    block = "\n\tcomplete_national_focus = {\n\t\tfocus = %s\n\t}\n" % focus_id
    text = _strip_keep_len(raw)
    hi = text.find("history = {")
    if hi >= 0:
        br = text.find("{", hi)
        pos = br + 1
        new_text = raw[:pos] + block + raw[pos:]
    else:
        new_text = raw.rstrip() + "\nhistory = {" + block + "}\n"
    snapshot(dst)
    _write_focus_text(dst, new_text, _bom)
    tip = "" if found else "（注意：现有国策树里没找到这个 id）"
    return {"ok": True, "msg": "%s 已标记完成 %s%s" % (tag, focus_id, tip)}



def focus_complete_delete(root, tag, index):
    """删掉第 index 个已完成国策。"""
    root = xuerong.core.paths._pick(root)
    tag = (tag or "").upper()
    try:
        index = int(index)
    except Exception:
        return {"ok": False, "msg": "index 不合法"}
    cur = load_completed_focuses(root, tag)
    if not cur.get("ok"):
        return {"ok": False, "msg": cur.get("msg")}
    if index < 0 or index >= len(cur["items"]):
        return {"ok": False, "msg": "没有第 %d 个" % (index + 1)}
    fid = cur["items"][index]["focus"]
    dst, rel, err = _politics_write(root, tag)
    if not dst:
        return {"ok": False, "msg": err}
    raw, _bom = _read_focus_text(dst)
    text = _strip_keep_len(raw)
    blocks = list(find_blocks(text, "complete_national_focus"))
    # 先在块式里找
    for bi, (a, b, body) in enumerate(blocks):
        f = _first(body, r'(?m)^\s*focus\s*=\s*([A-Za-z0-9_]+)')
        if f != fid:
            continue
        # F8：回退到 complete_national_focus 那一行的行首，整块连键名一起删。
        # 原来只退到 "{" 前面，删完会剩下一行悬空的 "complete_national_focus ="，游戏直接报错。
        st = raw.rfind("\n", 0, a) + 1
        en = b
        while en < len(raw) and raw[en] in "\r\n":
            en += 1
        snapshot(dst)
        _write_focus_text(dst, raw[:st] + raw[en:], _bom)
        return {"ok": True, "msg": "已删除 %s" % fid}
    # 再找简写形式
    pat = re.compile(r'(?m)^[ \t]*complete_national_focus[ \t]*=[ \t]*' + re.escape(fid) + r'[ \t]*(?:#.*)?\r?\n?')
    new_text = pat.sub('', raw)
    if new_text != raw:
        snapshot(dst)
        _write_focus_text(dst, new_text, _bom)
        return {"ok": True, "msg": "已删除 %s" % fid}
    return {"ok": False, "msg": "没定位到 %s" % fid}



# ref: HOI4 Mod Utilities "Focus tree preview"
def focus_tree_graph(tid):
    """返回一棵国策树的节点与连线（只读，供预览渲染）"""
    tid = (tid or "").strip()
    t = state.trees().get(tid)
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
        # 优先用 resolve_positions() 算好的绝对坐标（relative_position_id 链已展开）；
        # 直接取 x/y 拿到的是相对偏移，预览会因此把节点挤成一条线。
        try:
            _ax = f.get("ax")
            x = round(float(_ax if _ax is not None else (f.get("x") or 0)), 2)
        except Exception:
            x = 0
        try:
            _ay = f.get("ay")
            y = round(float(_ay if _ay is not None else (f.get("y") or 0)), 2)
        except Exception:
            y = 0
        node = {
            "id": fid, "x": x, "y": y,
            "icon": f.get("icon") or "",
            "cost": f.get("cost") or "",
            "name": state.loc().get(fid, ""),
            "desc": state.loc().get(fid + "_desc", ""),
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
    for tid in state.tree_order():
        t = state.trees().get(tid) or {}
        out.append({"id": tid, "count": len(t.get("focuses") or []),
                    "file": os.path.basename(t.get("file") or "")})
    return {"ok": True, "trees": out, "count": len(out)}



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



def save_focus(root, rel, fid, fields):
    # v1.24.1：参数缺失时原来会在 os.path.join 里抛 TypeError，
    # 一路冒到 socketserver，前端只看到「连接被断」。这里先拦住。
    if not root or not rel:
        return False, "参数不完整：缺少 root 或 file"
    if not fid:
        return False, "参数不完整：缺少节点 id"
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        return False, "找不到文件：%s" % rel
    raw, _bom = _read_focus_text(path)
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
        for m in re.finditer(r'(?m)^\s*(?:focus|shared_focus)\s*=\s*\{', newtext):
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
    _write_focus_text(path, newtext, _bom)
    state.changed()[path] = rel
    _reload()
    return True, "已保存"



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
    if not root or not rel:
        return False, "参数不完整：缺少 root 或 file"
    if not fid:
        return False, "参数不完整：缺少节点 id"
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        return False, "找不到文件：%s" % rel
    text, _bom = _read_focus_text(path)
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
    _write_focus_text(path, newtext, _bom)
    state.changed()[path] = rel
    _reload()
    return True, "已新建 " + fid



def delete_focus(root, rel, fid):
    if not root or not rel:
        return False, "参数不完整：缺少 root 或 file"
    if not fid:
        return False, "参数不完整：缺少节点 id"
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        return False, "找不到文件：%s" % rel
    text, _bom = _read_focus_text(path)
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
    _write_focus_text(path, newtext, _bom)
    state.changed()[path] = rel
    _reload()
    return True, "已删除 " + fid

