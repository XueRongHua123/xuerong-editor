# -*- coding: utf-8 -*-
"""世界创建（world）域（P2-rest 第 4 域，从 focus_editor.py 迁入）。

29 个函数，按功能分五组：
  编排        world_create（275 行：地图 → tag → 州 → 国家历史 → 军队 → 本地化 → 剧本）
  国家 tag    load_country_tags / _country_tags_write_base / country_tag_refs /
              country_tag_add / country_tag_delete / country_history_create
  剧本        _bookmark_write_base / _bookmark_date / _bookmark_country_block /
              _game_language / _bookmark_loc / bookmark_add
  部队        _units_write_base / _units_files / _parse_division_template / _parse_division /
              load_units / _oob_files / _tpl_render / template_add / unit_add
  本地化      _loc_need_keys / _loc_defined_set / loc_missing / loc_generate
  建 mod      mod_home / create_mod
  地图辅助    _centroids_from_map

任务书只列了 17 个，另外 12 个是反向闭包（bookmark/units/country_tags/loc 各自的内部分解），
不带就得反向 import 门面。

依赖边界：
  · ROOTS / STATES / TREES / LOC / PROV_RGB → xuerong.state 访问器
  · _states_dir_for_write / state_create → model/state；map_generate / _map_pick /
    _ensure_prov_rgb → model/map；snapshot → model/history
  · _UNITS_CACHE 只被 load_units 用，模块级缓存放本文件
  · 四个横切口由门面 bind()：reload_data / load_mod / _qa_dir / _lp_done
  · world_create 里 import 的 world_leader / focus_gen / world_events / world_loc /
    mapgen_scaffold 都是函数内 import，原样保留
"""
import hashlib
import io
import os
import re

from xuerong import state
from xuerong.core.paths import (_LAYERS_CACHE, _layer_files, _mod_descriptor, _top_mod,
                                is_under_game, mod_layers, write_base)
from xuerong.core.text import (_atomic_write, _bom_for, _first, _strip_keep_len, brace_match,
                               find_blocks, strip_comments, top_items)
from xuerong.model.history import snapshot
from xuerong.model.map import _ensure_prov_rgb, _map_pick, map_generate
from xuerong.model.state import _states_dir_for_write, state_create

# load_units 的缓存：只在本模块用，不跨模块（原样从门面搬来）
_UNITS_CACHE = {"root": "", "mtime": 0, "templates": [], "divisions": []}

# ---------------------------------------------------------------- 门面回注
_INJ = {}


def bind(**kw):
    _INJ.update(kw)


def _reload():
    f = _INJ.get("reload_data")
    if f:
        f()


def _load_mod(*a, **k):
    return _INJ["load_mod"](*a, **k)


def _qa_dir(*a, **k):
    return _INJ["_qa_dir"](*a, **k)


def _lp_done(*a, **k):
    return _INJ["_lp_done"](*a, **k)


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



def load_country_tags(root=None):
    """解析 common/country_tags 里的所有 tag。

    格式：
        BET = "countries/BETA.txt"
        H00 = "countries/H00.txt"
        dynamic_tags  = yes          ← 特殊行，不是 tag
    """
    root = _map_pick(root)
    files, _rep = _layer_files("common/country_tags", mod_layers(root))
    out, seen = [], {}
    dyn = False
    for p in (files or []):
        fn = os.path.basename(p)
        try:
            raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        text = _strip_keep_len(raw)
        for ln in text.splitlines():
            s0 = ln.strip()
            if not s0 or s0.startswith("#"):
                continue
            if re.match(r'(?i)dynamic_tags\s*=\s*yes', s0):
                dyn = True
                continue
            m = re.match(r'([A-Z0-9_]{2,8})\s*=\s*"([^"]+)"', s0)
            if m:
                seen[m.group(1)] = {"tag": m.group(1), "def": m.group(2), "file": fn}
    out = sorted(seen.values(), key=lambda x: x["tag"])
    return {"ok": True, "items": out, "count": len(out), "dynamic": dyn,
            "msg": "共 %d 个 tag%s" % (len(out), "，含动态 tag 段" if dyn else "")}



def _country_tags_write_base(root):
    """common/country_tags 的写入层，拒写父 mod。

    先按传入的 root 解析叠加链，再退回全局 ROOTS。
    只看 ROOTS 的话，直接调用（脚本、world_create 这类编排）会因为没有
    全局状态而误报「找不到可写的 mod 目录」，哪怕 root 本身完全可写。
    """
    top = None
    if root:
        lay = mod_layers(root) or [root]
        cand = lay[-1] if lay else root
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        for r in (state.roots() or []):
            lay = mod_layers(r) or [r]
            cand = lay[-1] if lay else r
            if cand and not is_under_game(cand):
                top = cand
    if not top:
        return None, "找不到可写的 mod 目录"
    tgt, why = write_base(root, "common/country_tags")
    if not tgt:
        return None, "找不到可写目录"
    if os.path.abspath(tgt) != os.path.abspath(top):
        nm = os.path.basename(tgt.rstrip("\\/")) or tgt
        return None, ("common/country_tags 被 %s 的 replace_path 独占，"
                      "直接写进去会改坏它。请先在「诊断 → 目录写入目标」里接管该目录" % nm)
    return tgt, ""



