# -*- coding: utf-8 -*-
"""部队：读取师模板 / OOB，写模板与单位，模板渲染。

依赖 _inj 之外无兄弟模块；template_add / unit_add 只在自己文件内调
load_units / _oob_files / _units_write_base / _tpl_render。
"""
import io
import os
import re

from xuerong.core.paths import _layer_files, _top_mod, mod_layers, write_base
from xuerong.core.text import (_atomic_write, _bom_for, _first, _strip_keep_len, brace_match,
                               find_blocks, top_items)
from xuerong.model.history import snapshot
from xuerong.model.map import _map_pick

# load_units 的缓存：只在本模块用，不跨模块（原样从门面搬来）
_UNITS_CACHE = {"root": "", "mtime": 0, "templates": [], "divisions": []}


def _units_write_base(root):
    """算 history/units 的写入层，并拒绝写进父 mod。

    replace_path 独占时 write_base 会返回父 mod。直接往那里写就是污染别人的 mod，
    必须先用自己的 mod 接管该目录。
    返回 (路径, 错误消息)。
    """
    top = _top_mod(root)
    if not top:
        return None, "找不到可写的 mod 目录"
    tgt, why = write_base(root, "history/units")
    if not tgt:
        return None, "找不到可写目录"
    if os.path.abspath(tgt) != os.path.abspath(top):
        nm = os.path.basename(tgt.rstrip("\\/")) or tgt
        return None, ("history/units 被 %s 的 replace_path 独占，"
                      "直接写进去会改坏它。请先在「诊断 → 目录写入目标」里接管该目录" % nm)
    return tgt, ""


def _units_files(root):
    """叠加链里所有 history/units/*.txt，按「后加载覆盖」去重文件名。

    返回 (该目录的写入基准层, 文件列表)。_layer_files 只给文件，基准层按
    history/units 的 write_base 算。"""
    files, _replaced = _layer_files("history/units", mod_layers(root))
    base, _why = write_base(root, "history/units")
    return base, files


def _parse_division_template(body, rel, src):
    """解析一个 division_template 块。"""
    name = _first(body, r'(?m)^\s*name\s*=\s*"([^"]*)"')
    locked = bool(re.search(r'(?m)^\s*is_locked\s*=\s*yes', body))
    regs, sup = [], []
    rm = re.search(r'regiments\s*=\s*\{', body)
    if rm:
        rb = body.find("{", rm.end() - 1)
        re_ = brace_match(body, rb)
        if re_ > rb:
            for k, v, b in top_items(body[rb + 1:re_ - 1]):
                if not b:
                    continue
                x = _first(v, r'(?m)^\s*x\s*=\s*(-?\d+)', "0")
                y = _first(v, r'(?m)^\s*y\s*=\s*(-?\d+)', "0")
                regs.append({"unit": k, "x": int(x), "y": int(y)})
    sm = re.search(r'support\s*=\s*\{', body)
    if sm:
        sb = body.find("{", sm.end() - 1)
        se = brace_match(body, sb)
        if se > sb:
            for k, v, b in top_items(body[sb + 1:se - 1]):
                if not b:
                    continue
                x = _first(v, r'(?m)^\s*x\s*=\s*(-?\d+)', "0")
                y = _first(v, r'(?m)^\s*y\s*=\s*(-?\d+)', "0")
                sup.append({"unit": k, "x": int(x), "y": int(y)})
    return {"name": name, "locked": locked, "regiments": regs, "support": sup,
            "file": rel, "source": src,
            "regiment_count": len(regs), "support_count": len(sup)}


def _parse_division(body, rel, src, idx):
    """解析 units 里的一个 division 块。"""
    return {
        "i": idx,
        "name": _first(body, r'(?m)^\s*name\s*=\s*"([^"]*)"'),
        "location": int(_first(body, r'(?m)^\s*location\s*=\s*(\d+)', "0") or 0),
        "template": _first(body, r'(?m)^\s*division_template\s*=\s*"([^"]*)"'),
        "exp": _first(body, r'(?m)^\s*start_experience_factor\s*=\s*([\d.]+)', ""),
        "eq": _first(body, r'(?m)^\s*start_equipment_factor\s*=\s*([\d.]+)', ""),
        "file": rel, "source": src,
    }


