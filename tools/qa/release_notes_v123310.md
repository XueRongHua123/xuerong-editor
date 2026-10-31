## 雪绒的钢铁雄心编辑器 v1.23.31

修决议深度 + 接国家精神，误报率降到 0.002%。

### 一、决议那句 144 条误报

上一版遗留 144 条，全是 `SOV_military_offensive = {` 这种类别名被判成字段。

跟踪 depth 才看清结构：

```
类别 = {                         depth 1
	决议id = {                    depth 2  ← 我查的是这层
		字段 = 值                 depth 3  ← 字段其实在这层
	}
}
```

按 `depth == 2` 查查的是**决议 id**。改成 `depth == 3` 之后那 144 条直接消失。

### 二、接国家精神

`common/ideas/*.txt`，结构是 `ideas = { country = { 精神 = { 字段 } } }`，
字段在 `depth == 3`。

### 三、误报从 0.58% 降到 0.002%

接入 `ideas` 后第一次跑：**3740 条 / 650351 行 = 0.5751%**。报的全是 trigger/effect。

| 轮次 | 处理 | 误报率 |
|---|---|---|
| 初版 | — | 0.5751% |
| 加 trigger/effect 表 | 从 `.cwt` 的 `alias[trigger:xxx]` 提取 1140 个名字 | 0.1415% |
| 加作用域词 | `ROOT`/`FROM`/`PREV`/`OWNER` 等 | — |
| 加脚本化识别 | 大写 tag 前缀、`_trigger`/`_effect` 收尾 | 0.0109% |
| 修长度下限 | `ENG` 这种三字母 tag 被 `< 4` 挡住了 | **0.00215%** |

最终 **14 条 / 650351 行**。

### 四、那张 trigger/effect 表怎么来的

`.cwt` 里 trigger 和 effect 不用块定义，是：

```
alias[trigger:if] = { ... }
alias[effect:add_war_support] = int
```

所以多扫一遍 `alias[(trigger|effect):名字]`，从 111 个 `.cwt` 里提出 **1140 个**。

有了这张表，检查字段时就能放过 `AND`、`NOT`、`hidden_effect`、`if` 这些关键字。

### 五、剩下的 14 条

```
communism > 0.5                    比较表达式，不是字段赋值
is_raj_or_raj_inheritor = yes      mod 自己定义的 scripted_trigger，没 tag 前缀
```

第一种可以把 `>` `<` 的比较排除掉；第二种没有命名特征可依，只能放过。

### 六、CWTools 覆盖

```
v1.23.28   2 个块
v1.23.29   3 个块（+ character）
v1.23.30   4 个块（+ decision）
v1.23.31   5 个块（+ idea）
```

### 回归

```
写接口      10/10
黄金测试      9/9
生成流程    15/15
误报率     0.00215%（原版 65 万行，人物+决议+精神）
```
