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
from xuerong.core import gfx, paths
from xuerong.core.paths import (_layer_dirs, _layers_find, _read_bom_text, _write_bom_text,
                                effective_layer_files, is_readonly_mod, is_under_game,
                                mod_layers, unique_editor_filename)
from xuerong.core.text import (_atomic_write, _bom_for, _strip_keep_len, append_into_block,
                               brace_match, braces_balanced, collect_top_blocks, find_blocks,
                               insert_before_date_or_end, set_raw_block, set_scalar,
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



def _extract_id_list(clean, key):
    """提取科技块内 key = { a b c } 的顶层标识符列表（跳过 limit = { ... }，去重保序）。"""
    out = []
    seen = set()
    for m in re.finditer(r'(?m)^\s*%s\s*=\s*\{' % re.escape(key), clean):
        b = clean.find('{', m.start())
        e = brace_match(clean, b)
        inner = clean[b + 1:e - 1]
        # 去掉 limit = { ... } 等嵌套条件块，避免把 has_dlc / tag 当成科技或编制 ID
        inner = re.sub(r'[A-Za-z0-9_]+\s*=\s*\{[^{}]*\}', ' ', inner)
        for tok in re.findall(r'[A-Za-z][A-Za-z0-9_]*', inner):
            if tok not in seen:
                seen.add(tok)
                out.append(tok)
    return out


def _build_tech_entry(tid, tv, rel, src, macros=None):
    macros = macros or {}

    def _num(tok):
        tok = (tok or "").strip()
        if tok.startswith("@"):
            tok = macros.get(tok[1:], "")
        try:
            return float(tok)
        except Exception:
            return None

    clean = strip_comments(tv or "")
    yr = re.search(r'(?m)^\s*(?:start_year|year)\s*=\s*(\d+)', clean)
    fname = "其他"
    fpx = fpy = None
    fb = re.search(r'folder\s*=\s*\{', clean)
    if fb:
        fstart = clean.find('{', fb.start())
        fend = brace_match(clean, fstart)
        finner = clean[fstart + 1:fend - 1]
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
    cost = re.search(r'(?m)^\s*research_cost\s*=\s*([0-9.]+)', clean)

    paths_list = []
    leads = []
    for pm in re.finditer(r'(?m)^\s*path\s*=\s*\{', clean):
        pb = clean.find('{', pm.start())
        pe = brace_match(clean, pb)
        pinner = clean[pb + 1:pe - 1]
        cm = re.search(r'research_cost_coeff\s*=\s*([0-9.]+)', pinner)
        coeff = 1
        if cm:
            try:
                f_c = float(cm.group(1))
                coeff = int(f_c) if f_c.is_integer() else f_c
            except Exception:
                coeff = 1
        for lm in re.finditer(r'leads_to_tech\s*=\s*"?([A-Za-z0-9_]+)"?', pinner):
            tgt = lm.group(1)
            leads.append(tgt)
            paths_list.append({"target": tgt, "coeff": coeff})
    if not paths_list:
        for tgt in re.findall(r'leads_to_tech\s*=\s*"?([A-Za-z0-9_]+)"?', clean):
            leads.append(tgt)
            paths_list.append({"target": tgt, "coeff": 1})

    pre = []
    for pm in re.finditer(r'prerequisite\s*=\s*\{', clean):
        pb = clean.find('{', pm.start())
        pe = brace_match(clean, pb)
        pre += re.findall(r'[A-Za-z][A-Za-z0-9_]*', clean[pb + 1:pe - 1])

    xor_list = _extract_id_list(clean, "xor")
    categories = _extract_id_list(clean, "categories")
    enable_equipments = _extract_id_list(clean, "enable_equipments")
    enable_subunits = _extract_id_list(clean, "enable_subunits")
    sub_technologies = _extract_id_list(clean, "sub_technologies")

    sprites = state.sprite_map() or gfx.SPRITE_MAP
    cand_icon = "GFX_%s_medium" % tid
    icon = cand_icon if cand_icon in sprites else ""

    return {
        "id": tid, "file": rel, "source": src,
        "name": state.loc().get(tid, tid),
        "year": yr.group(1) if yr else "",
        "path": fname,
        "fx": fpx,
        "fy": fpy,
        "cost": cost.group(1) if cost else "",
        "prereq": pre, "leads": leads,
        "paths": paths_list,
        "xor": xor_list,
        "categories": categories,
        "enable_equipments": enable_equipments,
        "enable_subunits": enable_subunits,
        "sub_technologies": sub_technologies,
        "icon": icon,
        "raw": "%s = {\n%s\n}" % (tid, (tv or "").strip()),
    }


def tech_view(tid):
    item = state.techs().get(tid)
    if not item:
        return None
    return {k: v for k, v in item.items() if k != "raw"}


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
        for s, e, body in find_blocks(text, "technologies"):
            for k, v, b in top_items(body):
                if not b:
                    continue
                if _looks_tech(v):
                    cand = [(k, v)]
                else:
                    cand = [(k2, v2) for k2, v2, b2 in top_items(v) if b2 and _looks_tech(v2)]
                for tid, tv in cand:
                    state.techs()[tid] = _build_tech_entry(tid, tv, rel, src, macros=macros)
                    n += 1
    for t in state.techs().values():
        tid_c = t["id"]
        t["leads"] = [x for x in t.get("leads", []) if x in state.techs() and x != tid_c]
        t["paths"] = [po for po in t.get("paths", []) if po.get("target") in state.techs() and po.get("target") != tid_c]
        t["prereq"] = [p for p in t.get("prereq", []) if p in state.techs() and p != tid_c]
        t["xor"] = [x for x in t.get("xor", []) if x in state.techs() and x != tid_c]
    for tid, t in state.techs().items():
        pre = set(t["prereq"])
        for other in state.techs().values():
            if tid in other.get("leads", []):
                pre.add(other["id"])
        t["prereq"] = sorted(pre)
        for xid in list(t.get("xor") or []):
            other = state.techs().get(xid)
            if other is not None and tid not in (other.get("xor") or []):
                other["xor"] = sorted(set(other.get("xor") or []) | {tid})
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



def _writable_tech_top(root=None):
    """找非原版、非工坊的可写链顶 mod 目录。"""
    picked = paths._pick(root)
    if picked:
        lay = mod_layers(picked) or [picked]
        for cand in reversed(lay):
            if cand and not is_under_game(cand) and not is_readonly_mod(cand):
                return cand
    for r in reversed(state.roots() or []):
        lay = mod_layers(r) or [r]
        for cand in reversed(lay):
            if cand and not is_under_game(cand) and not is_readonly_mod(cand):
                return cand
    return None


def _ensure_tech_file_writable(root, rel, tid=None):
    """单文件接管：若 rel 在只读层或顶层尚不存在，从叠加链复制单文件到可写链顶。"""
    if not rel and tid:
        rel = (state.techs().get(tid) or {}).get("file") or ""
    if not rel:
        return None, None, "", "缺少文件路径"
    rel_n = rel.replace("\\", "/").lstrip("/")
    top = _writable_tech_top(root)
    if not top:
        return None, None, rel_n, "找不到可写的 mod 目录（原版与工坊目录只读）"
    dst = os.path.join(top, rel_n.replace("/", os.sep))
    if not os.path.isfile(dst):
        layers = mod_layers(top) or [top]
        src, _sr = _layers_find(rel_n, layers)
        if not src or not os.path.isfile(src):
            return top, None, rel_n, "找不到文件：" + rel_n
        os.makedirs(os.path.dirname(dst) or top, exist_ok=True)
        txt = io.open(src, encoding="utf-8-sig", errors="replace").read()
        _atomic_write(dst, txt.encode("utf-8"))
    return top, dst, rel_n, ""


def _sync_tech_relations(tid, old_entry, new_entry):
    """增量重建 state.techs() 中 tid 与其他科技的双向 prereq / leads / xor。"""
    techs = state.techs()
    old_leads = set((old_entry or {}).get("leads") or [])
    new_leads = [x for x in (new_entry.get("leads") or []) if x in techs and x != tid]
    new_entry["leads"] = new_leads
    new_entry["paths"] = [
        po for po in (new_entry.get("paths") or [])
        if po.get("target") in techs and po.get("target") != tid
    ]

    # 更新被删除 leads 的目标 prereq
    for lost in old_leads - set(new_leads):
        other = techs.get(lost)
        if other is not None:
            # 只有当 other 自身 raw 的 prerequisite 没有声明 tid 时才移除
            oclean = strip_comments(other.get("raw") or "")
            has_own_pre = False
            for pm in re.finditer(r'prerequisite\s*=\s*\{', oclean):
                pb = oclean.find('{', pm.start())
                pe = brace_match(oclean, pb)
                if tid in re.findall(r'[A-Za-z][A-Za-z0-9_]*', oclean[pb + 1:pe - 1]):
                    has_own_pre = True
                    break
            if not has_own_pre:
                other["prereq"] = [p for p in (other.get("prereq") or []) if p != tid]

    # 更新新增 leads 的目标 prereq
    for added in new_leads:
        other = techs.get(added)
        if other is not None:
            other["prereq"] = sorted(set(other.get("prereq") or []) | {tid})

    # 更新自身 prereq
    pre = {p for p in (new_entry.get("prereq") or []) if p in techs and p != tid}
    for other_id, other in techs.items():
        if other_id != tid and tid in (other.get("leads") or []):
            pre.add(other_id)
    new_entry["prereq"] = sorted(pre)

    # 更新双向 xor
    old_xor = set((old_entry or {}).get("xor") or [])
    new_xor = sorted({x for x in (new_entry.get("xor") or []) if x in techs and x != tid})
    new_entry["xor"] = new_xor
    for lost in old_xor - set(new_xor):
        other = techs.get(lost)
        if other is not None:
            other["xor"] = [x for x in (other.get("xor") or []) if x != tid]
    for added in new_xor:
        other = techs.get(added)
        if other is not None:
            other["xor"] = sorted(set(other.get("xor") or []) | {tid})

    techs[tid] = new_entry


def _refresh_tech_in_state(top, path, rel, tid, full_text=None):
    """从磁盘文本重新解析 tid 并增量刷新 state.techs()。"""
    if full_text is None:
        full_text = io.open(path, encoding="utf-8-sig", errors="replace").read()
    clean = strip_comments(full_text)
    loc = _tech_block_range(clean, tid)
    if not loc:
        return None
    b, e = loc
    tv = clean[b + 1:e - 1]
    macros = {}
    for mm in re.finditer(r'(?m)^\s*@([A-Za-z0-9_]+)\s*=\s*(-?[0-9.]+)', clean):
        macros[mm.group(1)] = mm.group(2)
    src = os.path.basename((top or "").rstrip("\\/")) or (top or "")
    rel_os = rel.replace("/", os.sep)
    old_entry = state.techs().get(tid)
    entry = _build_tech_entry(tid, tv, rel_os, src, macros=macros)
    _sync_tech_relations(tid, old_entry, entry)
    return entry


def _update_tech_pos_in_text(text, tid, x, y, macros, year=None):
    """在文件文本中原地更新某科技块的 folder.position（保留 @宏）及可选 start_year。"""
    loc = _tech_block_range(text, tid)
    if not loc:
        return text, False, "找不到科技块：" + tid
    b, e = loc
    block = text[b + 1:e - 1]

    fm = re.search(r'(?m)^[ \t]*folder\s*=\s*\{', block)
    if not fm:
        return text, False, "这个科技没有 folder 块：" + tid
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
    if year is not None and str(year).strip():
        ys = str(year).strip()
        ym = re.search(r'(?m)^([ \t]*)(start_year|year)[ \t]*=[ \t]*\d+', block2)
        if ym:
            block2 = block2[:ym.start()] + "%s%s = %s" % (ym.group(1), ym.group(2), ys) + block2[ym.end():]
    return text[:b + 1] + block2 + text[e - 1:], True, ""


def tech_move(root, rel, tid, x, y):
    """把科技在树上的位置写回 folder.position 的 x/y（支持单文件接管与 @宏 保留）。"""
    if not rel or not tid:
        return {"ok": False, "msg": "参数不完整"}
    if root and is_under_game(root) and not _writable_tech_top(None):
        return {"ok": False, "msg": "原版目录只读：请先复制到自己的模组再修改"}
    top, p, rel_n, err = _ensure_tech_file_writable(root, rel, tid=tid)
    if not p:
        return {"ok": False, "msg": err}
    try:
        x = int(round(float(x)))
        y = int(round(float(y)))
    except Exception:
        return {"ok": False, "msg": "坐标必须是整数"}

    text = io.open(p, encoding="utf-8-sig", errors="replace").read()
    macros = {}
    for mm in re.finditer(r'(?m)^[ \t]*@([A-Za-z0-9_]+)\s*=\s*(-?[0-9.]+)', text):
        macros[mm.group(1)] = mm.group(2)

    new_text, ok_u, msg_u = _update_tech_pos_in_text(text, tid, x, y, macros)
    if not ok_u:
        return {"ok": False, "msg": msg_u}
    if new_text == text:
        return {"ok": True, "msg": "坐标没变"}
    snapshot(p)
    _atomic_write(p, new_text.encode("utf-8"))
    if tid in state.techs():
        state.techs()[tid]["fx"] = x
        state.techs()[tid]["fy"] = y
        state.techs()[tid]["file"] = rel_n.replace("/", os.sep)
        state.techs()[tid]["source"] = os.path.basename((top or "").rstrip("\\/")) or (top or "")
    return {"ok": True, "msg": "%s → x=%d y=%d" % (tid, x, y), "x": x, "y": y}


def tech_batch_move(root, moves):
    """批量更新多个科技坐标（[{tid, rel?, x, y, year?}]），自动按文件单文件接管并增量刷新。"""
    if not isinstance(moves, (list, tuple)) or not moves:
        return {"ok": False, "msg": "moves 不能为空"}

    by_rel = {}
    for mv in moves:
        if not isinstance(mv, dict):
            continue
        tid = (mv.get("tid") or mv.get("id") or "").strip()
        if not tid:
            continue
        rel = (mv.get("rel") or mv.get("file") or (state.techs().get(tid) or {}).get("file") or "").strip()
        if not rel:
            continue
        by_rel.setdefault(rel.replace("\\", "/"), []).append(mv)

    if not by_rel:
        return {"ok": False, "msg": "没有可移动的有效科技条目"}

    moved = 0
    results = []
    for rel_n, items in by_rel.items():
        top, p, _rn, err = _ensure_tech_file_writable(root, rel_n)
        if not p:
            results.append({"rel": rel_n, "ok": False, "msg": err})
            continue
        text = io.open(p, encoding="utf-8-sig", errors="replace").read()
        macros = {}
        for mm in re.finditer(r'(?m)^[ \t]*@([A-Za-z0-9_]+)\s*=\s*(-?[0-9.]+)', text):
            macros[mm.group(1)] = mm.group(2)

        cur_text = text
        changed_tids = []
        for mv in items:
            tid = (mv.get("tid") or mv.get("id") or "").strip()
            try:
                nx = int(round(float(mv.get("x", 0))))
                ny = int(round(float(mv.get("y", 0))))
            except Exception:
                results.append({"tid": tid, "ok": False, "msg": "坐标必须是整数"})
                continue
            yr = mv.get("year")
            nxt, ok_u, msg_u = _update_tech_pos_in_text(cur_text, tid, nx, ny, macros, year=yr)
            if not ok_u:
                results.append({"tid": tid, "ok": False, "msg": msg_u})
                continue
            cur_text = nxt
            changed_tids.append((tid, nx, ny, yr))

        if cur_text != text and braces_balanced(cur_text):
            snapshot(p)
            _atomic_write(p, cur_text.encode("utf-8"))
            state.changed()[p] = rel_n
        for tid, nx, ny, yr in changed_tids:
            if tid in state.techs():
                state.techs()[tid]["fx"] = nx
                state.techs()[tid]["fy"] = ny
                if yr is not None and str(yr).strip():
                    state.techs()[tid]["year"] = str(yr).strip()
                state.techs()[tid]["file"] = rel_n.replace("/", os.sep)
                state.techs()[tid]["source"] = os.path.basename((top or "").rstrip("\\/")) or (top or "")
            moved += 1
            results.append({"tid": tid, "ok": True, "x": nx, "y": ny})

    return {"ok": True, "moved": moved, "results": results, "msg": "已批量移动 %d 个科技" % moved}



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
    block_list, _dspans = collect_top_blocks(text, "set_technology", include_date=False)
    unlocked, blocks = [], len(block_list)
    for _depth, _a, _b, body in block_list:
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
    non_date_blocks, dspans = collect_top_blocks(text, "set_technology", include_date=False)
    top_blocks = [blk for blk in non_date_blocks if blk[0] == 0]
    cur = load_country_techs(root, tag)["unlocked"]
    has = tech in cur

    if on and has:
        return {"ok": True, "msg": "已经有 %s 了" % tech}
    if (not on) and (not has):
        return {"ok": True, "msg": "本来就没有 %s" % tech}

    if on:
        if top_blocks:
            _depth, _a, b, _body = top_blocks[0]
            new_text = append_into_block(raw, b, "\t%s = 1" % tech)
            msg = "已加 %s" % tech
        else:
            ins = "\nset_technology = {\n\t%s = 1\n}\n" % tech
            new_text = insert_before_date_or_end(raw, dspans, ins)
            msg = "已加 %s（新建 set_technology 块）" % tech
        snapshot(dst)
        _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
        return {"ok": True, "msg": msg}

    pat = re.compile(r'(?m)^[ \t]*' + re.escape(tech) + r'[ \t]*=[ \t]*1[ \t]*\r?\n?')
    new_text = None
    for _depth, a, b, _body in non_date_blocks:
        seg = raw[a:b]
        seg2 = pat.sub('', seg)
        if seg2 != seg:
            new_text = raw[:a] + seg2 + raw[b:]
            break
    if new_text is None:
        return {"ok": False, "msg": "没定位到 %s 那一行" % tech}

    snapshot(dst)
    _atomic_write(dst, _bom_for(dst) + new_text.encode("utf-8"))
    return {"ok": True, "msg": "已删 %s" % tech}



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
    top, path, rel_n, err = _ensure_tech_file_writable(root, rel, tid=tid)
    if not path:
        return False, err
    text = io.open(path, encoding="utf-8-sig", errors="replace", newline="").read()
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(tid), text)
    if not m:
        return False, "未找到科技 " + tid
    b = text.find('{', m.start())
    e = brace_match(text, b)
    if props:
        for k in ("year", "start_year", "research_cost", "path"):
            if props.get(k) not in (None, ""):
                raw = set_scalar(raw, k, props.get(k))
        if "prereq_raw" in props and props.get("prereq_raw") is not None:
            raw = set_raw_block(raw, "prerequisite", props.get("prereq_raw"))
        for key, bname in (("enable_equipments_raw", "enable_equipments"),
                           ("sub_technologies_raw", "sub_technologies"),
                           ("xor_raw", "xor"),
                           ("categories_raw", "categories"),
                           ("enable_subunits_raw", "enable_subunits")):
            if key in props and props.get(key) is not None:
                raw = set_raw_block(raw, bname, props.get(key))
    okv, msgv = validate_tech_script(raw, tid)
    if not okv:
        return False, msgv + "，未保存"
    new_text = text[:m.start()] + raw.strip() + "\n" + text[e:]
    snapshot(path)
    _atomic_write(path, new_text.encode("utf-8"))
    state.changed()[path] = rel_n
    ents = {}
    if name: ents.setdefault("simp_chinese", {})[tid] = name
    if desc: ents.setdefault("simp_chinese", {})[tid + "_desc"] = desc
    if name_ja: ents.setdefault("japanese", {})[tid] = name_ja
    if desc_ja: ents.setdefault("japanese", {})[tid + "_desc"] = desc_ja
    if name_en: ents.setdefault("english", {})[tid] = name_en
    if desc_en: ents.setdefault("english", {})[tid + "_desc"] = desc_en
    if ents:
        save_loc(top, ents)
    macros = {}
    for mm in re.finditer(r'(?m)^\s*@([A-Za-z0-9_]+)\s*=\s*(-?[0-9.]+)', strip_comments(new_text)):
        macros[mm.group(1)] = mm.group(2)
    rb = raw.find("{")
    re_idx = raw.rfind("}")
    tv = raw[rb + 1:re_idx] if (rb >= 0 and re_idx > rb) else raw
    src = os.path.basename((top or "").rstrip("\\/")) or (top or "")
    rel_os = rel_n.replace("/", os.sep)
    old_entry = state.techs().get(tid)
    entry = _build_tech_entry(tid, tv, rel_os, src, macros=macros)
    _sync_tech_relations(tid, old_entry, entry)
    return True, "科技已保存"



