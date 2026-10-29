## 雪绒的钢铁雄心编辑器 v1.14.0

河流能看了，海峡能改了。

### 1. 河流图层

`rivers.bmp` 是 12 色调色板图，背景用索引 254/255。

构建图层时转成 RGBA 叠层：背景透明，河流保留原色调，存成 `rivers.png`（0.20 MB）。

图层预设新增「河流」：

```
预设   [地形] [州] [省色块]
       [政治] [战略区] [原始]
       [铁路] [河流]
```

也可以在图层面板里单独勾「河流」并调不透明度。

### 2. 海峡 / 连接

`map/adjacencies.csv` 是 10 列 CSV：

```
From;To;Type;Through;start_x;start_y;stop_x;stop_y;adjacency_rule_name;Comment
8857;2284;sea;7617;1560;1009;1556;1016;PANAMA_CANAL;Panama
```

muvluvCN 有 249 条连接（sea 195、impassable 45、9 条类型为空）。

列表按行号显示，类型用颜色区分：

- `sea` 青色
- `impassable` 红色
- 其它灰色

### 3. 四项编辑

| 操作 | 说明 |
|---|---|
| 改类型 | 下拉选 sea / land / impassable / lake |
| 删除 | 按行号摘掉整行 |
| 新增 | 填两端省号 + 类型，追加到末尾 |
| 查重 | 新增前检查这两省之间是否已有连接 |

实测：

```
改类型    第 2 行 sea → land
新增      17300 ↔ 17301（sea）
删除      已删除第 2 行连接
```

### 两个对齐问题

**河流层放错了容器**：第一版把 `<img id="mapRivers">` 插到了 `mapStack` 外面，
不跟随地图的 transform，结果河流画在地图上方的黑色区域里。

移进 `mapStack`（`mapEdges` 之后）才对。

**预设的 ID 映射漏了一项**：`PRESETS.river` 的 `on` 里有 `'rivers'`，但 `ID` 映射表没加
`rivers: 'mapLRivers'`，导致点「河流」预设时复选框没被勾上。

### 说明

河流目前只读（能看不能改）。画河需要逐像素改 `rivers.bmp` 的调色板索引，
和地形画笔同一套机制，但河流有主干/支流的层级关系，不是单像素能表达的。
