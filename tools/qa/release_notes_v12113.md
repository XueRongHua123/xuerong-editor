## 雪绒的钢铁雄心编辑器 v1.21.13

开局空军（`air_wings`）。

### 数据形态

```hoi4
air_wings = {
	524 = {                              ← 省号（基地）
		name = "中华太空舰队"
		transport_plane_equipment_1 = {
			owner = "CHI"
			amount = 5
		}
	}
}
```

muvluvCN 里 9 个文件提到 `air_wings`，其中 **5 个是有效内容**
（CHI / EUR / SOV / UNI / USA 的 1999 文件），另外 4 个整段被注释掉了。

### 新增接口

```
POST /api/air_wings           {}                                    全部联队
POST /api/air_wing_add        {province, name, type, owner, amount} 加一支
POST /api/air_wing_delete     {index}                               删一支
```

### 实测（muvluvCN）

```
9 支航空联队，5139 架飞机
  省 524  中华太空舰队         transport_plane×5
  省 125  炮击部队            MVLV_AL_shell×1000, transport_plane×5
  省 463  第1轰炸舰队          MVLV_shell×1000, transport_plane×5
  省 357  国联宇宙总军第一舰队   transport_plane×3
  …

加 省999「测试联队」fighter_equipment_3 ×25 → 10 支、5164 架
删 → 9 支、5139 架，文件回到 'air_wings = {
}
'（无残留）
未接管 history/units → 被 replace_path 独占，拒绝写入
CN 未被改动
```

### 修了一个删除残留

第一版的 `start` 取的是 `{` 的位置，删完只剩半截：

```
air_wings = {
	999 =          ← 残留
}
```

改成取「省号 = {」那一行的**行首**之后，删完是干净的：

```
air_wings = {
}
```

### 界面

「编辑」tab → 开局空军：

```
[载入联队]

9 支航空联队，5139 架飞机
  省524  中华太空舰队              5   [删]
  省125  炮击部队                1005   [删]
  …

加联队
[省号] [联队名____]
[fighter_equipment_1] [TAG] [10] [加]
```

### 关于舰队和空军的写入目标

两者都写进 `history/units/zz_air_wings.txt` / `zz_units.txt`（新建文件），
所以都受 `history/units` 的 replace_path 约束——需要先接管该目录。

### 回归

```
写接口  10/10
```
