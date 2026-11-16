# -*- coding: utf-8 -*-
"""雪绒编辑器 · 模块化包（v2.0.0 拆模块目标结构）

分层规则（由 `qa/_check_import_boundary.py` 强制）：

    core  →  只依赖标准库和 state，不许 import model / api
    model →  可以 import core，不许 import api
    api   →  随便 import

    focus_editor.py 是过渡期的门面（facade）：所有旧调用点仍然走它。
    迁移完成后它只剩 main() 和 Handler 装配。

这个 `__init__` 故意不 import 任何子模块——包初始化时把 api 拖进来会让
`python -c "import xuerong.state"` 触发整条链，测试和打包都变慢。
"""
