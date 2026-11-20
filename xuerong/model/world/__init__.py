# -*- coding: utf-8 -*-
"""世界创建（world）域 —— 包级入口（原单文件 1,570 行按功能拆成六个模块）。

包名对外不变，既有 import 点一行不改：
  · focus_editor.py:65 一次取 29 个名字，:8726 再 bind() 三个横切口
  · api/handlers/world_mod_h.py:12 / state_country_h.py:21 / content_h.py:30 取各自那几条

模块分工与依赖方向（单向，无环）：
  _inj.py      门面回注出口（reload_data / load_mod / _lp_done），零业务依赖
  units.py     部队：师模板与 OOB 解析、模板/单位写回、模板渲染
  country.py   国家 tag：country_tags 读写、国家历史
  bookmark.py  剧本：日期块、国家块、本地化键、bookmark_add
  loc.py       本地化：缺键计算与 yml 生成
  create.py    编排：world_create（地图 → tag → 州 → 国家历史 → 军队 → 本地化 → 剧本）、
               建 mod 骨架与 _centroids_from_map

  create → units / country / bookmark / loc（world_create 调它们的写入口）
  units / bookmark 不依赖兄弟模块；country / loc 只借 _inj._reload；
  create 借 _inj._load_mod / _lp_done。子模块一律 import 具体模块，
  不走包 __init__，所以这里再做一层再导出不会成环。

背景（沿用原单文件说明）：本域从门面 focus_editor.py 迁出，29 个公开函数里只有 17 个是
任务书点名的，另外 12 个是反向闭包（bookmark / units / country_tags / loc 各自的内部分解），
不带就得反向 import 门面。世界创建的数据面来自 xuerong.state 访问器
（ROOTS / STATES / TREES / LOC / PROV_RGB），写盘能力来自 core.paths 与 model.state / model.map；
三个横切口仍由门面 bind() 注入，world_create 里的 world_leader / focus_gen / world_events /
world_loc / mapgen_scaffold 依旧是函数内 import，原样保留。
"""
from xuerong.model.world._inj import bind
from xuerong.model.world.bookmark import (_bookmark_country_block, _bookmark_date,
                                          _bookmark_loc, _bookmark_write_base,
                                          _game_language, bookmark_add)
from xuerong.model.world.country import (_country_tags_write_base, country_history_create,
                                         country_tag_add, country_tag_delete,
                                         country_tag_refs, load_country_tags)
from xuerong.model.world.create import (_centroids_from_map, create_mod, mod_home, world_create)
from xuerong.model.world.loc import (_loc_defined_set, _loc_need_keys, loc_generate, loc_missing)
from xuerong.model.world.units import (_oob_files, _parse_division, _parse_division_template,
                                       _tpl_render, _units_files, _units_write_base, load_units,
                                       template_add, unit_add)

__all__ = [
    "bind",
    # country
    "load_country_tags", "_country_tags_write_base", "country_tag_refs", "country_tag_add",
    "country_tag_delete", "country_history_create",
    # bookmark
    "_bookmark_write_base", "_bookmark_date", "_bookmark_country_block", "_game_language",
    "_bookmark_loc", "bookmark_add",
    # units
    "_units_write_base", "_units_files", "_parse_division_template", "_parse_division",
    "load_units", "_oob_files", "_tpl_render", "template_add", "unit_add",
    # loc
    "_loc_need_keys", "_loc_defined_set", "loc_missing", "loc_generate",
    # create
    "mod_home", "create_mod", "_centroids_from_map", "world_create",
]