def country_tag_refs(root, tag):
    """统计一个 tag 在哪些地方被引用，删之前先看清楚。"""
    root = _map_pick(root)
    tag = (tag or "").upper()
    refs = {"states_owner": 0, "states_core": 0, "history_files": [], "trees": []}
    try:
        for sid, sty in (state.states() or {}).items():
            if (sty.get("owner") or "").upper() == tag:
                refs["states_owner"] += 1
            if tag in [x.upper() for x in (sty.get("cores") or [])]:
                refs["states_core"] += 1
    except Exception:
        pass
    try:
        files, _r = _layer_files("history/countries", mod_layers(root))
        for p in (files or []):
            fn = os.path.basename(p)
            m = re.match(r'([A-Z0-9_]{2,8})\s*-', fn.upper())
            if m and m.group(1) == tag:
                refs["history_files"].append(fn)
    except Exception:
        pass
    try:
        for tid, t in (state.trees() or {}).items():
            tags = [x.upper() for x in (t.get("country_tags") or [])]
            if tag in tags:
                refs["trees"].append(tid)
    except Exception:
        pass
    total = refs["states_owner"] + refs["states_core"] + len(refs["history_files"]) + len(refs["trees"])
    return {"tag": tag, "refs": refs, "total": total,
            "msg": "%s 被引用 %d 处（州归属 %d、核心 %d、国家历史 %d、国策树 %d）" % (
                tag, total, refs["states_owner"], refs["states_core"],
                len(refs["history_files"]), len(refs["trees"]))}



def country_tag_add(root, tag, color=None, culture="western_european_gfx"):
    """新建国家 tag。

    culture 必须在这里兜一次底：路由是 `body.get("culture")` 直传，
    前端不发这个字段时拿到 None，显式传入会盖掉默认值，下面
    `culture.replace("_gfx", "_2d")` 立刻 AttributeError → 接口 500。
    """
    culture = culture or "western_european_gfx"

    root = _map_pick(root)
    tag = (tag or "").upper().strip()
    if not re.match(r'^[A-Z][A-Z0-9]{1,3}$', tag):
        return {"ok": False, "msg": "tag 格式不对（1 位字母 + 1-3 位字母数字，如 GER、UNI）"}
    cur = load_country_tags(root)
    if any(x["tag"] == tag for x in cur["items"]):
        return {"ok": False, "msg": "已经有 %s 这个 tag 了" % tag}

    rgb = color
    if not rgb:
        # 用 tag 的哈希生成一个稳定颜色
        h = int(hashlib.md5(tag.encode()).hexdigest()[:6], 16)
        rgb = [60 + (h >> 16) % 160, 60 + (h >> 8) % 160, 60 + h % 160]
    try:
        rgb = [int(x) for x in rgb][:3]
        if len(rgb) != 3:
            raise ValueError
        rgb = [max(0, min(255, x)) for x in rgb]
    except Exception:
        return {"ok": False, "msg": "颜色要三个 0-255 的整数"}

    tgt, err = _country_tags_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}

    # 1) country_tags 追加
    d = os.path.join(tgt, "common", "country_tags")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "zz_editor_tags.txt")
    line = '%s = "countries/%s.txt"\n' % (tag, tag)
    if os.path.exists(p):
        raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
        if not raw.endswith("\n"):
            raw += "\n"
        new_text = raw + line
    else:
        new_text = line
    if os.path.exists(p):
        snapshot(p)
    _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))

    # 2) common/countries 定义
    cd = os.path.join(tgt, "common", "countries")
    os.makedirs(cd, exist_ok=True)
    cp = os.path.join(cd, tag + ".txt")
    body = ("graphical_culture = %s\ngraphical_culture_2d = %s\n\n"
            "color = { %d %d %d }\n") % (
        culture, culture.replace("_gfx", "_2d"), rgb[0], rgb[1], rgb[2])
    if not os.path.exists(cp):
        _atomic_write(cp, _bom_for(cp) + body.encode("utf-8"))

    try:
        _LAYERS_CACHE.clear()
    except Exception:
        pass
    _reload()
    return {"ok": True, "tag": tag, "color": rgb, "file": "zz_editor_tags.txt",
            "msg": "已加 tag %s（颜色 %d,%d,%d，定义 countries/%s.txt）" % (
                tag, rgb[0], rgb[1], rgb[2], tag)}



