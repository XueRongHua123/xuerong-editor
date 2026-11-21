# -*- coding: utf-8 -*-
"""事件域（P0-3 D5 从 focus_editor.py 迁入）。

事件图（国家/省份事件 + add_namespace）与逐个事件的读写。
`_EVENT_GRAPH_CACHE` 跟着本模块走——它只被这几个函数用（含 space_create/delete 里的
`.clear()`），搬出去会变成两份缓存。

依赖边界：
  · EVENTS / LOC / CHANGED → xuerong.state
  · 文本改写 → core.text；叠加链 → core.paths
  · 本地化写 → model.loc（save_loc / _loc_write_pairs）；快照 → model.history
  · 唯一钩子：reload_data
"""
import io
import os
import re

from xuerong import state
from xuerong.core import paths
from xuerong.core.paths import (_chain_layers, effective_layer_files, is_readonly_mod,
                                is_under_game, unique_editor_filename)
from xuerong.core.text import (_atomic_write, _bom_for, brace_match, braces_balanced,
                               set_raw_block, set_scalar, strip_comments, top_items)
from xuerong.model.history import snapshot
from xuerong.model.loc import save_loc, _loc_write_pairs

_RELOAD = None


def bind(reload_data):
    global _RELOAD
    _RELOAD = reload_data


def _reload():
    if _RELOAD:
        _RELOAD()


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
    root = paths._pick(root)
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
                      "name": state.loc().get(eid + ".t", "") or state.loc().get(eid + ".title", ""),
                      "text": "#" + str(len(nodes) + 1)})
        for tid, where in _event_fire_targets(ev["body"]):
            edges.append({"from": eid, "to": tid, "where": where,
                          "external": tid not in ids})
    # 外部引用也画成节点（灰色），方便看出跳到别处
    ext = sorted({e["to"] for e in edges if e["external"]})
    for tid in ext:
        nodes.append({"id": tid, "kind": "external", "file": "",
                      "name": state.loc().get(tid + ".t", ""), "text": ""})
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
    root = paths._pick(root)
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
    _atomic_write(fn, _bom_for(fn) + body.encode("utf-8"))
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
        _atomic_write(loc_fn, b"\xef\xbb\xbf" + (chr(10).join(lines) + chr(10)).encode("utf-8"))
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
    root = paths._pick(root)
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
                _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))
                touched.append("%s（删 %d 个块）" % (os.path.relpath(p, root), len(spans)))
            removed += max(1, len(spans))     # 只剩 add_namespace 声明时也算删过
    if not removed:
        return {"ok": False, "msg": "没有找到 %s.* 的事件" % ns}
    _EVENT_GRAPH_CACHE.clear()
    _reload()
    return {"ok": True, "ns": ns, "removed": removed, "files": touched,
            "msg": "已删除命名空间 %s 的 %d 个事件" % (ns, removed)}



def event_detail(eid, root=None):
    """读一个事件的 title / desc / 各 option 的名称与触发目标，供就地编辑"""
    eid = (eid or "").strip()
    root = paths._pick(root)
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
                        "titleText": state.loc().get(tit.group(1), "") if tit else "",
                        "descText": state.loc().get(dsc.group(1), "") if dsc else "",
                        "options": opts}
    return {"ok": False, "msg": "找不到事件 %s（可能不在本 mod 里）" % eid}



