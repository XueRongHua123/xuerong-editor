## 雪绒的钢铁雄心编辑器 v1.27.0

> **重要更新**｜地图编辑全子域通过实机 L3，深度适配 KR / MD / TNO 大型模组

本版本完成地图编辑全部 8 个子域的《钢铁雄心 IV》1.19 实机主菜单 L3 验证并摘除地图主入口实验性标签，同时针对 Kaiserreich、Millennium Dawn、TNO 等大型异构模组完成深度适配与多项核心修复。

### 1. 地图编辑 8 子域通过 HOI4 1.19 实机 L3 并摘除主入口实验性标签

- **覆盖范围**：改地形（单省、批量、画笔）、高程画笔、涂省/省界、合并省、铁路、战略区、补给区、海峡/邻接 8 个子域全部接入单文件 COW 接管、只读目录拦截与无 BOM 写盘。
- **BMP 与表格写盘护栏**：`bmp_info()`、`bmp_write_rect()` 与 `bmp_write_rect_8()` 校验并拦截压缩 BMP；`definition.csv` 统一按 `utf-8-sig` 读取并保留原始行尾；高程画笔羽化多点按 `max(t)` 聚合；幽灵省清理仅删除末尾连续段以防止省号断号。
- **防跨州分裂与结构校验**：
  - 战略区新建与修改省列表新增 `_sr_check_state_split` 护栏，拆散同州时返回 `STATE_SPLIT_SR` 拦截并支持 `expand_states` 自动整州补全及跨层迁出。
  - 跨州合并省同步修复州文件定位并接管旧战略区移出源省，防止出现一省多州。
  - 铁路支持块式与行式混存定位，等级钳制 `1..5` 并拒绝海省；`adjacencies.csv` 保留 `-1;-1` 哨兵行并将新增条目插入其前方，`sea` 类型校验 `through` 字段。
- **界面标签调整**：摘除地图主入口（`#mapHead`）的 `实验性` 标签；独立功能「生成地图 / 造一个新世界」仍保留 `实验性` 标签与状态说明。

### 2. 三大异构大型模组深度适配与 P0 修复

- **贴图解码与装备图标（`xuerong/core/gfx.py`）**：`icon_png()` 新增 `_decode_dx10_dds` 兜底解码 DX10 32bpp 无压缩 `.dds`（DXGI `91`、`87`、`93`、`88`、`28`、`29`），解决大型模组科技与国策图标 404；扩充 `EQUIP_ICONS` 路径匹配补全装备图标索引。
- **人物与角色（`xuerong/model/character.py`、`xuerong/state.py`）**：`load_characters()` 兼容无引号本地化键（`name = KEY`）与多角色条目，补全 `navy_leader`、`advisor`、`scientist` 新建与改名支持。
- **决议与国家精神（`xuerong/model/decision.py`、`xuerong/model/idea.py`）**：`load_decisions()` 移除跨文件 `seen_cat` 误丢弃以合并跨文件同类别决议，`decision_set()` 支持插入缺失标量字段；`country_idea_toggle()` 写盘后同步刷新内存状态。
- **国家历史、装备变体与意识形态（`focus_editor.py`、`xuerong/model/equipment.py`）**：国家历史编辑器、装备变体与共享国策接入单文件 COW 接管与只读保护；新增 `_load_ideologies()` 动态加载模组意识形态并兼容 `set_stability` / `set_war_support`。
- **科技与现代剧本开局块（`xuerong/model/tech.py`、`xuerong/model/tech_gui.py`）**：`load_technology_tags()` 不区分大小写兼容 `technology_Categories`；`load_country_techs()` 与 `country_tech_toggle()` 在顶层无 `set_technology` 时兼容开局日期块（如 `2000.1.1`），同时保持 1936/1939 日期块隔离读写。
- **OOB 编制与空海单位（`xuerong/model/world/units.py`、`focus_editor.py`）**：`_parse_division_template()` 兼容单行坐标 `{ x = 0 y = 2 }` 并锚定顶层 `support` 避开 `regimental_support`，新增 `patch_division_template_block()` 局部写回保留扩展键与注释；`load_air_wings()` 兼容 BBA 单行多联队，`load_navy()` 支持多行 `ship` 解析，清理 `air_wing_delete` 与 `war_delete` 硬编码 BOM。
- **共享国策展开与视口懒加载（`focus_editor.py`、`xuerong/api/handlers/focus_h.py`、`web/js/10-focus.js`）**：`expand_shared_trees()` 改用 BFS 递归展开下游共享国策树并计算合成树 `ax`/`ay` 坐标；`/api/focus` 兜底查询 `shared_focuses` 消除 404；前端超 400 节点国策树按视口每批 32 并发分批懒加载图标。
- **事件树、对象对比、诊断隔离与双主题界面（`xuerong/model/event.py`、`object_diff.py`、`support_bundle.py`、`xuerong/core/paths.py`、`xuerong/model/diagnose/`、`web/`、`focus_editor_index.html`）**：
  - 事件树改走 `effective_layer_files()` 全叠加链合并、允许 `hidden = yes` 0-option、校验前移并在接管时剥离非 `.yml` BOM。
  - `object_diff` 默认 `interacted` 过滤底层纯 `blocked` 残骸并跳过 `title = { ... }` 条件块；`diagnose(scope="current")` 全项检查隔离至顶层可写层提速；修正脱敏诊断包原版 `is_game` 判定。
  - 修复 `#unitAddBtn` 报错、`evDraw` 竞态、`#srcState` 只读来源区分、动态 `#histParty` 意识形态、人物/决议大列表提示以及 `#techModal` / `#designerModal` 1280×720 双主题布局。

### 3. 回归与实机验证摘要

- **实机 HOI4 1.19 L3 差分（`error.log` 均新增 0 条）**：`xr_l3_map_bmp` `61 -> 61`、`xr_l3_map_txt` `61 -> 61`、`xr_l3_map_xmod`（13,510 省第三方大 mod）`227 -> 227`。
- **自动化回归**：`tests/test_submod_e2e.py`（含 `test_27` 与 `test_28`）、`qa/regress_all.py`（180/180）、`tests/routes_smoke.py`（226 OK / 0 倒退）、`tests/test_http_contract.py`（21 PASS）及全量静态门禁通过。
