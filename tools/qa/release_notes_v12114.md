## 雪绒的钢铁雄心编辑器 v1.21.14

开局政治与外交（`set_politics` / `set_popularities` / `declare_war_on`）。

### 先说数据情况

原计划只做外交，查了 muvluvCN：

```
declare_war_on     2 处（只有 BET 和 H00 用）
puppet             0
add_relation       0
set_autonomy       0
set_politics      41 处（每个国家都有）
```

**外交字段 CN 几乎不用，但 `set_politics` 每个国家都有**，所以政治和外交一起做了。

### 数据形态

```hoi4
set_politics = {
	ruling_party = democratic
	last_election = "1933.5.17"
	election_frequency = 60
	elections_allowed = yes
}

set_popularities = {
	democratic = 75
	fascism = 20
	communism = 5
}

declare_war_on = {
	target = UNI
	type = beta_wargoal_focus
}
```

### 新增接口

```
POST /api/politics             {tag}
POST /api/politics_save        {tag, fields:{ruling_party, elections_allowed, ...}}
POST /api/popularities_save    {tag, pops:{democratic, fascism, communism, neutrality}}
POST /api/war_add              {tag, target, type}
POST /api/war_delete           {tag, index}
```

### 实测

```
AFR 读取：democratic / 1933.5.17 / 60 / yes
          支持率 {democratic:75, fascism:20, communism:5}
BET 读取：fascism / 1936.1.1 / 48 / no
          支持率 {fascism:100}
          战争 [{target:UNI, type:beta_wargoal_focus}]

改执政党 communism + 选举 no → 生效
改支持率 {communism:60, democratic:30, fascism:10} → 读回一致
加宣战 BET→CHI annex → 两条
删宣战 → 剩原来那条
未接管 → 被 replace_path 独占，拒绝写入
CN 未被改动
```

### 修了一个拼接错误

`popularities_save` 第一版写的是：

```python
new_text = raw[:b - 1] + body + "
	" + raw[b - 1:]
```

`b` 是 `}` 的位置，`b-1` 是块体最后一位——这等于**把新内容插在旧内容后面**，
旧的支持率一行没删，读回来还是原值。改成替换整段块体 `raw[a+1:b-1]` 才对。

### 界面

「编辑」tab → 开局政治与外交：

```
[TAG] [载入]

执政党 [communism ▾] [选举 no ▾] [保存]

支持率（四党）
[民主] [法西] [共产] [中立] [存]

宣战
  UNI  beta_wargoal_focus        [删]
[目标 TAG] [annex] [加]
```

### 回归

```
写接口  10/10
```

### 还没做

- 附庸 / 自治度（`set_autonomy`，CN 里 0 处，但要支持别的 mod）
- 国家关系（`add_relation`）
- 已做的是「有则改之、无则新建」：文件里没有 `set_politics` 时会补一个
