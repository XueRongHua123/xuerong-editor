# -*- coding: utf-8 -*-
"""州 / 省份域 —— 包级入口（原单文件 `xuerong/model/state.py` 1,396 行按功能拆成六个模块）。

P2-state 从门面迁入；本轮是纯搬家，45 个函数体与 5 个顶层赋值一个字未改。
包名对外不变，既有 import 点一行不改：
  · focus_editor.py:83 一次 import 本包（`_m_state`），:84-91 括号再取 26 个名字
  · focus_editor.py:8713 `_m_map.bind(_state_locate=_m_state._state_locate, ...)`
  · focus_editor.py:8716 `_m_state.bind(...)` 注入 10 个横切口，
    :8771-8797 用 `_m_state.xxx` 建 27 个同名别名
  · api/handlers/state_country_h.py:16-18 取 8 个名字
  · model/world/country.py:16、model/world/create.py:14 各取 1 个

依赖边界（与原单文件一致）：
  · 五个全局容器走 `xuerong.state` 的访问器（states / roots / loc / changed / countries）；
    开局日期与写盘提示也走访问器（`refresh_start_date` 会改 START_DATE）
  · 六个州元数据常量从 `xuerong.state` import（一处定义）
  · 三个 map 助手 `_ensure_prov_rgb` / `_map_pick` / `_refine_load_ids` 来自 `xuerong.model.map`
  · 其余横切动作用 `bind()` 回注（见 `_inj`）；`_INJ[...]` 与 `_INJ.get(...)` 两种取法的
    差异是原行为，保持不动

模块分工与依赖方向（单向，无环）：
  _inj.py      注入层：`_INJ` + `bind` + 10 个转发桩，零依赖
  index.py     → _inj              省↔州索引与定位：definition.csv 地理查询、
                                   state 文件枚举与指纹、省→州映射表与缓存、`_state_locate` 家族
  edit.py      → _inj              写侧改属性：owner / 建筑 / 资源 / 胜利点 / scope 的文本层改写
  io.py        → _inj index edit   读展示与保存：列表 / 详情 payload、`state_save`、批量建筑应用
  create.py    → _inj index        新建州：目标目录、空闲 ID、`state_create`
  refine.py    → _inj index io create  精细调整：省份逐个指派、预览与落盘

`_coastal_provinces` / `state_is_coastal` 归 index 而不是 refine：它们是「读 definition.csv
把省映射到州属性」的地理查询，与索引同族；放进 refine 会成为 `io ↔ refine` 环
（`io.state_detail` 调 `state_is_coastal`，`refine.state_refine_apply` 调 `io.state_save`）。

27 个业务函数 + 7 个索引内部辅助（`_state_files_in_layers` / `_read_raw_state` /
`_state_locate_fast` / `_strip_inline_comment` / `_state_id_and_provs` /
`_state_files_fingerprint` / `_prov_to_state_map`）+ `bind` 在这里再导出；10 个注入桩留在
`_inj`，只经 `bind()` 使用。子模块一律 import 具体模块、不走包 `__init__`，所以这里再做
一层再导出不会成环。
"""
from xuerong.model.state._inj import bind
from xuerong.model.state.create import _free_state_id, _states_dir_for_write, state_create
from xuerong.model.state.edit import (_drop_in_scope, _insert_pos, _set_building,
                                      _set_in_scope, _set_owner_all, _set_prov_building,
                                      _set_resource, _set_victory_points,
                                      _state_history_range, _state_owner_effective)
from xuerong.model.state.index import (_coastal_provinces, _find_state_of_prov,
                                      _prov_to_state_map, _read_raw_state,
                                      _state_file_for, _state_files_fingerprint,
                                      _state_files_in_layers, _state_id_and_provs,
                                      _state_locate, _state_locate_fast,
                                      _strip_inline_comment, state_is_coastal)
from xuerong.model.state.io import (_state_fields_from, _state_prov_list, state_apply_buildings,
                                    state_detail, state_save, states_payload)
from xuerong.model.state.refine import (state_province_edit, state_refine_apply,
                                        state_refine_preview)

__all__ = [
    "bind",
    # index
    "_coastal_provinces", "state_is_coastal", "_state_locate", "_state_files_in_layers",
    "_read_raw_state", "_state_locate_fast", "_strip_inline_comment", "_state_id_and_provs",
    "_state_files_fingerprint", "_prov_to_state_map", "_find_state_of_prov", "_state_file_for",
    # edit
    "_state_owner_effective", "_state_history_range", "_insert_pos", "_set_owner_all",
    "_set_in_scope", "_drop_in_scope", "_set_resource", "_set_building",
    "_set_prov_building", "_set_victory_points",
    # io
    "states_payload", "state_detail", "state_save", "state_apply_buildings",
    "_state_prov_list", "_state_fields_from",
    # create
    "_states_dir_for_write", "_free_state_id", "state_create",
    # refine
    "state_province_edit", "state_refine_preview", "state_refine_apply",
]