def load_units(root=None, force=False):
    """解析叠加链里的 division_template 与 units（开局部队）。

    返回 {templates: [...], divisions: [...], templates_total, divisions_total}
    """
    root = _map_pick(root)
    base, files, mt, key = None, [], 0, ""
    try:
        base, files = _units_files(root)
        mt = max([os.path.getmtime(p) for p in files] or [0])
        key = os.path.abspath(base or "")
        if (not force and _UNITS_CACHE["root"] == key
                and _UNITS_CACHE["mtime"] == mt and mt):
            return _UNITS_CACHE
    except Exception:
        files = []
    templates, divisions = [], []
    seen_tpl = {}
    seen_div = 0
    for p in (files or []):
        fn = os.path.basename(p)
        rel = os.path.join("history", "units", fn)
        src = ""
        try:
            for b in (mod_layers(root) or []):
                if os.path.abspath(p).startswith(os.path.abspath(b) + os.sep):
                    src = os.path.basename(b.rstrip("\\/")) or b
                    break
        except Exception:
            pass
        try:
            raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        text = _strip_keep_len(raw)
        for a, b2, body in find_blocks(text, "division_template"):
            rec = _parse_division_template(body, rel, src)
            if not rec["name"]:
                continue
            seen_tpl[rec["name"]] = rec
        # units 段：一个文件可能有多个
        for um in re.finditer(r'(?m)^[ \t]*units[ \t]*=\s*\{', text):
            ub = text.find("{", um.end() - 1)
            ue = brace_match(text, ub)
            if ue <= ub:
                continue
            for dm in re.finditer(r'(?m)^[ \t]*division[ \t]*=\s*\{', text[ub + 1:ue - 1]):
                db = text.find("{", ub + 1 + dm.end() - 1)
                de = brace_match(text, db)
                if de <= db:
                    continue
                rec = _parse_division(text[db + 1:de - 1], rel, src, seen_div)
                seen_div += 1
                if rec["location"] or rec["template"]:
                    divisions.append(rec)
    templates = sorted(seen_tpl.values(), key=lambda x: x["name"])
    out = {"root": os.path.abspath(base or ""),
           "templates": templates, "divisions": divisions,
           "templates_total": len(templates), "divisions_total": len(divisions),
           "by_prov": {}}
    for d in divisions:
        k = str(d["location"])
        out["by_prov"].setdefault(k, []).append(d)
    _UNITS_CACHE.update(out)
    return out


