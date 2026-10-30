## 雪绒的钢铁雄心编辑器 v1.20.1

按上一版整理的技术债清单做验证，查出并修了三个数据层缺陷，写回归从 7/10 到 10/10。

### 缺陷 1：州记录的 root 与 file 错位

`load_states(root)` 内部用 `_layer_files` 拿**整条叠加链**的文件，但写入 `STATES[sid]["root"]`
时用的是**函数参数**，不是文件实际所在的层。

结果：原版的 `1-France.txt` 被记成「子 mod 的文件」，`state_save` 报「州文件不存在」。

实测（父 mod + 子 mod 各有 id=1 的州）：

```
改前: root=child_mod  file=history\states-France.txt   ← 错位
报错: 州文件不存在：history\states-France.txt
```

修法：从文件绝对路径反推它属于哪个 base，`root` / `source` 都用那个。

### 缺陷 2：原版记录能覆盖 mod 记录

`_prefer(existing, root)` 只判断「现有记录是否来自原版」，允许原版覆盖。

但 `mod_layers(GAME)` 只返回一层，`layers.index(子mod)` 抛 ValueError 后走到 `return True`
——**原版的州把子 mod 的记录盖掉了**。

实测：

```
_prefer(cur=child_mod, root=GAME) = True    ← 应该是 False
```

修法：加一条「原版不能覆盖 mod 记录」，并改用 `ROOTS` 展开的完整链判断 mod 之间谁更靠后。

修后：

```
_prefer(child→GAME) = False
_prefer(GAME→child) = True
_prefer(child→parent) = False
```

### 缺陷 3：省颜色表是全局单例，换 mod 不刷新

`_ensure_prov_rgb(root)` 开头 `if PROV_RGB: return PROV_RGB` —— 第一个 mod 加载完就锁死了。

后果：跑回归先测 CN（13264 省）再测京都（17325 省），京都的 17214/17217 被判「不存在」，
州细化失败。

修法：按 `os.path.abspath(root)` 缓存，切换时 `clear()` + `update()`，保持全局引用有效。

### 写回归从 7/10 到 10/10

另外修了三处测试脚本的适配问题（都不是编辑器缺陷）：

| 项 | 原因 | 改法 |
|---|---|---|
| 地形「terrain.bmp 没变」 | `mod_layers` 是 `[原版, mod]`，测试取了**原版**的 terrain.bmp | 倒序找，先看 mod 自己的 |
| 战略区「没有空闲省」 | CN 的战略区覆盖了全部省 | 改成测「修改已有战略区的范围」 |
| 州细化「这些省不存在」 | 同缺陷 3 | 只选当前 mod 层的州 |

### 验证

```
读接口  36/36（muvluvCN / 雪绒拓展 / 京都燃烧）
写接口  10/10
```

写接口逐项：改地形、改铁路等级、战略区增删、装备改属性、州细化，两个 mod 全部通过。

### 落点验证

单独写了一个双 mod 测试（父 mod + 子 mod 各有 id=1 的州同 id），确认：

```
STATES[1].root  = child_mod
STATES[1].file  = 1-Child.txt
state_save      → 已写入 1-Child.txt
父 mod 文件变了  = False
子 mod 文件变了  = True
```

改州不会污染父 mod。
