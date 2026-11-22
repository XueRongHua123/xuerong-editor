## 雪绒的钢铁雄心编辑器 v1.26.1

> **小更新**｜修复科技树工作台右栏页签切换横向错位及删除科技残留网格框的问题

针对 `v1.26.0` 科技树工作台实测中发现的两处体验与清理缺陷发布热修：切换右侧面板不再把表单挤成横向滚动条，删除科技时同步清理关联网格框与失效连线。

### 修复内容

1. **右栏页签切换错位修复与布局优化（`web/js/12b-tech-studio.js`、`web/css/components.css`、`focus_editor_index.html`）**
   - 修复 `switchRightTab()` 切换「科技属性 / 页面与 GUI / 国家开局」时写入内联 `style="display: flex"` 覆盖 CSS `display: block`，导致右栏元素被强行横向排列并裁切溢出的缺陷；切换页签与选中不同科技时自动重置滚动条至顶部。
   - 右栏宽度调整为 `clamp(350px, 26vw, 400px)` 并禁止横向溢出；「年份 / 科研花费 / 科技树页签」改为带显式标签的三列排布（`.tt-meta-3`）；底部增加吸底操作栏（`.tt-sticky-act`）固定「保存科技」与快捷「删除」按钮。

2. **删除科技同步清理 `.gui` 网格框与引用连线（`xuerong/model/tech.py`、`xuerong/model/tech_gui.py`）**
   - `delete_tech()` 在科技被彻底删除（未从下层恢复）时，同步删除可写 `interface/countrytechtreeview.gui` 中对应的 `<tid>_tree` / `root_tech == tid` `gridboxtype`，并清理可写科技文件中指向该科技的 `leads_to_tech` 与 `xor` 引用。
   - 新增空孤立网格框诊断（`diagnostics.orphan_gridboxes`）及底栏「清理空根树框」一键清除入口；新增 `tech_folder_delete` / `/api/tech_folder_delete` 与「删除本页签」按钮（页签内仍有科技时拦截提示）。

3. **回归验证锁定（`tests/test_submod_e2e.py`）**
   - 扩充 `test_17_tech_studio_e2e`：锁定 Chrome 反复切换右栏页签后 `#ttRPaneTech` 保持 `display == "block"` 且无横向溢出，以及删除根科技自动清理 `<tid>_tree` 和空页签彻底删除的完整链路。
