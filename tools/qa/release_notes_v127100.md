## 雪绒的钢铁雄心编辑器 v1.27.1

> **小更新**｜三大异构大 mod 实机 L3 闭环与书签/装备/人物/海军修复

本版本围绕 Kaiserreich、Millennium Dawn 与 TNO 三大异构大型模组完成《钢铁雄心 IV》1.19 实机主菜单 L3 零新增报错闭环，同时修复书签跨模组读取与 L2 检查、人物 `replace_path` 隔离、装备注释保留与变体写盘、师团模板叠加顺序及海军 OOB 接管漂移等 6 项深层缺陷。

### 1. 书签跨模组修复与 8 项 L2 静态检查

- **动态意识形态加载（`xuerong/core/ideologies.py`）**：新增 `load_ideology_names()`，沿 `effective_layer_files("common/ideologies", ...)` 动态读取模组意识形态键名（KR `10` 项无 `neutrality`，MD `5` 项含 `neutrality`，TNO `38` 项无 `neutrality`），空目录回退原版 4 意识形态。
- **书签读写与格式修正（`xuerong/model/world/bookmark.py`、`focus_editor.py`）**：
  - `bookmark_add()` 动态选取模组意识形态与 `picture`，已有 `default = yes` 时不再重复写入；双语 `.yml` 改用 `unique_editor_filename()` 隔离命名与 `bkey + "_" + tag + "_DESC"` 键名。
  - `load_bookmarks()` 兼容裸国家块（`FRA = {`）与裸键值（`name = KR_scenario_name`）；`bookmark_set()` 补齐四段日期；`bookmark_delete()` 剥除硬编码 UTF-8 BOM 并修复 `bookmark =` 残留。
- **书签 L2 静态诊断与可读性校验（`xuerong/model/diagnose/`、`qa/check_game_readable.py`）**：`diagnose` 新增 `_diag_bookmarks()` 8 项规则，`schema.py` 放行裸国家块，`check_game_readable.py` 补入第 7 节书签可读性检查（45/45 通过）。

### 2. 人物 `replace_path` 隔离防原版泄漏

- **`character_add()` 遵守 `replace_path`（`xuerong/model/character.py`）**：写回改走 `reversed(effective_layer_files(...))` 检索既有文件，被 `replace_path` 屏蔽且上层无同名文件时新建空白容器再写入，修复 KR `FRA characters.txt` 体制下回落拷贝原版 `FRA.txt` 导致 `FRA_pierre_laval` 与 `liberalism` 泄漏的问题。

### 3. 装备变体、师团叠加与海军接管加固

- **装备注释保留与槽位继承（`xuerong/model/equipment.py`）**：`_equip_locate_in_file()` 与 `equipment_edit()` 改用 `_strip_keep_len()` 在原文坐标定位并在 COW 接管后重定位，保留块内 `#` 注释；`load_equipment()` 与 `equipment_detail()` 沿 `archetype` 继承 `module_slots`；`add_equipment()` 补齐只读守卫与无 BOM 写盘。
- **脚本枚举登记与装备变体写盘（`focus_editor.py`）**：`copy_item("equip")` 同步登记 `common/script_enums.txt`；`country_variant_add()` 与 `save_variant()` 放宽命名校验、支持 `upgrades` 并防撞名无 BOM 写盘。
- **师团叠加顺序与海军局部索引（`xuerong/model/world/units.py`、`focus_editor.py`）**：`load_units()` 改为 `reversed(files)`（底层→顶层）防止下层模板定义反盖上层；`load_navy()` 支持单行 `ship`，`navy_set_ship()`、`navy_add_ship()` 与 `navy_add_tf()` 改用 COW 前锁定的文件局部索引 `(local_fi, local_ti)` 消除跨文件索引漂移。

### 4. 三大异构大 mod 实机 HOI4 1.19 L3 闭环与全量回归

- **三大异构大 mod 实机 L3 差分（纯 HTTP API 构建隔离 submod，零改父 mod，`error.log` 均新增 `0` 条）**：
  - **Kaiserreich（`1521695605`）**：基线 `MENU_OK` `82.7s` `222` 行 → 目标 `MENU_OK` `41.8s` `222` 行（覆盖 `character_add`/`set`、`decision_add`/`set`、`country_save`、`idea_add`/`save`/`toggle`、`equipment_edit` 14/14 注释保留、`copy_item("equip")` 登记 `script_enums.txt`、`bookmark_add`、`loc_save`、`diagnose` 0 error）。
  - **Millennium Dawn（`3374271790`）**：基线 `MENU_OK` `150.8s` `153` 行 → 目标 `MENU_OK` `186.4s` `152` 行（覆盖 `country_tech_toggle`/`tech_save`、`equipment_edit` 12/12 注释保留、`template_save` 4 团、`navy_set_ship` 零漂移、`bookmark_add`、`loc_save`、`diagnose` 0 error）。
  - **TNO（`2438003901`）**：基线 `MENU_OK` `76.5s` `490` 行 → 目标 `MENU_OK` `55.1s` `490` 行（覆盖共享国策接管与 `shared_add`/`save_shared`、`event_add`/`save` 0-opt/1-opt、`bookmark_add`、`loc_save`、`diagnose` 0 error）。
- **自动化回归与门禁**：`tests/test_submod_e2e.py` 新增 `test_29_l3_bookmark_char_equip_navy_cross_mod_fixes`（126 断言，`-W error::ResourceWarning` 0 警告，全量 28 通过 + 1 跳过 `test_03`）、`qa/regress_all.py` 180/180、`qa/check_game_readable.py` 45/45、`tests/routes_smoke.py` 226 OK / 0 倒退、`tests/test_http_contract.py` 21 PASS 及全量静态门禁通过。
