## 雪绒的钢铁雄心编辑器 v1.5.0

**事件树预览**：把一个事件命名空间的触发关系画成分层图。

参考 [HOI4 Mod Utilities](https://marketplace.visualstudio.com/items?itemName=Chaofan.hoi4modutilities) 的 "Event tree preview"（含 `after` 链）。

### 怎么用

左侧「国策树」面板下面点「事件树预览」→ 顶部下拉选命名空间。

### 布局

事件没有 x/y 坐标，用**触发深度**分层：

```
第 0 层：没有入边的事件（故事起点）
第 1 层：被第 0 层触发的
…
同一层内按 id 自然排序（generic.2 在 generic.10 前面）
```

### 连线的三种颜色

| 样式 | 含义 |
|---|---|
| 灰色实线 | `option = { country_event = X }` —— 玩家选了选项触发 |
| 橙黄虚线 | `after = { country_event = X }` —— 事件结束后自动触发 |
| 蓝色点线 | `immediate = { country_event = X }` —— 事件一触发就跑 |
| 紫色虚线 + 虚线框节点 | 指向**本命名空间之外**的事件（比如 `mvlv_generic.100 → mvlv_usa.101`） |

### 解析细节

一个事件体里可能同时有 `option` / `after` / `immediate` 三个块，触发语句藏在各自的块里。
实现上先按 `brace_match` 把这三个块的范围记下来，再看每条触发语句落在哪个块里，
决定它属于哪种线。

事件触发有两种写法都要认：

```hoi4
country_event = { id = mvlv_generic.12 days = 5 }   # 块式
country_event = mvlv_generic.12                     # 简写
```

### 实测（muvluvCN 1.19）

```
287 个事件，分属 44 个命名空间
mvlv_generic：47 个事件，42 条触发，9 个外部引用
```

点节点显示：事件 id、中文标题、所在文件、深度。

### 已知限制

- 第一层事件多时会排成很长一排（`mvlv_generic` 第一层 12 个），需要横向滚动
- 没有做「只显示某个子分支」的过滤
- 循环触发（A→B→A）会让同一批事件挤在同一层