def _oob_files(root, tag, kind="land"):
    """读国家历史里点名要加载的 OOB 文件名（不含 .txt）。

    HOI4 不扫描 history/units 目录，而是由 history/countries/<TAG> 里的
    set_oob / oob / set_air_oob / set_naval_oob 逐条点名加载。
    自己起个文件名写进去，游戏根本不会读。

    同一个国家常有 DLC 分支（有/没有 Man the Guns 各一套），
    返回全部，调用方对每个都追加才保险。
    """
    tag = (tag or "").strip().upper()
    if not tag:
        return []
    keys = {
        "land":  ("set_oob", "oob"),
        "air":   ("set_air_oob", "air_oob"),
        "naval": ("set_naval_oob", "naval_oob"),
    }.get(kind) or ("set_oob", "oob")

    hist = None
    for b in reversed(mod_layers(root) or []):
        if not b:
            continue
        hd = os.path.join(b, "history", "countries")
        if not os.path.isdir(hd):
            continue
        for fn in sorted(os.listdir(hd)):
            if fn.upper().startswith(tag + " ") and fn.endswith(".txt"):
                hist = os.path.join(hd, fn)
                break
        if hist:
            break
    if not hist:
        return []
    try:
        txt = io.open(hist, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return []

    all_names = []
    for k in keys:
        for m in re.finditer(r'(?m)^\s*' + k + r'\s*=\s*"([^"]+)"', txt):
            nm = m.group(1).strip()
            if nm and nm not in all_names:
                all_names.append(nm)
    if not all_names:
        return []
    # 只保留和第一条同年份的：GER_1936 和 GER_1936_nsb 是一组（DLC 分支），
    # GER_1939 是 1939 剧本的，改了没意义还会污染。
    first = all_names[0]
    yr = re.search(r'(\d{4})', first)
    if not yr:
        return [first]
    y = yr.group(1)
    return [n for n in all_names if y in n]


def _tpl_render(name, regs, sup, locked, indent="\t", with_key=True):
    """生成一个 division_template 文本。

    with_key=False 时只从 { 开始 —— 替换已有块时用
    （find_blocks 返回的偏移指向 { 的位置，块文本不能再带 division_template =）。
    """
    out = [("division_template = " if with_key else "") + "{\n"]
    out.append('%sname = "%s"\n' % (indent, name))
    if locked:
        out.append("%sis_locked = yes\n" % indent)
    if regs:
        out.append("%sregiments = {\n" % indent)
        for r in regs:
            out.append("%s\t%s = { x = %d y = %d }\n" % (
                indent, r["unit"], int(r.get("x") or 0), int(r.get("y") or 0)))
        out.append("%s}\n" % indent)
    if sup:
        out.append("%ssupport = {\n" % indent)
        for r in sup:
            out.append("%s\t%s = { x = %d y = %d }\n" % (
                indent, r["unit"], int(r.get("x") or 0), int(r.get("y") or 0)))
        out.append("%s}\n" % indent)
    out.append("}\n")
    return "".join(out)


def template_add(name, unit, x=0, y=0, root=None, tag=None):
    """新建一个只有一格编制的 division_template。"""
    root = _map_pick(root)
    if not name:
        return {"ok": False, "msg": "模板名不能为空"}
    tgt, err = _units_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    d = os.path.join(tgt, "history", "units")
    os.makedirs(d, exist_ok=True)
    tag = (tag or "").strip().upper()
    _oobs = _oob_files(root, tag, "land") if tag else []
    if _oobs:
        # 模板必须和部队进同一个被点名的 OOB 文件，自起文件名游戏不读
        p = os.path.join(d, _oobs[0] + ".txt")
        if not os.path.exists(p):
            for b2 in reversed(mod_layers(tgt) or []):
                if not b2:
                    continue
                cand = os.path.join(b2, "history", "units", _oobs[0] + ".txt")
                if os.path.isfile(cand):
                    try:
                        import shutil as _sh7
                        _sh7.copyfile(cand, p)
                    except Exception:
                        pass
                    break
    elif tag:
        p = os.path.join(d, "%s_1936_zz.txt" % tag)
    else:
        p = os.path.join(d, "zz_units.txt")
    block = _tpl_render(name, [{"unit": unit or "infantry", "x": x, "y": y}], [], False)
    if os.path.exists(p):
        raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
    else:
        raw = ""
    new_text = (raw.rstrip() + "\n\n" if raw.strip() else "") + block
    if os.path.exists(p):
        snapshot(p)
    _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))
    load_units(root, force=True)
    return {"ok": True, "msg": "已新建模板「%s」" % name}


