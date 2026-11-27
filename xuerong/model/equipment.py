# -*- coding: utf-8 -*-
"""装备域（P0-3 D3 从 focus_editor.py 迁入）。

一行一个 `#!` 定义，读 common/equipment；写走 save/add/delete，落到可写层。

依赖边界：
  · EQUIPMENTS / LOC / CHANGED / GAME → xuerong.state
  · 文本改写 → core.text；叠加链 → core.paths
  · 本地化写 → model.loc.save_loc；写前快照 → model.history.snapshot
  · 唯一钩子：reload_data
"""
import io
import os
import re

from xuerong import state
from xuerong.core import paths
from xuerong.core.paths import (_layer_dirs, _top_mod, effective_layer_files,
                                ensure_writable_file, is_readonly_mod, is_under_game,
                                mod_layers, unique_editor_filename)
from xuerong.core.text import (_atomic_write, _bom_for, _strip_keep_len, brace_match,
                               braces_balanced, find_blocks, set_raw_block, set_scalar,
                               strip_comments, top_items)
from xuerong.model.history import snapshot
from xuerong.model.loc import save_loc

_RELOAD = None


def bind(reload_data):
    global _RELOAD
    _RELOAD = reload_data


def _reload():
    if _RELOAD:
        _RELOAD()


def _build_equip_entry(eid, inner_body, rel, src):
    clean = strip_comments(inner_body or "")
    yr = re.search(r'(?m)^\s*year\s*=\s*(\d+)', clean)
    bd = re.search(r'(?m)^\s*is_buildable\s*=\s*(\w+)', clean)
    props = {}
    for pk in ("year", "is_buildable", "type", "reliability", "maximum_speed",
               "defense", "breakthrough", "hardness", "soft_attack", "hard_attack",
               "air_attack", "armor", "piercing", "build_cost_ic",
               "is_archetype", "archetype", "can_be_produced", "group_by",
               "interface_category"):
        m2 = re.search(r'(?m)^\s*%s\s*=\s*([^\s#]+)' % pk, clean)
        if m2 and not m2.group(1).startswith("{"):
            props[pk] = m2.group(1)
    slots = []
    for sm in re.finditer(r'module_slots\s*=\s*\{', clean):
        sb = clean.find('{', sm.start())
        se = brace_match(clean, sb)
        sbody = clean[sb + 1:se - 1]
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
    return {
        "id": eid,
        "file": rel,
        "source": src,
        "name": state.loc().get(eid, eid),
        "year": yr.group(1) if yr else "",
        "buildable": bd.group(1) if bd else "",
        "slots": slots,
        "picture": (re.search(r'(?m)^\s*picture\s*=\s*"?([A-Za-z0-9_]+)"?', clean) or [None, ""])[1],
        "props": props,
        "raw": "%s = {\n%s\n}" % (eid, (inner_body or "").strip()),
    }


def equip_view(eid):
    e = state.equipments().get(eid)
    if not e:
        return None
    loc = state.loc()
    d = {k: v for k, v in e.items() if k != "raw"}
    d["slots"] = [dict(s, name=(loc.get("EQ_MOD_SLOT_" + s["slot"] + "_TITLE")
                                 or loc.get(s["slot"], s["slot"]))) for s in e.get("slots", [])]
    return d


def load_equipment(root):
    # 按 HOI4 实机规则读（respect replace_path 与同名文件整文件覆写，底层 → 顶层）。
    n = 0
    for base, d, fn in effective_layer_files("common/units/equipment", root):
        name = os.path.basename(base.rstrip("\\/")) or base
        rel = os.path.join("common", "units", "equipment", fn)
        try:
            with io.open(os.path.join(d, fn), encoding="utf-8-sig", errors="replace") as f:
                text = strip_comments(f.read())
        except Exception:
            continue
        for s, e, body in find_blocks(text, "equipments"):
            for k, v, b in top_items(body):
                if not b:
                    continue
                state.equipments()[k] = _build_equip_entry(k, v, rel, name)
                n += 1
    return n



def _equip_locate(root, eid):
    """找某个装备定义所在的文件与字符区间。

    装备都写在 equipments = { ... } 里，一个文件可以有多个 equipments 块。
    返回 (base, path, block_start, block_end, block_body)"""
    for base, d, fn in reversed(effective_layer_files("common/units/equipment", root)):
        p = os.path.join(d, fn)
        try:
            with io.open(p, encoding="utf-8-sig", errors="replace") as f:
                raw = f.read()
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



