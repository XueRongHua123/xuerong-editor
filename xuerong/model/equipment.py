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
from xuerong.core.paths import _layer_dirs, mod_layers
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
                  state.equipments()[k] = {"id": k, "file": rel, "source": name,
                                   "name": state.loc().get(k, k),
                                   "year": yr.group(1) if yr else "",
                                   "buildable": bd.group(1) if bd else "",
                                   "slots": slots,
                                   "picture": (re.search(r'(?m)^\s*picture\s*=\s*"?([A-Za-z0-9_]+)"?', v) or [None, ""])[1],
                                   "props": props,
                                   "raw": "%s = {\n%s\n}" % (k, v.strip())}
                  n += 1
    return n



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
    root = paths._pick(root)
    base, path, b, e, body = _equip_locate(root, eid)
    if not path:
        return {"ok": False, "msg": "找不到装备 %s" % eid}
    readonly = os.path.abspath(base) == os.path.abspath(state.game() or "")

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
            "name": state.loc().get(eid, eid),
            "scalars": scalars, "slots": slots, "refs": refs,
            "msg": "%s（%d 个属性，%d 个槽）" % (eid, len(scalars), len(slots))}



def equipment_edit(eid, props, root=None):
    """改装备的标量属性。

    props: {key: value}。key 已存在就改值，不存在就插入。
    块结构（module_slots / resources 等）不在这个接口的范围内，避免把嵌套写坏。"""
    root = paths._pick(root)
    if not isinstance(props, dict) or not props:
        return {"ok": False, "msg": "没有要改的属性"}
    base, path, b, e, body = _equip_locate(root, eid)
    if not path:
        return {"ok": False, "msg": "找不到装备 %s" % eid}
    if os.path.abspath(base) == os.path.abspath(state.game() or ""):
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
    _atomic_write(path, _bom_for(path) + new_raw.encode("utf-8"))
    _reload()
    return {"ok": True, "id": eid, "changed": changed,
            "msg": "已更新 %s：%s" % (eid, "，".join(changed))}



def equipment_delete(eid, root=None):
    """删除一个装备定义（摘掉整个块）"""
    root = paths._pick(root)
    base, path, b, e, body = _equip_locate(root, eid)
    if not path:
        return {"ok": False, "msg": "找不到装备 %s" % eid}
    if os.path.abspath(base) == os.path.abspath(state.game() or ""):
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
    _reload()
    return True, "装备已保存"



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
    state.changed()[path] = os.path.join("common", "units", "equipment", "zz_focus_editor_equipment.txt")
    _reload()
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
    state.changed()[path] = rel
    _reload()
    return True, "已删除装备 " + eid
