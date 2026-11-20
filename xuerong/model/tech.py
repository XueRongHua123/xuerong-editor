# -*- coding: utf-8 -*-
"""科技域（P0-3 D4 从 focus_editor.py 迁入）。

读 common/technologies 的 technology 块；写要处理 `x = @token` 这种坐标 token
（_tech_coord_token / tech_move）。比 equipment 复杂，所以在它之后搬。

依赖边界：
  · TECHS / LOC / CHANGED → xuerong.state
  · 文本改写 → core.text；BOM 读写与叠加链 → core.paths
  · 国家历史定位 → model.country；本地化写 → model.loc；快照 → model.history
  · 唯一钩子：reload_data
"""
import io
import os
import re

from xuerong import state
from xuerong.core import paths
from xuerong.core.paths import (_layer_dirs, _read_bom_text, _write_bom_text,
                                effective_layer_files, is_under_game,
                                mod_layers, unique_editor_filename)
from xuerong.core.text import (_atomic_write, _bom_for, _strip_keep_len, brace_match,
                               braces_balanced, find_blocks, set_raw_block, set_scalar,
                               strip_comments, top_items)
from xuerong.model.country import _country_hist_file, _country_hist_write_base
from xuerong.model.history import snapshot
from xuerong.model.loc import save_loc

_RELOAD = None


def bind(reload_data):
    global _RELOAD
    _RELOAD = reload_data


def _reload():
    if _RELOAD:
        _RELOAD()


def _looks_tech(body):
    keys = {"research_cost", "start_year", "year", "folder", "path", "xp_research",
            "enable_equipments", "research_cost", "categories"}
    return any(k in keys for k, v, b in top_items(body))



def load_techs(root):
    name = os.path.basename(root.rstrip("\\/")) or root
    n = 0
    _tech_files = [
        (os.path.basename((_b or "").rstrip("\\/")) or (_b or name), _d, _f)
        for _b, _d, _f in effective_layer_files("common/technologies", root)
    ]
    for src, d, fn in _tech_files:
        rel = os.path.join("common", "technologies", fn)
        text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8-sig", errors="replace").read())
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
                    state.techs()[tid] = {"id": tid, "file": rel, "source": src,
                                  "name": state.loc().get(tid, tid),
                                  "year": yr.group(1) if yr else "",
                                  "path": fname,
                                  "fx": fpx,
                                  "fy": fpy,
                                  "cost": cost.group(1) if cost else "",
                                  "prereq": pre, "leads": leads,
                                  "raw": "%s = {\n%s\n}" % (tid, tv.strip())}
                    n += 1
    for t in state.techs().values():
        t["leads"] = [x for x in t.get("leads", []) if x in state.techs() and x != t["id"]]
        t["prereq"] = [p for p in t.get("prereq", []) if p in state.techs() and p != t["id"]]
    for tid, t in state.techs().items():
        pre = set(t["prereq"])
        for other in state.techs().values():
            if tid in other.get("leads", []):
                pre.add(other["id"])
        t["prereq"] = sorted(pre)
    return n



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
    if tid in state.techs():
        state.techs()[tid]["fx"] = x
        state.techs()[tid]["fy"] = y
    return {"ok": True, "msg": "%s → x=%d y=%d" % (tid, x, y), "x": x, "y": y}



def load_country_techs(root=None, tag=""):
    """解析某国的 set_technology，返回已解锁科技列表。"""
    root = paths._pick(root)
    tag = (tag or "").upper()
    if not tag:
        return {"ok": False, "msg": "没给 tag", "unlocked": []}
    p, rel = _country_hist_file(root, tag)
    if not p:
        return {"ok": False, "msg": "找不到 %s 的国家历史文件" % tag, "unlocked": []}
    try:
        raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
    except Exception as e:
        return {"ok": False, "msg": "读取失败：%s" % e, "unlocked": []}
    text = _strip_keep_len(raw)
    unlocked, blocks = [], 0
    for a, b, body in find_blocks(text, "set_technology"):
        blocks += 1
        for ln in body.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            m = re.match(r'([A-Za-z][A-Za-z0-9_\-\.]*)\s*=\s*1\b', ln)
            if m:
                unlocked.append(m.group(1))
    # 去重保序
    seen = set()
    out = []
    for x in unlocked:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return {"ok": True, "tag": tag, "file": os.path.basename(p),
            "blocks": blocks, "unlocked": out, "count": len(out),
            "msg": "%s：%d 项科技（%d 个 set_technology 块）" % (tag, len(out), blocks)}