def _writable_top_for(root=None):
    """找当前解析链顶的可写 mod 目录（跳过原版与工坊只读目录）。"""
    if root:
        ab_exp = os.path.abspath(root)
        for r in reversed(state.roots() or []):
            lay = mod_layers(r) or [r]
            ab_lay = [os.path.abspath(x) for x in lay if x]
            if ab_exp in ab_lay:
                for cand in reversed(lay):
                    if cand and not is_readonly_mod(cand):
                        return cand
        for cand in reversed(mod_layers(root) or [root]):
            if cand and not is_readonly_mod(cand):
                return cand
    for r in reversed(state.roots() or []):
        lay = mod_layers(r) or [r]
        for cand in reversed(lay):
            if cand and not is_readonly_mod(cand):
                return cand
    if root:
        cand = _top_mod(root)
        if cand and not is_readonly_mod(cand):
            return cand
    return None


def equipment_detail(eid, root=None):
    """某个装备的完整信息：属性、模块槽、来源文件、是否可编辑"""
    explicit_root = root
    root = paths._pick(root)
    base, path, b, e, body = _equip_locate(root, eid)
    if not path:
        return {"ok": False, "msg": "找不到装备 %s" % eid}
    top = _writable_top_for(explicit_root or root)
    same_top = bool(top and base and os.path.normcase(os.path.abspath(base)) == os.path.normcase(os.path.abspath(top)))
    from_parent = bool(not same_top)
    readonly = not bool(top)
    src_name = os.path.basename((base or "").rstrip("\\/")) or (base or "")

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
    if root:
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
                        with io.open(p2, encoding="utf-8-sig", errors="replace") as fh:
                            t2 = fh.read()
                    except Exception:
                        continue
                    if re.search(r'\b%s\b' % re.escape(eid), t2):
                        refs.append(os.path.relpath(p2, root))
                        if len(refs) >= 20:
                            break

    src_note = ("，来自 " + src_name) if (from_parent and src_name) else ""
    return {"ok": True, "id": eid,
            "file": os.path.relpath(path, base) if base else path,
            "readonly": readonly,
            "from_parent": from_parent,
            "source": src_name,
            "archetype": scalars.get("archetype", ""),
            "year": scalars.get("year", ""),
            "buildable": scalars.get("is_buildable", ""),
            "name": state.loc().get(eid, eid),
            "scalars": scalars, "slots": slots, "refs": refs,
            "msg": "%s（%d 个属性，%d 个槽%s）" % (eid, len(scalars), len(slots), src_note)}



