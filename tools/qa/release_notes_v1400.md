## 雪绒的钢铁雄心编辑器 v1.4.0

国策树**图形预览**：把一棵树画成节点图，节点带真实图标、位置按 x/y 网格排、前置与互斥用连线表示。

参考 [HOI4 Mod Utilities](https://marketplace.visualstudio.com/items?itemName=Chaofan.hoi4modutilities) 的 "Focus tree preview"。

### 怎么用

左侧「国策树」面板 → 「图形预览」→ 顶部下拉选树。

```
国策树预览  [MUV_AFR（53 节点）▾]  MUV_AFR：53 个节点，58 条连线  MVLV_AFR.txt   [适应] [关闭]
```

- 节点位置由 focus 的 `x` / `y` 决定，每格 96px（HOI4 的国策格边长）
- 图标直接走已有的 `/api/icon?gfx=` 接口，显示游戏里的真实国策图标
- 灰色实线 + 箭头 = prerequisite（前置）
- 红色虚线 = mutually_exclusive（互斥）
- 点节点，顶部显示：中文名、id、坐标、成本、前置、互斥

### 实测（muvluvCN 1.19）

42 棵国策树，第一棵 `MUV_AFR`：

```
53 个节点，58 条连线
点「稳住苏伊士防线」→ [AFR_SecureSuezFront] (12,0) 成本 1
```

### 数据来源

复用已有的 `parse_focus_like`（本来就为编辑器解析了 `x/y/icon/cost/prereq/mutex`），
只加了两个只读接口：

- `GET /api/focus_trees` — 所有树及其节点数
- `GET /api/focus_graph?tree=X` — 单棵树的节点与连线

`prereq` 在 HOI4 里是「组的列表」：组内 OR、组间 AND。预览里每条边单独画，
所以一个节点可能有多个入边；组内 OR 的语义只在点选时的文字里体现
（显示成 `A|B + C` 这种）。

### 踩的坑

预览按钮在国策树面板（`<details>`）里，而初始化函数的执行早于这段脚本 → 按钮没绑上事件。
改成脚本末尾自己绑一次（`DOMContentLoaded` 兜底）。

### 未做

- 拖动画布（现在靠滚动条）
- 共享国策（`shared_focus`）跨树引用不画
- 图标加载失败时没有占位（游戏里的 thisisdog.dds 兜底没接）
