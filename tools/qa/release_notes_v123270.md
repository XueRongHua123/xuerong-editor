## 雪绒的钢铁雄心编辑器 v1.23.27

诊断检查项从 4 个补到 8 个。

### 新增四个

| 检查项 | 严重度 | 防什么 |
|---|---|---|
| `script.character.not_recruited` | warning | 人物定义了但没被 `recruit_character` 招募，游戏里不出现 |
| `loc.key_missing` | info | 引用的本地化键不存在，界面显示裸 key |
| `loc.tag_def_missing` | warning | 新国家的 `TAG_DEF` 没写，通用事件/决议显示异常 |
| `script.division_template.missing` | error | `units` 引用了不存在的师团模板 |

加上原来的四个（OOB 未点名 / sprite 缺失 / recruit 在末行 / 决议类别未注册），
一共八项，全部是这几版真机踩出来的。

### 两个误报修掉了

**一、`corps_commander` 被当成人物 id**

第一版收集人物时匹配了 `characters` 块里所有 `xxx = {`，把类型块也算进去了。
爆出「人物 corps_commander 没被招募」这种假警。

改成按花括号深度判断，只取 `characters` 的直接子级。

**二、`recruit_character` 末尾判断太严**

原版文档说的是「文件末尾必须至少还有一行，**哪怕空行**」。
第一版看的是最后一个**非空**行，结果文件末尾有空行也报。

改成看物理最后一行。

实测：

```
AAA - Test.txt   最后一行是 recruit_character       → 报
BBB - Test.txt   后面有一个空行                     → 不报
```

### 当前八项

```
error    script.division_template.missing
warning  script.oob.not_referenced
warning  gfx.sprite_missing
warning  script.recruit.last_line
warning  script.decision.category_undefined
warning  script.character.not_recruited
warning  loc.tag_def_missing
info     loc.key_missing
```

### 回归

```
写接口      10/10
黄金测试      9/9
生成流程    15/15
```
