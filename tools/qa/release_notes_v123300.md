## 雪绒的钢铁雄心编辑器 v1.23.30

人物类型块内部字段 + 决议字段检查。

### 一、人物类型块内部

原来只查 `depth 2`（人物体直接子级），`corps_commander = { skill = 5 }` 里的字段
一个都不查。放宽到 `depth 2~3` 之后有个坑：

```
portraits = {          depth 2
	army = {           depth 3  ← army/large 不在 character 的字段表里
		large = GFX_x  depth 4
	}
}
```

`portraits` 用的是另一套字段（`army`/`navy`/`civilian`/`large`/`small`），
直接放宽会撞一片。所以单独给 `portraits` 一张表，并按块名判断当前在哪。

### 二、决议字段检查

`common/decisions/*.txt`，类别 id 在 `depth 1`、决议 id 在 `depth 2`、
字段在 `depth 3`… 实测结构是「类别 = { 决议 = { 字段 } }」，
所以查 `depth 2`。

### 三、降噪

第一次跑原版全量：**1680 条 / 498983 行 = 0.3367%**。主要是两类：

| 原因 | 例子 | 处理 |
|---|---|---|
| 规则漏项 | `legacy_id`（775 次）、`id`（586 次）、`targeted_modifier` | 加白名单 |
| 条件块内部 | `OR`、`has_government` 在 `allowed = { }` 里 | 整块跳过 |
| 前缀字段 | `war_with_on_remove` 一组 | 前缀白名单 |

加完降噪：

```
告警 144 | 误报率 0.0289%
```

### 四、已知遗留

剩下 144 条全是 `SOV_xxx = {` 这种类别名被判成 depth 2。原因是我在处理
空行和 `}` 之后块栈没对齐，类别被当成了决议体。

比例 0.03%（十万行三十条），先记着。

### 五、CWTools 覆盖

```
v1.23.28   2 个块（oob、bookmark）
v1.23.29   3 个块（+ character）
v1.23.30   4 个块（+ decision，character 扩展到类型块内部）
```

### 回归

```
写接口      10/10
黄金测试      9/9
生成流程    15/15
误报率     0.0289%（原版 49.9 万行）
```
