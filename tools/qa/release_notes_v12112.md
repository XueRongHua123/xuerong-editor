## 雪绒的钢铁雄心编辑器 v1.21.12

舰队补齐：加船、加特遣队、改舰船属性。

### 新增接口

```
POST /api/navy_add_ship    {fi, ti, name, definition, exp}   往特遣队加一艘
POST /api/navy_add_tf      {fi, name, location}              往舰队加一个特遣队
POST /api/navy_set_ship    {fi, ti, si, fields}              改某艘船
```

`fields` 支持 `name` / `definition` / `exp`。

### 实测

```
原始 第一舰队：1 队 1 艘
加船 → 船数 2，最后一艘 {name: 测试舰A, definition: destroyer}
加特遣队 → 队数 2
改船 → {name: 改名舰, definition: battleship}
```

生成的文件片段：

```hoi4
task_force = {
    name = "第一炮击分队"
    location = 12736
    ship = { name = "墨西哥" definition = carrier ... }
    }
    ship = { name = "测试舰A" definition = destroyer start_experience_factor = 0.5 }
}
    task_force = {
        name = "测试战队"
        location = 9999
    }
}
```

### 修了两个插入位置的坑

**坑 1**：`find_blocks` 返回的 `end` 是 `}` **后一位**，不是 `}` 的位置。
直接 `raw[:en] + ins + raw[en:]` 会把内容插到 `}` 外面：

```
}			ship = { ... }      ← 插错了
```

**坑 2**：往回跳过空白时如果连 `
` 一起跳，会跨行退到内层块的 `}`：

```
}                              ← 退到了 ship 的 }
		ship = { ... }          ← 插到 ship 后面了
```

最后改成：**只跳行内缩进、不跨行**，并**插在 `}` 所在行的行首前**，`}` 的缩进就不会被吃掉。

### 界面

「编辑」tab → 开局舰队下面：

```
加船（选舰队/特遣队）
[0] [0] [舰名____]
[destroyer] [0.3] [加船]

加特遣队
[0] [队名____] [省号] [加队]
```

序号对应列表里的顺序（从 0 开始）。

### 回归

```
写接口  10/10
```

### 还没做

- 空军（`air_wings`）
