## 雪绒的钢铁雄心编辑器 v1.23.29

人物字段检查，误报率实测 0%。

### 怎么区分人物 id 和字段

上一版没接 `character`，因为人物 id 和字段混在同一层，不好分。看了真实数据才发现
结构其实很干净：

```
characters = {                 depth 0
	GER_adolf_hitler = {         depth 1  ← 人物 id
		name = GER_adolf_hitler   depth 2  ← 字段
		corps_commander = {       depth 2  ← 类型块
			skill = 5              depth 3  ← 类型块里的字段
		}
	}
}
```

**人物 id 一律在 depth 1，字段在 depth 2**。靠层级分就行，不用猜命名规律。

### 误报率实测

| 数据 | 规模 | 告警 | 误报率 |
|---|---|---|---|
| 原版全部人物文件 | 232 文件 / 165014 行 | 0 | **0.000%** |
| MUV-LUV（CN + CNsub） | 188 文件 / 6583 行 | 0 | **0.000%** |

两组都是零误报。原版那 16 万行里大写 id、小写 id、带数字 id、纯数字 id 都有，
说明层级判断是稳的。

### 能报出什么

```
characters = {
	ZZT_test = {
		namee = "拼错字段"        ← depth 2，报
		corps_commander = {
			skil = 4              ← depth 3，不报
		}
	}
}
```

第一条报出，第二条不报。

### 已知缺口

**类型块内部的字段不查**。`corps_commander`、`field_marshal`、`advisor`、
`country_leader` 这些块里的 `skill`、`attack_skill`、`ideology`、`idea_token`
拼错了现在发现不了。

原因：这些块里的字段需要单独一张表（类型块的 schema 和人物体的不一样），
规则文件里 `character` 那个块是合并写的，拆不干净。留到下一版。

### 回归

```
写接口      10/10
黄金测试      9/9
生成流程    15/15
```
