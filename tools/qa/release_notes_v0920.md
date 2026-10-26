## 雪绒的钢铁雄心编辑器 v0.92.0

把 mod 叠加链**显示出来**——之前它只在后台跑，界面上无处可查。

### 之前的问题

编辑器读 `descriptor.mod` 全在后台，界面里既看不到读的是哪个文件，也看不到叠加链有几层。
用户只能看到地图"能打开"或"打不开"，中间过程不可见。

### 现在：图层面板底部有「来源链」

```
来源链
1. 原版（游戏本体）
2. muvluvCN ← 地图
   replace_path 22
3. muvluvCNsub
   replace_path 26 · 依赖 muvluvCN
```

- 显示链上每个 mod 的名称、`replace_path` 条数、依赖
- `← 地图` 标出 `provinces.bmp` / `definition.csv` 实际来自哪一层
- 没有 `descriptor.mod` 的层会标注「无 descriptor.mod」

### 来源下拉也修正了

之前 submod 在下拉里显示「（无地图）」——因为它自己不包含 `provinces.bmp`，
但按叠加链它其实能用父 mod 的地图。现在显示：

> 2989050816（地图来自 2800380626）

### 顺带核对了一件事

`muvluvCNsub` 有自己的 `definition.csv`、`provinces.bmp` 来自父 mod。两份 csv 的 md5 完全一致
（`63d512a8bdb2`，13264 行），所以不会出现「省 id 与像素错位」。这个检查以后会作为地图构建的一部分。

### 验证

- `probe_layers.mjs`：来源链渲染出 3 层，标记正确
- `probe_v081.mjs`：界面功能 0 报错
- 接口 `/api/map_meta` 的 `layers` 每层带 `has_descriptor / mod_name / deps / replace_count`