def country_tech_toggle(root, tag, tech, on=True):
    """给某国加上或去掉一项初始科技。"""
    root = paths._pick(root)
    tag = (tag or "").upper()
    tech = (tech or "").strip()
    if not tag or not tech:
        return {"ok": False, "msg": "tag 和科技 id 都要给"}
    src, rel = _country_hist_file(root, tag)
    if not src:
        return {"ok": False, "msg": "找不到 %s 的国家历史文件" % tag}
    tgt, err = _country_hist_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    dst = os.path.join(tgt, rel)
    os.makedirs(os.path.dirname(dst) or tgt, exist_ok=True)
    if not os.path.exists(dst):
        try:
            import shutil as _sh
            _sh.copyfile(src, dst)
        except Exception as e:
            return {"ok": False, "msg": "复制来源失败：%s" % e}

    raw = io.open(dst, encoding="utf-8-sig", errors="replace").read()
    text = _strip_keep_len(raw)
    blocks = list(find_blocks(text, "set_technology"))
    cur = load_country_techs(root, tag)["unlocked"]
    has = tech in cur

    if on and has:
        return {"ok": True, "msg": "已经有 %s 了" % tech}
    if (not on) and (not has):
        return {"ok": True, "msg": "本来就没有 %s" % tech}

    if not blocks:
        if not on:
            return {"ok": True, "msg": "本来就没有 %s" % tech}
        ins = "\n\tset_technology = {\n\t\t%s = 1\n\t}\n" % tech
        body_i = text.find("history = {")
        if body_i >= 0:
            br = text.find("{", body_i)
            pos = br + 1
            new_text = raw[:pos] + ins + raw[pos:]
        else:
            new_text = raw.rstrip() + "\nhistory = {" + ins + "}\n"
        snapshot(dst)
        _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
        return {"ok": True, "msg": "已加 %s（新建 set_technology 块）" % tech}

    a, b, body = blocks[0]
    if on:
        # 在块末尾插入
        ins = "\n\t\t%s = 1" % tech
        new_text = raw[:b - 1] + ins + raw[b - 1:]
    else:
        # 删掉那一行
        pat = re.compile(r'(?m)^[ \t]*' + re.escape(tech) + r'[ \t]*=[ \t]*1[ \t]*\r?\n?')
        seg = raw[a:b]
        seg2 = pat.sub('', seg)
        if seg2 == seg:
            return {"ok": False, "msg": "没定位到 %s 那一行" % tech}
        new_text = raw[:a] + seg2 + raw[b:]

    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "%s %s" % ("已加" if on else "已删", tech)}



def tech_tree_graph(folder="", tag=None, root=None):
    """返回某个 folder 下的科技树节点与连线，供预览渲染。

    坐标来自 state.techs() 的 fx / fy（解析 technologies 定义时读的 x / y）。
    tag 给了就带上该国的解锁状态（unlocked）。
    """
    root = paths._pick(root)
    folder = (folder or "").strip()
    unlocked = set()
    if tag:
        try:
            unlocked = set(load_country_techs(root, tag).get("unlocked") or [])
        except Exception:
            unlocked = set()
    if not folder:
        from collections import Counter
        c = Counter((t.get("path") or "") for t in state.techs().values())
        folders = [{"folder": k or "其他", "count": v}
                   for k, v in sorted(c.items(), key=lambda kv: -kv[1])]
        return {"ok": True, "folders": folders,
                "msg": "%d 个科技目录" % len(folders)}

    nodes, byid = [], {}
    for tid, t in state.techs().items():
        if (t.get("path") or "") != folder:
            continue
        fx, fy = t.get("fx"), t.get("fy")
        if fx in (None, "") or fy in (None, ""):
            continue
        try:
            x = float(fx)
            y = float(fy)
        except Exception:
            continue
        n = {"id": tid, "name": t.get("name") or tid,
             "x": x, "y": y, "year": t.get("year") or "",
             "cost": t.get("cost") or "",
             "on": tid in unlocked}
        nodes.append(n)
        byid[tid] = n
    edges = []
    for tid, t in state.techs().items():
        if tid not in byid:
            continue
        for child in (t.get("leads") or []):
            if child in byid:
                edges.append([tid, child])
    # 没坐标的也报一下数量，界面可以提示
    noxy = sum(1 for tid, t in state.techs().items()
               if (t.get("path") or "") == folder
               and (t.get("fx") in (None, "") or t.get("fy") in (None, "")))
    return {"ok": True, "folder": folder, "nodes": nodes, "edges": edges,
            "total": len(nodes), "noxy": noxy,
            "msg": "%s：%d 个节点、%d 条连线%s" % (
                folder, len(nodes), len(edges),
                ("，%d 个无坐标已跳过" % noxy) if noxy else "")}