def add_tech(root, tid, folder, year="1936", x=0, y=0, parent_tech=None, as_root=False,
             name_zh="", desc_zh=""):
    if not re.match(r'^[A-Za-z0-9_]+$', tid or ""):
        return False, "科技 id 只能字母数字下划线"
    top = _writable_tech_top(root)
    if not top:
        return False, "找不到可写的 mod 目录"
    try:
        ix = int(round(float(x or 0)))
        iy = int(round(float(y or 0)))
    except Exception:
        ix, iy = 0, 0
    folder = folder or "custom_folder"
    d = os.path.join(top, "common", "technologies")
    os.makedirs(d, exist_ok=True)
    fn = unique_editor_filename(top, "common/technologies", "zz_focus_editor_technologies.txt")
    path = os.path.join(d, fn)
    text = io.open(path, encoding="utf-8-sig", errors="replace", newline="").read() if os.path.exists(path) else "technologies = {\n}\n"
    if re.search(r'(?m)^\s*%s\s*=\s*\{' % re.escape(tid), text):
        return False, "科技已存在"
    block = ("\t%s = {\n\t\tresearch_cost = 1\n\t\tstart_year = %s\n"
             "\t\tfolder = {\n\t\t\tname = %s\n\t\t\tposition = { x = %d y = %d }\n\t\t}\n\t}\n"
             % (tid, year, folder, ix, iy))
    tm = re.search(r'(?m)^\s*technologies\s*=\s*\{', text)
    if not tm:
        return False, "缺少 technologies = { ... } 根块"
    tb = text.find('{', tm.start())
    te = brace_match(text, tb)
    text = text[:te - 1] + block + text[te - 1:]
    snapshot(path)
    _atomic_write(path, text.encode("utf-8"))
    rel = os.path.join("common", "technologies", fn)
    state.changed()[path] = rel

    ents = {}
    if name_zh:
        ents.setdefault("simp_chinese", {})[tid] = str(name_zh)
    if desc_zh:
        ents.setdefault("simp_chinese", {})[tid + "_desc"] = str(desc_zh)
    if ents:
        save_loc(top, ents)

    ib = block.find("{")
    ie = block.rfind("}")
    tv = block[ib + 1:ie]
    src = os.path.basename((top or "").rstrip("\\/")) or (top or "")
    entry = _build_tech_entry(tid, tv, rel, src)
    _sync_tech_relations(tid, None, entry)

    if parent_tech:
        p_entry = state.techs().get(parent_tech)
        p_rel = (p_entry or {}).get("file") or rel
        tech_link(top, p_rel, parent_tech, tid, mode="path")
    elif as_root:
        from xuerong.model.tech_gui import tech_gridbox_register
        tech_gridbox_register(top, folder, tid)

    return True, "已新建科技 " + tid



