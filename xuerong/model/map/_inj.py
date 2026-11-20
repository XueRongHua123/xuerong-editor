# -*- coding: utf-8 -*-
"""地图域的门面回注出口 —— 专设此模块以切断子模块对包 __init__ 的循环 import。

四个横切口由门面调 map.bind() 一次性注入（bind 定义在此、由包 __init__ 再导出）。
本模块零依赖：不 import 任何 xuerong.* 。
"""


# ---------------------------------------------------------------- 门面回注
_INJ = {}


def bind(**kw):
    """门面启动时回注横切依赖（见模块 doc）。"""
    _INJ.update(kw)


# _qa_dir / _dir_mtime / _first 原来也走 _INJ，三者的真实现都不依赖 model 层，
# 已经下沉到 core（qa_dir / _dir_mtime 在 core.paths，_first 在 core.text），
# 这里直接 import 即可，少三层转发。剩下的 4 个回注是真跨域：
#   load_units      —— world 域，map 反向 import 会成包级环
#   _state_locate / _parse_state_provinces / _set_state_provinces
#                    —— state 文本原语，真实现仍在门面


def load_units(*a, **k):
    return _INJ["load_units"](*a, **k)


def _state_locate(*a, **k):
    return _INJ["_state_locate"](*a, **k)


def _parse_state_provinces(*a, **k):
    return _INJ["_parse_state_provinces"](*a, **k)


def _set_state_provinces(*a, **k):
    return _INJ["_set_state_provinces"](*a, **k)
