## 雪绒的钢铁雄心编辑器 v1.26.0

> **重要更新**｜全新科技树工作台落地，可视化编辑科技页、背景、图标、网格拖拽与连线

推出**科技树工作台（Tech Tree Studio）**，把原先只支持列表填表的科技弹窗升级为可视化全屏工作台；同步修复国家历史日期块隔离写入与跨会话本地化保留缺陷，完成全部 8 大核心编辑域的游戏实机生效（L4）验证。

### 主要更新

1. **全新科技树工作台（Tech Tree Studio）**
   - **三栏全屏可视化画布（`#techModal` / `web/js/12b-tech-studio.js`）**：按 `00_technology.txt` 与 `interface/countrytechtreeview.gui` 还原页签切换、背景图、年份标尺、`gridboxtype` 根树边框、子节点布局与 `path`（贝塞尔箭头 + 科研系数角标）/ `xor`（互斥）连线，自适应深色与纸质双主题。
   - **科技页与 GUI 可视化编辑（`xuerong/model/tech_gui.py`）**：支持新建/排序/编辑科技页签（`ledger`、`available`、滚动区尺寸、背景图、`techtree_<folder>_item` 皮肤尺寸与 `slotsize`），支持年份刻度增删改并同步更新科技文件 `@year` 宏，支持分区标题与 `gridboxtype` 根树注册/迁移/格式切换（`LEFT`/`UP`/`DOWN`/`RIGHT`）。
   - **画布拖拽、连线与开局点选**：支持节点批量拖拽写回网格 `(x, y)` 坐标、点选建立/删除 `path` 与 `xor` 连线、新增科技直接作为根树或挂接父节点，并内置「游戏内不可见根科技 / 坐标重叠 / 缺分类 / 缺图标」实时诊断与一键修复。
   - **PNG 导入直转 DDS 贴图（`xuerong/core/gfx.py`）**：右侧支持直接上传 PNG 生成科技图标（`kind="tech"`）、2 帧页签图标（`kind="tech_tab"`，182×61）与等比缩放背景图（`kind="tech_bg"`），同步注册 `.gfx` 条目与前端图标映射，免去手工切 DDS 步骤。
   - **孤立科技修复与 GUI 解析锁死**：查明孤立根科技必须挂入 `path = { leads_to_tech = ... }` 或注册 `<root_tech>_tree` 方可在游戏内显示；抽取 `_block_body_range()` / `_iter_block_children()` 修复多处 GUI 外层块遍历失效隐患，并清理不存在 sprite 导致的控制台 404 请求。

2. **国家历史脚本块隔离与跨会话本地化保留**
   - **日期块与 DLC 条件块隔离（`xuerong/core/text.py` / `tech.py` / `character.py` / `focus_editor.py`）**：国家科技、将领招募（`recruit_character`）与外交附庸（`set_autonomy`）读写均跳过 `1939.1.1 = { ... }` 日期块与 DLC `if` 分支，新增开局脚本统一插入首个日期块之前，防止写入 1936 开局后被忽略或粘连括号。
   - **本地化增量合并（`xuerong/model/loc.py`）**：`save_loc` 先读取磁盘现有 `zz_focus_editor_l_<lang>.yml` 再合并当前会话增量后原子写盘，重启编辑器后局部保存本地化不再覆盖既有条目。

3. **自动化校验与实机里程碑**
   - 新增 `tests/test_submod_e2e.py` `test_17_tech_studio_e2e`（端到端覆盖科技页签、GUI、年份宏、子标题、根树、`path`/`xor` 连线、批量拖拽、PNG 导入、编码规范与 Chrome 无头零报错验收）。
   - 全量回归 `tests/test_submod_e2e.py`（17 项，16 通过 / 1 跳过缺失旧个人目录）、`tests/test_http_contract.py`（21/21）、`tests/routes_smoke.py`（224 OK / 0 500）、`qa/regress_all.py`（180/180）及 HOI4 实机启动 `qa/hoi4_l3_check.py`（`61 -> 61`，新增 0 条）均通过。
   - 阶段三全部 8 大核心编辑域（国策、事件、本地化、国家精神、决议、人物、科技、州）与保持域（国家与外交）均已完成 1936 法国开局实机截图验收。
