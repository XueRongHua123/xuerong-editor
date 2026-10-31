## 雪绒的钢铁雄心编辑器 v1.23.3

河流从 GeoJSON 生成。

### 输入

```json
{
  "type": "FeatureCollection",
  "features": [
    {"type": "Feature", "properties": {"name": "长江"},
     "geometry": {"type": "LineString", "coordinates": [[116,30],[117,30.5],[118,31]]}},
    {"type": "Feature", "properties": {},
     "geometry": {"type": "MultiLineString", "coordinates": [[...], [...]]}}
  ]
}
```

`LineString` / `MultiLineString` 都认，也兼容用细长 `Polygon` 当河的写法。

### 接口

```
POST /api/map_generate
  source:      "geojson"
  src_path:    "boundaries.geojson"     行政区划
  rivers_path: "rivers.geojson"         河流（可选）
  bbox:        [lon1, lat1, lon2, lat2]  可选，两套数据共用
```

### 关键：两套数据必须共用 bbox

上一版实现里，行政区划和河流**各自算自己的 bbox**——河流的坐标范围通常比
行政区划小很多，两边一除，河道就会整个偏到角上，和陆地对不上。

现在 `mapgen.generate` 先算好行政区划的 bbox 并复用给 `rivers_from_geojson`，
除非调用方显式传 `bbox`。

### 修了一个函数只认多边形

`geojson_bbox` 原来只遍历 `Polygon` 的环，`LineString` 返回空，导致单独传河流文件时
bbox 算出来是 `None`，直接放弃。

改成同时收多边形环和线段点。顺手把 `_iter_lines` 挪到了 `geojson_bbox` 前面（它要先定义）。

### 实测

行政区划两个矩形（0..20 经度，0..20 纬度），河流两条竖线：

```
读矢量行政区划 adm.geojson…
  得到 2 个省（真实行政区划）
读河流线 riv.geojson…
  河道 400 像素
rivers.bmp:
   [254] (122,122,122) 59600   ← 陆
   [  3] (  0,225,255) 400     ← 河
```

河道像素数 = 200 行的 2 条竖线，符合预期。

### 界面

「编辑」tab → 生成地图，源路径下面多一行：

```
[源文件路径（程序化可空）]
[河流 geojson（可选）]
```

只对 `geojson` 来源生效。

### 还没做

- 河流粗细分级（主流/支流/小溪现在统一用索引 3）
- 城市点位
- 从地图图片自动提取河流（三个方案都没通，见上一版说明）

### 回归

```
写接口  10/10
```
