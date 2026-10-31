## 雪绒的钢铁雄心编辑器 v1.21.16

开局剧本（`common/bookmarks`）。

### 数据形态

```hoi4
bookmarks = {
	bookmark = {
		name = "1999_START_NAME"
		desc = "1999_START_DESC"
		date = 1999.8.7.1
		picture = "GFX_select_date_1939"
		default_country = "JAP"
		"CHI" = { history = "CHI_1999_DESC"  ideology = democratic }
		"USA" = { … }
	}
}
```

muvluvCN 有两个文件、共 **2 个剧本**：

```
[0] 1973_START_NAME  2073.1.1.12  25 个国家  blitzkrieg.txt
[1] 1999_START_NAME  1999.8.7.1   14 个国家  the_gathering_storm.txt
```

（`blitzkrieg.txt` 开头写着 `# Broken, may fix it later`，但内容本身没被注释，仍然有效。）

### 新增接口

```
POST /api/bookmarks        {}                                    全部剧本
POST /api/bookmark_add     {name, date, desc, picture, default_country}
POST /api/bookmark_set     {index, fields:{date/name/desc/picture/default_country}}
POST /api/bookmark_delete  {index}
```

新剧本写进 `common/bookmarks/zz_editor_bookmarks.txt`，日期格式校验 `1936.1.1` 或 `1936.1.1.12`。

### 实测

```
接管后 2 个剧本
加 TEST_START（1940.1.1）→ 3 个
改 date 1945.6.1 + name TEST2 → 生效
删 → 回 2 个
CN 未被改动
```

### 修了一个索引错位

`load_bookmarks` 是**跨文件**遍历的，索引是全局的；
但 `bookmark_set` / `bookmark_delete` 定位时用的是**单个文件**里的 `find_blocks`。

拿全局索引直接去单文件里找，第二个文件起的条目就全部对不上，报「重新定位失败」。

修法：进文件前先把全局索引换算成该文件内的序号。

```python
local = 0
for j, x in enumerate(items):
    if j == index: break
    if os.path.basename(x["file"]) == os.path.basename(it["file"]):
        local += 1
```

### 关于写入目标

`common/bookmarks` 在 muvluvCN 里**没有被 replace_path 接管**，
所以新剧本写到自己的 mod 就能生效，不需要先接管目录（和 `history/units` 不一样）。

### 界面

「编辑」tab → 开局剧本：

```
[载入剧本]

共 2 个剧本
  1973_START_NAME       2073.1.1.12   25   [删]
  1999_START_NAME       1999.8.7.1    14   [删]

新建剧本
[名称 key____] [1936.1.1]
[描述 key____] [GER] [加]
```

### 回归

```
写接口  10/10
```