def delete_tech(root, rel, tid):
    if not rel or not tid:
        return False, "参数不完整"
    path = os.path.join(root, rel) if root else ""
    if not path or not os.path.isfile(path):
        return False, "找不到文件：" + str(rel)
    text = io.open(path, encoding="utf-8-sig", errors="replace", newline="").read()
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(tid), text)
    if not m:
        return False, "未找到科技 " + tid
    b = text.find('{', m.start())
    e = brace_match(text, b)
    snapshot(path)
    _atomic_write(path, _bom_for(path) + (text[:m.start()] + text[e:]).encode("utf-8"))
    state.changed()[path] = rel
    techs = state.techs()
    techs.pop(tid, None)
    restored = False
    roots = list(state.roots() or [])
    if not roots and root:
        roots = [root]
    for r in reversed(roots):
        for base, d, fn in reversed(effective_layer_files("common/technologies", r)):
            fp = os.path.join(d, fn)
            try:
                raw = io.open(fp, encoding="utf-8-sig", errors="replace", newline="").read()
            except Exception:
                continue
            if tid not in raw:
                continue
            text_l = strip_comments(raw)
            macros = {}
            for mm in re.finditer(r'(?m)^\s*@([A-Za-z0-9_]+)\s*=\s*(-?[0-9.]+)', text_l):
                macros[mm.group(1)] = mm.group(2)
            found = None
            for _s, _e, body in find_blocks(text_l, "technologies"):
                for k, v, kb in top_items(body):
                    if not kb:
                        continue
                    if k == tid and _looks_tech(v):
                        found = v
                        break
                    if not _looks_tech(v):
                        for k2, v2, b2 in top_items(v):
                            if b2 and k2 == tid and _looks_tech(v2):
                                found = v2
                                break
                        if found is not None:
                            break
                if found is not None:
                    break
            if found is not None:
                src_l = os.path.basename((base or "").rstrip("\\/")) or base
                rel_l = os.path.join("common", "technologies", fn)
                entry = _build_tech_entry(tid, found, rel_l, src_l, macros=macros)
                entry["leads"] = [x for x in entry.get("leads", []) if x in techs and x != tid]
                pre = {p for p in entry.get("prereq", []) if p in techs and p != tid}
                for other_id, other in techs.items():
                    if other_id != tid and tid in (other.get("leads") or []):
                        pre.add(other_id)
                entry["prereq"] = sorted(pre)
                techs[tid] = entry
                restored = True
                break
        if restored:
            break
    if not restored:
        for other in techs.values():
            if tid in (other.get("leads") or []):
                other["leads"] = [x for x in other["leads"] if x != tid]
            if tid in (other.get("prereq") or []):
                other["prereq"] = [x for x in other["prereq"] if x != tid]
    return True, "已删除科技 " + tid



