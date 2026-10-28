## 雪绒的钢铁雄心编辑器 v1.0.8

**支持启动器的多 mod playset**，并用「muv 京都燃烧」这个 4 层叠加的 playset 实测通过。

### 之前的问题

编辑器只认单个 mod：`--mod` 传一个，然后沿 `descriptor.mod` 的 `dependencies` 往上找父 mod。

但启动器里的 playset 是**手动排序的多 mod 叠加**，很多 mod 根本不写 `dependencies`——
这条路走不通。

### 现在

`--mod` 可以传多次，按**启动器里的加载顺序**依次叠加（后面的覆盖前面的）：

```
python focus_editor.py --mod <mod1> --mod <mod2> --mod <mod3> --mod <mod4>
```

叠加链 = 原版 + 传入的所有 mod，保留顺序。多个 mod 都存在时优先用 playset 顺序，
只有单个 mod 时才回退到 `dependencies` 自动找父。

### 实测「muv 京都燃烧」（4 个 mod，合计 2.6 GB）

| # | mod | 大小 | 自带地图 | replace_path |
|---|---|---|---|---|
| 1 | JLm Fonts | 419 MB | 否 | 0 |
| 2 | Additional Japanese map fonts | 75 MB | 否 | 0 |
| 3 | **Muvluv 1998 JAPAN シナリオ** | **1.84 GB** | **是（36 MB）** | 21 |
| 4 | Muvluv 1998 JAPAN シナリオ CN | 294 MB | 否 | 15（依赖 3） |

叠加结果：

```
1. Hearts of Iron IV
2. JLm Fonts
3. Additional Japanese map fonts
4. Muvluv 1998 JAPAN シナリオ        ← 地图（replace_path 21）
5. Muvluv 1998 JAPAN シナリオ CN      replace_path 15 · 依赖 Muvluv 1998 JAPAN シナリオ
```

### 地图读取结果：全部正确

| 检查项 | 结果 |
|---|---|
| 地图尺寸 | **3072 × 4096（竖版）** —— 这个 mod 真的重做了地图，不是标准的 5632×2048 |
| 省份数 | 17324 |
| `definition.csv` 与 `provinces.bmp` | csv 17325 / bmp 17324，幽灵 1（省 0），**未定义像素 0，同色省 0 组** |
| 开局面 | 1998.7.11（从该 mod 的 bookmark 读出） |
| 构建耗时 | 45.4 秒（比 5632×2048 的 36 秒慢，像素总数 1258 万） |
| 渲染 | 日本列岛、朝鲜半岛、中国东部地形正确，海洋深蓝，森林绿，平原棕 |

截图里能看到完整的日本列岛轮廓——竖版地图、1.7 万省、5 层叠加，全部正常。

### 顺带改的默认视图

这个 mod 有 17324 个省，缩到 17% 时「省色块」就是一片彩色噪点（每省一色，太多太小）。

现在：**省数超过 8000 时，默认开「地形」而不是「省色块」**，并在状态栏提示怎么切回去。

### 一个仍然存在的限制

编辑器现在需要命令行传 4 个 `--mod`。启动器里的 playset 顺序，用户得手动对应。

下一步可以在界面上加「playset 编辑器」：让用户按顺序添加 mod 文件夹，不用敲命令行。
