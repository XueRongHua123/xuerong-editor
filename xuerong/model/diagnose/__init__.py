# -*- coding: utf-8 -*-
"""体检 / 诊断（P0-3 从 focus_editor.py 迁入）。

只读：扫描已加载的 mod，产出 findings 列表交给前端渲染，不改任何文件。
（唯一例外是 qa/map_diag.py 的地图格式检查，它也只读。）

依赖边界：
  · 叠加链与 descriptor → xuerong.core.paths
  · replace 侧的小工具 → xuerong.model.replace（同层，允许）
  · 全局容器 → xuerong.state
  · 零钩子：不调门面的任何函数

本文件是包门面：把拆到 _base / content / replace / schema / mapfmt 的 27 个名字
重新导出，外部 `from xuerong.model.diagnose import ...` 的写法一个字都不用改。
"""

from xuerong import state
from xuerong.core import paths
from xuerong.model.diagnose._base import (_finding, _looks_like_scripted,
                                          _map_diag_skip)
from xuerong.model.diagnose.content import (_diag_bookmarks,
                                           _diag_character_unrecruited,
                                           _diag_decision_category,
                                           _diag_division_template_missing,
                                           _diag_gfx_missing, _diag_localisation_missing,
                                           _diag_oob_not_referenced,
                                           _diag_recruit_last_line,
                                           _diag_tag_def_missing, _diag_tag_undefined,
                                           _gfx_names, _loc_keys)
from xuerong.model.diagnose.mapfmt import _diag_map_format
from xuerong.model.diagnose.replace import (_diag_replace_refs, _diag_replace_risk,
                                           _diag_replace_stub)
from xuerong.model.diagnose.schema import (_cwt_rules, _cwt_te,
                                           _diag_schema_character,
                                           _diag_schema_decision,
                                           _diag_schema_focus,
                                           _diag_schema_ideas,
                                           _diag_schema_unknown_field,
                                           _is_skip_block)

_PROGRESS = {"fn": None, "begin": None, "done": None, "fail": None}


def set_progress_hook(fn, begin=None, done=None, fail=None):
    """门面启动期注入诊断进度上报钩子；model 层不 import 门面。"""
    _PROGRESS["fn"] = fn
    _PROGRESS["begin"] = begin
    _PROGRESS["done"] = done
    _PROGRESS["fail"] = fail


def _prog_begin(phase):
    beg = _PROGRESS.get("begin")
    if beg:
        try:
            beg(phase)
        except Exception:
            pass


def _prog_tick(stage, pct=0, sub=""):
    fn = _PROGRESS.get("fn")
    if fn:
        try:
            fn(stage, sub, pct)
        except Exception:
            pass


def _prog_done():
    dn = _PROGRESS.get("done")
    if dn:
        try:
            dn()
        except Exception:
            pass


def diagnose(root=None, scope="current"):
    """扫描当前 mod，返回结构化诊断列表。

    scope="current"（默认）：只查当前顶层可写 mod 自身的改动与 replace_path / 地图，
    避免空 submod 误报前置父层或原版的历史问题并节省数十秒无效扫描；
    scope="all"：连同前置父层与底层地图一并全链检查。
    """
    import time as _time
    t0 = _time.time()
    root = paths._pick(root) if root else (state.roots()[-1] if state.roots() else None)
    if not root:
        return {"ok": False, "msg": "没有打开的 mod", "findings": []}
    own_only = (scope != "all")
    findings = []
    checks = (
        ("OOB 引用", lambda r: _diag_oob_not_referenced(r, own_only=own_only)),
        ("缺失贴图", lambda r: _diag_gfx_missing(r, own_only=own_only)),
        ("人物招募位置", lambda r: _diag_recruit_last_line(r, own_only=own_only)),
        ("决议分类", lambda r: _diag_decision_category(r, own_only=own_only)),
        ("未招募人物", lambda r: _diag_character_unrecruited(r, own_only=own_only)),
        ("缺失本地化", lambda r: _diag_localisation_missing(r, own_only=own_only)),
        ("国家 tag 定义", lambda r: _diag_tag_def_missing(r, own_only=own_only)),
        ("未定义 tag 引用", lambda r: _diag_tag_undefined(r, own_only=own_only)),
        ("replace_path 风险", lambda r: _diag_replace_risk(r, own_only=own_only)),
        ("replace_path 断链引用", lambda r: _diag_replace_refs(r, own_only=own_only)),
        ("replace_path 空目录", lambda r: _diag_replace_stub(r, own_only=own_only)),
        ("师团模板引用", lambda r: _diag_division_template_missing(r, own_only=own_only)),
        ("剧本检查", lambda r: _diag_bookmarks(r, own_only=own_only)),
        ("脚本字段校验", _diag_schema_unknown_field),
        ("人物字段校验", _diag_schema_character),
        ("决议字段校验", _diag_schema_decision),
        ("国家精神字段校验", _diag_schema_ideas),
        ("地图格式", lambda r: _diag_map_format(r, own_only=own_only)),
        # _diag_schema_focus：国策树嵌套太深（focus → completion_reward
        # → add_tech_bonus → 参数），深度算不稳，误报 0.24% 不可接受。
        # 代码留着，等有更好的深度跟踪再启用。
    )
    total = len(checks)
    _prog_begin("全链诊断…" if not own_only else "当前层诊断…")
    try:
        for idx, (label, fn) in enumerate(checks, 1):
            _prog_tick("诊断（%d/%d）：%s" % (idx, total, label), int(idx * 100 / total))
            try:
                findings.extend(fn(root))
            except Exception:
                pass
    finally:
        _prog_done()
    order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda x: (order.get(x["severity"], 3), x["file"], x["line"]))
    return {"ok": True, "scope": "all" if not own_only else "current",
            "elapsed_ms": int((_time.time() - t0) * 1000),
            "findings": findings, "count": len(findings)}