def _fmt_coeff(coeff):
    try:
        fc = float(coeff)
        return str(int(fc)) if fc.is_integer() else str(fc)
    except Exception:
        return "1"


def _edit_xor_in_file(root, rel, tid, peer_id, add=True):
    """在 tid 所在文件内添加或删除 xor 中的 peer_id（单文件接管 + 无 BOM）。"""
    top, path, rel_n, err = _ensure_tech_file_writable(root, rel, tid=tid)
    if not path:
        return False, None, None, "", err
    text = io.open(path, encoding="utf-8-sig", errors="replace", newline="").read()
    loc = _tech_block_range(text, tid)
    if not loc:
        return False, None, None, "", "未找到科技 " + tid
    b, e = loc
    block = text[b + 1:e - 1]
    clean_blk = _strip_keep_len(block)
    xm = re.search(r'(?m)^[ \t]*xor\s*=\s*\{', clean_blk)
    if add:
        if xm:
            xb = block.find('{', xm.start())
            xe = brace_match(clean_blk, xb)
            xinner = block[xb + 1:xe - 1]
            existing = re.findall(r'[A-Za-z][A-Za-z0-9_]*', strip_comments(xinner))
            if peer_id in existing:
                return True, top, path, rel_n, ""
            nb = block[:xe - 1].rstrip() + "\n\t\t\t%s\n\t\t" % peer_id + block[xe - 1:]
        else:
            nb = block.rstrip() + "\n\t\txor = {\n\t\t\t%s\n\t\t}\n\t" % peer_id
    else:
        if not xm:
            return True, top, path, rel_n, ""
        xb = block.find('{', xm.start())
        xe = brace_match(clean_blk, xb)
        xinner = block[xb + 1:xe - 1]
        xinner2 = re.sub(r'(?m)^[ \t]*%s[ \t]*\r?\n?' % re.escape(peer_id), '', xinner)
        if xinner2 == xinner:
            xinner2 = re.sub(r'\b%s\b' % re.escape(peer_id), '', xinner)
        rem = re.findall(r'[A-Za-z][A-Za-z0-9_]*', strip_comments(xinner2))
        if not rem:
            nb = block[:xm.start()].rstrip() + "\n\t" + block[xe:].lstrip("\r\n")
        else:
            nb = block[:xb + 1] + xinner2 + block[xe - 1:]

    new_text = text[:b + 1] + nb + text[e - 1:]
    if not braces_balanced(new_text):
        return False, None, None, "", "xor 编辑后括号不平衡"
    snapshot(path)
    _atomic_write(path, new_text.encode("utf-8"))
    state.changed()[path] = rel_n
    _refresh_tech_in_state(top, path, rel_n, tid, full_text=new_text)
    return True, top, path, rel_n, ""


