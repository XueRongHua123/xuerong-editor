## 雪绒的钢铁雄心编辑器 v1.23.28

接入 CWTools 的 HOI4 规则，加 schema 字段检查。

### 规则从哪来

```
cwtools/cwtools-hoi4-config
license: MIT
111 个 .cwt，1025 KB
```

MIT 许可，规则是纯文本数据不是代码，可以直接拿。已下载到 `qa/cwt/raw/`，
随 exe 一起打包。

### 解析器

`qa/cwt/parse.py`，只做一件事：从 `.cwt` 里提取「块名 → 允许的字段名集合」。

`.cwt` 的完整语法有 `single_alias`、`value_set`、`enum`、`<unit.line_unit>` 这类引用，
第一版不碰它们的语义，只认 `名字 = { 字段 = 类型 }` 的基本形状。

**设计上宁松勿严**：跨层级把所有字段都收进来，白名单大一点、少报，比漏解析误报好。

结果：164 个块。几个相关的：

```
oob           68 个字段
character     40 个字段
bookmark      26 个字段
decision      48 个字段
```

### 新检查项 schema.unknown_field

只查两个结构固定的位置——块名不随内容变的地方：

```
history/units/*.txt 里 `division = { ... }` 的直接子级
common/bookmarks 里 `bookmark = { ... }` 的直接子级
```

**不查**人物 id、装备名这类动态标识符，那些是内容不是字段，查了全是误报。

### 调试过程

第一版把「所有 `xxx = {`」都当字段，跑出 **542 条误报**——`GER_adolf_hitler = {`
是人物 id，`civilian = {` 是枚举值，都被当成拼错的字段。

收紧到只查固定结构后归零。

第二版一个都不报，原因是深度算错：`units` 先占一层，`division` 里的字段实际在
`depth == 2`，我按 `depth == 1` 查，扫了个空。改成记住进入块时的深度
（`base_depth`）之后正常。

### 实测

```
错例：division_templet = "Typo"
  → ZZT_1936.txt 第 5 行的字段 division_templet 不在 oob 的规则定义里

正例：v1.23.25 生成的测试模组
  → 0 条
```

### 顺手抓到两个真问题

用诊断扫自己的测试模组，报出两条：

```
loc.tag_def_missing    国家 XTT 缺 XTT_DEF 本地化
gfx.sprite_missing     zz_editor_decisions.txt 引用了 GFX_decision_generic
```

第二条是真的——那份文件是 v1.23.25 之前生成的，用的是已经改掉的旧图标名。
诊断功能在自己的产物上生效了。

### 打包

exe 需要带规则，`make_release.py` 加了 `--add-data qa/cwt;qa/cwt`，
`_cwt_rules()` 里的路径改成优先用 `sys._MEIPASS`。

### 回归

```
写接口      10/10
黄金测试      9/9
生成流程    15/15
```
