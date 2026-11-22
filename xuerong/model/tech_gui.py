# -*- coding: utf-8 -*-
"""科技树工作台（Tech Tree Studio）GUI 与 technology_tags 读写引擎。

负责：
  · common/technology_tags/*.txt 读写（technology_folders / technology_categories）
  · interface/countrytechtreeview.gui 解析与精细编辑（tabs / pages / years / subtitles / gridboxes / item skins）
  · tech_studio_payload 聚合视图与实时诊断（invisible_roots / overlaps / missing_cats / missing_gfx）

硬规则：
  · 仅允许 import 标准库、xuerong.state、xuerong.core.*、xuerong.model.{history,loc,country}
  · 绝不得 import focus_editor 或 xuerong.api.*
  · 非 .yml 文件一律写无 BOM UTF-8，且禁止整目录 replace_path，只做单文件接管
"""
import io
import os
import re
import shutil
from collections import deque

from xuerong import state
from xuerong.core import gfx, paths
from xuerong.core.paths import (
    _chain_layers, _layers_find, effective_layer_files,
    is_readonly_mod, is_under_game, mod_layers,
)
from xuerong.core.text import (
    _atomic_write, _first, _strip_keep_len,
    brace_match, braces_balanced, find_blocks, strip_comments, top_items,
)
from xuerong.model.history import snapshot
from xuerong.model.loc import save_loc


_GUI_REL = "interface/countrytechtreeview.gui"
_TAGS_REL = "common/technology_tags/00_technology.txt"
_TAB_STEP_X = 89
_TAB_START_X = 22


# ------------------------------------------------------------------ 单文件接管辅助

def _writable_top(root=None):
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


def _ensure_rel_writable(root, rel):
    """确保 rel 在可写链顶存在；若缺失则从叠加链复制单文件（绝不写 replace_path）。

    返回 (top, dst_abs_path, err_msg)。
    """
    rel_n = (rel or "").replace("\\", "/").lstrip("/")
    top = _writable_top(root)
    if not top:
        return None, None, "找不到可写的 mod 目录"
    dst = os.path.join(top, rel_n.replace("/", os.sep))
    if os.path.isfile(dst):
        return top, dst, ""
    layers = mod_layers(top) or [top]
    src, _src_root = _layers_find(rel_n, layers)
    if not src or not os.path.isfile(src):
        return top, None, "叠加链中找不到文件：" + rel_n
    os.makedirs(os.path.dirname(dst) or top, exist_ok=True)
    text = io.open(src, encoding="utf-8-sig", errors="replace").read()
    _atomic_write(dst, text.encode("utf-8"))
    return top, dst, ""


def _effective_layers(root=None):
    """返回当前生效的叠加链（由底到顶）。"""
    picked = paths._pick(root)
    if picked:
        lay = _chain_layers(picked)
        if lay:
            return lay
    for r in (state.roots() or []):
        lay = _chain_layers(r)
        if lay:
            return lay
    if state.game():
        return [os.path.abspath(state.game())]
    return []


# ------------------------------------------------------------------ 通用块扫描辅助

def _iter_child_blocks(raw_text, clean_text=None):
    """只扫描当前层级的直接子块，返回 [(key, start, end, inner_start, inner_end)]。"""
    if clean_text is None:
        clean_text = _strip_keep_len(raw_text)
    out = []
    i = 0
    n = len(clean_text)
    while i < n:
        ch = clean_text[i]
        if ch in " \t\r\n":
            i += 1
            continue
        m = re.match(r'([A-Za-z0-9_.\-]+)\s*=\s*', clean_text[i:])
        if not m:
            i += 1
            continue
        key = m.group(1)
        j = i + m.end()
        if j < n and clean_text[j] == '{':
            end = brace_match(clean_text, j)
            out.append((key, i, end, j + 1, end - 1))
            i = end
        else:
            k = j
            instr = False
            while k < n:
                c = clean_text[k]
                if c == '"':
                    instr = not instr
                elif c == '\n' and not instr:
                    break
                k += 1
            i = k
    return out


def _block_body_range(block_text):
    """给定单个 `key = { ... }` 块文本，返回花括号内部范围 `(body_start, body_end)`。"""
    ib = block_text.find("{")
    ie = block_text.rfind("}")
    if ib < 0 or ie <= ib:
        return 0, len(block_text)
    return ib + 1, ie


def _iter_block_children(block_text, clean_text=None):
    """遍历单个外层块 `{ ... }` 内部的直接子块，返回基于 `block_text` 的偏移。"""
    bs, be = _block_body_range(block_text)
    sub_raw = block_text[bs:be]
    sub_clean = (clean_text[bs:be] if clean_text is not None else _strip_keep_len(sub_raw))
    for k, s, e, is_s, is_e in _iter_child_blocks(sub_raw, sub_clean):
        yield k, bs + s, bs + e, bs + is_s, bs + is_e


def _unq(s):
    s = (s or "").strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def _block_scalar(clean_body, key):
    m = re.search(r'(?mi)^[ \t]*%s[ \t]*=[ \t]*("[^"]*"|[^\s#\}]+)' % re.escape(key), clean_body)
    return _unq(m.group(1)) if m else ""


def _parse_xy(clean_body, key="position"):
    """解析 position = { x = ... y = ... }，返回 (x_raw, y_raw)。"""
    for k, _s, _e, is_s, is_e in _iter_child_blocks(clean_body, clean_body):
        if k.lower() == key.lower():
            inner = clean_body[is_s:is_e]
            mx = re.search(r'(?i)(?:^|[\s{])x\s*=\s*([^\s\}#]+)', inner)
            my = re.search(r'(?i)(?:^|[\s{])y\s*=\s*([^\s\}#]+)', inner)
            return (_unq(mx.group(1)) if mx else "0"), (_unq(my.group(1)) if my else "0")
    return None, None


def _parse_wh(clean_body, key="size"):
    """解析 size / slotsize = { width = ... height = ... }，返回 (w_raw, h_raw)。"""
    for k, _s, _e, is_s, is_e in _iter_child_blocks(clean_body, clean_body):
        if k.lower() == key.lower():
            inner = clean_body[is_s:is_e]
            # 去掉嵌套 min = { ... } 等子块后再匹配直接属性
            stripped = re.sub(r'[A-Za-z0-9_]+\s*=\s*\{[^{}]*\}', '', inner)
            mw = re.search(r'(?i)(?:^|\s)(?:width|x)\s*=\s*([^\s\}#]+)', stripped)
            mh = re.search(r'(?i)(?:^|\s)(?:height|y)\s*=\s*([^\s\}#]+)', stripped)
            return (_unq(mw.group(1)) if mw else ""), (_unq(mh.group(1)) if mh else "")
    return "", ""


def _to_int(val, default=0):
    try:
        return int(round(float(str(val).strip())))
    except Exception:
        return default


def _resolve_coord(raw_val, total_span, default=0):
    s = str(raw_val or "").strip()
    if not s:
        return default
    if s.endswith("%"):
        try:
            pct = float(s.rstrip("%").strip())
            return int(round(total_span * pct / 100.0))
        except Exception:
            return default
    return _to_int(s, default)


# ------------------------------------------------------------------ 读解析：technology_tags

def _loc_resolve(key, loc_map=None):
    loc_map = loc_map if loc_map is not None else (state.loc() or {})
    val = loc_map.get(key, key)
    for _ in range(3):
        if not isinstance(val, str) or "$" not in val:
            break
        nxt = re.sub(r'\$([A-Za-z0-9_.\-]+)\$', lambda m: loc_map.get(m.group(1), m.group(1)), val)
        if nxt == val:
            break
        val = nxt
    return val


def load_technology_tags(root=None):
    """解析叠加链中有效的 technology_folders 与 technology_categories。"""
    root = paths._pick(root)
    loc_map = state.loc() or {}
    folders_map = {}
    folder_order = []
    categories = []
    cat_seen = set()

    files = effective_layer_files("common/technology_tags", root)
    for base, d, fn in files:
        rel = os.path.join("common", "technology_tags", fn).replace("\\", "/")
        src = os.path.basename((base or "").rstrip("\\/")) or (base or "")
        fp = os.path.join(d, fn)
        try:
            text = strip_comments(io.open(fp, encoding="utf-8-sig", errors="replace").read())
        except Exception:
            continue

        for _s, _e, body in find_blocks(text, "technology_folders"):
            for fid, fbody, is_blk in top_items(body):
                if not fid:
                    continue
                if fid not in folders_map:
                    folder_order.append(fid)
                ledger = ""
                doctrine = False
                available_raw = ""
                if is_blk:
                    ledger = _first(fbody, r'(?m)^\s*ledger\s*=\s*"?([A-Za-z0-9_]+)"?', "")
                    doctrine = bool(re.search(r'(?m)^\s*doctrine\s*=\s*yes\b', fbody))
                    av_blocks = find_blocks(fbody, "available")
                    if av_blocks:
                        available_raw = av_blocks[0][2].strip()
                folders_map[fid] = {
                    "id": fid,
                    "name": _loc_resolve(fid, loc_map),
                    "ledger": ledger,
                    "doctrine": doctrine,
                    "available_raw": available_raw,
                    "file": rel,
                    "source": src,
                }

        for _s, _e, body in find_blocks(text, "technology_categories"):
            for cid in re.findall(r'[A-Za-z][A-Za-z0-9_]*', body):
                if cid not in cat_seen:
                    cat_seen.add(cid)
                    categories.append({"id": cid, "name": _loc_resolve(cid, loc_map)})

    folders = [folders_map[fid] for fid in folder_order]
    return {"ok": True, "folders": folders, "categories": categories}


# ------------------------------------------------------------------ 读解析：countrytechtreeview.gui

def _parse_item_skin(clean_body):
    """解析 techtree_<folder>_item / _small_item 节点皮肤。"""
    w_raw, h_raw = _parse_wh(clean_body, "size")
    x_raw, y_raw = _parse_xy(clean_body, "position")
    bg_sprite = ""
    for k, _s, _e, is_s, is_e in _iter_child_blocks(clean_body, clean_body):
        if k.lower() == "background":
            sub = clean_body[is_s:is_e]
            bg_sprite = _block_scalar(sub, "quadTextureSprite") or _block_scalar(sub, "spriteType")
            if bg_sprite:
                break
    return {
        "width": _to_int(w_raw, 0),
        "height": _to_int(h_raw, 0),
        "x": _to_int(x_raw, 0),
        "y": _to_int(y_raw, 0),
        "bg_sprite": bg_sprite,
    }


