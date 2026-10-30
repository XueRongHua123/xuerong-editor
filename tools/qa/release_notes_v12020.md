## 雪绒的钢铁雄心编辑器 v1.20.2

做「真实游戏内验证」的第一步：新增游戏可读性校验 `qa/check_game_readable.py`，
跑出并修了一个真 bug。

### 新工具：check_game_readable.py

不启动游戏，验证编辑器写出的文件 HOI4 能不能正确解析。30 项检查，覆盖 6 类写操作：

| 类别 | 检查项 |
|---|---|
| 州文件 | 花括号配平、owner/category/manpower/add_core_of/buildings 是否写进目标文件、BOM 策略 |
| 地形 bmp | 头部完好（w/h/bpp/offset/row 不变）、8 位索引图、索引读回一致 |
| 战略区 | 花括号、新建文件有 BOM、含 strategic_region/id/name/provinces/weather |
| 补给区 | 花括号、新建文件有 BOM、含 supply_area/id/name/value/states |
| 铁路 | 花括号、每行是否都是纯数字序列 |

**结果：30/30 通过。**

### 修的 bug：`_state_file_for` 与 `STATES` 记录不一致

同一个州 id 在多个文件里出现时（原版有 `1-France.txt`，mod 又加了 `1-Corsica.txt`），
`_state_file_for` 按文件名序遍历，挑到 `1-Corsica.txt`；而 `state_save` 用的是
`STATES[sid]["file"]`（`1-France.txt`）。

**两个函数指向不同文件**，导致：

- `state_save` 写 `1-France.txt`
- 后续读取用 `_state_file_for` 拿 `1-Corsica.txt` → 读不到刚写的值

实测：`state_save` 返回「已写入 1-France.txt」，但校验脚本按 `_state_file_for` 读回来
`owner`/`state_category`/`manpower` 全部对不上，5 项检查失败。

修法：`_state_file_for` 优先返回 `STATES` 里已经定下来的那条记录（root + file），
只有记录缺失时才回退到遍历。

修后 30/30 全绿。

### 关于 BOM 的一个发现

`state_save` 用 `_read_bom_text` / `_write_bom_text` 保留原文件的 BOM 状态。

CN 的 `1-France.txt` **本来就没有 BOM**（首字节 `0a`），写回后仍然没有。

这不是缺陷：HOI4 对普通 txt（states / strategicregions / railways）不强制 BOM，
只有本地化 yml 必须有。编辑器新建的文件（战略区、补给区）都会写 BOM。

### 回归

```
可读性  30/30
写接口  10/10
```

### 还没做的「真实游戏内验证」

这个工具验证的是**语法层面**（花括号、字段名、编码、bmp 头），不是「HOI4 真能加载」。

剩下要做的：

1. 启动 HOI4，加载一个改过的 mod，看 `error.log` 有没有相关报错
2. 进游戏看改动是否生效（地形颜色、州归属、战略区边界）