def country_techs_payload(root=None, tag=""):
    """界面用：已解锁 + 全部科技分组。"""
    info = load_country_techs(root, tag)
    if not info.get("ok"):
        return info
    unlocked = set(info["unlocked"])
    groups = {}
    for tid, t in state.techs().items():
        path = t.get("path") or "其他"
        groups.setdefault(path, []).append({
            "id": tid, "name": t.get("name") or tid,
            "year": t.get("year") or "", "cost": t.get("cost") or "",
            "prereq": t.get("prereq") or [],
            "on": tid in unlocked,
        })
    for k in groups:
        groups[k].sort(key=lambda x: (x["year"], x["id"]))
    items = [{"folder": k, "techs": v} for k, v in sorted(groups.items())]
    return {"ok": True, "tag": tag, "file": info["file"],
            "unlocked": info["unlocked"], "count": info["count"],
            "groups": items, "total": len(state.techs()),
            "msg": info["msg"]}



# ---------------- 科技 ----------------
def validate_tech_script(raw, tid):
    if not braces_balanced(raw):
        return False, "花括号不匹配"
    for m in re.finditer(r'(?m)^\s*(research_cost|start_year|year)\s*=\s*([^\s#]+)', raw):
        if not re.match(r'^[0-9.]+$', m.group(2)):
            return False, "%s 必须是数字" % m.group(1)
    for m in re.finditer(r'leads_to_tech\s*=\s*"?([A-Za-z0-9_]+)"?', raw):
        t = m.group(1)
        if t != tid and t not in state.techs():
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
    _atomic_write(path, _bom_for(path) + (text[:m.start()] + raw.strip() + "\n" + text[e:]).encode("utf-8"))
    state.changed()[path] = rel
    ents = {}
    if name: ents.setdefault("simp_chinese", {})[tid] = name
    if desc: ents.setdefault("simp_chinese", {})[tid + "_desc"] = desc
    if name_ja: ents.setdefault("japanese", {})[tid] = name_ja
    if desc_ja: ents.setdefault("japanese", {})[tid + "_desc"] = desc_ja
    if name_en: ents.setdefault("english", {})[tid] = name_en
    if desc_en: ents.setdefault("english", {})[tid + "_desc"] = desc_en
    if ents:
        save_loc(root, ents)
    _reload()
    return True, "科技已保存"



def add_tech(root, tid, folder, year="1936"):
    if not re.match(r'^[A-Za-z0-9_]+$', tid or ""):
        return False, "科技 id 只能字母数字下划线"
    folder = folder or "custom_folder"
    d = os.path.join(root, "common", "technologies")
    os.makedirs(d, exist_ok=True)
    fn = unique_editor_filename(root, "common/technologies", "zz_focus_editor_technologies.txt")
    path = os.path.join(d, fn)
    text = io.open(path, encoding="utf-8", errors="replace", newline="").read() if os.path.exists(path) else "technologies = {\n}\n"
    if re.search(r'(?m)^\s*%s\s*=\s*\{' % re.escape(tid), text):
        return False, "科技已存在"
    block = ("\t%s = {\n\t\tresearch_cost = 1\n\t\tstart_year = %s\n"
             "\t\tfolder = {\n\t\t\tname = %s\n\t\t\tposition = { x = 0 y = 0 }\n\t\t}\n\t}\n" % (tid, year, folder))
    tm = re.search(r'(?m)^\s*technologies\s*=\s*\{', text)
    if not tm:
        return False, "缺少 technologies = { ... } 根块"
    tb = text.find('{', tm.start())
    te = brace_match(text, tb)
    text = text[:te - 1] + block + text[te - 1:]
    snapshot(path)
    _atomic_write(path, _bom_for(path) + text.encode("utf-8"))
    state.changed()[path] = os.path.join("common", "technologies", fn)
    _reload()
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
    _atomic_write(path, _bom_for(path) + (text[:m.start()] + text[e:]).encode("utf-8"))
    state.changed()[path] = rel
    _reload()
    return True, "已删除科技 " + tid



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
    adj = {k: set(v.get("leads", [])) for k, v in state.techs().items()}
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
    state.changed()[path] = rel
    _reload()
    return True, "已添加前置：%s → %s" % (src, dst)
