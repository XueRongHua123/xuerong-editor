## 雪绒的钢铁雄心编辑器 v0.75.0

地图层 2 第一项：**政治视图**——按国家给地图上色。

### 效果

![政治视图](https://github.com/XueRongHua123/xuerong-editor/raw/main/docs/shots/political.png)

图层面板勾上「政治（按国家）」后：

- 每个省按所属国家的 `color` 上色（国家中心里解析的那份颜色）
- 国家边界自动压深 55% 描边，一眼能看出国界
- 无主省 / 无州省统一深灰，海洋保持底图
- 勾选时自动隐藏省色块，避免两层打架

### 数据链路

`provinces.bmp` 颜色 → 省 id → `history/states/*.txt` 的 `owner` → `common/countries/*.txt` 的 `color`

### 代价

- 构建时间 16.7 → **17.4 秒**（多一层 + 一次 4 邻域 owner 比较）
- 缓存多一个 `political.png`，**0.24 MB**（纯色块压缩率极高）

### 验证

- `qa/probe_v075.mjs`：层加载 5632px、勾选后 `provDisplay:none` 且政治层 opacity 0.85、
  取消后政治层隐藏且省色块恢复，0 报错
- 视觉巡检 27 状态 × 双主题 × 两档视口全绿
