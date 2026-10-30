## 雪绒的钢铁雄心编辑器 v1.20.5

**按 replace_path 计算真实写入目标**。改这些目录的改动才会真的生效。

### 问题

HOI4 的 `replace_path` 是**独占**的：某个 mod 声明后，该目录只从这个 mod 读，
**其他 mod（含后加载的）在这一目录下的文件全部被忽略**。

muvluvCN 系实测：

```
CN（2800380626）声明了 21 项
  events / common/ideas / common/national_focus / common/technologies
  common/country_tags / map/strategicregions / history/states / history/countries ……

CNsub（2989050816）声明了 26 项
  history/states / history/countries / common/units/equipment
  common/characters / common/scripted_effects / common/units ……
```

同一目录被两层都声明时，**后加载的赢**。

真机实测：在测试 mod 里把州 1 的 `name` 改成 `ZZTEST_NAME`，
加载顺序确认它在最后，进游戏州名仍是「科西嘉」——**文件根本没被读取**。

### 修法

新增三个函数：

```python
_replace_owner(mod_root, sub)   # 该目录被哪一层的 replace_path 独占
write_base(mod_root, sub)       # 真正的写入层：被独占写那一层，否则写链顶
write_note(mod_root, sub)       # 给人看的一句话说明
```

接入三处写操作：

| 函数 | 目录 | 之前 | 现在 |
|---|---|---|---|
| `state_save` | history/states | 写链顶 | 写 replace_path 层 |
| `_sr_write_dir` | map/strategicregions | 写链顶 | 写 replace_path 层 |
| `_supply_dir_write` | map/supplyareas | 写链顶 | 写 replace_path 层 |

### 新增诊断接口

```
GET /api/write_targets
```

返回每类资源的真实写入层。muvluvCN 系实测：

```
共 10 类，9 类被 replace_path 接管
  history/states           2989050816   独占
  history/countries        2989050816   独占
  map/strategicregions     2800380626   独占
  map/supplyareas          2989050816   可写
  common/ideas             2800380626   独占
  common/national_focus    2800380626   独占
  common/technologies      2800380626   独占
  common/units/equipment   2989050816   独占
  common/units             2989050816   独占
  events                   2800380626   独占
```

### 这意味着什么

改 `history/states` → 落到 CNsub，**生效**。
改 `map/strategicregions` / `common/ideas` / `common/technologies` → 落到 **CN 本身**，也**生效**，
但改的是 CN 的文件。

要在自己的 mod 里改这些目录而不动 CN，唯一办法是**自己的 mod 也声明
`replace_path` 并全量拷贝该目录**——这是 HOI4 的机制，不是编辑器能绕过的。

### 回归

```
写接口  10/10
```
