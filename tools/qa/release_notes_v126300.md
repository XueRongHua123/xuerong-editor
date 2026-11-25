## 雪绒的钢铁雄心编辑器 v1.26.3

> **小更新**｜修复叠加链反盖、纯内容 submod 选层与本地化误报等六项问题

本版本汇总 `v1.26.2` 之后的工程债修复，涵盖多层级叠加链覆盖顺序、纯内容 submod 选层、跨层本地化扫描、新建州防撞号、事件树破环分层以及双主题 `--danger` 样式与文件句柄收敛。

### 修复内容

1. **叠加链反向覆盖与全局 `paths._pick` 选层修复（`xuerong/core/paths.py`、`xuerong/model/equipment.py`、`focus_editor.py`）**
   - 取消 `focus_editor.py` 将全局 `_paths.set_root_picker` 错绑至地图专用 `_map_pick(None)`，改由 `paths._pick()` 默认优先选取 `ROOTS` 顶层非只读/非原版 mod（地图域仍独立走 `_map_pick()`），并修正 `ensure_writable_file()` 的 `_ROOT_PICKER` 为 `_pick(root)`。
   - 修复 `equipment.py`（`load_equipment()`、`_equip_locate()`、`delete_equipment()`）、`focus_editor.py`（`load_orgs()`、`load_modules()`、`load_countries()` 的 `tag_files`、`def_file` 与 `history/countries`）按 `effective_layer_files(...)` 与正确层序加载，消除原版或底层反向覆盖顶层 submod 修改的问题。

2. **门面、路由与 `world` 域纯内容 submod 选层修复（`focus_editor.py`、`xuerong/api/handlers/content_h.py`、`misc_h.py`、`xuerong/model/world/`）**
   - 将 `ensure_file_writable`、`r_api_equipment_list`、`r_api_orphan_tags` 以及 `world/loc.py`、`country.py`、`units.py`、`bookmark.py` 中非地图用途的 `_map_pick` 统一切换至 `paths._pick`，解决无 `map/` 目录的纯内容 submod 选层错位问题。
   - 新增 `xuerong/model/world/_write_guard.py` 的 `world_write_base()`，收敛 `units` / `bookmark` / `country` 三处写层守卫并统一 `root` 与 `state.roots()` 回退逻辑。

3. **二级 submod 本地化漏扫父层误报修复（`xuerong/model/world/loc.py`）**
   - `_loc_defined_set(root)` 改为递归遍历 `mod_layers(root)` 全叠加链的 `localisation/**/*.yml`（覆盖各语种及 `replace/` 子目录），消除二级 submod 漏扫父层本地化定义导致的误报。

4. **新建州磁盘州号防撞与数据结构补全（`xuerong/model/state/create.py`）**
   - `_free_state_id(root=None)` 兼扫内存 `state.states()` 与叠加链各层 `history/states/*.txt` 文件名前缀州号，并由 `state_create()` 透传 `root`，解决多层级磁盘州号撞号（`S2`）。
   - 修正新建州内存结构 `victory_points` 类型为列表 `[]`，并补齐 `province_count`、`resources` 与 `province_buildings`。

5. **事件树循环触发破环分层与死代码清理（`web/js/11-map.js`、`web/js/20-panels.js`、`xuerong/core/gfx.py`）**
   - `evDraw()` 增加环路最小入度破环 BFS 分层逻辑，解决事件循环触发（`A→B→A`）及其下游节点全部挤在第 0 层的排版问题；清理 `openUnloadModalOld`、`mapStatusPos` 与 `gfx.py` 冗余死代码，并解除运行态缓存文件追踪。

6. **双主题 `--danger` 变量补全、`load_units` 缓存隔离与 22 处句柄收敛（`web/css/tokens.css`、`xuerong/model/world/units.py`、`core/paths.py` 等）**
   - `tokens.css` 补全暗色（`#e57373`）与纸页（`#b83833`）双主题 `--danger` 变量定义，恢复 40+ 处警告与报错样式，并移除重复 `body.theme-paper` 声明与拼写错误 `--svund`。
   - `load_units()` 新增 `_units_snapshot()` 浅拷贝隔离返回值容器并补齐 `_UNITS_CACHE["mtime"]` 更新，防止外部修改污染模块缓存；将 `core/paths.py`（6 处）、`world/{bookmark,country,loc,units}.py`（14 处）及 `state/create.py`（2 处）合计 22 处文件读写统一改用 `with io.open(...)` 关闭。

### 回归验证

- `tests/test_submod_e2e.py` 新增 `test_19`、`test_20`、`test_21` 锁定全部修复（`20 ok, 1 skipped`）；`qa/regress_all.py`（180/180）、`tests/routes_smoke.py`（226 OK / 0 倒退）、`tests/test_http_contract.py`（21 PASS）及 `ResourceWarning` 与静态门禁全部通过。