def tech_link(root, rel, src, dst, mode="path", coeff=1):
    """连接两项科技：mode='path' 插入独立 path 块，mode='xor' 双向写 xor 互斥；增量刷新 state。"""
    if not src or not dst:
        return False, "参数不完整"
    if src == dst:
        return False, "不能连接自身"
    mode = (mode or "path").strip().lower()
    if mode not in ("path", "xor"):
        return False, "不支持的连接模式：" + mode

    if mode == "xor":
        src_rel = rel or (state.techs().get(src) or {}).get("file") or ""
        dst_rel = (state.techs().get(dst) or {}).get("file") or src_rel
        ok1, top1, _p1, _r1, err1 = _edit_xor_in_file(root, src_rel, src, dst, add=True)
        if not ok1:
            return False, err1
        ok2, _top2, _p2, _r2, err2 = _edit_xor_in_file(top1 or root, dst_rel, dst, src, add=True)
        if not ok2:
            return False, err2
        return True, "已添加互斥：%s ↔ %s" % (src, dst)

    top, path, rel_n, err = _ensure_tech_file_writable(root, rel, tid=src)
    if not path:
        return False, err
    text = io.open(path, encoding="utf-8-sig", errors="replace", newline="").read()
    loc = _tech_block_range(text, src)
    if not loc:
        return False, "未找到源科技 " + src
    b, e = loc
    block = text[b + 1:e - 1]
    clean_blk = strip_comments(block)
    if re.search(r'leads_to_tech\s*=\s*"?%s"?' % re.escape(dst), clean_blk):
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

    coeff_s = _fmt_coeff(coeff)
    new_path_block = "\n\t\tpath = {\n\t\t\tleads_to_tech = %s\n\t\t\tresearch_cost_coeff = %s\n\t\t}" % (dst, coeff_s)
    # 插入独立 path = { ... } 块：若有已有 path 块则放在最后一个之后，否则放在末尾
    clean_keep = _strip_keep_len(block)
    last_pe = None
    for pm in re.finditer(r'(?m)^[ \t]*path\s*=\s*\{', clean_keep):
        pb = block.find('{', pm.start())
        last_pe = brace_match(clean_keep, pb)
    if last_pe is not None:
        nb = block[:last_pe] + new_path_block + block[last_pe:]
    else:
        nb = block.rstrip() + new_path_block + "\n\t"

    new_text = text[:b + 1] + nb + text[e - 1:]
    if not braces_balanced(new_text):
        return False, "添加前置后括号不平衡"
    snapshot(path)
    _atomic_write(path, new_text.encode("utf-8"))
    state.changed()[path] = rel_n
    _refresh_tech_in_state(top, path, rel_n, src, full_text=new_text)
    return True, "已添加前置：%s → %s" % (src, dst)


