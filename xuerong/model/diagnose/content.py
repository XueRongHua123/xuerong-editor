# -*- coding: utf-8 -*-
"""内容层诊断：oob / gfx / recruit / decision / character / localisation / tag / division。"""

import io
import os
import re

from xuerong import state
from xuerong.core.ideologies import load_ideology_names
from xuerong.core.paths import (_replace_owner, _top_mod,
                                effective_layer_files, is_under_game,
                                mod_layers)
from xuerong.core.text import _strip_keep_len, brace_match
from xuerong.model.diagnose._base import _finding


_GFX_NAMES_CACHE = {"key": None, "sig": None, "val": set()}
_LOC_KEYS_CACHE = {"key": None, "sig": None, "val": set()}


def _resolve_top(root=None):
    top = _top_mod(root)
    if top:
        return top
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            return cand
    return None


def _scan_targets(root=None, own_only=True):
    top = _resolve_top(root)
    if not top:
        return None, []
    if own_only:
        return top, [top]
    layers = [b for b in (mod_layers(top) or [top]) if b and not is_under_game(b)]
    if top not in layers:
        layers.append(top)
    return top, layers


def _layer_rel(top, base_dir, rel):
    if not top or os.path.abspath(base_dir) == os.path.abspath(top):
        return rel
    name = os.path.basename(base_dir.rstrip("\\/")) or base_dir
    return name + "/" + rel


def _diag_oob_not_referenced(root, own_only=True):
    """history/units 下的 OOB 文件有没有被国家历史点名。

    HOI4 不扫描这个目录，靠 set_oob / set_air_oob / set_naval_oob 逐条点名。
    自己起个文件名写进去，游戏一个单位都不会加载，而且 error.log 里不会有任何提示。
    """
    out = []
    top, targets = _scan_targets(root, own_only)
    if not targets:
        return out

    unit_files = []
    for base_dir in targets:
        ud = os.path.join(base_dir, "history", "units")
        if not os.path.isdir(ud):
            continue
        for fn in sorted(os.listdir(ud)):
            if fn.endswith(".txt"):
                unit_files.append((base_dir, os.path.join(ud, fn), fn))
    if not unit_files:
        return out

    # 收集所有被点名的名字
    referenced = set()
    layers = mod_layers(top) or [top]
    for b in layers:
        if not b:
            continue
        h2 = os.path.join(b, "history", "countries")
        if not os.path.isdir(h2):
            continue
        for fn in os.listdir(h2):
            if not fn.endswith(".txt"):
                continue
            try:
                with io.open(os.path.join(h2, fn), encoding="utf-8-sig", errors="replace") as _fh:
                    txt = _fh.read()
            except Exception:
                continue
            for k in ("set_oob", "oob", "set_air_oob", "air_oob",
                      "set_naval_oob", "naval_oob", "load_oob"):
                for m in re.finditer(r'(?m)^\s*' + k + r'\s*=\s*"([^"]+)"', txt):
                    referenced.add(m.group(1).strip())

    for base_dir, p, fn in unit_files:
        stem = fn[:-4]
        if stem in referenced:
            continue
        try:
            with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
                txt = _fh.read()
        except Exception:
            continue
        if not re.search(r'(?m)^\s*(units|air_wings|division_template|fleet)\s*=\s*\{', txt):
            continue
        first = ""
        for _i, ln in enumerate(txt.splitlines(), 1):
            if ln.strip():
                first = ln.strip()
                break
        rel = _layer_rel(top, base_dir, os.path.join("history", "units", fn).replace(os.sep, "/"))
        out.append(_finding(
            "script.oob.not_referenced", "warning",
            "%s 里有内容，但没有被任何国家历史的 set_oob / set_air_oob / set_naval_oob 点名，"
            "游戏不会加载它（也不报错）" % fn,
            rel, 0, first,
            "给你自己的国家加一条 set_oob = \"%s\"；或者把内容并进已被点名的那个文件"
            % stem))
    return out


def _gfx_names(root):
    """收集所有 interface/*.gfx 里定义的 sprite 名（带文件统计缓存）。"""
    layers = tuple(b for b in (mod_layers(root) or []) if b)
    gfxs = []
    max_mt = 0.0
    total_sz = 0
    for b in layers:
        gd = os.path.join(b, "interface")
        if not os.path.isdir(gd):
            continue
        for fn in os.listdir(gd):
            if not fn.lower().endswith(".gfx"):
                continue
            fp = os.path.join(gd, fn)
            try:
                st = os.stat(fp)
                max_mt = max(max_mt, st.st_mtime)
                total_sz += st.st_size
            except Exception:
                pass
            gfxs.append(fp)
    sig = (len(gfxs), max_mt, total_sz)
    if _GFX_NAMES_CACHE["key"] == layers and _GFX_NAMES_CACHE["sig"] == sig:
        return set(_GFX_NAMES_CACHE["val"])
    names = set()
    for fp in gfxs:
        try:
            with io.open(fp, encoding="utf-8-sig", errors="replace") as _fh:
                txt = _fh.read()
        except Exception:
            continue
        for m in re.finditer(r'name\s*=\s*"([^"]+)"', txt):
            names.add(m.group(1))
    _GFX_NAMES_CACHE.update({"key": layers, "sig": sig, "val": set(names)})
    return names