def country_history_create(root, tag, capital=1, ruling_party="neutrality",
                           name=None, oob=None, research_slots=3):
    """给新 tag 写 history/countries/<TAG> - <Name>.txt。

    country_tag_add 只写 common/country_tags 和 common/countries，
    不写 history —— 新国家在游戏里就是「没有首都、没有政府、没有科技」的空壳。
    这个函数补的就是这一层，格式照原版最简国家（如 NWF）写。
    """
    root = _map_pick(root)
    tag = (tag or "").upper().strip()
    if not re.match(r'^[A-Z][A-Z0-9]{1,3}$', tag):
        return {"ok": False, "msg": "tag 格式不对（如 GER、UNI）"}
    top, _states = _states_dir_for_write(root)
    if not top:
        return {"ok": False, "msg": "找不到可写的 mod 目录（原版只读）"}
    try:
        cap = int(capital)
    except Exception:
        return {"ok": False, "msg": "capital 必须是省号"}

    d = os.path.join(top, "history", "countries")
    os.makedirs(d, exist_ok=True)
    # HOI4 按 tag 认国家历史、不看文件名，同一个 tag 有两个文件会互相打架。
    # 所以先按「文件名里的 tag」查重，而不是只查同名文件。
    try:
        for fn in os.listdir(d):
            if not fn.endswith(".txt"):
                continue
            head = fn.split(" ")[0].split(".")[0].strip().upper()
            if head == tag:
                return {"ok": False,
                        "msg": "这个 tag 已经有国家历史：%s" % fn}
    except Exception:
        pass
    safe = re.sub(r'[^\w\u4e00-\u9fa5-]+', "_", (name or tag))[:40]
    fname = "%s - %s.txt" % (tag, safe)
    p = os.path.join(d, fname)
    if os.path.exists(p):
        return {"ok": False, "msg": "已经存在：%s" % fname}

    body = 'capital = %d\nset_research_slots = %d\n' % (cap, int(research_slots))
    if oob:
        body += 'oob = "%s"\n' % oob
    body += (
        'set_technology = {\n\tinfantry_weapons = 1\n}\n'
        'set_politics = {\n'
        '\truling_party = %s\n'
        '\tlast_election = "1936.1.1"\n'
        '\telection_frequency = 48\n'
        '\telections_allowed = no\n'
        '}\n'
        'set_popularities = {\n'
        '\tdemocratic = 10\n'
        '\tfascism = 10\n'
        '\tcommunism = 10\n'
        '\tneutrality = 70\n'
        '}\n' % ruling_party)
    try:
        _atomic_write(p, _bom_for(p) + body.encode("utf-8"))
    except Exception as e:
        return {"ok": False, "msg": "写文件失败：%s" % e}
    _reload()
    return {"ok": True, "tag": tag,
            "file": os.path.relpath(p, top).replace(os.sep, "/"),
            "msg": "已建 %s 的国家历史（首都省 %d）" % (tag, cap)}



def _centroids_from_map(map_dir, notes=None):
    """从 map/definition.csv + provinces.bmp 反算每省像素质心。

    `world_create` 正常走 mapgen.generate，那边会直接把 centroids 返回；
    这个函数只是兜底：手工改过图、或从别的工具生成的 mod 也能补坐标表。

    返回空字典的两种情况含义完全不同：
      · map/ 下没这两个文件（返回空是正常结论，不报）
      · numpy / PIL / 图片读不开（返回空表示**没算**，必须能说出原因）
    第二种把原因写进 notes（可选 list），调用点拿去拼进步骤消息，
    否则界面上只剩「unitstacks 0 / buildings 0 / weather 0」，看不出是缺库。
    """
    cen = {}

    def _note(msg):
        if notes is not None:
            try:
                notes.append(msg)
            except Exception:
                pass

    map_dir = os.path.abspath(map_dir)
    csvp = os.path.join(map_dir, "definition.csv")
    provp = os.path.join(map_dir, "provinces.bmp")
    if not (os.path.isfile(csvp) and os.path.isfile(provp)):
        return cen
    try:
        import numpy as np
        from PIL import Image
    except Exception as e:
        # 分开写：ImportError 时说清缺哪个模块（exe 里缺 numpy 就是这个），
        # 其它异常说明是哪类错误。
        name = getattr(e, "name", "") or ""
        if isinstance(e, ImportError):
            _note("缺模块 %s，质心表未计算" % (name or str(e)))
        else:
            _note("加载 numpy/PIL 失败 %s: %s，质心表未计算"
                  % (e.__class__.__name__, e))
        return cen
    rgb2pid = {}
    for line in io.open(csvp, encoding="utf-8", errors="replace"):
        p = line.strip().split(";")
        if len(p) < 4:
            continue
        try:
            rgb2pid[(int(p[1]), int(p[2]), int(p[3]))] = int(p[0])
        except Exception:
            continue
    try:
        im = Image.open(provp).convert("RGB")
    except Exception as e:
        _note("provinces.bmp 读不开 %s: %s，质心表未计算"
              % (e.__class__.__name__, e))
        return cen
    a = np.asarray(im, dtype=np.int32)
    h, w = a.shape[:2]
    keys = (a[:, :, 0] << 16) | (a[:, :, 1] << 8) | a[:, :, 2]
    flat = keys.reshape(-1)
    uniq, inv, cnt = np.unique(flat, return_inverse=True, return_counts=True)
    ys, xs = np.mgrid[0:h, 0:w]
    sx = np.bincount(inv, weights=xs.reshape(-1), minlength=len(uniq))
    sy = np.bincount(inv, weights=ys.reshape(-1), minlength=len(uniq))
    for i, k in enumerate(uniq):
        k = int(k)
        pid = rgb2pid.get(((k >> 16) & 255, (k >> 8) & 255, k & 255))
        if not pid or pid <= 0 or cnt[i] <= 0:
            continue
        cen[pid] = (round(sx[i] / cnt[i], 2), round(sy[i] / cnt[i], 2))
    return cen



