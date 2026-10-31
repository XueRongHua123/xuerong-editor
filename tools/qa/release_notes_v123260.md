## 雪绒的钢铁雄心编辑器 v1.23.26

三件事：原子写入、黄金测试、诊断面板。

### 一、原子写入

71 处 `io.open(path,"wb").write(data)` 改成 `_atomic_write(path, data)`。

直接写的风险是写到一半崩溃或断电，文件变成半截，原内容也没了——mod 文件被截断后
游戏加载会直接崩，而且看不出是哪个文件坏的。

新实现：写同目录临时文件 → `fsync` → `os.replace` 覆盖。要么是旧内容，要么是新内容。

### 二、黄金测试

`qa/golden.py` + `qa/cases/*.json`。

用例是数据，不是代码：

```json
{
  "name": "bookmark_date_three_segments",
  "fn": "_bookmark_date",
  "args": ["1936.1.1"],
  "expect": "1936.1.1.12",
  "note": "HOI4 剧本日期是四段，只写三段游戏会把日当时"
}
```

加用例只往 JSON 数组里加一条。支持三种断言：`expect`（精确相等）、
`expect_bytes`（bytes 比较）、`expect_contains`（子串包含）。
带 `fixture` 的用例会先把文件铺到临时目录再测，所以 `_oob_files` 这种读磁盘的也能测。

当前 9 条，覆盖这几版修出来的每个坑：剧本日期补段、BOM、三种 OOB 的年份过滤、
剧本国家块字段。

### 三、诊断面板

左侧导航新增「🩺 诊断」。

结构照 HOI4 modding 工具链的通行做法，每条诊断带：

```
code      稳定错误码
severity  error / warning / info
file      mod 内相对路径
line      行号
excerpt   出错那段原文
msg       一句话说清问题
repair    怎么改
```

**目前四个检查项**，全是这几版真机踩出来的：

| 检查项 | 防什么 |
|---|---|
| `script.oob.not_referenced` | OOB 文件没被 `set_oob` 点名，游戏不加载也不报错 |
| `gfx.sprite_missing` | `icon` / `picture` 引用的 sprite 不存在，界面空白 |
| `script.recruit.last_line` | `recruit_character` 在文件最后一行，招募静默失败 |
| `script.decision.category_undefined` | 决议类别没在 `categories/` 注册 |

这四个问题的共同点：**游戏不会报错，只是「东西不出现」**。以前只能靠进游戏肉眼找，
现在打开面板就能看到。

实测造的四个错例全部准确报出，正例（v1.23.25 生成的测试模组）零误报。

### 回归

```
写接口      10/10
黄金测试      9/9
生成流程    15/15
```
