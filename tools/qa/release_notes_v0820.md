## 雪绒的钢铁雄心编辑器 v0.82.0

修掉一个影响所有可拖拽区域的交互问题，并把结论写成了设计纲要。

### 问题

在地图上按住左键拖动，界面文字会被选中；继续把鼠标拖出窗口，浏览器会把它当成"拖拽操作"，
可能新开页面或触发搜索。右键也有类似的多余行为。

### 三个根因

1. 界面整体没有 `user-select: none`，只有零星几个组件设了
2. `<img>` 默认可拖拽，拖到标签栏会被当成"打开图片"
3. 画布的 `pointerdown` 没有 `preventDefault()`，浏览器照常开始文本选择

### 修法

| 措施 | 说明 |
|---|---|
| `html, body { user-select: none }` | 全局禁用选择 |
| 白名单恢复 | `input / textarea / select / pre / code / [contenteditable] / .selectable / #aiOut / #lintList / #scriptBody / #cpList` 仍可选中复制 |
| 所有 `img` 设 `draggable=false` | 并用 `MutationObserver` 覆盖后续动态插入的图片 |
| `document` 捕获阶段拦截 `dragstart` | 界面没有需要原生拖放的功能 |
| `document` 捕获阶段拦截 `contextmenu` | 输入框与可复制区域放行，其余不弹菜单 |
| 画布 `pointerdown` 加 `preventDefault()` | 拖动不再触发选择 |

### 验收

- 拖动 200px 后 `window.getSelection().toString().length === 0`
- `dragstart` 的 `defaultPrevented = true`，图片 `draggable = false`
- 地图上右键被拦截，输入框右键正常
- AI 输出区、体检列表、脚本检查表仍可选中复制
- 0 报错

### 新增文档：`docs/DESIGN.md`

把这次和之前的经验固化成 9 节设计纲要，后续加功能照着做：

1. 指针交互：可拖拽区域不许选中文字
2. 缩放：所有屏幕坐标除以 `uiZoom()`
3. 写盘：只改指定字段、先备份、返回 diff
4. 数据解析：按游戏语义来（日期块、rgb/hsv、回退原版）
5. 图层与模式：一次只改一件事
6. 提示：用状态栏不用 alert
7. 列表与结果区规范
8. 跨 mod 兼容（回退、缓存键、容错、派生值）
9. 测试与验收命令清单
