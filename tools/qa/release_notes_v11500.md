## 雪绒的钢铁雄心编辑器 v1.15.0

装备变体能直接改了。新增「装备」页，找装备、看属性、改数值、删变体。

### 1. 列表与搜索

`/api/equipment_list?q=` 支持按 id 或名字过滤。

muvluvCN 实测：**348 个装备**，分布在 `common/units/equipment/` 的 58 个文件里。

### 2. 详情

点任意装备，右侧显示：

```
CAS_equipment　近距支援机　底盘 cv_fighter_equipment　1940
common/units/equipment/single_engine_airframe.txt

属性（35 个）
  air_agility        65
  air_attack         8
  air_range          900
  ...
模块槽
  （这个装备没有模块槽）
引用位置
  common/units/equipment/single_engine_airframe.txt
```

**「底盘」那行是 archetype**——HOI4 里子装备继承底盘属性，所以有些字段在本装备里不存在（用底盘的默认值）。

### 3. 改属性

每个属性一个输入框，改完点「保存改动」。

- 属性已存在 → 改值
- 属性不存在 → 插入到块末尾（这是 HOI4 的合法写法，等同覆盖底盘默认值）
- 空值跳过
- 属性名做合法性检查（只允许 `[a-z_0-9]+`）

实测：把 `CAS_equipment` 的 `air_agility` 从 65 改成 999，文件里写入了 `air_agility = 999`。

### 4. 删除

**带引用检查**：扫描 `common/`、`history/`、`events/` 里有没有别的地方用这个 id，
有就拒绝删除并列出前三个引用位置。

只有定义文件自己引用的（也就是没有外部引用）才允许删。

### 5. 只读保护

来自原版的装备（`root == GAME`）标记为只读，保存和删除按钮禁用。

### 结构说明

装备都是 `equipments = { 名字 = { ... } }` 的形式，一个文件可以有多个 `equipments` 块。
后端按「找块 → 定位字符区间 → 只改块内文本」的方式处理，不重写整个文件结构。

块结构（`module_slots`、`resources` 等嵌套）不在编辑范围内——只做标量属性，
避免把嵌套写坏。

### 待做

- 模块槽编辑（增删槽、改 allowed_module_categories）
- 装备的 `resources` 成本编辑（钢/钨/铬等）
- 批量改（按 archetype 批量调整同类装备）
