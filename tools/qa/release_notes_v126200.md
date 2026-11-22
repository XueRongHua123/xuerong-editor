## 雪绒的钢铁雄心编辑器 v1.26.2

> **小更新**｜完善画河流与地图单文件接管流程，补齐高程热力预览与吸管取省并完成 HOI4 L3 实机验证

本版本围绕 submod 地图编辑链路打通了只读层单文件接管、HOI4 河流控制点与 1px 规则校验、高程热力图层预览及地图工具互斥机制，并完成全量回归与真机启动 L3 差分检查。

### 更新内容

1. **地图单文件接管与局部图层秒级刷新（`xuerong/core/paths.py`、`xuerong/model/map/io.py`、`render.py`、`web/js/11-map.js`）**
   - 新增 `ensure_writable_file()`、`_ensure_map_writable()` 与 `_map_pair_compatible()`：当 `rivers.bmp`、`terrain.bmp`、`heightmap.bmp` 或 `provinces.bmp` 位于只读原版或下层父 mod 时，默认拦截并提示用户确认，确认后单文件复制到当前可写 submod 顶层再写入，同时兼容子层单文件与下层 `provinces.bmp` 同分辨率编辑。
   - `map_build()` 支持 `only="terrain"` / `only="rivers"` 局部刷新；前端新增 `_mapWriteWithAdopt()` 与图层版本递增（`MAP.ver`），局部改图无需重建全部缓存图层。

2. **画河流升级与 HOI4 规则检测（`xuerong/model/map/river.py`、`focus_editor.py`、`focus_editor_index.html`、`web/js/11-map.js`）**
   - 河流笔刷新增控制点类型：`source`（源头起点 绿 0）、`flow_in`（汇入主干 红 1）、`split`（分流岔口 黄 2），控制点强制单点 1px 落笔，画笔默认宽度调整为 `1`。
   - `river_stats()` 补充 `sources` / `flow_ins` / `splits` 计数、`thick_2x2` 2×2 粗块检测及 `no_source_blocks` 缺控制点河段提示；河流预览与构建图层统一使用 `_RIVER_RGBA_MAP` 标准色表并在写盘/撤销后自动失效缓存。

3. **高程热力层、画笔互斥与吸管取省（`xuerong/model/map/terrain.py`、`xuerong/api/handlers/map_h.py`、`web/js/11-map.js`）**
   - 新增 `height_preview()` 与 `GET /api/height_preview.png`，在图层面板提供「高程热力」叠加层与透明度调节。
   - 新增 `mapRegisterBrush` / `mapDeactivateBrushes` 互斥管理，开启河流/地形/高程任一画笔或切换工具模式时自动退出其余激活画笔。
   - 解锁地图工具栏「吸管取省（I）」模式，点击地图任意省份即可吸取省号填入涂色目标并切至涂色模式。

4. **自动化与真机 L3 验证**
   - `qa/check_game_readable.py` 扩展至 36/36（覆盖河流控制点/主干写入、8 位 BMP 头部、像素读回与撤销）；`tests/test_map_ui.py` 覆盖河流笔刷、互斥与吸管取省；`tests/test_submod_e2e.py` 新增 `test_18_map_river_adopt_and_rules`（17 通过 / 1 跳过）。
   - 全量 `qa/regress_all.py`（180/180）、`tests/routes_smoke.py`（226 OK / 0 倒退）、`tests/browser_smoke.py` 全部通过；通过编辑器 API 单文件接管原版 `rivers.bmp` 绘制合规支流后启动真实 `hoi4.exe` L3 主菜单差分检查，`MENU_OK` 且 `error.log` 相对原版基线新增 `0` 条。
