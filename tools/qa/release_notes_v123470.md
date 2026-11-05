# 雪绒的钢铁雄心编辑器 v1.23.47

## 这一版修的是「地图生成了但格式不对」

上一版的地图生成会产出两张坏图：

- `terrain.bmp` 整张写成索引 0（= 平原）—— 引擎看到的是一张没有海的陆地
- `rivers.bmp` 整张写成 254（= 海）—— 引擎看到的是一张全是海的图

根因是**生成器代码改对了，但部署的产物还是旧的**。`write_terrain` / `write_rivers` 早就有 `sea_mask` 参数，海写索引 15、河流 255=陆 / 254=海，逻辑是对的；但 mod 目录里那两个 .bmp 没有重新生成。

修法是从 `provinces.bmp` + `definition.csv` 重建省标签和海陆掩码，重新生成这两张图：

```
terrain.bmp  {0: 453046, 15: 71242}      陆=平原 海=索引15
rivers.bmp   {255: 453046, 254: 71242}   255=陆 254=海
```

## 体检结果

`map_diag.py` 从 **14 PASS / 2 FAIL** 变成 **16 PASS / 0 FAIL**：

```
[PASS] provinces.bmp 尺寸与 definition.csv 一致
[PASS] definition.csv 列数正确
[PASS] terrain.bmp 海是索引 15        ← 本版修好
[PASS] rivers.bmp 海陆方向正确         ← 本版修好
[PASS] cities.bmp 以 15（无城市）为主
[PASS] heightmap.bmp 海低陆高
[PASS] world_normal.bmp 尺寸是 provinces 的一半
[PASS] trees.bmp 宽高比与 provinces 一致
[PASS] strategicregions 覆盖全部陆省
[PASS] supplyareas 州号都存在
[PASS] supply_nodes.txt 格式正确
[PASS] continent.txt 无空洲
[PASS] default.map 引用的文件都存在
[PASS] adjacencies.csv 表头正确
[PASS] unitstacks.txt 引用的省都存在
[PASS] buildings.txt 引用的省都存在

合计：FAIL 0 / WARN 0 / PASS 16
结论：可以进游戏
```

## 地图尺寸不是崩溃原因（第七轮结论）

之前怀疑「1024×512 太小」，把同一张图放大到多个尺寸重测：

| 尺寸 | 像素 | 结果 |
|---|---|---|
| 1024×512 | 52 万 | 崩溃 `+11816992` |
| 2048×1024 | 210 万 | 崩溃 `+11816992` |
| 4096×2048 | 840 万（原版 73%） | 崩溃 `+11816992` |
| 5120×2560 | 1310 万（超过原版） | 加载期崩溃 `+9038208` |
| 512×256 | 13 万 | 卡住，不崩溃 |

**尺寸排除了**。5 倍那组是另一类崩溃（像素量超过原版才出现），原版 1150 万、ES 1297 万都在那条线以下。0.5 倍那组缩小后丢了 25 个省的像素，不是干净实验。

## 已知限制

**地图生成出来仍然进不去游戏。** 格式全部合规了，但点「开始」后引擎内部崩溃（`PHYSFS_swapULE64 + 11816992`），七轮排查已排除十余个假设，尚未定位。

按当前定义的目标（**生成格式正确、不因地图格式报错的地图**），本版已达标。能正常游玩是另一层问题，不在本版范围。

「造一个新世界」在界面上标注为**实验性**。

## 其他

- `DEV_LESSONS.md` 新增一条：改生成器代码之后必须重新生成产物并跑 `map_diag` 核对，只看代码 diff 会以为修好了