def equipment_edit(eid, props, root=None):
    """改装备的标量属性。

    props: {key: value}。key 已存在就改值，不存在就插入。
    块结构（module_slots / resources 等）不在这个接口的范围内，避免把嵌套写坏。"""
    explicit_root = root
    root = paths._pick(root)
    if not isinstance(props, dict) or not props:
        return {"ok": False, "msg": "没有要改的属性"}
    for k in props:
        ks = str(k).strip()
        if not re.match(r'^[a-z_0-9]+$', ks):
            return {"ok": False, "msg": "属性名不合法：%s" % ks}

    base, path, b, e, body = _equip_locate(root, eid)
    if not path:
        return {"ok": False, "msg": "找不到装备 %s" % eid}
    top = _writable_top_for(explicit_root or root)
    if not top:
        return {"ok": False, "msg": "这个装备来自只读层，且没有可写的 submod 目录"}

    new_body = body
    changed = []
    for k, v in props.items():
        k = str(k).strip()
        v = str(v).strip()
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

    need_adopt = (
        is_under_game(path)
        or is_readonly_mod(path)
        or not base
        or os.path.normcase(os.path.abspath(base)) != os.path.normcase(os.path.abspath(top))
    )
    if need_adopt:
        dst, err = ensure_writable_file(explicit_root or root, "common/units/equipment", os.path.basename(path))
        if not dst:
            return {"ok": False, "msg": err or "接管只读文件失败"}
        path = dst

    with io.open(path, encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()
    new_raw = raw[:b + 1] + new_body + raw[e - 1:]
    snapshot(path)
    _atomic_write(path, _bom_for(path) + new_raw.encode("utf-8"))
    _reload()
    return {"ok": True, "id": eid, "changed": changed,
            "msg": "已更新 %s：%s" % (eid, "，".join(changed))}



def equipment_delete(eid, root=None):
    """删除一个装备定义（摘掉整个块）"""
    explicit_root = root
    root = paths._pick(root)
    base, path, b, e, body = _equip_locate(root, eid)
    if not path:
        return {"ok": False, "msg": "找不到装备 %s" % eid}
    top = _writable_top_for(explicit_root or root)
    if (is_under_game(path)
            or is_readonly_mod(path)
            or not top
            or not base
            or os.path.normcase(os.path.abspath(base)) != os.path.normcase(os.path.abspath(top))):
        src_name = os.path.basename((base or "").rstrip("\\/")) or (base or "")
        return {"ok": False, "msg": "装备 %s 来自只读层或下层父 mod（%s），不能直接删除" % (eid, src_name)}
    # 引用检查：还有别的地方用就不让删
    det = equipment_detail(eid, root)
    refs = [r for r in (det.get("refs") or []) if not r.endswith(os.path.basename(path))]
    if refs:
        return {"ok": False,
                "msg": "还有 %d 处引用这个装备，先改掉再删：%s" % (len(refs), refs[:3])}
    with io.open(path, encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()
    start = raw.rfind("\n", 0, b)
    if start < 0:
        start = b
    new_raw = raw[:start] + raw[e:]
    snapshot(path)
    _atomic_write(path, _bom_for(path) + new_raw.encode("utf-8"))
    _reload()
    return {"ok": True, "id": eid,
            "msg": "已删除装备 %s" % eid}



def equipment_list(root=None, query=None):
    """装备列表（可按 id 或名字过滤）"""
    root = paths._pick(root)
    items = []
    q = (query or "").strip().lower()
    for k, v in sorted(state.equipments().items()):
        nm = v.get("name") or k
        if q and q not in k.lower() and q not in str(nm).lower():
            continue
        items.append({"id": k, "name": nm, "file": v.get("file", ""),
                      "year": v.get("year", ""), "buildable": v.get("buildable", ""),
                      "archetype": (v.get("props") or {}).get("archetype", "")})
    return {"ok": True, "count": len(items), "items": items[:400],
            "total": len(items), "msg": "共 %d 个装备%s" % (
                len(items), ("（含 %s）" % query) if q else "")}



# ---------------- 装备 ----------------
def save_equipment(root, rel, eid, raw, name="", desc="", name_ja="", desc_ja="", props=None,
                   name_en="", desc_en="", picture=""):
    if not rel or not eid:
        return False, "参数不完整：缺少文件或装备 id"
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_readonly_mod(cand):
            top = cand
    if not top and root:
        cand = _top_mod(root)
        if cand and not is_readonly_mod(cand):
            top = cand
    need_adopt = (
        not root
        or is_under_game(root)
        or is_readonly_mod(root)
        or (bool(top) and os.path.normcase(os.path.abspath(top)) != os.path.normcase(os.path.abspath(root)))
    )
    path = os.path.join(root, rel) if root else ""
    if need_adopt or not path or not os.path.isfile(path):
        rel_n = rel.replace("\\", "/").strip("/")
        sub = os.path.dirname(rel_n)
        basename = os.path.basename(rel_n)
        if not sub or not basename:
            return False, "找不到文件：" + str(rel)
        path, err = ensure_writable_file(root, sub, basename)
        if not path:
            return False, err
        root = top or root
    with io.open(path, "rb") as f:
        raw_bytes = f.read()
    text = raw_bytes.decode("utf-8-sig" if raw_bytes.startswith(b"\xef\xbb\xbf") else "utf-8", errors="replace")
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
    new_text = text[:m.start()] + raw.strip() + "\n" + text[e:]
    _atomic_write(path, _bom_for(path) + new_text.encode("utf-8"))
    state.changed()[path] = rel
    ents = {}
    if name: ents.setdefault("simp_chinese", {})[eid] = name
    if desc: ents.setdefault("simp_chinese", {})[eid + "_desc"] = desc
    if name_ja: ents.setdefault("japanese", {})[eid] = name_ja
    if desc_ja: ents.setdefault("japanese", {})[eid + "_desc"] = desc_ja
    if name_en: ents.setdefault("english", {})[eid] = name_en
    if desc_en: ents.setdefault("english", {})[eid + "_desc"] = desc_en
    if ents:
        save_loc(root, ents)
    rb = raw.find("{")
    re_idx = raw.rfind("}")
    inner_body = raw[rb + 1:re_idx] if (rb >= 0 and re_idx > rb) else raw
    src = os.path.basename((root or "").rstrip("\\/")) or root
    state.equipments()[eid] = _build_equip_entry(eid, inner_body, rel, src)
    return True, "装备已保存"



def _ensure_script_enum_equipment(root, eid):
    """确保新装备 id 登记在 script_enum_equipment_bonus_type，避免 HOI4 启动报错。"""
    src, _ = paths._layers_find("common/script_enums.txt", paths.mod_layers(root))
    if not src or not os.path.isfile(src):
        return
    dst = os.path.join(root, "common", "script_enums.txt")
    if not os.path.isfile(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with io.open(src, "rb") as f:
            raw = f.read()
        _atomic_write(dst, raw)
    with io.open(dst, encoding="utf-8-sig", errors="replace", newline="") as f:
        txt = f.read()
    m = re.search(r'(?m)^\s*script_enum_equipment_bonus_type\s*=\s*\{', txt)
    if not m:
        return
    b = txt.find("{", m.start())
    e = brace_match(txt, b)
    body = txt[b + 1:e - 1]
    if re.search(r'(?m)^\s*%s(?:\s|$|#)' % re.escape(eid), body):
        return
    snapshot(dst)
    with io.open(dst, "rb") as f:
        has_bom = f.read(3) == b"\xef\xbb\xbf"
    new_txt = txt[:e - 1].rstrip("\r\n") + "\n\t%s\n" % eid + txt[e - 1:]
    _atomic_write(dst, (b"\xef\xbb\xbf" if has_bom else b"") + new_txt.encode("utf-8"))
    state.changed()[dst] = os.path.join("common", "script_enums.txt")


def add_equipment(root, eid):
    if not re.match(r'^[A-Za-z0-9_]+$', eid or ""):
        return False, "id 只能字母数字下划线"
    d = os.path.join(root, "common", "units", "equipment")
    os.makedirs(d, exist_ok=True)
    fn = unique_editor_filename(root, "common/units/equipment", "zz_focus_editor_equipment.txt")
    path = os.path.join(d, fn)
    if os.path.exists(path):
        with io.open(path, encoding="utf-8", errors="replace", newline="") as f:
            text = f.read()
    else:
        text = "equipments = {\n}\n"
    if re.search(r'(?m)^\s*%s\s*=\s*\{' % re.escape(eid), text):
        return False, "装备已存在"
    brace = text.find('{', text.find("equipments"))
    end = brace_match(text, brace)
    block = ("\n\t%s = {\n\t\tyear = 1936\n\t\tis_buildable = yes\n\t\ttype = infantry\n"
             "\t\tbuild_cost_ic = 1.0\n\t}\n" % eid)
    snapshot(path)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text[:end - 1] + block + text[end - 1:])
    rel = os.path.join("common", "units", "equipment", fn)
    state.changed()[path] = rel
    _ensure_script_enum_equipment(root, eid)
    ib = block.find("{")
    ie = block.rfind("}")
    inner_body = block[ib + 1:ie]
    src = os.path.basename((root or "").rstrip("\\/")) or root
    state.equipments()[eid] = _build_equip_entry(eid, inner_body, rel, src)
    return True, "已新建装备 " + eid



def delete_equipment(root, rel, eid):
    if not rel or not eid:
        return False, "参数不完整"
    path = os.path.join(root, rel) if root else ""
    if not path or not os.path.isfile(path):
        return False, "找不到文件：" + str(rel)
    with io.open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        text = f.read()
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % re.escape(eid), text)
    if not m:
        return False, "未找到装备 " + eid
    b = text.find('{', m.start())
    e = brace_match(text, b)
    snapshot(path)
    _atomic_write(path, _bom_for(path) + (text[:m.start()] + text[e:]).encode("utf-8"))
    state.changed()[path] = rel
    equips = state.equipments()
    equips.pop(eid, None)
    roots = list(state.roots() or [])
    if not roots and root:
        roots = [root]
    for r in reversed(roots):
        hit = False
        for base, d, fn in reversed(effective_layer_files("common/units/equipment", r)):
            src_l = os.path.basename((base or "").rstrip("\\/")) or base
            fp = os.path.join(d, fn)
            try:
                with io.open(fp, encoding="utf-8-sig", errors="replace", newline="") as f:
                    raw = f.read()
            except Exception:
                continue
            if eid not in raw:
                continue
            rel_l = os.path.join("common", "units", "equipment", fn)
            text_l = strip_comments(raw)
            for _s, _e, body in find_blocks(text_l, "equipments"):
                for k, v, kb in top_items(body):
                    if kb and k == eid:
                        equips[eid] = _build_equip_entry(eid, v, rel_l, src_l)
                        hit = True
                        break
                if hit:
                    break
            if hit:
                break
        if hit:
            break
    return True, "已删除装备 " + eid
