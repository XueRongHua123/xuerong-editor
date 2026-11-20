# -*- coding: utf-8 -*-
"""地图域 —— 包级入口（原单文件 `xuerong/model/map.py` 2,907 行按功能拆成六个模块）。

P2-map 从 focus_editor.py 迁入；本轮是纯搬家，73 个函数体与 1 个顶层赋值一个字未改。
包名对外不变，既有 import 点一行不改：
  · focus_editor.py:92 `from xuerong.model import map as _m_map`
  · focus_editor.py:93-97 括号一次取 68 个名字
  · focus_editor.py:8713 `_m_map.bind(load_units=..., _state_locate=...,
    _parse_state_provinces=..., _set_state_provinces=...)` 注入 4 个横切口
  · api/handlers/map_h.py:18 取 32 个名字；content_h.py:27 / misc_h.py:20 各取 _map_pick
  · model/{character,decision,focus}.py 与 model/world/{bookmark,country,loc,units}.py 各取 _map_pick
  · model/world/create.py:13 取 _ensure_prov_rgb / map_generate
  · model/state/{create,index,refine}.py 取 _map_pick / _ensure_prov_rgb / _refine_load_ids

模块分工与依赖方向（单向，无环）：
  _inj.py      注入层：`_INJ` + `bind` + 4 个转发桩，零依赖，不 import 任何 xuerong.*
  io.py        读侧底座：叠加链与路径、CSV、BMP 读写、元信息与缓存；不 import 兄弟模块
  terrain.py   地形 / 高程：terrain.txt 与 terrain.bmp 的读改、刷地形、heightmap 绘制 → io
  river.py     河流：rivers.bmp 的绘制 / 撤销 / 统计 / 预览、河流底图 → io
  render.py    渲染与生成：map_build、地形底图、山体阴影、map_generate → io, terrain, river, _inj
  prov.py      省操作：点级撤销、跨省修复、笔刷、合并、邻居、完整性、分析 → io, render, _inj

归属不是按「看着整齐」定的：`prov` 要 `_strategic_regions`（在 render），
而 render 又要 io / terrain / river，所以 prov 只能排在 render 之后；
`_apply_terrain_texture` 要 `_terrain_tex_map`，这条边把 terrain 放在 render 之前；
`_strategic_regions` / `_tag_fallback_color` / `_terrain_colors` 归 render 而不是 prov，
`_terrain_tex_map` 归 terrain 而不是 render，都是为了让上面这张 DAG 不出现环。

依赖边界（与原单文件一致）：
  · 叠加链与路径 → xuerong.core.paths；文本工具 → xuerong.core.text
  · 全局容器（PROV_RGB / MAP_EDIT / 各种缓存）→ xuerong.state 的访问器
  · 写前快照 → xuerong.model.history.snapshot
  · 门面回注 4 个留在 `_inj`，只经 `bind()` 使用，不从包入口再导出
  · qa_dir / _dir_mtime / _first 原来也走回注，已下沉 core，各子模块直接 import

68 个业务函数 + `bind` 在这里再导出（`__all__` 69 项）；子模块一律 import 具体模块、
不走包 `__init__`，所以这里再做一层再导出不会成环。
"""

from xuerong.model.map._inj import bind
from xuerong.model.map.io import (
    _map_files,
    _map_key,
    _map_dir,
    _csv_path_for,
    _refine_load_ids,
    map_sources,
    _map_pick,
    _map_files_layered,
    bmp_info,
    bmp_read_rect,
    bmp_write_rect,
    _ensure_prov_rgb,
    _map_files_strict,
    map_meta,
    map_cache_clear,
    _map_ids_from_cache,
    _prov_state_map,
    bmp_write_rect_8,
    _prov_type_map,
    map_asset,
)
from xuerong.model.map.prov import (
    _save_point_undo,
    _load_point_undo,
    _apply_point_undo,
    _scan_cross,
    map_repair_cross,
    map_repair_preview,
    map_repair_ghost,
    map_analysis,
    map_edit_begin,
    map_edit_dab,
    map_edit_commit,
    map_edit_undo,
    map_edit_redo,
    map_merge_preview,
    map_merge_apply,
    map_prov_neighbors,
    map_edit_state,
    map_integrity,
)
from xuerong.model.map.render import (
    set_progress_hook,
    map_generate,
    _hsv_hex,
    map_build,
    _strategic_regions,
    _terrain_index_map,
    _hillshade_mask,
    _apply_hillshade,
    _apply_terrain_texture,
    _terrain_index_trusted,
    _render_terrain,
    _tag_fallback_color,
    _terrain_colors,
)
from xuerong.model.map.river import (
    _def_rgb_kind,
    _line_pts,
    river_paint,
    river_undo,
    river_stats,
    river_preview,
    _build_rivers_png,
)
from xuerong.model.map.terrain import (
    _terrain_tex_map,
    _terrain_type_to_index,
    terrain_types,
    prov_terrain_set,
    _terrain_common,
    _terrain_apply,
    prov_terrain_batch,
    prov_terrain_by_type,
    height_paint,
    height_sample,
    terrain_paint,
)

__all__ = [
    "bind",
    "set_progress_hook",
    # io
    "_map_files",
    "_map_key",
    "_map_dir",
    "_csv_path_for",
    "_refine_load_ids",
    "map_sources",
    "_map_pick",
    "_map_files_layered",
    "bmp_info",
    "bmp_read_rect",
    "bmp_write_rect",
    "_ensure_prov_rgb",
    "_map_files_strict",
    "map_meta",
    "map_cache_clear",
    "_map_ids_from_cache",
    "_prov_state_map",
    "bmp_write_rect_8",
    "_prov_type_map",
    "map_asset",
    # terrain
    "_terrain_tex_map",
    "_terrain_type_to_index",
    "terrain_types",
    "prov_terrain_set",
    "_terrain_common",
    "_terrain_apply",
    "prov_terrain_batch",
    "prov_terrain_by_type",
    "height_paint",
    "height_sample",
    "terrain_paint",
    # river
    "_def_rgb_kind",
    "_line_pts",
    "river_paint",
    "river_undo",
    "river_stats",
    "river_preview",
    "_build_rivers_png",
    # render
    "map_generate",
    "_hsv_hex",
    "map_build",
    "_strategic_regions",
    "_terrain_index_map",
    "_hillshade_mask",
    "_apply_hillshade",
    "_apply_terrain_texture",
    "_terrain_index_trusted",
    "_render_terrain",
    "_tag_fallback_color",
    "_terrain_colors",
    # prov
    "_save_point_undo",
    "_load_point_undo",
    "_apply_point_undo",
    "_scan_cross",
    "map_repair_cross",
    "map_repair_preview",
    "map_repair_ghost",
    "map_analysis",
    "map_edit_begin",
    "map_edit_dab",
    "map_edit_commit",
    "map_edit_undo",
    "map_edit_redo",
    "map_merge_preview",
    "map_merge_apply",
    "map_prov_neighbors",
    "map_edit_state",
    "map_integrity",
]
