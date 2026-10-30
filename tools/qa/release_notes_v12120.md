## 雪绒的钢铁雄心编辑器 v1.21.2

省面板部队增删改 + `division_template` 编辑后端。

### 省面板增删改

点省后，每支部队后面有 `[移]` `[删]`：

```
开局部队
  战术机联队              [移][删]
  战术机联队              [移][删]
```

底部加部队区：

```
[331 ▾] [1] [加部队]
```

选模板、填数量、点加。数量大于 1 时循环调用接口。

### division_template 编辑（后端）

```
POST /api/template_save    {name, fields:{new_name, regiments, support, locked}}
POST /api/template_delete  {name}
POST /api/template_add     {name, unit, x, y}
```

`fields` 里给什么改什么，没给的保留原值。

**实测**：

```
原模板: 331 编制 2 来自 SOV_nf2.txt
改名 → 改名Y：目标文件第 2 行变成 name = "改名Y"
加编制 → 编制 2 → 3
新建 全新模板_B → 列表里出现，删除后消失
未接管时 → 被 replace_path 独占，拒绝写入
```

### 修了三个 bug

1. **替换块重复前缀**：`find_blocks` 返回的偏移指向 `{`，而 `_tpl_render` 又自带 `division_template = `，
   结果生成 `division_template = division_template = {`。加 `with_key` 参数解决。
2. **改错文件**：同名模板在多个文件里出现（CN 的 `SOV_nf.txt` 和 `SOV_nf2.txt` 都有 `331`），
   `_tpl_locate` 按正序找第一个，而 `load_units` 的覆盖语义取最后一个。改成倒序。
3. **JS 语法**：省面板插部队容器时漏了一个引号，导致整段脚本解析失败。

### 已知行为

改一个同名模板时，只改 `load_units` 显示的那一份（最后加载的）。
其他文件里的同名副本仍然存在——这是 HOI4 数据里本来就有的重复定义，不是编辑器造的。

### 还没做

- 模板编辑的**界面**（后端接口就绪，界面下一版）
- 编制格的**可视化排布**（现在只能通过接口传 x/y）

### 回归

```
写接口  10/10
```
