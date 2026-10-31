## 雪绒的钢铁雄心编辑器 v1.21.19

决议编辑（`common/decisions`）。

### 数据形态

```hoi4
BETA_category = {                     ← 类别
	take_back_hive = {                ← 决议
		icon = generic_prepare_civil_war
		cost = 0
		fire_only_once = no
		days_remove = 14
		available = { … }             ← 脚本块，不动
		complete_effect = { … }       ← 脚本块，不动
		ai_will_do = { … }            ← 子块，不是决议
	}
}
```

muvluvCN：30 个文件，但**大部分决策被注释掉**，实际有效的是
**19 个类别、240 条决议**。

### 新增接口

```
POST /api/decisions        {}               类别 + 决议
POST /api/decision_set     {id, fields}     改标量字段
POST /api/decision_delete  {id}             删决议
```

`fields` 只接受标量白名单：`icon / priority / cost / fire_only_once / days_remove /
days_re_enable / days_mission_timeout / is_good` 等。
`available` / `visible` / `complete_effect` 这些脚本块**不碰**。

### 实测

```
接管 common/decisions（29 个文件）
take_back_hive 原 {cost: 0, days_remove: 14}
改 → {cost: 25, days_remove: 7} 读回一致
删 → 240 → 239
```

### 修了一个误判

第一版把 `ai_will_do` 当成独立决议，还让 `modifier = {` 的值取成了 `{`：

```
19 个类别，343 条决议      ← 多出 100 条假的
  ai_will_do  {'modifier': '{'}
```

加了两层过滤：

1. `DECISION_SKIP` 排除 `ai_will_do` / `modifier` / `available` / `visible` /
   `complete_effect` / `remove_effect` 等 16 个子块名
2. 字段取值时排除等于 `{` 的（说明是块不是标量）

修后：**240 条**，干净。

### 界面

「编辑」tab → 决议：

```
[载入] [过滤 id/类别____]

19 个类别，240 条决议
  take_back_hive  BETA_category        [删]
  Replenish_energy  BETA_category      [删]
  …

编辑选中
[cost] [days_remove] [priority] [保存]
```

### 还没做

- **新建决议**（要写 `available` / `complete_effect` 脚本效果，复杂度高）
- 改 `icon` 之外的文本（那要动本地化）

### 回归

```
写接口  10/10
```
