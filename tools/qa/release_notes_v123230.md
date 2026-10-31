## 雪绒的钢铁雄心编辑器 v1.23.23

部队和模板的两个问题。

### 问题一：模板文件没有国家前缀

`template_add` 一直写到 `history/units/zz_units.txt`。

HOI4 靠**文件名的国家前缀**判断 `division_template` 属于谁。原版连「只有模板没有部队」
的文件都是带前缀的（`CRO_1936.txt`、`ENG_LAR_Motorized.txt`），没有一个是光秃秃的名字。

写成 `zz_units.txt`，游戏不知道这个模板归哪个国家，`units` 里引用它就找不到。

**改法**：`template_add` 加 `tag` 参数，写到 `<TAG>_1936_zz.txt`，和部队同文件。

原版 `GER_1936.txt` 就是模板在文件顶部、`units` 在后面——模板和部队放一起是标准做法。

### 问题二：division 的 name 字段写法不对

原来写：

```hoi4
division = {
	name = "测试部队"
	location = 1
	...
}
```

原版是：

```hoi4
division = {	
	division_name = {
		is_name_ordered = yes
		name_order = 25
	}
	location = 6334
	...
}
```

`division` 直接子级没有 `name` 这个字段，名字要放 `division_name` 里面。
（`name = "Qafar Sefari"` 那种写法是 `division_template` 的，不是 `division` 的。）

**改法**：

```python
if name:
    division_name = { name = "测试部队" }
else:
    division_name = { is_name_ordered = yes  name_order = 1 }
```

### 实测

```hoi4
division_template = {
	name = "XTT_TestTpl"
	regiments = {
		infantry = { x = 0 y = 0 }
	}
}
units = {
	division = {
		division_name = {
			name = "测试部队"
		}
		location = 1
		division_template = "XTT_TestTpl"
		start_experience_factor = 0.5
		start_equipment_factor = 1
	}
}
```

两个都在 `GER_1936_zz.txt` 里。

### 还没验证的

`division_template` 少了原版的 `division_names_group` 字段（`division_names_group = GER_Inf_01`），
那个是部队命名池，可能会影响名字生成，但不确定是否必需。

### 回归

```
写接口  10/10
```
