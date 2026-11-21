## 雪绒的钢铁雄心编辑器 v1.25.6

修复同一事件文件包含多个 `add_namespace` 声明时保存后续命名空间事件误报前缀不一致的缺陷，并明确「进游戏检查」仅负责自动测主菜单 `error.log` 与缺 mod 禁用原因提示。

### 主要改进

1. **多命名空间事件文件保存修复（`xuerong/model/event.py`）**
   - `save_event()` 从原先只读取文件第一个 `add_namespace`（`re.search`）改为提取全部 `add_namespace = <ns>` 列表校验；在同一 `events/zz_focus_editor_events.txt` 中创建并保存第二个及以上命名空间（如 `my_ns.1`）不再误报「事件 id 前缀与文件 namespace 不一致」，真正不匹配时会明确指出缺失的前缀与文件当前已声明的命名空间。
   - `add_event()` 改用整词边界正则避免 `add_namespace = foo` 被已有的 `add_namespace = foo_` 子串误判为已声明；`load_events()` 与 `delete_event()` 对 `ns.id` 优先按自身前缀映射 `namespace`。

2. **「进游戏检查」状态提示与作用范围说明（`focus_editor_index.html`、`web/js/22-data.js`）**
   - 修复未加载非原版 mod 时打开「进游戏检查」按钮静默置灰的问题，顶部横幅明确提示先在欢迎页或左侧「数据源」加载待测 mod。
   - 弹窗标题与说明明确「进游戏检查」会自动拉起 HOI4 至主菜单收集 `error.log` 后**自动关闭游戏**（用于 L3 报错定位）；如需亲自选国家进档实操测试，需通过 Paradox 官方启动器启用 mod 进入。
