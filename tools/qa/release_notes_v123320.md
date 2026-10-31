## 雪绒的钢铁雄心编辑器 v1.23.32

国策树检查做了又撤回，五个检查项误报率稳定在 0.002%。

### 试了国策树，撤回了

`common/national_focus` 的嵌套太深：

```
focus_tree = {                           depth 1
	focus = {                              depth 2
		completion_reward_xxx = {            depth 3  ← effect 块
			add_tech_bonus = {                 depth 4
				bonus = 0.75                     depth 5
```

嵌套四五层之后，块栈和深度的对齐开始出错，`bonus`/`uses`/`category` 这些
effect 参数被当成国策字段报出来。

试了三轮降噪：

```
初版                                  3726 条 / 0.5388%
加「块名本身也放过」+ 扩充 skip 块      1815 条 / 0.2625%
加 completion_reward* 等前缀跳过        1658 条 / 0.2398%
```

停在 0.24%，是其他检查项的 100 倍。**撤回**。

代码留着（`_diag_schema_focus`），注释里写了原因，等有更好的深度跟踪方案再开。

### 顺手修了一个通用 bug

「块名本身」和「块里面的内容」是两回事。`_SCHEMA_SKIP_BLOCKS` 原来只管
「进入这个块之后不检查」，但块名本身（`limit = {` 这一行）还是会被当成字段。

结果 `limit` 报了 1823 条。改成 `_is_skip_block()` 前缀判断后消失。

这个 bug 五个检查项都受影响，不只是国策树。

### 现在覆盖五个块

```
oob         history/units 的 division
bookmark    common/bookmarks 的 bookmark
character   common/characters（含类型块内部）
decision    common/decisions
idea        common/ideas
```

### 误报率（原版全量）

```
人物 232 文件 + 决议 89 + 精神 213 + OOB 609
749716 行
告警 17 条
误报率 0.00227%
```

剩下 17 条是比较表达式（`communism > 0.5`）和无 tag 前缀的自定义 trigger。

### 回归

```
写接口      10/10
黄金测试      9/9
生成流程    15/15
```