def _diag_gfx_missing(root, own_only=True):
    """icon / picture 引用的 sprite 在本体和 mod 里都找不到。

    HOI4 的决议 icon 会自动补 GFX_decision_，国策 icon 用完整名，
    精神 picture 自动补 GFX_idea_。名字写错不报错，界面上一片空白。
    """
    out = []
    top, targets = _scan_targets(root, own_only)
    if not targets:
        return out

    target_specs = [
        ("common/decisions", r'(?m)^\s*icon\s*=\s*([A-Za-z_][A-Za-z0-9_]*)'),
        ("common/decisions/categories", r'(?m)^\s*icon\s*=\s*([A-Za-z_][A-Za-z0-9_]*)'),
        ("common/national_focus", r'(?m)^\s*icon\s*=\s*([A-Za-z_][A-Za-z0-9_]*)'),
        ("common/ideas", r'(?m)^\s*picture\s*=\s*([A-Za-z_][A-Za-z0-9_]*)'),
    ]
    scan_files = []
    for base_dir in targets:
        for sub, pat in target_specs:
            d = os.path.join(base_dir, sub.replace("/", os.sep))
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if fn.endswith(".txt"):
                    scan_files.append((base_dir, sub, pat, fn, os.path.join(d, fn)))
    if not scan_files:
        return out

    known = _gfx_names(top)
    if not known:
        return out

    for base_dir, sub, pat, fn, p in scan_files:
        try:
            with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
                lines = _fh.read().splitlines()
        except Exception:
            continue
        rel = _layer_rel(top, base_dir, os.path.join(sub, fn).replace(os.sep, "/"))
        for i, ln in enumerate(lines, 1):
            m = re.search(pat, ln + "\n")
            if not m:
                continue
            raw = m.group(1).strip()
            # 已经是完整 sprite 名就直接查；裸名按各自命名空间补前缀
            cands = [raw]
            if not raw.startswith("GFX_"):
                cands += ["GFX_" + raw, "GFX_decision_" + raw, "GFX_idea_" + raw,
                          "GFX_decision_category_" + raw]
            if any(c in known for c in cands):
                continue
            out.append(_finding(
                "gfx.sprite_missing", "warning",
                "%s 第 %d 行引用了 %s，但在 interface/*.gfx 里找不到这个 sprite，"
                "界面上会显示空白或默认图" % (fn, i, raw),
                rel, i, ln.strip(),
                "检查拼写；决议 icon 写裸名（游戏自动补 GFX_decision_），"
                "国策 icon 写完整 GFX_ 名，精神 picture 写裸名（自动补 GFX_idea_）"))
    return out


def _diag_recruit_last_line(root, own_only=True):
    """history/countries 里 recruit_character 不能是最后一行。

    文件末尾就是 recruit_character 时招募会静默失败——人物定义了但游戏里不出现。
    """
    out = []
    top, targets = _scan_targets(root, own_only)
    if not targets:
        return out
    for base_dir in targets:
        d = os.path.join(base_dir, "history", "countries")
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(d, fn)
            try:
                with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
                    lines = _fh.read().splitlines()
            except Exception:
                continue
            # 文档说的是「文件末尾必须至少还有一行，哪怕空行」，
            # 所以看的是物理最后一行，不是最后一个非空行。
            if not lines:
                continue
            i = len(lines)
            ln = lines[-1]
            if not ln.strip():
                continue
            if re.match(r'^\s*recruit_character\s*=', ln):
                rel = _layer_rel(top, base_dir, os.path.join("history", "countries", fn).replace(os.sep, "/"))
                out.append(_finding(
                    "script.recruit.last_line", "warning",
                    "%s 的 recruit_character 在文件最后一行，招募会静默失败" % fn,
                    rel, i, ln.strip(),
                    "在文件末尾补一个空行或注释"))
    return out


