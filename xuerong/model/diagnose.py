# -*- coding: utf-8 -*-
"""体检 / 诊断（P0-3 从 focus_editor.py 迁入）。

只读：扫描已加载的 mod，产出 findings 列表交给前端渲染，不改任何文件。
（唯一例外是 qa/map_diag.py 的地图格式检查，它也只读。）

依赖边界：
  · 叠加链与 descriptor → xuerong.core.paths
  · replace 侧的小工具 → xuerong.model.replace（同层，允许）
  · 全局容器 → xuerong.state
  · 零钩子：不调门面的任何函数
"""
import io
import os
import re
import sys

from xuerong import state
from xuerong.core import paths
from xuerong.core.paths import _mod_descriptor, _replace_owner, _top_mod, is_under_game, mod_layers
from xuerong.core.text import find_blocks, strip_comments, top_items
from xuerong.model.replace import (_REF_KEYWORDS, _replace_adopt_block, _replace_collect,
                                   _replace_ignore_key, _replace_ignored, _replace_ref_dir)


def _qa_dir():
    """qa/ 目录：源码是 work/qa（或 tools/qa），打包后是 _MEIPASS/qa。"""
    here = paths.app_dir()
    for base in (getattr(sys, "_MEIPASS", "") or "", here, os.path.dirname(here)):
        for rel in (("qa",), ("tools", "qa")):
            p = os.path.join(base, *rel) if base else ""
            if p and os.path.isdir(p):
                return p
    return os.path.join(here, "qa")


def _finding(code, severity, msg, file="", line=0, excerpt="", repair="", fix=None):
    """一条诊断结果。

    fix 非空表示这条 finding 有可执行的动作（诊断面板会渲染成按钮）：

        {"kind": "replace_dangling",        动作类型
         "sub": "common/ideas",             出问题的目录（被 replace 掉的那个）
         "subs": ["common/ideas", ...],     同一行里涉及的多个被 replace 目录
         "ref_dir": "common/achievements",  引用方目录（已去掉 vanilla/ 前缀）
         "options": ["drop_replace", "adopt_ref_dir", "ignore"]}

    空 dict 和不传等价，前端按「没有按钮」处理。
    """
    return {"code": code, "severity": severity, "msg": msg,
            "file": file, "line": line or 0,
            "excerpt": (excerpt or "").strip()[:200], "repair": repair,
            "fix": fix or {}}


def _diag_oob_not_referenced(root):
    """history/units 下的 OOB 文件有没有被国家历史点名。

    HOI4 不扫描这个目录，靠 set_oob / set_air_oob / set_naval_oob 逐条点名。
    自己起个文件名写进去，游戏一个单位都不会加载，而且 error.log 里不会有任何提示。
    """
    out = []
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out

    ud = os.path.join(top, "history", "units")
    if not os.path.isdir(ud):
        return out

    # 收集所有被点名的名字
    referenced = set()
    hd = os.path.join(top, "history", "countries")
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
                txt = io.open(os.path.join(h2, fn), encoding="utf-8-sig", errors="replace").read()
            except Exception:
                continue
            for k in ("set_oob", "oob", "set_air_oob", "air_oob",
                      "set_naval_oob", "naval_oob", "load_oob"):
                for m in re.finditer(r'(?m)^\s*' + k + r'\s*=\s*"([^"]+)"', txt):
                    referenced.add(m.group(1).strip())

    for fn in sorted(os.listdir(ud)):
        if not fn.endswith(".txt"):
            continue
        stem = fn[:-4]
        if stem in referenced:
            continue
        p = os.path.join(ud, fn)
        try:
            txt = io.open(p, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        if not re.search(r'(?m)^\s*(units|air_wings|division_template|fleet)\s*=\s*\{', txt):
            continue
        first = ""
        for i, ln in enumerate(txt.splitlines(), 1):
            if ln.strip():
                first = ln.strip()
                break
        out.append(_finding(
            "script.oob.not_referenced", "warning",
            "%s 里有内容，但没有被任何国家历史的 set_oob / set_air_oob / set_naval_oob 点名，"
            "游戏不会加载它（也不报错）" % fn,
            os.path.join("history", "units", fn).replace(os.sep, "/"),
            0, first,
            "给你自己的国家加一条 set_oob = \"%s\"；或者把内容并进已被点名的那个文件"
            % stem))
    return out


def _gfx_names(root):
    """收集所有 interface/*.gfx 里定义的 sprite 名。"""
    names = set()
    for b in (mod_layers(root) or []):
        if not b:
            continue
        gd = os.path.join(b, "interface")
        if not os.path.isdir(gd):
            continue
        for fn in os.listdir(gd):
            if not fn.lower().endswith(".gfx"):
                continue
            try:
                txt = io.open(os.path.join(gd, fn), encoding="utf-8-sig", errors="replace").read()
            except Exception:
                continue
            for m in re.finditer(r'name\s*=\s*"([^"]+)"', txt):
                names.add(m.group(1))
    return names


def _diag_gfx_missing(root):
    """icon / picture 引用的 sprite 在本体和 mod 里都找不到。

    HOI4 的决议 icon 会自动补 GFX_decision_，国策 icon 用完整名，
    精神 picture 自动补 GFX_idea_。名字写错不报错，界面上一片空白。
    """
    out = []
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out
    known = _gfx_names(top)
    if not known:
        return out

    targets = [
        ("common/decisions", r'(?m)^\s*icon\s*=\s*([A-Za-z_][A-Za-z0-9_]*)'),
        ("common/decisions/categories", r'(?m)^\s*icon\s*=\s*([A-Za-z_][A-Za-z0-9_]*)'),
        ("common/national_focus", r'(?m)^\s*icon\s*=\s*([A-Za-z_][A-Za-z0-9_]*)'),
        ("common/ideas", r'(?m)^\s*picture\s*=\s*([A-Za-z_][A-Za-z0-9_]*)'),
    ]
    for sub, pat in targets:
        d = os.path.join(top, sub.replace("/", os.sep))
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(d, fn)
            try:
                lines = io.open(p, encoding="utf-8-sig", errors="replace").read().splitlines()
            except Exception:
                continue
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
                    os.path.join(sub, fn).replace(os.sep, "/"), i, ln.strip(),
                    "检查拼写；决议 icon 写裸名（游戏自动补 GFX_decision_），"
                    "国策 icon 写完整 GFX_ 名，精神 picture 写裸名（自动补 GFX_idea_）"))
    return out


def _diag_recruit_last_line(root):
    """history/countries 里 recruit_character 不能是最后一行。

    文件末尾就是 recruit_character 时招募会静默失败——人物定义了但游戏里不出现。
    """
    out = []
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out
    d = os.path.join(top, "history", "countries")
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".txt"):
            continue
        p = os.path.join(d, fn)
        try:
            lines = io.open(p, encoding="utf-8-sig", errors="replace").read().splitlines()
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
            out.append(_finding(
                "script.recruit.last_line", "warning",
                "%s 的 recruit_character 在文件最后一行，招募会静默失败" % fn,
                os.path.join("history", "countries", fn).replace(os.sep, "/"), i, ln.strip(),
                "在文件末尾补一个空行或注释"))
    return out


