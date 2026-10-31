## 雪绒的钢铁雄心编辑器 v1.22.0

**地图从零生成**。四种来源，一次生成完整 map/ 目录。

### 四种来源

| 来源 | 用什么 | 适用 |
|---|---|---|
| **procedural** | 分形噪声造大陆 + Voronoi 切省 | 架空世界，不需要任何素材 |
| **lineart** | 黑白线稿 PNG（线条 = 省界） | 自己画的世界 |
| **mask** | 海陆掩码 PNG（黑海白陆） | 有海陆轮廓但没有省界 |
| **image** | 任意图片按色块切省 | 已有带区块的图 |

### 生成什么

一次产出 **24 项文件**，和原版 `map/` 完全对应：

```
provinces.bmp      24 位，每省唯一 RGB
definition.csv     0 是海，1..N 是省（land;plains;0;PROVn）
heightmap.bmp      海=0，陆=110±18 平滑噪声
world_normal.bmp   由高度图梯度算，半分辨率
terrain.bmp        全 0（默认地形）
rivers.bmp / cities.bmp / trees.bmp   全 0
default.map        max_provinces = N+1
continent.txt      1 个大洲
terrain/           从原版复制
adjacencies.csv / colors.txt / seasons.txt / …   从原版复制
railways / buildings / cities / supply_nodes / positions / unitstacks   空
strategicregions/  按省序每 60 个切一区
supplyareas/       按省序每 120 个切一区
mapgen.json        生成参数留档
```

### 核心算法

**连通分量**（`label_regions`）：两遍扫描 + 并查集，numpy 行内向量化。
`scipy` 不可用，自己实现的，600×240 的图 409ms 跑完。

**颜色分配**（`unique_colors`）：随机取 RGB，全局去重，排除灰度（避免和边界混淆）。

**程序化大陆**：5 层分形噪声 + 边缘衰减函数（避免大陆被裁成方块）。

**Voronoi 切省**：泊松盘撒种子点，分块算距离矩阵，只在陆地上编号。

### 实测

```
生成 600x240、60 个省 → 409ms
文件清单 24 项齐全
provinces.bmp      600x240 bpp=24  ✓
terrain.bmp        600x240 bpp=8   ✓
world_normal.bmp   300x120 bpp=24  ✓（半分辨率）
definition.csv     61 行（1 海 + 60 省）
default.map        max_provinces = 61
```

### 界面

「编辑」tab → 生成地图：

```
[程序化（分形大陆）▾]
[源文件路径（程序化可空）]
[600] [240] [60] [7]
[输出目录_______] [生成]
生成日志…
```

### 已知限制

- **尺寸**：默认 600×240 是小图，做正式 mod 建议 3000×1000 以上（生成时间会到几十秒）
- **省界形状**：Voronoi 切出来是直线多边形，不像真地图；`lineart` 和 `image` 两种源可以绕开
- **没有河、没有城市、没有树木**：这三张图都是全 0
- **战略区/补给区是按 id 顺序切的**，不是按地理位置聚类

### 还没做

- **从 GeoJSON 生成**（Natural Earth 的真实行政区划，最准）
- **断口检测**（线稿没闭合时会连成一片）
- **省大小均衡**（Voronoi 会产生大小悬殊的省）
- **河流/城市/树木的实际生成**

### 回归

```
写接口  10/10
```
