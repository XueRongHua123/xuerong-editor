## 雪绒的钢铁雄心编辑器 v1.21.15

开局已完成国策（`complete_national_focus` / `mark_focus_tree_completed`）。

### 数据情况

muvluvCN 里这几个字段**全是 0 处**：

```
complete_national_focus      0
mark_focus_tree_completed    0
set_national_focus           0
add_national_focus           0
```

CN 的国策全部从零开始推进，没有预置完成项。但别的 mod 会用，所以按通用性做了。

### 两种写法都认

```hoi4
complete_national_focus = {
	focus = AFR_SecureSuezFront
}

complete_national_focus = AFR_SecureSuezFront

mark_focus_tree_completed = yes
```

### 新增接口

```
POST /api/completed_focuses       {tag}          已完成的国策 + 是否整树完成
POST /api/focus_complete_add      {tag, focus}   加一个
POST /api/focus_complete_delete   {tag, index}   删一个
```

返回的每项会去 `TREES` 里查名字和所属树，查不到的标 `known: false`（界面显示 ⚠）。

### 实测

```
读 AFR：0 个已完成国策
从国策树里取一个真实 id：AFR_SecureSuezFront
加 → AFR：1 个已完成国策 [{focus: AFR_SecureSuezFront, form: block}]
删 → 剩 0
```

加的时候如果 id 在现有国策树里找不到，会提示「注意：现有国策树里没找到这个 id」——
不阻止，因为可能有别的 mod 定义了它。

### 界面

「编辑」tab → 开局已完成国策：

```
[TAG] [载入]

AFR：0 个已完成国策
  AFR_SecureSuezFront            [删]
  bogus_focus ⚠                  [删]

[国策 id________] [加]
```

### 回归

```
写接口  10/10
```
