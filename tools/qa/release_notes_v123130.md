## 雪绒的钢铁雄心编辑器 v1.23.13

修 `bookmark_add` 的三个问题。这三个是真机验证暴露出来的：生成的文件格式没错，
但游戏里表现出来是错的。

### 1. 日期少一段，游戏把「日」当「时」解析

原来写 `date = 1936.1.1`，游戏显示成「14月,1939」。

HOI4 的剧本日期是**四段**：`年.月.日.小时`。只写三段时，解析器把第三段当小时，
日期整体错位。

改成自动补第四段：

```python
def _bookmark_date(date):
    parts = [p for p in date.split(".") if p != ""]
    if len(parts) == 3:
        parts.append("12")
    return ".".join(parts)
```

`1936.1.1` → `1936.1.1.12`。

### 2. 没有国家块，选国家界面是空的

生成的剧本只有：

```hoi4
XTT_VSTART = {
	name = "XTT_VSTART"
	date = 1936.1.1.12
	default_country = "GER"
}
```

游戏里点进去，选国家界面一片空白——**HOI4 只列剧本里写了 `"TAG" = {}` 的那些国家**，
`default_country` 只是「默认高亮哪个」，不代表「列表里有谁」。

新增 `countries` 参数（默认只放 default_country），每个国家生成一个块：

```hoi4
"GER" = {
	history = "GER_DESC"
	ideology = neutrality
	ideas = {
	}
	focuses = {
	}
}
```

同时补了 `default = yes`（标记这个是默认剧本）。

### 3. 没有本地化，界面显示的是 key

原来界面上直接显示 `XTT_VSTART` 这个 key。

新增 `_bookmark_loc()`，在 `localisation/zz_editor_bookmarks_l_english.yml` 里
生成 name / desc / 各国 `_DESC` 的条目。

### 实测

```
已新建剧本 XTT_VSTART（1936.1.1.12，3 个国家可选）

bookmarks = {
	bookmark = {
		name = "XTT_VSTART"
		desc = "XTT_VSTART"
		date = 1936.1.1.12
		picture = "GFX_select_date_1936"
		default_country = "GER"
		default = yes

		"GER" = {
			history = "GER_DESC"
			ideology = neutrality
			...
```

### 怎么发现的

在原版 HOI4 上装一个由编辑器生成的测试模组，一路点到「开始游戏 → 选择剧本 → 选择国家」，
看到日期显示「14月,1939」、国家列表空、名称是裸 key。

接口层测不出来——`bookmark_add` 一直返回 `ok: true`，文件也写对了位置，
只是内容不完整。

### 回归

```
写接口  10/10
```
