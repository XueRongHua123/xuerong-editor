# -*- coding: utf-8 -*-
"""注入层：`_INJ` 容器、`bind()` 与 10 个转发桩。

零依赖模块 —— 不 import 任何 `xuerong.*`。其它子模块直接在顶部引用这些桩名，
所以被搬运的函数体里那些裸名调用（`_parse_state_provinces(...)` 等）一个字都不用改。
`_INJ[...]` 与 `_INJ.update(...)` 的取法保持原样，不要统一。
"""


# ---------------------------------------------------------------- 门面回注
_INJ = {}


def bind(**kw):
    _INJ.update(kw)


def _all_prov_neighbors(*a, **k):
    return _INJ["_all_prov_neighbors"](*a, **k)


def _hist_depths(*a, **k):
    return _INJ["_hist_depths"](*a, **k)


def _hist_find_top(*a, **k):
    return _INJ["_hist_find_top"](*a, **k)


def _refine_grow_units(*a, **k):
    return _INJ["_refine_grow_units"](*a, **k)


def _parse_state_provinces(*a, **k):
    return _INJ["_parse_state_provinces"](*a, **k)


def _set_state_provinces(*a, **k):
    return _INJ["_set_state_provinces"](*a, **k)


def ensure_file_writable(*a, **k):
    return _INJ["ensure_file_writable"](*a, **k)


def link_countries(*a, **k):
    return _INJ["link_countries"](*a, **k)


def refresh_start_date(*a, **k):
    return _INJ["refresh_start_date"](*a, **k)


def reload_data(*a, **k):
    return _INJ["reload_data"](*a, **k)