def world_create(out_dir, source="procedural", width=1024, height=512,
                 n_provinces=40, min_size=300, seed=11, src_path=None,
                 sea_level=0.42, balance=True, min_province_px=800,
                 n_regions=None, n_supply=None,
                 tag="ZZV", country_name="新世界", color=None,
                 per_state=8, mod_name=None, army=True,
                 n_focus=24, focus_shape="tree", gen_focus=True,
                 gen_event=True, unit_name=None):
    """一键建世界：地图 → tag → 州 → 国家历史 → 军队 → 本地化 → 剧本。

    每一步都调用编辑器已有的函数（map_generate / country_tag_add /
    state_create / country_history_create / template_add / unit_add /
    loc_generate / bookmark_add / focus_gen / world_events / world_loc），
    不自己拼文件。任何一步失败都会记进 steps 并终止后续步骤，避免在半成品上继续叠加。

    A2 起多了三个参数：`n_focus`（国策节点数）、`focus_shape`（tree / chain）、
    `gen_focus` / `gen_event`（要不要真内容，关掉就是 A1 的空占位）。

    返回 {"ok", "steps": [{step, ok, msg}], "out_dir", "provinces", "states"}
    """
    steps = []
    out_dir = os.path.abspath(out_dir) if out_dir else ""

    def rec(name, r):
        ok = bool(r.get("ok")) if isinstance(r, dict) else bool(r)
        msg = (r.get("msg") if isinstance(r, dict) else "") or ""
        steps.append({"step": name, "ok": ok, "msg": msg})
        return ok

    if not out_dir:
        return {"ok": False, "msg": "要指定输出目录", "steps": steps}

    def done(extra=None):
        d = {"ok": all(s["ok"] for s in steps), "steps": steps,
             "out_dir": out_dir}
        if extra:
            d.update(extra)
        return d

    # 1) 地图（只出 map/，骨架交给下面的步骤）
    r = map_generate(source=source, out_dir=out_dir, width=width, height=height,
                     n_provinces=n_provinces, min_size=min_size, seed=seed,
                     src_path=src_path, sea_level=sea_level, balance=balance,
                     min_province_px=min_province_px,
                     n_regions=n_regions, n_supply=n_supply)
    if not rec("地图生成", r):
        return done()

    # 2) descriptor：mod_layers / country_tag_add / state_create 都靠它认出
    #    「这是一个 mod」，没有它后面每一步都会报「找不到可写的 mod 目录」。
    try:
        import mapgen_scaffold as _scaf
        _scaf.write_descriptor(out_dir, mod_name or country_name or "新世界")
        steps.append({"step": "写 descriptor", "ok": True, "msg": ""})
    except Exception as e:
        steps.append({"step": "写 descriptor", "ok": False, "msg": str(e)})
        return done()

    # 3) 重载，让 PROV_RGB / COUNTRIES 认识这张新图
    try:
        _load_mod(out_dir)
        _ensure_prov_rgb(out_dir)   # 懒加载，不主动触发就一直是空的
        _lp_done()
        steps.append({"step": "重载地图", "ok": True,
                      "msg": "%d 个省" % len(state.prov_rgb())})
    except Exception as e:
        _lp_done()
        steps.append({"step": "重载地图", "ok": False, "msg": str(e)})
        return done()

    n_prov = max(0, len(state.prov_rgb()) - 1)   # 去掉省 0

    # 3) tag 必须先存在，州和历史的 owner 才能引用
    if not rec("建国家 tag", country_tag_add(out_dir, tag, color)):
        return done()

    # 4) 按每州 per_state 个省切州，全部归这个 tag。
    #    必须只取陆省：HOI4 的州里一旦出现 sea 省，加载期直接报错退出。
    #    definition.csv 第 5 列是 land / sea，用它精确筛。
    land = []
    csvp = os.path.join(out_dir, "map", "definition.csv")
    try:
        for line in io.open(csvp, encoding="utf-8", errors="replace"):
            parts = line.strip().split(";")
            if len(parts) >= 5 and parts[4].strip() == "land":
                try:
                    pid = int(parts[0])
                except Exception:
                    continue
                if pid > 0:
                    land.append(pid)
    except Exception as e:
        steps.append({"step": "读 definition.csv", "ok": False, "msg": str(e)})
        return done()
    land.sort()
    made_states, first_state = 0, None
    state_map = []          # [(州号, [省号...])]，补给图要用真实州号
    try:
        step_n = int(per_state) if int(per_state) > 0 else 8
    except Exception:
        step_n = 8
    for i in range(0, len(land), step_n):
        pids = land[i:i + step_n]
        if not pids:
            continue
        r = state_create(pids, root=out_dir,
                         name="%s_%d" % (tag, made_states + 1),
                         owner=tag)
        if r.get("ok"):
            made_states += 1
            sid = r.get("id") or r.get("state") or made_states
            state_map.append((sid, list(pids)))
            if first_state is None:
                first_state = sid
        elif "已经存在" not in (r.get("msg") or ""):
            steps.append({"step": "建州 %d" % (made_states + 1),
                          "ok": False, "msg": r.get("msg") or ""})
            break
    steps.append({"step": "建州", "ok": made_states > 0,
                  "msg": "建成 %d 个州，每州 %d 省" % (made_states, step_n)})

    # 5) 国家历史：首都取第一个陆省
    capital = land[0] if land else 1
    rec("国家历史", country_history_create(
        out_dir, tag, capital=capital, name=country_name,
        oob=("%s_1936" % tag if army else None)))

    # 6) 开局部队（可选）
    if army:
        try:
            tres = template_add("%s_Infantry" % tag, "infantry",
                                root=out_dir, tag=tag)
            if rec("师团模板", tres):
                # A2-5 方案 B：直接给固定番号。番号组（division_names_group）
                # 需要 common/units/names_divisions 里有对应条目，那一步还没做，
                # 不写名字的话界面上就是一串空白。
                rec("开局部队", unit_add(capital, "%s_Infantry" % tag,
                                         name=unit_name or "第 1 步兵师",
                                         root=out_dir, tag=tag))
        except Exception as e:
            steps.append({"step": "军队", "ok": False, "msg": str(e)})

    # 7) 本地化占位
    try:
        rec("本地化", loc_generate(out_dir))
    except Exception as e:
        steps.append({"step": "本地化", "ok": False, "msg": str(e)})

    # 8) 剧本
    try:
        rec("剧本", bookmark_add(out_dir, country_name or mod_name or "新世界",
                                 "1936.1.1.12", default_country=tag,
                                 countries=[tag]))
    except Exception as e:
        steps.append({"step": "剧本", "ok": False, "msg": str(e)})

    # 8.5) 国家领袖：common/characters 被整目录屏蔽，不写就没有领袖，
    #      「选择国家」按钮会点了没反应（详见 qa/world_leader.py 开头）
    leader_loc = []
    try:
        import world_leader
        lr = world_leader.write(out_dir, tag, leader_name=(country_name or "新世界") + "领袖")
        leader_loc = lr["loc"]
        lk = world_leader.link_history(out_dir, tag, cid=lr.get("id"))
        steps.append({"step": "国家领袖", "ok": True,
                      "msg": "%s；%s" % (lr["path"], lk.get("msg") or "")})
    except Exception as e:
        steps.append({"step": "国家领袖", "ok": False, "msg": str(e)})

    # 9) 国策树（A2-1/A2-2）：一棵 15–30 节点的真树 + 中文名
    focus_text, focus_loc = None, []
    if gen_focus:
        try:
            import sys as _sys
            _qa = _qa_dir()
            if _qa not in _sys.path:
                _sys.path.insert(0, _qa)
            import focus_gen
            fr = focus_gen.build(tag=tag, n_focus=n_focus, shape=focus_shape)
            bad = focus_gen.check(fr["text"], tag)
            focus_text, focus_loc = fr["text"], fr["loc"]
            steps.append({"step": "国策树", "ok": not bad,
                          "msg": "%d 个节点 / %d 层%s" % (
                              len(fr["nodes"]), len(fr["layers"]),
                              "" if not bad else "：" + bad[0])})
        except Exception as e:
            steps.append({"step": "国策树", "ok": False, "msg": str(e)})

    # 10) 开局事件（A2-3）：一条 on_startup 触发的国家事件
    ev_text, oa_text, ev_loc = None, None, []
    if gen_event:
        try:
            import world_events
            er = world_events.build(tag=tag)
            ev_text, oa_text, ev_loc = er["events"], er["on_actions"], er["loc"]
            steps.append({"step": "开局事件", "ok": True,
                          "msg": er["event_id"]})
        except Exception as e:
            steps.append({"step": "开局事件", "ok": False, "msg": str(e)})

    # 11) 被 replace 的目录逐个补占位。
    #    这一步是「能加载」和「能进游戏」的分界：descriptor 里 50 条 replace_path
    #    声明了 50 个只从本 mod 读的目录，缺一个就有一个目录读空。
    #    最要命的是 common/national_focus —— 没有 default = yes 的树必崩，
    #    而且 error.log 一个字都不写（详见 qa/world_stubs.py 开头）。
    try:
        import sys as _sys
        _qa = _qa_dir()
        if _qa not in _sys.path:
            _sys.path.insert(0, _qa)
        import world_stubs
        ov = {}
        if focus_text:
            ov["common/national_focus"] = focus_text
        if ev_text:
            ov["events"] = ev_text
        if oa_text:
            ov["common/on_actions"] = oa_text
        made = world_stubs.write_all(out_dir, tag, overrides=ov)
        bad = [p for p in world_stubs.check(out_dir, dirs=world_stubs.REPLACE_DIRS)
               if p["level"] == "error"]
        steps.append({"step": "目录占位", "ok": not bad,
                      "msg": "%d 个目录" % len(made) if not bad
                             else bad[0]["dir"] + "：" + bad[0]["msg"]})
    except Exception as e:
        steps.append({"step": "目录占位", "ok": False, "msg": str(e)})

    # 10) 补给图：地图阶段不知道州号，这里按真实州号重写
    #     （早期版本把省号写进了 states={}，5 个州的地图写出 207 个州号）
    try:
        import mapgen_write as _mgw
        n_sa = _mgw.write_supply_graph(os.path.join(out_dir, "map"), state_map)
        steps.append({"step": "补给图", "ok": n_sa > 0,
                      "msg": "%d 个补给区 / %d 个补给节点" % (n_sa, len(state_map))})
    except Exception as e:
        steps.append({"step": "补给图", "ok": False, "msg": str(e)})

    # 12) 地标落点：unitstacks / buildings / weatherpositions
    #     这三张表的坐标是**地图像素坐标**，原版那份是 5632×2048 空间的，
    #     在我们 1024×512 的图上每个点都越界。必须按省质心重写。
    try:
        import mapgen_write as _mgw
        cen = (r or {}).get("centroids") or {}
        _cen_notes = []
        if not cen:
            cen = _centroids_from_map(os.path.join(out_dir, "map"), notes=_cen_notes)
        _sz = ((r or {}).get("width"), (r or {}).get("height"))
        mp = _mgw.write_map_positions(os.path.join(out_dir, "map"), cen,
                                      states=state_map,
                                      size=_sz if all(_sz) else None)
        # 三种情况要能区分：算出了坐标 / 图里本来就没有坐标可算 / 库缺失导致没算。
        # 以前后两种都只显示「unitstacks 0 / buildings 0 / weather 0」，看不出区别。
        _msg = ("unitstacks %d / buildings %d / weather %d"
                % (mp["unitstacks"], mp["buildings"], mp["weather"]))
        if _cen_notes:
            _msg = _msg + "；" + "；".join(_cen_notes)
        steps.append({"step": "地标落点", "ok": bool(cen), "msg": _msg})
    except Exception as e:
        steps.append({"step": "地标落点", "ok": False, "msg": str(e)})

    # 13) 世界本地化（A2-2 的国策名 + 国名 + 州名 + 事件文本）
    try:
        import world_loc
        entries = []
        entries += world_loc.country_entries(
            tag, country_name or "新世界",
            desc="%s，一个刚刚被造出来的国家。" % (country_name or "新世界"),
            adjective=(country_name or "新世界"))
        entries += world_loc.state_entries([s for s, _p in state_map])
        entries += focus_loc
        entries += ev_loc
        entries += leader_loc
        n_loc = world_loc.write(out_dir, entries)
        steps.append({"step": "世界本地化", "ok": n_loc >= 0,
                      "msg": "%d 条中文" % n_loc})
    except Exception as e:
        steps.append({"step": "世界本地化", "ok": False, "msg": str(e)})

    return done({"provinces": len(land), "states": made_states, "tag": tag,
                 "focus_nodes": len(focus_loc) // 2 if focus_loc else 0})



def country_tag_delete(root, tag):
    """删一个国家 tag（只从自己的 mod 层里摘，且要先看引用）。"""
    root = _map_pick(root)
    tag = (tag or "").upper().strip()
    if not tag:
        return {"ok": False, "msg": "tag 不能为空"}
    info = country_tag_refs(root, tag)
    if info["total"] > 0:
        return {"ok": False, "need_confirm": True, "refs": info,
                "msg": "%s 还被引用，直接删会留下悬空引用。%s" % (tag, info["msg"])}

    tgt, err = _country_tags_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    d = os.path.join(tgt, "common", "country_tags")
    if not os.path.isdir(d):
        return {"ok": False, "msg": "自己的 mod 里没有 common/country_tags，还没接管"}

    removed = False
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".txt"):
            continue
        p = os.path.join(d, fn)
        raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
        pat = re.compile(r'(?m)^[ \t]*' + re.escape(tag) + r'\s*=\s*"[^"]*"[ \t]*\r?\n?')
        new_text = pat.sub('', raw)
        if new_text != raw:
            snapshot(p)
            _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))
            removed = True
            break
    if not removed:
        return {"ok": False, "msg": "自己的 mod 里没找到 %s 这一行（可能在父 mod，只读）" % tag}
    try:
        _LAYERS_CACHE.clear()
    except Exception:
        pass
    _reload()
    return {"ok": True, "tag": tag, "msg": "已删除 tag %s" % tag}



