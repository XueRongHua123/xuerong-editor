## 雪绒的钢铁雄心编辑器 v1.12.0

地形能改了。选中一个省，下拉选新地形，点应用——definition.csv 和 terrain.bmp 一起写，图层自动重建。

### 为什么不能只改 definition.csv

HOI4 读地形看的是 `terrain.bmp`（像素级索引图），`definition.csv` 的第 7 列只是元数据。

只改 csv，游戏里地形不会变。

所以改一个省要同时做两件事：

```
1. definition.csv 第 7 列 → 地形名
2. terrain.bmp 里该省所有像素的索引 → 新类型对应的索引
```

京都燃烧实测：省 17318，plains → forest，**3784 个像素**改成索引 1，csv 与 bmp 的 md5 都变了。

### 一个格式坑

`terrain.bmp` 是 **8 位索引图**（bpp = 8），不是 24 位 RGB。

原来的 `bmp_write_rect` 只处理 24 位，写进去会把 P 模式 bmp 改成 RGB，HOI4 就读不出来了。

新增 `bmp_write_rect_8`：按行 seek 写单字节，保留原调色板与文件头。

### 同源保护

`terrain.bmp` 和 `provinces.bmp` 必须来自同一层。

muvluvCN 换了地图但没换地形图（地形图用的还是原版的），这种情况下改地形会错位，所以直接拒绝：

```
terrain.bmp 与 provinces.bmp 不同源（mod 换了地图没换地形图），改地形会错位
```

这条保护不是保守，是必要——错位的地形比不改更糟。

### 界面

右侧「编辑」页选中省后：

```
地形         plains
改地形
[forest (1020)]  [应用]
```

下拉里列出所有可写类型及当前使用数量（数据来自 `common/terrain/*.txt`）。

应用后自动重建图层并强制重载图片（src 相同浏览器会用缓存，必须先清空）。

### 交付

- 改地形：单省，写 csv + bmp
- 类型列表：`/api/terrain_types`
- 写入：`POST /api/terrain_set`

### 待做

- 批量改（框选多个省一次改）
- 按地形批量选省（「把所有 forest 改成 hills」）
- 画笔式刷地形（逐像素级）