def _diag_decision_category(root):
    """决议引用的类别有没有在 common/decisions/categories 里定义。

    1.13 起决议类别必须注册，否则报 Unknown category / Invalid Decision Category。
    """
    out = []
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out
    dd = os.path.join(top, "common", "decisions")
    if not os.path.isdir(dd):
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
                txt = io.open(os.path.join(cd, fn), encoding="utf-8-sig", errors="replace").read()
            except Exception:
                continue
            for m in re.finditer(r'(?m)^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=\s*\{', txt):
                cats.add(m.group(1))

    for fn in sorted(os.listdir(dd)):
        if not fn.endswith(".txt"):
            continue
        p = os.path.join(dd, fn)
        try:
            lines = io.open(p, encoding="utf-8-sig", errors="replace").read().splitlines()
        except Exception:
            continue
        for i, ln in enumerate(lines, 1):
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)[ \t]*=\s*\{\s*$', ln)
            if not m:
                continue
            name = m.group(1)
            if name in cats or name.endswith("_category") is False and name in cats:
                continue
            if name in cats:
                continue
            # 顶层块名就是类别名；只要不是已注册的类别就提醒
            if name in ("categories",):
                continue
            out.append(_finding(
                "script.decision.category_undefined", "warning",
                "%s 第 %d 行的顶层块 %s 看起来是决议类别，但没有在 "
                "common/decisions/categories 里注册" % (fn, i, name),
                os.path.join("common", "decisions", fn).replace(os.sep, "/"), i, ln.strip(),
                "在该文件里补一个同名类别块，或确认这里用的是已注册类别"))
    return out


def _loc_keys(root):
    """收集所有层 localisation/*.yml 里定义的键。"""
    keys = set()
    for b in (mod_layers(root) or []):
        if not b:
            continue
        for sub in ("localisation", "localisation/simp_chinese", "localisation/english"):
            d = os.path.join(b, sub.replace("/", os.sep))
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                if not fn.lower().endswith(".yml"):
                    continue
                try:
                    txt = io.open(os.path.join(d, fn), encoding="utf-8-sig", errors="replace").read()
                except Exception:
                    continue
                for m in re.finditer(r'(?m)^[ \t]*([A-Za-z_][A-Za-z0-9_.\-]*)\s*:\d*\s*"', txt):
                    keys.add(m.group(1))
    return keys


def _diag_character_unrecruited(root):
    """common/characters 里有定义，但没有任何国家的 recruit_character 招募它。

    人物光定义不招募，游戏里不出现在将领/领袖列表，也不报错。
    """
    out = []
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out

    # 我们自己的 character id
    mine = {}
    cd = os.path.join(top, "common", "characters")
    if not os.path.isdir(cd):
        return out
    for fn in sorted(os.listdir(cd)):
        if not fn.endswith(".txt"):
            continue
        p = os.path.join(cd, fn)
        try:
            lines = io.open(p, encoding="utf-8-sig", errors="replace").read().splitlines()
        except Exception:
            continue
        # 只取 characters 块的直接子级。块里的 corps_commander / advisor /
        # country_leader 是类型块，不是人物 id，按花括号深度区分。
        in_chars = False
        depth = 0
        for i, ln in enumerate(lines, 1):
            stripped = ln.strip()
            if not in_chars:
                if re.match(r'^[ \t]*characters[ \t]*=\s*\{\s*$', ln):
                    in_chars = True
                    depth = 1
                continue
            if depth == 1 and stripped.endswith('{'):
                m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)[ \t]*=\s*\{\s*$', stripped)
                if m:
                    mine[m.group(1)] = (fn, i, stripped)
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
                txt = io.open(os.path.join(hd, fn), encoding="utf-8-sig", errors="replace").read()
            except Exception:
                continue
            for m in re.finditer(r'(?m)^\s*recruit_character\s*=\s*([A-Za-z0-9_]+)', txt):
                recruited.add(m.group(1))

    for cid, (fn, ln, raw) in sorted(mine.items()):
        if cid in recruited:
            continue
        out.append(_finding(
            "script.character.not_recruited", "warning",
            "%s 里定义了人物 %s，但没有任何国家的 recruit_character 招募它，"
            "游戏里不会出现在将领或领袖列表" % (fn, cid),
            os.path.join("common", "characters", fn).replace(os.sep, "/"), ln, raw,
            "在对应国家的 history/countries 里加 recruit_character = %s" % cid))
    return out


def _diag_localisation_missing(root):
    """mod 里引用的本地化键有没有定义。

    只查我们自己写的文件（人物的 name、剧本的 name/desc、决议的 title），
    父层和本体的键不查，避免误报。
    """
    out = []
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out
    keys = _loc_keys(top)
    if not keys:
        return out

    def check(path, rel, pat, what):
        p = os.path.join(top, path.replace("/", os.sep))
        if not os.path.isfile(p):
            return
        try:
            lines = io.open(p, encoding="utf-8-sig", errors="replace").read().splitlines()
        except Exception:
            return
        for i, ln in enumerate(lines, 1):
            m = re.search(pat, ln)
            if not m:
                continue
            k = m.group(1).strip().strip('"')
            # 纯文本（含空格或非 ASCII）不是键，跳过
            if not re.match(r'^[A-Za-z_][A-Za-z0-9_.\-]*$', k):
                continue
            if k in keys:
                continue
            out.append(_finding(
                "loc.key_missing", "info",
                "%s 第 %d 行的%s用了键 %s，但 localisation 里没有这个键，界面会显示裸 key"
                % (rel, i, what, k),
                rel, i, ln.strip(),
                '在 localisation 下补一行 %s:0 "显示文本"' % k))

    # 剧本
    check("common/bookmarks/zz_editor_bookmarks.txt",
          "common/bookmarks/zz_editor_bookmarks.txt",
          r'^\s*(?:name|desc)\s*=\s*"?([A-Za-z_][A-Za-z0-9_.\-]*)"?', "剧本名/描述")
    # 人物
    cd = os.path.join(top, "common", "characters")
    if os.path.isdir(cd):
        for fn in os.listdir(cd):
            if fn.endswith(".txt"):
                check("common/characters/" + fn, "common/characters/" + fn,
                      r'^\s*name\s*=\s*"?([A-Za-z_][A-Za-z0-9_.\-]*)"?', "人物名")
    return out


def _diag_tag_def_missing(root):
    """新建的国家 tag 缺 TAG_DEF 本地化。

    缺了不报错，但通用事件和决议里引用该国名字的地方会显示异常。
    """
    out = []
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out

    cd = os.path.join(top, "common", "countries")
    if not os.path.isdir(cd):
        return out
    keys = _loc_keys(top)

    # tag 从 country_tags 反查文件名
    tags = {}
    for fn in os.listdir(cd):
        if not fn.endswith(".txt"):
            continue
        stem = fn[:-4]
        tags[stem] = fn

    td = os.path.join(top, "common", "country_tags")
    tagmap = {}
    if os.path.isdir(td):
        for fn in os.listdir(td):
            if not fn.endswith(".txt"):
                continue
            try:
                txt = io.open(os.path.join(td, fn), encoding="utf-8-sig", errors="replace").read()
            except Exception:
                continue
            for m in re.finditer(r'(?m)^\s*([A-Z0-9]{3})\s*=\s*"([^"]+)"', txt):
                tagmap[m.group(1)] = m.group(2)

    for tag, cfn in sorted(tagmap.items()):
        if tag + "_DEF" in keys:
            continue
        out.append(_finding(
            "loc.tag_def_missing", "warning",
            "国家 %s 缺 %s_DEF 本地化，通用事件/决议里引用该国名字时会显示异常"
            % (tag, tag),
            os.path.join("common", "country_tags", "zz_editor_tags.txt").replace(os.sep, "/"),
            0, tag,
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


# replace_path 掉这些目录时，原版内容会整体消失，
# 但原版（以及其他 mod）的脚本仍然在引用它们
_REPLACE_RISK = (
    ("common/country_tags", "国家 tag", r'(?m)^\s*([A-Z][A-Z0-9]{2})\s*='),
    ("common/scripted_triggers", "脚本化 trigger", r'(?m)^\s*([a-z_][a-z0-9_]*)\s*=\s*\{'),
    ("common/scripted_effects", "脚本化 effect", r'(?m)^\s*([a-z_][a-z0-9_]*)\s*=\s*\{'),
    ("common/ideas", "国家精神", r'(?m)^\s*([a-z_][a-z0-9_]*)\s*=\s*\{'),
    ("common/technologies", "科技", r'(?m)^\s*([a-z_][a-z0-9_]*)\s*=\s*\{'),
)


def _diag_replace_risk(root):
    """replace_path 把原版目录整体屏蔽后，原版定义的 tag / trigger / effect
    仍然被原版脚本引用，会变成海量的 Unknown xxx-type 错误。

    这是实测最贵的一类：40 省测试地图 replace 了 common/country_tags，
    只剩自建的 1 个 tag，原版 383 个全部失效，
    error.log 从 0 涨到 58762 行，其中九成是 "Unknown trigger-type: GER"。
    """
    out = []
    layers = mod_layers(root) or [root] or []
    if not layers:
        return out
    game = layers[0]
    for sub, label, pat in _REPLACE_RISK:
        owner = _replace_owner(root, sub)
        if not owner:
            continue
        ours = _replace_collect(owner, sub, pat)
        if sub == "common/country_tags":
            # 别名目录不受这次 replace 影响，合并进来
            ours |= _replace_collect(owner, "common/country_tag_aliases", pat)
        theirs = _replace_collect(game, sub, pat)
        if sub == "common/country_tags":
            theirs |= _replace_collect(game, "common/country_tag_aliases", pat)
        missing = theirs - ours
        if not missing:
            continue
        # 分级：只提供极少数名字的，几乎肯定是「骨架 + 误 replace」，原版会大面积失效；
        # 提供几十上百个的，是 overhaul 型 mod 的有意整体替换，只作提示。
        sev = "error" if len(ours) < 10 else "info"
        sample = "、".join(sorted(missing)[:6])
        kind = "error" if sev == "error" else "info"
        if sev == "error":
            note = ("原版脚本仍在引用这些名字，加载期会刷出海量 Unknown xxx-type 错误"
                    if sub != "common/country_tags" else
                    "原版脚本里的 TAG = { } 一律报 Unknown trigger/effect-type")
        else:
            note = "整体替换是有意为之的话可忽略；若仍有原版脚本在用这些名字，会报 Unknown"
        out.append(_finding(
            "replace.drops_vanilla", sev,
            "%s 被 replace_path 整体替换：原版 %d 个%s，本 mod 提供 %d 个，"
            "缺 %d 个（%s…）。%s"
            % (sub, len(theirs), label, len(ours), len(missing), sample, note),
            "descriptor.mod", 0, 'replace_path="%s"' % sub,
            "去掉这条 replace_path，把自建内容写进 %s 下的新文件与原版合并；"
            "确实要整体替换时，需自行提供被引用到的全部名字" % sub))
    return out


def _diag_replace_refs(root):
    """replace 掉一个数据目录后，还有哪些文件在引用它。

    HOI4 的 replace_path 是整体屏蔽：声明后该目录只从这一层读。
    只替换 common/ideas 而不替换引用它的 achievements / continuous_focus /
    special_projects / factions，这些文件里的 add_timed_idea 就全指向不存在的
    精神，加载期刷出海量 Invalid idea（实测一轮 3879 条）。

    这个检查在动手之前把「会断哪些引用」列出来，省掉一轮 150 秒的真机验证。
    """
    out = []
    layers = mod_layers(root) or [root] or []
    if not layers:
        return out
    top = _top_mod(root)
    if not top:
        return out

    replaced = set()
    for sub, _label, _kw in _REF_KEYWORDS:
        if _replace_owner(root, sub):
            replaced.add(sub)
    if not replaced:
        return out

    # 必须扫全部层：真正在引用被 replace 目录的往往是原版文件
    # （achievements.txt、continuous_focus、special_projects、factions）。
    # 只看本 mod 自己的文件会一条都报不出来。
    hits = {}
    scanned = []
    ignored = _replace_ignored(root)
    for layer in layers:
        if not layer or not os.path.isdir(layer):
            continue
        for dirpath, _dirs, files in os.walk(layer):
            rel_dir = os.path.relpath(dirpath, layer).replace(os.sep, "/")
            if rel_dir.startswith(("localisation", "map", ".git")):
                continue
            if any(rel_dir == d or rel_dir.startswith(d + "/") for d in replaced):
                continue
            scanned.append((layer, dirpath, rel_dir, files))
    if not scanned:
        return out
    for layer, dirpath, rel_dir, files in scanned:
        for fn in sorted(files):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(dirpath, fn)
            base = (rel_dir + "/" + fn) if rel_dir != "." else fn
            # 原版文件加 vanilla/ 前缀，避免和同名 mod 文件混在一起
            rel = base if layer == top else ("vanilla/" + base)
            try:
                txt = io.open(p, encoding="utf-8-sig", errors="replace").read()
            except Exception:
                continue
            for sub, label, kws in _REF_KEYWORDS:
                if sub not in replaced:
                    continue
                for kw in kws:
                    idx = txt.find(kw)
                    if idx < 0:
                        continue
                    line = txt.count(chr(10), 0, idx) + 1
                    # 按目录归并：原版里同一个目录往往有几十个文件都在引用，
                    # 逐个报会把界面刷满，也没有额外信息量。
                    gkey = rel.rsplit("/", 1)[0] if rel.endswith(".txt") else rel
                    hits.setdefault(gkey, []).append((sub, label, kw, line, rel))
                    break

    for gkey in sorted(hits):
        items = hits[gkey]
        subs = sorted({(i[0], i[1]) for i in items})
        sub_list = [s[0] for s in subs]
        first = items[0]
        ref_dir = _replace_ref_dir(first[4])
        # 用户点过「忽略」的组合不再提示：这些引用确认不会被执行到。
        if _replace_ignore_key(root, sub_list, ref_dir, gkey) in ignored:
            continue
        desc = "、".join("%s(%s)" % (lb, sb) for sb, lb in subs)
        # 「接管」只对真正的子目录开放：common/achievements.txt 这种直接在
        # common/ 根下的文件，分组键会折成 common，接管它等于把整个原版 common
        # （实测 2267 个文件）搬进 mod 再 replace_path="common"，直接把工程炸掉。
        opts = ["drop_replace"]
        note = ""
        if "/" in ref_dir:
            why = _replace_adopt_block(ref_dir)
            if why:
                note = why
            else:
                opts.append("adopt_ref_dir")
        else:
            note = ("引用方是 %s 根目录下的单个文件，接管整个 %s 代价太大，"
                    "只能撤销 replace 或忽略" % (ref_dir or "mod", ref_dir or "mod"))
        opts.append("ignore")
        out.append(_finding(
            "replace.dangling_refs", "error",
            "这个目录下有 %d 处引用已被 replace 替换掉的 %s，加载期会报 Invalid / Unknown；"
            "首个是 %s 第 %d 行的 %s" % (len(items), desc, first[4], first[3], first[2]),
            first[4], first[3], first[2],
            "要么去掉对应的 replace_path，要么把这个目录也一并替换并自行提供内容",
            fix={"kind": "replace_dangling",
                 "sub": sub_list[0] if sub_list else "",
                 "subs": sub_list,
                 "ref_dir": ref_dir,
                 "group": gkey,
                 "note": note,
                 "options": opts}))
        if len(out) >= 40:
            out.append(_finding(
                "replace.dangling_refs.more", "info",
                "同类目录还有很多，已列出前 40 个", "", 0, "",
                "先处理这 40 个，再重新跑诊断"))
            break
    return out


def _diag_replace_stub(root):
    """声明了 replace_path 的目录，这一层里到底有没有写东西。

    2026-11-02 真机二分（46 轮）的结论固化成检查项：

    * 目录被 replace 但本 mod 里为空 → 引擎在读一个空目录，等于这一类数据全没了
    * 其中 **common/national_focus 没有 `default = yes` 的国策树 → 进游戏必崩**，
      崩点在 `Loaded N provinces` 之后 1–2 秒，`error.log` 一个字都不写，
      堆栈全是 PHYSFS_swapULE64（符号解析失败），从日志上完全看不出来。

    三条对照：注释占位崩、只匹配本 tag 的树崩、带 `default = yes` 的树过。
    """
    out = []
    layers = mod_layers(root) or [root] or []
    seen = set()
    for b in reversed(layers):
        if not b:
            continue
        try:
            decl = _mod_descriptor(b).get("replace") or []
        except Exception:
            continue
        for sub in decl:
            sub = (sub or "").strip().replace("\\", "/")
            if not sub or sub in seen:
                continue
            seen.add(sub)
            owner = b
            try:
                owner = _replace_owner(root, sub) or b
            except Exception:
                pass
            d = os.path.join(owner, sub.replace("/", os.sep))
            files = []
            anyfile = []
            if os.path.isdir(d):
                anyfile = [f for f in os.listdir(d)
                           if os.path.isfile(os.path.join(d, f))]
                files = [f for f in anyfile if f.endswith(".txt")]
            if not anyfile:
                # 空目录本身不一定会崩：muvluvCN 就把 common/ai_equipment、
                # common/bop 有意 replace 成空，游戏照常进。所以只报 warning，
                # 只有「已知必崩」的目录才升级成 error。
                hard = sub in ("common/national_focus", "history/states")
                out.append(_finding(
                    "replace.empty_dir", "error" if hard else "warning",
                    "%s 被 replace_path 声明为「只从本 mod 读」，但这一层里是空的"
                    " —— 游戏会读到一个空目录" % sub,
                    "descriptor.mod", 0, 'replace_path="%s"' % sub,
                    "删掉这条 replace_path（改为新增文件与原版合并），"
                    "或往 %s/ 里放内容" % sub,
                    {"kind": "replace_dangling", "sub": sub, "subs": [sub],
                     "options": ["drop_replace", "ignore"]}))
                continue
            if not files and sub.startswith(("common/", "history/", "events")):
                out.append(_finding(
                    "replace.no_txt", "warning",
                    "%s 被 replace_path 整体接管，但目录里没有 .txt，"
                    "引擎读不到任何数据" % sub,
                    "descriptor.mod", 0, 'replace_path="%s"' % sub,
                    "确认这一类数据是不是真的不需要"))
            if sub == "common/national_focus":
                blob = ""
                for f in files:
                    try:
                        blob += io.open(os.path.join(d, f), encoding="utf-8-sig",
                                        errors="replace").read()
                    except Exception:
                        pass
                if "default = yes" not in blob:
                    out.append(_finding(
                        "replace.focus_no_default", "error",
                        "common/national_focus 被整体替换，但没有 default = yes 的"
                        "国策树 —— 实测进游戏必崩，且 error.log 无任何记录",
                        os.path.join("common", "national_focus", files[0]), 0,
                        "缺少 default = yes",
                        "写一棵带 default = yes 的树（qa/world_stubs.py 的 "
                        "focus_tree_stub 可直接用），或撤销这条 replace_path"))
            if sub == "common/ai_strategy":
                for f in files:
                    try:
                        raw = io.open(os.path.join(d, f), encoding="utf-8-sig",
                                      errors="replace").read()
                    except Exception:
                        continue
                    if re.match(r'\s*ai_strategy\s*=\s*\{\s*\}', raw):
                        out.append(_finding(
                            "replace.ai_strategy_bare", "warning",
                            "common/ai_strategy 里写了空的 `ai_strategy = { }`，"
                            "引擎会把块名当成策略名，报 missing or empty enable trigger",
                            os.path.join("common", "ai_strategy", f), 0,
                            "ai_strategy = { }",
                            "改成一条永不启用的具名策略（见 qa/world_stubs.py）"))
    return out


def _diag_tag_undefined(root):
    """引用了不存在的国家 tag。

    `TAG = { ... }` 在脚本里是 scope 切换，`original_tag = TAG` 是筛选条件。
    tag 没在 common/country_tags 里定义时，游戏对每一处引用报一条
    "Unknown trigger-type: TAG" 或 "Unknown effect-type: TAG"。

    这是实测最贵的那类错误：一个被 replace 掉的 country_tags 目录，
    在 40 省的测试地图上刷出 58762 行 error.log，其中九成是它。
    静态跑这里 2 秒就能定位，不必等 150 秒一轮的真机加载。
    """
    out = []

    # 1) 收集「实际能生效」的 tag。
    #    不能简单地把叠加链上所有层的 tag 都算数：某一层若声明
    #    replace_path="common/country_tags"，下层（含原版）的 tag 会被整体屏蔽，
    #    脚本里再引用它们就是 Unknown trigger-type。
    #    这正是 40 省测试地图刷出 58762 行 error.log 的那个根因。
    known = set()
    layers = mod_layers(root) or [root] or []
    for sub in ("common/country_tags", "common/country_tag_aliases"):
        srcs = layers
        owner = _replace_owner(root, sub)
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
                    txt = io.open(os.path.join(td, fn), encoding="utf-8-sig",
                                  errors="replace").read()
                except Exception:
                    continue
                for m in re.finditer(r'(?m)^\s*([A-Z][A-Z0-9]{2})\s*=', txt):
                    known.add(m.group(1))
    if not known:
        return out

    # 2) 只扫本 mod 自己的文件（原版的引用是官方数据，不归我们管）
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out

    # 3) 两种明确的 tag 引用写法
    pat_scope = re.compile(r'^([A-Z][A-Z0-9]{2})\s*=\s*\{')
    pat_param = re.compile(
        r'^(?:original_tag|country_exists|has_tag|tag|add_core|remove_core|'
        r'has_war_with|is_in_faction_with|is_guaranteed_by)\s*=\s*([A-Z][A-Z0-9]{2})\s*$')

    per_file = {}
    total = 0
    dropped = 0
    for dirpath, _dirs, files in os.walk(top):
        rel_dir = os.path.relpath(dirpath, top).replace(os.sep, "/")
        if rel_dir.startswith("localisation") or rel_dir.startswith("map"):
            continue
        if any(rel_dir.startswith(d) for d in _TAG_SKIP_DIRS):
            continue
        for fn in sorted(files):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(dirpath, fn)
            base = (rel_dir + "/" + fn) if rel_dir != "." else fn
            # 原版文件加 vanilla/ 前缀，避免和同名 mod 文件混在一起
            rel = base if layer == top else ("vanilla/" + base)
            try:
                lines = io.open(p, encoding="utf-8-sig",
                                errors="replace").read().splitlines()
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


def _diag_division_template_missing(root):
    """units 里引用的 division_template 有没有定义。"""
    out = []
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out

    ud = os.path.join(top, "history", "units")
    if not os.path.isdir(ud):
        return out

    defined = set()
    used = []
    for fn in sorted(os.listdir(ud)):
        if not fn.endswith(".txt"):
            continue
        p = os.path.join(ud, fn)
        try:
            lines = io.open(p, encoding="utf-8-sig", errors="replace").read().splitlines()
        except Exception:
            continue
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
                used.append((fn, i, m2.group(1), ln.strip()))

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
                txt = io.open(os.path.join(d2, fn), encoding="utf-8-sig", errors="replace").read()
            except Exception:
                continue
            for m in re.finditer(r'division_template\s*=\s*\{[^}]*?name\s*=\s*"([^"]+)"', txt, re.S):
                defined.add(m.group(1))

    for fn, i, tname, raw in used:
        if tname in defined:
            continue
        out.append(_finding(
            "script.division_template.missing", "error",
            "%s 第 %d 行引用了师团模板 %s，但整个叠加链里都没有定义这个模板"
            % (fn, i, tname),
            os.path.join("history", "units", fn).replace(os.sep, "/"), i, raw,
            '补一个 division_template = { name = "%s" ... }，或改成已存在的模板名' % tname))
    return out


# CWTools 规则里没覆盖、但游戏确实认的字段。
# 出现这些不报——规则是别人维护的，不全会漏。
_SCHEMA_EXTRA = {
    "legacy_id", "id", "targeted_modifier", "equipment_bonus",
    "allowed_civil_war", "research_bonus", "rule",
}


# 这些前缀开头的字段一律放过（规则文件没列全，但游戏确实认）
_SCHEMA_EXTRA_PREFIX = (
    "war_with",           # war_with_on_remove 等一组
    "target_",            # target_ROOT_trigger 等
)


# 作用域关键字和常见的脚本化效果/触发器名。后者由 mod 自己定义
# （scripted_effects / scripted_triggers），规则里查不到，只能按命名特征放过。
_SCHEMA_SCOPE_WORDS = {
    "ROOT", "FROM", "PREV", "THIS", "OWNER", "CONTROLLER",
    "CAPITAL", "OVERLORD", "FACTION_LEADER", "ENEMY", "IF", "ELSE",
}


# 这些块里装的是 trigger / effect，不是字段，整块跳过不查
_SCHEMA_SKIP_BLOCKS = {
    "allowed", "available", "visible", "trigger", "limit",
    "complete_effect", "remove_effect", "cancel_trigger", "update_effect",
    "on_add", "on_remove", "do_effect", "ai_will_do", "modifier",
    "targeted_modifier", "equipment_bonus", "research_bonus",
    "rule", "allowed_civil_war", "effect", "modifiers",
    # 国策树里这些块装的是 UI/搜索配置，不是国策字段
    "search_filters", "search_filter_prios", "focus", "shared_focus",
    "completion_reward", "continuous_focus_position",
}


# 这些前缀开头的块名，里面装的是 effect / UI 配置，整块跳过
_SKIP_PREFIX = (
    "completion_reward", "search_filter", "custom_effect_tooltip",
    "custom_trigger_tooltip", "custom_tooltip",
)


def _is_skip_block(name):
    return name in _SCHEMA_SKIP_BLOCKS or name.startswith(_SKIP_PREFIX)


def _looks_like_scripted(name):
    """像 mod 自定义脚本化效果/触发器的名字。

    这类东西在 scripted_effects / scripted_triggers 里定义，规则文件里没有，
    命名上通常是「大写 tag 前缀 + 小写描述」，比如 JAP_faction_demand_finalize。
    """
    if not name or len(name) < 3:
        return False
    head = name.split('_', 1)[0]
    if head.isupper() and head.isalpha() and 3 <= len(head) <= 6:
        return True            # 纯 tag 或 tag 前缀
    # 小写开头但内部带 tag 的，比如 is_raj_or_raj_inheritor
    parts = name.split('_')
    for p2 in parts:
        if p2.isupper() and p2.isalpha() and 3 <= len(p2) <= 6:
            return True
    # 以 _trigger / _effect 收尾的，多半是脚本化触发器
    return name.endswith(('_trigger', '_triggers', '_effect', '_effects'))


_CWT_RULES = [None]


_CWT_TE = [None]


def _cwt_te():
    """trigger / effect 名字集合（从 .cwt 的 alias[trigger:xxx] 提取）。"""
    if _CWT_TE[0] is not None:
        return _CWT_TE[0]
    names = set()
    try:
        import importlib.util as _ilu
        here = _qa_dir()
        p = os.path.join(here, "cwt", "parse.py")
        if os.path.isfile(p):
            spec = _ilu.spec_from_file_location("_cwt_parse_te", p)
            mod = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            names = mod.load_trigger_effect_names()
    except Exception:
        names = set()
    _CWT_TE[0] = names
    return names


def _cwt_rules():
    """惰性加载 .cwt 规则（来自 cwtools/cwtools-hoi4-config，MIT）。"""
    if _CWT_RULES[0] is not None:
        return _CWT_RULES[0]
    rules = {}
    try:
        import importlib.util as _ilu
        # PyInstaller 打包后资源在 sys._MEIPASS 下，源码运行时在脚本目录
        here = _qa_dir()
        p = os.path.join(here, "cwt", "parse.py")
        if os.path.isfile(p):
            spec = _ilu.spec_from_file_location("_cwt_parse", p)
            mod = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            rules = mod.load_rules()
    except Exception:
        rules = {}
    _CWT_RULES[0] = rules
    return rules


def _diag_schema_unknown_field(root):
    """检查文件里的字段名在 HOI4 的 schema 里存不存在。

    规则来自 CWTools 的 HOI4 配置（MIT）。拼错字段名游戏不报错，那一段静默失效——
    比如把 division_template 写成 division_templet，部队模板就引用不到。
    """
    out = []
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out
    rules = _cwt_rules()
    if not rules:
        return out

    def scan(rel, block_name, schema_name):
        """只查 `<block_name> = { ... }` 这一层的字段。

        不查块名本身、不查动态 id（人物 id、装备名那些都是内容不是字段）。
        """
        allowed = rules.get(schema_name)
        if not allowed:
            return
        p = os.path.join(top, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            return
        try:
            lines = io.open(p, encoding="utf-8-sig", errors="replace").read().splitlines()
        except Exception:
            return
        depth = 0
        inside = False
        base_depth = 0        # 进入目标块时的深度，子级字段就查这一层
        for i2, ln in enumerate(lines, 1):
            st = ln.strip()
            opens = ln.count("{")
            closes = ln.count("}")
            if not st or st.startswith("#"):
                depth += opens - closes
                continue
            if not inside:
                m = re.match(r'^' + re.escape(block_name) + r'\s*=\s*\{\s*$', st)
                depth += opens - closes
                if m:
                    inside = True
                    base_depth = depth
                continue
            # 在目标块里，只看直接子级（深度等于进入时的深度）
            if depth == base_depth:
                m = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*[=<>]', st)
                if m:
                    f = m.group(1)
                    if f not in allowed:
                        out.append(_finding(
                            "schema.unknown_field", "warning",
                            "%s 第 %d 行的字段 %s 不在 %s 的规则定义里"
                            % (os.path.basename(rel), i2, f, schema_name),
                            rel, i2, st,
                            "对照原版同类文件确认字段名"))
            depth += opens - closes
            if depth < base_depth:
                inside = False
                depth = max(depth, 0)

    # history/units：units 里的 division
    ud = os.path.join(top, "history", "units")
    if os.path.isdir(ud):
        for fn in sorted(os.listdir(ud)):
            if fn.endswith(".txt"):
                scan("history/units/" + fn, "division", "oob")
    # common/bookmarks：bookmark 块
    scan("common/bookmarks/zz_editor_bookmarks.txt", "bookmark", "bookmark")

    return out


def _diag_schema_character(root):
    """common/characters 里人物的字段名检查。

    结构很干净：`characters = {` 下一层（depth 1）是人物 id，再下一层（depth 2）
    才是字段。所以不用猜哪些标识符是 id，靠层级就能分开。
    """
    out = []
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out
    rules = _cwt_rules()
    allowed = rules.get("character")
    if not allowed:
        return out
    te_names = _cwt_te()

    cd = os.path.join(top, "common", "characters")
    if not os.path.isdir(cd):
        return out

    # 这些块名是人物体内的类型块，不是字段
    PORTRAIT_FIELDS = {"army", "navy", "civilian", "large", "small",
                       "female", "undefined", "male"}
    TYPE_BLOCKS = {"corps_commander", "field_marshal", "navy_leader",
                   "country_leader", "advisor", "scientist", "operative",
                   "instance", "portraits"}

    for fn in sorted(os.listdir(cd)):
        if not fn.endswith(".txt"):
            continue
        rel = "common/characters/" + fn
        p = os.path.join(cd, fn)
        try:
            lines = io.open(p, encoding="utf-8-sig", errors="replace").read().splitlines()
        except Exception:
            continue
        in_chars = False
        depth = 0
        stack = [""]
        for i, ln in enumerate(lines, 1):
            st = ln.strip()
            if not st or st.startswith("#"):
                depth += ln.count("{") - ln.count("}")
                continue
            if not in_chars:
                if re.match(r'^characters\s*=\s*\{\s*$', st):
                    in_chars = True
                    depth = 1
                    continue
                depth += ln.count("{") - ln.count("}")
                continue
            # depth 1 = 人物 id，2 = 人物体字段，3 = 类型块里的字段
            if 2 <= depth <= 3:
                # 找出当前在哪个块里，portraits 的字段是另一套
                parent = ""
                for k2 in range(len(stack) - 1, -1, -1):
                    if stack[k2]:
                        parent = stack[k2]
                        break
                m = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*[=<>]', st)
                if m:
                    f = m.group(1)
                    if parent == "portraits":
                        ok = f in PORTRAIT_FIELDS
                    elif parent in _SCHEMA_SKIP_BLOCKS:
                        ok = True          # trigger / effect 块里不查
                    else:
                        ok = ((f in allowed) or (f in TYPE_BLOCKS)
                              or (f in _SCHEMA_EXTRA)
                              or (f in te_names)
                              or (f in _SCHEMA_SCOPE_WORDS)
                              or _is_skip_block(f)
                              or _looks_like_scripted(f)
                              or f.startswith(_SCHEMA_EXTRA_PREFIX))
                    if not ok:
                        out.append(_finding(
                            "schema.unknown_field", "warning",
                            "%s 第 %d 行的字段 %s 不在 %s 的规则定义里"
                            % (fn, i, f, "portraits" if parent == "portraits" else "character"),
                            rel, i, st,
                            "对照原版同类人物确认字段名"))
            # 维护块栈
            opens = ln.count("{")
            closes = ln.count("}")
            if opens:
                nm = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*[=<>]', st)
                stack.append(nm.group(1) if nm else "")
                for _ in range(opens - 1):
                    stack.append("")
            depth += opens - closes
            while len(stack) > 1 and depth < len(stack):
                stack.pop()
            if depth <= 0:
                in_chars = False
                depth = 0
                stack = [""]
    return out


def _diag_schema_decision(root):
    """common/decisions 里决议的字段名检查。

    结构：`类别名 = { 决议id = { 字段 } }`，类别 id 在 depth 1，字段在 depth 2。
    """
    out = []
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out
    rules = _cwt_rules()
    allowed = rules.get("decision")
    if not allowed:
        return out
    te_names = _cwt_te()

    dd = os.path.join(top, "common", "decisions")
    if not os.path.isdir(dd):
        return out
    cat_dir = os.path.join(dd, "categories")

    for fn in sorted(os.listdir(dd)):
        if not fn.endswith(".txt"):
            continue
        p = os.path.join(dd, fn)
        if not os.path.isfile(p):
            continue
        rel = "common/decisions/" + fn
        try:
            lines = io.open(p, encoding="utf-8-sig", errors="replace").read().splitlines()
        except Exception:
            continue
        depth = 0
        stack = [""]
        for i, ln in enumerate(lines, 1):
            st = ln.strip()
            opens = ln.count("{")
            closes = ln.count("}")
            if not st or st.startswith("#"):
                depth += opens - closes
                while len(stack) > 1 and depth < len(stack):
                    stack.pop()
                continue
            # 结构是「类别 depth1 → 决议 depth2 → 字段 depth3」，
            # 查 depth 2 会把决议 id 当字段，所以查 depth 3。
            if depth == 3:
                parent = ""
                for k2 in range(len(stack) - 1, -1, -1):
                    if stack[k2]:
                        parent = stack[k2]
                        break
                m = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*[=<>]', st)
                if m and not _is_skip_block(parent):
                    f = m.group(1)
                    if (f not in allowed and f not in _SCHEMA_EXTRA
                            and f not in te_names
                            and f not in _SCHEMA_SCOPE_WORDS
                            and not _is_skip_block(f)
                            and not _looks_like_scripted(f)
                            and not f.startswith(_SCHEMA_EXTRA_PREFIX)):
                        out.append(_finding(
                            "schema.unknown_field", "warning",
                            "%s 第 %d 行的字段 %s 不在 decision 的规则定义里"
                            % (fn, i, f),
                            rel, i, st,
                            "对照原版同类决议确认字段名"))
            if opens:
                nm = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*[=<>]', st)
                stack.append(nm.group(1) if nm else "")
                for _ in range(opens - 1):
                    stack.append("")
            depth += opens - closes
            while len(stack) > 1 and depth < len(stack):
                stack.pop()
            if depth < 0:
                depth = 0
                stack = [""]
    return out


def _diag_schema_ideas(root):
    """common/ideas 里国家精神的字段检查。

    结构：`ideas = { country = { 精神id = { 字段 } } }`，
    所以字段在 depth 3（ideas 0 → country 1 → 精神 2 → 字段 3）。
    """
    out = []
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out
    rules = _cwt_rules()
    allowed = rules.get("idea")
    if not allowed:
        return out
    te_names = _cwt_te()

    idd = os.path.join(top, "common", "ideas")
    if not os.path.isdir(idd):
        return out

    for fn in sorted(os.listdir(idd)):
        if not fn.endswith(".txt"):
            continue
        p = os.path.join(idd, fn)
        if not os.path.isfile(p):
            continue
        rel = "common/ideas/" + fn
        try:
            lines = io.open(p, encoding="utf-8-sig", errors="replace").read().splitlines()
        except Exception:
            continue
        depth = 0
        stack = [""]
        for i, ln in enumerate(lines, 1):
            st = ln.strip()
            opens = ln.count("{")
            closes = ln.count("}")
            if not st or st.startswith("#"):
                depth += opens - closes
                while len(stack) > 1 and depth < len(stack):
                    stack.pop()
                continue
            if depth == 3:
                parent = ""
                for k2 in range(len(stack) - 1, -1, -1):
                    if stack[k2]:
                        parent = stack[k2]
                        break
                m = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*[=<>]', st)
                if m and not _is_skip_block(parent):
                    f = m.group(1)
                    if (f not in allowed and f not in _SCHEMA_EXTRA
                            and f not in te_names
                            and f not in _SCHEMA_SCOPE_WORDS
                            and not _is_skip_block(f)
                            and not _looks_like_scripted(f)
                            and not f.startswith(_SCHEMA_EXTRA_PREFIX)):
                        out.append(_finding(
                            "schema.unknown_field", "warning",
                            "%s 第 %d 行的字段 %s 不在 idea 的规则定义里"
                            % (fn, i, f),
                            rel, i, st,
                            "对照原版同类国家精神确认字段名"))
            if opens:
                nm = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*[=<>]', st)
                stack.append(nm.group(1) if nm else "")
                for _ in range(opens - 1):
                    stack.append("")
            depth += opens - closes
            while len(stack) > 1 and depth < len(stack):
                stack.pop()
            if depth < 0:
                depth = 0
                stack = [""]
    return out


def _diag_schema_focus(root):
    """common/national_focus 里国策的字段检查。

    结构：`focus_tree = { focus = { 字段 } }`，
    国策体在 depth 2，字段在 depth 3。

    规则里 focus_tree 的字段表是「树本身 + 国策体」合并的，所以白名单偏宽——
    宁可放过也不误报。
    """
    out = []
    top = None
    for r in (state.roots() or []):
        lay = mod_layers(r) or [r]
        cand = lay[-1] if lay else r
        if cand and not is_under_game(cand):
            top = cand
    if not top:
        return out
    rules = _cwt_rules()
    allowed = rules.get("focus_tree")
    if not allowed:
        return out
    te_names = _cwt_te()

    fd = os.path.join(top, "common", "national_focus")
    if not os.path.isdir(fd):
        return out

    for fn in sorted(os.listdir(fd)):
        if not fn.endswith(".txt"):
            continue
        p = os.path.join(fd, fn)
        if not os.path.isfile(p):
            continue
        rel = "common/national_focus/" + fn
        try:
            lines = io.open(p, encoding="utf-8-sig", errors="replace").read().splitlines()
        except Exception:
            continue
        depth = 0
        stack = [""]
        for i, ln in enumerate(lines, 1):
            st = ln.strip()
            opens = ln.count("{")
            closes = ln.count("}")
            if not st or st.startswith("#"):
                depth += opens - closes
                while len(stack) > 1 and depth < len(stack):
                    stack.pop()
                continue
            # 进入 focus_tree 之后，国策体在 depth 2、字段在 depth 3
            if depth == 3:
                parent = ""
                for k2 in range(len(stack) - 1, -1, -1):
                    if stack[k2]:
                        parent = stack[k2]
                        break
                m = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*[=<>]', st)
                if m and not _is_skip_block(parent):
                    f = m.group(1)
                    if (f not in allowed and f not in _SCHEMA_EXTRA
                            and f not in te_names
                            and f not in _SCHEMA_SCOPE_WORDS
                            and not _is_skip_block(f)
                            and not _looks_like_scripted(f)
                            and not f.startswith(_SCHEMA_EXTRA_PREFIX)):
                        out.append(_finding(
                            "schema.unknown_field", "warning",
                            "%s 第 %d 行的字段 %s 不在 focus_tree 的规则定义里"
                            % (fn, i, f),
                            rel, i, st,
                            "对照原版同类国策确认字段名"))
            if opens:
                nm = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*[=<>]', st)
                stack.append(nm.group(1) if nm else "")
                for _ in range(opens - 1):
                    stack.append("")
            depth += opens - closes
            while len(stack) > 1 and depth < len(stack):
                stack.pop()
            if depth < 0:
                depth = 0
                stack = [""]
    return out


_MAP_DIAG_FILES = {
    1: "default.map", 2: "provinces.bmp", 3: "provinces.bmp",
    4: "definition.csv", 5: "definition.csv", 6: "definition.csv",
    7: "definition.csv", 8: "definition.csv", 9: "provinces.bmp",
    10: "continent.txt", 11: "definition.csv", 12: "strategicregions",
}


# map_diag 顶层把 numpy / PIL 的 import 吞成了 np=None / Image=None（它要能单独跑），
# 所以「import map_diag 成功」不等于「检查能跑」。
# np=None 会让 diagnose() 在逐像素那一段抛 AttributeError（'NoneType' has no
# attribute 'frombuffer'），报出来的错跟地图本身毫无关系——必须先单独识别出来。
# Image=None 只降级（24 位图有手写兜底，8 位索引图由它自己出 WARN），不算硬失败。
_MAP_DIAG_HARD_DEPS = (("np", "numpy"),)


def _map_diag_skip(msg, excerpt="", repair=""):
    """地图检查没跑成时的那一条诊断。

    统一口径：severity 恒为 warning，msg 里必带「未检查」，因为诊断面板把
    「零条 finding」渲染成"没有发现问题"——缺库时返回空列表等于告诉用户地图没问题。
    """
    return _finding("map.format.skipped", "warning", msg,
                    os.path.join("map", "default.map"), 0, excerpt, repair)


def _diag_map_format(root):
    """map/ 目录格式体检：这一项回答"这张地图能不能进游戏"。

    查的是 HOI4 地图加载期的硬约束（尺寸 256 倍数、definition.csv 行尾与列、
    大洲 1..N、continent.txt 是纯列表、海必须是省、省必须归属战略区）。
    判断依据与引擎一致：同一个最小地图，这里报的 FAIL 就是 error.log 里报的那几条。

    实现在 qa/map_diag.py，两边共用一套规则，改一处两边都变。

    检查跑不起来（缺 numpy / map_diag 加载失败 / 它自己抛异常）时**不是**返回空列表，
    而是产出一条 "map.format.skipped" 的 warning：空列表会被面板当"没有发现问题"。
    """
    out = []
    # 先定位 map/：没有 provinces.bmp 就没有检查对象，这时静默返回才是对的
    # ——"没有地图可检查"和"地图检查没跑成"是两件不同的事，前者不该出诊断。
    mp = None
    try:
        for b in reversed(mod_layers(root) or [root]):
            cand = os.path.join(b, "map")
            if os.path.isfile(os.path.join(cand, "provinces.bmp")):
                mp = cand
                break
    except Exception as e:
        # 叠加链本身取不出来时定位不到 map/，这与"没有地图"不同：是检查根本没开始。
        # 静默返回空列表会让面板显示"没有发现问题"。
        out.append(_map_diag_skip(
            "地图格式检查未执行（未检查）：解析叠加链时出错 %s: %s，"
            "无法定位 map 目录。这条不代表地图没问题。"
            % (e.__class__.__name__, e),
            "root：%s" % root))
        return out
    if not mp:
        return out

    try:
        import sys as _sys
        _qa = _qa_dir()
        if _qa not in _sys.path:
            _sys.path.insert(0, _qa)
        import map_diag
    except ImportError as e:
        # 缺 numpy 走不到这里（map_diag 自己 try 掉了），到这里是真的找不到 qa/map_diag.py，
        # 或者它依赖的 stdlib 之外的东西缺失。异常里的 name 就是那个模块名。
        name = getattr(e, "name", "") or ""
        out.append(_map_diag_skip(
            "地图格式检查未执行（未检查）：缺少模块「%s」，qa/map_diag.py 加载失败。"
            "这条不代表地图没问题。" % (name or str(e)),
            "map 目录：%s" % mp,
            "确认安装包里带 qa/ 目录（打包用 --add-data 带 qa）"))
        return out
    except Exception as e:
        out.append(_map_diag_skip(
            "地图格式检查未执行（未检查）：加载 qa/map_diag.py 时出错 %s: %s。"
            "这条不代表地图没问题。" % (e.__class__.__name__, e),
            "map 目录：%s" % mp))
        return out

    lost = [nm for attr, nm in _MAP_DIAG_HARD_DEPS if getattr(map_diag, attr, None) is None]
    if lost:
        # 逐像素那一段（孤儿色、空省、海省统计、rivers/terrain/cities 方向）
        # 全压在 numpy 上，缺库时 diagnose() 直接死在 np.frombuffer。
        out.append(_map_diag_skip(
            "地图格式检查未执行（未检查）：缺少 %s，逐像素检查（孤儿色、空省、"
            "海省统计、rivers/terrain/cities 方向）全部跳过。这条不代表地图没问题。"
            % " / ".join(lost),
            "map 目录：%s" % mp,
            "pip install numpy；发行版请用带 numpy 的安装包"))
        return out

    try:
        res = map_diag.diagnose(mp)
    except ImportError as e:
        # map_diag 内部还有几处函数内的延迟 import（比如按需读 csv），
        # 缺模块时它会在这里抛，而不是在 import map_diag 那一行。
        name = getattr(e, "name", "") or ""
        out.append(_map_diag_skip(
            "地图格式检查中断（未完成）：检查过程缺少模块「%s」。"
            "这条不代表地图没问题。" % (name or str(e)),
            "map 目录：%s" % mp,
            "补齐该模块后重跑；发行版请用带 numpy 的安装包"))
        return out
    except Exception as e:
        out.append(_map_diag_skip(
            "地图格式检查中断（未完成）：map_diag.diagnose() 抛出 %s: %s。"
            "这条不代表地图没问题。" % (e.__class__.__name__, e),
            "map 目录：%s" % mp))
        return out
    for it in res.get("items", []):
        if it.get("level") == "PASS":
            continue
        fn = _MAP_DIAG_FILES.get(it.get("id")) or "provinces.bmp"
        msg = it.get("title") or ""
        if it.get("detail"):
            msg = msg + "：" + it["detail"]
        out.append(_finding(
            "map.format.%d" % int(it.get("id") or 0),
            "error" if it.get("level") == "FAIL" else "warning",
            msg, os.path.join("map", fn), 0, "", ""))
    return out


def diagnose(root=None):
    """扫描当前 mod，返回结构化诊断列表。"""
    root = paths._pick(root) if root else (state.roots()[-1] if state.roots() else None)
    if not root:
        return {"ok": False, "msg": "没有打开的 mod", "findings": []}
    findings = []
    for fn in (_diag_oob_not_referenced, _diag_gfx_missing,
               _diag_recruit_last_line, _diag_decision_category,
               _diag_character_unrecruited, _diag_localisation_missing,
               _diag_tag_def_missing, _diag_tag_undefined, _diag_replace_risk,
               _diag_replace_refs, _diag_replace_stub,
               _diag_division_template_missing,
               _diag_schema_unknown_field, _diag_schema_character,
               _diag_schema_decision, _diag_schema_ideas,
               _diag_map_format,
               # _diag_schema_focus：国策树嵌套太深（focus → completion_reward
               # → add_tech_bonus → 参数），深度算不稳，误报 0.24% 不可接受。
               # 代码留着，等有更好的深度跟踪再启用。
               ):
        try:
            findings.extend(fn(root))
        except Exception:
            pass
    order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda x: (order.get(x["severity"], 3), x["file"], x["line"]))
    return {"ok": True, "findings": findings, "count": len(findings)}