def event_edit(eid, title=None, desc=None, options=None, root=None,
               title_text=None, desc_text=None):
    """就地改事件的 title / desc / 各 option 的名称与触发目标。

    只替换匹配到的行，不动其它内容；改前 snapshot。"""
    eid = (eid or "").strip()
    root = paths._pick(root)
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
                    _reload()
                    return {"ok": True, "id": eid, "file": os.path.relpath(p, root),
                            "locFile": _lf, "changed": ["文本"],
                            "msg": "已更新 %s 的文本（写进 %s）" % (eid, _lf)}
                return {"ok": False, "msg": "没有实际改动（参数为空或未匹配到字段）"}
            snapshot(p)
            _atomic_write(p, _bom_for(p) + "".join(out).encode("utf-8"))
            # 中文文本写进本地化，不塞回事件文件
            _pairs = {}
            if title_text and title:
                _pairs[title] = title_text
            if desc_text and desc:
                _pairs[desc] = desc_text
            _locfn = _loc_write_pairs(root, _pairs) if _pairs else ""
            if _pairs:
                changed.append("文本")
            _reload()
            _msg = "已更新 %s 的 %s" % (eid, "、".join(sorted(set(changed))))
            if _locfn:
                _msg += "（文本写进 %s）" % _locfn
            return {"ok": True, "id": eid, "file": os.path.relpath(p, root),
                    "locFile": _locfn, "changed": changed, "msg": _msg}
    return {"ok": False, "msg": "找不到事件 %s" % eid}



def _build_event_entry(eid, ev_type, ns, inner_body, rel, src, raw_full=None):
    raw_str = raw_full.strip() if raw_full is not None else ("%s = {\n%s\n}" % (ev_type, (inner_body or "").strip()))
    loc_map = state.loc()
    title = loc_map.get(eid + ".t", "")
    if not title:
        clean = strip_comments(inner_body or raw_str)
        tm = re.search(r'(?m)^\s*title\s*=\s*"?([A-Za-z0-9_.\-]+)"?', clean)
        if tm:
            title = loc_map.get(tm.group(1), "")
    return {
        "id": eid,
        "file": rel,
        "source": src,
        "type": ev_type,
        "ns": ns,
        "title": title,
        "raw": raw_str,
    }


def event_view(eid):
    item = state.events().get(eid)
    if not item:
        return None
    return {k: v for k, v in item.items() if k != "raw"}


def load_events(root):
    # 按 HOI4 实机规则读（respect replace_path 与同名文件整文件覆写，底层 → 顶层）。
    n = 0
    for ab, d, fn in effective_layer_files("events", root):
        name = os.path.basename(ab.rstrip("\\/")) or ab
        rel = os.path.join("events", fn)
        text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8-sig", errors="replace").read())
        all_ns = re.findall(r'(?m)^\s*add_namespace\s*=\s*(\w+)', text)
        def_ns = all_ns[0] if all_ns else ""
        for k, v, b in top_items(text):
            if not b or not k.endswith("_event"):
                continue
            m = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_.\-]+)"?', v)
            if not m:
                continue
            eid = m.group(1)
            ns = eid.split(".", 1)[0] if "." in eid else def_ns
            state.events()[eid] = _build_event_entry(eid, k, ns, v, rel, name)
            n += 1
    return n



def _writable_mod_top(root=None):
    top = None
    for r in (state.roots() or []):
        lay = paths.mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top and root and not is_under_game(root):
        top = root
    return top


def _adopt_rel_to_top(root, rel):
    """当目标文件不在当前可写顶层或传入了只读层时，从生效链拷贝到顶层可写 mod。"""
    top = _writable_mod_top(root)
    if not top:
        return None, "找不到可写的 mod 目录"
    dst = os.path.join(top, rel)
    if os.path.isfile(dst):
        return dst, ""
    norm_rel = rel.replace("\\", "/")
    cands = []
    if root:
        cands.append(os.path.join(root, rel))
    for b in reversed(paths.mod_layers(top) or []):
        if b:
            cands.append(os.path.join(b, norm_rel.replace("/", os.sep)))
    src = next((c for c in cands if os.path.isfile(c)), None)
    if not src:
        return None, "找不到文件：" + rel
    os.makedirs(os.path.dirname(dst) or top, exist_ok=True)
    import shutil as _sh
    _sh.copyfile(src, dst)
    return dst, ""


