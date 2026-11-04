## 雪绒的钢铁雄心编辑器 v1.23.45

### 加载子 mod 时自动带上依赖链

以前加载一个子 mod，编辑器只跟它 `descriptor.mod` 里写的 `dependencies` 走。问题在于 **`dependencies` 不是游戏的加载链**——它只是启动器用来提示「你缺前置」的元数据。游戏真正按什么顺序叠 mod，写在 `dlc_load.json` 的 `enabled_mods` 里。

所以我们跟错了源。表现是：加载 XRT1，链只有 `[原版, muvluvCN, XRT1]`，`muvluvCNsub` 永远带不进来——因为 XRT1 的 `dependencies` 里只写了 `muvluvCN`。

现在改成**跟 `dlc_load.json` 的实际顺序**，`dependencies` 只用来补漏：

```
改前  mod_layers(XRT1): [原版, muvluvCN, XRT1]
改后  mod_layers(XRT1): [原版, muvluvCN, muvluvCNsub, muvluvCNsub雪绒拓展, XRT1]
```

实测数据量（加载 XRT1）：

| | 改前 | 改后 |
|---|---|---|
| 国策树 | 43 | **85** |
| 科技 | 660 | **770** |
| 装备 | 304 | **323** |
| 国家精神 | 490 | **511** |

### 顺手解决的两件通用性问题

**一、`_find_mod_by_name` 不再写死 Steam 库路径**

原来硬编码 `E:\SteamLibrary\steamapps\workshop\content\394360`。换机器、或者把游戏挪到别的盘，依赖就找不到了。

现在从三个地方推：注册表里的 Steam 安装位置（HKCU + HKLM 都查）→ `steamapps/libraryfolders.vdf` 里的所有库 → 从游戏目录本身反推一个库。

**二、不用再手动把父 mod 一个个加进数据源**

加一个子 mod，父 mod 自动带上。

### 侧栏显示「自动带上」

```
数据源                        ①
[＋ 添加 mod] [－ 卸载]
XRT1 已加载
自动带上：muvluvCN、muvluvCNsub、muvluvCNsub雪绒拓展
☑ 跟随启动器加载依赖
```

「自动带上」那行是淡色小字，鼠标悬停显示每一层的完整路径。

### 新增「跟随启动器加载依赖」开关

默认开启。关掉后只跟 `dependencies`，回到 v1.23.44 的行为。

切换后需要重新加载 mod 才生效——链变了，不会自动重载（自动重载会打断正在编辑的节点）。

开关状态存在 `cache/options.json`，重启记得住。

### 验收

```
qa/regress_all.py          180/180（15 个真实 mod）
qa/_test_focus_all.py      12 过 / 0 挂
开关两态                   开：[原版, CN, CNsub, 雪绒, XRT1] / 关：[原版, CN, XRT1]
```

### 已知限制

- 关掉开关时，`_mod_dep_chain` 只跟第一条能定位到的父依赖。雪绒拓展依赖 `muvluvCN` + `muvluvCNsub`，关掉后只找到 CN。这是 v1.23.44 就有的行为，默认开启时不受影响。
- `data_payload` 里的 `ideas` / `equipment` / `techs` 还没有 `source` 字段，前端不知道每条数据来自哪一层。
- `roots[].readonly` 用 `is_under_game()` 判断，所以创意工坊的 mod 在侧栏显示成可写（真正的只读保护在 `_is_readonly_root`，是另一套逻辑）。