def _bookmark_write_base(root):
    """common/bookmarks 的写入层，拒写父 mod。"""
    top = _top_mod(root)
    if not top:
        return None, "找不到可写的 mod 目录"
    tgt, why = write_base(root, "common/bookmarks")
    if not tgt:
        return None, "找不到可写目录"
    if os.path.abspath(tgt) != os.path.abspath(top):
        nm = os.path.basename(tgt.rstrip("\\/")) or tgt
        return None, ("common/bookmarks 被 %s 的 replace_path 独占，"
                      "请先在「诊断 → 目录写入目标」里接管该目录" % nm)
    return tgt, ""



def _bookmark_date(date):
    """把 1936.1.1 补成 1936.1.1.12。

    HOI4 的剧本日期是「年.月.日.小时」，只写三段时游戏会把日当小时解析，
    显示成「14月,1939」这种鬼东西。
    """
    parts = [p for p in (date or "").split(".") if p != ""]
    if len(parts) == 3:
        parts.append("12")
    return ".".join(parts)



def _bookmark_country_block(tag, ideology="neutrality"):
    """剧本里的「可选国家」条目。

    国家 tag 必须写成**裸键**（`ZZV = { ... }`），不能加引号。
    原版 blitzkrieg.txt / the_gathering_storm.txt 都是裸键；写成 `"ZZV" = {`
    解析出来是个字符串键而不是国家作用域，于是**选国家界面里一个可选国家都没有**：
    地图在、日期在、剧本名也在，就是没有国家可以点，「选择国家」按钮也不出现。
    （2026-11-03 实测踩到，卡了半晚的自动点击其实就是卡在这个空列表上。）
    """
    return ('\t\t%s = {\n'
            '\t\t\thistory = %s_DESC\n'
            '\t\t\tideology = %s\n'
            '\t\t\tideas = {\n'
            '\t\t\t}\n'
            '\t\t\tfocuses = {\n'
            '\t\t\t}\n'
            '\t\t}\n') % (tag.upper(), tag.upper(), ideology)



