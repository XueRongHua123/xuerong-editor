## 雪绒的钢铁雄心编辑器 v1.23.18

人物类型可以在界面上改了。

### 补的是什么

`character_set` 原来只能改名字和五项技能，改不了类型（陆军将军 / 元帅 / 国家领导人 / 特工）。

这在真机验证时暴露出来：新建了一个元帅，进游戏发现「选择集团军指挥官」列表里找不到他。
那个列表只显示陆军将军，元帅指挥的是集团军群，属于另一套入口。

当时的验证需要把类型从 `field_marshal` 换成 `corps_commander`，而编辑器做不到，
只能改测试脚本的参数重新生成——绕过了界面，等于这个操作编辑器本身不支持。

### 改法

**后端**：`character_set` 接受 `fields.type`。

HOI4 里人物类型就是块名：

```hoi4
XTT_Gen = {
	name = "测试将军"
	corps_commander = {        ← 类型就是这个块名
		skill = 5
		...
	}
}
```

改类型等于改块名。技能字段在各类型里通用，不用搬家。

**前端**：人物面板「编辑选中」下面加类型下拉：

```
（不改类型）
陆军将军 corps_commander
元帅 field_marshal
国家领导人 country_leader
特工 operative
```

点列表里的人会自动带出当前类型，选新的再点保存。

### 实测

```
改前类型: field_marshal
改类型:   测试将军 已更新：type:field_marshal→corps_commander
改后类型: corps_commander
技能还在吗: {'skill': 5, 'attack_skill': 6, 'defense_skill': 4,
            'planning_skill': 3, 'logistics_skill': 2}
```

五项技能全部保留。

### 测试模组

```
15 项 | 成功 15 | 失败 0
char set type  测试将军 已更新：type:field_marshal→corps_commander
```

`GER.txt` 里现在写的是 `corps_commander`，进游戏后应该出现在集团军指挥官列表里。

### 回归

```
写接口  10/10
```