def _diag_decision_category(root, own_only=True):
    """决议引用的类别有没有在 common/decisions/categories 里定义。

    1.13 起决议类别必须注册，否则报 Unknown category / Invalid Decision Category。
    """
    out = []
    top, targets = _scan_targets(root, own_only)
    if not targets:
        return out
    dec_files = []
    for base_dir in targets:
        dd = os.path.join(base_dir, "common", "decisions")
        if not os.path.isdir(dd):
            continue
        for fn in sorted(os.listdir(dd)):
            if fn.endswith(".txt"):
                dec_files.append((base_dir, fn, os.path.join(dd, fn)))
    if not dec_files:
        return out

    # 已定义的类别（含父层）
    cats = set()
    for b in (mod_layers(top) or []):
        if not b:
            continue
        cd = os.path.join(b, "common", "decisions", "categories")
        if not os.path.isdir(cd):
            continue
        for fn in os.listdir(cd):
            if not fn.endswith(".txt"):
                continue
            try:
                with io.open(os.path.join(cd, fn), encoding="utf-8-sig", errors="replace") as _fh:
                    txt = _fh.read()
            except Exception:
                continue
            for m in re.finditer(r'(?m)^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=\s*\{', txt):
                cats.add(m.group(1))

    for base_dir, fn, p in dec_files:
        try:
            with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
                lines = _fh.read().splitlines()
        except Exception:
            continue
        rel = _layer_rel(top, base_dir, os.path.join("common", "decisions", fn).replace(os.sep, "/"))
        for i, ln in enumerate(lines, 1):
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)[ \t]*=\s*\{\s*$', ln)
            if not m:
                continue
            name = m.group(1)
            if name in cats or name in ("categories",):
                continue
            out.append(_finding(
                "script.decision.category_undefined", "warning",
                "%s 第 %d 行的顶层块 %s 看起来是决议类别，但没有在 "
                "common/decisions/categories 里注册" % (fn, i, name),
                rel, i, ln.strip(),
                "在该文件里补一个同名类别块，或确认这里用的是已注册类别"))
    return out


def _loc_keys(root):
    """递归收集所有层 localisation/**/*.yml 里定义的键（带文件统计缓存）。"""
    layers = tuple(b for b in (mod_layers(root) or []) if b)
    ymls = []
    max_mt = 0.0
    total_sz = 0
    for b in layers:
        loc_root = os.path.join(b, "localisation")
        if not os.path.isdir(loc_root):
            continue
        for cur, _dn, files in os.walk(loc_root):
            for fn in files:
                if not fn.lower().endswith(".yml"):
                    continue
                fp = os.path.join(cur, fn)
                try:
                    st = os.stat(fp)
                    max_mt = max(max_mt, st.st_mtime)
                    total_sz += st.st_size
                except Exception:
                    pass
                ymls.append(fp)
    sig = (len(ymls), max_mt, total_sz)
    if _LOC_KEYS_CACHE["key"] == layers and _LOC_KEYS_CACHE["sig"] == sig:
        return set(_LOC_KEYS_CACHE["val"])

    keys = set()
    line_re = re.compile(r'(?m)^[ \t]*([A-Za-z_][A-Za-z0-9_.\-]*)\s*:\d*\s*"')
    for fp in ymls:
        try:
            with io.open(fp, encoding="utf-8-sig", errors="replace") as _fh:
                txt = _fh.read()
        except Exception:
            continue
        for m in line_re.finditer(txt):
            keys.add(m.group(1))
    _LOC_KEYS_CACHE.update({"key": layers, "sig": sig, "val": set(keys)})
    return keys


def _diag_character_unrecruited(root, own_only=True):
    """common/characters 里有定义，但没有任何国家的 recruit_character 招募它。

    人物光定义不招募，游戏里不出现在将领/领袖列表，也不报错。
    """
    out = []
    top, targets = _scan_targets(root, own_only)
    if not targets:
        return out

    # 我们自己的 character id
    mine = {}
    for base_dir in targets:
        cd = os.path.join(base_dir, "common", "characters")
        if not os.path.isdir(cd):
            continue
        for fn in sorted(os.listdir(cd)):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(cd, fn)
            try:
                with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
                    lines = _fh.read().splitlines()
            except Exception:
                continue
            # 只取 characters 块的直接子级。块里的 corps_commander / advisor /
            # country_leader 是类型块，不是人物 id，按花括号深度区分。
            in_chars = False
            depth = 0
            rel = _layer_rel(top, base_dir, os.path.join("common", "characters", fn).replace(os.sep, "/"))
            for i, ln in enumerate(lines, 1):
                stripped = ln.strip()
                if not in_chars:
                    if re.match(r'^[ \t]*characters[ \t]*=\s*\{\s*$', ln):
                        in_chars = True
                        depth = 1
                    continue
                if depth == 1 and stripped.endswith('{'):
                    m = re.match(r'^([A-Za-z_][A-Za-z0-9_.\-]*)[ \t]*=\s*\{\s*$', stripped)
                    if m:
                        mine[(base_dir, m.group(1))] = (fn, rel, i, stripped)
                depth += ln.count('{') - ln.count('}')
                if depth <= 0:
                    in_chars = False
    if not mine:
        return out

    # 所有层里被招募的
    recruited = set()
    for b in (mod_layers(top) or []):
        if not b:
            continue
        hd = os.path.join(b, "history", "countries")
        if not os.path.isdir(hd):
            continue
        for fn in os.listdir(hd):
            if not fn.endswith(".txt"):
                continue
            try:
                with io.open(os.path.join(hd, fn), encoding="utf-8-sig", errors="replace") as _fh:
                    txt = _fh.read()
            except Exception:
                continue
            for m in re.finditer(r'(?m)^\s*recruit_character\s*=\s*([A-Za-z0-9_.\-]+)', txt):
                recruited.add(m.group(1))

    for (_bd, cid), (fn, rel, ln, raw) in sorted(mine.items(), key=lambda x: (x[1][1], x[1][2], x[0][1])):
        if cid in recruited:
            continue
        out.append(_finding(
            "script.character.not_recruited", "warning",
            "%s 里定义了人物 %s，但没有任何国家的 recruit_character 招募它，"
            "游戏里不会出现在将领或领袖列表" % (fn, cid),
            rel, ln, raw,
            "在对应国家的 history/countries 里加 recruit_character = %s" % cid))
    return out


def _diag_localisation_missing(root, own_only=True):
    """mod 里引用的本地化键有没有定义。

    只查我们自己写的文件（人物的 name、剧本的 name/desc、决议的 title），
    父层和本体的键不查，避免误报。
    """
    out = []
    top, targets = _scan_targets(root, own_only)
    if not targets:
        return out

    # 先收集本 mod 待校验的键；没有候选文件时直接返回，避免无谓遍历原版 localisation/（28s）
    cands = []

    def collect(base_dir, path, rel, pat, what):
        p = os.path.join(base_dir, path.replace("/", os.sep))
        if not os.path.isfile(p):
            return
        try:
            with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
                lines = _fh.read().splitlines()
        except Exception:
            return
        for i, ln in enumerate(lines, 1):
            m = re.search(pat, ln)
            if not m:
                continue
            k = m.group(1).strip().strip('"')
            if not re.match(r'^[A-Za-z_][A-Za-z0-9_.\-]*$', k):
                continue
            cands.append((_layer_rel(top, base_dir, rel), i, ln.strip(), what, k))

    for base_dir in targets:
        # 剧本（扫描目录下所有 .txt，兼容 unique_editor_filename 派生名）
        bd = os.path.join(base_dir, "common", "bookmarks")
        if os.path.isdir(bd):
            for fn in sorted(os.listdir(bd)):
                if fn.lower().endswith(".txt"):
                    collect(base_dir, "common/bookmarks/" + fn,
                            "common/bookmarks/" + fn,
                            r'^\s*(?:name|desc)\s*=\s*"?([A-Za-z_][A-Za-z0-9_.\-]*)"?',
                            "剧本名/描述")
        # 人物
        cd = os.path.join(base_dir, "common", "characters")
        if os.path.isdir(cd):
            for fn in os.listdir(cd):
                if fn.endswith(".txt"):
                    collect(base_dir, "common/characters/" + fn, "common/characters/" + fn,
                            r'^\s*name\s*=\s*"?([A-Za-z_][A-Za-z0-9_.\-]*)"?', "人物名")
    if not cands:
        return out

    keys = _loc_keys(top)
    if not keys:
        return out
    for rel, i, raw_ln, what, k in cands:
        if k in keys:
            continue
        out.append(_finding(
            "loc.key_missing", "info",
            "%s 第 %d 行的%s用了键 %s，但 localisation 里没有这个键，界面会显示裸 key"
            % (rel, i, what, k),
            rel, i, raw_ln,
            '在 localisation 下补一行 %s:0 "显示文本"' % k))
    return out


def _diag_tag_def_missing(root, own_only=True):
    """新建的国家 tag 缺 TAG_DEF 本地化。

    缺了不报错，但通用事件和决议里引用该国名字的地方会显示异常。
    """
    out = []
    top, targets = _scan_targets(root, own_only)
    if not targets:
        return out

    tagmap = {}
    for base_dir in targets:
        cd = os.path.join(base_dir, "common", "countries")
        if not os.path.isdir(cd):
            continue
        td = os.path.join(base_dir, "common", "country_tags")
        if os.path.isdir(td):
            for fn in os.listdir(td):
                if not fn.endswith(".txt"):
                    continue
                try:
                    with io.open(os.path.join(td, fn), encoding="utf-8-sig", errors="replace") as _fh:
                        txt = _fh.read()
                except Exception:
                    continue
                for m in re.finditer(r'(?m)^\s*([A-Z0-9]{3})\s*=\s*"([^"]+)"', txt):
                    tagmap[m.group(1)] = (base_dir, m.group(2))
    if not tagmap:
        return out

    keys = _loc_keys(top)
    for tag, (base_dir, _cfn) in sorted(tagmap.items()):
        if tag + "_DEF" in keys:
            continue
        rel = _layer_rel(top, base_dir, os.path.join("common", "country_tags", "zz_editor_tags.txt").replace(os.sep, "/"))
        out.append(_finding(
            "loc.tag_def_missing", "warning",
            "国家 %s 缺 %s_DEF 本地化，通用事件/决议里引用该国名字时会显示异常"
            % (tag, tag),
            rel, 0, tag,
            '在 localisation 下补 %s_DEF:0 "国家全名" 和 %s:0 "短名"' % (tag, tag)))
    return out


# 大写词里不是国家 tag 的那些（作用域切换、逻辑运算、布尔常量）
_TAG_NOT_A_TAG = {
    "ROOT", "FROM", "PREV", "THIS", "OWNER", "CONTROLLER", "CAPITAL",
    "OVERLORD", "FACTION_LEADER", "ENEMY", "IF", "ELSE", "ELSE_IF",
    "AND", "OR", "NOT", "NOR", "NAND", "XOR", "LIMIT", "YES", "NO", "DEF",
    "FROMFROM", "MIO", "VICTORY_POINTS", "TAG",
}


# 这些目录里的顶层大写块是数据分组（人名组、师命名组等），
# 只是碰巧和 3 位 tag 同形，不是 scope 切换
_TAG_SKIP_DIRS = ("common/names", "common/units/names", "common/units/codenames")


def _collect_effective_tags(top):
    """收集当前叠加链实际生效的国家 tag 与别名集合（尊重 replace_path）。"""
    known = set()
    layers = mod_layers(top) or [top] or []
    for sub in ("common/country_tags", "common/country_tag_aliases"):
        srcs = layers
        owner = _replace_owner(top, sub)
        if owner and owner in layers:
            # 只剩接管层及以上有效
            srcs = layers[layers.index(owner):]
        for layer in srcs:
            td = os.path.join(layer, *sub.split("/"))
            if not os.path.isdir(td):
                continue
            try:
                fns = os.listdir(td)
            except Exception:
                continue
            for fn in fns:
                if not fn.endswith(".txt"):
                    continue
                try:
                    with io.open(os.path.join(td, fn), encoding="utf-8-sig",
                                 errors="replace") as _fh:
                        txt = _fh.read()
                except Exception:
                    continue
                for m in re.finditer(r'(?m)^\s*([A-Z][A-Z0-9]{2})\s*=', txt):
                    known.add(m.group(1))
    return known


def _diag_tag_undefined(root, own_only=True):
    """引用了不存在的国家 tag。

    `TAG = { ... }` 在脚本里是 scope 切换，`original_tag = TAG` 是筛选条件。
    tag 没在 common/country_tags 里定义时，游戏对每一处引用报一条
    "Unknown trigger-type: TAG" 或 "Unknown effect-type: TAG"。

    这是实测最贵的那类错误：一个被 replace 掉的 country_tags 目录，
    在 40 省的测试地图上刷出 58762 行 error.log，其中九成是它。
    静态跑这里 2 秒就能定位，不必等 150 秒一轮的真机加载。
    """
    out = []
    top, targets = _scan_targets(root, own_only)
    if not targets:
        return out

    scan_txts = []
    for base_dir in targets:
        for dirpath, _dirs, files in os.walk(base_dir):
            rel_dir = os.path.relpath(dirpath, base_dir).replace(os.sep, "/")
            if rel_dir.startswith("localisation") or rel_dir.startswith("map") or rel_dir.startswith(".git"):
                continue
            if any(rel_dir.startswith(d) for d in _TAG_SKIP_DIRS):
                continue
            for fn in sorted(files):
                if fn.endswith(".txt"):
                    base = (rel_dir + "/" + fn) if rel_dir != "." else fn
                    scan_txts.append((base_dir, os.path.join(dirpath, fn), _layer_rel(top, base_dir, base)))
    if not scan_txts:
        return out

    # 1) 收集「实际能生效」的 tag。
    known = _collect_effective_tags(top)
    if not known:
        return out

    # 3) 两种明确的 tag 引用写法
    pat_scope = re.compile(r'^([A-Z][A-Z0-9]{2})\s*=\s*\{')
    pat_param = re.compile(
        r'^(?:original_tag|country_exists|has_tag|tag|add_core|remove_core|'
        r'has_war_with|is_in_faction_with|is_guaranteed_by)\s*=\s*([A-Z][A-Z0-9]{2})\s*$')

    per_file = {}
    total = 0
    dropped = 0
    for _base_dir, p, rel in scan_txts:
        try:
            with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
                lines = _fh.read().splitlines()
        except Exception:
            continue
        for i, ln in enumerate(lines, 1):
            st = ln.strip()
            if not st or st.startswith("#"):
                continue
            m = pat_scope.match(st) or pat_param.match(st)
            if not m:
                continue
            tg = m.group(1)
            if tg in known or tg in _TAG_NOT_A_TAG:
                continue
            n = per_file.get(rel, 0)
            if n >= 3 or total >= 30:
                dropped += 1
                continue
            per_file[rel] = n + 1
            total += 1
            out.append(_finding(
                "script.tag_undefined", "error",
                "引用了未定义的国家 tag %s；游戏会对这处引用报 "
                "Unknown trigger/effect-type: %s" % (tg, tg),
                rel, i, st,
                "确认 common/country_tags 里有 %s，或改成这个 mod 实际使用的 tag" % tg))
    if dropped:
        out.append(_finding(
            "script.tag_undefined.more", "info",
            "还有 %d 处同类引用未逐条列出（同一文件最多 3 条、总数最多 30 条）" % dropped,
            "", 0, "",
            "先修上面列出的，再重新跑诊断看剩余"))
    return out


def _diag_division_template_missing(root, own_only=True):
    """units 里引用的 division_template 有没有定义。"""
    out = []
    top, targets = _scan_targets(root, own_only)
    if not targets:
        return out

    defined = set()
    used = []
    for base_dir in targets:
        ud = os.path.join(base_dir, "history", "units")
        if not os.path.isdir(ud):
            continue
        for fn in sorted(os.listdir(ud)):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(ud, fn)
            try:
                with io.open(p, encoding="utf-8-sig", errors="replace") as _fh:
                    lines = _fh.read().splitlines()
            except Exception:
                continue
            rel = _layer_rel(top, base_dir, os.path.join("history", "units", fn).replace(os.sep, "/"))
            for i, ln in enumerate(lines, 1):
                m = re.match(r'^[ \t]*division_template\s*=\s*\{\s*$', ln)
                if m:
                    # 下一行通常是 name = "..."
                    for j in range(i, min(i + 5, len(lines))):
                        nm = re.search(r'name\s*=\s*"([^"]+)"', lines[j])
                        if nm:
                            defined.add(nm.group(1))
                            break
                    continue
                m2 = re.search(r'division_template\s*=\s*"([^"]+)"', ln)
                if m2:
                    used.append((fn, rel, i, m2.group(1), ln.strip()))
    if not used:
        return out

    # 父层也可能定义模板
    for b in (mod_layers(top) or []):
        if not b:
            continue
        d2 = os.path.join(b, "history", "units")
        if not os.path.isdir(d2):
            continue
        for fn in os.listdir(d2):
            if not fn.endswith(".txt"):
                continue
            try:
                with io.open(os.path.join(d2, fn), encoding="utf-8-sig", errors="replace") as _fh:
                    txt = _fh.read()
            except Exception:
                continue
            for m in re.finditer(r'division_template\s*=\s*\{[^}]*?name\s*=\s*"([^"]+)"', txt, re.S):
                defined.add(m.group(1))

    for fn, rel, i, tname, raw in used:
        if tname in defined:
            continue
        out.append(_finding(
            "script.division_template.missing", "error",
            "%s 第 %d 行引用了师团模板 %s，但整个叠加链里都没有定义这个模板"
            % (fn, i, tname),
            rel, i, raw,
            '补一个 division_template = { name = "%s" ... }，或改成已存在的模板名' % tname))
    return out


_BOOKMARK_NON_TAG_BLOCKS = {
    "filters", "label_order", "effect", "---", "zzz",
    "available", "ideas", "focuses", "label", "required_dlc", "randomize_weather",
}


def _bm_brace_error(text):
    """检查去注释文本的花括号与引号配平，返回 (ok, err_line, detail)。"""
    line = 1
    depth = 0
    instr = False
    open_line = 1
    str_line = 1
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
        elif ch == '"' and not (i > 0 and text[i - 1] == "\\"):
            if not instr:
                str_line = line
            instr = not instr
        elif not instr:
            if ch == "{":
                if depth == 0:
                    open_line = line
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth < 0:
                    return False, line, "多余的右花括号 '}'"
        i += 1
    if instr:
        return False, str_line, "存在未闭合的双引号字符串"
    if depth != 0:
        return False, open_line, "存在 %d 个未闭合的 '{'" % depth
    return True, 0, ""


def _bm_top_entries(src):
    """解析块直接子级条目：[(key, is_quoted, is_block, val_or_body, key_pos, inner_offset)]。"""
    out = []
    i = 0
    n = len(src)
    while i < n:
        while i < n and src[i] in " \t\r\n":
            i += 1
        if i >= n:
            break
        key_pos = i
        if src[i] == '"':
            i += 1
            buf = []
            while i < n:
                ch = src[i]
                if ch == "\\" and i + 1 < n:
                    buf.append(src[i + 1])
                    i += 2
                    continue
                if ch == '"':
                    i += 1
                    break
                buf.append(ch)
                i += 1
            key = "".join(buf)
            is_quoted = True
        else:
            m = re.match(r'[A-Za-z0-9_.\-:]+', src[i:])
            if not m:
                i += 1
                continue
            key = m.group(0)
            i += m.end()
            is_quoted = False

        while i < n and src[i] in " \t\r\n":
            i += 1
        if i >= n or src[i] != "=":
            continue
        i += 1
        while i < n and src[i] in " \t\r\n":
            i += 1
        if i >= n:
            break

        if src[i] == "{":
            end = brace_match(src, i)
            out.append((key, is_quoted, True, src[i + 1:end - 1], key_pos, i + 1))
            i = end
        elif src[i] == '"':
            val_pos = i + 1
            i += 1
            buf = []
            while i < n:
                ch = src[i]
                if ch == "\\" and i + 1 < n:
                    buf.append(src[i + 1])
                    i += 2
                    continue
                if ch == '"':
                    i += 1
                    break
                buf.append(ch)
                i += 1
            out.append((key, is_quoted, False, "".join(buf), key_pos, val_pos))
        else:
            val_pos = i
            while i < n and src[i] not in " \t\r\n{}":
                i += 1
            out.append((key, is_quoted, False, src[val_pos:i], key_pos, val_pos))
    return out


def _diag_bookmarks(root, own_only=True):
    """书签 L2 静态检查（BOM / 花括号 / 结构 / 四段日期 / tag / 意识形态 / default / loc / gfx）。"""
    out = []
    top, targets = _scan_targets(root, own_only)
    if not targets:
        return out

    target_set = {os.path.normcase(os.path.abspath(t)) for t in targets}
    bm_files = []
    if own_only:
        bd = os.path.join(top, "common", "bookmarks")
        if os.path.isdir(bd):
            for fn in sorted(os.listdir(bd)):
                if fn.lower().endswith(".txt"):
                    fp = os.path.join(bd, fn)
                    if os.path.isfile(fp):
                        bm_files.append((top, fp, fn))
    else:
        for base_dir, d, fn in effective_layer_files("common/bookmarks", top):
            if os.path.normcase(os.path.abspath(base_dir)) in target_set:
                bm_files.append((base_dir, os.path.join(d, fn), fn))

    if not bm_files:
        return out

    known_tags = _collect_effective_tags(top)
    valid_ides = set(load_ideology_names(top))
    loc_keys = _loc_keys(top)
    known_gfx = _gfx_names(top)

    def _line_str(raw_lines, ln_no):
        if 1 <= ln_no <= len(raw_lines):
            return raw_lines[ln_no - 1].strip()
        return ""

    for base_dir, fp, fn in bm_files:
        rel = _layer_rel(top, base_dir, "common/bookmarks/" + fn)
        try:
            with io.open(fp, "rb") as _fh:
                raw_bytes = _fh.read()
        except Exception:
            continue

        # 1) BOM 检查
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            out.append(_finding(
                "bookmark.bom", "error",
                "%s 带有 UTF-8 BOM，HOI4 读取 common/bookmarks/*.txt 会把 BOM 吃进首个键名导致解析失败" % fn,
                rel, 1, "",
                "用无 BOM UTF-8 重新保存该文件"))

        raw = raw_bytes.decode("utf-8-sig", "replace")
        raw_lines = raw.splitlines()
        text = _strip_keep_len(raw)

        # 2) 花括号配平
        b_ok, b_line, b_msg = _bm_brace_error(text)
        if not b_ok:
            out.append(_finding(
                "bookmark.braces", "error",
                "%s 第 %d 行花括号或引号未配平：%s" % (fn, b_line, b_msg),
                rel, b_line, _line_str(raw_lines, b_line),
                "补齐或删去多余的 '{' / '}' / '\"'"))
            continue

        # 3) 结构检查（放行纯空或纯注释覆写占位文件，如 MD 的 the_gathering_storm.txt）
        if not text.strip():
            continue
        bm_containers = [e for e in _bm_top_entries(text) if e[2] and e[0] == "bookmarks"]
        if not bm_containers:
            first_ln = next((idx for idx, ln in enumerate(raw_lines, 1)
                             if ln.strip() and not ln.strip().startswith("#")), 1)
            out.append(_finding(
                "bookmark.structure", "error",
                "%s 非空但缺少顶层 bookmarks = { ... } 块" % fn,
                rel, first_ln, _line_str(raw_lines, first_ln),
                "用 bookmarks = { bookmark = { ... } } 包裹剧本定义"))
            continue

        bm_blocks = []
        for _k, _q, _ib, ob_src, _kp, ob_off in bm_containers:
            for k2, _q2, ib2, b_src, kp2, b_off in _bm_top_entries(ob_src):
                if ib2 and k2 == "bookmark":
                    bm_blocks.append((b_src, ob_off + b_off, ob_off + kp2))
        if not bm_blocks:
            ln0 = text[:bm_containers[0][4]].count("\n") + 1
            out.append(_finding(
                "bookmark.structure", "warning",
                "%s 的 bookmarks = { } 块内没有任何 bookmark = { ... } 剧本" % fn,
                rel, ln0, _line_str(raw_lines, ln0),
                "至少添加一个 bookmark = { ... } 剧本块"))
            continue

        for b_src, b_off, bm_hdr_pos in bm_blocks:
            bm_hdr_line = text[:bm_hdr_pos].count("\n") + 1
            bm_name = None
            bm_desc = None
            bm_date = None
            bm_pic = None
            bm_dc = None
            country_blocks = []

            for k, _q, is_blk, val, kp, inner_off in _bm_top_entries(b_src):
                ln_no = text[:b_off + kp].count("\n") + 1
                if is_blk:
                    if k.lower() not in _BOOKMARK_NON_TAG_BLOCKS:
                        country_blocks.append((k, ln_no, val, b_off + inner_off))
                    continue
                if k == "name":
                    bm_name = (val.strip(), ln_no)
                elif k == "desc":
                    bm_desc = (val.strip(), ln_no)
                elif k == "date":
                    bm_date = (val.strip(), ln_no)
                elif k == "picture":
                    bm_pic = (val.strip(), ln_no)
                elif k == "default_country":
                    bm_dc = (val.strip(), ln_no)

            # 4) 四段日期校验 YYYY.M.D.H
            if bm_date is None:
                out.append(_finding(
                    "bookmark.date", "error",
                    "%s 第 %d 行的 bookmark 缺少 date 字段" % (fn, bm_hdr_line),
                    rel, bm_hdr_line, _line_str(raw_lines, bm_hdr_line),
                    "补充四段日期，例如 date = 1936.1.1.12"))
            else:
                dt_val, dt_ln = bm_date
                m_dt = re.match(r'^(\d{4})\.(\d{1,2})\.(\d{1,2})\.(\d{1,2})$', dt_val)
                date_ok = False
                if m_dt:
                    _y, mo, da, hr = (int(m_dt.group(1)), int(m_dt.group(2)),
                                      int(m_dt.group(3)), int(m_dt.group(4)))
                    date_ok = (1 <= mo <= 12) and (1 <= da <= 31) and (0 <= hr <= 24)
                if not date_ok:
                    out.append(_finding(
                        "bookmark.date", "error",
                        "%s 第 %d 行剧本日期 %s 非法（必须为 YYYY.M.D.H，月 1-12、日 1-31、时 0-24）"
                        % (fn, dt_ln, dt_val),
                        rel, dt_ln, _line_str(raw_lines, dt_ln),
                        "改为合法四段日期（如 1936.1.1.12）"))

            # 7a) default_country 校验（允许如 TNO 仅含 date 的占位第二书签缺省，其余书签缺或无效报 error）
            if bm_dc is not None:
                if not bm_dc[0]:
                    out.append(_finding(
                        "bookmark.default_country", "error",
                        "%s 第 %d 行的 default_country 为空" % (fn, bm_dc[1]),
                        rel, bm_dc[1], _line_str(raw_lines, bm_dc[1]),
                        '补充合法的国家 tag，例如 default_country = "GER"'))
                elif known_tags and bm_dc[0] not in known_tags:
                    dc_val, dc_ln = bm_dc
                    out.append(_finding(
                        "bookmark.default_country", "error",
                        "%s 第 %d 行的 default_country = %s 不在当前生效 country_tags 中"
                        % (fn, dc_ln, dc_val),
                        rel, dc_ln, _line_str(raw_lines, dc_ln),
                        "改为当前 mod 已定义的国家 tag"))
            elif country_blocks or bm_name:
                out.append(_finding(
                    "bookmark.default_country", "error",
                    "%s 第 %d 行的 bookmark 缺少 default_country" % (fn, bm_hdr_line),
                    rel, bm_hdr_line, _line_str(raw_lines, bm_hdr_line),
                    '补充合法的国家 tag，例如 default_country = "GER"'))

            # 8) 本地化键与贴图校验
            if loc_keys:
                for lbl, item in (("剧本名 name", bm_name), ("剧本描述 desc", bm_desc)):
                    if item and item[0] and item[0] not in loc_keys:
                        out.append(_finding(
                            "bookmark.loc", "info",
                            "%s 第 %d 行的%s引用键 %s，但 localisation 里未找到该键"
                            % (fn, item[1], lbl, item[0]),
                            rel, item[1], _line_str(raw_lines, item[1]),
                            '在 localisation/<lang>/ 下补一条 %s:0 "显示文本"' % item[0]))
            if known_gfx and bm_pic and bm_pic[0] and bm_pic[0] not in known_gfx:
                pic_val, pic_ln = bm_pic
                out.append(_finding(
                    "bookmark.picture", "warning",
                    "%s 第 %d 行的 picture = %s 在 interface/*.gfx 中找不到"
                    % (fn, pic_ln, pic_val),
                    rel, pic_ln, _line_str(raw_lines, pic_ln),
                    "确认该 GFX_ 贴图已在 interface/*.gfx 中定义"))

            # 5) 国家 tag 校验 & 6) ideology 校验
            for tag_key, c_ln, c_src, c_off in country_blocks:
                if known_tags:
                    if tag_key not in known_tags:
                        out.append(_finding(
                            "bookmark.tag", "error",
                            "%s 第 %d 行的国家块 %s 不在当前生效 country_tags / aliases 中"
                            % (fn, c_ln, tag_key),
                            rel, c_ln, _line_str(raw_lines, c_ln),
                            "确认该国家 tag 已在 common/country_tags 中定义"))
                elif not re.match(r'^[A-Z][A-Z0-9]{2}$', tag_key):
                    out.append(_finding(
                        "bookmark.tag", "warning",
                        "%s 第 %d 行的国家块 %s 不符合 3 位大写 tag 格式"
                        % (fn, c_ln, tag_key),
                        rel, c_ln, _line_str(raw_lines, c_ln),
                        "使用 3 位大写字母/数字组成合法国家 tag"))

                for ck, _cq, c_is_blk, c_val, c_kp, _c_ioff in _bm_top_entries(c_src):
                    if c_is_blk:
                        continue
                    if ck == "ideology":
                        ide_val = c_val.strip()
                        ide_ln = text[:c_off + c_kp].count("\n") + 1
                        if ide_val not in valid_ides:
                            sample = ", ".join(sorted(valid_ides)[:4])
                            out.append(_finding(
                                "bookmark.ideology", "error",
                                "%s 第 %d 行国家 %s 的 ideology = %s 不在当前 mod 意识形态列表（%s...）中"
                                % (fn, ide_ln, tag_key, ide_val, sample),
                                rel, ide_ln, _line_str(raw_lines, ide_ln),
                                "改为当前 mod common/ideologies/ 下定义的合法意识形态名"))

    # 7b) 全链生效书签 multi_default 检查
    default_hits = []
    for base_dir, d, fn in effective_layer_files("common/bookmarks", top):
        fp = os.path.join(d, fn)
        try:
            with io.open(fp, encoding="utf-8-sig", errors="replace") as _fh:
                raw = _fh.read()
        except Exception:
            continue
        raw_lines = raw.splitlines()
        text = _strip_keep_len(raw)
        if not text.strip():
            continue
        ok_b, _bl, _bm = _bm_brace_error(text)
        if not ok_b:
            continue
        rel = _layer_rel(top, base_dir, "common/bookmarks/" + fn)
        for _k, _q, is_blk, ob_src, _kp, ob_off in _bm_top_entries(text):
            if not is_blk or _k != "bookmarks":
                continue
            for k2, _q2, ib2, b_src, _kp2, b_off in _bm_top_entries(ob_src):
                if not ib2 or k2 != "bookmark":
                    continue
                for bk, _bq, b_is_blk, b_val, b_kp, _bio in _bm_top_entries(b_src):
                    if not b_is_blk and bk == "default" and b_val.strip().lower() == "yes":
                        ln_no = text[:ob_off + b_off + b_kp].count("\n") + 1
                        default_hits.append((base_dir, fn, rel, ln_no, _line_str(raw_lines, ln_no)))

    if len(default_hits) > 1:
        ab_top = os.path.normcase(os.path.abspath(top))
        if own_only:
            top_hits = [h for h in default_hits
                        if os.path.normcase(os.path.abspath(h[0])) == ab_top]
            emit_hits = top_hits[1:] if len(top_hits) > 1 else top_hits
        else:
            emit_hits = [h for h in default_hits[1:] if not is_under_game(h[0])]
        for _bd, fn, rel, ln_no, excerpt in emit_hits:
            out.append(_finding(
                "bookmark.multi_default", "warning",
                "%s 第 %d 行设置了 default = yes，但当前生效剧本中已有 %d 个 default = yes（存在默认剧本冲突）"
                % (fn, ln_no, len(default_hits)),
                rel, ln_no, excerpt,
                "非主剧本建议移除 default = yes，只保留一个默认选中剧本"))

    return out
