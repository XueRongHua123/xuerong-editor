## 雪绒的钢铁雄心编辑器 v0.84.0

地图界面的可读性修复：图层面板不再是"看不清的黑框"。

### 问题

图层面板在浅色的「纸页」主题下是深底 + 浅灰字，选项几乎读不出来；属性面板的三个按钮看起来像纯文字。

### 四个原因

1. **浮层硬编码深色**：`#mapTools` 背景写死 `rgba(10,12,10,.94)`，文字却用主题的 `--muted`
2. **同选择器重复定义**：`#mapTools` 在文件里出现两次，后定义的整体覆盖前面的主题色
3. **全局幽灵按钮带 `!important`**：`.btn{background:transparent!important}`，属性面板的实心按钮规则没加 `!important`，完全无效
4. **组标题与标签都用了弱色**：`--t3`（72% 透明）的 10px 小字压在深底上

### 修法

- 图层面板改用 `var(--panel)` + `var(--line2)`，与主题一致；删除重复的 `#mapTools` 规则
- 图层标签在未选中时用主文字色（`--t1`），选中时用 accent
- 复选框与滑块加 `accent-color: var(--accent)`
- 组标题（数据 / 基础）用次色 + 下划线分隔
- 属性面板按钮用 `#mapSide .mp-acts .btn {... !important}` 显式覆盖幽灵样式，并注释说明原因
- 地图舞台背景从近黑改为柔和深色 + 细点阵

### 顺带修掉一个包体回退

这版构建时发现 exe 从 20.1 MB 涨回 **31.6 MB**——原因是这台机器上后来装了 numpy，
Pillow 的 PyInstaller hook 会把它一并收进包（`libscipy_openblas64_.dll` 单个就有 20.6 MB 解压体积）。

已在打包脚本里显式排除 `numpy / scipy / pandas / matplotlib`，exe 恢复 **20.1 MB**。
验证：新 exe 启动后 `map_meta` 正常（Pillow 仍在）、页面含新面板结构。

### 设计纲要补充

`docs/DESIGN.md` 第十节新增三条：

- 深色浮层必须用主题令牌，不要"写死深色底 + 主题色字"
- 全局 `!important` 幽灵按钮与局部实心按钮的冲突处理（ID 前缀 + `!important` + 注释）
- 同一选择器只允许定义一次
- 验收补充：`getComputedStyle` 抽查 `backgroundColor` 与 `borderTopColor`，不能是 `rgba(0,0,0,0)`