def _game_language():
    """读游戏的界面语言。HOI4 只加载和当前语言匹配的 localisation 文件，
    中文语言下写 l_english 的 yml 完全不生效，界面上就是裸 key。"""
    try:
        p = os.path.join(os.path.expanduser("~"), "Documents",
                         "Paradox Interactive", "Hearts of Iron IV", "settings.txt")
        if os.path.exists(p):
            txt = io.open(p, encoding="utf-8", errors="replace").read()
            m = re.search(r'language\s*=\s*"?([a-z_]+)"?', txt)
            if m:
                return m.group(1)
    except Exception:
        pass
    return "l_english"



def _bookmark_loc(root, key, disp, desc_text, countries):
    """给剧本写本地化，否则界面上显示的是 NAME/DESC 这种 key。

    key 是 ASCII 标识符（写进 bookmarks），disp / desc_text 是中文显示名。
    """
    tgt, err = _bookmark_write_base(root)
    if not tgt:
        return False
    lang = _game_language()
    d = os.path.join(tgt, "localisation")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "zz_editor_bookmarks_%s.yml" % lang)

    lines = []
    if os.path.exists(p):
        try:
            old = io.open(p, encoding="utf-8-sig", errors="replace").read()
            if old.strip():
                lines = [old.rstrip("\n")]
        except Exception:
            lines = []
    if not lines:
        lines = ["%s:" % lang]

    # 已有内容里出现过的 key 不再重复写
    joined = "\n".join(lines)
    body = []
    def add(k, v):
        if re.search(r'(?m)^\s*' + re.escape(k) + r'\s*:', joined):
            return
        body.append(' %s:0 "%s"' % (k, v))
    add(key, disp)
    if desc_text and desc_text != disp:
        add(key + "_DESC", desc_text)
    else:
        # desc 与 name 同文时也要写一条，否则界面上的「历史简介」显示裸 key
        add(key + "_DESC", disp)
    for c in countries:
        add(c.upper() + "_DESC", c.upper())

    if not body:
        return True
    txt = "\n".join(lines + body) + "\n"
    io.open(p, "w", encoding="utf-8-sig", newline="").write(txt)
    return True



