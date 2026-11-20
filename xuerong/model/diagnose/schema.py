# -*- coding: utf-8 -*-
"""脚本 schema 校验：CWTools 规则对齐、字段与块名白名单。"""

import io
import os
import re

from xuerong import state
from xuerong.core.paths import is_under_game, mod_layers, qa_dir as _qa_dir


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
    """块名是否整块跳过（装的是 trigger / effect / UI 配置，不是字段）。

    放在这里而不是 _base：它读的是上面两个常量，而 _base 的三个工具函数是
    本文件的依赖。摆成单向之后两个模块谁先被 import 都不会出问题。
    """
    return name in _SCHEMA_SKIP_BLOCKS or name.startswith(_SKIP_PREFIX)


_CWT_RULES = [None]


_CWT_TE = [None]


from xuerong.model.diagnose._base import (_finding,  # noqa: E402
                                          _looks_like_scripted)


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