def tech_unlink(root, rel, src, dst, mode="path"):
    """断开两项科技连线：mode='path' 删除匹配 leads_to_tech 的 path 块，mode='xor' 双向移除互斥。"""
    if not src or not dst:
        return False, "参数不完整"
    mode = (mode or "path").strip().lower()
    if mode not in ("path", "xor"):
        return False, "不支持的连接模式：" + mode

    if mode == "xor":
        src_rel = rel or (state.techs().get(src) or {}).get("file") or ""
        dst_rel = (state.techs().get(dst) or {}).get("file") or src_rel
        ok1, top1, _p1, _r1, err1 = _edit_xor_in_file(root, src_rel, src, dst, add=False)
        if not ok1:
            return False, err1
        ok2, _top2, _p2, _r2, err2 = _edit_xor_in_file(top1 or root, dst_rel, dst, src, add=False)
        if not ok2:
            return False, err2
        return True, "已移除互斥：%s ↔ %s" % (src, dst)

    top, path, rel_n, err = _ensure_tech_file_writable(root, rel, tid=src)
    if not path:
        return False, err
    text = io.open(path, encoding="utf-8-sig", errors="replace", newline="").read()
    loc = _tech_block_range(text, src)
    if not loc:
        return False, "未找到源科技 " + src
    b, e = loc
    block = text[b + 1:e - 1]
    clean_keep = _strip_keep_len(block)

    pat_dst = re.compile(r'leads_to_tech\s*=\s*"?%s"?\b' % re.escape(dst))
    nb = None
    for pm in re.finditer(r'(?m)^[ \t]*path\s*=\s*\{', clean_keep):
        pb = block.find('{', pm.start())
        pe = brace_match(clean_keep, pb)
        p_clean = clean_keep[pb + 1:pe - 1]
        if pat_dst.search(p_clean):
            all_leads = re.findall(r'leads_to_tech\s*=\s*"?([A-Za-z0-9_]+)"?', p_clean)
            if len(all_leads) <= 1:
                tail = block[pe:].lstrip("\r\n")
                if tail.strip():
                    nb = block[:pm.start()].rstrip() + "\n" + tail
                else:
                    nb = block[:pm.start()].rstrip() + "\n\t"
            else:
                p_raw = block[pb + 1:pe - 1]
                p_raw2 = re.sub(r'(?m)^[ \t]*leads_to_tech\s*=\s*"?%s"?[ \t]*\r?\n?' % re.escape(dst), '', p_raw)
                nb = block[:pb + 1] + p_raw2 + block[pe - 1:]
            break

    if nb is None:
        return False, "未找到前置连接：%s → %s" % (src, dst)
    new_text = text[:b + 1] + nb + text[e - 1:]
    if not braces_balanced(new_text):
        return False, "移除前置后括号不平衡"
    snapshot(path)
    _atomic_write(path, new_text.encode("utf-8"))
    state.changed()[path] = rel_n
    _refresh_tech_in_state(top, path, rel_n, src, full_text=new_text)
    return True, "已移除前置：%s → %s" % (src, dst)
