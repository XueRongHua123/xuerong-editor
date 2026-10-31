## 雪绒的钢铁雄心编辑器 v1.23.4

修好了 `terrain_map` 来源的河流提取。现在只给一张真实地图图片，河道能被自动识别。

### 上一版的状态

`thin_water` 写好了但只返回 2 个像素。当时的记录是「原因未查明，留到下一版」。

### 查明：不是距离变换的错

单独测 `thin_water` 是**完全正常**的：

```
water.sum():            628
dist 分布:              1..6（海是同心层，河是 1）
thin_water(max_width=3): 387 像素  ✓
thin_water(max_width=2): 267 像素  ✓
```

距离矩阵也是对的——海逐层递增，河恒定为 1。

### 真正的原因在去噪

`from_terrain_map` 的流程是：

```
water → thin_water → rivers          （河道提取）
water → 邻居投票去噪 → land          （海陆判定）
land → Voronoi → labels
rivers & (labels > 0)                （只留陆地上的河）
```

**邻居投票对 2 像素宽的河不起作用**：

河中间像素的 4 个邻居是「左右陆地 + 上下河水」，`nb = 2`。
判定条件是 `nb >= 3 → 陆地`、`nb <= 1 → 水`，`nb == 2` 落在中间，
**原值保持不变**——河道像素仍然是「水」。

于是 `labels == 0`（不是陆地），最后那句 `rivers & (labels > 0)` 把 2096 个河道像素全清掉，
只剩 2 个边缘像素。

实测：

```
thin_water 后:              2098
rivers0 & (labels>0):          2   ← 全被清
rivers0 落在 labels==0 上的: 2096
```

### 修法

**先把河道从水里摘出来，再判海陆**：

```python
water = is_blue | deep
rivers = thin_water(water, max_width=3)
land = ~(water & ~rivers)      # 河道不再算水，算陆地
```

这样河道像素参与 Voronoi，`labels > 0`，最后不会被清掉。

### 实测

```
rmask.sum():          2098
rmask & (labels>0):   2098   ← 全部保留

rivers.bmp:
   [254] (122,122,122) 47700   ← 陆
   [255] (255,255,255) 10202   ← 海
   [  3] (  0,225,255)  2098   ← 河
```

### 已知偏差

`max_width=3` 会把海岸线最外 1-2 层也算成河（那些像素距离陆地也 ≤ 3）。
表现为沿海有一圈细蓝边，不影响游戏——HOI4 里那种地方本来也是水陆边界。

想更干净可以把 `max_width` 调到 2，但更细的河（1 像素宽）就会漏。

### 现在两条路径都能出河

```
geojson 来源 + rivers.geojson   已知坐标，精确
terrain_map 来源                 从图片颜色识别，免数据
```

### 回归

```
写接口  10/10
```
