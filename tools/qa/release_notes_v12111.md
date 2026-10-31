## 雪绒的钢铁雄心编辑器 v1.21.11

开局舰队（`history/units` 的 `fleet` 段）。

### 数据形态

三层嵌套，`ship` 是单行：

```hoi4
units = {
	fleet = {
		name = "第一舰队"
		naval_base = 12736
		task_force = {
			name = "第一炮击分队"
			location = 12736
			ship = { name = "墨西哥" definition = carrier ... }
		}
	}
}
```

### 新增接口

```
POST /api/navy                  {}            舰队 → 特遣队 → 舰船
POST /api/navy_delete_fleet     {fi}          删整支舰队
POST /api/navy_delete_tf        {fi, ti}      删某个特遣队
```

### 实测（muvluvCN）

```
30 支舰队，762 艘船
  第一舰队   基地 12736  1 队  1 艘
  北方舰队   基地 12674  2 队  17 艘
  第二舰队   基地 540    3 队  30 艘

删第 1 支 → 29 支舰队，761 艘船，第一支变成「北方舰队」
删特遣队 → 该舰队特遣队 2 → 1
```

### 一个数据现象

「北方舰队」在列表里出现两次，来自 `EEA_1999_navy.txt` 和 `EEA_1999_navy_legacy.txt`，
两个文件内容相同。这是 muvluvCN 自己留的 legacy 副本，不是解析重复。

### 修了一个偏移 bug

`find_blocks` 返回 `(start, end, body)`——`start` 是 `{` 的位置，`end` 是 `}` 的位置。
我解包时把 `end` 当成了 `{` 来用：

```python
for fpos, fb, fbody in find_blocks(ubody, "fleet"):   # fb 实际是 end
    fo_end = ub + 1 + brace_match(ubody, fb)          # 又算了一遍，全错
```

结果 `start=345 end=348`（只切 3 个字符），删舰队报「成功」但什么都没删掉。

改成直接用 `start` / `end`，不再重复算 `brace_match`：

```python
for fb, fend, fbody in find_blocks(ubody, "fleet"):
    fo = ub + 1 + _line
    fo_end = ub + 1 + fend + 1
```

### 界面

「编辑」tab → 开局舰队：

```
[载入舰队]

30 支舰队，762 艘船
▸ 第一舰队  基地 12736｜1 队｜1 艘        [删整支]
    第一炮击分队（1 艘）                  [删]
▸ 北方舰队  基地 12674｜2 队｜17 艘       [删整支]
```

### 还没做

- 加舰船 / 加特遣队 / 改舰船属性（`ship` 单行格式复杂，下版）
- 空军（`history/units` 里的 `air_wings`，这次没碰）

### 回归

```
写接口  10/10
```