def unit_add(location, template, name=None, exp=None, eq=None, root=None, tag=None):
    """在某省加一支开局部队。"""
    root = _map_pick(root)
    try:
        location = int(location)
    except Exception:
        return {"ok": False, "msg": "省份号不合法"}
    if location <= 0:
        return {"ok": False, "msg": "省份号不合法"}
    u = load_units(root)
    tpl_names = {t["name"] for t in u["templates"]}
    if template not in tpl_names:
        return {"ok": False, "msg": "没有这个师团模板：%s" % template}

    # 写到当前 mod 的 history/units（拒写父 mod）
    tgt, _err = _units_write_base(root)
    if not tgt:
        return {"ok": False, "msg": _err}
    d = os.path.join(tgt, "history", "units")
    os.makedirs(d, exist_ok=True)
    tag = (tag or "").strip().upper()
    _oobs = _oob_files(root, tag, "land") if tag else []
    if _oobs:
        # 写进国家历史点名的那个 OOB 文件（DLC 分支可能有多个，每个都写）
        p = os.path.join(d, _oobs[0] + ".txt")
        # 这个文件名和原版同名，直接写会把原版几百支部队全覆盖掉。
        # 先把原版那份复制过来，再往里面追加。
        if not os.path.exists(p):
            for b in reversed(mod_layers(tgt) or []):
                if not b:
                    continue
                cand = os.path.join(b, "history", "units", _oobs[0] + ".txt")
                if os.path.isfile(cand):
                    try:
                        import shutil as _sh4
                        _sh4.copyfile(cand, p)
                    except Exception:
                        pass
                    break
    elif tag:
        p = os.path.join(d, "%s_1936_zz.txt" % tag)
    else:
        p = os.path.join(d, "zz_units.txt")

    lines = ["\tdivision = {\n"]
    # 原版用的是 division_name = { is_name_ordered = yes / 或者具体 name }，
    # 直接写 name = "xxx" 游戏不认这个字段。
    if name:
        lines.append('\t\tdivision_name = {\n')
        lines.append('\t\t\tname = "%s"\n' % name.replace('"', ""))
        lines.append('\t\t}\n')
    else:
        lines.append('\t\tdivision_name = {\n')
        lines.append('\t\t\tis_name_ordered = yes\n')
        lines.append('\t\t\tname_order = 1\n')
        lines.append('\t\t}\n')
    lines.append("\t\tlocation = %d\n" % location)
    lines.append('\t\tdivision_template = "%s"\n' % template)
    lines.append("\t\tstart_experience_factor = %s\n" % (exp if exp not in (None, "") else "0.3"))
    lines.append("\t\tstart_equipment_factor = %s\n" % (eq if eq not in (None, "") else "1"))
    lines.append("\t}\n")
    block = "".join(lines)

    if os.path.exists(p):
        raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
    else:
        raw = "units = {\n}\n"
    text = _strip_keep_len(raw)
    um = re.search(r'(?m)^[ \t]*units[ \t]*=\s*\{', text)
    if um:
        ub = text.find("{", um.end() - 1)
        ue = brace_match(text, ub)
        if ue > ub:
            new_text = raw[:ue - 1] + block + raw[ue - 1:]
        else:
            new_text = raw.rstrip() + "\nunits = {\n" + block + "}\n"
    else:
        new_text = raw.rstrip() + "\nunits = {\n" + block + "}\n"

    snapshot(p) if os.path.exists(p) else None
    _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))
    # 其它 DLC 分支的 OOB 也补一份，否则换 DLC 组合部队就没了
    for _nm in _oobs[1:]:
        _p2 = os.path.join(d, _nm + ".txt")
        if not os.path.exists(_p2):
            for b in reversed(mod_layers(tgt) or []):
                if not b:
                    continue
                cand = os.path.join(b, "history", "units", _nm + ".txt")
                if os.path.isfile(cand):
                    try:
                        import shutil as _sh5
                        _sh5.copyfile(cand, _p2)
                    except Exception:
                        pass
                    break
        if os.path.exists(_p2):
            _raw2 = io.open(_p2, encoding="utf-8-sig", errors="replace").read()
        else:
            _raw2 = "units = {\n}\n"
        _t2 = _strip_keep_len(_raw2)
        _um2 = re.search(r'(?m)^[ \t]*units[ \t]*=\s*\{', _t2)
        if _um2:
            _ub2 = _t2.find("{", _um2.end() - 1)
            _ue2 = brace_match(_t2, _ub2)
            if _ue2 > _ub2:
                _new2 = _raw2[:_ue2 - 1] + block + _raw2[_ue2 - 1:]
            else:
                _new2 = _raw2.rstrip() + "\nunits = {\n" + block + "}\n"
        else:
            _new2 = _raw2.rstrip() + "\nunits = {\n" + block + "}\n"
        if os.path.exists(_p2):
            snapshot(_p2)
        _atomic_write(_p2, _bom_for(_p2) + _new2.encode("utf-8"))

    load_units(root, force=True)
    return {"ok": True, "file": os.path.relpath(p, tgt),
            "msg": "已在省 %d 布置 1 支 %s" % (location, template)}
