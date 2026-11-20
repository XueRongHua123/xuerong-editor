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
from xuerong.model.diagnose.content import (_diag_character_unrecruited,
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
        _diag_oob_not_referenced,
        _diag_gfx_missing,
        _diag_recruit_last_line,
        _diag_decision_category,
        _diag_character_unrecruited,
        _diag_localisation_missing,
        _diag_tag_def_missing,
        _diag_tag_undefined,
        lambda r: _diag_replace_risk(r, own_only=own_only),
        lambda r: _diag_replace_refs(r, own_only=own_only),
        lambda r: _diag_replace_stub(r, own_only=own_only),
        _diag_division_template_missing,
        _diag_schema_unknown_field,
        _diag_schema_character,
        _diag_schema_decision,
        _diag_schema_ideas,
        lambda r: _diag_map_format(r, own_only=own_only),
        # _diag_schema_focus：国策树嵌套太深（focus → completion_reward
        # → add_tech_bonus → 参数），深度算不稳，误报 0.24% 不可接受。
        # 代码留着，等有更好的深度跟踪再启用。
    )
    for fn in checks:
        try:
            findings.extend(fn(root))
        except Exception:
            pass
    order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda x: (order.get(x["severity"], 3), x["file"], x["line"]))
    return {"ok": True, "scope": "all" if not own_only else "current",
            "elapsed_ms": int((_time.time() - t0) * 1000),
            "findings": findings, "count": len(findings)}
