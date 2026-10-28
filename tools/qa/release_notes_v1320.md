## 雪绒的钢铁雄心编辑器 v1.3.2

检查面板新增「贴图」页：查脚本引用的 sprite 有没有 gfx 定义，以及定义的贴图文件是否真的存在。

参考 [CWTools](https://marketplace.visualstudio.com/items?itemName=tboby.cwtools-vscode) 的 validator「That referenced sprites and graphics files exist」。

### 查两件事

**1. 引用了但没定义**

从这六个目录扫 `icon = GFX_xxx` / `picture = GFX_xxx`：

```
common/national_focus   common/ideas   common/decisions
common/decisions/categories   events   common/units/equipment
```

再对比所有 `.gfx` 里的 `spriteType` 定义（原版 145 个文件 + mod 自己的）。
游戏里遇到没定义的 sprite 会显示空白方块。

**2. 定义了但贴图文件不存在**

mod 自己定义的 sprite，`texturefile` 指向的 `.dds` 在 mod 和原版里都找不到 —— 加载时会报"找不到文件"。

### 解析踩了三个坑

| 坑 | 现象 | 修法 |
|---|---|---|
| 正则提前截断 | 用 `spriteType\s*=\s*\{(.*?)\}` 取块，块内有 `frames = { }` 嵌套，第一个 `}` 就断了 → 只收到 14638 个 sprite | 改用 `brace_match` 配对取块 → 25082 个 |
| `name` 不带引号 | `name = GFX_goal_EasyUNI_un_logo` 这种写法被要求引号的正则漏掉 | `name\s*=\s*"?([^"\s\}]+)"?` → 27406 个 |
| sprite 名含中文 | `GFX_94式戦車` 被 `[A-Za-z0-9_.-]` 截成 `GFX_94`，报假缺失 | 引用正则改 `[^"\s\}]+` |

三轮修正后，muvluvCN 的报缺数量：**309 → 118 → 7 → 4**。

剩下 4 个抽验过，`grep` 遍 mod 和原版的 `interface/` 都搜不到，是真缺：

```
GFX_focus_SAF_colonialist_crusade    icon     MVLV_CAN.txt
GFX_report_event_czech_soldier_01    picture  stability_events.txt
GFX_report_event_japanese_soldiers   picture  stability_events.txt
GFX_report_event_nra_march           picture  stability_events.txt
```

### 顺带过滤

`icon = aluminium` / `icon = generic_air` 这类是资源名和类别名，不是 sprite。
只认 `GFX_` 开头（HOI4 的 sprite 命名约定），过滤掉这些噪音。

### 性能

首次扫描约 **2.8 秒**（要读原版 145 个 gfx、2.7 万个 sprite），结果缓存在内存里，同一 mod 第二次是毫秒级。

### 实测（muvluvCN 1.19）

```
引用 290 个 sprite，缺 4 个；贴图文件缺失 0 个
已定义 27406 个
```
