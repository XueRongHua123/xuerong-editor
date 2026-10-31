## 雪绒的钢铁雄心编辑器 v1.23.21

人物头像。

### 原来只能填两个怪参数

`character_add` 有 `portrait_large` 和 `portrait_small`，但要玩家自己准备 DDS 文件、
自己写 sprite 定义、自己记住哪个填 sprite 名哪个填路径：

```hoi4
portraits = {
	army = {
		large = GFX_portrait_GER_xxx      ← 这个要 sprite 名
		small = "gfx/leaders/GER/x.dds"   ← 这个要文件路径
	}
}
```

两个格式不一样，填错就是空头像或者报错。

### 新增 portrait_import

```
POST /api/portrait_import  {src_path, tag, id, overwrite, small}
```

一条命令做完四件事：

1. **转 DDS**：大图 **156×210**、小图 64×64（HOI4 原版头像就是这个尺寸）
2. **放对位置**：`gfx/leaders/<TAG>/<id>.dds`
3. **注册 sprite**：写进 `interface/zz_editor_portraits.gfx`
4. **返回 sprite 名**

缩放方式是**等比塞进目标框 + 补透明边**，不裁切不拉伸——玩家的图尺寸五花八门，
硬拉会把人脸拉变形。

### character_add 直接吃图片

新增 `portrait_src` 参数，给一张 png/jpg 就自动：

```
导入头像 → 拿到 GFX_portrait_GER_XTT_Gen → 自动填进 portraits 块
```

实测生成：

```hoi4
XTT_Gen = {
	name = "测试将军"
	portraits = {
		army = {
			large = GFX_portrait_GER_XTT_Gen
		}
	}
	corps_commander = { skill = 5 ... }
}
```

### 界面

「人物」面板 → 新建人物：

```
[id] [名字]
[类型下拉] [国家 TAG] [技能] [新建]
[头像图片路径（png/jpg，可空）]
```

填了路径就自动导入，不填就是默认剪影。

### 顺带补的

新建人物原来没有「国家 TAG」输入框，但 `country` 参数 v1.23.16 就有了——
不填的话会写进通用文件 `zz_editor_characters.txt`，人物不显示。现在界面上有输入框了。

### 还没做的

- 头像裁剪（现在只等比缩放，不加裁切框）
- 小头像（`small`）的自动生成——现在只导大图，小图 HOI4 会用默认
- 删除人物时头像文件不清理

### 回归

```
写接口  10/10
```