def _container_offset(clean_body, parent_w, parent_h):
    """计算嵌套子容器相对页容器的坐标偏移 (ox, oy) 及自身尺寸 (cw, ch)。"""
    x_raw, y_raw = _parse_xy(clean_body, "position")
    w_raw, h_raw = _parse_wh(clean_body, "size")
    ox = _resolve_coord(x_raw, parent_w, 0) if x_raw is not None else 0
    oy = _resolve_coord(y_raw, parent_h, 0) if y_raw is not None else 0
    cw = _resolve_coord(w_raw, parent_w, parent_w) if w_raw else parent_w
    ch = _resolve_coord(h_raw, parent_h, parent_h) if h_raw else parent_h
    ori = (_block_scalar(clean_body, "orientation") or "").lower()
    origo = (_block_scalar(clean_body, "origo") or "").lower()
    if "right" in ori:
        ox = parent_w + ox
    elif "center" in ori:
        ox = (parent_w // 2) + ox
        if "center" in origo:
            ox -= cw // 2
    if "bottom" in ori:
        oy = parent_h + oy
    elif ori == "center":
        oy = (parent_h // 2) + oy
        if "center" in origo:
            oy -= ch // 2
    return ox, oy, cw, ch


def _scan_page_elements(clean_text, rel_start, rel_end, ox, oy, pw, ph, container_name,
                        stripes_info, bgs, years, subtitles, gridboxes):
    """递归解析页面 containerWindowType 内的背景、年份、标题、gridboxtype。"""
    sub = clean_text[rel_start:rel_end]
    for k, _s, _e, is_s, is_e in _iter_child_blocks(sub, sub):
        kl = k.lower()
        cbody = sub[is_s:is_e]
        if kl == "containerwindowtype":
            cname = _block_scalar(cbody, "name")
            cox, coy, ccw, cch = _container_offset(cbody, pw, ph)
            if cname in ("techtree_stripes", "size_filler"):
                w_raw, h_raw = _parse_wh(cbody, "size")
                sw = _to_int(w_raw, 0)
                sh = _to_int(h_raw, 0)
                if sw > 0:
                    stripes_info["w"] = sw
                    ccw = sw
                if sh > 0:
                    stripes_info["h"] = sh
                    cch = sh
            _scan_page_elements(
                sub, is_s, is_e,
                ox + cox, oy + coy, ccw, cch,
                cname or container_name,
                stripes_info, bgs, years, subtitles, gridboxes,
            )
        elif kl == "icontype":
            iname = _block_scalar(cbody, "name")
            spr = _block_scalar(cbody, "spriteType") or _block_scalar(cbody, "quadTextureSprite")
            nl = iname.lower()
            sl = spr.lower()
            if ("techtree_bg" in nl or "techtree_bg" in sl or
                    (("_bg" in nl or "_bg" in sl) and "highlight" not in nl and "unavailable" not in sl)):
                x_raw, y_raw = _parse_xy(cbody, "position")
                bgs.append({
                    "name": iname,
                    "sprite": spr,
                    "x": ox + (_resolve_coord(x_raw, pw, 0) if x_raw is not None else 0),
                    "y": oy + (_resolve_coord(y_raw, ph, 0) if y_raw is not None else 0),
                })
        elif kl == "instanttextboxtype":
            tname = _block_scalar(cbody, "name")
            tval = _block_scalar(cbody, "text")
            x_raw, y_raw = _parse_xy(cbody, "position")
            lx = _resolve_coord(x_raw, pw, 0) if x_raw is not None else 0
            ly = _resolve_coord(y_raw, ph, 0) if y_raw is not None else 0
            px = ox + lx
            py = oy + ly
            font = _block_scalar(cbody, "font")
            mw = _to_int(_block_scalar(cbody, "maxWidth"), 0)
            mh = _to_int(_block_scalar(cbody, "maxHeight"), 0)
            fmt = _block_scalar(cbody, "format")
            if re.match(r'^\d{4}$', tval):
                years.append({
                    "name": tname,
                    "text": tval,
                    "x": px,
                    "y": py,
                    "local_x": lx,
                    "local_y": ly,
                    "ox": ox,
                    "oy": oy,
                    "container": container_name,
                    "font": font,
                    "maxWidth": mw,
                    "maxHeight": mh,
                    "format": fmt,
                })
            elif tval or "subtitle" in tname.lower() or "title" in tname.lower():
                subtitles.append({
                    "name": tname,
                    "text": tval,
                    "loc_text": state.loc().get(tval, tval),
                    "x": px,
                    "y": py,
                    "local_x": lx,
                    "local_y": ly,
                    "ox": ox,
                    "oy": oy,
                    "container": container_name,
                    "font": font,
                    "maxWidth": mw,
                    "maxHeight": mh,
                    "format": fmt,
                })
        elif kl == "gridboxtype":
            gname = _block_scalar(cbody, "name")
            if gname == "special_project_specialization_list":
                continue
            x_raw, y_raw = _parse_xy(cbody, "position")
            if x_raw is None and y_raw is None:
                continue
            sw_raw, sh_raw = _parse_wh(cbody, "slotsize")
            bw_raw, bh_raw = _parse_wh(cbody, "size")
            gfmt = _block_scalar(cbody, "format") or "LEFT"
            gori = _block_scalar(cbody, "orientation") or "UPPER_LEFT"
            root_tech = gname[:-5] if gname.endswith("_tree") else gname
            gridboxes.append({
                "name": gname,
                "root_tech": root_tech,
                "x_raw": x_raw or "0",
                "y_raw": y_raw or "0",
                "x": ox + _resolve_coord(x_raw, stripes_info["w"], 0),
                "y": oy + _resolve_coord(y_raw, stripes_info["h"], 0),
                "size_w_raw": bw_raw,
                "size_h_raw": bh_raw,
                "slot_w": _to_int(sw_raw, 70) or 70,
                "slot_h": _to_int(sh_raw, 70) or 70,
                "format": gfmt,
                "orientation": gori,
            })


def load_techtree_gui(root=None):
    """解析当前叠加链生效的 interface/countrytechtreeview.gui。"""
    layers = _effective_layers(root)
    gui_path, src_root = _layers_find(_GUI_REL, layers)
    if not gui_path or not os.path.isfile(gui_path):
        return {
            "ok": False,
            "file": _GUI_REL,
            "source": "",
            "tabs": [],
            "pages": {},
            "items": {},
            "msg": "找不到 interface/countrytechtreeview.gui",
        }
    src = os.path.basename((src_root or "").rstrip("\\/")) or (src_root or "")
    raw = io.open(gui_path, encoding="utf-8-sig", errors="replace").read()
    clean = _strip_keep_len(raw)

    tabs = []
    pages = {}
    items = {}

    # 扫描 guiTypes 下全部顶层块（含 countrytechtreeview 与节点皮肤 techtree_*_item）
    gui_bodies = find_blocks(clean, "guiTypes")
    top_containers = []
    if gui_bodies:
        gs, ge, _gb = gui_bodies[0]
        inner_clean = clean[gs + 1:ge - 1]
        for k, _s, _e, is_s, is_e in _iter_child_blocks(inner_clean, inner_clean):
            if k.lower() == "containerwindowtype":
                top_containers.append((inner_clean, is_s, is_e))
    else:
        for k, _s, _e, is_s, is_e in _iter_child_blocks(search_text, search_text):
            if k.lower() == "containerwindowtype":
                top_containers.append((search_text, is_s, is_e))

    main_tv = None
    for buf, is_s, is_e in top_containers:
        cbody = buf[is_s:is_e]
        cname = _block_scalar(cbody, "name")
        if cname == "countrytechtreeview":
            main_tv = (buf, is_s, is_e)
        elif cname.startswith("techtree_") and (cname.endswith("_item") or cname.endswith("_small_item")):
            items[cname] = _parse_item_skin(cbody)

    if main_tv:
        buf, tv_s, tv_e = main_tv
        tv_sub = buf[tv_s:tv_e]
        for k, _s, _e, is_s, is_e in _iter_child_blocks(tv_sub, tv_sub):
            if k.lower() != "containerwindowtype":
                continue
            pbody = tv_sub[is_s:is_e]
            pname = _block_scalar(pbody, "name")
            if not pname:
                continue
            if pname == "folder_tabs":
                for bk, _bs, _be, bis_s, bis_e in _iter_child_blocks(pbody, pbody):
                    if bk.lower() != "buttontype":
                        continue
                    bbody = pbody[bis_s:bis_e]
                    bname = _block_scalar(bbody, "name")
                    spr = _block_scalar(bbody, "quadTextureSprite") or _block_scalar(bbody, "spriteType")
                    bx_raw, by_raw = _parse_xy(bbody, "position")
                    cs = _block_scalar(bbody, "clicksound")
                    tabs.append({
                        "name": bname,
                        "folder": bname[:-4] if bname.endswith("_tab") else bname,
                        "sprite": spr,
                        "x": _to_int(bx_raw, 0),
                        "y": _to_int(by_raw, 0),
                        "clicksound": cs,
                    })
                continue

            stripes_info = {"w": 1400, "h": 1275}
            bgs = []
            years = []
            subtitles = []
            gridboxes = []
            _scan_page_elements(
                tv_sub, is_s, is_e,
                0, 0, stripes_info["w"], stripes_info["h"], "",
                stripes_info, bgs, years, subtitles, gridboxes,
            )
            # 若存在带 % 的 gridbox，使用最终 stripes_w / stripes_h 重算一次百分比坐标
            sw_fin = stripes_info["w"]
            sh_fin = stripes_info["h"]
            for gb in gridboxes:
                if str(gb.get("x_raw") or "").endswith("%"):
                    gb["x"] = _resolve_coord(gb["x_raw"], sw_fin, 0)
                if str(gb.get("y_raw") or "").endswith("%"):
                    gb["y"] = _resolve_coord(gb["y_raw"], sh_fin, 0)

            primary_bg = bgs[0] if bgs else {"sprite": "", "x": 0, "y": 0}
            pages[pname] = {
                "stripes_w": sw_fin,
                "stripes_h": sh_fin,
                "bg_sprite": primary_bg.get("sprite", ""),
                "bg_pos": {"x": primary_bg.get("x", 0), "y": primary_bg.get("y", 0)},
                "bgs": bgs,
                "years": years,
                "subtitles": subtitles,
                "gridboxes": gridboxes,
            }

    # 把节点皮肤关联到每个 page
    for pname, pinfo in pages.items():
        pinfo["item_style"] = items.get("techtree_%s_item" % pname)
        pinfo["small_item_style"] = items.get("techtree_%s_small_item" % pname)

    return {
        "ok": True,
        "file": _GUI_REL,
        "source": src,
        "tabs": tabs,
        "pages": pages,
        "items": items,
    }


# ------------------------------------------------------------------ 聚合载荷与像素换算

def _gridbox_pixel_pos(gb, fx, fy, stripes_w):
    """按 gridbox format 与 slotsize 换算节点在页面上的真实像素坐标 (px, py)。"""
    fmt = (gb.get("format") or "LEFT").upper()
    gx = gb.get("x", 0)
    gy = gb.get("y", 0)
    sw = gb.get("slot_w", 70) or 70
    sh = gb.get("slot_h", 70) or 70

    # gwtank_tree 类: position={x=10% y=172}, size={width=80% ...}, format=UP
    base_x = gx
    bw_raw = str(gb.get("size_w_raw") or "").strip()
    if fmt in ("UP", "DOWN") and bw_raw.endswith("%"):
        bw = _resolve_coord(bw_raw, stripes_w, 0)
        base_x = gx + (bw // 2)

    if fmt == "LEFT":
        return int(round(gx + fy * sw)), int(round(gy + fx * sh))
    if fmt == "RIGHT":
        return int(round(gx - fy * sw)), int(round(gy + fx * sh))
    if fmt == "DOWN":
        return int(round(base_x + fx * sw)), int(round(gy - fy * sh))
    # UP / UPPER_LEFT 等纵向时间轴
    return int(round(base_x + fx * sw)), int(round(gy + fy * sh))


def _collect_folder_macros(root, folder_techs):
    """读取当前 folder 相关科技文件顶部的 @macro = val。"""
    macros = {}
    rels = sorted({t.get("file") for t in folder_techs.values() if t.get("file")})
    layers = _effective_layers(root)
    for rel in rels:
        p, _src = _layers_find(rel, layers)
        if not p or not os.path.isfile(p):
            continue
        try:
            text = strip_comments(io.open(p, encoding="utf-8-sig", errors="replace").read())
            for mm in re.finditer(r'(?m)^\s*@([A-Za-z0-9_]+)\s*=\s*(-?[0-9.]+)', text):
                macros[mm.group(1)] = mm.group(2)
        except Exception:
            pass
    return macros


def tech_studio_payload(root=None, folder=None, tag=None):
    """聚合科技树工作台完整视图与实时诊断。"""
    root = paths._pick(root)
    tags_info = load_technology_tags(root)
    gui_info = load_techtree_gui(root)

    techs = state.techs() or {}
    sprites = state.sprite_map() or gfx.SPRITE_MAP

    # 统计各 folder 科技数及孤儿 folder
    counts = {}
    for t in techs.values():
        fp = (t.get("path") or "").strip()
        if fp:
            counts[fp] = counts.get(fp, 0) + 1

    tab_by_folder = {}
    for tb in gui_info.get("tabs") or []:
        f_id = tb.get("folder") or ""
        if f_id and f_id not in tab_by_folder:
            tab_by_folder[f_id] = tb

    folders = []
    known_fids = set()
    for f in tags_info.get("folders") or []:
        fid = f["id"]
        known_fids.add(fid)
        tb = tab_by_folder.get(fid) or {}
        tab_spr = tb.get("sprite", "") or ("GFX_%s_tab" % fid)
        folders.append({
            **f,
            "registered": True,
            "has_gui": fid in (gui_info.get("pages") or {}),
            "tab_sprite": tb.get("sprite", ""),
            "tab_icon_url": ("/api/icon?gfx=" + tab_spr) if tab_spr in sprites else "",
            "tab_x": tb.get("x"),
            "tab_y": tb.get("y"),
            "tech_count": counts.get(fid, 0),
        })

    for fid in sorted(counts):
        if fid in known_fids or fid == "其他":
            continue
        tb = tab_by_folder.get(fid) or {}
        tab_spr = tb.get("sprite", "") or ("GFX_%s_tab" % fid)
        folders.append({
            "id": fid,
            "name": state.loc().get(fid, fid),
            "ledger": "",
            "doctrine": False,
            "available_raw": "",
            "file": "",
            "source": "",
            "registered": False,
            "has_gui": fid in (gui_info.get("pages") or {}),
            "tab_sprite": tb.get("sprite", ""),
            "tab_icon_url": ("/api/icon?gfx=" + tab_spr) if tab_spr in sprites else "",
            "tab_x": tb.get("x"),
            "tab_y": tb.get("y"),
            "tech_count": counts.get(fid, 0),
        })

    cur_folder = (folder or "").strip()
    if not cur_folder:
        if any(f["id"] == "infantry_folder" for f in folders):
            cur_folder = "infantry_folder"
        elif folders:
            cur_folder = folders[0]["id"]

    page = dict((gui_info.get("pages") or {}).get(cur_folder) or {})
    if not page:
        page = {
            "stripes_w": 1400,
            "stripes_h": 1275,
            "bg_sprite": "",
            "bg_pos": {"x": 0, "y": 0},
            "bgs": [],
            "years": [],
            "subtitles": [],
            "gridboxes": [],
            "item_style": (gui_info.get("items") or {}).get("techtree_%s_item" % cur_folder),
            "small_item_style": (gui_info.get("items") or {}).get("techtree_%s_small_item" % cur_folder),
        }
    bg_spr = page.get("bg_sprite") or ""
    page["bg_url"] = ("/api/icon?gfx=" + bg_spr + "&full=1") if (bg_spr and bg_spr in sprites) else ""

    cur_techs = {tid: t for tid, t in techs.items() if (t.get("path") or "") == cur_folder}

    # 从每个 gridbox 的 root_tech 沿 leads BFS 推导归属，并标记空孤立根树框
    tech_to_gb = {}
    gridboxes = [dict(gb, orphan=bool((gb.get("root_tech") or "") and (gb.get("root_tech") not in techs)))
                 for gb in (page.get("gridboxes") or [])]
    page["gridboxes"] = gridboxes
    orphan_gridboxes = [{"name": gb["name"], "root_tech": gb.get("root_tech") or ""}
                        for gb in gridboxes if gb.get("orphan")]
    for gb in gridboxes:
        rtech = gb.get("root_tech") or ""
        if rtech not in cur_techs:
            continue
        q = deque([rtech])
        while q:
            cur = q.popleft()
            if cur in tech_to_gb:
                continue
            tech_to_gb[cur] = gb
            for ch in (cur_techs[cur].get("leads") or []):
                if ch in cur_techs and ch not in tech_to_gb:
                    q.append(ch)

    stripes_w = page.get("stripes_w") or 1400
    nodes = []
    pos_buckets = {}
    invisible_roots = []
    missing_cats = []
    missing_gfx = []
    valid_cats = {c["id"] for c in (tags_info.get("categories") or [])}

    for tid, t in cur_techs.items():
        fx = t.get("fx")
        fy = t.get("fy")
        gb = tech_to_gb.get(tid)
        visible_in_game = bool(gb) and (fx is not None and fy is not None)
        if gb and fx is not None and fy is not None:
            px, py = _gridbox_pixel_pos(gb, float(fx), float(fy), stripes_w)
        else:
            px, py = None, None

        icon_gfx = t.get("icon") or ""
        if not icon_gfx:
            cand_m = "GFX_%s_medium" % tid
            cand_b = "GFX_%s" % tid
            if cand_m in sprites:
                icon_gfx = cand_m
            elif cand_b in sprites:
                icon_gfx = cand_b
        icon_ok = bool(icon_gfx and icon_gfx in sprites)
        if not icon_ok:
            missing_gfx.append({"tid": tid, "expected": "GFX_%s_medium" % tid})

        for c in (t.get("categories") or []):
            if valid_cats and c not in valid_cats:
                missing_cats.append({"tid": tid, "category": c})

        if not visible_in_game:
            same_page_pre = [p for p in (t.get("prereq") or []) if p in cur_techs]
            if not same_page_pre:
                invisible_roots.append({
                    "tid": tid,
                    "name": t.get("name") or tid,
                    "reason": "no_gridbox" if not gb else "missing_coords",
                })
        elif px is not None and py is not None:
            pos_buckets.setdefault((px, py), []).append(tid)

        nodes.append({
            "id": tid,
            "name": t.get("name") or tid,
            "year": t.get("year") or "",
            "cost": t.get("cost") or "",
            "fx": fx,
            "fy": fy,
            "px": px,
            "py": py,
            "gridbox": gb["name"] if gb else "",
            "visible_in_game": visible_in_game,
            "file": t.get("file") or "",
            "source": t.get("source") or "",
            "icon_gfx": icon_gfx,
            "icon_url": ("/api/icon?gfx=" + icon_gfx) if icon_ok else "",
            "prereq": list(t.get("prereq") or []),
            "leads": list(t.get("leads") or []),
            "xor": list(t.get("xor") or []),
            "categories": list(t.get("categories") or []),
            "enable_equipments": list(t.get("enable_equipments") or []),
            "enable_subunits": list(t.get("enable_subunits") or []),
            "sub_technologies": list(t.get("sub_technologies") or []),
            "paths": list(t.get("paths") or []),
        })

    # 连线：path 与 xor
    edges = []
    xor_seen = set()
    for tid, t in cur_techs.items():
        path_objs = t.get("paths") or []
        if path_objs:
            for po in path_objs:
                ch = po.get("target")
                if ch in cur_techs:
                    edges.append({
                        "type": "path",
                        "from": tid,
                        "to": ch,
                        "coeff": po.get("coeff", 1),
                    })
        else:
            for ch in (t.get("leads") or []):
                if ch in cur_techs:
                    edges.append({"type": "path", "from": tid, "to": ch, "coeff": 1})
        for xid in (t.get("xor") or []):
            if xid in cur_techs and xid != tid:
                pair = (tid, xid) if tid < xid else (xid, tid)
                if pair not in xor_seen:
                    xor_seen.add(pair)
                    edges.append({"type": "xor", "from": pair[0], "to": pair[1]})

    overlaps = []
    for (px, py), tids in pos_buckets.items():
        if len(tids) > 1:
            overlaps.append({"px": px, "py": py, "tids": tids})

    unlocked = []
    if tag:
        try:
            from xuerong.model.tech import load_country_techs
            unlocked = list(load_country_techs(root, tag).get("unlocked") or [])
        except Exception:
            unlocked = []

    macros = _collect_folder_macros(root, cur_techs)

    return {
        "ok": True,
        "folder": cur_folder,
        "folders": folders,
        "categories": tags_info.get("categories") or [],
        "gui": page,
        "gui_file": gui_info.get("file") or _GUI_REL,
        "gui_source": gui_info.get("source") or "",
        "nodes": nodes,
        "edges": edges,
        "macros": macros,
        "unlocked": unlocked,
        "diagnostics": {
            "invisible_roots": invisible_roots,
            "overlaps": overlaps,
            "missing_cats": missing_cats,
            "missing_gfx": missing_gfx,
            "orphan_gridboxes": orphan_gridboxes,
        },
    }


# ------------------------------------------------------------------ 写操作辅助

def _ensure_tags_file(root):
    top, dst, err = _ensure_rel_writable(root, _TAGS_REL)
    if dst:
        return top, dst, ""
    if not top:
        return None, None, err
    dst = os.path.join(top, _TAGS_REL.replace("/", os.sep))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    skel = "technology_categories = {\n}\n\ntechnology_folders = {\n}\n"
    _atomic_write(dst, skel.encode("utf-8"))
    return top, dst, ""


def _render_folder_block(fid, fields, old_body=""):
    """构造 technology_folders 内的 <fid> = { ... } 块。"""
    ledger = fields.get("ledger")
    if ledger is None and old_body:
        ledger = _first(old_body, r'(?m)^\s*ledger\s*=\s*"?([A-Za-z0-9_]+)"?', "")
    doctrine = fields.get("doctrine")
    if doctrine is None and old_body:
        doctrine = bool(re.search(r'(?m)^\s*doctrine\s*=\s*yes\b', old_body))
    av_raw = fields.get("available_raw")
    if av_raw is None and old_body:
        av_blocks = find_blocks(strip_comments(old_body), "available")
        if av_blocks:
            av_raw = av_blocks[0][2].strip()

    lines = ["\t%s = {" % fid]
    if ledger:
        lines.append("\t\tledger = %s" % str(ledger).strip())
    if doctrine:
        lines.append("\t\tdoctrine = yes")
    if av_raw and str(av_raw).strip():
        av_s = str(av_raw).strip()
        # 若调用方误传外层 available = { ... }，剥掉外框
        m_av = re.match(r'^available\s*=\s*\{([\s\S]*)\}$', av_s)
        if m_av:
            av_s = m_av.group(1).strip()
        lines.append("\t\tavailable = {")
        for ln in av_s.splitlines():
            lines.append("\t\t\t" + ln.strip() if ln.strip() else "")
        lines.append("\t\t}")
    lines.append("\t}")
    return "\n".join(lines)


def _find_tv_range(gui_text):
    """在 gui_text 中定位 countrytechtreeview 的起止与内体边界。"""
    clean = _strip_keep_len(gui_text)
    for k, s, e, is_s, is_e in _iter_child_blocks(clean, clean):
        if k.lower() == "guitypes":
            inner = clean[is_s:is_e]
            for k2, s2, e2, is_s2, is_e2 in _iter_child_blocks(inner, inner):
                if k2.lower() == "containerwindowtype" and _block_scalar(inner[is_s2:is_e2], "name") == "countrytechtreeview":
                    return is_s + s2, is_s + e2, is_s + is_s2, is_s + is_e2
    for k2, s2, e2, is_s2, is_e2 in _iter_child_blocks(clean, clean):
        if k2.lower() == "containerwindowtype" and _block_scalar(clean[is_s2:is_e2], "name") == "countrytechtreeview":
            return s2, e2, is_s2, is_e2
    return None


def _find_tv_child(gui_text, tv_is, tv_ie, child_name):
    """在 countrytechtreeview 内查找直接子 containerWindowType（返回绝对起止与内体边界）。"""
    tv_sub = gui_text[tv_is:tv_ie]
    clean_sub = _strip_keep_len(tv_sub)
    for k, s, e, is_s, is_e in _iter_child_blocks(clean_sub, clean_sub):
        if k.lower() == "containerwindowtype" and _block_scalar(clean_sub[is_s:is_e], "name") == child_name:
            return tv_is + s, tv_is + e, tv_is + is_s, tv_is + is_e
    return None


def _find_top_skin(gui_text, skin_name):
    """在 guiTypes 顶层查找 techtree_<folder>_item / _small_item 块。"""
    clean = _strip_keep_len(gui_text)
    for k, _s, _e, is_s, is_e in _iter_child_blocks(clean, clean):
        if k.lower() == "guitypes":
            inner = clean[is_s:is_e]
            for k2, s2, e2, is_s2, is_e2 in _iter_child_blocks(inner, inner):
                if k2.lower() == "containerwindowtype" and _block_scalar(inner[is_s2:is_e2], "name") == skin_name:
                    return is_s + s2, is_s + e2, is_s + is_s2, is_s + is_e2
    return None


def _gui_insert_before_end(block_text, snippet):
    """在 containerWindowType 末尾 '}' 前插入子块。"""
    rb = block_text.rfind("}")
    if rb < 0:
        return block_text
    return block_text[:rb].rstrip() + "\n\n" + snippet.strip("\n") + "\n" + block_text[rb:]


def _replace_scalar_in_block(block_text, key, new_val, quoted=True):
    """替换单行标量（不改变原有缩进）。"""
    clean = _strip_keep_len(block_text)
    pat = re.compile(r'(?mi)^([ \t]*)%s([ \t]*=[ \t]*)("[^"]*"|[^\s#\}]+)' % re.escape(key))
    m = pat.search(clean)
    val_s = ('"%s"' % new_val) if quoted else str(new_val)
    if m:
        return block_text[:m.start()] + m.group(1) + key + m.group(2) + val_s + block_text[m.end():]
    return block_text


def _replace_xy_in_block(block_text, x, y):
    """更新块内直接子块 position = { x = ... y = ... }。"""
    clean = _strip_keep_len(block_text)
    for k, s, e, _is, _ie in _iter_block_children(block_text, clean):
        if k.lower() == "position":
            return block_text[:s] + ("position = { x = %d y = %d }" % (x, y)) + block_text[e:]
    # 无 position 时插入在 name 后
    m = re.search(r'(?mi)^([ \t]*name\s*=\s*[^\r\n]+)', clean)
    if m:
        return block_text[:m.end()] + "\n" + m.group(1)[:len(m.group(1)) - len(m.group(1).lstrip())] + \
               ("position = { x = %d y = %d }" % (x, y)) + block_text[m.end():]
    return block_text


def _replace_size_in_block(block_text, key, w, h):
    """更新块内 size / slotsize = { width = ... height = ... }（保留嵌套 min 等）。"""
    clean = _strip_keep_len(block_text)
    for k, s, e, is_s, is_e in _iter_block_children(block_text, clean):
        if k.lower() == key.lower():
            sub = block_text[is_s:is_e]
            csub = clean[is_s:is_e]
            mw = re.search(r'(?i)\bwidth\s*=\s*([^\s\}#]+)', csub)
            mh = re.search(r'(?i)\bheight\s*=\s*([^\s\}#]+)', csub)
            if mw and mh:
                # 仅替换第一个 width 与第一个 height（主尺寸在 min={...} 之前）
                s1 = sub[:mw.start()] + ("width = %d" % w) + sub[mw.end():]
                c1 = _strip_keep_len(s1)
                mh2 = re.search(r'(?i)\bheight\s*=\s*([^\s\}#]+)', c1)
                if mh2:
                    s1 = s1[:mh2.start()] + ("height = %d" % h) + s1[mh2.end():]
                return block_text[:is_s] + s1 + block_text[is_e:]
            return block_text[:s] + ("%s = { width = %d height = %d }" % (key, w, h)) + block_text[e:]
    return block_text


def _build_default_page_gui(fid, bg_sprite, stripes_w, stripes_h):
    bg_line = ""
    if bg_sprite:
        bg_line = (
            '\t\t\t\ticonType = {\n'
            '\t\t\t\t\tname = "%s_techtree_bg"\n'
            '\t\t\t\t\tspriteType = "%s"\n'
            '\t\t\t\t\tposition = { x = 0 y = 0 }\n'
            '\t\t\t\t\talwaystransparent = yes\n'
            '\t\t\t\t}\n' % (fid, bg_sprite)
        )
    years_cfg = [("1936", 270), ("1939", 550), ("1942", 970), ("1945", 1390)]
    yr_blocks = []
    for idx, (yr, yx) in enumerate(years_cfg, 1):
        yr_blocks.append(
            '\t\t\t\tinstantTextBoxType = {\n'
            '\t\t\t\t\tname = "%s_year%d"\n'
            '\t\t\t\t\tposition = { x = %d y = 50 }\n'
            '\t\t\t\t\tfont = "hoi_36header"\n'
            '\t\t\t\t\tborderSize = { x = 0 y = 0 }\n'
            '\t\t\t\t\ttext = "%s"\n'
            '\t\t\t\t\tmaxWidth = 170\n'
            '\t\t\t\t\tmaxHeight = 32\n'
            '\t\t\t\t\tformat = left\n'
            '\t\t\t\t\tOrientation = "UPPER_LEFT"\n'
            '\t\t\t\t}' % (fid, idx, yx, yr)
        )
    return (
        '\t\tcontainerWindowType = {\n'
        '\t\t\tname = "%s"\n'
        '\t\t\tposition = { x=0 y=47 }\n'
        '\t\t\tsize = { width = 100%% height = 100%% }\n'
        '\t\t\tmargin = { top = 13 left = 13 bottom = 24 right = 25 }\n'
        '\t\t\tdrag_scroll = { left middle }\n'
        '\t\t\tverticalScrollbar = "right_vertical_slider"\n'
        '\t\t\thorizontalScrollbar = "bottom_horizontal_slider"\n'
        '\t\t\tscroll_wheel_factor = 40\n\n'
        '\t\t\tbackground = {\n'
        '\t\t\t\tname = "Background"\n'
        '\t\t\t\tquadTextureSprite = "GFX_tiled_window_2b_border"\n'
        '\t\t\t}\n\n'
        '\t\t\tcontainerWindowType = {\n'
        '\t\t\t\tname = "techtree_stripes"\n'
        '\t\t\t\tposition = { x = 0 y = 0 }\n'
        '\t\t\t\tsize = {\n'
        '\t\t\t\t\twidth = %d height = %d\n'
        '\t\t\t\t\tmin = { width = 100%% height = 100%% }\n'
        '\t\t\t\t}\n'
        '\t\t\t\tclipping = no\n\n'
        '%s'
        '%s\n'
        '\t\t\t}\n'
        '\t\t}' % (fid, stripes_w, stripes_h, bg_line, "\n\n".join(yr_blocks))
    )


def _build_default_item_skins(fid):
    small = (
        '\tcontainerWindowType = {\n'
        '\t\tname = "techtree_%s_small_item"\n'
        '\t\tposition = { x=0 y=0 }\n'
        '\t\tsize = { width = 72 height = 72 }\n'
        '\t\tclipping = no\n\n'
        '\t\tbackground = {\n'
        '\t\t\tname = "bg"\n'
        '\t\t\tquadTextureSprite = "GFX_technology_unavailable_item_bg"\n'
        '\t\t}\n\n'
        '\t\tgridboxtype = {\n'
        '\t\t\tname = "special_project_specialization_list"\n'
        '\t\t}\n\n'
        '\t\ticonType = {\n'
        '\t\t\tname = "Icon"\n'
        '\t\t\tposition = { x=3 y=3 }\n'
        '\t\t\tspriteType = "GFX_technology_medium"\n'
        '\t\t\talwaystransparent = yes\n'
        '\t\t}\n\n'
        '\t\ticonType = {\n'
        '\t\t\tname = "bonus_icon"\n'
        '\t\t\tposition = { x=-1 y=-22 }\n'
        '\t\t\tspriteType = "GFX_tech_bonus"\n'
        '\t\t}\n\n'
        '\t\tinstantTextBoxType = {\n'
        '\t\t\tname = "bonus"\n'
        '\t\t\tposition = { x = -1 y = -21 }\n'
        '\t\t\tfont = "hoi_16mbs"\n'
        '\t\t\tborderSize = { x = 4 y = 4 }\n'
        '\t\t\ttext = ""\n'
        '\t\t\tmaxWidth = 80\n'
        '\t\t\tmaxHeight = 20\n'
        '\t\t\tformat = center\n'
        '\t\t}\n'
        '\t}' % fid
    )
    large = (
        '\tcontainerWindowType = {\n'
        '\t\tname = "techtree_%s_item"\n'
        '\t\tposition = { x=-56 y=-7 }\n'
        '\t\tsize = { width = 183 height = 84 }\n'
        '\t\tclipping = no\n\n'
        '\t\tbackground = {\n'
        '\t\t\tname = "Background"\n'
        '\t\t\tquadTextureSprite = "GFX_technology_unavailable_item_bg"\n'
        '\t\t}\n\n'
        '\t\tgridboxtype = {\n'
        '\t\t\tname = "special_project_specialization_list"\n'
        '\t\t}\n\n'
        '\t\ticonType = {\n'
        '\t\t\tname = "Icon"\n'
        '\t\t\tposition = { x=91 y=50 }\n'
        '\t\t\tspriteType = "GFX_technology_medium"\n'
        '\t\t\tcenterposition = yes\n'
        '\t\t\talwaystransparent = yes\n'
        '\t\t}\n\n'
        '\t\tinstantTextBoxType = {\n'
        '\t\t\tname = "Name"\n'
        '\t\t\tposition = { x = 3 y = -3 }\n'
        '\t\t\tfont = "hoi_20bs"\n'
        '\t\t\tborderSize = { x = 4 y = 4 }\n'
        '\t\t\ttext = ""\n'
        '\t\t\tmaxWidth = 160\n'
        '\t\t\tmaxHeight = 20\n'
        '\t\t\tfixedsize = yes\n'
        '\t\t\tformat = left\n'
        '\t\t}\n\n'
        '\t\ticonType = {\n'
        '\t\t\tname = "bonus_icon"\n'
        '\t\t\tposition = { x=111 y=-22 }\n'
        '\t\t\tspriteType = "GFX_tech_bonus"\n'
        '\t\t}\n\n'
        '\t\tinstantTextBoxType = {\n'
        '\t\t\tname = "bonus"\n'
        '\t\t\tposition = { x = 111 y = -22 }\n'
        '\t\t\tfont = "hoi_16mbs"\n'
        '\t\t\tborderSize = { x = 4 y = 4 }\n'
        '\t\t\ttext = ""\n'
        '\t\t\tmaxWidth = 80\n'
        '\t\t\tmaxHeight = 20\n'
        '\t\t\tformat = center\n'
        '\t\t}\n'
        '\t}' % fid
    )
    return small + "\n\n" + large


def _update_page_bg_and_stripes(page_block, bg_sprite=None, stripes_w=None, stripes_h=None):
    """更新页面内 techtree_stripes / size_filler 尺寸与背景 iconType。"""
    clean = _strip_keep_len(page_block)
    out = page_block
    for k, s, e, is_s, is_e in _iter_block_children(page_block, clean):
        if k.lower() != "containerwindowtype":
            continue
        cname = _block_scalar(clean[is_s:is_e], "name")
        if cname not in ("techtree_stripes", "size_filler"):
            continue
        sub = out[s:e]
        if stripes_w is not None or stripes_h is not None:
            sbs, sbe = _block_body_range(sub)
            cw, ch = _parse_wh(_strip_keep_len(sub[sbs:sbe]), "size")
            nw = _to_int(stripes_w, _to_int(cw, 1400) or 1400) if stripes_w is not None else (_to_int(cw, 1400) or 1400)
            nh = _to_int(stripes_h, _to_int(ch, 1275) or 1275) if stripes_h is not None else (_to_int(ch, 1275) or 1275)
            sub = _replace_size_in_block(sub, "size", nw, nh)
        if bg_sprite is not None:
            csub = _strip_keep_len(sub)
            updated_bg = False
            for ik, is2, ie2, iis, iie in _iter_block_children(sub, csub):
                if ik.lower() == "icontype":
                    ib = csub[iis:iie]
                    iname = _block_scalar(ib, "name").lower()
                    ispr = (_block_scalar(ib, "spriteType") or _block_scalar(ib, "quadTextureSprite")).lower()
                    if "techtree_bg" in iname or "techtree_bg" in ispr or "_bg" in iname or "_bg" in ispr:
                        ib_raw = sub[is2:ie2]
                        ib_new = _replace_scalar_in_block(ib_raw, "spriteType", bg_sprite, quoted=True)
                        if ib_new == ib_raw:
                            ib_new = _replace_scalar_in_block(ib_raw, "quadTextureSprite", bg_sprite, quoted=True)
                        sub = sub[:is2] + ib_new + sub[ie2:]
                        updated_bg = True
                        break
            if not updated_bg and bg_sprite:
                bg_snip = (
                    '\t\t\t\ticonType = {\n'
                    '\t\t\t\t\tname = "techtree_bg"\n'
                    '\t\t\t\t\tspriteType = "%s"\n'
                    '\t\t\t\t\tposition = { x = 0 y = 0 }\n'
                    '\t\t\t\t\talwaystransparent = yes\n'
                    '\t\t\t\t}' % bg_sprite
                )
                sub = _gui_insert_before_end(sub, bg_snip)
        out = out[:s] + sub + out[e:]
        break
    return out


def _block_body_range(block_text):
    """给定单个 `key = { ... }` 块文本，返回花括号内部范围 `(body_start, body_end)`。"""
    ib = block_text.find("{")
    ie = block_text.rfind("}")
    if ib < 0 or ie <= ib:
        return 0, len(block_text)
    return ib + 1, ie


def _iter_block_children(block_text, clean_text=None):
    """遍历单个外层块 `{ ... }` 内部的直接子块，返回基于 `block_text` 的偏移。"""
    bs, be = _block_body_range(block_text)
    sub_raw = block_text[bs:be]
    sub_clean = (clean_text[bs:be] if clean_text is not None else _strip_keep_len(sub_raw))
    for k, s, e, is_s, is_e in _iter_child_blocks(sub_raw, sub_clean):
        yield k, bs + s, bs + e, bs + is_s, bs + is_e


# ------------------------------------------------------------------ 写操作：6 个核心接口 + category

def tech_folder_save(root, fid, fields=None):
    """新建或修改科技页签（同步写 00_technology.txt、countrytechtreeview.gui 与可选中文名）。"""
    fid = (fid or "").strip()
    if not re.match(r'^[A-Za-z0-9_]+$', fid):
        return {"ok": False, "msg": "folder id 只能字母数字下划线"}
    fields = fields or {}

    top, tag_path, err = _ensure_tags_file(root)
    if not tag_path:
        return {"ok": False, "msg": err}

    tag_text = io.open(tag_path, encoding="utf-8-sig", errors="replace").read()
    clean_tag = _strip_keep_len(tag_text)
    tf_blocks = find_blocks(clean_tag, "technology_folders")
    if not tf_blocks:
        tag_text = tag_text.rstrip() + "\n\ntechnology_folders = {\n}\n"
        clean_tag = _strip_keep_len(tag_text)
        tf_blocks = find_blocks(clean_tag, "technology_folders")

    tf_s, tf_e, tf_body_clean = tf_blocks[0]
    tf_body_raw = tag_text[tf_s + 1:tf_e - 1]
    existing_span = None
    for k, s, e, is_s, is_e in _iter_child_blocks(tf_body_clean, tf_body_clean):
        if k == fid:
            existing_span = (s, e, tf_body_raw[is_s:is_e])
            break

    is_new_folder = existing_span is None
    if existing_span:
        es, ee, old_body = existing_span
        new_block = _render_folder_block(fid, fields, old_body=old_body)
        # 对齐外缩进
        new_tf_body = tf_body_raw[:es].rstrip() + "\n" + new_block + "\n" + tf_body_raw[ee:].lstrip("\r\n")
        if not new_tf_body.startswith("\n"):
            new_tf_body = "\n" + new_tf_body
    else:
        new_block = _render_folder_block(fid, fields)
        new_tf_body = tf_body_raw.rstrip() + "\n" + new_block + "\n"

    new_tag_text = tag_text[:tf_s + 1] + new_tf_body + tag_text[tf_e - 1:]
    if not braces_balanced(new_tag_text):
        return {"ok": False, "msg": "00_technology.txt 括号不匹配，已中止保存"}
    snapshot(tag_path)
    _atomic_write(tag_path, new_tag_text.encode("utf-8"))

    # 同步 .gui（若需要）
    need_gui = (
        is_new_folder
        or fields.get("sync_gui")
        or any(k in fields for k in ("bg_sprite", "stripes_w", "stripes_h", "tab_sprite", "copy_from"))
    )
    if need_gui:
        _top_g, gui_path, g_err = _ensure_rel_writable(top, _GUI_REL)
        if gui_path and os.path.isfile(gui_path):
            gui_text = io.open(gui_path, encoding="utf-8-sig", errors="replace").read()
            tv = _find_tv_range(gui_text)
            if tv:
                tv_s, tv_e, tv_is, tv_ie = tv
                tab_sprite = fields.get("tab_sprite") or ("GFX_%s_tab" % fid)
                # 1) folder_tabs buttonType
                ft_pos = _find_tv_child(gui_text, tv_is, tv_ie, "folder_tabs")
                if ft_pos:
                    ft_s, ft_e, ft_is, ft_ie = ft_pos
                    ft_raw = gui_text[ft_s:ft_e]
                    ft_clean = _strip_keep_len(ft_raw)
                    tab_name = fid + "_tab"
                    found_tab = None
                    max_x = _TAB_START_X - _TAB_STEP_X
                    for bk, bs, be, bis_s, bis_e in _iter_block_children(ft_raw, ft_clean):
                        if bk.lower() == "buttontype":
                            bbody = ft_clean[bis_s:bis_e]
                            bx_raw, _ = _parse_xy(bbody, "position")
                            max_x = max(max_x, _to_int(bx_raw, 0))
                            if _block_scalar(bbody, "name") == tab_name:
                                found_tab = (bs, be)
                    if found_tab:
                        if fields.get("tab_sprite"):
                            ts, te = found_tab
                            tb_old = ft_raw[ts:te]
                            tb_new = _replace_scalar_in_block(tb_old, "quadTextureSprite", fields["tab_sprite"], quoted=True)
                            if tb_new == tb_old:
                                tb_new = _replace_scalar_in_block(tb_old, "spriteType", fields["tab_sprite"], quoted=True)
                            ft_raw = ft_raw[:ts] + tb_new + ft_raw[te:]
                    else:
                        next_x = max_x + _TAB_STEP_X
                        tab_snip = (
                            '\t\t\tbuttonType = {\n'
                            '\t\t\t\tname = "%s"\n'
                            '\t\t\t\tposition = { x = %d y = 0 }\n'
                            '\t\t\t\tquadTextureSprite = "%s"\n'
                            '\t\t\t\tframe = 1\n'
                            '\t\t\t\tclicksound = ui_research_tab_infantry\n'
                            '\t\t\t}' % (tab_name, next_x, tab_sprite)
                        )
                        ft_raw = _gui_insert_before_end(ft_raw, tab_snip)
                    gui_text = gui_text[:ft_s] + ft_raw + gui_text[ft_e:]
                    tv = _find_tv_range(gui_text)
                    tv_s, tv_e, tv_is, tv_ie = tv

                # 2) <fid> 页面 containerWindowType
                pg_pos = _find_tv_child(gui_text, tv_is, tv_ie, fid)
                bg_spr = fields.get("bg_sprite")
                sw = fields.get("stripes_w")
                sh = fields.get("stripes_h")
                created_page = False
                if pg_pos:
                    ps, pe, _pis, _pie = pg_pos
                    if bg_spr is not None or sw is not None or sh is not None:
                        pg_old = gui_text[ps:pe]
                        pg_new = _update_page_bg_and_stripes(pg_old, bg_sprite=bg_spr, stripes_w=sw, stripes_h=sh)
                        gui_text = gui_text[:ps] + pg_new + gui_text[pe:]
                else:
                    created_page = True
                    copy_from = (fields.get("copy_from") or "").strip()
                    src_pg = _find_tv_child(gui_text, tv_is, tv_ie, copy_from) if copy_from else None
                    if src_pg:
                        pg_new = gui_text[src_pg[0]:src_pg[1]]
                        pg_new = _replace_scalar_in_block(pg_new, "name", fid, quoted=True)
                        # 复制模板时移除旧 gridboxtype，避免跨页重复 root_tech
                        clean_pg = _strip_keep_len(pg_new)
                        for gk, gs, ge, _gis, _gie in reversed(list(_iter_block_children(pg_new, clean_pg))):
                            if gk.lower() == "gridboxtype":
                                pg_new = pg_new[:gs].rstrip() + "\n" + pg_new[ge:].lstrip("\r\n")
                        pg_new = "\t\t" + pg_new.lstrip()
                        if bg_spr is not None or sw is not None or sh is not None:
                            pg_new = _update_page_bg_and_stripes(pg_new, bg_sprite=bg_spr, stripes_w=sw, stripes_h=sh)
                    else:
                        pg_new = _build_default_page_gui(
                            fid,
                            bg_spr or "",
                            _to_int(sw, 1400) or 1400,
                            _to_int(sh, 1275) or 1275,
                        )
                    # 插到 folder_tabs 之前
                    ft_pos2 = _find_tv_child(gui_text, tv_is, tv_ie, "folder_tabs")
                    ins_at = ft_pos2[0] if ft_pos2 else (tv_ie - 1)
                    gui_text = gui_text[:ins_at].rstrip() + "\n\n" + pg_new + "\n\n\t\t" + gui_text[ins_at:].lstrip()

                # 3) 补齐节点皮肤 techtree_<fid>_item / _small_item
                if created_page:
                    has_item = _find_top_skin(gui_text, "techtree_%s_item" % fid) is not None
                    has_small = _find_top_skin(gui_text, "techtree_%s_small_item" % fid) is not None
                    if not (has_item and has_small):
                        skins = _build_default_item_skins(fid)
                        rb = gui_text.rfind("}")
                        if rb >= 0:
                            gui_text = gui_text[:rb].rstrip() + "\n\n" + skins + "\n" + gui_text[rb:]

                if braces_balanced(gui_text):
                    snapshot(gui_path)
                    _atomic_write(gui_path, gui_text.encode("utf-8"))

    if fields.get("name_zh"):
        save_loc(top, {"simp_chinese": {fid: str(fields["name_zh"])}})

    return {"ok": True, "id": fid, "created": is_new_folder,
            "msg": "已%s科技页 %s" % ("新建" if is_new_folder else "保存", fid)}


def tech_folder_delete(root, fid):
    """从可写层 00_technology.txt 与 countrytechtreeview.gui 删除科技页签及其 GUI 页面/皮肤。"""
    fid = (fid or "").strip()
    if not fid:
        return {"ok": False, "msg": "缺少 folder id"}
    top = paths._pick(root)
    if not top:
        return {"ok": False, "msg": "请先选择可写 mod 目录"}

    using = [tid for tid, t in (state.techs() or {}).items() if (t.get("path") or "").strip() == fid]
    if using:
        return {"ok": False,
                "msg": "页签 %s 下仍有 %d 项科技（如 %s），请先删除或移走这些科技再删页签" % (fid, len(using), ", ".join(using[:3]))}

    removed_tags = False
    tag_path = os.path.join(top, _TAGS_REL.replace("/", os.sep))
    if os.path.isfile(tag_path):
        tag_text = io.open(tag_path, encoding="utf-8-sig", errors="replace").read()
        clean_tag = _strip_keep_len(tag_text)
        tf_blocks = find_blocks(clean_tag, "technology_folders")
        if tf_blocks:
            tf_s, tf_e, tf_body_clean = tf_blocks[0]
            tf_body_raw = tag_text[tf_s + 1:tf_e - 1]
            for k, s, e, _is_s, _is_e in _iter_child_blocks(tf_body_clean, tf_body_clean):
                if k == fid:
                    new_body = tf_body_raw[:s].rstrip() + "\n" + tf_body_raw[e:].lstrip("\r\n")
                    if not new_body.startswith("\n"):
                        new_body = "\n" + new_body
                    new_tag_text = tag_text[:tf_s + 1] + new_body + tag_text[tf_e - 1:]
                    if braces_balanced(new_tag_text):
                        snapshot(tag_path)
                        _atomic_write(tag_path, new_tag_text.encode("utf-8"))
                        removed_tags = True
                    break

    removed_gui = False
    gui_path = os.path.join(top, _GUI_REL.replace("/", os.sep))
    if os.path.isfile(gui_path):
        gui_text = io.open(gui_path, encoding="utf-8-sig", errors="replace").read()
        changed_g = False
        tv = _find_tv_range(gui_text)
        if tv:
            ft_pos = _find_tv_child(gui_text, tv[2], tv[3], "folder_tabs")
            if ft_pos:
                ft_s, ft_e = ft_pos[0], ft_pos[1]
                ft_raw = gui_text[ft_s:ft_e]
                ft_clean = _strip_keep_len(ft_raw)
                tab_name = fid + "_tab"
                for bk, bs, be, bis_s, bis_e in _iter_block_children(ft_raw, ft_clean):
                    if bk.lower() == "buttontype" and _block_scalar(ft_clean[bis_s:bis_e], "name") == tab_name:
                        ft_new = ft_raw[:bs].rstrip() + "\n" + ft_raw[be:].lstrip("\r\n")
                        gui_text = gui_text[:ft_s] + ft_new + gui_text[ft_e:]
                        changed_g = True
                        break
            tv = _find_tv_range(gui_text)
            if tv:
                pg_pos = _find_tv_child(gui_text, tv[2], tv[3], fid)
                if pg_pos:
                    gui_text = gui_text[:pg_pos[0]].rstrip() + "\n" + gui_text[pg_pos[1]:].lstrip("\r\n")
                    changed_g = True
        for skin_name in ("techtree_%s_item" % fid, "techtree_%s_small_item" % fid):
            sk = _find_top_skin(gui_text, skin_name)
            if sk:
                gui_text = gui_text[:sk[0]].rstrip() + "\n" + gui_text[sk[1]:].lstrip("\r\n")
                changed_g = True
        if changed_g and braces_balanced(gui_text):
            snapshot(gui_path)
            _atomic_write(gui_path, gui_text.encode("utf-8"))
            removed_gui = True

    if not removed_tags and not removed_gui:
        return {"ok": False, "msg": "当前可写层未包含页签 %s（若来自原版或父 mod 只读层请勿直接删除）" % fid}
    return {"ok": True, "id": fid, "msg": "已从当前 mod 移除科技页签 " + fid}


def tech_folders_reorder(root, order):
    """重排 00_technology.txt 中 technology_folders 顺序并同步更新 folder_tabs 横坐标。"""
    if not isinstance(order, (list, tuple)) or not order:
        return {"ok": False, "msg": "order 不能为空"}
    order = [str(x).strip() for x in order if str(x).strip()]

    top, tag_path, err = _ensure_rel_writable(root, _TAGS_REL)
    if not tag_path:
        return {"ok": False, "msg": err}

    tag_text = io.open(tag_path, encoding="utf-8-sig", errors="replace").read()
    clean_tag = _strip_keep_len(tag_text)
    tf_blocks = find_blocks(clean_tag, "technology_folders")
    if not tf_blocks:
        return {"ok": False, "msg": "00_technology.txt 中找不到 technology_folders"}

    tf_s, tf_e, tf_body_clean = tf_blocks[0]
    tf_body_raw = tag_text[tf_s + 1:tf_e - 1]
    folder_raws = {}
    orig_seq = []
    for k, s, e, _is_s, _is_e in _iter_child_blocks(tf_body_clean, tf_body_clean):
        if k not in folder_raws:
            orig_seq.append(k)
        folder_raws[k] = tf_body_raw[s:e].strip("\r\n")

    final_seq = [fid for fid in order if fid in folder_raws]
    for fid in orig_seq:
        if fid not in final_seq:
            final_seq.append(fid)

    rebuilt = "\n" + "\n".join("\t" + folder_raws[fid].lstrip() for fid in final_seq) + "\n"
    new_tag_text = tag_text[:tf_s + 1] + rebuilt + tag_text[tf_e - 1:]
    if not braces_balanced(new_tag_text):
        return {"ok": False, "msg": "重排后括号不平衡，已取消"}
    snapshot(tag_path)
    _atomic_write(tag_path, new_tag_text.encode("utf-8"))

    # 同步 folder_tabs 按钮 x 坐标
    _tg, gui_path, _ge = _ensure_rel_writable(top, _GUI_REL)
    if gui_path and os.path.isfile(gui_path):
        gui_text = io.open(gui_path, encoding="utf-8-sig", errors="replace").read()
        tv = _find_tv_range(gui_text)
        if tv:
            ft_pos = _find_tv_child(gui_text, tv[2], tv[3], "folder_tabs")
            if ft_pos:
                ft_s, ft_e = ft_pos[0], ft_pos[1]
                ft_raw = gui_text[ft_s:ft_e]
                ft_clean = _strip_keep_len(ft_raw)
                rank = {fid + "_tab": idx for idx, fid in enumerate(final_seq)}
                base_extra = len(final_seq)
                edits = []
                for bk, bs, be, bis_s, bis_e in _iter_block_children(ft_raw, ft_clean):
                    if bk.lower() != "buttontype":
                        continue
                    bname = _block_scalar(ft_clean[bis_s:bis_e], "name")
                    if bname in rank:
                        nx = _TAB_START_X + rank[bname] * _TAB_STEP_X
                    else:
                        nx = _TAB_START_X + base_extra * _TAB_STEP_X
                        base_extra += 1
                    _, by_raw = _parse_xy(ft_clean[bis_s:bis_e], "position")
                    by = _to_int(by_raw, 0)
                    edits.append((bs, be, _replace_xy_in_block(ft_raw[bs:be], nx, by)))
                for bs, be, rep in reversed(edits):
                    ft_raw = ft_raw[:bs] + rep + ft_raw[be:]
                new_gui = gui_text[:ft_s] + ft_raw + gui_text[ft_e:]
                if braces_balanced(new_gui):
                    snapshot(gui_path)
                    _atomic_write(gui_path, new_gui.encode("utf-8"))

    return {"ok": True, "order": final_seq, "msg": "已重排 %d 个科技页签" % len(final_seq)}


def _find_textbox_in_page(page_text, target_name, ox=0, oy=0, container_name="", pw=1400, ph=1275):
    """递归在 page_text 内定位指定 name 的 instantTextBoxType。

    返回 (rel_start, rel_end, parent_ox, parent_oy) 或 None。
    """
    clean = _strip_keep_len(page_text)
    for k, s, e, is_s, is_e in _iter_child_blocks(clean, clean):
        kl = k.lower()
        cbody = clean[is_s:is_e]
        if kl == "instanttextboxtype":
            if _block_scalar(cbody, "name") == target_name:
                return s, e, ox, oy
        elif kl == "containerwindowtype":
            cname = _block_scalar(cbody, "name")
            cox, coy, ccw, cch = _container_offset(cbody, pw, ph)
            if cname in ("techtree_stripes", "size_filler"):
                w_raw, h_raw = _parse_wh(cbody, "size")
                ccw = _to_int(w_raw, ccw) or ccw
                cch = _to_int(h_raw, cch) or cch
            hit = _find_textbox_in_page(
                page_text[is_s:is_e], target_name,
                ox=ox + cox, oy=oy + coy,
                container_name=cname or container_name, pw=ccw, ph=cch,
            )
            if hit:
                hs, he, hox, hoy = hit
                return is_s + hs, is_s + he, hox, hoy
    return None


def _sync_year_macro(root, folder, year_str, macro_val):
    """同步更新所属 common/technologies/*.txt 顶部的 @<year> = <val>。"""
    if not year_str or macro_val is None or str(macro_val).strip() == "":
        return []
    val_s = str(macro_val).strip()
    techs = state.techs() or {}
    rels = sorted({t.get("file") for t in techs.values() if t.get("path") == folder and t.get("file")})
    updated_files = []
    for rel in rels:
        _top, dst, _err = _ensure_rel_writable(root, rel)
        if not dst or not os.path.isfile(dst):
            continue
        text = io.open(dst, encoding="utf-8-sig", errors="replace").read()
        pat = re.compile(r'(?m)^([ \t]*)@%s[ \t]*=[ \t]*(-?[0-9.]+)' % re.escape(year_str))
        if pat.search(text):
            new_text = pat.sub(lambda m: "%s@%s = %s" % (m.group(1), year_str, val_s), text, count=1)
        else:
            tm = re.search(r'(?m)^[ \t]*technologies\s*=\s*\{', text)
            if not tm:
                continue
            tb = text.find("{", tm.start())
            new_text = text[:tb + 1] + ("\n\t@%s = %s" % (year_str, val_s)) + text[tb + 1:]
        if new_text != text and braces_balanced(new_text):
            snapshot(dst)
            _atomic_write(dst, new_text.encode("utf-8"))
            updated_files.append(rel.replace("\\", "/"))
            # 同步更新内存中使用该宏的科技坐标
            try:
                fval = float(val_s)
            except Exception:
                fval = None
            if fval is not None:
                for t in techs.values():
                    if t.get("file") == rel:
                        raw = t.get("raw") or ""
                        if re.search(r'x\s*=\s*@%s\b' % re.escape(year_str), raw):
                            t["fx"] = fval
                        if re.search(r'y\s*=\s*@%s\b' % re.escape(year_str), raw):
                            t["fy"] = fval
    return updated_files


def _page_stripes_span(page_raw):
    clean = _strip_keep_len(page_raw)
    for k, s, e, is_s, is_e in _iter_block_children(page_raw, clean):
        if k.lower() == "containerwindowtype":
            cname = _block_scalar(clean[is_s:is_e], "name")
            if cname in ("techtree_stripes", "size_filler"):
                w_raw, h_raw = _parse_wh(clean[is_s:is_e], "size")
                return s, e, (_to_int(w_raw, 1400) or 1400), (_to_int(h_raw, 1275) or 1275)
    return None, None, 1400, 1275


def tech_year_save(root, folder, op="update", data=None):
    """增删改 countrytechtreeview.gui <folder> 内的年份 instantTextBoxType，可选同步 @year 宏。"""
    folder = (folder or "").strip()
    op = (op or "update").strip().lower()
    data = data or {}
    if not folder:
        return {"ok": False, "msg": "缺少 folder"}
    if op not in ("add", "update", "delete"):
        return {"ok": False, "msg": "不支持的操作：" + op}

    top, gui_path, err = _ensure_rel_writable(root, _GUI_REL)
    if not gui_path:
        return {"ok": False, "msg": err}

    gui_text = io.open(gui_path, encoding="utf-8-sig", errors="replace").read()
    tv = _find_tv_range(gui_text)
    if not tv:
        return {"ok": False, "msg": "找不到 countrytechtreeview 容器"}
    pg = _find_tv_child(gui_text, tv[2], tv[3], folder)
    if not pg:
        return {"ok": False, "msg": "找不到科技页面：" + folder}

    ps, pe = pg[0], pg[1]
    page_raw = gui_text[ps:pe]
    st_s, st_e, pw, ph = _page_stripes_span(page_raw)

    tb_name = (data.get("old_name") or data.get("name") or "").strip()
    new_name = (data.get("name") or tb_name).strip()
    yr_text = str(data.get("text") or "").strip()

    if op == "add":
        if not re.match(r'^\d{4}$', yr_text):
            return {"ok": False, "msg": "年份必须是 4 位数字"}
        if not new_name:
            new_name = "%s_year_%s" % (folder, yr_text)
        x = _to_int(data.get("x"), 270)
        y = _to_int(data.get("y"), 50)
        snip = (
            '\t\t\t\tinstantTextBoxType = {\n'
            '\t\t\t\t\tname = "%s"\n'
            '\t\t\t\t\tposition = { x = %d y = %d }\n'
            '\t\t\t\t\tfont = "hoi_36header"\n'
            '\t\t\t\t\tborderSize = { x = 0 y = 0 }\n'
            '\t\t\t\t\ttext = "%s"\n'
            '\t\t\t\t\tmaxWidth = 170\n'
            '\t\t\t\t\tmaxHeight = 32\n'
            '\t\t\t\t\tformat = left\n'
            '\t\t\t\t\tOrientation = "UPPER_LEFT"\n'
            '\t\t\t\t}' % (new_name, x, y, yr_text)
        )
        if st_s is not None:
            st_new = _gui_insert_before_end(page_raw[st_s:st_e], snip)
            page_new = page_raw[:st_s] + st_new + page_raw[st_e:]
        else:
            page_new = _gui_insert_before_end(page_raw, snip)
    else:
        if not tb_name:
            return {"ok": False, "msg": "缺少文本框 name"}
        pbs, pbe = _block_body_range(page_raw)
        hit = _find_textbox_in_page(page_raw[pbs:pbe], tb_name, pw=pw, ph=ph)
        if not hit:
            return {"ok": False, "msg": "找不到年份控件：" + tb_name}
        hs, he, ox, oy = hit
        hs += pbs
        he += pbs
        if op == "delete":
            page_new = page_raw[:hs].rstrip() + "\n" + page_raw[he:].lstrip("\r\n")
        else:
            tb_block = page_raw[hs:he]
            if new_name and new_name != tb_name:
                tb_block = _replace_scalar_in_block(tb_block, "name", new_name, quoted=True)
            if yr_text:
                if not re.match(r'^\d{4}$', yr_text):
                    return {"ok": False, "msg": "年份必须是 4 位数字"}
                tb_block = _replace_scalar_in_block(tb_block, "text", yr_text, quoted=True)
            if data.get("x") is not None or data.get("y") is not None:
                tbs, tbe = _block_body_range(tb_block)
                c_tb = _strip_keep_len(tb_block[tbs:tbe])
                cx_raw, cy_raw = _parse_xy(c_tb, "position")
                cur_px = ox + _resolve_coord(cx_raw, pw, 0)
                cur_py = oy + _resolve_coord(cy_raw, ph, 0)
                nx = _to_int(data["x"], cur_px) if data.get("x") is not None else cur_px
                ny = _to_int(data["y"], cur_py) if data.get("y") is not None else cur_py
                tb_block = _replace_xy_in_block(tb_block, nx - ox, ny - oy)
            page_new = page_raw[:hs] + tb_block + page_raw[he:]

    new_gui = gui_text[:ps] + page_new + gui_text[pe:]
    if not braces_balanced(new_gui):
        return {"ok": False, "msg": "countrytechtreeview.gui 括号不平衡，已中止"}
    snapshot(gui_path)
    _atomic_write(gui_path, new_gui.encode("utf-8"))

    synced = []
    if data.get("sync_macro") and data.get("macro_val") is not None and yr_text:
        synced = _sync_year_macro(top, folder, yr_text, data.get("macro_val"))

    return {"ok": True, "op": op, "name": new_name, "synced_macros": synced,
            "msg": "年份刻度已%s" % {"add": "添加", "update": "更新", "delete": "删除"}[op]}


def tech_subtitle_save(root, folder, op="update", data=None):
    """增删改 countrytechtreeview.gui <folder> 内的标题 instantTextBoxType，可选同步本地化。"""
    folder = (folder or "").strip()
    op = (op or "update").strip().lower()
    data = data or {}
    if not folder:
        return {"ok": False, "msg": "缺少 folder"}
    if op not in ("add", "update", "delete"):
        return {"ok": False, "msg": "不支持的操作：" + op}

    top, gui_path, err = _ensure_rel_writable(root, _GUI_REL)
    if not gui_path:
        return {"ok": False, "msg": err}

    gui_text = io.open(gui_path, encoding="utf-8-sig", errors="replace").read()
    tv = _find_tv_range(gui_text)
    if not tv:
        return {"ok": False, "msg": "找不到 countrytechtreeview 容器"}
    pg = _find_tv_child(gui_text, tv[2], tv[3], folder)
    if not pg:
        return {"ok": False, "msg": "找不到科技页面：" + folder}

    ps, pe = pg[0], pg[1]
    page_raw = gui_text[ps:pe]
    st_s, st_e, pw, ph = _page_stripes_span(page_raw)

    tb_name = (data.get("old_name") or data.get("name") or "").strip()
    new_name = (data.get("name") or tb_name).strip()
    txt = str(data.get("text") or "").strip()

    if op == "add":
        if not new_name:
            new_name = "%s_subtitle_%d" % (folder, abs(hash(txt or folder)) % 10000)
        x = _to_int(data.get("x"), 30)
        y = _to_int(data.get("y"), 100)
        font = (data.get("font") or "hoi_33").strip()
        mw = _to_int(data.get("maxWidth"), 600) or 600
        mh = _to_int(data.get("maxHeight"), 62) or 62
        fmt = (data.get("format") or "left").strip()
        snip = (
            '\t\t\t\tinstantTextBoxType = {\n'
            '\t\t\t\t\tname = "%s"\n'
            '\t\t\t\t\tposition = { x = %d y = %d }\n'
            '\t\t\t\t\tfont = "%s"\n'
            '\t\t\t\t\tborderSize = { x = 0 y = 0 }\n'
            '\t\t\t\t\ttext = "%s"\n'
            '\t\t\t\t\tmaxWidth = %d\n'
            '\t\t\t\t\tmaxHeight = %d\n'
            '\t\t\t\t\tformat = %s\n'
            '\t\t\t\t\tOrientation = "UPPER_LEFT"\n'
            '\t\t\t\t}' % (new_name, x, y, font, txt or new_name.upper(), mw, mh, fmt)
        )
        if st_s is not None:
            st_new = _gui_insert_before_end(page_raw[st_s:st_e], snip)
            page_new = page_raw[:st_s] + st_new + page_raw[st_e:]
        else:
            page_new = _gui_insert_before_end(page_raw, snip)
    else:
        if not tb_name:
            return {"ok": False, "msg": "缺少标题控件 name"}
        pbs, pbe = _block_body_range(page_raw)
        hit = _find_textbox_in_page(page_raw[pbs:pbe], tb_name, pw=pw, ph=ph)
        if not hit:
            return {"ok": False, "msg": "找不到标题控件：" + tb_name}
        hs, he, ox, oy = hit
        hs += pbs
        he += pbs
        if op == "delete":
            page_new = page_raw[:hs].rstrip() + "\n" + page_raw[he:].lstrip("\r\n")
        else:
            tb_block = page_raw[hs:he]
            if new_name and new_name != tb_name:
                tb_block = _replace_scalar_in_block(tb_block, "name", new_name, quoted=True)
            if "text" in data and data.get("text") is not None:
                tb_block = _replace_scalar_in_block(tb_block, "text", txt, quoted=True)
            if data.get("x") is not None or data.get("y") is not None:
                tbs, tbe = _block_body_range(tb_block)
                c_tb = _strip_keep_len(tb_block[tbs:tbe])
                cx_raw, cy_raw = _parse_xy(c_tb, "position")
                cur_px = ox + _resolve_coord(cx_raw, pw, 0)
                cur_py = oy + _resolve_coord(cy_raw, ph, 0)
                nx = _to_int(data["x"], cur_px) if data.get("x") is not None else cur_px
                ny = _to_int(data["y"], cur_py) if data.get("y") is not None else cur_py
                tb_block = _replace_xy_in_block(tb_block, nx - ox, ny - oy)
            page_new = page_raw[:hs] + tb_block + page_raw[he:]

    new_gui = gui_text[:ps] + page_new + gui_text[pe:]
    if not braces_balanced(new_gui):
        return {"ok": False, "msg": "countrytechtreeview.gui 括号不平衡，已中止"}
    snapshot(gui_path)
    _atomic_write(gui_path, new_gui.encode("utf-8"))

    if data.get("text_zh") and (txt or new_name):
        loc_key = txt or new_name
        save_loc(top, {"simp_chinese": {loc_key: str(data["text_zh"])}})

    return {"ok": True, "op": op, "name": new_name,
            "msg": "分区标题已%s" % {"add": "添加", "update": "更新", "delete": "删除"}[op]}


def tech_gridbox_save(root, folder, op="update", data=None):
    """在 countrytechtreeview.gui <folder> 中增删改 gridboxtype。"""
    folder = (folder or "").strip()
    op = (op or "update").strip().lower()
    data = data or {}
    if not folder:
        return {"ok": False, "msg": "缺少 folder"}
    if op not in ("add", "update", "delete"):
        return {"ok": False, "msg": "不支持的操作：" + op}

    top, gui_path, err = _ensure_rel_writable(root, _GUI_REL)
    if not gui_path:
        return {"ok": False, "msg": err}

    gui_text = io.open(gui_path, encoding="utf-8-sig", errors="replace").read()
    tv = _find_tv_range(gui_text)
    if not tv:
        return {"ok": False, "msg": "找不到 countrytechtreeview 容器"}
    pg = _find_tv_child(gui_text, tv[2], tv[3], folder)
    if not pg:
        return {"ok": False, "msg": "找不到科技页面：" + folder}

    ps, pe = pg[0], pg[1]
    page_raw = gui_text[ps:pe]
    clean_pg = _strip_keep_len(page_raw)

    root_tech = (data.get("root_tech") or "").strip()
    gb_name = (data.get("old_name") or data.get("name") or (root_tech + "_tree" if root_tech else "")).strip()
    new_name = (data.get("name") or (root_tech + "_tree" if root_tech else gb_name)).strip()

    if not gb_name and not new_name:
        return {"ok": False, "msg": "缺少 gridbox name 或 root_tech"}

    hit = None
    for k, s, e, is_s, is_e in _iter_block_children(page_raw, clean_pg):
        if k.lower() == "gridboxtype" and _block_scalar(clean_pg[is_s:is_e], "name") == (gb_name or new_name):
            hit = (s, e)
            break

    if op == "add":
        if hit:
            return {"ok": False, "msg": "gridbox 已存在：" + (gb_name or new_name)}
        x = _to_int(data.get("x"), 140)
        y = _to_int(data.get("y"), 210)
        sw = _to_int(data.get("slot_w"), 70) or 70
        sh = _to_int(data.get("slot_h"), 70) or 70
        fmt = (data.get("format") or "LEFT").strip().upper()
        snip = (
            '\t\t\tgridboxtype = {\n'
            '\t\t\t\tname = "%s"\n'
            '\t\t\t\tposition = { x = %d y = %d }\n'
            '\t\t\t\tslotsize = { width = %d height = %d }\n'
            '\t\t\t\tformat = "%s"\n'
            '\t\t\t}' % (new_name, x, y, sw, sh, fmt)
        )
        page_new = _gui_insert_before_end(page_raw, snip)
    elif op == "delete":
        if not hit:
            return {"ok": False, "msg": "找不到 gridbox：" + gb_name}
        page_new = page_raw[:hit[0]].rstrip() + "\n" + page_raw[hit[1]:].lstrip("\r\n")
    else:
        if not hit:
            return {"ok": False, "msg": "找不到 gridbox：" + gb_name}
        gb_block = page_raw[hit[0]:hit[1]]
        gbs, gbe = _block_body_range(gb_block)
        c_gb = _strip_keep_len(gb_block[gbs:gbe])
        if new_name and new_name != gb_name:
            gb_block = _replace_scalar_in_block(gb_block, "name", new_name, quoted=True)
        if data.get("x") is not None or data.get("y") is not None:
            cx_raw, cy_raw = _parse_xy(c_gb, "position")
            _, _, pw, ph = _page_stripes_span(page_raw)
            cur_x = _resolve_coord(cx_raw, pw, 140)
            cur_y = _resolve_coord(cy_raw, ph, 210)
            nx = _to_int(data["x"], cur_x) if data.get("x") is not None else cur_x
            ny = _to_int(data["y"], cur_y) if data.get("y") is not None else cur_y
            gb_block = _replace_xy_in_block(gb_block, nx, ny)
        if data.get("slot_w") is not None or data.get("slot_h") is not None:
            c_sw, c_sh = _parse_wh(c_gb, "slotsize")
            nsw = _to_int(data["slot_w"], _to_int(c_sw, 70) or 70) if data.get("slot_w") is not None else (_to_int(c_sw, 70) or 70)
            nsh = _to_int(data["slot_h"], _to_int(c_sh, 70) or 70) if data.get("slot_h") is not None else (_to_int(c_sh, 70) or 70)
            gb_block = _replace_size_in_block(gb_block, "slotsize", nsw, nsh)
        if data.get("format"):
            gb_block = _replace_scalar_in_block(gb_block, "format", str(data["format"]).strip().upper(), quoted=True)
        page_new = page_raw[:hit[0]] + gb_block + page_raw[hit[1]:]

    new_gui = gui_text[:ps] + page_new + gui_text[pe:]
    if not braces_balanced(new_gui):
        return {"ok": False, "msg": "countrytechtreeview.gui 括号不平衡，已中止"}
    snapshot(gui_path)
    _atomic_write(gui_path, new_gui.encode("utf-8"))
    return {"ok": True, "op": op, "name": new_name,
            "msg": "gridbox %s 已%s" % (new_name, {"add": "注册", "update": "更新", "delete": "删除"}[op])}


def tech_gridbox_register(root, folder, root_tech, x=140, y=210, slot_w=70, slot_h=70, fmt="LEFT"):
    """幂等注册根科技对应的 <root_tech>_tree gridboxtype，使孤立根科技进游戏可见。"""
    root_tech = (root_tech or "").strip()
    if not folder or not root_tech:
        return {"ok": False, "msg": "folder 和 root_tech 都要给"}
    gb_name = root_tech + "_tree"
    gui_info = load_techtree_gui(root)
    page = (gui_info.get("pages") or {}).get(folder) or {}
    for gb in (page.get("gridboxes") or []):
        if gb.get("name") == gb_name:
            return {"ok": True, "name": gb_name, "already": True, "msg": "%s 已注册" % gb_name}
    return tech_gridbox_save(root, folder, "add", {
        "name": gb_name,
        "root_tech": root_tech,
        "x": x,
        "y": y,
        "slot_w": slot_w,
        "slot_h": slot_h,
        "format": fmt,
    })


def tech_item_style_save(root, folder, fields=None):
    """修改 techtree_<folder>_item / _small_item 的 size 及本页 gridbox slotsize。"""
    folder = (folder or "").strip()
    fields = fields or {}
    if not folder:
        return {"ok": False, "msg": "缺少 folder"}

    top, gui_path, err = _ensure_rel_writable(root, _GUI_REL)
    if not gui_path:
        return {"ok": False, "msg": err}

    gui_text = io.open(gui_path, encoding="utf-8-sig", errors="replace").read()
    changed = False

    w = fields.get("width", fields.get("item_w"))
    h = fields.get("height", fields.get("item_h"))
    if w is not None or h is not None:
        sk = _find_top_skin(gui_text, "techtree_%s_item" % folder)
        if sk:
            s0, e0 = sk[0], sk[1]
            blk = gui_text[s0:e0]
            sbs, sbe = _block_body_range(blk)
            cw, ch = _parse_wh(_strip_keep_len(blk[sbs:sbe]), "size")
            nw = _to_int(w, _to_int(cw, 183) or 183) if w is not None else (_to_int(cw, 183) or 183)
            nh = _to_int(h, _to_int(ch, 84) or 84) if h is not None else (_to_int(ch, 84) or 84)
            blk2 = _replace_size_in_block(blk, "size", nw, nh)
            if blk2 != blk:
                gui_text = gui_text[:s0] + blk2 + gui_text[e0:]
                changed = True

    sw_i = fields.get("small_width")
    sh_i = fields.get("small_height")
    if sw_i is not None or sh_i is not None:
        sk_s = _find_top_skin(gui_text, "techtree_%s_small_item" % folder)
        if sk_s:
            s0, e0 = sk_s[0], sk_s[1]
            blk = gui_text[s0:e0]
            sbs, sbe = _block_body_range(blk)
            cw, ch = _parse_wh(_strip_keep_len(blk[sbs:sbe]), "size")
            nw = _to_int(sw_i, _to_int(cw, 72) or 72) if sw_i is not None else (_to_int(cw, 72) or 72)
            nh = _to_int(sh_i, _to_int(ch, 72) or 72) if sh_i is not None else (_to_int(ch, 72) or 72)
            blk2 = _replace_size_in_block(blk, "size", nw, nh)
            if blk2 != blk:
                gui_text = gui_text[:s0] + blk2 + gui_text[e0:]
                changed = True

    slot_w = fields.get("slot_w")
    slot_h = fields.get("slot_h")
    if slot_w is not None or slot_h is not None:
        tv = _find_tv_range(gui_text)
        if tv:
            pg = _find_tv_child(gui_text, tv[2], tv[3], folder)
            if pg:
                ps, pe = pg[0], pg[1]
                page_raw = gui_text[ps:pe]
                clean_pg = _strip_keep_len(page_raw)
                edits = []
                for k, s, e, _is_s, _is_e in _iter_block_children(page_raw, clean_pg):
                    if k.lower() == "gridboxtype":
                        gblk = page_raw[s:e]
                        gbs, gbe = _block_body_range(gblk)
                        cg = _strip_keep_len(gblk[gbs:gbe])
                        if _block_scalar(cg, "name") == "special_project_specialization_list":
                            continue
                        cw, ch = _parse_wh(cg, "slotsize")
                        nw = _to_int(slot_w, _to_int(cw, 70) or 70) if slot_w is not None else (_to_int(cw, 70) or 70)
                        nh = _to_int(slot_h, _to_int(ch, 70) or 70) if slot_h is not None else (_to_int(ch, 70) or 70)
                        gblk2 = _replace_size_in_block(gblk, "slotsize", nw, nh)
                        if gblk2 != gblk:
                            edits.append((s, e, gblk2))
                if edits:
                    for s, e, rep in reversed(edits):
                        page_raw = page_raw[:s] + rep + page_raw[e:]
                    gui_text = gui_text[:ps] + page_raw + gui_text[pe:]
                    changed = True

    if not changed:
        return {"ok": True, "msg": "节点皮肤与槽位尺寸未发生变化"}
    if not braces_balanced(gui_text):
        return {"ok": False, "msg": "countrytechtreeview.gui 括号不平衡，已中止"}
    snapshot(gui_path)
    _atomic_write(gui_path, gui_text.encode("utf-8"))
    return {"ok": True, "msg": "已更新 %s 节点皮肤/槽位尺寸" % folder}


def tech_category_add(root, cat_id, name_zh=""):
    """往 00_technology.txt 的 technology_categories 追加分类并可选写本地化。"""
    cat_id = (cat_id or "").strip()
    if not re.match(r'^[A-Za-z0-9_]+$', cat_id):
        return {"ok": False, "msg": "分类 id 只能字母数字下划线"}

    top, tag_path, err = _ensure_tags_file(root)
    if not tag_path:
        return {"ok": False, "msg": err}

    tag_text = io.open(tag_path, encoding="utf-8-sig", errors="replace").read()
    clean_tag = _strip_keep_len(tag_text)
    cat_blocks = find_blocks(clean_tag, "technology_categories")
    if not cat_blocks:
        tag_text = "technology_categories = {\n}\n\n" + tag_text
        clean_tag = _strip_keep_len(tag_text)
        cat_blocks = find_blocks(clean_tag, "technology_categories")

    cs, ce, cbody = cat_blocks[0]
    existing = set(re.findall(r'[A-Za-z][A-Za-z0-9_]*', cbody))
    already = cat_id in existing
    if not already:
        new_body = tag_text[cs + 1:ce - 1].rstrip() + "\n\t%s\n" % cat_id
        new_text = tag_text[:cs + 1] + new_body + tag_text[ce - 1:]
        if not braces_balanced(new_text):
            return {"ok": False, "msg": "00_technology.txt 括号不匹配，已中止"}
        snapshot(tag_path)
        _atomic_write(tag_path, new_text.encode("utf-8"))

    if name_zh:
        save_loc(top, {"simp_chinese": {cat_id: str(name_zh)}})

    return {"ok": True, "id": cat_id, "already": already,
            "msg": ("分类 %s 已存在" if already else "已添加科技分类 %s") % cat_id}
