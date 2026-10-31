## 雪绒的钢铁雄心编辑器 v1.23.5

城市区域从 GeoJSON 生成。

### cities.bmp 到底存什么

原版 `map/cities.bmp` 的调色板和 `terrain.bmp` 完全一样，一开始以为它是地形副本。
读了 `map/cities.txt` 才明白：

```hoi4
types_source = "map/cities.bmp"
pixel_step_x = 2
pixel_step_y = 2

city_group = {
	color_index = 15
	density = 0.9
	building = { distance = 1  mesh = { "westerngfx_house_1_1" } }
	…
}
city_group = { color_index = 0 … }
city_group = { color_index = 1 … }
city_group = { color_index = 2 … }
```

四个组，四套建筑模型，用 `color_index` 指到 `cities.bmp` 的调色板索引。

对应原版像素量：

```
[15] 9,597,334
[ 0] 1,587,984
[ 2]   249,896
[ 1]    99,116
```

**15 是「无城市」**（海和空地都是它），**0 / 1 / 2 才是城市**，不同风格。

### 接口

```
POST /api/map_generate
  source:      "geojson"
  src_path:    "boundaries.geojson"
  cities_path: "cities.geojson"     城市点（可选）
  city_radius: 4                    每个点周围的建筑半径
```

城市 GeoJSON 用 `Point` / `MultiPoint`：

```json
{"type":"Feature","properties":{"name":"北京"},
 "geometry":{"type":"Point","coordinates":[116.4,39.9]}}
```

### 生成方式

`cities.bmp` 不是「点」，是「区域」——每个像素代表一块建筑。所以：

1. 城市点按 bbox 投影
2. 每点周围撒半径 `city_radius` 的圆
3. 圆内按 0.85 的密度随机填充（避免死板的正圆）
4. 落在陆地上的城市像素写索引 0，其余写 15

### 修了一个索引撞车

第一版把海和城市都写成 15，输出里只剩两种索引且分不开：

```
cities.bmp:
   [  0] 59703
   [ 15]   297     ← 城市？还是海？分不出来
```

改成 15 = 无城市、0 = 城市之后：

```
cities.bmp:
   [ 15] (  8,31,130) 59703   ← 无城市
   [  0] ( 86,124, 27)   297   ← 城市
```

### 界面

「编辑」tab → 生成地图：

```
[GeoJSON 行政区划（最准）▾]
[源文件路径（程序化可空）]
[河流 geojson（可选）]
[城市点 geojson（可选）]
[300] [200] [60] [7]
```

### 还没做

- 城市风格分组（现在统一用索引 0，西方建筑）
- 城市密度分级（大城/小城）
- 从地图图片识别城市（现在只能用 GeoJSON）

### 回归

```
写接口  10/10
```
