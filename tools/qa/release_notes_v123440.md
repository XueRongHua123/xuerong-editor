## 雪绒的钢铁雄心编辑器 v1.23.44

### 修了三个地图生成的 bug

这三个 bug 是同一族：`mapgen` 里有一批写法是 `arr[labels == 0] = 海底的东西`，但我们的海是**真省**（id 从 n+1 开始），`labels` 里根本没有 0。这句永远不执行，整张图停在「陆地的默认值」上。

**一、`rivers.bmp` 整张图被标成「海」**

```python
RIVER_LAND = 254      # 旧
RIVER_SEA  = 255      # 旧
arr = np.full(..., RIVER_LAND)
arr[labels == 0] = RIVER_SEA     # 永不成立
```

按省份类型做面积统计（原版 + East Showdown 双向验证）确认：**255 = 陆，254 = 海**，旧代码写反了。结果整张 1024×512 全涂成 254，引擎眼里全图都是海。

现在改成 `RIVER_LAND = 255` / `RIVER_SEA = 254`，并新增 `sea_mask` 参数，由 `mapgen.generate` 传 `~land`。

**二、`cities.bmp` 整张图 52 万像素全是「有城市」**

旧代码全填 `TERRAIN_PLAINS`（索引 0），而 **0 在这张图里是 `CITY_FOREIGN = 有城市`**，15 才是「无城市」。原版 86% 是 15，ES 是 100% 的 15。

现在改成「没有城市掩码就整张 15」。

**三、`supply_nodes.txt` 第一列写成了州号**

第一列是**节点等级**（原版 727 行全是 1，ES 1822 行也全是 1），我们写成了 1/2/3/4。现在恒为 1。

### 地图体检器新增 4 条检查

`qa/map_diag.py` 从 12 项扩到 16 项，新加的四条都是 FAIL 级：

```
rivers.bmp 海陆方向             陆地 255 占比 / 海洋 254 占比
terrain.bmp 海是索引 15          海省里 15 的占比
cities.bmp 以 15（无城市）为主    15 的占比
supply_nodes.txt 格式            第一列是否恒为 1
```

编辑器的诊断面板会自动带上这四条（`_diag_map_format` 直接 import `map_diag`，改一处两边都变）。

对修前/修后的图跑，结果对比：

```
=== 修前 ===
FAIL  rivers.bmp 海陆方向反了 — 陆地像素里 255 只占 0%，海洋像素里 254 只占 100%
FAIL  cities.bmp 大部分不是 15（无城市）— 15 只占 0%
FAIL  supply_nodes.txt 第一列不是恒为 1 — 前几个：[['2','6'], ['3','11'], ['4','16']]
合计：FAIL 3 / PASS 13   结论：会被 MAP_ERROR 拦住

=== 修后 ===
PASS  rivers.bmp 方向正确 — 陆地 255 占 100% / 海洋 254 占 100%
PASS  terrain.bmp 海是索引 15 — 占 100%
PASS  cities.bmp 以 15（无城市）为主 — 占 100%
PASS  supply_nodes.txt 格式正确 — 4 行
合计：FAIL 0 / PASS 16    结论：可以进游戏
```

### 生成的世界现在长这样

```
20 个陆省 + 48 个省（512×512）
rivers.bmp   陆地 255 / 海洋 254，方向正确
terrain.bmp  陆 0（plains）/ 海 15（ocean）
cities.bmp   全 15（无城市）
supply_nodes 4 行，等级恒为 1
```

### 已知限制

**新地图仍然进不了游戏**（点「开始」后崩在初始化阶段），这个版本的改动修的是格式层的问题，不是崩溃本身。崩溃的排查还在进行，目前已经排除：省边界形状（用规整棋盘验证过）、地形、河流、高度图、城市、补给、铁路、邻接规则、国策树、军队、事件、剧本字段、364 个原版 tag 的历史。

「造一个新世界」这个功能目前仍是实验性的，界面上有标注。

### 验证

- `qa/_check_world_stubs.py`：30 过 / 0 挂
- `qa/map_diag.py`：16 PASS / 0 FAIL
- `qa/regress_all.py`：15 个真实 mod，180/180
- `world_create` 完整跑通，无失败步骤
