## 雪绒的钢铁雄心编辑器 v1.20.3

**严重缺陷修复**：改州会写进父 mod 的真实文件，污染别人的模组。

### 缺陷

`state_save` 用 `STATES[sid]["root"]` + `["file"]` 定位目标文件。

当加载一个**纯 submod**（自己只有增量、州文件来自父 mod）时：

```
STATES[1].root = 父 mod 的目录
state_save → 直接写父 mod 的 history/states/1-France.txt
```

`state_save` 原本只挡了原版目录：

```python
if is_under_game(root):
    return {"ok": False, "msg": "原版目录只读"}
```

**父 mod 不在这个判断里**，所以直接写进去了。

### 实测事故

在 `muvluvCN_verify`（依赖 muvluvCN 的测试 mod）上改州 1 的 owner，
`state_save` 返回「已写入 history\states-France.txt」，
但实际写的是 **CN 的 `2800380626/history/states/1-France.txt`**。

已用 `snapshot` 备份恢复：

```
CN 文件   359 字节  md5 92c488d4570b
备份文件  359 字节  md5 92c488d4570b
diff      完全一致
owner 行  EUR / FRA（原值）
```

### 修法

写之前先算出「链顶」——当前加载的最上层非原版目录，然后：

1. 目标文件在链顶不存在时，从父 mod 复制一份过来
2. 在链顶的副本上改

```python
_top = None
for _r in (ROOTS or []):
    _lay = mod_layers(_r) or [_r]
    _cand = _lay[-1] if _lay else _r
    if _cand and not is_under_game(_cand):
        _top = _cand
if _top and os.path.abspath(_top) != os.path.abspath(root):
    root = _top
    # 父 mod 有原文件 → 先复制到链顶
```

这样父 mod 一个字节都不动，改动落在自己的 mod 里，符合 HOI4 的覆盖语义。

### 验证

```
改前 CN md5:  92c488d4570b
写入返回:      已写入 history\states-France.txt
改后 CN md5:  92c488d4570b   ← 没变
测试 mod 里:   1-France.txt 存在，owner = SOV
```

### 回归

```
写接口  10/10（muvluvCN / 京都燃烧各 5 项）
```

### 影响范围

**所有通过 `state_save` 改州的入口**：

- 地图州视图的「改归属国」
- 「类别与人力」保存
- 「核心领土」保存
- 「建筑位」保存
- 州细化（内部调 `state_save` 继承字段）

加载纯 submod 时，这些操作之前都会写进父 mod。现在都落到链顶。

### 剩下的

真机验证没做成——`hoi4.exe` 拉起 Steam 后游戏窗口没出来。
测试 mod（`muvluvCN_verify`）已就位，等下次启动游戏验证。
