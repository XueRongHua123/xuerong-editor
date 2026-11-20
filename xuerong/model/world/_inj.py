# -*- coding: utf-8 -*-
"""世界创建域的门面回注出口 —— 专设此模块以切断子模块对包 __init__ 的循环 import。

三个横切口由门面调 world.bind() 一次性注入（bind 定义在此、由包 __init__ 再导出）：
  · reload_data —— 用 .get() 取，未注入时静默跳过（建世界流程不强依赖）
  · load_mod    —— 用 [] 取，未注入即 KeyError
  · _lp_done    —— 同上，用 [] 取
两种取法的差异是原文件的行为，保持不动。
"""

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


def _lp_done(*a, **k):
    return _INJ["_lp_done"](*a, **k)
