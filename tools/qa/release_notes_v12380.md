## 雪绒的钢铁雄心编辑器 v1.23.8

人物与决议都能**新建**了。

### 之前只能改和删

人物面板能改名字和五项技能、能删，但造不出新人。
决议面板能改 cost / days_remove / priority、能删，但造不出新决议。

### 新增接口

```
POST /api/character_add   {id, name, type, skill, attack, defense, planning, logistics}
POST /api/decision_add    {id, category, icon, cost, effect, fire_only_once}
```

### 人物新建

生成的结构：

```hoi4
characters = {
	TEST_GENERAL = {
		name = "测试将军"
		field_marshal = {
			skill = 5
			attack_skill = 6
			defense_skill = 4
			planning_skill = 3
			logistics_skill = 2
		}
	}
}
```

- id 校验：字母开头，只允许字母数字下划线，重名拒绝
- 类型可选 `field_marshal` / `corps_commander` / `country_leader` / `operative`
- 五项技能必须 0-10 的整数
- 写进 `common/characters/zz_editor_characters.txt`

实测 649 → 650 个人物。

### 决议新建

生成的结构：

```hoi4
my_category = {
	my_test_decision = {
		icon = GFX_decision_generic
		cost = 30
		fire_only_once = yes
		available = {
			always = yes
		}
		complete_effect = {
			add_political_power = 80
		}
	}
}
```

- 类别已存在 → 插到那个类别的块尾（在它的 `}` 前，行首对齐）
- 类别不存在 → 新建类别
- `available` 固定 `always = yes`，`complete_effect` 接受任意脚本行
- 写进 `common/decisions/zz_editor_decisions.txt`（新类别）或已有类别的文件

实测 19 类别 240 条 → 20 类别 241 条。

### 界面

「人物」面板底部加：

```
新建人物
[id（英文）] [名字]
[corps_commander ▾] [3] [新建]
```

「决议」面板底部加：

```
新建决议
[决议 id] [类别 id]
[GFX_decision_generic] [50] [新建]
[add_political_power = 50]
```

最后一行是完成效果脚本，可以写多行。

### 还没做

- 人物头像（`portraits` 留空，游戏会用默认占位图）
- 决议的 `available` 条件（固定 `always = yes`，不能设条件）
- 决议的 `remove_effect` / `days_remove`（新建时不能设，建完再改）

### 回归

```
写接口  10/10
```