# ---------------- 事件 ----------------
def save_event(root, rel, eid, raw, title="", desc="", title_ja="", desc_ja="",
               title_en="", desc_en="", options=None, trigger_raw="", immediate_raw="", picture=""):
    if not rel or not eid:
        return False, "参数不完整：缺少文件或事件 id"
    explicit = {os.path.abspath(r) for r in (state.roots() or []) if r}
    need_adopt = (
        not root
        or is_under_game(root)
        or is_readonly_mod(root)
        or (bool(explicit) and os.path.abspath(root) not in explicit)
    )
    path = os.path.join(root, rel) if root else ""
    if need_adopt or not path or not os.path.isfile(path):
        path, err = _adopt_rel_to_top(root, rel)
        if not path:
            return False, err
        root = _writable_mod_top(root) or root
    with io.open(path, "rb") as f:
        raw_bytes = f.read()
    text = raw_bytes.decode("utf-8-sig" if raw_bytes.startswith(b"\xef\xbb\xbf") else "utf-8", errors="replace")

    if trigger_raw:
        raw = set_raw_block(raw, "trigger", trigger_raw)
    if immediate_raw:
        raw = set_raw_block(raw, "immediate", immediate_raw)
    if picture:
        raw = set_scalar(raw, "picture", picture)

    # 精确匹配包含该 id 的完整 *_event = { ... } 块，避免残余前缀（原 text[:brace-1] 会残留 country_event =）
    ev_span = None
    for em in re.finditer(r'(?m)^[ \t]*[A-Za-z_]*_event[ \t]*=\s*\{', text):
        eb = text.find("{", em.end() - 1)
        ee = brace_match(text, eb)
        if ee <= eb:
            continue
        ebody = text[eb + 1:ee - 1]
        if re.search(r'(?m)^[ \t]*id\s*=\s*"?%s"?' % re.escape(eid), ebody):
            ev_span = (em.start(), ee)
            break
    if not ev_span:
        return False, "未找到事件 " + eid
    ev_start, e = ev_span
    if not braces_balanced(raw):
        return False, "花括号不匹配，未保存"
    all_ns = re.findall(r'(?m)^\s*add_namespace\s*=\s*(\w+)', text)
    if all_ns and "." in eid:
        ev_ns = eid.split(".", 1)[0]
        if ev_ns not in all_ns:
            return False, "事件 id 前缀「%s」不在文件声明的 add_namespace（%s）中" % (ev_ns, ", ".join(all_ns))
    if "option" not in raw:
        return False, "事件至少需要一个 option"
    snapshot(path)
    new_text = text[:ev_start] + raw.strip() + "\n" + text[e:]
    _atomic_write(path, _bom_for(path) + new_text.encode("utf-8"))
    state.changed()[path] = rel
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
    _EVENT_GRAPH_CACHE.clear()
    raw_clean = raw.strip()
    tm = re.match(r'\s*([A-Za-z_]*_event)\s*=\s*\{', raw_clean)
    ev_type = tm.group(1) if tm else (state.events().get(eid, {}).get("type") or "country_event")
    rb = raw_clean.find("{")
    re_idx = raw_clean.rfind("}")
    inner_body = raw_clean[rb + 1:re_idx] if (rb >= 0 and re_idx > rb) else raw_clean
    ns = eid.split(".", 1)[0] if "." in eid else (all_ns[0] if all_ns else "")
    src = os.path.basename((root or "").rstrip("\\/")) or root
    state.events()[eid] = _build_event_entry(eid, ev_type, ns, inner_body, rel, src, raw_full=raw_clean)
    return True, "事件已保存"



