## 雪绒的钢铁雄心编辑器 v1.21.8

国家离岸建筑（`add_offsite_building`）。

### 先说一个发现

原计划做 `add_building_construction`（州内建筑），查了 muvluvCN：

```
add_building_construction   0 次（history/countries 和 history/states 都没有）
add_offsite_building       136 次
```

CN 用的是**离岸建筑**——不占州建筑位，直接给国家加产能。
州内建筑在 `history/states` 的 `buildings` 块里，那个早就支持了。

### 数据形态

和科技、想法都不同，`add_offsite_building` 是**多个独立块**：

```hoi4
add_offsite_building = {
	type = arms_factory
	level = 5
}
add_offsite_building = {
	type = industrial_complex
	level = 30
}
```

### 新增接口

```
POST /api/country_starter              {tag}                清单 + 可选类型
POST /api/country_offsite_add          {tag, type, level}
POST /api/country_offsite_delete       {tag, index}
POST /api/country_offsite_set          {tag, index, type, level}
```

`country_starter` 返回的 types 来自 `STATE_BUILDINGS` 加 `ammunition_plant` / `ammunition_silo`。

### 界面

「编辑」tab → 国家离岸建筑：

```
[TAG] [载入]

AFR：5 项离岸建筑，合计 44 级
  arms_factory              ×5   [改][删]
  industrial_complex        ×30  [改][删]
  dockyard                  ×5   [改][删]
  ammunition_plant          ×2   [改][删]
  ammunition_silo           ×2   [改][删]

添加
[ammunition_plant ▾] [1] [加]
```

### 实测（AFR）

```
原始：5 项，合计 44 级
加 synthetic_refinery ×4 → 6 项，48 级
改 → ×9
删 → 回到 5 项 44 级
未接管 history/countries → 被 replace_path 独占，拒绝写入
CN 未被改动
```

### 浏览器实测

```
控件全在（TAG/载入/列表/类型下拉/加 按钮）
载入 → 5 行，类型下拉 13 个选项
problems: []
```

### 回归

```
写接口  10/10
```
