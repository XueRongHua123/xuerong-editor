## 雪绒的钢铁雄心编辑器 v1.23.25

按 `set_oob` 定位 OOB 文件，并修两处图标名。

### 一、history/units 不是扫描加载的

查了权威参考第 1.4 和 18.7 节：

> `replace_path = "history/units"` 毫无作用，因为 OOB 文件是通过 `oob = "TAG_1936"` 直接点名加载的。

> 文件名任意，但必须与加载处写的名字一致。

GER 实际点名：

```
set_oob        = "GER_1936" / "GER_1936_nsb"
set_air_oob    = "GER_1936_air_bba" / "GER_1936_air_legacy"
set_naval_oob  = "GER_1936_naval" / "GER_1936_naval_mtg"
```

之前自己起名 `GER_1936_zz.txt`、`GER_1936_zz_air.txt` 写进去，游戏根本不读——这就是部队和空军看不到的真正原因。v1.23.23 加国家前缀是方向错了，前缀不影响加载，**点名才影响**。

新增 `_oob_files(root, tag, kind)`：读国家历史，把点名的 OOB 名字捞出来。只保留和第一条同年份的（`GER_1936` 和 `GER_1936_nsb` 是一组 DLC 分支，`GER_1939` 属于 1939 剧本，改了没意义还会污染）。

`unit_add` 和 `air_wing_add` 改成写点名文件，并且**对每个 DLC 分支都写一份**（有 NSB 走 `_nsb`，没有走基础版，只写一个换 DLC 就丢）。

### 二、写点名文件时的覆盖问题

`GER_1936.txt` 和原版同名，直接写会把原版 30 支部队全覆盖掉（第一次测试剩 190 字节）。

和 `character_add` 是同一个坑：**写同名文件前先复制原版**。

实测：

```
原版 GER_1936.txt      9486 字节, 30 支队伍
生成后                 9661 字节, 31 支队伍     ← 30 + 新增 1
原版 GER_1936_air_bba  3899 字节
生成后                 3992 字节               ← +93 字节
```

### 三、两处图标名不存在

```
GFX_decision_generic  → 不存在（决议默认图标）
GFX_idea_generic      → 不存在（精神默认图标）
```

改成验证过存在的：

```
decision_add   默认 icon  → GFX_decision_category_generic
idea_add       默认 picture → GFX_idea_generic_army_war_college
```

（决议图标的命名空间在原版里比较乱：`icon = aluminium` 会补成 `GFX_decision_aluminium`，
`icon = decision_generic_agriculture` 补出来是 `GFX_decision_decision_generic_agriculture`——
后者原版自己也没有对应 sprite。所以不追求还原原版写法，用确认存在的名字。）

### 还没验证的

海军 `navy_add_ship` 用的是 `load_navy` 记录的 `file`，那本来就是点名文件，
但如果有 Man the Guns，实际生效的是 `GER_1936_naval_mtg` 而不是 `GER_1936_naval`，
现在只写前者。这个要进游戏确认。

### 回归

```
写接口  10/10
```