def bookmark_add(root, name, date, desc=None, picture=None, default_country=None,
                 countries=None):
    """新建一个剧本。

    countries: 这个剧本里可选的国家列表，默认只放 default_country。
    HOI4 的选国家界面只列剧本里写了 "TAG" = {} 的那些国家，不写就是空的。
    """
    root = _map_pick(root)
    name = (name or "").strip()
    date = (date or "").strip()
    if not name:
        return {"ok": False, "msg": "name 不能为空"}
    if not re.match(r'^\d{4}\.\d{1,2}\.\d{1,2}(\.\d+)?$', date):
        return {"ok": False, "msg": "date 格式要像 1936.1.1 或 1936.1.1.12"}
    date = _bookmark_date(date)
    tag = (default_country or "GER").upper().strip()
    clist = []
    for c in (countries or [tag]):
        c = (c or "").upper().strip()
        if c and c not in clist:
            clist.append(c)
    if tag not in clist:
        clist.insert(0, tag)

    tgt, err = _bookmark_write_base(root)
    if not tgt:
        return {"ok": False, "msg": err}
    d = os.path.join(tgt, "common", "bookmarks")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "zz_editor_bookmarks.txt")

    # 本地化 key 只能是最长 25 字符的 ASCII 标识符，中文名必须放在值那边。
    # 直接把中文名当 key 写进 yml，游戏报 Invalid key name，剧本名也显示不出来。
    bkey = "ZZ_EDITOR_BM_" + hashlib.md5(name.encode("utf-8")).hexdigest()[:8].upper()
    block = ['\tbookmark = {',
             '		name = "%s"' % bkey,
             '		desc = "%s_DESC"' % bkey,
             '\t\tdate = %s' % date,
             '\t\tpicture = "%s"' % (picture or "GFX_select_date_1936"),
             '\t\tdefault_country = "%s"' % tag,
             '\t\tfilters = { new_content continent }',
             '\t\tdefault = yes',
             '']
    for c in clist:
        block.append(_bookmark_country_block(c).rstrip("\n"))
    block.append('\t}')
    block_txt = "\n".join(block) + "\n"

    if os.path.exists(p):
        raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
    else:
        raw = "bookmarks = {\n}\n"
    text = _strip_keep_len(raw)
    bm = re.search(r'(?m)^[ \t]*bookmarks[ \t]*=\s*\{', text)
    if bm:
        bb = text.find("{", bm.end() - 1)
        be = brace_match(text, bb)
        if be > bb:
            pos = be
            while pos > 0 and raw[pos - 1] in " \t":
                pos -= 1
            if pos > 0 and raw[pos - 1] == "}":
                pos -= 1
            ls = raw.rfind("\n", 0, pos) + 1
            new_text = raw[:ls] + block_txt + raw[ls:]
        else:
            new_text = raw.rstrip() + "\n" + block_txt
    else:
        new_text = raw.rstrip() + "\nbookmarks = {\n" + block_txt + "}\n"
    if os.path.exists(p):
        snapshot(p)
    _atomic_write(p, _bom_for(p) + new_text.encode("utf-8"))
    try:
        _bookmark_loc(root, bkey, name, desc or name, clist)
    except Exception:
        pass
    return {"ok": True,
            "msg": "已新建剧本 %s（%s，%d 个国家可选）" % (name, date, len(clist))}



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
    defined = set(state.loc().keys())
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
    _defined = _loc_defined_set(root) if root else set(state.loc().keys())
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
    _atomic_write(fn, _bom_for(fn) + body.encode("utf-8"))
    _reload()
    return {"ok": True, "written": added, "total": len(existing), "path": fn,
            "msg": "已写入 %d 个键到 %s（占位值=键名，改完重新加载本地化）" % (
                added, os.path.basename(fn))}



def mod_home():
    return os.path.join(os.path.expanduser("~"), "Documents", "Paradox Interactive", "Hearts of Iron IV", "mod")



def create_mod(base, mod_id, name, version="0.1.0", game_version="1.19.*",
               tree_id="", tag="", create_tree=True, dep=""):
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
    # dep：做 submod 时依赖的本体。给了就在 descriptor 里写 dependencies，
    # 这样只加载本 mod 也能让 mod_layers 自动把本体补进叠加链——本体的
    # replace_path 才会生效，原版的数据才不会漏进来。
    # 做「从原版开始的新 mod」时留空，链里只有原版，行为不变。
    dep_name = ""
    if dep:
        _dp = os.path.abspath(str(dep))
        if os.path.isdir(_dp):
            dep_name = (_mod_descriptor(_dp).get("name") or
                        os.path.basename(_dp.rstrip("\\/")))
        else:
            dep_name = str(dep).strip()
    try:
        os.makedirs(root)
        desc = ['version="%s"' % version, 'tags={', '\t"Alternative History"', '}',
                'name="%s"' % name, 'supported_version="%s"' % game_version]
        if dep_name:
            desc += ['dependencies={', '\t"%s"' % dep_name, '}']
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