def add_event(root, eid):
    if not re.match(r'^[A-Za-z0-9_]+\.[A-Za-z0-9_]+$', eid or ""):
        return False, "事件 id 需要 namespace.member 格式"
    ns = eid.split(".")[0]
    d = os.path.join(root, "events")
    os.makedirs(d, exist_ok=True)
    fn = unique_editor_filename(root, "events", "zz_focus_editor_events.txt")
    path = os.path.join(d, fn)
    text = io.open(path, encoding="utf-8-sig", errors="replace", newline="").read() if os.path.exists(path) else ""
    if re.search(r'(?m)^\s*id\s*=\s*"?%s"?' % re.escape(eid), text):
        return False, "事件已存在"
    if not re.search(r'(?m)^\s*add_namespace\s*=\s*' + re.escape(ns) + r'\b', text):
        text += "\nadd_namespace = %s\n" % ns
    block = ("country_event = {\n\tid = %s\n\ttitle = %s.t\n\tdesc = %s.d\n"
             "\tis_triggered_only = yes\n\toption = {\n\t\tname = %s.a\n\t}\n}" % (eid, eid, eid, eid))
    text += "\n" + block + "\n"
    snapshot(path)
    _atomic_write(path, _bom_for(path) + text.encode("utf-8"))
    rel = os.path.join("events", fn)
    state.changed()[path] = rel
    _EVENT_GRAPH_CACHE.clear()
    ib = block.find("{")
    ie = block.rfind("}")
    inner_body = block[ib + 1:ie]
    src = os.path.basename((root or "").rstrip("\\/")) or root
    state.events()[eid] = _build_event_entry(eid, "country_event", ns, inner_body, rel, src, raw_full=block)
    return True, "已新建事件 " + eid



def delete_event(root, rel, eid):
    if not rel or not eid:
        return False, "参数不完整"
    path = os.path.join(root, rel) if root else ""
    if not path or not os.path.isfile(path) or is_under_game(root or ""):
        path, err = _adopt_rel_to_top(root, rel)
        if not path:
            return False, err
    with io.open(path, "rb") as f:
        raw_bytes = f.read()
    text = raw_bytes.decode("utf-8-sig" if raw_bytes.startswith(b"\xef\xbb\xbf") else "utf-8", errors="replace")
    ev_span = None
    id_pat = re.compile(r'(?m)^[ \t]*id\s*=\s*"?%s"?(?![A-Za-z0-9_.\-])' % re.escape(eid))
    for em in re.finditer(r'(?m)^[ \t]*[A-Za-z_]*_event[ \t]*=\s*\{', text):
        eb = text.find("{", em.end() - 1)
        ee = brace_match(text, eb)
        if ee <= eb:
            continue
        ebody = text[eb + 1:ee - 1]
        if id_pat.search(ebody):
            ev_span = (em.start(), ee)
            break
    if not ev_span:
        return False, "未找到事件 " + eid
    ev_start, ee = ev_span
    new_text = text[:ev_start] + text[ee:]
    snapshot(path)
    _atomic_write(path, _bom_for(path) + new_text.encode("utf-8"))
    state.changed()[path] = rel
    _EVENT_GRAPH_CACHE.clear()
    events = state.events()
    events.pop(eid, None)
    roots = list(state.roots() or [])
    if not roots and root:
        roots = [root]
    for r in reversed(roots):
        hit = False
        for ab, d, fn in reversed(effective_layer_files("events", r)):
            fp = os.path.join(d, fn)
            try:
                raw = io.open(fp, encoding="utf-8-sig", errors="replace", newline="").read()
            except Exception:
                continue
            if eid not in raw:
                continue
            text_l = strip_comments(raw)
            all_ns = re.findall(r'(?m)^\s*add_namespace\s*=\s*(\w+)', text_l)
            ns = eid.split(".", 1)[0] if "." in eid else (all_ns[0] if all_ns else "")
            for k, v, b in top_items(text_l):
                if not b or not k.endswith("_event"):
                    continue
                em2 = re.search(r'(?m)^\s*id\s*=\s*"?([A-Za-z0-9_.\-]+)"?', v)
                if em2 and em2.group(1) == eid:
                    src_l = os.path.basename(ab.rstrip("\\/")) or ab
                    rel_l = os.path.join("events", fn)
                    events[eid] = _build_event_entry(eid, k, ns, v, rel_l, src_l)
                    hit = True
                    break
            if hit:
                break
        if hit:
            break
    return True, "已删除事件 " + eid
