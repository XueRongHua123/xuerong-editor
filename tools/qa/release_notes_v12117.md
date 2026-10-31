## 雪绒的钢铁雄心编辑器 v1.21.17

州资源编辑。第二层（开局剧本配置）最后一项。

### 数据情况

原以为是国家级 `add_resource`，查了 muvluvCN：

```
add_resource（history/countries）    0 处
resources=（history/states）        298 处
```

**CN 的铁、铝、油都在州上**，不在国家上。所以资源编辑做进了州编辑面板。

### 数据形态

在 `history/states/*.txt` 的 `state = { }` **顶层**（不在 `history` 里）：

```hoi4
state = {
	id = 104
	name = "STATE_104"

	resources={
		aluminium=7 # was: 10
	}

	history = {
		1999.1.1 = { owner = H11 }
	}
}
```

### 新增

**后端**：

- `STATE_RESOURCES` 常量：`oil / rubber / steel / aluminium / tungsten / chromium`
- `_set_resource(body, key, value)`：改/建/删单条资源；归零就删行，块空了整段删
- `state_save` 接受 `fields.resources = {aluminium: 15, oil: 3}`
- `load_states` 解析 `resources` 进 `STATES[sid]["resources"]`
- `state_detail` 带上 `resources`

**前端**：州面板建筑位下面加：

```
资源
  oil      [  0 ]     rubber    [  0 ]
  steel    [  0 ]     aluminium [ 15 ]
  tungsten [  0 ]     chromium  [  0 ]
  [保存资源]
```

### 实测

```
州 104 原资源：{aluminium: 7}
改成 {aluminium: 15, oil: 3}
读回：{oil: 3, aluminium: 15}
```

### 回归

```
写接口  10/10
```
