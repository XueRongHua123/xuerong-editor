## 雪绒的钢铁雄心编辑器 v1.23.16

人物、部队、空军现在会写到正确的国家文件里。

### 问题：写对了内容，写错了文件

原版 HOI4 靠**文件名**判断归属：

```
common/characters/GER.txt        → 里面的人物是德国的
history/units/AFG_1936.txt       → 里面的部队是阿富汗的
```

编辑器原来统一写通用文件：

```
common/characters/zz_editor_characters.txt
history/units/zz_units.txt
history/units/zz_air_wings.txt
```

这些文件没有任何国家信息，**游戏不知道里面的人物/部队属于谁**，结果就是：

- 德国陆军将领列表里找不到「测试将军」
- 地图上看不到「测试部队」
- 看不到「测试联队」

决议和州资源没受影响，因为 `common/decisions` 和 `history/states` 的归属不靠文件名。

### 改法

三个函数各加一个归属参数：

| 函数 | 新参数 | 写到 |
|---|---|---|
| `character_add` | `country` | `common/characters/<TAG>.txt` |
| `unit_add` | `tag` | `history/units/<TAG>_1936_zz.txt` |
| `air_wing_add` | 用已有的 `owner` | `history/units/<TAG>_1936_zz_air.txt` |

不给参数时退回原来的通用文件（保持兼容）。

### 实测

```
人物: 已新建人物「测试将军」（XTT_Gen，field_marshal）
部队: 已在省 1 布置 1 支 XTT_TestTpl
空军: 已在省 1 加联队「测试联队」（fighter_equipment_1 ×10，owner GER）

生成的文件：
  common/characters/GER.txt           ← 归德国
  history/units/GER_1936_zz.txt       ← 归德国
  history/units/GER_1936_zz_air.txt   ← 归德国
```

### 怎么发现的

在游戏里选德国进游戏，将领列表没有「测试将军」，地图上也看不到部队和联队。
但决议在、科西嘉的石油也在。

这个对比本身就是线索：**决议和州不用文件名判断归属，人物和部队用**。

### 回归

```
写接口  10/10
```
