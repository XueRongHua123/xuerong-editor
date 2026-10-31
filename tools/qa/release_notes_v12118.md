## 雪绒的钢铁雄心编辑器 v1.21.18

人物编辑（`common/characters`）。第三层第一项。

### 数据形态

```hoi4
characters = {
	AFR_units_leader_1 = {
		name = "易卜拉欣·杜鲁"
		portraits = {
			army = {
				large = GFX_易卜拉欣杜鲁头像
				small = "gfx/leaders/AFR/易卜拉欣杜鲁小图.dds"
			}
		}
		field_marshal = {
			traits = { desert_fox  war_hero  … }
			skill = 7
			attack_skill = 6
			defense_skill = 6
			planning_skill = 6
			logistics_skill = 4
		}
	}
}
```

muvluvCN：**10 个文件、649 个人物**。

四种类型：`field_marshal` / `corps_commander` / `country_leader` / `operative`
（界面额外认 `advisor` / `scientist`）。

### 新增接口

```
POST /api/characters        {}                       全部人物
POST /api/character_set     {id, fields}             改名字/技能
POST /api/character_delete  {id}                     删人物
```

`fields` 支持 `name` / `skill` / `attack_skill` / `defense_skill` / `planning_skill` / `logistics_skill`。

### 实测

```
共 649 个人物
  AFR_units_leader_1  field_marshal    易卜拉欣·杜鲁  技能 7
  AFR_units_leader_2  corps_commander  梅尔维纳·阿德巴尼  技能 5
  CHI_Cuiyifei        field_marshal    崔亦菲  技能 7

改 skill 7→9、attack_skill 6→8 → 读回一致
改 name → 测试将军
删 AFR_units_leader_3 → 649→648
CN 未被改动
```

### 一个行为差异

`common/characters` 在 muvluvCN 里**没有被 replace_path 接管**，
所以「未接管也能改」——写进自己的 mod 就生效，和 `common/bookmarks` 一样，
不像 `history/units` 那样必须先接管。

### 界面

「编辑」tab → 人物：

```
[载入] [过滤 id/名字____]

共 649 个人物
  易卜拉欣·杜鲁  field_marshal   7   [删]
  梅尔维纳·阿德巴尼  corps_commander  5   [删]
  …

编辑选中
[名字____] [技能]
[攻击] [防御] [计划] [后勤] [保存]
```

点一行填充编辑框。

### 修了一个检查条件

第一版用 `if 'chPanel' in s` 判断是否已注入，结果**误匹配 `ctechPanel`**，
导致补丁以为自己已经跑过、直接跳过，HTML 和 JS 都没进去。
改成 `if 'id="chPanel"' in s`。

### 回归

```
写接口  10/10
```
