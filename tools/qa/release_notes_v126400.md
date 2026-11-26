## 雪绒的钢铁雄心编辑器 v1.26.4

> **小更新**｜修复真实 submod 科技保存、写时接管与多项交互痛点

本版本汇总 `v1.26.3` 之后的多级 submod 实战修复与工程债清零，涵盖科技保存花括号保护、国策与装备写时接管、父层 `replace_path` 写层放行、本地化冲突键同步、诊断全链进度、事件选图预览以及多项界面弹窗修复。

### 修复与优化

1. **科技保存 `path` 子块花括号保护（`xuerong/core/text.py`、`xuerong/model/tech.py`、`web/js/12-tech.js`）**
   - `set_scalar()` 增加 `(?!\{)` 前瞻与同名子块 `key = {` 保护，避免把块头识别为标量值导致花括号配对破坏。
   - `save_tech()` 移除标量列表中的 `"path"`，前端 `#techPath` 设为只读并停止在保存时回传 `props.path`，修复保存含 `path = { leads_to_tech = ... }` 的科技必定报错的问题。

2. **多级 submod 国策与装备写时接管（`xuerong/model/focus.py`、`xuerong/model/equipment.py`）**
   - `save_focus()` 与 `save_equipment()` 对齐 `idea.py` 接入 `ensure_writable_file()`，编辑父 mod 或只读层条目时自动复制接管至顶层可写 submod 后写入，不再原地修改下层父 mod 文件。

3. **父层 `replace_path` 写层放行与新建世界兼容（`xuerong/model/country.py`、`xuerong/model/world/_write_guard.py`）**
   - `_country_hist_write_base()` 与 `world_write_base()` 改为仅当 `replace_path` 独占层严格高于当前可写层时阻断，下层父 mod 的 `replace_path` 不再阻断上层 submod 写入国家历史或世界数据。
   - 有显式 `root` 时走 `mod_layers(root)`、无 `root` 时回退 `state.roots()`，保护「造一个新世界」独立目录不被旧会话污染，并修正阻断提示路径为「地图 → 图层 → 目录写入目标」。

4. **本地化保存同步同层靠后 `replace/*.yml` 冲突键（`xuerong/model/loc.py`）**
   - `_write_loc()` 新增 `_sync_later_replace_ymls()`，在写入默认 `zz_focus_editor_l_<lang>.yml` 时同步更新同目录下字母序更靠后的 `replace/*.yml` 同名键，避免保存名称与描述后刷新被同层文件回盖。

5. **诊断 17 阶段实时进度、事件选图预览、幽灵贴图过滤与体检统计补全（`xuerong/model/diagnose/__init__.py`、`xuerong/api/handlers/map_h.py`、`focus_editor.py`、`focus_editor_index.html`、`web/js/13-event.js`、`20-panels.js`、`21-tools.js`、`90-boot.js`）**
   - `diagnose()` 接入 `set_progress_hook()` 上报 17 个检查阶段名称与百分比，前端轮询 `/api/load_progress` 实时展示当前阶段与耗时。
   - `/api/icons` 新增 `kind=event` 与 `_filter_existing_sprites()` 过滤贴图缺失的幽灵条目，`/api/icon` 缺失贴图时返回 404；事件编辑面板新增「选择图片」按钮与 `#eventPicPreview` 实时预览。
   - `lint_project()` 返回 `scope.shared_focuses`，`renderLint()` 在全项目体检统计栏补显共享国策数量。

6. **弹窗稳态与界面交互修复（`web/css/components.css`、`layout.css`、`web/js/11-map.js`、`12b-tech-studio.js`、`22-data.js`、`90-boot.js`）**
   - `#diploModal` 固定高度并支持内部滚动、阻止同国家重复重载导致的失焦重排，并补全点击遮罩关窗。
   - `#updModal` 在开发版或已有其他弹窗开启时不抢焦点，并安全渲染更新说明 Markdown；`#stateModal` 保存刷新前校验弹窗仍开启，防止关窗后自动重开。
   - `#srcState` 综合五域自有条目与依赖链区分继承链与纯原版空壳；`#lcChainStrip` 允许换行防止 5 层叠加链截断；`#techModal` 重名页签附加 `(folder_id)` 与缺图隐藏；`#srcBox` 顶部引导条不再换行挤压，错开 `#status` 与看板娘间距。

7. **底层工程债清零（`focus_editor.py`、`xuerong/core/paths.py`、`xuerong/model/`、`web/js/22-data.js`）**
   - 清零门面 32 个函数与 `model/` 非地图 `_map_pick` 错选，修复 `file_excerpt()` 层序；将 `focus_editor.py` 与 `xuerong/` 共 68 个后端文件全部裸 `io.open`/`open` 收敛为 `with` 上下文管理器并由 AST 护栏锁定零裸句柄与零 BOM。
   - 修复 `load_battalions()` 与 `load_country_tags()` 跨层反盖、`_rail_over_level()` 跨层查找 `_layers_find("map/railways.txt")`、`_layer_files()` 大小写去重，并清理前端 `#ofsType` `dataset.filled` 一次性守卫残余。

### 回归验证

- `tests/test_submod_e2e.py` 新增并跑通 `test_22` 至 `test_26`（覆盖非地图选层、68 文件零裸句柄 AST 护栏、跨层反盖/铁路查找、P0/P1/P2 修复与诊断进度/事件选图/体检统计 1280×720 无头 Chrome 复验；发版前复跑 `test_25` 与 `test_26` 2 tests OK）。
- `qa/regress_all.py`（180/180）、`tests/routes_smoke.py`（226 OK / 0 倒退）、`tests/test_http_contract.py`（21 PASS）、`tests/test_scope_bridge.py`（236 路由 0 违规）及 `qa/_check_import_boundary.py`（67 文件 0 违规）全部通过。
