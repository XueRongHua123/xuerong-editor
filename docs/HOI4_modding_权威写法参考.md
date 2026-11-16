# 钢铁雄心 IV Mod 代码写法权威参考（1.19）

面向本地 mod 开发的中文技术手册。写法以 `hoi4.paradoxwikis.com`（Paradox 官方维护的 HOI4 modding 文档站）为准，逐条对应到 wiki 页面，代码块可直接复制后改字段使用。

| 项 | 内容 |
|---|---|
| 对应版本 | 1.19.*（wiki 各页版本标记已在正文括注，未标注的按 `{{version|Timeless}}` 处理） |
| 取材时间 | 2026-10-31 |
| 原始 wikitext | `work/tmp/wiki/*.wiki`（页面原文，含未使用的部分） |
| 整理笔记 | `work/tmp/notes/*.md`（按页面切分的中间产物） |
| 覆盖范围 | 工程结构、脚本语法、作用域/触发器/效果（含各作用域条件与修正键全表）、变量、修正、国策、事件、决议、精神、角色、科技、装备、单位、国家、州、地图与地形、钩子、defines、本地化、界面、图形、3D 模型与实体、scripted GUI、AI、音乐与音效、情报机构、突袭、控制台、调试 |
| 未覆盖 | Nudger 图形化操作细节、工坊上架流程、突袭与行动的脚本数据库（wiki 无此文档，只能读本体文件） |

### 怎么用

1. 搭工程 → 第 1 章。描述符和目录一次配对，后面省很多时间。
2. 写第一段脚本 → 第 2、3 章。「键值 + 块 + scope」是全部系统的共同底座。
3. 做具体内容 → 直接跳对应章，复制模板改字段。查不到去哪改，先看附录 B 的「我要做什么 → 改哪里」。
4. 报错看不懂 → 第 32 章「常见错误汇编」+ 第 31 章「调试与日志」。

### 三条硬规矩（wiki 开篇强调）

1. **永不修改游戏本体文件**。改动一律走 mod，哪怕只改一个数字。Steam 更新会静默覆盖手改的文件。
2. **尽量少覆盖原版文件**。优先新增独立文件而不是复制原版改写，文件名用 mod 自己的前缀，兼容性和维护成本都低。
3. **文本 UTF-8 无 BOM，本地化 `.yml` UTF-8 带 BOM**。这两条规则方向相反，是新手翻车的头号原因。

### 目录

| 章 | 内容 |
|---|---|
| 1 | 工程结构：描述符、加载顺序、replace_path |
| 2 | Clausewitz 脚本语法 |
| 3 | 作用域（Scopes）与数据选择器 |
| 4 | 触发器（Triggers）与事件目标 |
| 5 | 效果（Effects） |
| 6 | 脚本化效果与脚本化触发器 |
| 7 | 变量与数据类型 |
| 8 | 修正体系（Modifiers） |
| 9 | 国策树 |
| 10 | 事件 |
| 11 | 决议与任务 |
| 12 | 国家精神（Ideas） |
| 13 | 角色与舆论 |
| 14 | 力量平衡与成就 |
| 15 | 科技 |
| 16 | 装备原型与升级链 |
| 17 | 单位定义与编制 |
| 18 | 海空军与 OOB |
| 19 | 国家创建 |
| 20 | 州与地图 |
| 21 | 剧本起点（Bookmarks） |
| 22 | 游戏规则（Game Rules） |
| 23 | on_actions 钩子 |
| 24 | defines 常量 |
| 25 | 本地化 |
| 26 | 界面（.gui） |
| 27 | 图形资源 |
| 28 | scripted GUI |
| 29 | AI |
| 30 | 控制台命令 |
| 31 | 调试与日志 |
| 32 | 常见错误汇编 |
| 33 | 音乐与音效 |
| 34 | 3D 模型与实体 |
| 35 | 情报机构与突袭 |
| 附 A | 取材清单与已知缺口 |
| 附 B | 路径速查与任务映射 |
| 附 C | 开发纪律与自检清单 |

---

## 第 1 章 工程结构：描述符、加载顺序、replace_path

### 1.1 用户目录

游戏把 mod、存档、日志、截图、设置都放在「用户目录」，位置由本体 `launcher-settings.json` 的 `gameDataPath` 决定：

| 系统 | 默认路径 |
|---|---|
| Windows | `C:\Users\<用户名>\Documents\Paradox Interactive\Hearts of Iron IV\` |
| Windows（OneDrive 重定向） | `C:\Users\<用户名>\OneDrive\<文档>\Paradox Interactive\Hearts of Iron IV\` |
| macOS | `~/Documents/Paradox Interactive/Hearts of Iron IV/` |
| Linux | `~/.local/share/Paradox Interactive/Hearts of Iron IV/` |

用户目录里的关键内容：

| 路径 | 用途 |
|---|---|
| `mod/` | 用户侧 mod 描述符（`.mod`）与本地 mod 文件夹 |
| `map/`、`history/states/`、`localisation/` | Nudger（内置地图编辑器）的输出目录，**这些目录里的文件会在启动时被加载，优先级高于本体** |
| `logs/` | `error.log`、`game.log`、`system.log` |
| `save games/` | 存档 |
| `screenshots/` | F11 截图与 F10 世界地图 |
| `settings.txt` | 设置，含只有这里能改的 `save_as_binary=no`、编辑器路径 |

**路径里不能有非 ASCII 字符**（带音标的拉丁字母、中文、日文、西里尔文都算）。用户目录路径含非 ASCII 时，本地 mod 会加载失败、`error.log` 打不开（但游戏仍会尝试写它）。绕法有两种：把 mod 文件夹挪到纯 ASCII 路径并在 `.mod` 里改 `path`；或改 `launcher-settings.json` 的 `gameDataPath` 把整个用户目录搬到 ASCII 路径。

### 1.2 两个描述符

每个 mod 有两个 `.mod` 文件，内容大体相同，但职责不同：

| 类型 | 位置 | 作用 |
|---|---|---|
| 用户侧描述符 | 用户目录 `mod/modname.mod` | 定义「这台机器上 mod 在哪个文件夹」，**只有这里能写 `path`** |
| mod 侧描述符 | `<mod 文件夹>/descriptor.mod` | 定义与具体用户无关的 mod 信息，随 mod 一起分发 |

文件名决定加载顺序（除非被 `dependencies` 覆盖），**文件名不能含空格**。Steam 创意工坊的 mod 形如 `mod/ugc_1234567890.mod`。

启动器的「所有已安装 mod → 上传 mod → 创建 mod」能生成这对文件，但路径位置和可填字段都受限，多半还要手工编辑。

### 1.3 描述符字段

启动器能设的：

```
name = "Average mod"
path = "mod/modname"
picture = "thumbnail.png"
version = "v1"
supported_version = "1.13.*"
tags={
	"Gameplay"
	"Historical"
}
remote_file_id="1678247250"
```

| 字段 | 取值 | 说明 |
|---|---|---|
| `name` | 字符串 | 启动器显示名。**必须全局唯一**，`dependencies` 靠它匹配 |
| `path` | 相对或绝对路径 | mod 根目录。相对路径以用户目录为基准。**只能用 ASCII**，分隔符必须是正斜杠 `/`。只写在用户侧描述符 |
| `picture` | 文件名 | 缩略图，必须放在 mod 根目录，体积 < 1MB。**本地 mod 不显示图片**，只有工坊/Paradox Mods 才有 |
| `version` | 任意字符串 | 启动器显示用，不参与任何逻辑 |
| `supported_version` | 版本号 | 不匹配时启动器打「过期」标记。末位可写 `*` 表示该大版本内任意小版本 |
| `tags` | 字符串列表 | 工坊/Paradox Mods 分类 |
| `remote_file_id` | 数字 | 关联工坊条目，用于启动器内更新 |

只能手写、启动器不给设的：

```
user_dir = "NewSaveFolder"
dependencies = { "Major Mod" "Major Mod 2" }
replace_path = "history/states"
replace_path = "map/strategicregions"
```

| 字段 | 说明 |
|---|---|
| `user_dir` | 改存档目录名。不同 `user_dir` 的 mod 与本体的存档互不兼容，等于强制隔离存档 |
| `dependencies` | **强制本 mod 排在列表内所有 mod 之后加载**。它不表示「依赖这些 mod 才能跑」，而是「加载顺序在它们后面」。子 mod 必须写这个，否则父 mod 的 `replace_path` 会把你的文件一起卸掉 |
| `replace_path` | 见 1.4 |

`dependencies` 里的名字必须与对方 `.mod` 的 `name` **逐字符一致**，包括破折号类型（`–` 与 `-` 不是一个字符）。最稳的做法是从对方的 `.mod` 文件里复制，不要从启动器界面手打。

### 1.4 replace_path 的真实语义

`replace_path` 在**主菜单加载阶段**卸载此前已加载的、指定文件夹内的**直接子文件**（不含子文件夹）。

它的边界非常明确，误用会踩坑：

- **不改变加载顺序**。排在它前面的 mod 或本体照样先加载，只是这些文件随后被卸载。要让文件真正覆盖别人，靠 `dependencies` 排顺序。
- **只管索引加载，不管直接链接加载**。`replace_path = "history/units"` 毫无作用，因为 OOB 文件是通过 `oob = "TAG_1936"` 直接点名加载的。同理 `replace_path = "gfx/flags"` 也无效：国旗是在国家切换意识形态组时才按文件名加载的。加载画面同理：`replace_path = "gfx/loadingscreens"` 能屏蔽原版读取界面，但主菜单背景不变，因为它是 `interface/frontendmainviewbg.gfx` 里直接指向图片的 sprite。
- **必须同时写在两个描述符里**。只写 mod 侧，启动器会把它从用户侧删掉；只写用户侧，它不生效（其它字段启动器会自动抄，这个不会）。
- **会崩游戏**。有些文件夹一旦为空，游戏没有兜底逻辑，例如国策树为空直接崩。另一些文件夹的条目除「给人看」外还有硬编码用途，卸载后触发莫名错误（例如脚本化触发器被卸掉导致抵抗系统异常启动）。
- 使用前提：被替换的文件夹里**你自己的 mod 至少要放一个含内容的文件**，并且逐条核对原版该文件夹里有什么值得保留。

典型用法只有一种：大改地图时 `replace_path = "history/states"`、`replace_path = "map/strategicregions"`，确保原版州文件不会被混进来。

### 1.5 加载顺序与文件生效规则

本体先加载，mod 后加载。顺序决定两件事：

1. **同名同路径文件，后加载的胜出**。只针对单文件，不针对「整文件夹」。不可能出现「两个同名文件都生效」，游戏只会读后加载的那个。
2. **文件夹不合并，但文件会逐层覆盖**。mod 根目录下的 `common/national_focus/` 与本体同名目录在逻辑上叠加，同名文件互相覆盖，不同名文件共存。

由此引出的实战规则：

- 新增内容 → 起一个别人不会用的文件名，塞进同名目录。
- 改原版内容 → 复制原版文件到 mod 同名路径，改完保存。但要承担随版本更新的维护成本，尽量改用 `scripted_effect` 替换、`replace_path`、或直接在新增文件里重定义同一 id（后者对 `ideas`、`decisions` 这类 id 寻址的系统有效，对国策树这类整文件解析的系统无效）。
- **大小写不同但拼写相同的文件名会被加载两次**：`events/Generic.txt` 与 `events/GENERIC.txt` 同时存在时，mod 那份会被读两次。即使用了 `replace_path` 卸掉本体文件夹，这个现象依然存在。文件名要么与本体完全一致，要么完全不同。

### 1.6 启用列表与启动器缓存

| 文件 | 作用 |
|---|---|
| `dlc_load.json` | 已启用 mod 与禁用 DLC 的清单，`enabled_mods` 内是 `.mod` 的短路径，如 `"mod/modname.mod"`。可在不启动启动器的情况下手改开关。写多个 `enabled_mods` 定义时，游戏用第一个 |
| `launcher-v2.sqlite` / `launcher-v2_openbeta.sqlite` | 启动器的 mod 与播放集数据库。启动器偶尔会卡在「无效路径」等错误上，删掉此文件让游戏重建即可恢复 |

### 1.7 目录映射总表

mod 根目录等价于本体根目录。常用位置：

| 内容 | 路径 |
|---|---|
| 国家 tag 注册 | `common/country_tags/*.txt` |
| 国家定义（颜色、意识形态） | `common/countries/*.txt` |
| 国家历史（政治、科技、OOB 引用） | `history/countries/TAG - Name.txt` |
| 州 | `history/states/NNN-Name.txt` |
| 国策树 | `common/national_focus/*.txt` |
| 事件 | `events/*.txt` |
| 决议 | `common/decisions/*.txt`、分类在 `common/decisions/categories/` |
| 国家精神 | `common/ideas/*.txt` |
| 角色 | `common/characters/*.txt` |
| 科技 | `common/technologies/*.txt` |
| 装备原型 | `common/units/equipment/*.txt` |
| 单位（营）定义 | `common/units/*.txt` |
| OOB | `history/units/*.txt` |
| 修正定义 | `common/modifiers/`、`common/dynamic_modifiers/` |
| 脚本化效果/触发器 | `common/scripted_effects/*.txt`、`common/scripted_triggers/*.txt` |
| 脚本化本地化 | `common/scripted_localisation/*.txt` |
| 钩子 | `common/on_actions/*.txt` |
| 游戏规则 | `common/game_rules/*.txt` |
| AI 策略 | `common/ai_strategy/*.txt`、`common/ai_strategy_plans/*.txt`、`common/ai_templates/*.txt` |
| 界面定义 | `interface/*.gui`、`interface/*.gfx` |
| 图形资源 | `gfx/interface/`、`gfx/flags/` |
| 本地化 | `localisation/<语言>/*.yml` |
| 音乐 | `music/*.txt` + `sound/*.asset` |
| 常量覆盖 | `common/defines/*.lua` 风格的 `NDefines.xxx` 文本文件 |
| 剧本起点 | `common/bookmarks/*.txt` |

> 一个常见误解：把文件多套一层目录（如 `mod/yourmod/test/common/national_focus/`）不会报错，但也**完全不会被当作国策读取**，表现为「文件被无视」。

### 1.8 最小可跑 mod 骨架

新建 mod 只要这几个文件就能进游戏并被加载。以下内容与本地 `mods/muvluvCNsub_xuerong` 的实际结构一致。

```
我的mod/
├─ descriptor.mod
├─ thumbnail.png
├─ events/
│   └─ mymod_events.txt
└─ localisation/
    └─ simp_chinese/
        └─ mymod_l_simp_chinese.yml
```

用户目录 `mod/mymod.mod`（只有这个文件写 `path`）：

```
name="我的mod"
path="mod/mymod"
picture="thumbnail.png"
version="0.1.0"
tags={
	"Gameplay"
}
supported_version="1.19.*"
```

`我的mod/descriptor.mod`（去掉 `path`，其余保持一致）：

```
name="我的mod"
picture="thumbnail.png"
version="0.1.0"
tags={
	"Gameplay"
}
supported_version="1.19.*"
```

`events/mymod_events.txt`（`.txt`，UTF-8 无 BOM）：

```
add_namespace = mymod

country_event = {
	id = mymod.1
	title = mymod.1.t
	desc = mymod.1.d

	is_triggered_only = yes

	immediate = {
		add_political_power = 50
		log = "mymod.1 fired"
	}

	option = {
		name = mymod.1.a
	}
}
```

`localisation/simp_chinese/mymod_l_simp_chinese.yml`（`.yml`，UTF-8 **带 BOM**，首行语言头不能少）：

```
l_simp_chinese:
 mymod.1.t:0 "我的第一个事件"
 mymod.1.d:0 "这个事件由 mymod.1 触发。"
 mymod.1.a:0 "知道了"
```

验证顺序：

1. 启动器里能看到「我的mod」且没有过期标记 → 描述符与 `supported_version` 正确。
2. 进游戏控制台 `debug`，输入 `event mymod.1` → 事件触发、政治点 +50、`logs/game.log` 出现 `mymod.1 fired`。
3. 退出后看 `logs/error.log`，若出现 `Malformed token: mymod.1` 说明漏了 `add_namespace`；若事件名显示成 `mymod.1.t` 说明 `.yml` 没带 BOM 或文件名没以 `_l_simp_chinese.yml` 结尾。

四个高频失败点，对照本节即可定位：`path` 指向错目录、`.yml` 缺 BOM、事件没写 `add_namespace`、目录多套了一层（如 `mymod/test/events/` 不会被当作事件目录）。

---

## 第 2 章 Clausewitz 脚本语法

HOI4 的脚本不是编程语言，是一棵**键值树**。游戏读文件时把它解析成嵌套的「键 → 值/子块」，所有系统的写法都是这棵树的变形。

### 2.1 三种基本形态

```
# 1. 纯键值
has_stability > 0.5
stability = 0.3

# 2. 带子块的键（块内继续写键值，层数不限）
add_stability = {
    value = 0.1
    days = 30
}

# 3. 列表（空格分隔，可换行，不能加逗号）
tags = {
    "Gameplay"
    "Historical"
}
```

规则细节：

- 赋值用 `=`。比较也用 `=`，语义由上下文决定：在 trigger 里 `stability = 0.3` 表示「精确等于」，在 effect 里表示「设为 0.3」。
- 比较运算符：`>`、`<`、`>=`、`<=`。写在触发器里时，`has_stability > 0.5` 与 `has_stability = { value = 0.5 operator = greater_than }` 等价，前者是后者的简写。
- 字符串加双引号。含空格、非 ASCII、或可能与关键字冲突的字符串必须加引号；纯标识符可以不加（`ideology = neutrality` 与 `ideology = "neutrality"` 等价），但**加引号永远安全**，养成习惯最好。
- 布尔值写 `yes` / `no`，不是 `true` / `false`。少数位置也接受 `true`/`false`，但 `yes`/`no` 是通用写法。
- 数字不带单位；比例一律用小数（`0.25` 表示 25%），不是 `25`。这一条在修正和触发器中到处适用。
- 日期写 `1936.1.1` 或 `1936.1.1.0`（时.分），也可写 `1936.1.1.12`。月份日期不补零。
- 注释用 `#`，到行尾结束。**没有多行注释**。被 `#` 吃掉的内容除了「防止执行」还可以用来写「为什么这么写」。
- 没有变量声明、没有函数、没有 `if/else` 语法关键字以外的控制流。分支靠 `if = { limit = { ... } ... }`、`else`、`while_loop`、`for_each_scope_loop`。

### 2.2 编码

| 文件类型 | 编码 |
|---|---|
| `.txt`、`.gui`、`.gfx`、`.asset`、`.lua`（defines） | UTF-8 **无 BOM** |
| `.yml`（本地化） | UTF-8 **带 BOM** |

用错的表现：本地化全部显示成键名（BOM 缺失或编码不对）、文本出现乱码方块（存成了 GBK）、文件整个不加载（BOM 出现在 `.txt` 开头）。

编辑器的坑：Atom 不支持完整 BOM，做本地化会出事。VS Code 右下角能切 `UTF-8 with BOM`，改完保存前确认一次。

### 2.3 缩进与括号

缩进不影响解析，但**括号影响，而且是致命的**。规范：

- 首行不缩进，一级缩进用 1 个 tab 或 4 个空格，同一文件内保持一致。
- 一对开闭括号必须处于同一缩进层级。
- 某行引入了未闭合的 `{`，其后所有内容整体右移一级，直到对应的 `}`。
- 一行最多一个同类括号。
- 只有 `}` 的行，前面除缩进外不能再有别的东西。

**多余右括号会让整个文件从这里开始停止解析**。这条比缩进错误严重得多：`error.log` 里不会给你逐条报错，而是「文件后半段全部没生效」。

```
capital = 123
set_convoys = 321

set_technology = {
    infantry_weapons = 1
}
}                                    # 多余的右括号

set_politics = {                     # 以下全部被忽略
    ideology = neutrality
    elections_allowed = no
}
```

在 `history/countries/` 这类「文件顶层不强制包一块」的文件里，一个多余右括号就够让文件当场终止，症状是「国家历史只生效了一半」。

少一个右括号的表现不同：游戏会把后续文件的顶层键当作当前块的子键吞进去，`error.log` 里出现大量 `Unexpected token`，或干脆报 scope 错误。

### 2.4 用编辑器自查括号

任何能高亮括号配对、能折叠代码块的编辑器都行。判断方法：从 `{` 所在行往下沿着缩进引导线走，能顺畅走到对应的 `}` 就是对的；引导线被打断的位置就是漏了缩进或漏了括号。

反例（`my_idea_2` 被写进了 `my_idea_1`，因为它打断了 `my_idea_1` 到 `}` 的引导线）：

```
ideas = {
    country = {
        my_idea_1 = {
            modifier = {
                political_power_gain = 0.1
            }
        my_idea_2 = {        # 打断了 my_idea_1 的引导线，实际在 my_idea_1 内部
        }
    }
}
```

### 2.5 加载与解析的边界

- 每个文件独立解析，一个文件崩不影响另一个文件的加载（但会污染 `error.log` 的定位）。
- 同一目录下所有 `.txt` 都会被读，文件名任意。想「停用」某个文件，把文件名改成不匹配的扩展名（`.txt.bak`），而不是清空内容——空文件与原版同名文件共存时仍会覆盖原版。
- 注释掉的代码不参与解析，但保留在文件里便于回退。

---

## 第 3 章 作用域（Scopes）与数据选择器

### Scopes

URL：`https://hoi4.paradoxwikis.com/index.php?title=Scopes&action=raw`（1.13）

### 语法规则

- 统一形态 `scope = { <contents> }`。
- 作用：切换"当前被操作的实体"。作为 effect 时，块内每条 effect 都对该实体执行；作为 trigger 时，块内所有 trigger 必须同时为真（逻辑 AND）。
- 三种用途分类，用错位置会静默失败：
  - **trigger scope**：只能放 trigger 块，放进 effect 块直接失败。
  - **effect scope**：只能放 effect 块。
  - **dual scope**：两边都能用；只有部分 dual scope 能当"目标"（`transfer_state_to = ROOT`、`owns_state = 123`）。
- 四种批量前缀（非 dual scope 常见形态）：

| 前缀 | 类型 | 语义 |
|---|---|---|
| `all_<object>` | trigger scope | 遍历全部，遇到一个 false 即返回 false，否则 true |
| `any_<object>` | trigger scope | 遇到一个 true 即返回 true；支持 `count = <int>/<variable>` |
| `every_<object>` | effect scope | 对每个满足 `limit` 的对象按顺序执行 effect |
| `random_<object>` | effect scope | 对一个随机满足 `limit` 的对象执行 |

- 六类目标域：country / state / character / division / MIO / contract（+ special project）。**只能使用与目标域匹配的 effect/trigger**，例如 `add_building_construction` 只能出现在 state scope，国家要用 `add_offsite_building`。
- 非 dual scope **不能选中不存在的国家**，例外 `every_possible_country`。

### 可选设置字段

| 字段 | 类型 | 作用 | 示例 |
|---|---|---|---|
| `limit` | trigger block | 仅 effect scope 可用；对每个候选目标求值，过滤执行对象 | `limit = { num_of_military_factories > 5 }` |
| `random_select_amount` | int | 仅 `every_` 型；随机截取至多 N 个目标 | `random_select_amount = 3` |
| `include_invisible` | bool | 让 `every_/random_` 型 unit leader、MIO scope 包含 `visible` 未满足的对象 | `include_invisible = yes` |
| `tooltip` | loc key | 替换该 scope 在提示框里的标题 | `tooltip = any_friendly_country_tt` |
| `display_individual_scopes` | bool | `every_` 型把合并的目标列表拆成逐条显示 | `display_individual_scopes = yes` |
| `visible_when_empty` | bool | 无有效目标时仍显示该 scope 的 effect 行 | `visible_when_empty = yes` |
| `prioritize` | state id 列表 | 仅 `random_` 型且目标为 state；优先在这些州里选 | `prioritize = { 123 321 }` |

`limit` 内多条 trigger 是 AND；**不能用于 trigger scope 或 dual scope**，只用于 effect scope。`party_leader` 的 `limit` 必须含 `has_ideology`。

### Dual scopes 字段表

| 字段 | 类型 | 作用 | 示例 |
|---|---|---|---|
| `TAG` | country scope | 按国家 tag / tag alias 定位；原 tag 不存在时回落到该 tag 派生的动态国家 | `SOV = { country_event = my_event.1 }` |
| `<state_id>` | state scope | 州县 ID | `123 = { transfer_state_to = SCO }` |
| `<character>` | character scope | 角色 ID（1.12.8 前须已被该国招募） | `ENG_theodore_makhno = { set_nationality = UKR }` |
| `mio:<MIO>` | MIO scope | 仅国家域内；`common/military_industrial_organization/organizations/*.txt` | `mio:AST_cockatoo_doe_organization = { ... }` |
| `sp:<special_project>` | special project scope | 仅国家域内（1.15） | `sp:sp_land_flamethrower_tank = { ... }` |
| `ROOT` | 依上下文 | 块根节点；焦点里=做焦点的国家，事件里=接事件的国家 | `target = ROOT` |
| `THIS` | 依上下文 | 当前 scope；主要用于 variables 与内建本地化命令 | `set_temp_variable = { target_country = THIS }` |
| `PREV` | 依上下文 | 上一层 scope，可链式 `PREV.PREV` | `target = PREV` |
| `FROM` | 依上下文 | 块内建的第二 scope（事件=发出方，targeted decision=被指向方），可链式 `FROM.FROM` | `target = FROM` |
| `overlord` | country scope | 宗主国 | `overlord = { ... }` |
| `faction_leader` | country scope | 阵营领袖（1.10.1） | `faction_leader = { add_to_faction = FROM }` |
| `owner` | country scope | state/character/combatant 域内：州所有者 / 招募该角色的国家 / 师的所有者 | `owner = { add_ideas = owns_this_state }` |
| `controller` | country scope | state 域内：州控制者 | `controller = { ROOT = { ... } }` |
| `capital_scope` | state scope | 当前国家首都所在州 | `capital_scope = { ... }` |
| `event_target:<key>` | 依上下文 | 已保存的事件目标，冒号后不能有空格 | `event_target:my_event_target = { ... }` |
| `var:<variable>` | 依上下文 | 指向 scope 的变量；当"目标"用时 `var:` 多可省略 | `var:my_variable = { ... }` |

### 可复制代码块

```hoi4
# effect scope：对苏联加稳定与战争支持
SOV = {
    add_stability = 0.1
    add_war_support = 0.2
}
```

```hoi4
# trigger scope：州 123 必须由英国拥有、由爱尔兰控制
123 = {
    is_owned_by = ENG
    is_controlled_by = IRE
}
```

```hoi4
# 非 dual scope 不能当目标，用 PREV 绕开
random_country = {
    ROOT = { add_to_faction = PREV }
}
```

```hoi4
# limit 用法：只对军工厂 >5 的邻国要军通
every_neighbor_country = {
    limit = {
        num_of_military_factories > 5
    }
    give_military_access = ROOT
}
```

```hoi4
# every_ + random_select_amount
every_country = {
    random_select_amount = 3
    country_event = lottery_win.0
}
```

```hoi4
# random_ 型针对州时优先 123/321
random_owned_controlled_state = {
    prioritize = { 123 321 }
    limit = {
        is_core_of = PREV
    }
    add_building_construction = {
        type = industrial_complex
        level = 1
        instant_build = yes
    }
}
```

```hoi4
# tooltip 替换 + hidden_trigger 充当隐藏 limit
any_country = {
    hidden_trigger = {
        has_opinion = { target = PREV value > 50 }
    }
    tooltip = any_friendly_country_tt
    has_war_with = ITA
}
```

```hoi4
# 空目标时仍显示提示
every_other_country = {
	limit = {
		is_in_faction_with = ROOT
	}
	tooltip = ALL_OTHER_FACTION_MEMBERS
	visible_when_empty = yes
	add_political_power = 100
}
```

```hoi4
# 数组 scope：遍历数组中的 scope
for_each_scope_loop = {
    array = global.majors
    if = {
        limit = { NOT = { tag = ROOT } }
        random_owned_controlled_state = {
            transfer_state_to = ROOT
        }
    }
}
```

### 常见错误 / 限制

- **`Invalid event target`**：日志形如 `controller: invalid event target: controller`。含义是该 dual scope 在当前位置没有可指向对象（例如州无控制者）。游戏中该段 effect 会被整段跳过，作为 trigger 时既不真也不假；每 tick 检查会刷错误日志。修法是保证每州都有 owner/controller，或用 `if = { limit = { is_subject = yes } overlord = { ... } }` 先判存在性再取 scope。
- 非 dual scope 不能当目标；`add_to_faction = random_country` 是无效语法。
- `PREV` 在 `all_/every_` 型里会把工具提示指向"第一个可能的目标"，导致提示与实际执行不一致；需用 `hidden_effect` + `custom_effect_tooltip` / `custom_trigger_tooltip` 覆盖。
- `every_` 型不加 `display_individual_scopes = yes` 时，多目标共用第一目标的 if 分支结果，提示会误报。
- `tooltip` 键在 `NOT` 内需额外定义 `<key>_NOT`。
- effect scope 中 `limit` 缺失时不过滤；`random_` 型不加 `limit` 可能选到不合格对象并静默无操作。
- `prioritize` 只对 state 目标的 `random_` 型有效，国家/角色不行。
- 作用域错误是静默的：把 state trigger 放进 country scope 不会报错，只是永不成立。

### 改变 scope 的 effect

| effect | 目标域 | 作用 |
|---|---|---|
| `start_civil_war` | country | 引发内战，scope 变为叛乱动态国家 |
| `create_dynamic_country` | country | 新建动态国家，scope 变为它 |

`start_civil_war` 参数（节选，完整见 `Effect.wiki`）：`ideology`（必填）、`ruling_party`、`size`（默认 0.5）、`army_ratio`、`navy_ratio`、`air_ratio`、`capital`、`states`（可 `all`）、`states_filter`、`keep_unit_leaders`、`keep_unit_leaders_trigger`、`keep_political_leader`、`keep_political_party_members`、`keep_all_characters`、块内 effects。

明确写出的限制：`states = all` 包含该国控制的所有州；**若当前首都州被划入叛乱方则内战不触发**，需先 `set_capital`，内战结束后用 `on_civil_war_end` 还原。内战固定禁止选举；用 `ruling_party` 时原国家也禁止选举。此 effect 不能用于 history 或 bookmark 的 `effect = { }`；要多方混战需用 `create_dynamic_country` + `add_civil_war_target` 模拟。

---

## 第 4 章 触发器（Triggers）与事件目标

### Triggers

URL：`https://hoi4.paradoxwikis.com/index.php?title=Triggers&action=raw`（1.16，页面标题 Triggers，正文自称 Conditions）

### 语法规则

- 三种运算符：`=`、`>`、`<`。
  - `=` 是**严格等于**（与前作不同，不表示"大于等于"），也可用于开块：`has_opinion = { target = GRE value < -10 }`。
  - `>` / `<` 是严格比较，`has_political_power > 100` 在正好 100 时为假。
  - 未特别注明时，trigger 只支持 `=`。
- `yes` / `no` **区分大小写**，不得含大写。
- 三个通用上下文 scope：country / state / character。trigger 只在所属域生效，放错域不会报错但不生效。
- 多数 trigger 块默认是 AND，遇 false 立即停止。
- 官方另附完整列表：`documentation/triggers_documentation.html` / `.md`（1.17.1.1 时该文件更新至 1.17.0）。

### Flow control 字段表

| 字段 | 类型 | 作用 | 示例 |
|---|---|---|---|
| `AND` | 块 | 全真为真，遇 false 停 | `AND = { original_tag = GER has_stability > 0.5 }` |
| `OR` | 块 | 任一真为真，遇 true 停 | `OR = { original_tag = ENG original_tag = USA }` |
| `NOT` | 块 | 任一真则为假（即 NOR） | `NOT = { has_stability > 0.5 }` |
| `count_triggers` | 块 + `amount` | 子 trigger 真值求和 ≥ amount 则真（1.5） | `amount = 2` |
| `if` / `else_if` / `else` | 块 | `limit` 为真则按 AND 求值子 trigger；limit 不成立时返回 true | `if = { limit = { has_dlc = "Waking the Tiger" } has_war_support > 0.5 }` |
| `hidden_trigger` | 块 | 隐藏内部 tooltip，同时充当 AND | `hidden_trigger = { country_exists = GER }` |
| `custom_trigger_tooltip` | `tooltip` | 用自己的本地化键替换内部 tooltip（别名为 custom_override_tooltip） | `tooltip = sunrise_invasion_tt` |
| `custom_override_tooltip` | `tooltip` / `not_tooltip` | AND 块 + 自定义正/负 tooltip（1.15） | `not_tooltip = MY_TOOLTIP_NOT` |

`NOT` 可用来"模拟 ≥ / ≤"：例如 `NOT = { has_stability < 0.5 }` 等价于 ≥0.5。NAND 无直接写法，用 `NOT = { AND = { … } }`。

### Any scope 常用 trigger

| 字段 | 类型 | 作用 | 示例 |
|---|---|---|---|
| `always` | bool | 恒真/恒假，调试用 | `always = yes` |
| `has_global_flag` | string / 块 | 全局 flag 是否存在；块形式可加 `days`、`date`、`value` | `has_global_flag = { flag = my_flag days > 30 value > 0 }` |
| `has_dlc` | string | DLC 是否启用 | `has_dlc = "Waking the Tiger"` |
| `has_start_date` | date | 本局起始日期（必须用 > 或 <） | `has_start_date > 1950.01.01` |
| `date` | date | 当前日期（必须用 > 或 <） | `date < 1950.01.01` |
| `difficulty` | int | 难度（必须用 > 或 <） | `difficulty > 0` |
| `country_exists` | scope/var | 国家是否存在 | `country_exists = GER` |
| `is_ironman` | bool | 铁人模式 | `is_ironman = yes` |
| `is_historical_focus_on` | bool | 历史国策开关 | `is_historical_focus_on = yes` |
| `threat` | float | 世界紧张度（必须用 > 或 <） | `threat > 0.5` |
| `has_game_rule` | 块 | 游戏规则取值 | `has_game_rule = { rule = GER_can_remilitarize_rhineland option = yes }` |
| `has_variable` | var | 变量是否已赋值（值为 0 也算已赋值） | `has_variable = my_var` |
| `check_variable` | 块或简写 | 比较变量；`compare` 默认 `greater_than_or_equals` | `check_variable = { my_var > 10 }` |
| `log` | string | 写 game.log（effect/trigger 通用） | `log = "v=[?myVar]"` |
| `print_variables` | 块 | 导出变量到 `logs/variable_dumps/` | `file = "my_dump_file"` |

`has_global_flag` / `has_country_flag` 的块形式若省略 `value` 比较，默认按 `>0` 判断；`value` 限定 −32768..32767。

### Country scope 常用 trigger

| 字段 | 类型 | 作用 | 示例 |
|---|---|---|---|
| `exists` | bool | 当前 scope 是否存在 | `exists = yes` |
| `tag` | scope/var | 是否为目标 tag（不含动态国家） | `tag = GER` |
| `original_tag` | scope/var | 是否源自目标 tag（含内战/动态国家） | `original_tag = GER` |
| `is_ai` | bool | 是否 AI | `is_ai = yes` |
| `has_country_flag` | string/块 | 国家 flag | `has_country_flag = my_flag` |
| `has_cosmetic_tag` | string | 外观 tag | `has_cosmetic_tag = SOV_custom` |
| `has_event_target` | key | 是否已保存该事件目标 | `has_event_target = my_var` |
| `has_decision` | string | 决议是否已激活 | `has_decision = my_decision` |
| `has_dynamic_modifier` | 块 | 是否带某动态修正（可加 `scope`） | `{ modifier = my_dynamic_modifier scope = GER }` |
| `has_active_mission` | string | 任务是否在进行 | `has_active_mission = my_mission` |
| `has_collaboration` | 块 | 对目标国的合作度（0–1 标度，必须用 < 或 >） | `{ target = GER value > 0.5 }` |
| `has_manpower` | float/var | 人力（必须用 > 或 <，`=` 是精确值） | `has_manpower > 1000` |
| `num_divisions` | int | 师数量（必须用 > 或 <） | `num_divisions > 5` |
| `has_army_size` | 块 | 师数量，可按 `type` 限定 | `{ size > 10 type = armor }` |
| `has_navy_size` | 块 | 舰船数量，可按 `type` / `archetype` 限定 | `{ size > 10 type = capital_ship }` |
| `has_deployed_air_force_size` | 块 | 飞机数量，可按 `type` 限定 | `{ size > 10 type = cas }` |
| `strength_ratio` | 块 | 对目标国的师数比（对方无师时按 1；己方空军更强 +10%） | `{ tag = GER ratio > 1 }` |
| `num_of_nukes` | int | 核弹数 | `num_of_nukes > 5` |
| `casualties` / `casualties_k` | int | 伤亡（个 / 千） | `casualties_k > 10` |
| `has_attache_from` | scope | 是否有该国武官 | `has_attache_from = GER` |
| `is_lend_leasing` | scope | 是否在租借给该国 | `is_lend_leasing = GER` |
| `has_template` | string | 是否有该名师模板 | `has_template = "Infantry Division"` |
| `has_equipment` | 块 | 装备库存量 | `{ infantry_equipment_1 > 10 }` |
| `stockpile_ratio` | 块 | 库存/在役比率（运输船例外，按绝对数量） | `{ archetype = infantry_equipment ratio > 0.5 }` |
| `has_doctrine` | token | 是否已启用某大学说/子学说（1.17） | `has_doctrine = mobile_warfare` |
| `has_mastery` | 块 | 某 track 的精通点数 | `{ amount = 200 track = infantry }` |
| `has_military_industrial_organization` | token | 是否有该 MIO | `has_military_industrial_organization = infantry_mio_token` |
| `pc_total_score` / `pc_current_score` | decimal | 和平会议分数（只对战胜国有效） | `pc_total_score > 2400` |
| `pc_is_winner` 等 `pc_*` | bool/scope | 和平会议身份判定（1.12） | `pc_is_winner = yes` |

### 可复制代码块

```hoi4
# flow control
count_triggers = {
    amount = 2
    10 = { state_population > 100000 }
    11 = { state_population > 100000 }
    12 = { state_population > 100000 }
}
```

```hoi4
# if 在 trigger 里：limit 不成立时整块返回 true
if = {
    limit = {
        has_dlc = "Poland: United and Ready"
    }
    has_political_power > 100
}
else_if = {
    limit = {
        has_dlc = "Waking the Tiger"
    }
    has_war_support > 0.5
}
else = {
    always = no
}
```

```hoi4
# 自定义 tooltip（含 NOT 反向键）
custom_trigger_tooltip = {
    tooltip = sunrise_invasion_tt
    any_state = {
        is_owned_by = JAP
        is_on_continent = europe
        is_coastal = yes
    }
}
```

```hoi4
# 变量 trigger：state scope 里读国家变量
country = {
    state = {
        limit = {
            check_variable = { from.my_country_var > 0.0 }
        }
    }
}
```

### 常见错误 / 限制

- 变量有作用域归属，**不能**在 state scope 里直接读国家变量，必须先 `from.` / 具体 tag 前缀。
- `yes`/`no` 写大写不生效。
- 数值型 trigger 大多必须用 `>` 或 `<`，用 `=` 表示精确值，几乎永远为假。
- `if` 的 `limit` 永远不会显示给玩家；limit 不成立时整条 trigger 返回 true（trigger 版与 effect 版语义不同）。
- 未在 trigger scope 中显式支持 `limit`，要过滤请把 trigger 放进 `if = { limit = { … } }`。
- `has_start_date`、`date`、`difficulty`、`threat`、`convoy_threat`、`mine_threat` 等只接受 `>` / `<`。

### 事件目标（Event targets）

请求 URL：`https://hoi4.paradoxwikis.com/index.php?title=Event_target&action=raw`
返回：`#REDIRECT [[Data structures#Event targets]]`
实体内容 URL：`https://hoi4.paradoxwikis.com/index.php?title=Data_structures&action=raw&section=7`

### 语法规则

- 事件目标 = 指向某个 scope（国家/州/角色）的指针；一个事件目标同时只能指向一个 scope，一个 scope 可有多个事件目标。
- 无固定目录，任何事件块里都能赋值。
- 两类，区别只在清除时机：

| 类型 | 赋值 effect | 生命周期 | 清除方式 |
|---|---|---|---|
| 全局（global） | `save_global_event_target_as = my_event_target` | 永久 | `clear_global_event_target = key` / `clear_global_event_targets = <scope>`（手动） |
| 普通（regular） | `save_event_target_as = my_event_target` | 当前 effect 块及其触发的事件链 | 自动，无法手动清除 |

- 引用：`event_target:my_event_target`，既能当 scope 也能当目标。
- 检查存在：`has_event_target = key`。
- 重复 `save_global_event_target_as` 会改指向到当前执行处的 scope。
- 本地化里作命名空间**不需要** `event_target:` 前缀：`[TAG_democratic_side.GetName]`。
- 少数 effect 块（如 scripted diplomatic actions）无法设置事件目标。

```hoi4
start_civil_war = {
    size = 0.5
    ideology = democratic
    save_global_event_target_as = TAG_democratic_side
}
```

```hoi4
event_target:TAG_democratic_side = {
    transfer_state = 123
}
transfer_units_fraction = {
    target = event_target:TAG_democratic_side
    size = 0.2
}
```

```hoi4
random_owned_controlled_state = {
    save_event_target_as = target_state
}
country_event = { id = mod_event.0 days = 10 }
```

```hoi4
123 = {
    save_event_target_as = demanded_prov_target
}
TAG = {
    country_event = generic.23
}
```

### 常见错误 / 限制

- 普通事件目标出了 effect 块（及其触发的事件链）即失效，跨块复用必须用 global 版。
- `event_target:` 冒号后不能有空格。
- 指向的对象被吞并/删除后再用会得到 `invalid event target`（与 Scopes 节同一类错误）。
- 全局事件目标不会被自动清理，需在 `on_civil_war_end` 之类节点手动清。
- Scripted GUI 中不能用 `save_event_target_as` / `save_global_event_target_as`。

### 国家作用域：情报、AI、角色、和平会议

country scope。共 24 条。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `estimated_intel_max_piercing` | `tag = <scope>` 目标国；`value = <int>` 比较值 | 依当前作用域对该国的情报，检查其最大 piercing | `estimated_intel_max_piercing = { tag = GER value > 2 }` |
| `estimated_intel_max_armor` | `tag = <scope>`；`value = <int>` | 依情报检查该国最大 armor | `estimated_intel_max_armor = { tag = GER value > 2 }` |
| `compare_intel_with` | `target = <tag>/<variable>`；`civilian_intel`、`army_intel`、`navy_intel`、`airforce_intel` 各可接 `<>= <float>/<variable>` | 比较两国情报量 | `compare_intel_with = { target = POL civilian_intel > 0.5 army_intel = 0 navy_intel < 0 }` |
| `intel_level_over` | `target = <tag>/<variable>`；同上四个 intel 子键 | 检查当前国对目标国的情报等级 | `intel_level_over = { target = POL civilian_intel > 0.5 army_intel = 0 navy_intel < 0 }` |
| `has_intelligence_agency` | `<boolean>` | 是否有情报机构 | `has_intelligence_agency = yes` |
| `network_national_coverage` | `target = <tag>/<variable>`；`value <> <float>/<variable>` | 检查对某国的情报网全国覆盖率 | `network_national_coverage = { target = POL value < 70 }` |
| `network_strength` | `target = <tag>`；`state = <id>/<variable>`；`value <> <float>/<variable>` | 检查情报网强度 | `network_strength = { target = POL value < 70 }` |
| `has_done_agency_upgrade` | `<string>` 机构升级 token | 是否已完成指定机构升级（到最高级） | `has_done_agency_upgrade = upgrade_army_department` |
| `agency_upgrade_number` | `<int>/<variable>` | 已完成的机构升级数量 | `agency_upgrade_number > 4` |
| `decryption_progress` | `target = <tag>`；`value <> <float>` | 对某国的破译进度 | `decryption_progress = { target = POL value < 0.5 }` |
| `has_captured_operative` | `<tag>` 或 `<bool>` | 是否俘获过特工（可指定是哪个国家的） | `has_captured_operative = POL` / `has_captured_operative = yes` |
| `has_finished_collecting_for_operation` | `target = <tag>`；`operation = <token>` | 对目标国某行动的资源收集是否完成 | `has_finished_collecting_for_operation = { target = POL operation = operation_infiltrate_armed_forces_navy }` |
| `is_preparing_operation` | `target = <tag>`；`operation = <token>`（可选） | 是否正在筹备针对该国的行动 | `is_preparing_operation = { target = POL operation = operation_infiltrate_armed_forces_navy }` |
| `is_running_operation` | `target = <tag>`；`operation = <token>`（可选） | 是否正在执行针对该国的行动 | `is_running_operation = { target = POL operation = operation_infiltrate_armed_forces_navy }` |
| `num_finished_operations` | `target = <tag>`；`operation = <token>`（可选） | 对该国已完成的行动数 | `num_finished_operations = { target = POL operation = operation_infiltrate_armed_forces_navy }` |
| `has_operation_token` | `tag = <tag>`；`token = <token>` | 是否持有针对该国的行动 token | `has_operation_token = { tag = POL token = token_name }` |
| `is_active_decryption_bonuses_enabled` | `<tag>` | 对该国的破译加成是否存在 | `is_active_decryption_bonuses_enabled = POL` |
| `is_cryptology_department_active` | `<bool>` | 密码学部门是否启用 | `is_cryptology_department_active = yes` |
| `is_decrypting` | `<tag>` | 是否正在破译该国 | `is_decrypting = POL` |
| `is_fully_decrypted` | `<tag>` | 是否已完全破译该国 | `is_fully_decrypted = POL` |
| `num_fake_intel_divisions` | `<int>` | 假情报师数量 | `num_fake_intel_divisions > 10` |
| `num_free_operative_slots` | `<int>` | 空闲特工槽位数量 | `num_free_operative_slots > 2` |
| `num_operative_slots` | `<int>` | 特工槽位总量 | `num_operative_slots > 2` |
| `num_of_operatives` | `<int>` | 当前特工数量 | `num_of_operatives > 2` |

本节坑：

- `estimated_intel_max_piercing` / `estimated_intel_max_armor` 的 `value` 必须用 `>` 或 `<`，不能写 `=`。
- `network_national_coverage` / `network_strength` / `decryption_progress` 的 `value` 同样必须用 `<` 或 `>`；`network_strength` 的 `target` 与 `state` 可只用其一，也可两个同时用。
- `compare_intel_with` 与 `intel_level_over` 是全节唯一允许 `=` 的数值触发：`=` 表示必须完全相等，`<` 表示当前国比对方少 x 情报。
- `has_intelligence_agency` 的参数含义写的是 “The intelligence agency to check”，实际按布尔用。
- `num_fake_intel_divisions`、`num_free_operative_slots`、`num_operative_slots`、`num_of_operatives`、`agency_upgrade_number` 均必须用 `<` 或 `>`。
- `has_done_agency_upgrade` 只能匹配“已升到最高级”的升级项。

原文示例：

```
estimated_intel_max_piercing = {
    tag = GER
    value > 2
}
compare_intel_with = { 
    target = POL 
    civilian_intel > 0.5
    army_intel = 0
    navy_intel < 0
}
network_strength = {
    target = POL
    value < 70
}
has_captured_operative = POL
has_captured_operative = yes
has_finished_collecting_for_operation = {
    target = POL
    operation = operation_infiltrate_armed_forces_navy
}
has_operation_token = {
    tag = POL
    token = token_name
}
```

---



country scope。共 6 条。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `ai_irrationality` | `<int>` | 当前作用域 AI 的非理性值 | `ai_irrationality > 10` |
| `ai_liberate_desire` | `target = <scope>`；`count = <float>` | AI 对目标国的解放意愿 | `ai_liberate_desire = { target = GER count > 1 }` |
| `ai_has_role_division` | `<string>` 角色名 | AI 是否拥有该角色的师 | `ai_has_role_division = infantry` |
| `ai_has_role_template` | `<string>` 角色名 | AI 是否拥有该角色的师模板 | `ai_has_role_template = armor` |
| `ai_wants_divisions` | `<int>` | AI 期望的师数量 | `ai_wants_divisions > 10` |
| `has_template_ai_majority_unit` | `<string>` 单位名 | 师模板是否以该单位为主 | `has_template_ai_majority_unit = infantry` |

本节坑：

- `ai_irrationality`、`ai_wants_divisions` 必须用 `>` 或 `<`；`ai_liberate_desire` 的 `count` 同样必须用 `>` 或 `<`。
- `ai_has_role_division` / `ai_has_role_template` 的角色名来自 `common/ai_templates/*.txt`，写自定义角色名之前要先在 mod 里定义。
- 全节无 scope 前置要求以外的限制，均按国家作用域判定。

原文示例：

```
ai_liberate_desire = {
    target = GER
    count > 1
}
```

---



country scope。共 8 条。wiki 明示：这些是“国家作用域里的角色相关触发”，不是 character scope 的触发。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `can_be_country_leader` | `<character>` 角色 token | 该角色是否有国家领导人职位（不论是否启用），且能在本国使用 | `can_be_country_leader = POL_character_test` |
| `has_character` | `<string>` 角色 token | 是否已招募该角色（不需要在台上） | `has_character = my_character` |
| `has_country_leader` | `ruling_only = <bool>`（默认 yes）；`character = <character_token>`（推荐）；`name = <string>`（可选）；`id = <int>`（可选） | 是否为指定国家领导人 | `has_country_leader = { id = 10 }` |
| `has_country_leader_ideology` | `<ideology>` 意识形态 | 在任领导人的意识形态 | `has_country_leader_ideology = nazism` |
| `has_country_leader_with_trait` | `<string>` 特质 token | 领导人是否拥有该特质 | `has_country_leader_with_trait = champion_of_peace_1` |
| `is_female` | `<bool>` | 国家领导人是否为女性 | `is_female = yes` |
| `has_unit_leader` | `<int>` id | 是否拥有该 id 的陆军/单位指挥官 | `has_unit_leader = 1` |
| `has_scientist_specialization` | `specialization = <specialization_token>` | 是否有该专精且技能≥1 的科学家 | `has_scientist_specialization = specialization_nuclear` |

本节坑：

- `has_unit_leader` 只能用 legacy id，角色 id（character id）不生效。
- `has_country_leader` 的 `ruling_only` 默认 `yes`（只查在任者）；`has_character` 查的是“已招募”，与是否在任无关。
- 参数表把 `character` 标为 “recommended criteria”，`name` 与 `id` 是可选补充条件。
- `has_scientist_specialization` 的判定是“至少 1 级”，不是“任意等级”。
- `can_be_country_leader` 判定的是“拥有该职位且本国可用”，与是否在任无关。

原文示例：

```
can_be_country_leader = POL_character_test
has_character = my_character
has_country_leader = {
    id = 10
}
has_country_leader = {
	character = SPR_niceto_alcala_zamora
	ruling_only = yes
}
has_country_leader = {
    name = "John Smith"
    ruling_only = yes
}
has_country_leader_ideology = nazism
has_scientist_specialization = specialization_nuclear
```

---



country scope。共 14 条。wiki 明示：这些并非“和平会议相关触发”，而是“只能在和平会议内使用的触发”。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `pc_is_winner` | `<bool>` | 是否为和平会议中的胜者 | `pc_is_winner = yes` |
| `pc_is_on_winning_side` | `<bool>` | 是否在胜方阵营 | `pc_is_on_winning_side = yes` |
| `pc_is_loser` | `<bool>` | 是否为败者 | `pc_is_loser = yes` |
| `pc_is_untouched_loser` | `<bool>` | 是否为未被处置的败者 | `pc_is_untouched_loser = yes` |
| `pc_is_on_same_side_as` | `<scope>` 国家 | 是否与指定国同阵营 | `pc_is_on_same_side_as = BHR` |
| `pc_is_liberated` | `<bool>` | 是否在会议中被解放 | `pc_is_liberated = yes` |
| `pc_is_liberated_by` | `<scope>` 国家 | 是否被指定国解放 | `pc_is_liberated_by = BHR` |
| `pc_is_puppeted` | `<bool>` | 是否在会议中被傀儡化 | `pc_is_puppeted = yes` |
| `pc_is_puppeted_by` | `<scope>` 国家 | 是否被指定国傀儡化 | `pc_is_puppeted_by = BHR` |
| `pc_is_forced_government` | `<bool>` | 是否被强制更换政府 | `pc_is_forced_government = yes` |
| `pc_is_forced_government_by` | `<scope>` 国家 | 是否被指定国强制换政府 | `pc_is_forced_government_by = BHR` |
| `pc_is_forced_government_to` | `<ideology group>` | 是否被强制换成指定意识形态组 | `pc_is_forced_government_to = democratic` |
| `pc_total_score` | `<decimal>` | 会议内总分 | `pc_total_score > 2400` |
| `pc_current_score` | `<decimal>` | 会议内当前分 | `pc_current_score > 100` |

本节坑：

- `pc_total_score` 与 `pc_current_score` 只能对胜方国家使用。
- 全节只能在和平会议内使用（wiki：these can only be used within peace conferences）。
- `pc_is_forced_government_to` 参数是意识形态组（ideology group），不是单个意识形态。

原文示例：

```
pc_total_score > 2400
pc_current_score > 100
pc_is_forced_government_to = democratic
pc_is_on_same_side_as = BHR
```

### 阵营与州作用域

本节未列出条目。原文只有一句：`There are currently no faction-specific triggers.`（wiki 版本 1.17，表格被 HTML 注释掉）。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| 本节未列出 | — | faction scope 目前没有专属触发器 | — |

本节坑：

- wiki 只写了“阵营作用域目前没有专属触发器”，本节没有任何参数表；不要照国家作用域的条目硬套到 faction scope。

---



state scope。`section=32` 返回 `==State scope==` 与 `===General===`，共 48 条（`area` 在 wiki 里被 HTML 注释掉，不计）。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `state` | `<scope>` 或 `<variable>` | 当前作用域是否为指定州 | `state = 10` / `state = var:state` |
| `region` | `<int>` 战略区 id | 当前州是否属于该战略区 | `region = 10` |
| `<building>`（building_count_trigger） | `<int>` | 该建筑数量 | `arms_factory > 10` |
| `free_building_slots` | `building = <string>`；`size = <int>`；`include_locked = <bool>` | 是否有足够空位建该建筑 | `free_building_slots = { building = arms_factory size > 10 include_locked = yes }` |
| `non_damaged_building_level` | `building = <string>`；`level = <int>` | 未受损的该建筑数量 | `non_damaged_building_level = { building = arms_factory level > 4 }` |
| `any_province_building_level` | `building = <string>`；`limit = <int>`；`province = { id = <int> … limit_to_border = <bool> }` | 指定省是否达到该省级建筑等级 | `any_province_building_level = { province = { id = 445 id = 494 limit_to_border = yes } building = bunker level < 5 }` |
| `has_state_flag`（简写） | `<string>` | 州是否有该 flag | `has_state_flag = my_flag` |
| `has_state_flag`（块式） | `flag = <string>`；`value = <int>`（可选）；`date = <date>`（可选）；`days = <int>`（可选） | 比较该 flag 的最后设置日期／存在天数／值 | `has_state_flag = { flag = my_flag days > 30 date > 1936.6.1 value > 0 }` |
| `state_population` | `<float>` | 州人口 | `state_population > 10000` |
| `state_population_k` | `<float>` | 州人口（千人） | `state_population_k > 10` |
| `is_capital` | `<bool>` | 是否为首都 | `is_capital = yes` |
| `is_controlled_by` | `<scope>/<variable>` | 是否被该国控制 | `is_controlled_by = GER` |
| `is_fully_controlled_by` | `<scope>/<variable>` | 是否被该国完全控制 | `is_fully_controlled_by = GER` |
| `is_owned_by` | `<scope>/<variable>` | 是否归该国所有 | `is_owned_by = GER` |
| `is_claimed_by` | `<scope>/<variable>` | 是否被该国声索 | `is_claimed_by = GER` |
| `is_core_of` | `<scope>/<variable>` | 是否为该国核心 | `is_core_of = GER` |
| `is_owned_and_controlled_by` | `<scope>/<variable>` | 是否既归其所有又由其控制 | `is_owned_and_controlled_by = GER` |
| `is_demilitarized_zone` | `<bool>` | 是否为非军事化区 | `is_demilitarized_zone = yes` |
| `is_border_conflict` | `<bool>` | 是否属于边境冲突 | `is_border_conflict = yes` |
| `is_in_home_area` | `<bool>` | 是否陆路连接首都 | `is_in_home_area = yes` |
| `is_coastal` | `<bool>` | 是否为沿海州 | `is_coastal = yes` |
| `is_one_state_island` | `<bool>` | 是否为无相邻陆地州的沿海州 | `is_one_state_island = yes` |
| `is_island_state` | `<bool>` | 是否为所有省份都没有陆地邻接的州 | `is_island_state = yes` |
| `is_on_continent` | `<string>` 大洲名 | 是否在该大洲 | `is_on_continent = europe` |
| `is_on_same_continent_as` | `<scope>/<variable>` | 是否与给定国家（取其首都州）同大洲 | `is_on_same_continent_as = FRA` |
| `impassable` | `<bool>` | 是否不可通行 | `impassable = yes` |
| `has_state_category` | `<string>` | 州类别 | `has_state_category = rural` |
| `state_strategic_value` | `<int>` | 州战略价值 | `state_strategic_value > 10` |
| `state_and_terrain_strategic_value` | `<int>` | 州＋地形战略价值 | `state_and_terrain_strategic_value > 10` |
| `num_owned_neighbour_states` | `owner = <scope>`；`count = <int>` | 相邻州中属于该国的数量 | `num_owned_neighbour_states = { owner = GER count > 2 }` |
| `distance_to` | `value = <float>`；`target = <scope>` 州 | 与指定州的距离 | `distance_to = { value > 1000 target = 49 }` |
| `ships_in_area` | `area = <int>` 战略区；`size = <int>` | 该战略区内的舰船数 | `ships_in_area = { area = 104 size > 14 }` |
| `<resource>`（resource_count_trigger） | `<int>` | 州内该资源量 | `tungsten > 10` |
| `has_resources_amount` | `resource = <string>`；`amount = <int>`；`delivered = <bool>` | 资源量（`delivered` 只算加成后实际到手的量） | `has_resources_amount = { resource = oil amount > 10 delivered = yes }` |
| `has_resources_rights` | `receiver = <scope>`（州作用域下必填）；`resources = { <resource> … }`（可选） | 是否存在该参数的资源权 | `has_resources_rights = { receiver = POL resources = { oil steel } }` |
| `days_since_last_strategic_bombing` | `<int>` | 距上次战略轰炸的天数 | `days_since_last_strategic_bombing < 10` |
| `has_railway_connection` | `start_state`/`target_state`，或 `start_province`/`target_province` | 两地之间是否有铁路连通 | `has_railway_connection = { start_state = 10 target_state = 90 }` |
| `can_build_railway` | 同上（州或省成对） | 两地之间能否修铁路 | `can_build_railway = { start_province = 402 target_province = 9400 }` |
| `has_railway_level` | `state = <scope>/<variable>`；`level = <int>` | 州内是否存在该等级的铁路 | `has_railway_level = { state = 114 level = 5 }` |
| `pc_does_state_stack_demilitarized` | `<bool>` | 该州是否在（当前或已结束的）和平会议中被非军事化 | `pc_does_state_stack_demilitarized = yes` |
| `pc_does_state_stack_dismantled` | `<bool>` | 该州是否在和平会议中被拆解 | `pc_does_state_stack_dismantled = yes` |
| `pc_is_state_claimed` | `<scope>` 国家 | 会议中是否被任何国家声索 | `pc_is_state_claimed = yes` |
| `pc_is_state_claimed_by` | `<scope>` 国家 | 会议中是否被指定国声索 | `pc_is_state_claimed_by = BHR` |
| `pc_is_state_claimed_and_taken_by` | `<scope>` 国家 | 会议中是否被指定国以 “Take State” 吞并 | `pc_is_state_claimed_and_taken_by = SOV` |
| `pc_is_state_outside_influence_for_winner` | `<scope>` 国家 | 是否在指定胜国势力范围之外 | `pc_is_state_outside_influence_for_winner = ROOT` |
| `pc_turn` | `<int>` | 会议已进行的回合数 | `pc_turn > 20` |
| `can_construct_building` | `<build type>` 建筑类型 | ROOT 国与该州能否建造该建筑 | `can_construct_building = bunker` |
| `has_contested_owner` | `<country>/<variable>` | 该州是否有该国作为争议所有者 | `has_contested_owner = GER` |

本节坑：

- `has_state_flag` 有两个条目（简写与块式），块式的 `value` 未设置时按 `>0` 判定，且 `value` 取值被限制在 `-32768` 到 `32767`。
- `any_province_building_level` 的参数表写 `limit = <int>`，示例却用 `level < 5`；按示例写 `level`。该表还要求 `level` 必须用 `>` 或 `<`。
- `is_in_home_area` 只有在该州同时“被本国拥有”时才为真（仅陆地连通不够）。
- `is_one_state_island` 与 `is_island_state` 判据不同：前者“无相邻陆地州”，后者“每个省份都没有陆地邻接”；两者的相邻都可能通过海路跨越连接。
- `is_on_continent` 的大洲名来自 `map/continent.txt`；`is_on_same_continent_as` 对给定的国家 tag 使用其首都州作比较。
- `has_resources_rights` 在州作用域下 `receiver` 必填；州内无资源时恒为 false。
- `has_railway_level` 仅支持等级 1–5，等级 0 不生效。
- `pc_is_state_claimed_by` 的 “claim” 包含强制换政府、傀儡化、解放，不限于直接占地；只查“战胜国自己拿走”要用 `pc_is_state_claimed_and_taken_by`。
- `pc_is_state_outside_influence_for_winner` 在 1.12.8 之前叫 `pc_is_state_outside_influence_for`。
- 5 个 `pc_*` 州触发（`pc_is_state_claimed`、`pc_is_state_claimed_by`、`pc_is_state_claimed_and_taken_by`、`pc_is_state_outside_influence_for_winner`、`pc_turn`）只能在和平会议内使用。
- `can_construct_building` 判的是 ROOT 国＋该州，两个 scopes 都要成立。
- `has_contested_owner`、`has_resources_rights`、`<resource>`、`<building>`、`is_on_same_continent_as`、`occupation_law` 是双向可用的：国家作用域和州作用域都能写，参数取另一个 scope。
- wiki 注释里保留了 `area`（补给区）条目，但原文自注 “remains in documentation, yet doesn't make sense”，不要使用。

原文示例：

```
free_building_slots = {
    building = arms_factory
    size > 10
    include_locked = yes
}
non_damaged_building_level = {
    building = arms_factory
    level > 4
}
any_province_building_level = {
    province = {
        id = 445
        id = 494
        limit_to_border = yes
    }
    building = bunker
    level < 5
}
has_state_flag = {
    flag = my_flag
    days > 30
    date > 1936.6.1
    value > 0
}
num_owned_neighbour_states = {
    owner = GER
    count > 2
}
distance_to = {
    value > 1000
    target = 49
}
ships_in_area = { area = 104 size > 14 } 
has_resources_amount = {
    resource = oil
    amount > 10
    delivered = yes
}
has_resources_rights = {
  receiver = POL
  resources = { oil steel }
}
has_railway_connection = {
	start_state = 10
	target_state = 90
}
can_build_railway = {
	start_province = 402
	target_province = 9400
}
has_railway_level = {
    	state = 114
    	level = 5
}
```

---



state scope。共 10 条。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `compliance` | `<int>` | 顺从度 | `compliance > 50` |
| `compliance_speed` | `<int>` | 顺从度增长速度 | `compliance_speed > 50` |
| `has_active_resistance` | `<bool>` | 是否有非零抵抗 | `has_active_resistance = yes` |
| `has_resistance` | `<bool>` | 是否有抵抗 | `has_resistance = yes` |
| `resistance` | `<int>` | 抵抗度 | `resistance > 50` |
| `resistance_speed` | `<int>` | 抵抗增长速度 | `resistance_speed > 50` |
| `resistance_target` | `<int>` | 目标抵抗值 | `resistance_target > 50` |
| `has_occupation_modifier` | `<token>` | 是否有该占领修正（影响抵抗／顺从） | `has_occupation_modifier = modifier_name` |
| `occupation_law` | `<token>` | 当前的占领法 | `occupation_law = law_name` |
| `occupied_country_tag` | `<tag>` | 制造抵抗的是哪个国家 | `occupied_country_tag = POL` |

本节坑：

- `compliance`、`compliance_speed`、`resistance`、`resistance_speed`、`resistance_target` 的数值必须用 `>` 或 `<`。
- `has_active_resistance` 判的是“抵抗值非零”，`has_resistance` 判的是“存在抵抗”，两者不是同一条件。
- `occupation_law` 也可在国家作用域使用（双向触发）。
- `occupied_country_tag` 返回的是“制造抵抗的国家”，不是占领者。

原文示例：

```
compliance > 50
compliance_speed > 50
has_active_resistance = yes
has_resistance = yes
resistance > 50
resistance_speed > 50
resistance_target > 50
has_occupation_modifier = modifier_name
occupation_law = law_name
occupied_country_tag = POL
```

### 角色作用域：顾问、领袖、将领、特工、科学家

#### Character scope#General（Trigger index=36）

作用域：`Character`（`==Character scope==` 说明：Can be used in '''Character''' scope）。22 个条件，23 条表格行（`has_character_flag` 有短/长两种写法）。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `is_character` | `<scope>` 角色 ID | 当前角色的 token 是否等于指定值 | `is_character = POL_test_character` |
| `can_be_country_leader` | `<bool>` | 角色是否拥有国家领袖角色（激活或未激活） | `can_be_country_leader = yes` |
| `is_country_leader` | `<bool>` | 角色是否是**激活中**的国家领袖 | `is_country_leader = yes` |
| `is_unit_leader` | `<bool>` | 角色是否有激活的陆/海军将领角色 | `is_unit_leader = yes` |
| `is_advisor` | `<bool>` | 角色是否有顾问类角色（含顾问/理论家/最高指挥部） | `is_advisor = yes` |
| `is_air_chief` | `<bool>` | 角色是否被选为空军首长 | `is_air_chief = yes` |
| `is_army_chief` | `<bool>` | 角色是否被选为陆军首长 | `is_army_chief = yes` |
| `is_army_leader` | `<bool>` | 角色是否有陆军将领（General / Field Marshal）角色 | `is_army_leader = yes` |
| `is_navy_chief` | `<bool>` | 角色是否被选为海军首长 | `is_navy_chief = yes` |
| `is_navy_leader` | `<bool>` | 角色是否有海军将领（Admiral）角色 | `is_navy_leader = yes` |
| `is_high_command` | `<bool>` | 角色是否被选为最高指挥部 | `is_high_command = yes` |
| `is_corps_commander` | `<bool>` | 角色是否是军团长 | `is_corps_commander = yes` |
| `is_operative` | `<bool>` | 角色是否是特工 | `is_operative = yes` |
| `is_political_advisor` | `<bool>` | 角色是否被选为政治顾问 | `is_political_advisor = yes` |
| `is_theorist` | `<bool>` | 角色是否被选为理论家 | `is_theorist = yes` |
| `is_character_slot` | `<string>` 顾问槽位 | 角色是否在指定角色槽位内有角色 | `is_character_slot = political_advisor` |
| `has_air_ledger` | `<bool>` | 角色是否有空军履历（ledger） | `has_air_ledger = yes` |
| `has_army_ledger` | `<bool>` | 角色是否有陆军履历 | `has_army_ledger = yes` |
| `has_navy_ledger` | `<bool>` | 角色是否有海军履历 | `has_navy_ledger = yes` |
| `has_character_flag` | `<string>` flag 名 | 当前作用域是否有指定 flag | `has_character_flag = my_flag` |
| `has_character_flag`（长写法） | `flag = <string>` 必填；`value = <int>` 可选；`date = <date>` 可选；`days = <int>` 可选 | 比较 flag 的最后设置日期、距今天数、和/或数值 | 见下方代码块 |
| `has_trait` | `<trait>` 特质 | 当前作用域是否有指定特质 | `has_trait = really_good_boss` |
| `has_id` | `<int>` | 角色 ID 是否等于指定数字 | `has_id = 1` |

```text
has_character_flag = {
    flag = my_flag
    days > 30
    date > 1936.6.1
    value > 0
}
```

限制与坑：

- `is_air_chief` / `is_army_chief` / `is_navy_chief` / `is_high_command` / `is_political_advisor` / `is_theorist`：1.12 之前判断的是「该槽位里有角色」，不管是否被选中；1.12 起才判断「被选中」。
- `can_be_country_leader` 与 `is_country_leader` 不同：前者含未激活的领袖角色定义，后者只认当前在位者。
- `is_advisor` 覆盖面比 `is_political_advisor` 宽，含理论家与最高指挥部。
- `is_character_slot` 的槽位 token 定义在 `common/idea_tags/*.txt`。
- `has_character_flag` 长写法里 `value` 未写时默认按 `>0` 比较，取值被限制在 -32768…32767。
- `has_trait`、`has_id` 自 1.5 起可用，其余大多自 1.11。

#### Advisors（Trigger index=37）

作用域：`Character`，专用于顾问判断。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `is_hired_as_advisor` | `<bool>` | 角色是否已作为顾问在任意槽位被启用 | `is_hired_as_advisor = yes` |
| `not_already_hired_except_as` | `<slot>` 槽位 | 角色是否未被雇佣（指定槽位除外） | `not_already_hired_except_as = political_advisor` |
| `advisor_can_be_fired` | `<bool>` 或 `slot = <slot>` | 角色在指定槽位的 `can_be_fired` 属性是否为真 | `advisor_can_be_fired = no` |
| `has_advisor_role` | `<slot>` 槽位 | 角色是否拥有该槽位的顾问角色 | `has_advisor_role = political_advisor` |

```text
advisor_can_be_fired = {
    slot = political_advisor
}
```

限制与坑：

- `advisor_can_be_fired` 在一个顾问可出现在多个槽位时**必须**用长写法指定 `slot`，短写法结果不确定。
- `has_advisor_role` 的合法槽位见 `Character_modding#Advisors`；wiki 未标版本（`???`）。
- `is_hired_as_advisor` 需要 1.12.10+，`advisor_can_be_fired` 需要 1.12.8+。

#### Country leaders（Trigger index=38）

作用域：`Character`，专用于国家领袖。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `has_ideology` | `<ideology>` 子意识形态 | 角色是否被赋予指定子意识形态 | `has_ideology = liberalism` |
| `has_ideology_group` | `<ideology>` 意识形态组 | 角色是否被赋予指定意识形态组 | `has_ideology_group = democratic` |

限制与坑：

- 两个条件都自 1.11 起；`has_ideology` 查的是子意识形态（如 `liberalism`），`has_ideology_group` 查的是大组（如 `democratic`），写错层级不会报错但恒为假。

#### Unit leaders（Trigger index=39）

作用域：将帅（General / Admiral / Field Marshal）角色。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `has_unit_leader_flag` | `<string>` flag 名 | 当前作用域是否有指定 flag | `has_unit_leader_flag = my_flag` |
| `has_unit_leader_flag`（长写法） | `flag = <string>` 必填；`value`/`date`/`days` 可选 | 比较 flag 的设置日期、距今天数、数值 | 见代码块 |
| `is_leading_army` | `<bool>` | 是否指挥单一集团军 | `is_leading_army = yes` |
| `is_leading_army_group` | `<bool>` | 是否指挥集团军群 | `is_leading_army_group = yes` |
| `is_leading_volunteer_group` | `<tag>` 国家 tag | 是否在指定国家内指挥志愿军 | `is_leading_volunteer_group = POL` |
| `is_leading_volunteer_group_with_original_country` | `<tag>` 国家 tag | 是否在「原始 tag 为指定国」的国家内指挥志愿军 | `is_leading_volunteer_group_with_original_country = POL` |
| `is_field_marshal` | `<bool>` | 是否是元帅 | `is_field_marshal = yes` |
| `is_assigned` | `<bool>` | 是否已被指派 | `is_assigned = yes` |
| `can_select_trait` | `<string>` 特质 | 是否可以选择指定特质 | `can_select_trait = offensive_doctrine` |
| `has_ability` | `<string>` 能力 | 是否拥有指定将领能力 | `has_ability = glider_planes` |
| `skill` | `<int>` | 技能值高于/低于指定值 | `skill > 1` |
| `skill_advantage` | `<int>` | 战斗中相对敌方将领的技能优势超过指定值 | `skill_advantage > 1` |
| `planning_skill_level` | `<int>` | 计划技能高于/低于指定值 | `planning_skill_level > 1` |
| `logistics_skill_level` | `<int>` | 后勤技能高于/低于指定值 | `logistics_skill_level > 1` |
| `defense_skill_level` | `<int>` | 防御技能高于/低于指定值 | `defense_skill_level > 1` |
| `attack_skill_level` | `<int>` | 攻击技能高于/低于指定值 | `attack_skill_level > 1` |
| `average_stats` | `<int>` | 平均技能高于/低于指定值 | `average_stats > 5` |
| `is_border_war` | `<bool>` | 是否处于边境战争 | `is_border_war = yes` |
| `num_units` | `<int>` | 指挥的师数量高于/低于指定值 | `num_units > 5` |
| `is_exiled_leader` | `<bool>` | 是否是流亡国家的将领 | `is_exiled_leader = yes` |
| `is_exiled_leader_from` | `<tag>` 国家 | 是否来自指定流亡国家的将领 | `is_exiled_leader_from = POL` |
| `is_female` | `<bool>` | 是否为女性 | `is_female = yes` |
| `is_leading_army_in_province` | `<province id>` | 所指挥的军队是否有师位于指定省份 | `is_leading_army_in_province = 1234` |

```text
has_unit_leader_flag = {
    flag = my_flag
    days > 30
    date > 1936.6.1
    value > 0
}
```

限制与坑：

- `has_unit_leader_flag` 已废弃（Deprecated），改用 `has_character_flag`；长写法的 `value` 默认按 `>0`，范围 -32768…32767。
- `skill`、`skill_advantage`、`planning_skill_level`、`logistics_skill_level`、`defense_skill_level`、`attack_skill_level`、`average_stats`、`num_units` 必须用 `>` 或 `<`，不能用 `=`。
- `is_leading_volunteer_group` 在目标国处于内战状态时只对其中一方有效；`is_leading_volunteer_group_with_original_country` 则对内战双方都有效（按原始 tag 匹配）。
- `is_female` 对王牌（aces）同样有效。
- `is_leading_army_in_province` 需要 1.17+，其余多数为 1.5 / 1.6 / 1.11。

#### Operatives（Trigger index=40）

作用域：特工（operative）专用。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `has_nationality` | `<tag>` 国籍 | 特工是否具有该国籍 | `has_nationality = POL` |
| `is_operative_captured` | `<bool>` | 特工是否被俘 | `is_operative_captured = yes` |
| `operative_leader_mission` | `<token>` 任务 | 特工是否在执行指定任务 | `operative_leader_mission = mission_name` |
| `operative_leader_operation` | `<token>` 行动 | 特工是否在执行指定行动 | `operative_leader_operation = operation_name` |

限制与坑：

- 全部为 1.9+，且「only work for operatives」，在非特工作用域使用不会得到有效结果。
- `operative_leader_mission` / `operative_leader_operation` 传的是 mission / operation 的 token，不是本地化键。

#### Scientists（Trigger index=41）

作用域：科学家（scientist）专用。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `has_scientist_level` | `level = <int>` 等级条件；`specialization = <specialization_token>` 专业 | 角色对应科学家在某专业上的技能等级是否满足条件，支持 `< > =` | 见代码块 |
| `is_active_scientist` | `<bool>` | 科学家是否被指派到项目 | `is_scientist_active = yes` |
| `is_scientist_injured` | `<bool>` | 科学家是否受伤 | `is_scientist_injured = yes` |

```text
has_scientist_level = {
  level > 2
  specialization = specialization_nuclear
}
```

限制与坑：

- 全部 1.15+（特殊项目 DLC 体系）。
- 条件名是 `is_active_scientist`，但 wiki 给的示例写成 `is_scientist_active = yes`——按条件名 `is_active_scientist` 使用，示例疑为笔误，未实测。
- `has_scientist_level` 必须成块写，`level` 用比较运算符，`specialization` 用等号。

### 战斗、师、军工组织、合同、特殊项目、元条件

#### Combat（Trigger index=42）

作用域：**combatant scope**。wiki 明言：abilities（`Command power#Abilities for field marshals and generals`）、combat tactics、unit leader traits 里的部分 trigger 块会检查它，**在别处无法访问**。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `hardness` | `<float>` | 当前作用域硬度是否达到指定值 | `hardness > 0.5` |
| `armor` | `<float>` | 装甲值是否达到指定值 | `armor > 0.5` |
| `dig_in` | `<float>` | 挖壕加成是否达到指定值 | `dig_in > 0.5` |
| `min_planning` | `<float>` | 计划值是否达到指定值 | `min_planning > 0.5` |
| `fastest_unit` | `<float>` km/h | 是否有速度达到指定值的单位 | `fastest_unit > 12` |
| `temperature` | `<float>` 摄氏度 | 所在省份温度是否高于指定值 | `temperature > 20` |
| `reserves` | `<float>` | 待命预备队数量是否达到指定值 | `reserves > 10` |
| `has_combat_modifier` | `<string>` 战斗修正 | 是否具有指定战斗修正 | `has_combat_modifier = river_crossing` |
| `is_fighting_in_terrain` | `<string>` 地形 | 是否在指定地形作战 | `is_fighting_in_terrain = desert` |
| `is_fighting_in_weather` | `<string>` 天气，或 `{ <string> ... }` 多个取或 | 是否在指定天气作战 | `is_fighting_in_weather = sandstorm` |
| `phase` | `<bool>` | 是否处于 phase 状态 | `phase = yes` |
| `recon_advantage` | `<bool>` | 是否具有侦察优势 | `recon_advantage > 0` |
| `night` | `<bool>` | 是否夜战 | `night = yes` |
| `frontage_full` | `<bool>` | 战线宽度是否已满 | `frontage_full = yes` |
| `has_flanked_opponent` | `<bool>` | 是否已包抄对手 | `has_flanked_opponent = yes` |
| `has_max_planning` | `<bool>` | 是否拥有最大计划加成 | `has_max_planning = yes` |
| `has_reserves` | `<bool>` | 是否有待命预备队 | `has_reserves = yes` |
| `is_amphibious_invasion` | `<bool>` | 是否正在两栖登陆 | `is_amphibious_invasion = yes` |
| `is_attacker` | `<bool>` | 是否是进攻方 | `is_attacker = yes` |
| `is_defender` | `<bool>` | 是否是防守方 | `is_defender = yes` |
| `is_winning` | `<bool>` | 是否正在赢得战斗 | `is_winning = yes` |
| `is_fighting_air_units` | `<bool>` | 是否正在与空军单位交战 | `is_fighting_air_units = yes` |
| `less_combat_width_than_opponent` | `<bool>` | 战斗宽度是否小于对手 | `less_combat_width_than_opponent = yes` |
| `has_carrier_airwings_on_mission` | `<bool>` | 是否有航母舰载机在执行任务 | `has_carrier_airwings_on_mission = yes` |
| `has_carrier_airwings_in_own_combat` | `<bool>` | 是否有航母舰载机参与自身战斗 | `has_carrier_airwings_in_own_combat = yes` |
| `has_artillery_ratio` | `<float>` | 己方战斗部队编制中炮兵营占比是否超过某水平 | `has_artillery_ratio > 0.1` |
| `has_unit_type` | `<unit_type>` | 战斗方是否至少有该兵种之一 | `has_unit_type = amphibious_mechanized` |

```text
is_fighting_in_weather = { rain_light rain_heavy }
```

限制与坑：

- 只能在 combatant scope 用；在 country/state/character 等作用域写这些条件无效，且 wiki 说「impossible to access elsewhere」。
- `hardness`、`armor`、`dig_in`、`min_planning`、`fastest_unit`、`temperature`、`reserves` 必须用 `>` 或 `<`。
- `is_fighting_in_weather` 支持块写法做 OR（`{ rain_light rain_heavy }`）。
- `recon_advantage` 参数被标为 `<bool>`，但示例是 `recon_advantage > 0`，写法不统一，按示例用比较运算符。
- `has_artillery_ratio`、`has_unit_type` 的版本 wiki 标 `???`（未确认）；其余为 1.0。

---



#### Division scope（Trigger index=43）

作用域：`Division`。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `division_has_majority_template` | `<battalion>` 营 | 当前师是否以指定营为主要构成 | `division_has_majority_template = light_armor` |
| `division_has_battalion_in_template` | `<battalion>` 营 | 当前师编制中是否有该类型营 | `division_has_battalion_in_template = light_armor` |
| `unit_strength` | `<float>` | 单位兵力（0–1 比例）是否满足条件 | `unit_strength < 0.3` |
| `unit_organization` | `<float>` | 单位组织度（0–1 比例）是否满足条件 | `unit_organization < 0.3` |
| `is_unit_template_reserves` | `<bool>` | 师的补给优先级是否设为 'Reserves'（最低） | `is_unit_template_reserves = yes` |
| `has_officer_name` | `<string>` 本地化键 | 师是否有使用该名字键的军官 | `has_officer_name = FIN_nikke_parmi` |

限制与坑：

- 营 token 定义在 `common/units/*.txt`。
- `unit_strength`、`unit_organization` 必须用 `<` 或 `>`，取值 0–1。
- `is_unit_template_reserves` 的 Notes 写着「Must use either the < or > operator」，但参数是 bool、示例是 `= yes`，两者矛盾；按布尔写法用，Notes 疑为复制粘贴残留。
- 本节全部 1.12+；`has_officer_name` 的版本列为空。

---



#### MIO scope（Trigger index=44）

作用域：Military-industrial organisation。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `is_military_industrial_organization` | `<token>` MIO | 当前 MIO 是否等于指定 token | `is_military_industrial_organization = my_mio_token` |
| `is_mio_visible` | `<bool>` | 当前 MIO 是否可见 | `is_mio_visible = yes` |
| `is_mio_available` | `<bool>` | 当前 MIO 是否可用（wiki 描述误写为 visible） | `is_mio_available = yes` |
| `is_mio_assigned_to_task` | `<bool>` | 当前 MIO 是否被指派到任务 | `is_mio_assigned_to_task = yes` |
| `has_mio_size` | `<int>` | MIO 规模 | `has_mio_size > 3` |
| `has_mio_trait` | `<token>` 特质，或长写法 | MIO 特质列表中是否有目标特质 | `has_mio_trait = my_trait_token` |
| `is_mio_trait_available` | `<token>` 特质；`check_mio_parent_completed = <bool>`（默认 true）；`check_mio_mutually_exclusive = <bool>`（默认 true） | 特质是否在列表中且可点 | 见代码块 |
| `is_mio_trait_completed` | `<token>` 特质 | 特质是否在列表中且已完成 | 见代码块 |
| `has_mio_number_of_completed_traits` | `<int>` | 已解锁特质数量 | `has_mio_number_of_completed_traits < 2` |
| `has_mio_flag` | `<string>` flag | 当前作用域是否有指定 flag | `has_mio_flag = my_flag` |
| `has_mio_flag`（长写法） | `flag`、`value`、`date`、`days` | 比较 flag 的设置日期/距今天数/数值 | 见代码块 |
| `has_mio_policy` | `<token>` 政策 | MIO 是否允许该政策 | `has_mio_policy = my_policy_token` |
| `has_mio_policy_active` | `<token>` 政策 | MIO 是否已启用该政策 | `has_mio_policy_active = my_policy_token` |
| `has_mio_research_category` | `<token>` 类别 | MIO 是否有该研究类别 | `has_mio_research_category = my_research_category_token` |
| `has_mio_equipment_type` | `<token>` 类型 | MIO 是否有该装备类型 | `has_mio_equipment_type = my_equipment_type_token` |

```text
is_mio_trait_available = {
    token = my_trait_token
    check_mio_parent_completed = no
}
```

```text
has_mio_flag = {
    flag = my_flag
    days > 30
    date > 1936.6.1
    value > 0
}
```

```text
is_mio_trait_completed = {
    token = my_trait_token
}
```

限制与坑：

- 全部 1.13+（Arms Against Tyranny 的 MIO 体系）。
- `has_mio_size`、`has_mio_number_of_completed_traits` 接受变量（`[[variables]]`），必须用 `<` 或 `>`。
- `is_mio_trait_available` 的 `check_mio_parent_completed`、`check_mio_mutually_exclusive` 默认都是 true，想忽略前置/互斥时显式写 `no`。
- `has_mio_trait` / `is_mio_trait_available` / `is_mio_trait_completed` 的块写法和字符串写法 wiki 参数列都写成 `trait = <token>`，但示例里用的是 `token = ...`；按**示例**的 `token =` 写。
- `has_mio_equipment_type` 的合法值见 `common/script_enums.txt` 里的 `script_enum_equipment_bonus_type` 与 `common/equipment_groups.txt`。
- `is_mio_available` 的 wiki 描述照抄成了 "is visible"，按名字理解为「可用」。

---



#### Contract scope（Trigger index=45）

作用域：purchase contract（采购合同）。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `contract_contains_equipment` | `<token>` 类型 | 当前采购合同是否包含某装备类型 | `contract_contains_equipment = infantry_equipment` |
| `deal_completion` | `<decimal>` 进度 | 交易完成度与目标值比较（0–1） | `deal_completition > 0.6` |
| `seller` | `<country>` | 当前合同的卖方国 | `seller = BHR` |
| `buyer` | `<country>` | 当前合同的买方国 | `buyer = OMA` |

限制与坑：

- 全部 1.13+。
- `contract_contains_equipment` 可以填装备类型、装备原型（archetype），或原型的类型。
- `deal_completion` 必须用 `<` 或 `>`，0–1 比例；wiki 示例把条件名拼成 `deal_completition`（多一个 t），照抄会失效，按 `deal_completion` 写。
- `seller` / `buyer` 传国家 tag。

---



#### Special projects（Trigger index=46）

作用域：特殊项目（special project）。本节只有一个条件。

| 条件 | 参数 | 作用 | 示例 |
|---|---|---|---|
| `has_project_flag` | `<string>` flag，或长写法 `flag`/`value`/`date`/`days` | 当前特殊项目是否设置过该 flag，可选比较数值与设置日期/距今天数 | `has_project_flag = my_flag` |

```text
has_project_flag = {
  flag = my_flag
  value < 12
  date > 1936.3.25
  days > 365
}
```

限制与坑：

- 1.15+。
- 长写法里 `value` 未写时默认按 `>0` 比较，取值限制 -32768…32767。
- `days` 表示「距最后一次修改（设置）已过的天数」。

---



#### Meta triggers（Trigger index=47）

本节是机制说明，没有条件表格。要点：

- 1.6 随 {{icon|mtg|1}} 引入，用法与 meta effects 完全一致：把 trigger 块绑定到动态本地化条目。常与 scripted localisation 配合做非数值判断，也可用于「本不允许变量检查的地方」插入变量检查。
- 可在**任何**支持 trigger 的作用域使用，包括 combat scope。
- 写在 scripted trigger 里的参数：
  - `text = { ... }`：meta trigger 使用的 trigger 块，其中需要动态化的字符串两侧加方括号写成 `[EXAMPLE]`。
  - `EXAMPLE = "..."`：替换 `text = { ... }` 中 `[EXAMPLE]` 的字符串；有限度接受动态本地化，例如用 `[?var_name]` 取变量值，或用 `[ROOT.GetTag]` 这类命名空间。
  - `debug = yes`：可选，把最终输出写进用户目录的 `logs/game.log` 便于调试。
- 官方示例（与 `has_equipment` 配合，让阈值取决于变量）：

```text
meta_trigger = {
    text = {
        has_equipment = { [EQUIPMENT_ARCHETYPE] > 100 }
    }
    EQUIPMENT_ARCHETYPE = "[GetEquipmentArchetype]"
}
```

此时 `GetEquipmentArchetype` 是 scripted localisation，其定义示例：

```text
defined_text = {
    name = GetEquipmentArchetype
    text = {
        trigger = {
            check_variable = { v = 0 }
        }
        localization_key = artillery_equipment
    }
    text = {
        localization_key = infantry_equipment
    }
}
```

限制与坑：

- `text` 里的占位符两侧方括号不能省，且替换名必须与 `EXAMPLE = "..."` 的键名**同名**。
- 替换值走动态本地化，能力有限（`[?var_name]`、`[ROOT.GetTag]` 等），不是任意脚本求值。
- 排查时加 `debug = yes`，输出落在 `logs/game.log`；不加则静默失败。
- meta trigger 只能写进 scripted trigger，不能直接内联在普通 trigger 块里。

---

## 第 5 章 效果（Effects）

### Effect

URL：`https://hoi4.paradoxwikis.com/index.php?title=Effect&action=raw`（1.16）

### 语法规则

- effect 是**一次性改变**，不产生持续状态；持续效果要通过 modifier（`add_ideas` 等）承载。
- 形态：`effect_name = <value>` 或 `effect_name = { <parameters> / <effects> }`。
- 参数可取自变量：`add_manpower = var:my_var`（wiki 用 `<variable>` 标记）。
- 常用位置：国策 `completion_reward`、事件 option、决议 effect。
- 官方完整列表：`documentation/effects_documentation.html` / `.md`。

### Any scope 常用字段

| 字段 | 类型 | 作用 | 示例 |
|---|---|---|---|
| `add_dynamic_modifier` | 块 | 加动态修正；`scope`、`days` 可选 | `{ modifier = example_dynamic_modifier scope = GER days = 14 }` |
| `remove_dynamic_modifier` | 块 | 移除动态修正 | `{ modifier = sabotaged_ressources }` |
| `force_update_dynamic_modifier` | bool | 立即重算动态修正中的变量值 | `force_update_dynamic_modifier = yes` |
| `set_global_flag` | string/块 | 设全局 flag，块形式可带 `days`、`value` | `{ flag = my_flag days = 123 value = 1 }` |
| `clr_global_flag` / `modify_global_flag` | string / 块 | 清除 / 增减 flag 值（flag 必须已存在） | `{ flag = my_flag value = 3 }` |
| `custom_effect_tooltip` | loc key | 在提示里显示自定义文本 | `custom_effect_tooltip = my_tooltip_tt` |
| `custom_override_tooltip` | 块 | 执行内部 effect 但只显示自定义 tooltip（1.15） | `{ tooltip = my_tt not_tooltip = my_tt_NOT }` |
| `effect_tooltip` | 块 | 只显示、不执行 | `effect_tooltip = { declare_war_on = { target = FRA } }` |
| `hidden_effect` | 块 | 执行但隐藏 tooltip | `hidden_effect = { ... }` |
| `log` | string | 写 game.log，支持本地化命令 | `log = "myVariable: [?myVariable]"` |
| `save_event_target_as` | string | 保存当前 scope 为事件目标（执行结束即失效） | `save_event_target_as = my_state` |
| `save_global_event_target_as` | string | 保存为全局事件目标（持久） | `save_global_event_target_as = my_country` |
| `clear_global_event_target(s)` | string / yes | 清除单个 / 全部全局事件目标 | `clear_global_event_target = my_country` |
| `play_song` | asset 名 | 播放音乐（须在电台中定义） | `play_song = "general_peace_1"` |
| `sound_effect` | asset 名 | 播放音效 | `sound_effect = "boom"` |
| `set_province_name` / `reset_province_name` | 块 / id | 改省名 / 还原 | `{ id = 325 name = LOC_KEY }` |
| `damage_units` | 块 | 按省/州/战略区伤害单位，可 `damage`/`org_damage`/`str_damage`/`ratio` | `{ province = 42 damage = 0.5 }` |
| `create_entity` | 块 | 生成地图实体（`x/y/z`、`province`、`rotation` 弧度、`scale`、`min_zoom`、`visible`） | `{ entity = entity_name id = 123 }` |
| `destroy_entity` / `set_entity_position` / `set_entity_rotation` / `set_entity_scale` / `set_entity_animation` / `set_entity_movement` | 块 | 实体操纵（角度单位弧度，360° ≈ 6.28） | `{ id = 123 rotation = 0.23 }` |
| `build_railway` | 块 | 建铁路；`path` 或 `start_province/target_province`，或 `start_state/target_state` | `{ level = 1 path = { 42 10 20 30 40 84 } }` |
| `create_purchase_contract` | 块 | 创建采购合同（1.13） | `{ seller = ROOT buyer = FROM civilian_factories = 2 }` |
| `add_state_resistance_compliance_modifier` | 块 | 给州加抵抗/顺从动态修正（1.17） | `{ modifier = dynamic_modifier_name state = 738 }` |

### Country scope 常用字段

| 字段 | 类型 | 作用 | 示例 |
|---|---|---|---|
| `add_political_power` / `add_stability` / `add_war_support` | float | 政治点 / 稳定度 / 战争支持（后两者 0–1） | `add_stability = 0.1` |
| `add_named_threat` | 块 | 调整世界紧张度并写入提示 | `{ threat = 5 name = GER_rhineland }` |
| `annex_country` | 块 | 吞并；`transfer_troops = yes` 才保留其师的装备 | `{ target = GER transfer_troops = yes }` |
| `declare_war_on` | 块 | 宣战；`type` 为 wargoal，`generator = { <state id> }` 供 take_state_focus 用 | `{ target = GER type = annex_everything }` |
| `white_peace` | scope / 块 | 白和；块形式可带 `message` | `white_peace = GER` |
| `start_peace_conference` | 块 | 和平会议；`score_factor`（0.0 = 白和）、`winner_scope`/`loser_scope` ∈ ALL/FACTION/LIMITED_FACTION/LIMITED | `{ tag = GER score_factor = 0.4 }` |
| `create_wargoal` | 块 | 授予战争目标；`expire` 天数，0/未设为永不失效 | `{ type = take_state_focus target = PREV generator = { 123 } }` |
| `remove_wargoal` | 块 | 移除战争目标，`type = all` 清空 | `{ type = all target = ROOT }` |
| `set_truce` | 块 | 停战 | `{ target = GER days = 90 }` |
| `start_civil_war` | 块 | 见 Scopes 节 | `{ ideology = democratic size = 0.1 }` |
| `add_civil_war_target` / `remove_civil_war_target` | scope | 把既有战争标记/取消为内战（1.9 / 1.12.13） | `add_civil_war_target = TAG` |
| `transfer_units_fraction` | 块 | 按比例转移师、装备、将领 | `{ target = SPD size = 0.5 army_ratio = 0.8 }` |
| `add_nuclear_bombs` / `launch_nuke` | int / 块 | 加核弹 / 投核弹（`use_nuke` 是否扣库存） | `{ state = 42 controller = GER use_nuke = yes }` |
| `add_resource` | 块 | 给州加资源 | `{ type = oil amount = 50 state = 88 }` |
| `create_import` / `give_resource_rights` / `remove_resource_rights` | 块 | 进口 / 授权资源 / 取消授权 | `{ receiver = POL state = 321 resources = { oil } }` |
| `add_fuel` / `set_fuel` / `set_fuel_ratio` | int/float | 燃料 | `set_fuel_ratio = 0.5` |
| `add_offsite_building` | 块 | 国家域离图建筑 | `{ type = arms_factory level = 1 }` |
| `modify_building_resources` | 块 | 改建筑产出资源 | `{ building = synthetic_refinery resource = oil amount = 1 }` |
| `damage_building` | 块 | 破坏建筑（`tags` 可批量；`repair_speed_modifier`） | `{ type = infrastructure state = 123 damage = 1 }` |
| `load_focus_tree` | 块 | 换国策树，`keep_completed`、`copy_completed_from` | `{ tree = british_focus keep_completed = yes }` |
| `complete_national_focus` / `unlock_national_focus` / `uncomplete_national_focus` | 块 | 完成 / 直接标记 / 撤销国策 | `{ focus = GER_autonomous_organization_todt }` |
| `reduce_focus_completion_cost` | 块 | 减少国策耗时（天，1.17） | `{ focus = focus_id cost = 35 }` |
| `add_ideas` / `add_timed_idea` | string / 块 | 加国家精神 / 限时精神（Modifiers 页指明这是最主要的加修正方式） | `add_ideas = my_idea` |

### Flow control（见 `Effect_s59_flow_control.wiki`）

| 字段 | 类型 | 作用 | 示例 |
|---|---|---|---|
| `if` | 块 + `limit` | limit 缺省视为恒真；**effect 必须写在块内才受 limit 约束** | `if = { limit = { tag = BHR } add_political_power = 100 }` |
| `else_if` / `else` | 块 | 顺序求值；可嵌套或平铺，重叠时优先平铺写法 | 见下 |
| `random` | `chance` 0–100 | 按百分比执行块内 effect | `random = { chance = 80 add_stability = 0.4 }` |
| `random_list` | 权重块 | 数字是**权重**不是百分比，按 权重/权重和 取概率；可用 `modifier = { factor = 1.3 … }` 与变量作权重 | 见下 |
| `for_loop_effect` | 块 | `start`/`end`/`compare`/`add`/`value`/`break`；默认 start=0、end=0、compare=less_than、add=1、value=v、break=break；上限 1000 次 | `start = -3 end = 9 add = 3` |
| `while_loop_effect` | 块 | 条件为真时循环，条件仅在每轮开头检查；上限 1000 次 | `limit = { country_exists = GER }` |

```hoi4
# if / else_if / else（平铺写法）
if = {
    limit = {
        stability < 0.3
    }
    add_stability = 0.3
}
else_if = {
    limit = {
        stability < 0.6
    }
    add_stability = 0.2
}
else = {
    add_stability = 0.1
}
```

```hoi4
# random_list：权重 + modifier 与变量
random_list = {
    30 = {
        modifier = {
            factor = 1.3
            has_country_flag = inward_perfect_flag
        }
        add_stability = 0.5
    }
    25 = {
        add_manpower = 10000
    }
    20 = {
        add_war_support = 0.5
    }
    my_variable = {
        army_experience = 100
    }
}
```

```hoi4
# for_loop_effect：-3 到 9 步长 3，共 15 政治点
for_loop_effect = {
    start = -3
    end = 9
    compare = less_than_or_equals
    add = 3
    value = value_name
    break = break_name
    add_political_power = value_name
}
```

```hoi4
# 三种 tooltip 手法混用
completion_reward = {
    hidden_effect = {
        every_subject_country = { country_event = my_event.1 }
    }
    custom_effect_tooltip = send_event_to_subjects_tt
    effect_tooltip = {
        add_political_power = 100
    }
    custom_effect_tooltip = reject_war_tt
}
```

### 常见错误 / 限制

- `if` 块写错位置时"静默无效"：effect 写在 `if = { }` 外面则永远执行（wiki 给出对照示例）。
- `random_list` 的数字不是百分比，总和不必为 100；权重 20 是权重 10 的两倍概率。
- 同一决议里的 `random_list` 默认**每次触发抽到同一结果**，需在决议块里加 `fixed_random_seed = no`；其它位置默认不固定，不必设置。
- 循环上限：`for_loop_effect` / `while_loop_effect` 均 1000 次（`MAX_EFFECT_ITERATION`，`common/defines/00_defines.lua`）。
- `add_dynamic_modifier` 的 tooltip 不显示含变量的修正项，只显示常量项——看起来"失效"其实生效，需 `custom_effect_tooltip` 说明。
- `play_song` / `sound_effect` 会对所有国家播放；单国播放要用 `scoped_play_song` / `scoped_sound_effect`。
- `save_event_target_as` 在 Scripted GUI 中不可用。
- `start_civil_war` 不能用于 history / bookmark effect；`states = all` 且含首都州时不触发。

### Meta effects（`Effect_s63_meta_effects.wiki`）

作用：把"只接受静态 token"的 effect 变成可用变量拼装的形式。

```hoi4
meta_effect = {
    text = {
        add_equipment_to_stockpile = {
            type = [EQ_TYPE]_[EQ_LEVEL]
            amount = eq_amount
        }
    }
    EQ_LEVEL = "[?eq_level|.0]"
    EQ_TYPE = "[This.GetEquipmentName]"
}
```

- `text = { ... }` 内写要生成的 effect；`[KEY]` 由下方同名参数替换。
- 替换值可来自变量格式化（`[?var|.0]` 取整数）或 scripted localisation。
- `debug = yes` 会把最终生成的 effect 打印到 game.log。

---

## 第 6 章 脚本化效果与脚本化触发器

### 脚本化效果（Scripted effects）

请求 URL：`https://hoi4.paradoxwikis.com/index.php?title=Scripted_effects&action=raw`
返回：`#REDIRECT [[Effect#Scripted effects]]`
实体内容 URL：`https://hoi4.paradoxwikis.com/index.php?title=Effect&action=raw&section=64`

### 语法规则

- 定义文件：`common/scripted_effects/*.txt`。
- 定义形态：
  ```hoi4
  scripted_effect_name = {
  	<effects>
  }
  ```
- 调用：`scripted_effect_name = yes`；**不会自动执行**，必须被别处调用。
- 控制台：`e scripted_effect_name`。
- 自定义控制台命令：名字以 `d_` 开头，控制台里省略 `d_`；执行时 **FROM = 执行命令的国家，ROOT = 选中的国家/州/角色**；命令行后续空格分隔的参数进入 `args` 临时数组。

```hoi4
d_transfer_states = {
	for_each_scope_loop = {
		array = args
		FROM = {
			transfer_state = PREV
		}
	}
}
```
调用：`transfer_states 123 321`

### 原版可直接复用的 scripted effects

| 名称 | scope | 作用 | 备注 |
|---|---|---|---|
| `instantiate_collaboration_government` | Country | 建立合作政府，当前 scope 为宗主 | 目标存在 `country_to_initiate` 临时变量 |
| `add_potential_special_forces_tree` | Country | 加 1 个特种部队分支专精 | — |
| `upgrade_economy_law` | Country | 经济法案向总动员推进一档 | 已在总动员则加 150 政治点；新增法案需手动改 |
| `gain_random_agency_upgrade` | Country | 随机获得可用情报局升级 | 无情报局时会先创建 |
| `add_ruling_to_dem` | Country | 执政党支持度全部转给民主集团 | 同类：`add_ruling_to_fas` / `_com` / `_neu` |
| `remove_any_country_role_from_character` | Character | 移除当前 scope 全部顾问角色 | 新增槽位需手动改 |
| `increase_state_category` | State | 州类别升到下一档（建筑位更多） | 对小岛、特大城市、`large_city` 无效；`city` 直接跳 Metropolis |
| `lerp` | Any | 生成 `lerp_result` 普通变量 = a+(b−a)·x | a/b/x 存于 `lerp_a`/`lerp_b`/`lerp_x`，x 截断在 0–1 |
| `store_core_states_on_game_start` | Country | 把当前核心州存为 ROOT 的数组 `core_states_at_game_start` | 只在国家历史里调用一次 |

### 脚本化触发器（Scripted triggers）

请求 URL：`https://hoi4.paradoxwikis.com/index.php?title=Scripted_triggers&action=raw`
返回：`#REDIRECT [[Triggers#Scripted triggers]]`
实体内容 URL：`https://hoi4.paradoxwikis.com/index.php?title=Triggers&action=raw&section=48`（1.16）

### 语法规则

- 定义文件：`common/scripted_triggers/*.txt`。
  ```hoi4
  scripted_trigger_name = {
  	<triggers>
  }
  ```
- 调用：`scripted_trigger_name = yes` 或 `= no`。
- **同名重复定义时，后加载生效**（按文件名与文件内顺序决定）。
- 部分原版 scripted trigger 被引擎硬编码引用，不能随意删除。

```hoi4
state_is_in_area = {
    OR = {
        state = 120
        state = 121
        state = 123
        state = 124
        state = 125
    }
}
```

```hoi4
focus = {
    id = TAG_focus_id
    available = {
        capital_scope = {
            state_is_in_area = yes
        }
    }
}
```

### Diplomacy scripted triggers（1.17）

- 两组互斥：可用性 `DIPLOMACY_<action>_ENABLE_TRIGGER`（默认 `common/scripted_triggers/diplomacy_scripted_triggers.txt`）；可见性 `is_diplomatic_action_valid_<action>`（默认 `common/scripted_triggers/00_diplo_action_valid_triggers.txt`）。
- 默认 scope = 发起动作的国家，`FROM` = 动作目标。
- 可用性 trigger 的 tooltip 会在悬停外交按钮时显示。
- 覆盖前需对照原版，否则会破坏游戏规则（例：英国在 MTG 下无法释放殖民地）。

```hoi4
DIPLOMACY_REVOKE_GUARANTEE_ENABLE_TRIGGER = {
    if = {
        limit = {
            has_game_rule = {
                rule = allow_revoke_guarantees
                option = BLOCKED
            }
        }
        custom_trigger_tooltip = {
            tooltip = RULE_ALLOW_REVOKE_GUARANTEES_BLOCKED_TOOLTIP
            always = no
        }
    }
    if = {
        limit = {
            tag = BHR
            FROM = { tag = QAT }
        }
        custom_trigger_tooltip = {
            tooltip = NO_REVOKING_ON_QAT_TT
            always = no
        }
    }
}
```

### Resistance initiation triggers

- `should_initiate_resistance`（默认 `common/scripted_triggers/00_resistance_initiate_triggers.txt`）决定抵抗是否自动启动。
- 州级覆盖写法：`should_initiate_resistance_<state id>_<state id>…`，必须回落到原名，否则覆盖后抵抗恒启动。

```hoi4
should_initiate_resistance_123_321 = {
	if = {
		limit = {
			tag = ENG
		}
		is_core_of = FRA
	}
	else = {
		should_initiate_resistance = yes
	}
}
```

### 原版可直接复用的 scripted triggers

| 名称 | scope | 作用 | 备注 |
|---|---|---|---|
| `can_ROOT_get_wargoal_on_THIS` | Country | ROOT 能否对当前 scope 造战争目标 | 需目标存在、不同阵营、非 ROOT 附庸 |
| `is_free_or_subject_of_root` | Country | 独立或是 ROOT 附庸 | — |
| `has_same_ideology` | Country | 与 ROOT 同意识形态 | 自定义意识形态需改；原版等价 `has_government = ROOT` |
| `is_enemy_ideology` | Country | 与 ROOT 敌对意识形态 | 共产/民主/法西斯互为敌对 |
| `has_ROOT_at_least_1_div_in_current_state_scope` | State | ROOT 在该州至少 1 个师 | — |
| `controls_or_subject_of` | State | 州由 ROOT 或其附庸控制 | — |
| `is_controlled_by_ROOT_or_ally` | State | 州由 ROOT / 附庸 / 同阵营控制 | — |
| `owns_or_subject_of` | State | 州由 ROOT 或其附庸拥有 | — |

---

## 第 7 章 变量与数据类型

### 变量（Variables）

请求 URL：`https://hoi4.paradoxwikis.com/index.php?title=Variables&action=raw`
返回：`#REDIRECT [[Data structures#Variables]]`（另有「本页旧版本」的 permanent link 提示）
实体内容 URL：`https://hoi4.paradoxwikis.com/index.php?title=Data_structures&action=raw&section=11`（1.16，落盘 52 KB）

### 数值与命名

- 变量 = 32 位有符号整数部分 + 0..99 999 的小数部分，写作 `<whole>.<decimals>`。
- 实际范围 −2 147 483 648.99 999 … 2 147 483 647.99 999；超出产生整数溢出（最大↔最小）。
- 可表示精度上限 **0.00001**，更细的小数被截断。
- 变量不存放在固定文件，由 effect（以及仅限临时变量的 trigger）动态创建。
- 数据库对象（国家、州、理念、装备类型等）有内部数字 ID；把变量设为 tag 即存该 tag 的 ID，之后当目标/scope 用时被解释为对应对象。
- 需要 `token:` 前缀的场合：给可 token 化类型赋字面量，如 `var_name = token:some_idea_name`。
- 命名：仅 A–Z a–z 0–9 与下划线，**不能以数字开头**（`123_my_variable` 非法）。
- 避免与游戏内建名冲突（如 `capital`）；惯例加前缀 `POL_capital`、`PC_capital`。

### 普通变量 vs 临时变量

| 对比项 | 普通变量（regular） | 临时变量（temp） |
|---|---|---|
| 操作符命名 | `set_variable` 等 | `set_temp_variable` 等（`variable` → `temp_variable`） |
| 生命周期 | 永久 | 仅当前 effect/trigger 块（不跨事件携带） |
| 能否在 trigger 块里修改 | 否 | 是 |
| 作用域 | 绑定 country/state/character/global | 无作用域，全局同一份 |
| 可在 scripted effect 内外传递 | 是 | 在 scripted effect/trigger 内部定义的临时变量，出了它可能消失；但外部先定义的会带进去并被正确修改 |

### 作用域语法

| 写法 | 含义 |
|---|---|
| `var_name` | 绑定 THIS |
| `GER.var_name` | 绑定德国 |
| `123.var_name` | 绑定州 123 |
| `global.var_name` | 绑定全局（**必须**写 `global`） |
| `PREV.PREV.var_name` | 绑定上两层的 scope |
| `event_target:my_event_target.var_name` | 绑定事件目标 |
| `ABC.capital:var_name` | 绑定 ABC 首都州；静态 scope 用 `.`，变量名用 `:` |
| `province_controllers^1234:capital:var_name` | 绑定控制省 1234 的国家的首都州 |

- `var:` 前缀：作为 scope 用时必需（`var:my_country_variable = { ... }`）；作为 effect/trigger 的目标时多数可省（`transfer_state = var:my_state_variable`）；`random_list` 的权重里可省；本地化里不需要（`[?var_name.GetName]`）。
- 变量与数组操作符（含 `check_variable`）里 `var:` **始终可选**。

```hoi4
every_country = {
    set_variable = { weighted_manpower = 0 }
    every_owned_state = {
        set_variable = { weighted_manpower = state_population_k }
        if = {
            limit = {
                NOT = { is_core_of = PREV }
            }
            divide_variable = { weighted_manpower = 10 }
        }
        add_to_variable = { PREV.weighted_manpower = weighted_manpower }
    }
}
```

### 本地化

- 显示变量：`[?var_name]`，**问号必需**（用于与事件目标区分）。
- 带 scope：`[?GER.num_of_dogs]`；变量本身是 scope 时仍要问号：`[?target_country.GetName]`。
- 仅支持动态本地化的 UI 才能显示；否则原样输出。
- 变量操作符默认无 tooltip；`add_to_temp_variable` 等支持 `tooltip = <loc key>`，`check_variable` 不支持，需 `custom_trigger_tooltip` / effect tooltip。
- tooltip 键内可用 `$LEFT$`（操作前的值）与 `$RIGHT$`（操作后的值）。

```hoi4
add_to_variable = {
    var = num_dogs
    value = ENG.num_cats
    tooltip = add_cats_to_dogs_tt
}
```
```yaml
 add_cat_to_dogs_tt: "Adds [ENG.GetAdjective] cats to our $LEFT$ dog(s) to get $RIGHT$ in total."
```

### 其它用法

- 未赋值变量读作 0；空值合并运算符 `?`：`cost = var_name?100`。
- 定向变量 `@TAG`：`var_name_@GER` 解析为 `var_name_GER`；可用 `@PREV`、`@var:target_var_name`；对州、意识形态组等也适用；与 flag 不同，是把目标 ID 存为独立变量而非拼进名字。
- 多目标后缀（如 `var_name_@THIS_@PREV`）技术上可行但行为极不一致，wiki 明确说规则仍未定论。

### 操作符字段表

| 字段 | 类型 | 作用 | 示例 |
|---|---|---|---|
| `set_variable` | 块 | 赋值，不存在则创建 | `{ var = my_variable value = 100 tooltip = set_var_to_100_tt }` |
| `set_temp_variable` | 块/简写 | 临时变量赋值 | `set_temp_variable = { temp_var = ROOT.overlord }` |
| `set_variable_to_random` | 块 | 随机值，结果 ∈ [min, max)；`integer = yes` 取整 | `{ var = random_num max = 11 integer = yes }` |
| `clear_variable` | 变量 | 彻底清除（仅普通变量） | `clear_variable = my_variable` |
| `add_to_variable` | 块 | 加 | `add_to_temp_variable = { temp_var = num_owned_states }` |
| `subtract_from_variable` | 块 | 减（等价于加负数） | `{ var = my_variable value = 100 }` |
| `multiply_variable` | 块 | 乘 | `multiply_temp_variable = { temp_var = num_owned_states }` |
| `divide_variable` | 块 | 除 | `divide_variable = { weighted_manpower = 10 }` |
| `modulo_variable` | 块 | 取欧几里得余数 | `{ var = my_variable value = 50 }` |
| `round_variable` | 变量 | 四舍五入到整数（恰好 .5 时取绝对值更大者，−1.5→−2） | `round_variable = my_variable` |
| `clamp_variable` | 块 | 夹到 [min,max]；min/max 可省略其一；只改当前值，之后可再越界 | `{ var = my_var min = 0 max = 2000 }` |
| `check_variable` | 块/简写 | 比较（trigger）；简写形式比较是严格的 | `check_variable = { my_var > 10 }` |
| `has_variable` | 变量 | 是否已赋值（值为 0 也算） | `has_variable = my_variable` |

### 数学表达式（value / accumulator）

- 结构：`{ value = X <操作> ... }`，以累加器（accumulator）为中心；`value` 是初值，后续操作符逐条作用于累加器。
- 支持操作（原表）：`add`、`subtract`、`multiply`、`divide`、`mod`、`min`、`max`、`clamp`、`round`、`pow`、`root`、`log`、`sin`、`cos`、`tan`、`atan`、`atan2`、`lerp`、`not`、`and`、`or`、`xor`、`equals`、`not_equals`、`greater_than_or_equals`、`less_than_or_equals`、`if`/`else`、`every_collection`。
- 精度说明（wiki 明写）：`atan`/`atan2`/`log`/`root`/`pow`（分数指数）为数值近似，可能有零点几的误差，需要精确整数时追加 `round = yes`；`pow` 的整数指数用重复乘法精确计算；`atan2(0,0)` 返回约 π/2。

```hoi4
value = 2
pow = 10
round = yes
```

```hoi4
{ value = 0
  every_collection = {
     named_collection = my_collection
     add = element_value } }
```

```hoi4
{ value = x
  if = { limit = { value = x  greater_than = 10 }  add = 100 }
  else = { subtract = 1 } }
```

### MTTH 变量

- 文件：`common/mtth/*.txt`，每个块是一个 MTTH 变量，块名即变量名。
- 结构与 MTTH 块一致：`base` / `factor` 起底，`modifier = { ... }` 内是触发条件与 `add` / `factor`。
- 引用：`set_variable = { my_var = mtth:my_mtth_variable_1 }`，按当前 scope 求值。

```hoi4
my_mtth_variable_1 = {
    base = 10
    modifier = {
        factor = 10
        is_major = yes
    }
    modifier = {
        add = -10
        tag = FRA
    }
}
my_mtth_variable_2 = {
    base = other_variable
    factor = 0.5
    add = 10
}
```

### 调试

| 字段/命令 | 作用 | 示例 |
|---|---|---|
| `log` | 写 `logs/game.log` | `log = "Current value of myVar in [THIS.GetName]: [?myVar]"` |
| `print_variables` | 导出到 `logs/variable_dumps/`，参数 `file`/`text`/`append`/`print_global`/`var_list` | `{ file = my_file var_list = { temp1 temp2 } }` |
| `set_var <var> <value>` | 控制台改值 | `set_var my_variable 10` |
| `get_var <var>` | 控制台打印 | `get_var my_variable` |
| `list_vars [scope]` | 列出当前 scope 变量 | `list_vars` |

### Token 值变量

- `token:xxx` 实际返回整数（通常是几万的数）并带"token 标记"，被解释为字符串表索引。
- `GetTokenKey` 取 token 字符串（不含 `token:` 前缀）：`[?some_var.GetTokenKey]`；`GetTokenLocalizedKey` 取同名本地化文本。
- 已知可 token 化类型（1.12）：ideas、`common/script_enums.txt` 全部项、意识形态/意识形态组、科技、装备类型（原型/非原型有时不一致）、行动、角色/将领（角色升为将领后 token 值改变，两者数值不等）、决议、建筑。
- 在 `set_(temp_)variable` 中赋 token 仍需 `token:` 前缀。

### 常见错误 / 限制

- 普通变量只能在 effect 块定义，trigger 块只能改临时变量。
- 变量作用域是绑定对象的：state scope 里读国家变量必须先加 scope 前缀。
- 精度上限 0.00001，超过被截断；数值越界溢出回绕。
- `clamp_variable` 不锁定后续赋值。
- 变量不能直接用在 idea 的 modifier 里，要用 dynamic modifier。
- 未赋值变量按 0 处理，容易掩盖拼写错误（配 `has_variable` 检查）。

---

## 第 8 章 修正体系（Modifiers）

### 修正总表（Modifiers）

URL：`https://hoi4.paradoxwikis.com/index.php?title=Modifiers&action=raw`（1.13，落盘 100 KB，原文 >100 KB 被工具截断）

### 语法规则

- 统一形态 `modifier_name = 0.1`，**加法叠加**到该 scope 的 modifier 总值；不同块里的同名 modifier 相加（0.2 + (−0.05) = +0.15）。
- **值为 0 永远无效果**；负值有效且为反向。
- 读取总值：`modifier@modifier_name`（国家/州）；将领用 `unit_modifier@…` / `leader_modifier@…`。
- 所有 modifier 值必须是数字，包括布尔型（须写 1 才生效）。
- **modifier 块不支持 `if`**；最接近的替代是 dynamic modifier + 变量。
- 不属于 modifier（即使看着像）：科技研究加成、装备加成、opinion modifier。
- 三种 tooltip 相关写法：

```hoi4
modifier = {
    hidden_modifier = {
        political_power_gain = 0.1
    }
    custom_modifier_tooltip = political_power_gain_tt
}
```

### 施加途径

| 途径 | 作用域 | 说明 |
|---|---|---|
| Ideas（`add_ideas` / `add_timed_idea`） | country | 加修正最简单的方式 |
| Dynamic modifiers | country / state / unit leader | 支持变量；州加修正的主要方式 |
| Country leader traits | country | 加在 idea（含顾问）或国家领袖上 |
| Unit leader traits | unit leader | 加在将领本身或其部队 |
| Global static modifiers | 硬编码触发条件 | 只能改内容，不能改名字 |
| Province static modifiers | province | 唯一给单个省加修正的途径 |
| Relation static modifiers | country→country | 唯一不写死 tag 的定向修正 |

### Dynamic modifiers

- 文件：`common/dynamic_modifiers/*.txt`，块名即 ID。
- 每日刷新；想立刻生效用 `force_update_dynamic_modifier`。
- 可施加到国家、州、将领；州上的变量必须是该州的变量，不能读国家/控制者的。
- **定义无法热重载**：改了必须重启游戏。
- 每日求值顺序：先把每个动态修正里的变量值临时重置为 0（常量值不重置）→ 按 `add_dynamic_modifier` 的添加顺序依次求值 → 求值期间块内变量一律按 0 处理（含依赖 `modifier@…` 或 MTTH 变量的）→ 该块求完才生效，再进入下一个。
- 参数：

| 字段 | 类型 | 作用 | 示例 |
|---|---|---|---|
| `icon` | sprite 名 | 显示图标，`interface/*.gfx` 中定义；不写则隐藏 | `icon = GFX_idea_unknown` |
| `enable` | trigger 块 | 满足时才生效（可选） | `enable = { always = yes }` |
| `remove_trigger` | trigger 块 | 满足时自动移除（可选） | `remove_trigger = { NOT = { has_variable = var_name } }` |
| `attacker_modifier` | bool | 州域时，对"不在该州但正在进攻该州敌军"的师也生效，默认 false | `attacker_modifier = yes` |

```hoi4
dynamic_modifier_name = {
    icon = GFX_idea_unknown
    enable = { always = yes }
    remove_trigger = {
        NOT = {
            has_variable = var_name
        }
    }
    political_power_gain = var_name
    weekly_manpower = 1000
    stability_factor = GER.stability_var
}
```

```hoi4
add_dynamic_modifier = { modifier = dynamic_modifier_name }
```

```hoi4
GER = {
    add_dynamic_modifier = {
        modifier = dynamic_modifier_name
        scope = POL
        days = 30
    }
}
```

- `scope` 指定"变量从哪个 scope 读"，修正本身仍施加在 `add_dynamic_modifier` 执行处。
- 移除：`remove_dynamic_modifier = { modifier = dynamic_modifier_name }`；若添加时指定过 `scope`，移除时也要写。
- 含变量的修正项不出现在 `add_dynamic_modifier` 的 tooltip 里，常量项会显示。
- 动态修正不能放 `equipment_bonus` / `research_bonus` 这类非 modifier 的理念属性。
- 性能：比 idea 差（每日刷新），能不用变量就优先用 national spirit。

### Static modifiers

文件：`common/modifiers/*.txt`，块名即静态修正 ID，共 5 类：

1. **Global modifiers**：由引擎硬编码决定何时生效（如非核心州惩罚、稳定度/战争支持效果），名字不能改，内容可改。
2. **Difficulty modifiers**：`common/difficulty_settings/*.txt`，外层 `difficulty_settings = { }`，内层 `difficulty_setting = { }`。
3. **Relation modifiers**：ROOT = 被施加方，FROM = 目标方；`valid_relation_trigger` 满足即自动移除。
4. **Province modifiers**：`add_province_modifier` / `remove_province_modifier`；图标要在 `interface/countrystateview.gui` 的 `custom_icon_container` 里注册，sprite 在 `interface/*.gfx`。
5. **Balance of power modifiers**：常含 `power_balance_weekly`（−1..1 区间）；用 `add_power_balance_modifier` / `remove_power_balance_modifier` / `remove_all_power_balance_modifiers`。

Difficulty setting 字段：

| 字段 | 类型 | 作用 | 示例 |
|---|---|---|---|
| `key` | loc key | 规则菜单显示名 | `key = difficulty_weaken_GER` |
| `modifier` | static modifier ID | 使用的静态修正 | `modifier = weaken_country` |
| `countries` | tag 列表 | 生效国家 | `countries = { SOV UKR BLR }` |
| `multiplier` | float | 最大档的倍率；5 档（含 0）按 1/4、1/2、3/4 递增 | `multiplier = 2.0` |

```hoi4
difficulty_settings = {
    difficulty_setting = {
        key = difficulty_weaken_GER
        modifier = weaken_country
        countries = { GER }
        multiplier = 2.0
    }
}
```

```hoi4
test_relation_modifier = {
	valid_relation_trigger = {
		FROM = {
			has_government = ROOT
		}
	}
	compliance_gain = 0.2
}
```

```hoi4
mod_modifier = {
	army_speed_factor = -0.5
	army_defence_factor = 0.5
	dig_in_speed_factor = 0.5
}
```

```hoi4
my_bop_modifier = {
    power_balance_weekly = -0.01
}
```

### Modifier definitions（自定义 modifier）

- 文件：`common/modifier_definitions/*.txt`，块名即 ID，同时作为本地化键。
- 作用：新建一个可被 `modifier@…` 读取的"伪变量"，默认无任何实际效果，只用来做加法聚合。

| 字段 | 类型 | 作用 | 示例 |
|---|---|---|---|
| `color_type` | good / bad / neutral | 数值着色；neutral 恒黄 | `color_type = good` |
| `value_type` | number / percentage / percentage_in_hundred / yes_no | 显示方式：原值 / 0–1 百分比 / 0–100 百分比 / 布尔（>1 为 yes） | `value_type = percentage` |
| `precision` | int ≤ 3 | 小数位数（引擎本身最多 3 位） | `precision = 1` |
| `postfix` | none / days / hours / daily | 数值后缀 | `postfix = daily` |
| `category` | 枚举，可多写 | 分类：none、all、country、state、unit_leader、army、naval、air、peace、politics、ai、defensive、aggressive、war_production、military_advancements、military_equipment、autonomy、government_in_exile、intelligence_agency | `category = country` |

```hoi4
modifier_definition_example = {
	color_type = good
	value_type = number
	precision = 1
	postfix = daily

	category = country
	category = state
}
modifier_definition_example_2 = {
    color_type = bad
    value_type = percentage
}
```

读取：`set_variable = { var_name = modifier@modifier_token_name }`；将领用 `leader_modifier@` / `unit_modifier@`。

### Opinion modifiers（不属于 modifier）

- 文件：`common/opinion_modifiers/*.txt`，位于 `opinion_modifiers = { ... }` 内；同名按"后加载生效"覆盖。
- 字段：

| 字段 | 类型 | 作用 | 示例 |
|---|---|---|---|
| `trade` | bool | true 影响贸易好感，默认 false 影响外交好感 | `trade = yes` |
| `value` | int | 好感变化量 | `value = -100` |
| `decay` | float | 每月向 0 衰减的速度；不写则不衰减 | `decay = 0.5` |
| `days` / `months` / `years` | int | 持续时间（1 月 = 30 天，1 年 = 365 天）；都不写为永久 | `months = 2` |
| `min_trust` / `max_trust` | int | 值可以变化的上下限 | `min_trust = 10` |

```hoi4
opinion_modifiers = {
    test_trade_modifier = {
        trade = yes
        value = -100    # Provides -100 trade opinion for 2 months
        months = 2
    }
    test_diplomatic_modifier = {
        value = 20      # Provides +20 diplomatic opinion that decays by 0.5 per month
        decay = 0.5
    }
}
```

- 只能通过 `add_opinion_modifier` / `reverse_add_opinion_modifier` 添加。

### List of modifiers 结构

落盘文件里的分类（`Modifiers.wiki` 第 308 行起）：

- `Country scope`：General、Politics、Diplomacy、Autonomy、Governments in exile、Equipment、Fuel and supply、Buildings、Resistance and compliance、Intelligence、Operatives、AI、Military outside of combat、MIOs、Unit leaders、General combat（后接海军/空军等，原文截断在此之后）。
- 每行带 **Modifier type**：`Flat`（绝对值）或 `Percentual`（百分比，写 0.3 表示 30%）。`Factor` 类字段（如 `*_factor`）全部是 Percentual。
- 例：`political_power_gain = 0.1` → +10%；`max_command_power = 20` → +20 点（Flat）；`conscription = 0.02` → +2%（Flat 的"百分点"写法）；`weekly_manpower = 1000` → Flat。

### 常见错误 / 限制

- 同一 modifier 写 `0` 完全不生效，不要用 0 覆盖。
- modifier 块里写 `if` 会被忽略（不支持条件）。
- 布尔类 modifier 必须写 `1`，写 `yes` 无效。
- dynamic modifier 定义改了不重启不生效；且不能放 `equipment_bonus`/`research_bonus`。
- 动态修正里含变量的项不进 tooltip，显示为"无效果"。
- 州域动态修正的变量必须定义在州上。
- relation / province / bop 修正的移除需要与添加时相同的标识（含 `id` / `scope`）。
- `difficulty_settings` 完全缺失时规则菜单打不开。

### 动态修正（Dynamic modifiers）

请求 URL：`https://hoi4.paradoxwikis.com/index.php?title=Dynamic_modifiers&action=raw`
返回：`#REDIRECT [[Modifiers#Dynamic modifiers]]`
实体内容见上节 `Modifiers` → Dynamic modifiers（原文同一节，未另设页面）。

### 静态修正（Static modifiers）

请求 URL：`https://hoi4.paradoxwikis.com/index.php?title=Static_modifiers&action=raw`
返回：`#REDIRECT [[Modifiers#Static modifiers]]`
实体内容见上节 `Modifiers` → Static modifiers（Global / Difficulty / Relation / Province / Balance of power 五类）。

### 修正键名单：陆战、海战、空战、针对性修正

作用域说明：本节多数键**不只在国家 scope**，也可用于 unit leader 与 navy leader scope。

| 修正键 | 取值语义 | 作用 |
|---|---|---|
| `offence` | 百分比；**国家 scope 无效** | 修改我方陆军、海军、空军的攻击值；国家 scope 要改用 `army_attack_factor` |
| `defence` | 百分比；**国家 scope 无效** | 修改我方陆军、海军、空军的防御值；国家 scope 要改用 `army_defence_factor` |
| `<Tactic>_preferred_weight_factor` | 百分比 | 修改指挥官选择指定战术的概率 |

坑：

- `offence` / `defence` 写进国家精神、国家修正里不生效，这是最常见的"数值不生效"来源；替代键是 `army_attack_factor` / `army_defence_factor`。
- `<Tactic>` 要换成 `common/combat_tactics.txt` 里真实存在的战术名，例如 `tactic_ambush_preferred_weight_factor`；战术本身在该文件定义。
- 本节的三个键从 1.0 / 1.6 起存在，与 1.13 版本行为一致。

---



作用域说明：本节多数键**不只在国家 scope**，也可用于 unit leader scope。

| 修正键 | 取值语义 | 作用 |
|---|---|---|
| `acclimatization_cold_climate_gain_factor` | 百分比 | 寒冷气候适应度增长倍率 |
| `acclimatization_hot_climate_gain_factor` | 百分比 | 炎热气候适应度增长倍率 |
| `air_superiority_bonus_in_combat` | 百分比 | 拥有制空权带来的战斗内加成 |
| `army_attack_factor` | 百分比 | 陆军攻击加成 |
| `army_core_attack_factor` | 百分比 | 陆军在核心领土上的攻击加成 |
| `army_claim_attack_factor` | 百分比；1.17 新增 | 陆军在有宣称领土上的攻击加成 |
| `army_attack_against_major_factor` | 百分比；1.11 起 | 对主要国家陆军的攻击加成 |
| `army_attack_against_minor_factor` | 百分比；1.11 起 | 对非主要国家陆军的攻击加成 |
| `army_attack_speed_factor` | 百分比 | 陆军发起进攻的速度 |
| `army_breakthrough_against_major_factor` | 百分比；1.11 起 | 对主要国家陆军的突破加成 |
| `army_breakthrough_against_minor_factor` | 百分比；1.11 起 | 对非主要国家陆军的突破加成 |
| `army_defence_factor` | 百分比 | 陆军防御加成 |
| `army_defence_against_major_factor` | 百分比；1.11 起 | 对主要国家陆军的防御加成 |
| `army_defence_against_minor_factor` | 百分比；1.11 起 | 对非主要国家陆军的防御加成 |
| `army_core_defence_factor` | 百分比 | 陆军在核心领土上的防御加成 |
| `army_claim_defence_factor` | 百分比；1.17 新增 | 陆军在有宣称领土上的防御加成 |
| `army_speed_factor` | 百分比 | 陆军速度加成 |
| `army_strength_factor` | 百分比；1.11 起 | 陆军兵力（strength）加成 |
| `<unit type>_attack_factor` | 百分比；只认 `army_armor`、`army_artillery`、`army_infantry`、`cavalry`、`mechanized`、`motorized`、`special_forces` | 指定兵种的攻击加成 |
| `<unit type>_defence_factor` | 百分比；兵种白名单同上 | 指定兵种的防御加成 |
| `<unit type>_speed_factor` | 百分比；只认 `army_armor` 与 `cavalry`；**`cavalry_speed_factor` 当前失效、游戏不识别** | 指定兵种的速度加成 |
| `modifier_army_sub_unit_<unit type>_attack_factor` | 百分比；`<unit type>` 可为所有已定义营（含 mod 新增营） | 指定营的攻击加成 |
| `modifier_army_sub_unit_<unit type>_defence_factor` | 百分比；同上 | 指定营的防御加成 |
| `modifier_army_sub_unit_<unit type>_speed_factor` | 百分比；同上 | 指定营的速度加成 |
| `army_morale` | 绝对值 | 师恢复率（recovery rate） |
| `army_morale_factor` | 百分比 | 师恢复率按比例修正 |
| `army_org` | 绝对值 | 陆军组织度 |
| `army_org_factor` | 百分比 | 陆军组织度按比例修正 |
| `army_org_regain` | 百分比（键名无 `_factor`，但类型标 Percentual） | 陆军组织度恢复速度 |
| `breakthrough_factor` | 百分比 | 全军突破 |
| `cas_damage_reduction` | 百分比 | 降低近距空中支援（CAS）造成的伤害 |
| `combat_width_factor` | 百分比 | 改变己方战斗宽度 |
| `coordination_bonus` | 百分比；1.11 起 | 协调加成，即伤害打在首要目标而非摊开的比例 |
| `dig_in_speed` | 绝对值 | 挖壕（entrenchment）速度 |
| `dig_in_speed_factor` | 百分比 | 挖壕速度按比例修正 |
| `experience_gain_army_unit` | 绝对值 | 陆军师获得的经验 |
| `experience_gain_army_unit_factor` | 百分比 | 陆军师经验按比例修正 |
| `experience_loss_factor` | 百分比 | 战斗中师经验的损失 |
| `initiative_factor` | 百分比；1.11 起 | 主动性（initiative） |
| `land_night_attack` | 百分比 | 夜间进攻所受惩罚 |
| `max_dig_in` | 绝对值；**也可用于 state scope** | 最大堑壕值 |
| `max_dig_in_factor` | 百分比；**也可用于 state scope** | 最大堑壕值按比例修正 |
| `max_planning` | 绝对值 | 最大计划值 |
| `max_planning_factor` | 百分比；1.9 起 | 最大计划值按比例修正 |
| `pocket_penalty` | 百分比 | 减少被包围（口袋）时部队承受的惩罚 |
| `recon_factor` | 百分比 | 侦察 |
| `recon_factor_while_entrenched` | 百分比 | 处于堑壕状态时的侦察 |
| `special_forces_cap` | 百分比 | 特种部队上限 |
| `special_forces_min` | 绝对值 | 特种部队下限 |
| `terrain_penalty_reduction` | 百分比；**只在 unit_leader scope 生效**（尽管写时原版国家精神里出现过该键） | 降低地形带来的惩罚 |
| `org_loss_at_low_org_factor` | 百分比 | 低组织度时部队的组织度损失 |
| `org_loss_when_moving` | 百分比 | 部队移动时的组织度损失 |
| `planning_speed` | 百分比；**state scope 也可用** | 计划速度 |
| `experience_gain_<unit type>_combat_factor` | 百分比；1.11 起；单位定义在 `common/units/*.txt` | 指定兵种战斗中的经验获取 |
| `experience_gain_<unit type>_training_factor` | 百分比；1.11 起；单位定义在 `common/units/*.txt` | 指定兵种训练时的经验获取 |

坑：

- `terrain_penalty_reduction` 写在国家修正里不生效，只认 unit_leader scope；这是把"地形适应"写进国家精神的经典踩坑点。
- `cavalry_speed_factor` 已是死键；`<unit type>_speed_factor` 只支持 `army_armor`、`cavalry` 两个兵种。
- 三套兵种键的区别：`<unit type>_*`（7 种固定白名单）、`modifier_army_sub_unit_<unit type>_*`（任意已定义营，含 mod 营）、`experience_gain_<unit type>_*`（按 `common/units` 里的单位）。给 MUVLUV 这类自制兵种加成就必须用 `modifier_army_sub_unit_` 前缀那套。
- `army_org_regain` 名字没有 `_factor` 但按百分比算，别当绝对值写 10。
- 可进 state scope 的三个例外：`max_dig_in`、`max_dig_in_factor`、`planning_speed`。
- 1.11 一次性加了一批 `*_against_major/minor`、`initiative_factor`、`army_strength_factor`、`coordination_bonus`；1.17 才加 `army_claim_attack_factor` / `army_claim_defence_factor`。写给旧版本 mod 时不要用新键。

---



作用域说明：本节无 SVersion 标注。部分键可做 targeted modifier 或用于 unit leader / state scope（表内注明）。

| 修正键 | 取值语义 | 作用 |
|---|---|---|
| `naval_invasion_prep_speed` | 绝对值；**可做 targeted modifier，也可用于 unit leader scope** | 登陆准备速度 |
| `naval_invasion_capacity` | 绝对值 | 同时能保持登陆计划的师数 |
| `naval_invasion_penalty` | 百分比；与 `amphibious_invasion_defence` 互为反向；**也可用于 state scope** | 登陆方所受惩罚 |
| `naval_invasion_planning_bonus_speed` | 百分比；1.11 起 | 登陆准备期间计划加成的累积速度 |
| `amphibious_invasion` | 百分比；1.6 起 | 登陆过程中单位的速度 |
| `amphibious_invasion_defence` | 百分比；与 `naval_invasion_penalty` 互为反向；**也可用于 state scope** | 登陆给守方带来的惩罚 |
| `invasion_preparation` | 百分比；与 `naval_invasion_prep_speed` 互为反向；**可用于 unit leader scope** | 执行登陆所需的准备量 |

坑：

- 两对互逆键不要混：`naval_invasion_prep_speed`（准备速度，越大越快）↔ `invasion_preparation`（所需准备，越大越慢）；`naval_invasion_penalty`（害登陆方）↔ `amphibious_invasion_defence`（利守方）。
- "登陆准备"与"登陆计划加成"是两条不同进度条：前者 `naval_invasion_prep_speed`，后者 `naval_invasion_planning_bonus_speed`。
- 想给某个沿岸州加防御，应把 `amphibious_invasion_defence` 或 `naval_invasion_penalty` 写进 state scope。

---



作用域说明：本节多数键**不只在国家 scope**，也可用于 navy leader scope，以及装备模块（equipment modules）内。

| 修正键 | 取值语义 | 作用 |
|---|---|---|
| `convoy_escort_efficiency` | 百分比；1.6 起 | 护航任务效率 |
| `convoy_raiding_efficiency_factor` | 百分比；1.6 起 | 破交（袭击运输船）任务效率 |
| `convoy_retreat_speed` | 百分比；1.6 起 | 运输船撤退速度 |
| `critical_receive_chance` | 百分比；1.6 起 | 敌方对我方舰船打出致命一击的概率 |
| `experience_gain_navy_unit` | 绝对值；1.6 起 | 舰船每日经验获取 |
| `experience_gain_navy_unit_factor` | 百分比；1.6 起 | 舰船经验按比例修正 |
| `mines_planting_by_fleets_factor` | 百分比；1.6 起 | 舰队布雷任务效率 |
| `mines_sweeping_by_fleets_factor` | 百分比；1.6 起 | 舰队扫雷任务效率 |
| `naval_accidents_chance` | 百分比；1.6 起 | 舰船意外沉没或受损的概率 |
| `navy_anti_air_attack` | 绝对值；1.6 起 | 舰船对敌机的攻击 |
| `navy_anti_air_attack_factor` | 百分比；1.6 起 | 舰船对空攻击按比例修正 |
| `naval_coordination` | 百分比；1.6 起 | 发现目标或切换任务时舰队的集结/散开速度 |
| `naval_critical_effect_factor` | 百分比；1.6 起 | 我方舰船承受持续致命一击的效果 |
| `naval_critical_score_chance_factor` | 百分比；1.6 起 | 我方对敌打出致命一击的概率 |
| `naval_damage_factor` | 百分比；1.6 起 | 我方舰船造成的伤害 |
| `naval_defense_factor` | 百分比；1.6 起 | 我方舰船承受的伤害 |
| `naval_detection` | 百分比；1.6 起 | 我方舰船发现潜艇的概率 |
| `naval_enemy_fleet_size_ratio_penalty_factor` | 百分比；1.6 起 | 敌方舰数多于我方时所受的惩罚 |
| `naval_enemy_positioning_in_initial_attack` | 绝对值；1.11 起 | 初始海战中敌方的阵位 |
| `naval_enemy_retreat_chance` | 百分比；1.6 起 | 敌方撤退概率 |
| `naval_has_potf_in_combat_attack` | 百分比；1.6 起 | 与"舰队之光"（pride of the fleet）同战时的海军攻击 |
| `naval_has_potf_in_combat_defense` | 百分比；1.6 起 | 与"舰队之光"同战时的海军防御 |
| `naval_hit_chance` | 百分比；1.6 起 | 海战攻击命中概率 |
| `naval_mine_hit_chance` | 百分比；1.6 起 | 水雷命中概率 |
| `naval_mines_damage_factor` | 百分比；1.6 起 | 我方水雷对敌舰的伤害 |
| `naval_mines_effect_reduction` | 百分比；1.6 起 | 减免敌方水雷对我方的伤害 |
| `naval_morale` | 绝对值；1.6 起 | 海军恢复率 |
| `naval_morale_factor` | 百分比；1.6 起 | 海军恢复率按比例修正 |
| `naval_night_attack` | 百分比；1.11 起 | 夜间我方舰船造成的伤害 |
| `naval_retreat_chance` | 百分比；1.6 起 | 我方舰船撤退概率 |
| `naval_retreat_chance_after_initial_combat` | 百分比；1.11 起 | 首轮交战后我方舰船撤退概率 |
| `naval_retreat_speed` | 百分比；1.6 起 | 我方舰船撤退速度 |
| `naval_retreat_speed_after_initial_combat` | 百分比；1.11 起 | 首轮交战后我方舰船撤退速度 |
| `naval_speed_factor` | 百分比；1.6 起 | 舰船速度 |
| `navy_org` | 绝对值 | 海军组织度 |
| `navy_org_factor` | 百分比 | 海军组织度按比例修正 |
| `navy_max_range` | 绝对值 | 海军最大航程 |
| `navy_max_range_factor` | 百分比 | 海军最大航程按比例修正 |
| `naval_torpedo_cooldown_factor` | 百分比；1.6 起 | 鱼雷发射冷却（射速） |
| `naval_torpedo_hit_chance_factor` | 百分比；1.6 起 | 我方鱼雷命中敌舰的可能性 |
| `naval_torpedo_reveal_chance_factor` | 百分比；1.6 起 | 我方潜艇发射鱼雷时暴露的概率 |
| `naval_torpedo_screen_penetration_factor` | 百分比；1.6 起 | 我方鱼雷削减敌方屏卫的速率 |
| `naval_torpedo_damage_reduction_factor` | 百分比；1.12 起 | 敌方鱼雷对我方舰船造成的伤害 |
| `naval_torpedo_enemy_critical_chance_factor` | 百分比；1.12 起 | 敌方鱼雷对我方打出致命一击的概率（wiki 原文误拼 cricical） |
| `naval_light_gun_hit_chance_factor` | 百分比；1.12 起 | 我方轻炮命中敌舰概率 |
| `naval_heavy_gun_hit_chance_factor` | 百分比；1.12 起 | 我方重炮命中敌舰概率 |
| `navy_capital_ship_attack_factor` | 百分比；1.6 起 | 主力舰攻击 |
| `navy_capital_ship_defence_factor` | 百分比；1.6 起 | 主力舰防御 |
| `navy_screen_attack_factor` | 百分比；1.6 起 | 屏卫舰攻击 |
| `navy_screen_defence_factor` | 百分比；1.6 起 | 屏卫舰防御 |
| `navy_submarine_attack_factor` | 百分比；1.6 起 | 潜艇攻击 |
| `navy_submarine_defence_factor` | 百分比；1.6 起 | 潜艇防御 |
| `navy_submarine_detection_factor` | 百分比；1.6 起 | 我方对敌方潜艇的探测 |
| `navy_visibility` | 百分比；1.6 起 | 海军可见度 |
| `navy_weather_penalty` | 百分比；1.11 起 | 恶劣天气下海军所受惩罚 |
| `night_spotting_chance` | 百分比；1.11 起 | 夜间发现敌舰的概率 |
| `positioning` | 百分比；1.6 起 | 海军阵位（positioning） |
| `repair_speed_factor` | 百分比；1.6 起 | 船坞修理海军的速度 |
| `screening_efficiency` | 百分比；1.6 起 | 屏卫舰的运作效率 |
| `screening_without_screens` | 百分比；1.11 起 | 无屏卫舰时的基础屏卫值 |
| `ships_at_battle_start` | 百分比；1.6 起 | 首次接触时参战的舰数 |
| `spotting_chance` | 百分比；1.6 起 | 发现敌方舰船的概率 |
| `strike_force_movement_org_loss` | 百分比；1.6 起 | 打击部队（strike force）移动时的组织度损失 |
| `sub_retreat_speed` | 百分比；1.6 起 | 潜艇撤退速度 |
| `submarine_attack` | 百分比；1.6 起 | 潜艇攻击 |

坑：

- 攻防成对但不能互换：`naval_damage_factor`（我方打出去的伤害）与 `naval_defense_factor`（我方承受的伤害）；`naval_critical_score_chance_factor`（我方打出暴击）与 `critical_receive_chance`（我方被暴击）。
- 只有 `naval_enemy_positioning_in_initial_attack` 是绝对值，其余 `naval_*` 基本是百分比；把它按 0.3 写会几乎无效。
- 同一节里 `navy_org` / `navy_org_factor`、`navy_max_range` / `navy_max_range_factor` 各有绝对与百分比两版，别只写一半就以为生效。
- 本节键还可写进装备模块，等同于给装了该模块的舰船单独加成；写进 navy leader（海军将领特质）同样成立。
- 1.12 才出现的鱼雷/火炮命中类键（`naval_torpedo_damage_reduction_factor`、`naval_light_gun_hit_chance_factor`、`naval_heavy_gun_hit_chance_factor` 等）不要用到 1.11 及更早版本。

---



作用域说明：节内无额外作用域说明，均为国家 scope 的航母相关键。

| 修正键 | 取值语义 | 作用 |
|---|---|---|
| `navy_carrier_air_agility_factor` | 百分比；1.6 起 | 从航母起飞执行任务的飞机机动 |
| `navy_carrier_air_attack_factor` | 百分比；1.6 起 | 从航母起飞执行任务的飞机攻击 |
| `navy_carrier_air_targetting_factor` | 百分比；1.6 起；wiki 原文拼写为 `targetting` | 从航母起飞执行任务的飞机目标选择 |
| `air_carrier_night_penalty_reduction_factor` | 百分比 | 航母航空兵的夜间惩罚减免 |
| `carrier_capacity_penalty_reduction` | 百分比；1.6 起 | 航母超载（飞机数超容量）惩罚减免 |
| `carrier_traffic` | 百分比；1.6 起 | 航母调度（traffic） |
| `sortie_efficiency` | 百分比；1.6 起 | 战斗中航母为飞机加油挂弹的速度 |
| `carrier_sortie_hours_delay` | 绝对值（小时）；1.12 起 | 航母为飞机加油挂弹的延迟 |
| `carrier_night_traffic` | 百分比；1.11 起 | 航母夜间调度 |
| `fighter_sortie_efficiency` | 百分比；1.6 起 | 战斗中航母为战斗机加油挂弹的速度 |

坑：

- 前缀分两类：`navy_carrier_*` 管舰载机本身的属性，`air_carrier_*` 只有夜间惩罚减免一条，`carrier_*` 管航母平台（调度、容量、整备延迟）。
- `sortie_efficiency` 是通用整备速度，`fighter_sortie_efficiency` 只作用于战斗机，两者同开会叠加但作用对象不同。
- `carrier_sortie_hours_delay` 是本节唯一绝对值（小时），写成 0.2 没有意义。
- `targetting` 三个 t 是游戏内部字符串，照抄。

---



作用域说明：本节多数键**不只在国家 scope**，也可用于 ace scope。

| 修正键 | 取值语义 | 作用 |
|---|---|---|
| `air_accidents_factor` | 百分比 | 空中事故发生概率 |
| `air_ace_bonuses_factor` | 百分比；1.11 起 | 王牌提供的加成 |
| `air_ace_generation_chance_factor` | 百分比；1.11 起 | 王牌出现的概率 |
| `ace_effectiveness_factor` | 百分比 | 王牌效能 |
| `air_agility_factor` | 百分比 | 我方飞机机动 |
| `air_attack_factor` | 百分比 | 我方飞机攻击 |
| `air_defence_factor` | 百分比 | 我方飞机防御 |
| `air_interception_detect_factor` | 百分比 | 执行拦截任务时发现敌机的概率 |
| `naval_strike_targetting_factor` | 百分比 | 执行对海打击任务时飞机选定目标的能力 |
| `port_strike` | 百分比 | 港口打击任务中飞机造成的伤害 |
| `air_close_air_support_org_damage_factor` | 百分比；1.11 起 | 近距空中支援任务对师组织度的伤害 |
| `air_bombing_targetting` | 百分比 | 对地轰炸的目标选择 |
| `air_cas_efficiency` | 百分比 | 近距空中支援效率 |
| `air_cas_present_factor` | 百分比 | 近距空中支援在陆战中的影响力 |
| `air_escort_efficiency` | 百分比 | 飞机缠斗（dogfight）能力 |
| `air_home_defence_factor` | 百分比；1.11 起 | 在本土区域（与首都陆路相连的州）防守时的飞机防御 |
| `air_intercept_efficiency` | 百分比 | 空中拦截效率 |
| `air_manpower_requirement_factor` | 百分比；示例为负值 `-0.5` | 部署一架飞机所需人力 |
| `air_maximum_speed_factor` | 百分比 | 空军最大速度 |
| `air_mission_efficiency` | 百分比 | 飞机执行任务时的效率 |
| `air_mission_xp_gain_factor` | 百分比 | 飞机执行任务的经验获取 |
| `air_nav_efficiency` | 百分比 | 港口打击与对海轰炸任务的效率 |
| `air_night_penalty` | 百分比 | 空军夜间承受的惩罚 |
| `air_power_projection_factor` | 百分比 | 飞机提供的投射力量（power projection） |
| `air_range_factor` | 百分比 | 飞机航程 |
| `air_strategic_bomber_bombing_factor` | 百分比 | 战略轰炸任务效率 |
| `air_strategic_bomber_night_penalty` | 百分比 | 战略轰炸任务的夜间惩罚 |
| `air_superiority_detect_factor` | 百分比 | 制空权任务中发现敌机的概率（界面上显示为 Fighter Detection） |
| `air_superiority_efficiency` | 百分比 | 制空权任务效率 |
| `air_training_xp_gain_factor` | 百分比；1.6 起 | 训练获得的空军经验 |
| `air_untrained_pilots_penalty_factor` | 百分比；1.6 起 | 经验不足的飞行员所受惩罚 |
| `air_weather_penalty` | 百分比 | 天气给飞机带来的惩罚 |
| `air_wing_xp_loss_when_killed_factor` | 百分比 | 飞机被击落造成的经验损失 |
| `army_bonus_air_superiority_factor` | 百分比 | 制空权给陆战带来的加成 |
| `enemy_army_bonus_air_superiority_factor` | 百分比 | 敌方制空权对陆战的影响 |
| `ground_attack_factor` | 百分比 | 飞机对敌方师的对地攻击加成 |
| `mines_planting_by_air_factor` | 百分比 | 飞机布雷效率 |
| `mines_sweeping_by_air_factor` | 百分比 | 飞机扫雷效率 |
| `strategic_bomb_visibility` | 百分比 | 敌方发现我方战略轰炸机的概率 |
| `rocket_attack_factor` | 百分比 | 火箭的攻击 |

坑：

- `air_manpower_requirement_factor` 要写负值才减人力；写正数等于要求更多人力。
- `air_superiority_detect_factor` 与 `air_interception_detect_factor` 分别对应"制空任务"和"拦截任务"，界面名不等于键名（前者显示 Fighter Detection）。
- `air_home_defence_factor` 的"本土"定义是与首都陆路相连的州，海外属地不算。
- `army_bonus_air_superiority_factor` / `enemy_army_bonus_air_superiority_factor` 是空军键但作用在陆战结算上，和 `air_superiority_bonus_in_combat`（Land combat 节）容易重名混淆。
- 本节键也可用于 ace（王牌）scope；`targetting` 同样是原文拼写。

---



作用域说明：本节全部键**必须写在专属的 targeted 块里**，不能混进普通修正块。

写法（wiki 原文）：

```
targeted_modifier = {
    tag = FROM    # 也可以是一个存着 scope 的变量
    attack_bonus_against = 0.1
    defense_bonus_against = 0.1
}
```

适用位置：ideas、traits、advisors、decisions 里的 `targeted_modifier = { ... }`，以及 relation modifiers。

| 修正键 | 取值语义 | 作用 |
|---|---|---|
| `extra_trade_to_target_factor` | 百分比；1.5 起 | 给目标国增加可供贸易的额外产出资源 |
| `generate_wargoal_tension_against` | 绝对值；1.5 起 | 我方针对目标国制造战争借口所需的世界紧张度 |
| `cic_to_target_factor` | 百分比；1.5 起 | 把本国一部分民用工业产能给目标国 |
| `mic_to_target_factor` | 百分比；1.5 起 | 把本国一部分军用工业产能给目标国 |
| `trade_cost_for_target_factor` | 百分比；1.5 起 | 目标国购买本国资源的成本 |
| `targeted_legitimacy_daily` | 绝对值；1.6 起 | 目标国的每日合法性变化 |
| `attack_bonus_against` | 百分比；1.5 起；**有 bug：对处于防御状态的单位不生效** | 对目标国军队的攻击加成 |
| `attack_bonus_against_cores` | 百分比；1.5 起 | 在目标国核心领土上对其军队的攻击加成 |
| `breakthrough_bonus_against` | 百分比；1.5 起 | 对目标国军队的突破加成 |
| `defense_bonus_against` | 百分比；1.5 起；**有 bug：对处于进攻状态的单位不生效** | 对目标国军队的防御加成 |

写法与限制（这是最容易写错的一节）：

- `targeted_modifier` 与 `modifier` 是**完全独立的两个块**。把 `targeted_modifier = { ... }` 塞进 `modifier = { ... }`（或反过来把 `tag = X` 写进 `modifier`）都不生效，游戏不报错、只是静默忽略。
- `tag = FROM` 里的 `FROM` 是 scope 关键字；也可以给一个存着 scope 的变量（如 `tag = var:xxx`）。目标由这个 scope 决定，键本身不带 `tag` 参数。
- 一批同目标键写在同一个 `targeted_modifier` 块里，用同一个 `tag`；要给多个国家分别加成，就写多个 `targeted_modifier` 块。
- 本节键都是"相对某个 tag"的，所以只写 key = value、不写 `tag` 时无法确定对象；idea / advisor / decision 里都走同一套块结构。
- `attack_bonus_against` 与 `defense_bonus_against` 的 bug 意味着不能靠它们做"攻防双向"的对某国特化，只能在对应姿态下生效（攻击方用前者、防守方用后者）。
- 没有 `defense_bonus_against_cores` 这类对称键；本节只有 `attack_bonus_against_cores`。

### 修正键名单：州、将领、科研、战略区作用域与叠加规则

作用域说明（wiki 原文）：一部分国家 scope 键（例如 Land combat 节里的一部分）虽然没列在本节，也能进 state scope；本节里很大一部分 state scope 键还能继续进 province scope。
本节列表之外可确认能进 state scope 的键（来自其他节的 Notes）：`max_dig_in`、`max_dig_in_factor`、`planning_speed`、`naval_invasion_penalty`、`amphibious_invasion_defence`、`compliance_gain`、`compliance_growth`。

| 修正键 | 取值语义 | 作用 |
|---|---|---|
| `army_speed_factor_for_controller` | 百分比 | 州控制者的师速度 |
| `attrition_for_controller` | 百分比 | 州控制者的损耗 |
| `equipment_capture_for_controller` | 绝对值；1.13 起 | 州控制者的装备缴获比例 |
| `equipment_capture_factor_for_controller` | 百分比；1.13 起 | 州控制者的装备缴获比例（按比例版） |
| `enemy_army_speed_factor` | 百分比；1.13 起 | 与州所有者交战的师的速度 |
| `enemy_local_supplies` | 百分比；1.13 起 | 与州所有者交战的师的补给 |
| `enemy_attrition` | 百分比；1.13 起 | 与州所有者交战的师的损耗 |
| `enemy_truck_attrition_factor` | 百分比；1.13 起 | 与州所有者交战的师的卡车损耗 |
| `compliance_gain` | 绝对值；1.9 起；**也可进国家 scope，也可做 targeted modifier** | 当前州的顺从度获得 |
| `compliance_growth` | 百分比；1.9 起；**也可进国家 scope** | 当前州的顺从度增长速度 |
| `disable_strategic_redeployment` | 布尔（只接受 1）；1.9 起 | 禁止该州内的战略调动 |
| `disable_strategic_redeployment_for_controller` | 布尔（只接受 1）；1.9 起 | 对该州控制者禁止战略调动 |
| `enemy_intel_network_gain_factor_over_occupied_tag` | 百分比；1.9 起 | 敌方情报网强度增长 |
| `local_building_slots` | 绝对值；1.9 起 | 建筑槽数量 |
| `local_building_slots_factor` | 百分比；1.9 起 | 建筑槽数量按比例修正 |
| `local_factories` | 百分比；1.9 起 | 州内可用工厂数 |
| `local_factory_energy_consumption` | 百分比；1.17 起；**游戏文件注释把它错标成 0 位小数整数，代码实际用小数** | 州内工厂的能源消耗 |
| `local_factory_energy_consumption_per_infrastructure` | 百分比；1.17.2 起 | 按州基础设施计算的工厂能源消耗 |
| `local_factory_sabotage` | 百分比；1.9 起 | 工厂被破坏的概率 |
| `local_intel_to_enemies` | 百分比；1.9 起 | 泄露给敌人的情报量 |
| `local_manpower` | 百分比；1.4 起 | 可用人力 |
| `local_non_core_manpower` | 百分比；1.3.3 起 | 可用非核心人力 |
| `local_org_regain` | 百分比；**可用于 province 与 strategic region** | 战后恢复的组织度 |
| `local_resource_gain_efficiency_per_infrastructure` | 百分比；1.17.2 起 | 按州基础设施计算的资源获取效率 |
| `local_resources` | 绝对值；1.9 起 | 可用资源量 |
| `local_supplies` | 百分比；1.9 起 | 可用补给量 |
| `local_supplies_for_controller` | 百分比；1.9 起 | 控制者可用的补给量 |
| `local_supply_impact_factor` | 百分比；1.12 起 | 州本地补给的影响力 |
| `local_non_core_supply_impact_factor` | 百分比；1.12 起 | 州未被控制者核心化时本地补给的影响力 |
| `mobilization_speed` | 百分比；1.9 起 | 动员速度 |
| `non_core_manpower` | 百分比；1.9 起 | 招募到的非核心人力 |
| `max_fuel_building` | 百分比；**不需要写在 building 里**；数值语义是"千单位"的燃油容量 | 该州控制者从建筑获得的燃油容量 |
| `recruitable_population` | 绝对值；1.9 起 | 可招募人力 |
| `recruitable_population_factor` | 百分比；1.9 起 | 可招募人力按比例修正 |
| `resistance_damage_to_garrison` | 百分比；1.9 起 | 抵抗对驻军造成的伤害 |
| `resistance_decay` | 百分比；1.9 起 | 抵抗衰减速度 |
| `resistance_garrison_penetration_chance` | 百分比；1.9 起 | 驻军被渗透的概率 |
| `resistance_growth` | 百分比；1.9 起 | 抵抗增长速度 |
| `resistance_target` | 百分比；1.9 起 | 抵抗增长的目标值 |
| `starting_compliance` | 百分比；1.9 起 | 基础顺从度数值 |
| `state_bunker_max_level_terrain_limit` | 绝对值；wiki 无版本标注 | 该州碉堡可建上限（地形限制） |
| `state_coastal_bunker_max_level_terrain_limit` | 绝对值；wiki 无版本标注 | 该州海岸碉堡可建上限 |
| `state_production_speed_<building>_factor` | 百分比；1.9.1 起 | 该州指定建筑的建造速度；全建筑用 `state_production_speed_buildings_factor`（1.9 加入） |
| `state_repair_speed_<building>_factor` | 百分比；1.9.1 起 | 该州指定建筑的修复速度 |
| `state_resource_<resource>` | 绝对值 | 该州指定资源的数量 |
| `state_resources_factor` | 百分比；1.9 起 | 州内资源总量 |
| `state_resource_cost_<resource>` | 绝对值；1.9 起 | 该州指定资源的成本 |
| `temporary_state_resource_<resource>` | 绝对值 | 在基础值之后追加的指定资源量 |
| `enemy_operative_detection_chance_over_occupied_tag` | 绝对值；1.9 起 | 占领该州的 tag 发现敌方特工的概率偏移 |
| `enemy_operative_detection_chance_factor_over_occupied_tag` | 百分比；1.9 起 | 占领该州的 tag 发现敌方特工的概率 |

坑（能放 / 不能放）：

- 能放：本节全部键；另外 Land combat 节里标注 "Can also apply in state scope" / "Works in state scope" 的 `max_dig_in`、`max_dig_in_factor`、`planning_speed`；Naval invasions 节的 `naval_invasion_penalty`、`amphibious_invasion_defence`；`compliance_gain`、`compliance_growth` 同时也可进国家 scope。
- 能继续下到 province：本节里"很大一部分"（wiki 未逐条列出），已明确写出的是 `local_org_regain`。
- 不能放：本节没有国家/将领专属键。反过来说，`unit leader` 专属键（`max_commander_army_size`、`terrain_penalty_reduction`、`trait_*_xp_gain_factor` 等）不进 state scope；空军、海军、科研这类国家层键（`air_*`、`navy_*`、`scientist_*`）在本节也没有任何一条。
- `equipment_capture_for_controller`（绝对值）与 `equipment_capture_factor_for_controller`（百分比）是一对，按需选一个。
- `max_fuel_building` 类型列写的是 Percentual，但语义是"给控制者的燃油容量（千单位）"，示例 `1500`；照百分比理解会写错数量级。
- `local_factory_energy_consumption` 的文件注释与实际解析不一致（注释说整数，实际吃小数）。
- `state_production_speed_<building>_factor` 只作用于单一建筑类型，要一次覆盖全部建筑必须换成 `state_production_speed_buildings_factor`。
- `disable_strategic_redeployment*` 是布尔，只认 1；写 0 或不写才有"不禁用"的效果。

---



作用域说明（wiki 原文）：陆地与海战两节里的大部分键在这里同样生效；本节列出的是 unit leader 专属键。

| 修正键 | 取值语义 | 作用 |
|---|---|---|
| `cannot_use_abilities` | 布尔（只接受 1）；1.5 起 | 禁止使用技能（abilities） |
| `dont_lose_dig_in_on_attack` | 布尔（只接受 1）；1.5 起 | 进攻时不丢失堑壕加成 |
| `exiled_divisions_attack_factor` | 百分比；1.6 起 | 该将领麾下流亡师的攻击 |
| `exiled_divisions_defense_factor` | 百分比；1.6 起 | 该将领麾下流亡师的防御 |
| `own_exiled_divisions_attack_factor` | 百分比；1.6 起 | 麾下同国流亡师的攻击 |
| `own_exiled_divisions_defense_factor` | 百分比；1.6 起 | 麾下同国流亡师的防御 |
| `experience_gain_factor` | 百分比；1.5 起 | 将领获得的经验 |
| `fortification_collateral_chance` | 百分比；1.5 起 | 战斗破坏敌方要塞的概率 |
| `fortification_damage` | 百分比；1.5 起 | 敌方要塞在战斗中受到的损坏 |
| `max_commander_army_size` | 绝对值；1.5 起 | 集团军司令无惩罚可带的师数 |
| `max_army_group_size` | 绝对值；1.5 起 | 元帅无惩罚可带的集团军群数 |
| `paradrop_organization_factor` | 百分比；1.5 起 | 伞降后伞兵剩余的组织度 |
| `paratrooper_aa_defense` | 百分比；1.5 起 | 对伞兵的防空强度 |
| `paratrooper_weight_factor` | 百分比；1.13 起；**也可用于国家 scope** | 伞兵占用的运输空间 |
| `promote_cost_factor` | 百分比；1.5 起 | 晋升该将领的花费 |
| `reassignment_duration_factor` | 百分比；1.5 起 | 调任惩罚持续时间 |
| `river_crossing_factor` | 百分比；1.5 起 | 渡河惩罚效果 |
| `sickness_chance` | 百分比；1.5 起 | 将领生病的概率 |
| `skill_bonus_factor` | 百分比；1.5 起 | 将领从技能等级获得的加成 |
| `trait_<trait>_xp_gain_factor` | 百分比；1.11 起 | 指定特质的经验获取（如 `trait_infantry_leader_xp_gain_factor`） |
| `terrain_trait_xp_gain_factor` | 百分比；1.5 起 | 所有地形特质（`basic_terrain_trait` 或 `assignable_terrain_trait` 类型）的经验获取 |
| `wounded_chance_factor` | 百分比；1.5 起 | 将领负伤的概率 |
| `shore_bombardment_bonus` | 百分比；1.5 起；**陆军与海军将领都可用** | 岸轰对师施加的惩罚 |

坑（能放 / 不能放）：

- 能放：本节 23 个键；加上 Land combat 与 Naval combat 两节里适用于 leader 的绝大多数键（含 `terrain_penalty_reduction`、`naval_invasion_prep_speed`、`invasion_preparation`）。
- 不能放：国家层的地产/科研/州级键（`local_*`、`state_*`、`scientist_*`、`compliance_*`）以及只在国家 scope 才认的 `offence` / `defence`。
- `shore_bombardment_bonus` 是本节唯一同时给陆军与海军将领用的键；想改"岸轰惩罚"不要去找 `naval_*`。
- `paratrooper_weight_factor` 是 1.13 起的双 scope 键（leader + country），其余本节键都只在 leader scope。
- `trait_<trait>_xp_gain_factor` 与 `terrain_trait_xp_gain_factor` 会叠加，前者按特质，后者按"地形特质"整类。
- `experience_gain_factor` 是"将领自己的经验"，与 `experience_gain_army_unit`（师的陆军经验）不是一回事。

---



作用域说明：本节只有 4 个键，全部只用于 scientist（科学家）scope，1.15 起。

| 修正键 | 取值语义 | 作用 |
|---|---|---|
| `female_random_scientist_chance` | 百分比；1.15 起 | 生成女性科学家的概率 |
| `scientist_breakthrough_bonus_factor` | 百分比；1.15 起（示例可为负 `-0.25`） | 科学家在特殊项目（special projects）上的突破加成 |
| `scientist_research_bonus_factor` | 百分比；1.15 起 | 科学家在特殊项目上的研究加成 |
| `scientist_xp_gain_factor` | 百分比；1.15 起 | 科学家获得的经验 |

坑（能放 / 不能放）：

- 能放：仅这 4 条，挂在科学家特质/科学家修正上。
- 不能放：陆地、海军、空军、州级、国家级的任何键都不在本节；把 `research_speed_factor` 之类国家科研键写进科学家不属本节内容，wiki 未列。
- `scientist_breakthrough_bonus_factor` 可以写负值（示例 -0.25），即减益。
- 本节无 `SVersion` 模板，但每条 Notes 列都标 1.15，属特殊项目（BBA/1.15）之后才有的 scope。

---



作用域说明（wiki 原文）：本节**只限为天气定义的 static modifiers** 使用。

| 修正键 | 取值语义 | 作用 |
|---|---|---|
| `air_accidents` | 绝对值 | 空中事故发生的基础概率 |
| `air_detection` | 绝对值 | 空中探测的基础概率 |
| `naval_strike` | 绝对值 | 对海打击的基础效率 |
| `navy_casualty_on_sink` | 百分比；1.6 起 | 该区域内舰船被击沉时的伤亡 |
| `navy_casualty_on_hit` | 百分比；1.6 起 | 该区域内舰船被击伤时的伤亡 |

坑（能放 / 不能放）：

- 能放：只有这 5 条，且只出现在 weather 的 static modifiers 里（`common/static_modifiers.txt` 相关定义）。
- 不能放：国家、州、将领、科研、targeted 的全部键；把 `air_detection`（本节，绝对值）与 `air_*detect_factor`（Air combat 节，百分比）混用在战略区里不会生效。
- 前三条是绝对值基础概率/效率，后两条是百分比。

---




| scope | 可放 | 明确不能放 / 注意 |
|---|---|---|
| 国家（country） | General/Land/Naval invasions/Carriers/Naval/Air 各节默认 scope；`compliance_gain`、`compliance_growth`、`paratrooper_weight_factor` | `offence`、`defence`、`terrain_penalty_reduction` 在此无效 |
| unit leader | 本节 23 键 + Land/Naval combat 的大部分 | 州级 `local_*`/`state_*`、科研 `scientist_*` 不放 |
| navy leader | Naval combat 大部分 + `shore_bombardment_bonus` | — |
| ace | Air combat 大部分 | — |
| state | 本节 50 键 + `max_dig_in(_factor)`、`planning_speed`、`naval_invasion_penalty`、`amphibious_invasion_defence` | 将领/科研/空军国家层键不放 |
| province | state 键中的"很大一部分"，已明确 `local_org_regain` | wiki 未逐条列举 |
| strategic region | 仅 5 条天气静态修正 | 其余全部不放（含 state 键） |
| scientist | 仅 4 条 | 其余全部不放 |
| 装备模块 | Naval combat 键 | — |
| targeted 块 | 本节 10 键，必须写在 `targeted_modifier = { }` 内 | 写进 `modifier = { }` 静默失效 |

---

## 第 9 章 国策树

### 国策树（National focuses）

URL：https://hoi4.paradoxwikis.com/index.php?title=National_focus_modding&action=raw （`{{Version|1.13}}`）

### 文件位置

| 内容 | 路径 |
|---|---|
| 国策树、国策、shared_focus、joint_focus、style（标题栏） | `common/national_focus/*.txt` |
| 连续国策面板（palette）与连续国策 | `common/continuous_focus/*.txt` |
| 国策内嵌窗口定义 | `common/focus_inlay_windows/*.txt` |
| AI 策略计划 | `common/ai_strategy_plans/*.txt` |
| 图标 sprite（常规 + shine） | `interface/*.gfx`（原版 `interface/goals.gfx`、`interface/goals_shine.gfx`） |
| 图标图片 | `gfx/interface/goals/`（约定，不是硬性要求） |
| 本地化 | `localisation/english/*_l_english.yml`（UTF-8-BOM） |

文件名无意义，一个文件可放多个 focus_tree。sprite 定义不要复制原版文件，新建自己的 `.gfx`。

### 最小可用模板（一个树 + 一个国策）

```
focus_tree = {
    id = TAG_focus_tree
    country = {
        base = 0                  # MTTH 块；开局前评估一次，之后不刷新
        modifier = {
            add = 10
            original_tag = TAG
        }
    }

    continuous_focus_position = { x = 450 y = 800 }   # 可选，连续国策面板左上角像素坐标
    initial_show_position = { focus = TAG_focus_name } # 可选

    focus = {
        id = TAG_focus_name
        x = 5
        y = 0
        icon = GFX_focus_icon_name
        cost = 8
        search_filters = { FOCUS_FILTER_POLITICAL }   # 可选但推荐

        completion_reward = {
            add_political_power = 100
        }
    }
}
```

带前置、互斥、可用性、AI 权重的完整单条：

```
focus = {
    id = TAG_focus_name_2
    x = -1
    y = 1
    relative_position_id = TAG_focus_name     # 相对定位，总位置 x=4 y=1
    icon = GFX_other_focus_icon_name
    prerequisite = { focus = TAG_focus_name }
    mutually_exclusive = { focus = TAG_focus_name_3 }

    cost = 8
    search_filters = { FOCUS_FILTER_POLITICAL }
    will_lead_to_war_with = QAT

    available = {
        country_exists = QAT
        NOT = { has_subject = QAT }
    }

    ai_will_do = {
        base = 5
        modifier = {
            factor = 0
            has_war = yes
        }
    }

    completion_reward = {
        declare_war_on = {
            target = QAT
            type = annex_everything
        }
    }
}
```

### 字段表：focus_tree

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `id` | 标识符 | 树 ID，必填；重复报错。用于 `has_focus_tree`、`load_focus_tree`，也是本地化键 |
| `country` | MTTH 块（`base`/`add`/`factor`/`modifier`） | 给国家打分，决定该国用哪棵树；开局前评估，之后基本不刷新（debug 下重存文件会刷新；动态建国时重新走一次） |
| `default` | `yes` | 标记默认树；全游戏只能有一个默认树。缺省视为非默认 |
| `reset_on_civilwar` | `yes`/`no` | 原文：与效果无关（写不写一样）。内战中国策树的实际行为见下 |
| `shared_focus` | `shared_focus` 的 id | 把该 shared focus 及其通过 prerequisite 连接的全部 shared focus 加进树；指向不存在的 focus 会在载入主菜单时崩溃 |
| `continuous_focus_position` | `{ x = int y = int }` | 连续国策面板左上角像素位置；默认 x=50 y=1000；两值都 0 或缺省则回默认 |
| `initial_show_position` | `{ focus = id }` 或 `{ x = int y = int }`，可带 `offset = { x/y/trigger }` | 打开树时相机初始位置；坐标同国策坐标（x 单位 96px、y 单位 130px），offset 在载入时求值 |
| `focus` | 块，可多个 | 国策本身；`focus` 写在 `focus_tree` 外或嵌套在另一个 `focus` 内会在 error log 报 unexpected token |
| `shortcut` | 块 | 左下角导航按钮：`name`（本地化键）、`target`（focus id）、`scroll_wheel_factor`（0–1，越大越放大）、`trigger`（可选，控制按钮是否显示，不覆盖目标 focus 的 allow） |
| `inlay_window` | `{ id = ... position = { x y } }` | 把 `common/focus_inlay_windows/` 里定义的窗口挂到树上 |

内嵌窗口定义（`common/focus_inlay_windows/*.txt`）：`window_name`（scripted GUI 组件名）、`internal`（bool，默认 no，true 时只有本国可见）、`visible`（trigger，不可见时不求值）、`scripted_buttons = { <name> = { available = {} click_effect = {} } }`、`scripted_images = { <icon> = { <GFX名> = { trigger } 或 = yes } }`（按顺序取第一个为真的，`= yes` 常作默认分支）。

### 字段表：focus

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `id` | 标识符（建议 `TAG_focusname`） | 必填；跨树重名会导致 prerequisite 连线错乱、`complete_national_focus`/`has_completed_focus` 失效 |
| `x` / `y` | 整数 | 网格坐标；单位为 x=96px、y=130px（`focus_spacing` 定义于 `interface/nationalfocusview.gui`）。正 x 向右，正 y 向下 |
| `relative_position_id` | 另一 focus 的 id | 相对该 focus 定位，叠加 x/y（并递归其 relative）。同树内才有效；自引用或互相引用造成递归会崩溃 |
| `offset` | `{ x = int y = int trigger = { ... } }` | 条件满足时在树载入时挪位；可用 `mark_focus_tree_layout_dirty` 中途刷新 |
| `icon` | `GFX_名字` 或 `icon = { GFX_a = { trigger } GFX_b = yes }` | 图标 sprite；块形式配合 `dynamic = yes` 做动态图标 |
| `dynamic` | `yes` | 允许标题用 scripted localisation、图标按条件动态；未设置时只在开局选一次 |
| `cost` | 数字（可小数） | 完成所需点数；1 点 = `NFocus` 的 `FOCUS_POINT_DAYS` 天，默认每天 1 点（即 cost 1 ≈ 一周）；小数向下取整到天 |
| `prerequisite` | `{ focus = id ... }` | 单个 prerequisite 内多条是 OR；多个 prerequisite 块之间是 AND |
| `mutually_exclusive` | `{ focus = id ... }` | 已选过该 focus 则本 focus 不可选；双向都写才画互斥箭头；可跨树、可配 shared focus |
| `available` | trigger（AND） | 可点时必须满足；默认 scope 是执行国 |
| `bypass` | trigger（AND） | 满足即“绕过”：标记完成但不执行 `completion_reward`，改执行 `bypass_effect` |
| `bypass_effect` | effect | 绕过时执行 |
| `bypass_if_unavailable` | `yes` | `available` 不满足时自动绕过，免去抄条件 |
| `enable_automatic_bypass` | `no` | 禁止自动绕过 |
| `allow_branch` | trigger | 该 focus 是否可见；**只在树首次载入时检查**，可用 `mark_focus_tree_layout_dirty` 刷新。带 allow_branch 的 focus 只看自己的条件，父分支被禁也会显示 |
| `available_if_capitulated` | `yes` | 投降状态下也能做；默认 false |
| `cancel_if_invalid` | `no` | `available` 变假时是否取消；默认 true |
| `continue_if_invalid` | `yes` | `available` 变假时是否继续；默认 false |
| `cancel` | trigger | 额外的取消条件，常配 `cancel_if_invalid = no` |
| `historical_ai` | trigger | 历史国策模式下 AI 是否允许选它（不保证选）；优先级高于 AI 策略计划的顺序 |
| `completion_reward` | effect | 完成奖励，按顺序执行，scope 为执行国 |
| `complete_tooltip` | effect | 也是 effect 块，只用于改写 tooltip（等价 hidden_effect + effect_tooltip） |
| `select_effect` | effect | 点击开始国策时执行，无 tooltip；会让该 focus 无法手动取消 |
| `search_filters` | `{ FOCUS_FILTER_X ... }` | 树内搜索筛选标签 |
| `text_icon` | style 名 | 标题栏样式，见下 |
| `will_lead_to_war_with` | TAG | 向该国（及其盟友/宗主/阵营成员）显示“正在制造战争借口”警报，并让 AI 备战 |
| `cancelable` | `no` | 无法手动取消；但只要写了 `select_effect`，本字段就不起作用 |
| `ai_will_do` | MTTH 块 | AI 权重，见结构限制 |

### 图标与 sprite 命名规则

- `icon = GFX_focus_icon` 实际绑定两张 sprite：
  - `GFX_focus_icon`：不可用 / 进行中 / 已完成状态下使用；
  - `GFX_focus_icon_shine`：**可用状态**以及政治/外交界面里当前正在做的国策使用。
- shine 的 sprite 名必须是常规名后加 `_shine`。文件名带 `shine` 既不必要也不充分——引擎只看 sprite 名。原文点明：shine 不动的最常见原因就是违反这条命名。
- 任一 sprite 缺失或写错，会用 `Goal_unknown` 缺图；`texturefile` 指向不存在的文件（含扩展名错、目录错）时图标全透明。
- shine sprite 需要一个 `effectFile = gfx/FX/buttonstate.lua` 加两组 `animation`（`animationrotation = -90.0` / `90.0`，`animationtexturefile = gfx/interface/goals/shine_overlay.dds`，`animationblendmode = "add"`，`animationtype = "scrolling"`，`animationtime = 0.75`，`animationlooping = no`，`animationmaskfile` 与图标同图）。套模板时三处都要改：`name`、`texturefile`、每个 animation 里的 `animationmaskfile`。
- 路径分隔符必须用 `/`；反斜杠会被当转义符导致读不到目录。
- 搜索筛选图标：sprite 名为 `GFX_` + 筛选名，例如 `FOCUS_FILTER_MY_MOD` → `GFX_FOCUS_FILTER_MY_MOD`；本地化键就是筛选名本身。
- 筛选排序：`search_filter_prios = { FOCUS_FILTER_MY_MOD = 1200 }`，写在 `focus_tree` 之外，全局生效（原版放在 `common/national_focus/generic.txt`）。
- 标题栏样式：根级 `style = { name = ... unavailable = GFX_... completed = ... available = ... current = ... }`，一个 `default = yes`；focus 里 `text_icon = <style name>` 引用。

### 本地化键规则

| 对象 | 键 |
|---|---|
| 国策名 | focus 的 `id` |
| 国策描述 | `id` + `_desc` |
| 树名（`has_focus_tree` / `load_focus_tree` 的 tooltip） | 树 `id` |
| 搜索筛选 | `FOCUS_FILTER_*` |
| 快捷导航按钮 | `shortcut` 的 `name` |

```
l_english:
 TAG_focus_name: "Example focus"
 TAG_focus_name_desc: "Example focus description"
```

动态标题：`dynamic = yes` 后标题可用 scripted localisation，例如 `TAG_political_focus: "[THIS.GetRulingIdeology] political focus"`。

### 结构限制与判定逻辑

- **坐标网格**：x 单位 96px、y 单位 130px；正下方相邻 = y+1，正右相邻 = x+2。位置相对树左上角。
- **一个树的 focus 数量上限**：`（wiki 未明确）`。原文只给出坐标与连线约束，没有写数量硬上限。
- **prerequisite 逻辑**：单块内多条 = OR，多块 = AND。表达不了 `A ∨ (B ∧ C)` 这类组合，也表达不了否定——需要时改用 `available` 里的 `has_completed_focus` 加 `custom_trigger_tooltip`。
- **前置应画在下方 focus 的上方**，否则路径生成会用错 90° 转角 sprite。
- **重复 focus id** 会破坏路径生成与前置连线（连没有重复的树也会受影响）。
- **allow_branch 只检查一次**（树载入时），刷新用 `mark_focus_tree_layout_dirty`；写在 focus 奖励里时该 effect 对 `has_completed_focus` 不生效——需要隐藏事件延迟执行，或先用 `load_focus_tree`（`keep_completed = yes`）把 focus 标记为完成。
- **完成时机**：`completion_reward` 执行时 focus 还没标记为完成，块内 `has_completed_focus` 返回 false。规避：用国家 flag；用零延迟隐藏事件；或用 `load_focus_tree` 强制标记。
- **内战行为**：原国继续用原树，正在做的 focus 不暂停不取消；叛军按各树 `country` 评分重新分配；若分到同一棵树，则继承全部已完成 focus 和当前进度，否则进度丢失。
- **`ai_will_do` 权重写法**：默认 1；`base` 改初值，`add` 加，`factor` 乘；`modifier` 是 trigger 块，内部同样支持这三个键，按书写顺序依次生效，支持变量。AI 挑选算法：对每个候选 focus 取 `0 ~ ai_will_do` 的随机小数，刚完成前置的候选再乘 `NAI:FOCUS_TREE_CONTINUE_FACTOR`，被 AI 策略计划 `focus_factors` 命中的再乘该系数，取最大者。全部 ≤0 则不选。
- 低权重比直觉更不容易被选中：原文给了三种情形公式（一个高值 + 若干同值小值；两组等值；一般式积分），并明确“AI 策略计划已经指定了 focus 顺序时不走这套评估”。
- `cost` 的小数会向下取整到天；和平/战争每天进度由 `NFocus` 的 `FOCUS_PROGRESS_PEACE` / `FOCUS_PROGRESS_WAR` 决定，可用 `reduce_focus_completion_cost` 单独降某条 focus 的成本。
- **shared_focus**：定义在 `focus_tree` 之外，语法与普通 focus 完全一致；树里写 `shared_focus = id` 会连带引入其 prerequisite 链（要求 allow_branch 为真）。指向不存在 focus → 载入主菜单崩溃；树里没有任何非 shared focus 也会崩。
- **joint_focus**（1.13，shared focus 的子集）：多国共享完成。额外字段 `joint_trigger`（对每个国家求值，决定哪些国家算 joint）、`completion_reward_joint_originator`（只给直接完成国）、`completion_reward_joint_member`（给其他 joint 国）。`completion_reward` 对所有 joint 国执行。往 generic 树里加 joint focus 会刷满 “missing scope” 报错。
- **连续国策**：`common/continuous_focus/*.txt`，`continuous_focus_palette = { id country default position focus ... }`。连续 focus 用 `available` 控制**可见**、`enable` 控制**可点**（与普通国策相反），`daily_cost`（政治点/天，默认见原文示例 0.4/1）、`modifier`、`idea`（选中加 hidden idea、取消移除）、`select_effect`/`cancel_effect`（可随时免费切换，两者应互为逆操作）、`supports_ai_strategy`（不写 AI 永不选）、`available_if_capitulated`。需要完成 `NCountry:MIN_FOCUSES_FOR_CONTINUOUS` 个普通国策后才解锁。
- **AI 策略计划**：`common/ai_strategy_plans/*.txt`；块名 = 计划 ID；`name`/`desc` 只给 `aiview` 用，不需本地化；`allowed` 只在开局检查；`enable` 每日检查，一旦为真即固定采用；`abort` 每日检查，为真则放弃；`ai_national_focuses = { ... }` 是严格的取用顺序（此时忽略 ai_will_do）；`focus_factors = { TAG_focus = 3 }` 乘权重（0 = 除非列入顺序否则永不选）；`weight` 是 MTTH 块，先乘权重再套用各 factor。

### 常见错误

- shine sprite 名没加 `_shine` → 可用状态仍是静态图。
- `texturefile` 目录/扩展名写错或用了 `\` → 图标透明或全缺。
- focus id 没加国家 tag 前缀 → 跨树重名，前置连线指向空白、转角 sprite 错乱。
- `relative_position_id` 指向另一棵树或不存在的 focus → 位置异常甚至崩溃；自引用/互引用递归 → 崩溃。
- `shared_focus = 不存在的id` 或树内只有 shared focus → 载入主菜单崩溃。
- 在 `completion_reward` 里立刻用 `has_completed_focus` 判断本 focus → 恒为 false。
- 忘记 `mark_focus_tree_layout_dirty` 却指望 `allow_branch`/`offset` 中途变化。
- `select_effect` 与 `cancelable = yes` 混用，以为能手动取消。

---

## 第 10 章 事件

### 事件（Events）

URL：https://hoi4.paradoxwikis.com/index.php?title=Event_modding&action=raw （`{{version|1.12}}`）

### 文件位置

| 内容 | 路径 |
|---|---|
| 事件本体（含 `add_namespace`） | `events/*.txt` |
| 事件图片 sprite | `interface/*.gfx`（原版 `eventpictures.gfx`） |
| 事件图片文件 | `gfx/event_pictures/*.dds`（约定） |
| 本地化 | `localisation/english/*_l_english.yml`，UTF-8-BOM，文件名必须 `_l_english.yml` 结尾（小写 L） |
| 触发入口 | `common/on_actions/*.txt`、`history/countries/*.txt`、任意 effect 块 |

事件类型：`country_event`、`news_event`、`state_event`、`unit_leader_event`、`operative_leader_event`。除外观、默认 scope、news 可关弹窗之外几乎没有差别。

### 最小可用模板

```
add_namespace = my_event

country_event = {
    id = my_event.1
    title = my_event.1.t
    desc = my_event.1.desc

    is_triggered_only = yes

    option = {
        name = my_event.1.a
        add_political_power = 100
    }
}
```

加图片与多标题的事件：

```
news_event = {
    id = my_news_event.1
    title = {
        text = my_news_event.1.t.a
        trigger = { tag = POL }
    }
    title = {
        text = my_event.1.t
    }
    desc = {
        text = my_news_event.1.desc.a
        trigger = { tag = POL }
    }
    desc = {
        text = my_event.1.desc
    }

    picture = GFX_my_news_event_picture

    is_triggered_only = yes
    major = yes

    option = {
        name = my_news_event.1.a
        trigger = { tag = POL }
    }
    option = {
        name = my_news_event.1.b
        trigger = { NOT = { tag = POL } }
    }
}
```

隐藏事件（做延迟/借 FROM）：

```
country_event = {
    id = my_hidden_event.1
    hidden = yes
    is_triggered_only = yes
    immediate = {
        random_country = {
            limit = { is_neighbor_of = BHR }
            annex_country = { target = BHR transfer_troops = yes }
        }
    }
}
```

### 字段表：事件主体

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `id` | `<namespace>.<整数>` | 事件 ID；namespace 必须先 `add_namespace`，且整数部分必须是整数 |
| `title` | 本地化键 或 `{ text = 键 trigger = {} }` | 标题；非 hidden 事件至少要有 title 或 desc |
| `desc` | 同上 | 描述 |
| `picture` | sprite 名 `GFX_...` 或 `"[ScriptedLocalisation]"` | 图片；`[ ]` 形式走 scripted localisation 的 `localization_key` |
| `trigger` | trigger（AND） | 自动触发条件；为假时只能用控制台或 effect 触发 |
| `mean_time_to_happen` | `{ days/months/years, modifier = { add/factor ... } }` | MTTH 块；月=30 天，年=365 天；modifier 按顺序求值，支持变量 |
| `is_triggered_only` | `yes` | 关闭自动触发；不阻止 effect / on_action random_events / border war 等其他触发方式 |
| `fire_only_once` | `yes` | 全局只触发一次（任一国家收到后其他国家也收不到） |
| `major` | `yes` | 任一国家收到则所有国家收到；news_event 必写 |
| `show_major` | trigger | major 事件只对满足条件的国家显示 |
| `fire_for_sender` | `no` | major 时连发起国也不显示 |
| `hidden` | `yes` | 隐藏事件，无需 title/desc；触发的第一个 option 自动选 |
| `minor_flavor` | `yes` | 标记为小事件，玩家可在决议菜单关弹窗 |
| `timeout_days` | 整数 | 多少天后自动选第一个 option；默认取 `NGame:EVENT_TIMEOUT_DEFAULT` |
| `immediate` | effect | 触发瞬间执行（在选 option 之前、其他事件评估之前）；tooltip 会显示，需要时套 `hidden_effect` |
| `after` | effect | 玩家选完 option 后执行（1.16.9 起） |
| `option` | 块，可多个 | 选项，本身是 effect 块 |

### 字段表：option

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `name` | 本地化键 | 选项文字；无法按条件切换，只能写多个 option 各自加 trigger |
| `trigger` | trigger | 该选项是否显示；触发时不满足则本次不出现 |
| `ai_chance` | MTTH 块（`base`/`factor`/`add`/`modifier`） | AI 选它的权重；按比例，不必凑 100；默认 1；全为 0 时选第一个；d100 掷骰，非零概率最低 1%；结果按种子+时间+国家固定 |
| `original_recipient_only` | `yes` | major 事件中只对发起国显示该选项 |

### 字段表：触发事件的 effect

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `id` | 事件 ID | 必填 |
| `hours` / `days` / `months` | 整数 | 延迟下限，可叠加（月=30 天） |
| `random_hours` / `random_days` | 整数 | 在上限内均匀随机追加；`random = N` 等价 `random_hours = N` |
| `tooltip` | 本地化键 | 覆盖触发提示里显示的事件名 |
| `trigger_for` | TAG / `controller` / `owner` / `occupied` / ROOT / FROM | 仅 state_event；指定事件归属国，必填（state scope 触发时） |
| `originator` | TAG | 仅 operative leader 事件；FROM 方，默认特工所属国 |
| `recipient` | TAG | 仅 operative leader 事件；接收国 |
| `set_root` / `set_from` / `set_from_from` | TAG | 仅 operative leader 事件；只改动态本地化里的 scope，不改代码 scope |

简写：`country_event = my_event.1`、`news_event = my_event.1`（两者底层相同，可互换）。state/operative leader 事件必须用展开式。

### 命名空间与内部 ID

- `add_namespace = my_event` 必须写在任何事件之外；`my_event.subtopic` 也是合法 namespace（对 `id = my_event.subtopic.1`）。
- 内部 ID = namespace 序号 × 100000 + 数字部分。namespace 序号从 10 开始，按文件加载顺序（文件名的 ASCII 字节序）每次 +1。
- 数字部分不是整数时按 0 处理 → 所有非整数 ID 互相冲突。
- 数字部分 ≥100000 会侵占下一个 namespace 的号段 → 两个事件被当成同一个。
- FROM 语义：用 effect 触发时，调用块的 ROOT 变成事件内的 FROM，原 FROM 变成 FROM.FROM，依此类推（from on_action 的 random_events 触发时不重置，沿用 on_action 的 scope）。

### 图标 / 图片命名规则

```
spriteType = {
    name = "GFX_my_sprite"
    texturefile = "gfx/event_pictures/my_event_picture.dds"
}
```

事件里写 `picture = GFX_my_sprite`。动态图片用 scripted localisation 的 `defined_text`，各分支 `localization_key = GFX_xxx`，最后一个不带 trigger 的做默认。

### 本地化键规则

```
l_english:
 my_event.123.t: "My event title"
 my_event_description: "My event description"
 my_event.1.a: "Option A"
```

惯例：标题 `namespace.数字.t`、描述 `namespace.数字.desc`、选项 `namespace.数字.a/b/c`。键名只是惯例，真正绑定靠 `title`/`desc`/`option` 里写的字符串。

### 结构限制与触发节奏

- 自动事件每 `NCountry:EVENT_PROCESS_OFFSET`（默认 20）天检查一次 `trigger`；一旦为真，改为每天评估 `mean_time_to_happen`。
- MTTH 返回 M 天时，当天触发概率 `1-2^(-1/M)`（中位时间）。trigger 在每日检查中变假则退回 20 天周期。
- 延迟触发的 effect：事件有 `delayed_event` 计时器；目标国不存在时计时器不推进，事件挂在该国 backlog，等国家出现后才开始倒数。
- `is_triggered_only = yes` 与 `trigger = { ... }` 可以共存：延迟触发的 effect、on_action 的 `random_events` 都会在“预计触发时刻”检查 trigger。

### 常见错误

未记录到日志的：

1. 想自动触发却写了 `is_triggered_only = yes` → 事件永不自动出现。
2. 自动触发事件没在 `trigger` 里检查接收国（只写 `ITA = { has_political_power > 123 }`）→ 第一个被检查的国家（默认 GER）先满足，效果落到错误国家。修法：加 `tag = ITA` 或改写成 `tag = ITA` + 直接条件。
3. 能用 effect 触发的条件却做成自动事件（如 `has_completed_focus`）→ 最坏要等 20 天，且反复做 trigger 检查，性能差。改在 focus 奖励里 `country_event = { id = ... hours = 6 random_hours = 3 }`。
4. 用很窄的 `date > / date <` 窗口卡具体日期 → 20 天检查周期跳过窗口，事件永不触发；只用 `date > X` 也不能保证准点。修法：`on_startup` 里按天数延迟触发 + `is_triggered_only = yes`（注意游戏没有闰日）。
5. `news_event` 漏 `major = yes` → 只有一个国家看到；`major = yes` 又加 `fire_only_once = yes` → 同样只有一个国家看到（后者优先，抵消 major）。

会进日志的：

- `Event is triggered only, but does not have a 1 base-factor.`：`is_triggered_only = yes` 同时写了 `mean_time_to_happen`。
- `Event is set to trigger every day.`：同时满足「可自动触发」「MTTH ≤ 1 天（缺省也算 1）」「可重复触发」。
- `Malformed token: event_id.123`：漏了 `add_namespace`。
- `Failed to create id 12300000 50. Already exists in game...`：内部 ID 冲突（重复 ID / 非整数 ID / 数字部分 ≥100000）。第二个数字 `50` 表示事件库（`54` 是国家领袖，`55` 是陆军将领）。

---

## 第 11 章 决议与任务

### 决议（Decisions）

URL：https://hoi4.paradoxwikis.com/index.php?title=Decision_modding&action=raw （`{{version|1.11}}`）

### 文件位置

| 内容 | 路径 |
|---|---|
| 决议本体 | `common/decisions/*.txt` |
| 决议类别 | `common/decisions/categories/*.txt` |
| 决议图标 / 类别图片 sprite | `interface/*.gfx`（原版 `decisions.gfx`） |
| 本地化 | `localisation/english/*_l_english.yml` |

文件名与 tag 无关，随便命名。决议必须放在某个类别块里才能被识别。

### 最小可用模板（类别 + 一个决议）

`common/decisions/categories/TAG_categories.txt`：

```
TAG_my_category = {
    allowed = { tag = TAG }
    priority = 10
    icon = TAG_category            # 实际 sprite：GFX_decision_category_TAG_category
    picture = GFX_decision_category_picture
    visible_when_empty = yes
}
```

`common/decisions/TAG_decisions.txt`：

```
TAG_my_category = {
    TAG_my_decision = {
        allowed = { tag = TAG }
        icon = TAG_my_decision     # 实际 sprite：GFX_decision_TAG_my_decision
        cost = 50
        days_re_enable = 30
        available = {
            has_political_power > 50
        }
        complete_effect = {
            add_stability = 0.05
        }
    }
}
```

带计时器 + 取消 + 修改器的决议（政治点成本、倒计时、取消回滚）：

```
TAG_my_timed_decision = {
    allowed = { original_tag = TAG }
    icon = TAG_timed
    cost = 100
    days_remove = 100
    fire_only_once = no
    modifier = {
        training_time_factor = -0.3
    }
    available = { has_war = yes }
    complete_effect = {
        add_war_support = 0.1
    }
    remove_effect = {
        add_war_support = -0.1
    }
    cancel_trigger = {
        has_war = no
    }
    cancel_effect = {
        add_stability = -0.05
    }
}
```

### 字段表：决议与类别通用

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `allowed` | trigger | **只在开局或载入存档时检查一次**；用于限定国家（`tag`/`original_tag`）与 DLC（`has_dlc`）。不满足则永不出现（除非重载决议） |
| `visible` | trigger | 每帧检查（前提 allowed 为真），决定是否显示在决议列表；targeted 决议里可同时看 ROOT 与 FROM，但优先用 `target_trigger` 省性能。**对任务（mission）无效** |
| `available` | trigger | 每帧检查（前提 visible 为真），决定能否点击；不满足则灰显 |
| `icon` | 名字 或 `{ key = GFX_... trigger = {} }` | 引擎自动加前缀：决议加 `GFX_decision_`，类别加 `GFX_decision_category_`；写全 `GFX_decision_xxx` 也认（会按同名 spriteType 精确匹配） |
| `priority` | 整数 或 MTTH 块 | 显示顺序，越大越靠上，默认 1；块形式支持 `base` + `modifier` |
| `highlight_states` | `{ highlight_state_targets = { state = N } }` 或 `{ highlight_states_trigger = {} }`、`highlight_provinces = { ... }`、`highlight_color_before_active`、`highlight_color_while_active`（0–3） | 悬停时在地图上描边；颜色缺省为白边。`highlight_provinces` 自 1.13.6 起 |

### 字段表：仅类别可用

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `picture` | sprite 名 | 描述左侧大图；**类别必须有本地化 desc 才会显示** |
| `visible_when_empty` | `yes` | 类别内没有可见决议时也显示类别 |
| `on_map_area` | `{ state / name / zoom / target_* / 各 trigger }` | 在决议列表顶部生成一个“跳转相机”按钮。`state` 是中心州；`zoom` 是离地像素（越小越近，默认相机范围 50–3000）；`name` 是本地化键；可用 `targets`、`target_array`、`target_trigger`、`target_root_trigger` 做动态区域 |
| `scripted_gui` | scripted GUI 名 | 在类别描述下方嵌入 GUI，该 GUI 的 context 必须是 `decision_category` |

### 字段表：仅决议可用

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `cost` | 整数 / 变量 | 政治点成本 |
| `custom_cost_trigger` + `custom_cost_text` | trigger + 本地化键 | 自定义成本显示（可用于指挥点等）。满足 trigger 用 `<key>`，否则 `<key>_blocked`，悬停用 `<key>_tooltip`。**这只是显示，实际扣除要自己在 `complete_effect` 里做**（建议 `hidden_effect`） |
| `ai_hint_pp_cost` | 常量整数 | 让 AI 以为要花这么多政治点而先攒钱（custom cost 无法被 AI 理解时用） |
| `complete_effect` | effect | 点击时立即执行（同时开始计时器） |
| `days_re_enable` | 整数 | 再次可用的冷却天数；默认次日即可再来 |
| `fire_only_once` | `yes` | 一次性决议（每国一次；targeted 时每目标一次） |
| `days_remove` | 整数 或 `-1` | 点击后到移除之间的天数；`-1` 表示永不因计时结束而移除 |
| `remove_effect` | effect | 计时结束时执行（注意不是点击时） |
| `remove_trigger` | trigger | 一满足就立刻移除并执行 `remove_effect` |
| `cancel_trigger` | trigger | 一满足就取消计时，**不**执行 `remove_effect` |
| `cancel_if_not_visible` | `yes`（默认 no） | 把 `visible` 的条件并入 `cancel_trigger` |
| `cancel_effect` | effect | 取消时执行，用来回滚 complete 的效果 |
| `modifier` | 修正块 | 计时期间生效的普通 modifier |
| `targeted_modifier` | `{ tag = XXX ... }` | 计时期间生效的针对性 modifier |
| `ai_will_do` | MTTH 块 | AI 权重；**默认 AI 永不会选**，必须写 |
| `war_with_on_complete` | TAG | 告知对方/AI：本决议的 `complete_effect` 会开战 |
| `war_with_on_remove` | TAG | 告知对方/AI：本决议的 `remove_effect` 会开战 |
| `fixed_random_seed` | `no` | 默认决议用固定随机种子（`random_list` 等每次结果相同）；设 `no` 才随机 |

### 任务（mission）

把决议变成任务只需 `days_mission_timeout`，其余差异：

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `days_mission_timeout` | 整数 | 任务持续天数（写它就变任务） |
| `timeout_effect` | effect | 计时结束/未被阻止时执行 |
| `available` | trigger | 满足就执行 `complete_effect`；**默认恒真，会立刻消失** |
| `selectable_mission` | `yes` | 改成需要玩家手动点按钮；否则 available 一满足就自动完成 |
| `activation` | trigger | 每日检查，决定任务是否出现（前提 `allowed` 为真）；`visible` 对任务无效 |
| `activate_mission` | effect `activate_mission = mission_name` | 绕过 `allowed` 和 `activation` 直接激活，性能更好 |
| `is_good` | `yes` | 改变灰显任务的提示语义（完成条件是好事还是坏事） |
| `war_with_on_timeout` | TAG | 告知对方/AI：`timeout_effect` 会开战 |

### 针对国家的决议（targeted）

只要决议里出现任一“目标检查”字段就会变成 targeted：`targets`、`target_array`、`target_trigger`（甚至只有 `target_root_trigger` 也算）。每个目标复制一份决议，图标右下角显示目标国旗。**FROM 是目标国，ROOT 是拿决议的国家**。

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `targets` | `{ TAG TAG }` | 目标国白名单 |
| `targets_dynamic` | `yes` | 连同该 original_tag 的所有动态国家（内战叛军等）一起检查 |
| `target_non_existing` | `yes` | 允许指向不存在的国家 |
| `target_array` | 数组名 | 用国家数组限定目标（如 `enemies`、`GER.core_states`） |
| `target_trigger` | trigger | 每日对 ROOT 与每个候选 FROM 求值 |
| `target_root_trigger` | trigger | 只对 ROOT 每日求值，先于 `target_trigger` 执行（省性能） |
| `war_with_target_on_complete` / `_on_remove` / `_on_timeout` | `yes` | targeted 版的战争预警，等价于把对应 `war_with_on_*` 设为 FROM |
| `activate_targeted_decision` | effect `{ target = TAG decision = id }` | 手动激活，替代自动出现 |

### 针对州的决议（state targeted）

`state_target` 取值：`yes`/`no`/`any`/`any_owned_state`/`any_controlled_state`/大洲键（`europe`、`africa`、`north_america`…）。用 `targets = { ... }` 或 `target_array` 显式指定目标时，`state_target` 只能写 `yes`/`any`，写其他值报错。此时 FROM 是州 scope；`targets = { 123 321 }` 或 `targets = { state = 123 }`。

`on_map_mode`：`map_only` / `decision_view_only` / `map_and_decisions_view`，决定 targeted 决议显示在地图上还是列表里。

### 图标与本地化命名规则

- 决议 sprite 名 = `GFX_decision_` + `icon` 值；类别 = `GFX_decision_category_` + `icon` 值。写 `icon = TAG_my_decision` 与 `icon = GFX_decision_TAG_my_decision` 都能用。
- 类别图片用独立的 sprite 名（示例写 `GFX_decision_category_picture`），不走前缀规则。
- 本地化键：类别 `id` 与 `id_desc`；决议 `id` 与 `id_desc`。自定义成本需要三件套 `<key>` / `<key>_blocked` / `<key>_tooltip`。

```
l_english:
 TAG_my_category: "My decision category"
 TAG_my_category_desc: "My decision category's description"
 TAG_my_decision: "My decision"
 TAG_my_decision_desc: "My decision's description"
```

### 结构限制

- 决议优先级只影响同类别内的排序；类别本身也吃 `priority`。
- `allowed` 只在开局/读档检查，改脚本后必须重载决议或重开存档。
- targeted 决议的 `fire_only_once` 是“每目标一次”，不是全局一次。
- 任务里 `visible` 完全不生效。
- `days_remove = -1` 只是不让计时器移除，仍可被 trigger 移除。

### 常见错误

- 把国家/DLC 限制写进 `visible` 或 `available` 而不是 `allowed` → 每帧求值，性能浪费，且读档行为不同。
- 任务写了 `visible` 却指望它控制出现。
- 任务的 `available` 留空或恒真 → 任务瞬间消失。
- 用 `custom_cost_text` 以为真会扣资源 → 必须自己在 `complete_effect` 里扣（常用 `hidden_effect`），同时给 `ai_hint_pp_cost`。
- targeted 决议里把 FROM 当成“发起的国家” → 实际 FROM 是目标。
- 用 `state_target = any_owned_state` 又同时写了 `targets = {}` → 报错。
- `days_remove` 与 `remove_effect` 混为一谈：以为点击瞬间就执行 remove 效果。
- 忘记 `ai_will_do` → AI 永不选该决议。

---

## 第 12 章 国家精神（Ideas）

### 国家精神（Ideas）

URL：https://hoi4.paradoxwikis.com/index.php?title=Idea_modding&action=raw （`{{Version|1.11}}`）

### 文件位置

| 内容 | 路径 |
|---|---|
| 国家精神 / 法案 / 设计商 / 隐藏精神 | `common/ideas/*.txt` |
| 精神类别（idea category / slot） | `common/idea_tags/*.txt` |
| 精神图标、类别图标、特质条 sprite | `interface/*.gfx`（原版 `ideas.gfx`、`countrypoliticsview.gfx`） |
| 类别行 UI 布局 | `interface/countrypoliticsview.gui` |
| 本地化 | `localisation/english/*_l_english.yml`（UTF-8-BOM） |

### 最小可用模板（一个国家精神）

```
ideas = {
    country = {                # 必须是 country 才会被当成国家精神
        TAG_my_spirit = {
            picture = TAG_my_spirit        # 实际 sprite：GFX_idea_TAG_my_spirit
            modifier = {
                political_power_cost = 0.1
                stability_factor = -0.2
            }
        }
    }
}
```

带针对修正、研究加成、装备加成、规则、取消与增删效果的完整精神：

```
ideas = {
    country = {
        TAG_my_spirit_2 = {
            picture = my_picture
            modifier = {
                training_time_factor = -0.1
            }
            targeted_modifier = {
                tag = QAT
                defense_bonus_against = 0.2
            }
            research_bonus = {
                infantry = 0.1
            }
            equipment_bonus = {
                infantry_equipment = {
                    instant = yes
                    defense = 0.2
                }
            }
            rule = {
                can_join_factions = no
            }
            allowed_civil_war = {
                has_government = democratic
            }
            cancel = {
                democratic > 0.6
            }
            on_add = {
                add_popularity = {
                    ideology = democratic
                    popularity = 0.2
                }
            }
            on_remove = {
                add_political_power = -50
            }
            do_effect = {
                NOT = { has_government = democratic }
            }
        }
    }
}
```

### 字段表：国家精神

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `picture` | 名字（引擎加 `GFX_idea_` 前缀） | 图标；缺 sprite 用默认 unknown 图 |
| `name` | 本地化键 | 改用别的名字键（同名 swap 时有用） |
| `modifier` | modifier 块 | 常规修正，持续生效；**不支持变量**（要变量用 dynamic modifiers） |
| `targeted_modifier` | `{ tag = XXX <modifier> }` | 针对某国的修正 |
| `research_bonus` | `{ <科技类别> = 0.1 }` | 科技类别研究加成；类别见 `common/technology_tags/` |
| `equipment_bonus` | `{ <装备原型> = { instant = yes <modifier> } }` | 装备加成；默认要研究新科技才生效，`instant = yes` 立即生效 |
| `rule` | `{ <game rule> = yes/no }` | 改变国家允许的行为（外交、和平会议等）；与原版默认相同时不显示 |
| `on_add` / `on_remove` | effect | 添加/移除时执行；**只有在游戏开始后添加才执行**（history 或 bookmark 的 effect 里添加不触发） |
| `cancel` | trigger | 满足即自动取消，并触发 `on_remove` |
| `allowed_civil_war` | trigger | 内战时对双方分别求值，只给为真的一方；**默认恒假，所以精神在内战爆发时会消失**，想让双方都保留写 `always = yes` |
| `do_effect` | trigger | 为假时不生效修正（含研究/装备加成），但精神不消失 |

### 字段表：可选中的精神（法案 / 设计商等）

这些参数在纯国家精神里没有意义，只对可点选的 idea 起作用。

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `allowed` | trigger | 只在开局/读档检查，限定国家与 DLC；`add_ideas` 可绕过 |
| `allowed_to_remove` | trigger | 持续检查，决定能否换成同类别的其他 idea |
| `visible` | trigger | 每帧检查（前提 allowed），决定是否显示 |
| `available` | trigger | 每帧检查（前提 visible），决定能否选 |
| `cost` | 整数 | 添加所需政治点；未设置默认 150（原版 `common/idea_tags` 里的值） |
| `removal_cost` | 整数 或 `-1` | 移除所需政治点；`-1` 表示不可手动移除；默认 0 |
| `level` | 整数 | 等级制价格：从 1 级换到 3 级要付 2 级 + 3 级的成本 |
| `traits` | `{ trait_id ... }` | 挂国家领袖特质（定义于 `common/country_leader/*.txt`），同时给静态修正与图标 |
| `ledger` | `army`/`air`/`navy`/`military`/`civilian`/`all`/`hidden` | 情报台账归属 |

类别内参数（写在 `common/ideas/*.txt` 的类别块里）：`designer = yes`、`law = yes`、`use_list_view = yes`。

### 字段表：idea category / slot（`common/idea_tags/*.txt`）

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `slot` | slot 名 | 政治界面里的一行；idea 通过 `slot` 归属到行 |
| `character_slot` | 角色槽名 | 角色用的槽，也能显示成普通 idea 槽 |
| `cost` | 整数 | 该类别默认添加成本（idea 未写 cost 时用） |
| `removal_cost` | 整数 | 默认移除成本 |
| `ledger` | 同上，另加 `invalid` | `invalid` 强制在更低一层（idea/角色）定义 |
| `hidden` | bool，默认 no | 不在界面显示 |
| `politics_tab` | bool，默认 yes | 是否在政治标签页显示 |

另有独立的 `slot_ledgers = { XXX_idea_slot = civilian ZZZ_idea_slot = invalid }`，优先级高于类别级 `ledger`。

### 图标命名规则

- 精神默认 sprite = `GFX_idea_` + idea 的 id。`picture` 值同样是加前缀（`picture = XYZ` → 找 `GFX_idea_XYZ`），所以写 `picture = GFX_XYZ` 会去找 `GFX_idea_GFX_XYZ`，通常找不到。
- 引擎**仍然会先找 `GFX_idea_<ideaname>`**，即使写了 `picture =`。要换图，sprite 名必须符合 `GFX_idea_...` 形态。
- 按 2D 图形文化切换：sprite 名后加 `_<graphical_culture_2d>`，例如 `GFX_idea_my_picture_middle_eastern_2d`。
- 类别行图标用单张 `GFX_idea_categories`，横向切片，`noOfFrames` 要等于类别数；类别顺序由 `common/idea_tags/*.txt` 中的定义顺序决定。新增类别必须同时改这个 sprite 的帧数。
- 空槽占位图 sprite 名 = `GFX_idea_slot_` + slot 名。
- 特质条：`GFX_idea_traits_strip`，`noOfFrames` 决定分段数；`sprite = 1` 取最左一段。改图必须同步改 `noOfFrames`。
- `texturefile` 写错时：精神在政治界面不可见但修正照常生效。

### 本地化键规则

| 对象 | 键 |
|---|---|
| 精神名 | idea 的 id |
| 精神描述 | id + `_desc` |
| 类别名 / 描述 | 类别 id / `id_desc` |
| 特质 | 特质 id |

```
l_english:
 TAG_my_spirit: "Idea's name"
 TAG_my_spirit_desc: "Idea's description"
```

没写本地化的精神：普通 idea 会用 `common/names` 随机起名，国家精神则直接用 id 当名字。

### 结构限制

- 一个类别默认最多 **7 个槽（横向 1 行）**，由 `interface/countrypoliticsview.gui` 里 `country_politics_idea_category_entry` 的 gridbox 决定（默认每槽 80×64）；不改 GUI 就无法超过 7 个。
- `<idea slot>_cost_factor` 修正（如 `political_advisor_cost_factor`、`economy_cost_factor`）要生效，前提是该 slot 在加载顺序上已有 idea 或角色定义。
- `common/ideas/*.txt` 按 Unicode 字符序加载：大写字母 < 下划线 < 小写字母。所以 `TAG.txt` 早于 `_economy.txt` 早于 `country.txt`。文件名以大写开头时，给原版法案写 `economy_cost_factor` 会报错；修法：改文件名小写、新开文件，或用 `replace_path` 且把法案文件改成 `00_economy.txt` 之类更早的名字。
- 角色槽的 cost 修正还要求 `common/ideas/*.txt` 里为角色槽定义了占位 idea（角色加载晚于 idea）。
- 没有“直接修改 idea”的接口，只能 `add_ideas` / `remove_ideas` / `swap_ideas` / `add_timed_idea`（+ `modify_timed_idea`）。`swap_ideas = { remove_idea = old add_idea = new }`。
- 限时精神：`add_timed_idea = { idea = my_idea days = 365 }`。
- 开局带精神：在 `history/countries/*.txt` 里 `add_ideas`；要让国家选择界面也显示，需要在 bookmark 的 `ideas = { ... }` 里补。

### 常见错误

- `picture = GFX_xxx` / `picture = idea_xxx` → 前缀叠加后找不到 sprite，显示默认图。
- 把 `research_bonus` / `equipment_bonus` 写进 `modifier = { ... }` → 无效（它们是 idea 的直接属性）。
- 依赖变量写 `modifier` → 不生效，需要 dynamic modifiers。
- 忘写 `allowed_civil_war` → 内战开始后精神消失。
- 期待 history 里的 `on_add` 生效 → 不执行，需要在同一 effect 块里手动补效果。
- 类别加到第 8 个槽才发现不显示 → GUI gridbox 的 7×1 限制。
- 新类别没改 `GFX_idea_categories` 的 `noOfFrames` → 类别图标错位。

---

## 第 13 章 角色与舆论

### 角色（Characters）

页面名说明：`Characters` 返回 404，正确页面是 `Character_modding`（角色系统，1.11 起）。

URL：https://hoi4.paradoxwikis.com/index.php?title=Character_modding&action=raw （`{{Version|1.12}}`，国家领袖 1.13）
原 404 地址：https://hoi4.paradoxwikis.com/index.php?title=Characters&action=raw

注意：**特工（operative）不是角色**，仍由 `create_operative_leader` 创建。

### 文件位置

| 内容 | 路径 |
|---|---|
| 角色定义 | `common/characters/*.txt` |
| 招募（必须） | `history/countries/TAG*.txt` 里 `recruit_character = ...` |
| 通用角色模板 | `history/general/*.txt`（本质是启动前执行的 effect 块） |
| 国家领袖特质 | `common/country_leader/*.txt` |
| 陆军/海军将领特质 | `common/unit_leader/*.txt` |
| 肖像 sprite | `interface/*.gfx`（原版 `interface/ideas.gfx`、DLC 的 `ghp_ideas_characters.gfx`） |
| 肖像图片 | `gfx/leaders/<TAG>/`（领袖）、`gfx/interface/ideas/`（顾问），只是约定 |
| 本地化 | `localisation/english/*_l_english.yml` |

文件名无意义；同名文件按加载顺序覆盖。

### 最小可用模板

`common/characters/TAG_characters.txt`：

```
characters = {
    TAG_my_leader = {
        name = TAG_my_leader
        portraits = {
            civilian = {
                large = GFX_portrait_TAG_my_leader
                small = GFX_advisor_TAG_my_leader
            }
        }
        country_leader = {
            ideology = despotism
            traits = { my_trait_1 }
            desc = TAG_my_leader_desc
        }
        advisor = {
            slot = political_advisor
            idea_token = TAG_my_leader_advisor
            ledger = civilian
            traits = { my_trait_1 }
            available = {
                has_political_power > 100
            }
        }
    }
}
```

`history/countries/TAG - TAG.txt`：

```
recruit_character = TAG_my_leader
# 这行之后必须还有内容（空行也算），否则招募失败
```

将领角色：

```
characters = {
    TAG_my_general = {
        name = TAG_my_general
        portraits = {
            army = {
                large = GFX_portrait_TAG_my_general
                small = GFX_advisor_TAG_my_general
            }
        }
        corps_commander = {
            traits = { my_trait_1 my_trait_2 }
            skill = 5
            attack_skill = 5
            defense_skill = 2
            planning_skill = 4
            logistics_skill = 5
            visible = { NOT = { has_character_flag = TAG_exiled_flag } }
        }
    }
}
```

### 字段表：角色本体

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `name` | 本地化键 | 角色名 |
| `portraits` | `{ civilian/army/navy = { large = ... small = ... } }` | 三类；`small` 作顾问头像，`large` 作领袖/将领大头像。顾问头像三类任意一类给 small 即可；large 与类别绑定。值可写 sprite 名，也可直接写文件路径字符串 |
| `gender` | `undefined`/`male`/`female` | 影响本地化代词；缺省 undefined，行为等同 male；`generate_character` 生成的未定义性别会按 `FEMALE_UNIT_LEADER_BASE_CHANCE` 随机 |
| `advisor` | 块，可多个 | 每个块占一个顾问槽 |
| `country_leader` | 块 | 国家领袖角色 |
| `corps_commander` / `field_marshal` / `navy_leader` | 块 | 陆军/元帅/海军将领 |
| `scientist` | 块 | 科学家（1.13 特殊项目相关） |
| `instance` | `{ allowed = {} ... }` | 开局按条件选择不同定义；每个 instance 必须有 `allowed`，且要有多份才有意义 |

### 字段表：advisor

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `slot` | slot 名 | 占用的角色槽，内置：`political_advisor`、`theorist`、`army_chief`、`navy_chief`、`air_chief`、`high_command` |
| `idea_token` | 标识符 | **必填**。作为 idea 处理时的 ID；`has_idea`、`show_ideas_tooltip`、`activate_advisor` 都吃这个而不是角色 ID。缺省会被当成 null token，导致所有没写 token 的顾问一起消失 |
| `ledger` | `army`/`air`/`navy`/`military`/`civilian`/`all`/`hidden` | `theorist` 与 `high_command` 必须逐个指定 |
| `can_be_fired` | `no` | 不可解雇（1.12.8 起才用；此前用 `removal_cost = -1`） |
| `traits` | `{ ... }` | 国家领袖特质，生效为修正 + 头像角标 |
| `available` / `visible` / `cost` | 同 idea | 可选条件与成本 |
| `on_add` / `on_remove` | effect | **scope 是角色，不是国家**；取国家用 `owner` |

### 字段表：country_leader

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `ideology` | ideology **type**（如 `despotism`、`marxism`、`nazism`） | 不能填意识形态组；type 影响提示文本、图标，以及与他国的 `similar_ruling_party` / `same_ruling_party` 关系 |
| `traits` | `{ ... }` | 国家领袖特质 |
| `expire` | 日期 `1949.1.1` | 到期后即使招募也不可用 |
| `id` | 整数 | 旧系统遗留，用于 `has_country_leader`；应省略 |
| `desc` | 本地化键 | **必须是本地化键**，直接写文本不显示 |

组队规则：每种意识形态组中**第一个被招募**的角色成为该党领袖。`set_politics` 会强制产生领袖，所以先 `recruit_character` 再 `set_politics`；跨起始日期换人用 `promote_character`。

### 字段表：将领

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `traits` | `{ ... }` | 将领特质（`common/unit_leader/*.txt`） |
| `skill` | 整数 | 总技能：陆军无直接效果；海军每级 +5% 命中、+2% 舰队协同 |
| `attack_skill` | 整数 | 陆军每级 +2.5% 进攻；海军每级 +5% 伤害 |
| `defense_skill` | 整数 | 陆军每级 +2.5% 防御；海军每级 +5% 防御 |
| `planning_skill` | 整数，仅陆军 | 每级 +5% 计划速度、+2% 计划上限加成 |
| `logistics_skill` | 整数，仅陆军 | 每级 -2.5% 补给消耗 |
| `maneuvering_skill` | 整数，仅海军 | 每级 +2.5% 阵位、+1% 海上撤退速度 |
| `coordination_skill` | 整数，仅海军 | 每级 +2% 舰队协同 |
| `legacy_id` | 整数 | 旧系统遗留（`has_id`、`has_unit_leader` 用），应省略 |
| `visible` | trigger | 将领是否可见可选；也可用国家 scope 的 trigger（视为招募国）；大多数情况改用 `add_corps_commander_role` 等 effect 更灵活 |

### 字段表：scientist

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `traits` | `{ scientist_trait_* }` | 用科学家特质，不是将领特质 |
| `skills` | `{ specialization_air = 3 ... }` | 给某个专精定等级；基础游戏 4 类，写多个不报错但**只认第一个** |
| `desc` | 本地化键 | 已知 bug：科学家描述不显示 |
| `visible` | trigger | 可见条件 |

### 字段表：country leader traits（`common/country_leader/*.txt`）

必须包在 `leader_traits = { ... }` 里，否则不生效。

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| `random` | `no` | 是否可能出现在随机生成的国家领袖身上 |
| `sprite` | 整数 | 取 `GFX_idea_traits_strip` 的第几帧（从左数，1 起） |
| `ai_will_do` | MTTH 块 | AI 选带此特质的顾问/idea 的权重，默认 1 |
| `command_cap` | 值 | 该特质带来/消耗的指挥上限（主要用于军事顾问） |
| 常规 modifier | 直接写 | 作用于拥有该角色/idea 的国家 |
| `targeted_modifier` / `equipment_bonus` | 同 idea | 可用；`research_bonus`、`rule` 不适用于特质 |

本地化键就是特质名。sprite 帧数：改图必须改 `noOfFrames`；不要在原版 `ideas.gfx` 上改，另建 `.gfx`（按 ASCII 文件名顺序，后加载的覆盖前者）。

### 字段表：unit leader traits（`common/unit_leader/*.txt`）

同样在 `leader_traits = { ... }` 内，每项一个特质 ID。

通用：`type`（`all`/`land`/`navy`/`operative`/`corps_commander`/`field_marshal`）、`trait_type`（`basic_trait`/`personality_trait`/`assignable_trait`/`basic_terrain_trait`/`assignable_terrain_trait`/`status_trait`/`exile`）、`show_in_combat`、`allowed`（将领 scope，FROM 为招募国）、`ai_will_do`、`new_commander_weight`（仅 personality_trait）、`slot`、`specialist_advisor_trait` / `expert_advisor_trait` / `genius_advisor_trait`、`unit_type`、`unit_trigger`。

修正类：`modifier`（给部队）、`non_shared_modifier`（给将领本人，tooltip 不同）、`corps_commander_modifier`、`field_marshal_modifier`、`sub_unit_modifiers`、`<skill>`（固定加）、`<skill>_factor`（百分比加成，`1` = +100%）、`override_effect_tooltip`、`custom_effect_tooltip`、`enable_ability`、`on_add`、`on_remove`、`daily_effect`。

选特质界面：`mutually_exclusive`（双方都要写）、`parent`、`num_parents_needed`（缺省或 -1 = 全部父项必需）、`gui_row`（缺省/-1 = 不进树）、`gui_column`、`prerequisites`（将领 scope）、`custom_prerequisite_tooltip`、`cost`（经验）、`gain_xp`（战斗单位 scope）、`gain_xp_leader`（将领 scope）、`gain_xp_on_spotting`、`custom_gain_xp_trigger_tooltip`、`trait_xp_factor`。

sprite：`GFX_trait_<特质名>`；本地化 `my_trait` 与 `my_trait_desc`。

### 肖像命名规则

- spriteType 的 `name` 必须以 `GFX_` 开头，整名一个词，不能有空格与非 ASCII 字符。
- `texturefile` 必须与真实文件路径 + 文件名 + 扩展名完全一致（Windows 默认隐藏扩展名，最容易漏）。
- 陆军将领必须有小头像（军官团里可以当部长）：手写 `small`，或额外定义 sprite 名 = 大头像名 + `_small`，系统会在升迁时自动用它。
- 肖像失效会退化成随机肖像；国家选择阶段还没分配，会显示默认剪影。
- 动画肖像用 `frameAnimatedSpriteType` 替代 `spriteType`。
- 运行时换图：`set_portraits`，角色 scope 直接写，国家 scope 用 `set_portraits = { character = TAG_xxx ... }`。

### 本地化键规则

| 对象 | 键 |
|---|---|
| 角色名 | `name` 指定的键 |
| 领袖描述 | `country_leader` 的 `desc` 键 |
| 国家领袖特质 | 特质 id |
| 将领特质 | 特质 id，描述 `id_desc` |

```
l_english:
 TAG_my_leader: "My leader's name"
 TAG_my_leader_desc: "My leader's description"
 my_trait_1: "My trait"
```

### 结构与运行限制

- **不 `recruit_character` 角色永不出现**；招募也不能放在 history 文件最后一行。
- 一个角色可以同时拥有多个角色（领袖 + 顾问 + 将领），这也是 1.11 角色系统存在的意义。
- `add_advisor_role` 创建的顾问不能带 script（`visible`/`available`/`on_add`）；想条件显示就用普通 advisor 块 + `visible`。同理不要对带 script 的顾问用 `remove_advisor_role`。
- 从游戏中移除角色：`retire_character`（国家 scope）/ `retire`（角色 scope）。不是永久的，`set_nationality` 可以连带角色重新加入。
- 换领袖用 `promote_character` 即可，旧领袖不影响；只摘领袖职位用 `remove_country_leader_role`。
- 不要用 `kill_country_leader` / `retire_country_leader` / `kill_ideology_leader` / `retire_ideology_leader`：它们作用于“当前任何领袖”，无法指定对象。前两者行为等同 `retire_character`；后两者只把人从继承序列里摘掉，旧领袖保留全部职位。
- 雇佣顾问：`activate_advisor = TAG_character_name_token`（用 `idea_token`）。
- `generate_character`：`token_base` 必填；`name` 可选（不写就随机）；顾问的 `idea_token` 会被拼成 `token_base_idea_token`，不写则用 slot 名。中途生成必须先在 history 里放“模板”（可用 `always = no` 让任何国家都不招募），否则失败；直接中途写完整块无效。

### 常见错误

- 定义了角色但忘了 `recruit_character` → 游戏里完全不存在。
- `recruit_character` 是文件最后一行 → 招募失败。
- 顾问漏 `idea_token` → 其他没写 token 的顾问一起消失，或无法被 `has_idea` / `activate_advisor` 识别。
- 把 `country_leader.ideology` 写成意识形态组（`democratic`）而不是 type（`liberalism`）。
- `country_leader.desc` 直接写文本而不是本地化键 → 不显示。
- sprite 名与角色定义里引用的名字不一致，或漏写 `spriteTypes = { ... }` 外壳、文件扩展名不是 `.gfx` → 肖像失效变随机图。
- `texturefile` 用反斜杠 / 漏扩展名 → 同上。
- 给只有 large 的陆军将领不准备 small 头像 → 军官团部长位缺图。
- 以为 `add_advisor_role` 能带 `visible` 条件 → 不会生效。
- 在 `common/characters/*.txt` 里等号左右不匹配（少一个花括号）→ 整个文件角色失效，且错误提示指向别处。

### 舆论（Opinions）

- `https://hoi4.paradoxwikis.com/index.php?title=Opinion_modding&action=raw` → **HTTP 404，无此页面**。
- 变体 `Opinion` → HTTP 200，内容是 `#REDIRECT [[Diplomacy]]`。
- 变体 `Opinions` → **HTTP 404**。

结论：wiki 没有独立的 opinion modding 页面；opinion 相关内容并入 `Diplomacy` 页（本笔记未展开该页，避免无原文支撑）。`（wiki 未明确）` opinion 数据文件的确切路径与字段，需读 `Diplomacy` 页或原版 `common/opinion_modifiers/` 实测确认。

对照：国家精神页确实有 `similar_ruling_party` / `same_ruling_party` 两个 opinion 修正的引用（见 Idea/Character 节），说明 opinion modifier 是存在的修正类型，但定义方式未在本批页面中说明。

---

## 第 14 章 力量平衡与成就

### 力量平衡（Balance of power）

URL：https://hoi4.paradoxwikis.com/index.php?title=Balance_of_power_modding&action=raw （`{{Version|1.13}}`）

### 文件位置

| 内容 | 路径 |
|---|---|
| 力量平衡定义 | `common/bop/*.txt` |
| 推动平衡的修正（static modifier） | `common/modifiers/*.txt` |
| 侧图标 | `interface/*.gfx` |

### 机制

- 每个 BoP 至少 2 侧；可定义多于 2 侧，但同一时间只显示初始化时指定的 2 侧。
- 用单值 -1 ~ 1 表示，最多 3 位小数。`[-1, 0)` 是左侧，`[0, 1]` 是右侧。侧本身没有“左/右”属性，初始化时才指定哪侧在哪半。
- 处于某个 `range` 时给修正或执行效果。range 可以挂在侧上（该侧可见时才可见），也可以直接挂在 BoP 上（始终可见，通常做中间“均衡”段）。
- **BoP 是全局的**：两个国家用同一个 BoP 时数值完全同步；两边都有每日/每周推动修正时效果叠加。

### 最小可用模板

```
TAG_example_balance = {
    initial_value = 0.25            # 注意：wiki 正文写的是 intial_value（原文拼写）
    left_side = default_left_side
    right_side = default_right_side
    decision_category = TAG_example_category

    range = {
        id = mid_range
        min = -0.1
        max = 0.1
        modifier = {
            war_support_weekly = 0.5
        }
        rule = {
            can_create_faction = yes
        }
    }

    side = {
        id = default_left_side
        icon = GFX_idea_generic_agrarian_society
        range = {
            id = left_side_range
            min = -1
            max = -0.1
            modifier = {
                war_support_weekly = 0.1
            }
            on_activate = {
                random_owned_controlled_state = {
                    limit = { NOT = { is_core_of = PREV } }
                    add_core_of = PREV
                    set_state_flag = cored_by_bop
                }
            }
            on_deactivate = {
                random_owned_controlled_state = {
                    limit = { has_state_flag = cored_by_bop }
                    remove_core_of = PREV
                    clr_state_flag = cored_by_bop
                }
            }
        }
    }

    side = {
        id = default_right_side
        icon = GFX_idea_generic_degauss_ship_hulls
        range = {
            id = right_side_range
            min = 0.1
            max = 1
            modifier = {
                war_support_weekly = 0.9
            }
        }
    }
}
```

初始化（通常写在 `history/countries/*.txt`，也可写在 focus 奖励或事件选项里）：

```
set_power_balance = {
    id = TAG_example_balance
    left_side = default_left_side
    right_side = default_right_side
    set_value = 0.1
}
```

推动平衡的修正（`common/modifiers/*.txt` 的 static modifier）：

```
my_bop_modifier = {
    power_balance_weekly = -0.01
}
```

```
add_power_balance_modifier = {
    id = TAG_example_balance
    modifier = my_bop_modifier
}
```

移除用 `remove_power_balance_modifier`（同语法）或 `remove_all_power_balance_modifiers`。

### 字段表

| 字段 | 类型/取值 | 作用 |
|---|---|---|
| 块名 | 标识符 | BoP 的唯一 ID；重复时 error.log 写 `Template ID duplicate: bop_name`，后加载的生效 |
| `intial_value` | -1 ~ 1 | 默认值（原文如此拼写，照抄原文；正常写法应为 `initial_value`，示例块里用的是 `initial_value`）。未设默认 0 |
| `left_side` / `right_side` | side id | 初始化时默认显示的两侧 |
| `decision_category` | 决议类别 id | 把该决议类别搬进 BoP 视图，无法在别处打开；类别内的 `allowed` 等触发器仍按持有国求值 |
| `side` | 块 | 侧定义：`id`（同 BoP 内不可重复，重复取第一个并报 `Side ID duplicate`）、`icon`（sprite，未定义或无此 sprite 则不显示图标，无兜底）、`range`（块，可多个） |
| `range` | 块 | `id`（同一 BoP 内不可重复；重复会报 `Range ID duplicate`，且 `is_power_balance_in_range` 的严格比较只认最左那段）、`min`、`max`（落在 min 上算内，落在 max 上只有 max=1 时才算内）、`modifier`、`rule`、`on_activate`、`on_deactivate` |

- BoP 修正本质是 static modifier，从 BoP 克隆到每个持有该 BoP 的国家，所以推动量随持有国数量线性放大（3 国时 `power_balance_daily = 0.01` 实际每天推 3%）。
- 效果的完整列表见 `Effect` 页的 “Balance of power” 段，触发器见 `Triggers` 页同名段（本页只做了 section 转引）。

### 常见错误

- 只定义 1 侧或没定义 default 左右侧 → UI 是按“总有左右两侧”设计的。
- `range` 的 `id` 在两侧重复 → 严格比较失效。
- 忘了 `set_power_balance` → BoP 不会出现在任何国家身上（它不是自动分配的）。
- 以为 BoP 数值按国家独立 → 全局共享。
- 给多个国家挂同一个 BoP 又叠加同一推动修正 → 数值被 N 倍推动。
- 抄 `intial_value` 这个拼写去用 `initial_value` 之外的名字 → 只有示例里验证过的写法可靠（原文两处写法不一致，`（wiki 未明确）` 哪个是引擎实际读取的键）。

### 成就（Achievements）

URL：https://hoi4.paradoxwikis.com/index.php?title=Achievements&action=raw （`{{Version|1.19}}`）

### 与 mod 制作的关系

这一页是**玩家成就清单**（293 个，Xbox 版 191 个），不是 modding 参考页：没有脚本字段、没有文件路径、没有可复用的模板。能用于 mod 的只有约束条件：

| 要点 | 内容 |
|---|---|
| 生效条件 | 仅单机铁人（Ironman），1936 起始（个别成就要求 1939），难度 regular / veteran / elite |
| 版本 | 可在旧版本获得，前提是该版本已存在该成就 |
| AI 设置 | 允许关闭 Historical AI Focuses。在 Custom Game Rules 的 “AI Behavior” 页把某国从 `Default` 改成**其历史路线**不算破坏铁人；改成非历史路线则会变成非铁人 |
| 校验和 | checksum 被改动就拿不到成就：改游戏文件、跑影响机制的 mod、安装损坏都会破坏；图形类 mod 不影响 checksum |
| Xbox | 自 2024-03-01 起不再与 Steam 同步，Trial of Allegiance 及后续 DLC 没有成就 |

对制作 MUV-LUV 类 total conversion 的直接含义：只要 mod 改了机制，校验和变化，成就体系与 mod 互斥——不需要在 mod 里做任何成就相关兼容代码。（成就定义不在 wiki 列出的任何 mod 目录内，`（wiki 未明确）` 其数据文件位置。）

---

## 第 15 章 科技

### 文件路径总表

| 内容 | 路径 | 来源页 |
|---|---|---|
| 装备（原型 + 具体型号） | `common/units/equipment/*.txt` | Equipment_modding |
| 装备模块 | `common/units/equipment/modules` | Country_creation（注释） |
| 装备升级项 | `common/units/equipment/upgrades` | Country_creation（注释） |
| 运输船 | `common/units/equipment/convoys.txt` | Ship |
| 单位（sub_units） | `common/units/*.txt` | Unit_modding |
| 单位类别（categories） | `common/unit_tags/00_categories.txt` | Unit_modding |
| 科技类别 / 科技文件夹 | `common/technology_tags/*.txt` | Technology_modding |
| 科技 | `common/technologies/*.txt` | Technology_modding |
| 科技共享组 | `common/technology_sharing/*.txt` | Technology_modding |
| 战斗战术 | `common/combat_tactics.txt` | Technology_modding |
| 师名组 | `common/units/names_divisions/*.txt` | Division_modding |
| 舰名组 | `common/units/names_ships/` | Country_creation |
| OOB（陆军/海军/空军） | `history/units/*.txt` | Division_modding / Country_creation |
| 国家历史 | `history/countries/TAG*.txt` | Country_creation |
| 科技树界面 | `interface/countrytechtreeview.gui` / `.gfx` | Technology_modding |
| 国策/学说树界面 | `interface/countrydoctrinetreeview.gui` | Technology_modding |
| 装备设计器界面 | `interface/equipmentdesigner/<tanks|ships|planes>` | Equipment_modding |
| 单位图标 sprite | `interface/subuniticons.gfx` | Unit_modding |
| 单位模型 entity | `gfx/entities/*.asset` | Unit_modding |
| 计数器贴图 | `gfx/interface/counters/**` | Unit_modding |

`common/units/equipment/` 与 `common/units/` 是两层不同目录：前者放 equipment（原型/型号），后者放 sub_units（师级单位定义）。写错目录表现是"装备能造但单位不出现"或反之。

### 科技（technologies）

来源：https://hoi4.paradoxwikis.com/index.php?title=Technology_modding&action=raw

科技在 `common/technologies/*.txt`；类别与文件夹在 `common/technology_tags/*.txt`；树界面在 `interface/countrytechtreeview.gui`（学说树是 `interface/countrydoctrinetreeview.gui`）。

> **The filename has no bearing on how the file is read: any technology can be in any folder without issues.**

### 15.1 文件骨架

```
technologies = {
    my_technology_1 = {
        ...
    }
    my_technology_2 = {
        ...
    }
}
```

块名即科技 ID，同时是本地化键。科技**默认隐藏**，需要在 GUI 里显式加入才会出现在树里。

### 15.2 常用字段总表

| 字段 | 示例 | 作用 |
|---|---|---|
| `research_cost` | `1` | 1 ≈ 默认科研速度下 100 天（`NDefines.NTechnology.BASE_TECH_COST = 100`） |
| `start_year` | `1936` | 设计年份；每提前一年 +200%（`BASE_YEAR_AHEAD_PENALTY_FACTOR = 2`，按剩余天数平滑） |
| `folder` | `{ name = my_folder  position = { x = 0 y = 1 } }` | 所属文件夹与格子坐标 |
| `path` | `{ leads_to_tech = X  research_cost_coeff = 1 }` | 连线并构成前置（OR） |
| `dependencies` | `{ my_technology_1 = 1 }` | 前置但不画线（AND） |
| `XOR` / `xor` | `{ my_technology_2 }` | 互斥，每个互斥科技都要写全 |
| `categories` | `{ my_category_1 }` | 类别：AI 权重、`research_bonus`、分享组范围 |
| `ai_will_do` | `{ base = 1  modifier = { factor = 3  tag = POL } }` | AI 研究意愿（MTTH 块） |
| `ai_research_weights` | `{ offensive = 1 }` | 按 focus 调 AI 优先级 |
| `enable_equipments` | `{ my_equipment_1 my_equipment_2 }` | 解锁装备类型 |
| `enable_subunits` | `{ my_subunit_1 }` | 解锁单位 |
| `enable_equipment_modules` | `{ ship_extra_fuel_tank }` | 解锁模块 |
| `enable_building` | `{ building = my_building  level = 5 }` | 解锁到该等级**上限**（不是加 5 级） |
| `enable_tactic` | `my_tactic` | 解锁战斗战术（`common/combat_tactics.txt`） |
| `allow` | `{ always = no }` | 持续检查；false 时界面不可点，但 effect 可给、仍可见 |
| `allow_branch` | `{ has_dlc = "..." }` | 可见性；false 时沿 `path` 相连的科技一起隐藏 |
| `on_research_complete` | `{ ... }` | 研究完成的 effect |
| `on_research_complete_limit` | `{ has_tech = X }` | 上面那块执行的前提 |
| `show_effect_as_desc` | `yes` | 修正/效果写进描述而非 tooltip |
| `show_equipment_icon` | `yes` | 悬停显示所解锁装备图标 |
| `force_use_small_tech_layout` | `yes` | 强制用 small item |
| `desc` | `MY_TECH_SPECIAL` | 附加描述（不覆盖原描述） |
| `doctrine` / `doctrine_name` | `yes` / `my_doctrine_name` | 学说标记 / 学说分支名 |
| `xp_research_type` | `army` / `navy` / `air` | 经验类型 |
| `xp_boost_cost` / `xp_research_bonus` | `40` / `1.5` | 经验加速 |
| `xp_unlock_cost` | `100` | 经验直接解锁 |
| `sub_technologies` / `sub_tech_index` | `{ ... }` / `1` | 子科技 / 覆盖子科技索引 |
| `ignore_for_layout` | `yes` | 写在 `path` 块内，避免 gridbox 重复报错 |

### 15.3 完整的、可直接改的科技模板

以 wiki 的 Examples 段为骨架，补上 `enable_equipments` / `enable_subunits` / `ai_will_do` / `categories`：

```
technologies = {
	my_technology_1 = {
		research_cost = 1
		start_year = 1936
		folder = { name = my_folder  position = { x = 0 y = 0 } }   # 与 gridbox 同坐标系
		allow_branch = { has_dlc = "Wojtek Expansion Pack" }
		path = { leads_to_tech = my_technology_3  research_cost_coeff = 1 }
		path = { leads_to_tech = my_technology_4  research_cost_coeff = 1 }
		xor = { my_technology_2 }
		categories = { my_category_1 }
		ai_research_weights = { defensive = 1 }
		ai_will_do = {
			base = 1
			modifier = { factor = 3  tag = POL }
		}
		army_attack_factor = 0.1        # 国家范围修正，直接写在科技里
	}

	my_technology_2 = {
		research_cost = 1.5
		start_year = 1937
		folder = { name = my_folder  position = { x = 0 y = 0 } }
		xor = { my_technology_1 }
		categories = { my_category_2 }
		ai_research_weights = { offensive = 1 }
		enable_equipment_modules = { my_module_1 }
		enable_subunits = { my_subunit_1 }
	}

	my_technology_3 = {
		research_cost = 1
		start_year = 1938
		folder = { name = my_folder  position = { x = -1 y = 1 } }
		path = { leads_to_tech = my_technology_5  research_cost_coeff = 1 }
		enable_equipments = { my_equipment_1 }
		force_use_small_tech_layout = yes
		show_equipment_icon = yes
		categories = { my_category_1 }
	}

	my_technology_4 = {
		research_cost = 1.5
		start_year = 1939
		folder = { name = my_folder  position = { x = 1 y = 1 } }
		path = { leads_to_tech = my_technology_5  research_cost_coeff = 0.8 }  # 走这条更省
		enable_equipments = { my_equipment_2 }
		categories = { my_category_1 }
	}

	my_technology_5 = {
		research_cost = 1.75
		start_year = 1940
		folder = { name = my_folder  position = { x = 0 y = 2 } }
		categories = { my_category_1 }
		enable_building = { building = my_building  level = 1 }
		sub_technologies = { my_technology_6 }
	}

	my_technology_6 = {
		allow = { has_built = { type = my_building  value > 3 } }
		research_cost = 0.8
		start_year = 1941
		categories = { my_category_1 }
		enable_building = { building = my_building  level = 3 }
	}
}
```

### 15.4 categories

```
categories = { my_category_1 my_category_2 }
```

类别定义在 `common/technology_tags/*.txt` 的 `technology_categories = { ... }` 块内，只列名字。本地化两个键：

```
my_category_1: "My Category"
my_category_1_research:0 "My Category's Research Speed"
```

后一个（`_research` 后缀）用于 `research_bonus = { my_category_1 = 0.1 }` 这类修正的 tooltip。

类别不显示给玩家，但有四个实际用途：AI 权重、`research_bonus`、`add_tech_bonus`、科技共享组限定的范围。

### 15.5 path / dependencies / XOR 的语义差异

- `path = { leads_to_tech = X ... }` 写在**起点**科技上。它让 X 需要本科技；多个 path 指向 X 时是 **OR**（任一条满足即可）。`research_cost_coeff` 乘在后续科技成本上，可以用来表示"走高级路线后更省"。
- `dependencies = { A = 1  B = 1 }` 是 **AND**，全部要研究完，且不画线、不分配 gridbox。
- `XOR = { A B }` 互斥。必须**每个**互斥科技里都写全对方，只写一边不够。
- `else` 在 history 文件里只支持嵌套写法（见 7.2）。

gridbox 规则：一个科技若在任何所在文件夹里都没有 path 连到它，就必须在文件夹容器里单独定义 gridboxType，否则整条分支不会出现。

### 15.6 folder 与 tech tree 坐标

```
folder = {
    name = my_folder
    position = { x = 0 y = 1 }
}
```

`position` 的单位是 gridbox 的 `slotsize`：`slotsize = { width = 70 height = 70 }` 时 1 单位 = 70 px。坐标轴方向由 gridbox 的 `format` 决定：

- `format = "LEFT"`：x 向上到下、y 从左到右（横向树，父节点在最左）
- `format = "UP"`：x 从左到右、y 向上到下（纵向树，父节点在最上）

原点由 gridbox 定义里的 `position = { x = 100 y = 100 }` 决定（像素，相对窗口左上角）。一个科技要出现在多个文件夹，就写多个 `folder = { ... }`。

### 15.7 force_branch / 子科技 / 隐藏科技

- 隐藏科技：`allow = { always = no }`。AI 仍能研究，所以要显式挡住，否则 AI 会去点。
- effect 给予：`set_technology = { my_technology_1 = 1 }`；取消：`= 0`，可加 `popup = no` 去提示。
- 取消研究**不总可靠**：互斥科技可能取消失败；解锁数据库对象的科技取消后对象仍可用直到重开游戏。
- `sub_technologies` 最多 3 个（`NDefines.NTechnology.MAX_SUBTECHS = 3`），子科技不需要自己的 gridbox 和 `folder`。

### 15.8 科技的 AI 权重

**AI 要研究某个科技，该科技的至少一个类别必须出现在 `common/ai_focuses/*.txt` 里**（原文全大写 MUST）。

`ai_will_do` 是 MTTH 块，默认分数 1，可用 `base` / `add` / `factor` 调整；`modifier = { ... }` 内是触发器，也可用这三个参数，按书写顺序依次应用。评估方式：每 7 天（`NDefines.NAI.RESEARCH_DAYS_BETWEEN_WEIGHT_UPDATE = 7`）为每个科技在 0 到 `ai_will_do` 值之间取随机数。

```
ai_will_do = {
    base = 1
    modifier = {
        factor = 3
        tag = POL
    }
}
```

### 15.9 科技的名字与图标

- 名字：本地化键 = 科技 ID；描述 = ID + `_desc`。
- **没写名字时借用所解锁装备的名字**（含描述）。可借此做国家专用名：

```
l_english:
 HON_my_equipment_1: "My Honduran equipment"
 my_equipment_1: "My equipment"
```

- 图标：`interface/*.gfx` 里 `spriteType`，命名 `GFX_<tech id>_medium`；国家专用插在 GFX 后：`GFX_HON_my_technology_1_medium`。
- 图标回退方向与名字相反：装备没有独立图标时用科技的图标。

### 15.10 科技对单位的加成写法

直接写国家范围修正，或按 subunit / 类别 / 地形写：

```
my_technology_1 = {
    category_all_infantry = {
        combat_width = -0.2
        urban = {
            attack = 0.15
        }
    }
    destroyer = {
        naval_speed = 0.1
    }
}
```

- 可用的键：subunit 名（`common/units/*.txt` 里定义的）、或其 `categories`（`common/unit_tags/*.txt`）。
- 地形作用域：`common/terrain/*.txt` 里的地形名，外加 `amphibious`（登陆）与 `river`（渡河）。
- 这些修正对单位是**乘算**。

### 15.11 科技文件夹（folders）

定义在 `common/technology_tags/*.txt` 的 `technology_folders = { ... }`，块名即 folder ID。三个参数：

```
available = { has_dlc = "Poland: United and Ready" }   # 可见性
ledger = army    # army / air / navy / military / civilian / all / hidden
doctrine = yes   # 是否学说文件夹，默认 false
```

本地化：`my_folder` 与 `my_folder_desc`。

文件夹要真正可用，界面必须补齐三样：folder tab、folder 容器（含 gridbox）、item 容器。少任何一样，玩家无法手动研究（AI 仍能研究，`set_technology` 仍能给予）。

### 15.12 科技共享组

`common/technology_sharing/*.txt`，每块 `technology_sharing_group = { ... }`：

```
technology_sharing_group = {
    id = tech_group_id
    name = tech_group_name
    desc = tech_group_desc
    picture = GFX_technology_sharing_default

    research_sharing_per_country_bonus = 0.1
    is_faction_sharing = yes

    categories = { infantry industry }

    available = {
        is_in_faction = yes
    }
}
```

- 只能通过 effect `add_to_tech_sharing_group` 加成员。
- `available` 为 false 时自动踢出。
- 上限受 `NTechnology.MAX_TECH_SHARING_BONUS` 限制。

---

## 第 16 章 装备原型与升级链

### 装备：archetype 与升级链

来源：https://hoi4.paradoxwikis.com/index.php?title=Equipment_modding&action=raw

### 16.1 两类条目

wiki 原文：

> Equipment is found in `common/units/equipment/*.txt`. Equipment is split into two types, archetype and regular. Archetype equipment is used to assign more general attributes that regular equipment then inherits via the *archetype* attribute.

顶层容器：

```
equipments = {
	<equipment> = {
		...
	}
}
```

**注意**：wiki 用的顶层容器名是 `equipments`。`archetypes = { ... }` 这种顶层块在 wiki 页面里没有出现 `（wiki 未明确）`；区分 archetype 与普通型号靠条目内的 `is_archetype = yes` 与 `archetype = <name>`。

### 16.2 archetype 条目字段（原文注释直译）

```
equipments = {
	<equipment> = {
		year = <int>		# Limits the equipment from appearing before the specified year. Optional
		picture = <name>	# GFX reference used to define equipment picture in lend-lease
		priority = <value> # ?（原文就是问号，wiki 未明确语义）
		archetype = <equipment archetype name>   # archetype of equipment, mutually exclusive with is_archetype = yes
		parent = <equipment type name>           # previous version of equipment, can't be archetype
		can_be_produced = {                      # Optional, specifies when equipment of this category can be produced.
			<triggers>
		}
		can_be_lend_leased = {
			# a trigger to check if a country can lend lease to another country.
			# scope is country, from is the country we will lend lease to
		}
		is_archetype = yes	# Specifies an entry as an archetype entry. All non-archetype entries inherit
		is_buildable = no	# Prevents this equipment from being built.
		active = yes		# Determines if this equipment is available without unlocking from a technology.

		type = <type>	    	 # Internal type: what kind of unit can use this equipment
		is_frame = <yes|no>      # Default yes for modular equipment, not applicable for non-modular equipment.
		                         # Frame refers to tank chassis, ship hulls, and airplane frames.
		group_by = <group>	  # How the equipment is grouped in the production screen
		interface_category = <type>  # Which category the equipment appears in the production screen
		max_military_factories = <amount>
		max_dockyard_factories = <amount>
			# Limit the amount of military factories or dockyards assignable to the type

		module_slots = { ... }
		module_count_limit = { ... }

		resources = {
			<resource> = <amount>
		}
		upgrades = {
			# List of upgrade names
		}  # Upgrades of equipment, mostly used for non equipment designer versions of equipment

		<unit stat name> = <value>

		manpower = <value>  # Manpower required to produce one unit of the equipment (naval only)
	}
}
```

关键约束，逐条：

- `archetype` 与 `is_archetype = yes` **互斥**（原文 "mutually exclusive"）。archetype 条目用 `is_archetype = yes`；具体型号用 `archetype = <某 archetype>`。
- `parent` 指向"上一代型号"，且**不能是 archetype**（原文 "can't be archetype"）。这是升级链的接法：`<equipment> = { parent = <上一代> }`。
- `year` 是"最早可出现年份"，早于该年不会出现在生产/设计界面。
- `is_buildable = no` 用于把某个 archetype 标记为不可生产（通常配合 `is_frame`、模块化底盘）。
- `active = yes` 表示不需要科技解锁就可用；配合科技的 `enable_equipments = { ... }` 使用。
- `is_frame` 对模块化装备默认为 yes；对非模块化装备不适用。
- `interface_category` 决定生产界面的分页；`group_by` 决定生产界面里的分组方式（取值受 `group_by` 类型限制，见 2.4）。
- `max_military_factories` / `max_dockyard_factories` 限制可分配到该类装备的工厂/船坞数量。
- `manpower` 在**海军装备**上表示生产一艘所需人力。

### 16.3 普通型号条目字段

```
equipments = {
    <equipment> = {
        year = <int>        # Limits the equipment from appearing before the specified year. Optional
        active = yes        # Determines if this equipment is available without unlocking from a technology.
        archetype = <equipment>  # Which archetype equipment this equipment inherits from.
        parent = <equipment>     # Which equipment is parent to this equipment (i.e. which does it supercede)
        priority = <int>         # Priority for usage over other equipment.
        visual_level = <int>     # Image priority in production screen

        resources = {
            <resource> = <amount>
        }

        <modifiers>
    }
}
```

- `parent` 是"它取代谁"，`priority` 决定默认优先使用哪个型号，`visual_level` 决定生产界面图标的显示优先级。
- 普通型号不重复写 archetype 的全部属性，只写差异项（数值修正叠加在 archetype 之上）。

### 16.4 内部类型 / 分组 / 界面分类

`type` 合法值（Equipment_modding 页原文列表）：

- Land：`anti_air`、`anti_tank`、`armor`、`artillery`、`heavy_tank_chassis`、`infantry`、`light_tank_chassis`、`mechanized`、`medium_tank_chassis`、`motorized`、`rocket`、`support_equipment`
- Naval：`capital_ship`、`carrier`、`convoy`、`naval_transport`、`screen_ship`、`submarine`
- Air：`air_transport`、`cas`、`fighter`、`interceptor`、`tactical_bomber`、`missile`、`naval_bomber`、`strat_bomber`、`suicide`

`group_by` 合法值：`archetype`、`type`。

`interface_category` 合法值：

- `interface_category_land`
- `interface_category_armor`
- `interface_category_capital_ships`
- `interface_category_screen_ships`
- `interface_category_other_ships`
- `interface_category_air`

### 16.5 upgrades 与模块化（两个体系）

wiki 明确两者是替代关系：

> **Any equipment that utilizes modules must have equipment designer set-up, if equipment designer not presented it will instead utilize upgrade system**

- 用了 `module_slots` 的装备 → 必须有对应的 equipment designer 界面容器，否则不显示设计器。
- 没用模块的装备 → 走 `upgrades = { ... }`（升级项列表），升级项本身定义在 `common/units/equipment/upgrades`（路径见 Country_creation 注释 `# See list in common/units/equipment/upgrades`）。
- 具体升级项名称，wiki 示例只给了 `ship_reliability_upgrade`、`sub_engine_upgrade`、`sub_stealth_upgrade`、`sub_torpedo_upgrade`（见第 7 节 OOB 变体）。完整的 upgrades 清单 `（wiki 未明确）`。

### 16.6 module_slots 与 module_count_limit

```
module_slots = {
	fixed_<slot name> = {
		required = <yes|no>
		allowed_module_categories = {
			# List of module category names
		}
	}
	<custom slot name> = {
		required = <yes|no>
		allowed_module_categories = {
			# List of module category names
		}
	}
	<slot name> = <earlier slot name>  # A later slot can inherit the exact same attributes from an earlier slot.
	<slot name> = inherit              # A slot can inherit the exact same attributes from the parent equipment type.
}
module_slots = inherit  # equipment will use same modules as parent
```

规则：

- `fixed_` 前缀的槽在装备设计器里会**归为一组**，用于单一用途/相关用途槽位；自定义槽**不能**以 `fixed_` 开头。
- 槽位可继承：`<slot> = <earlier slot>`，或 `= inherit` 从 parent 装备类型继承。
- 模块数量限制会自动被子类型继承；子类型的同条件限制会覆盖父级。

```
module_count_limit = {
	module = <module name>          # Match a specific module.
	category = <module category name>  # Match any module belonging to a category.
	module = any                     # Match any module.
	category = any                   # Match any module.
	module = empty                   # Match an empty module slot.

	count < <number>   # upper limit
	count > <number>   # lower limit
	count = <number>   # exact
	count = any        # allow any number（用于覆盖父级继承来的限制）

	title = <text or localization key>  # Optional override of the limitation title used in tool tips.
}
```

匹配语义：一个模块/槽位**只需满足任一**匹配条件即计入该限制。

### 16.7 装备设计器界面命名

设计器界面文件在 `interface/equipmentdesigner/tanks`、`.../ships`、`.../planes`；文件名不重要（原文 "The name of the file doesn't mater"），靠 `containerWindowType` 名字关联：

```
equipment_designer_<EQUIPMENT_TYPE>_<COUNTRY_TAG>
equipment_designer_<EQUIPMENT_ARCHETYPE>_<COUNTRY_TAG>
equipment_designer_<EQUIPMENT_TYPE>
equipment_designer_<EQUIPMENT_ARCHETYPE>
```

设计器窗口内必须有名为 `module_slots` 的内层容器；每个可用槽位在其中各有一个同名容器；槽容器内再列各可装模块的容器（放 `iconType` 等）。

`interface_design` 这个字段名在 wiki 全部已抓页面里**都没有出现** `（wiki 未明确）`。与设计器相关的真实字段是 `module_slots` / `module_count_limit` / `is_frame`，界面关联靠上面的 `containerWindowType` 命名约定。

`instant = yes` 也**不在装备定义里**，它属于 idea 的 `equipment_bonus`（见 `work/tmp/wiki/Idea_modding.wiki` 第 77 行原文）：

> `equipment_bonus = { ... }` … By default, the bonus is not granted immediately, but rather requiring to research a new tech first, which is how it's done within designer ideas. This can be prevented by adding `instant = yes` inside of the equipment archetype within the equipment bonus.

即：`instant = yes` 写在 **idea 的 equipment_bonus 内部**，作用于 archetype，表示修正立即生效而不是等下一代科技。不要把 `instant = yes` 写进 `common/units/equipment/*.txt`。

### 16.8 由模块派生新装备类型（variants）

```
<equipment_archetype>_my_variant = {
	archetype = <equipment_archetype>
	type = { innitial_type anti_air }   # 原文拼写就是 innitial_type
	for_each = {
		variant_name = { find_and_replace = { "chassis" "equipment" } }
			# optional；把本应作为本地化键的类型名做 find-and-replace
			# 例：light_tank_aa_chassis_1 → variant_name light_tank_aa_equipment_1
		hardness = { set = 0.5 }   # additional stats new type of equipment would get
	}
}
```

- 新类型必须出现在 `script_enums`，且至少要有一个 battalion 使用它（原文 "this type should be present in script_enums and must have at least one battalion using it"）。
- 复制 archetype 并派生 5 个变体时，**全部**都要写进 scripted_enums（`<archetype>_my_variant`、`..._variant_0`、`..._variant_1` …）。

### 16.9 1936 / 1940 变体示例（结构按 wiki，数值为占位）

wiki 没给带完整数值的 1936/1940 成对示例，只有上面的结构与字段语义。按结构写出的最小可读模板（`[..]` 为占位，需按目标 mod 平衡填）：

```
equipments = {
	# ---- archetype：定义公共属性，不直接生产 ----
	infantry_equipment = {
		is_archetype = yes
		is_buildable = no
		year = 1936
		type = infantry
		group_by = archetype
		interface_category = interface_category_land
		picture = GFX_infantry_equipment
		priority = 1
		resources = { steel = 1 }
		upgrades = { infantry_weapons_upgrade infantry_reliability_upgrade }
		build_cost_ic = [1.0]
		reliability = [0.9]
		maximum_speed = 4
		defense = [3]
		breakthrough = [2]
		hardness = 0
		armor_value = 0
		soft_attack = [6]
		hard_attack = [1]
		ap_attack = [2]
		air_attack = 0
	}

	# ---- 1936 型号：继承 archetype ----
	infantry_equipment_0 = {
		archetype = infantry_equipment
		year = 1936
		active = yes
		visual_level = 0
		build_cost_ic = [0.5]
		soft_attack = [6]
	}

	# ---- 1940 型号：parent 指向上一代，形成升级链 ----
	infantry_equipment_1 = {
		archetype = infantry_equipment
		parent = infantry_equipment_0
		year = 1940
		priority = 2
		visual_level = 1
		build_cost_ic = [0.6]
		soft_attack = [9]
		hard_attack = [2]
		ap_attack = [4]
	}
}
```

升级链读法：`archetype` 决定这一类的底子与设计器/升级体系；`parent` 决定它取代谁（决定旧型号退役判定）；`year` 决定最早出现年份（与科技 `start_year` 配合）；`priority` 决定自动配装偏好；`is_buildable = no` 只出现在 archetype 上。坦克/舰船/飞机另加 `module_slots`（或 `module_slots = inherit`），且必须有匹配的 `equipment_designer_*` 界面容器。

### 16.10 装备可用修正（modifier）清单

通用：`lend_lease_cost`（运输船占用）、`build_cost_ic`（生产成本）、`manpower`（生产人力成本）、`can_license`（可授权生产）、`is_convertable`（可改装）。

陆军：`reliability`（故障率）、`maximum_speed`（**绝对值 km/h，默认 4**，不写即 4）、`soft_attack`、`hard_attack`、`air_attack`、`ap_attack`（穿甲）、`breakthrough`、`defense`、`max_strength`（HP）、`armor_value`、`hardness`、`entrenchment`、`recon`。

海军（注意 OBSOLETE 项）：

```
naval_speed = 28            # 影响战斗速度与 evasion
fire_range = 32             # (OBSOLETE)
lg_armor_piercing = 12
lg_attack = 18              # 对 screen 更有效
hg_armor_piercing = 25
hg_attack = 12              # 对 capital/carrier 更有效
torpedo_attack = 1
anti_air_attack = 5
shore_bombardment = 8       # (OBSOLETE, 由 lg_attack/hg_attack 决定)
evasion = 15                # (OBSOLETE, 由 naval_speed 提供)
surface_detection = 12
sub_attack = 10
sub_detection = 5
surface_visibility = 25     # 越低越好
sub_visibility = 20         # 越低越好
naval_range = 3000
port_capacity_usage = 1
search_and_destroy_coordination = 0.1
convoy_raiding_coordination = 0.1
```

空军：

```
air_attack = 50
air_defence = 50
air_range = 500
air_agility = 10
air_ground_attack = 100
air_bombing = 300
air_superiority = 1
naval_strike_attack = 1.5
naval_strike_targetting = 0.5
carrier_size = 0.05
default_carrier_composition_weight = 1
carrier_capable = yes
```

### 16.11 装备本地化

```
<equipment>: ""
<equipment>_desc: ""
<equipment>_short: ""
```

国家专用前缀：

```
<tag>_<equipment>: ""
<tag>_<equipment>_desc: ""
<tag>_<equipment>_short: ""
```

注意：如果科技没写自己的名字，会借用其解锁的装备名字（见 4.9）。所以装备本地化缺失会连带科技显示空白/ID。

### 飞机设计器与机体（Aircraft designer）

#### 页面归属

- `Aircraft_designer`（pageid 9690，1.15 + BBA）：**游戏内容页**，全是机体/模块数值表。
  它在 References 里给的是路径，不是字段：`common/units/equipment/modules`、
  `plane_designer_l_english.yml`、`designer_l_english.yml`、`modifiers_l_english.yml`。
- 机体与模块的**脚本字段**在 `Equipment modding`（pageid 3940）的 `Equipment` / `Equipment Designer` 两节。

#### 机体（airframe）= equipment archetype

```
equipments = {
    <equipment> = {
        year = <int>                 # 早于该年份不可出现，可选
        picture = <name>             # 租借界面用的 GFX
        priority = <value>
        archetype = <name>           # 与 is_archetype = yes 互斥
        parent = <name>              # 上一代装备，不能是 archetype
        can_be_produced = { <triggers> }      # 可选
        can_be_lend_leased = { <triggers> }
        is_archetype = yes
        is_buildable = no
        active = yes                 # 不需要科技解锁即可用
        type = <type>                # 内部类型，决定谁能用
        is_frame = <yes|no>          # 模块化装备默认 yes；指坦克底盘、舰体、飞机机体
        group_by = <group>           # 生产界面分组方式（archetype / type）
        interface_category = <type>   # 生产界面分类
        max_military_factories = <n> / max_dockyard_factories = <n>
        module_slots = { ... }
        module_count_limit = { ... }
        resources = { <resource> = <amount> }
        upgrades = { ... }            # 给非设计器装备用的升级项
        <unit stat name> = <value>
        manpower = <value>            # 仅海军，造一件要多少人力
    }
}
```

Air 的 `type` 取值（Internal Types → Air）：`air_transport`、`cas`、`fighter`、`interceptor`、
`tactical_bomber`、`missile`、`naval_bomber`、`strat_bomber`、`suicide`。
`interface_category` 里对应 `interface_category_air`。

#### 模块槽（module_slots）

```
module_slots = {
    fixed_<slot name> = {          # fixed_ 前缀的槽在设计器里归类显示
        required = <yes|no>
        allowed_module_categories = {
            <module category names>
        }
    }
    <custom slot name> = {         # 不能以 fixed_ 开头
        required = <yes|no>
        allowed_module_categories = { ... }
    }
    <slot name> = <earlier slot name>   # 继承另一个槽的全部属性
    <slot name> = inherit                # 继承父装备的同名槽
}
module_slots = inherit                   # 整块沿用父装备
```

装到槽里的模块写在实例化处，如 `Country_creation` 的 OOB 示例：`fixed_ship_engine_slot = sub_ship_engine_1`
（注释原文：modules themselves are defined in `common/units/equipment/modules`）。

#### 模块数量限制（module_count_limit）

```
module_count_limit = {
    module = <module name>       # 精确模块
    category = <category name>   # 某类别任意模块
    module = any                 # 任意模块
    category = any               # 任意类别
    module = empty               # 空槽
    count <  <number>
    count >  <number>
    count =  <number>
    count =  any                 # 解除父类型继承来的限制
    title = <text 或本地化键>    # 可选，覆盖提示标题
}
```

匹配条件之间是「满足其一即生效」；子装备的任意限制只要匹配条件完全相同，就覆盖父装备的限制。

#### 模块本身

模块定义在 `common/units/equipment/modules/*.txt`（`Aircraft_designer` References 与 `Modifiers` 页 2518 行
均只给这一句）。wiki **没有**给出模块块的字段表，此处不编。
已知的关联点：

- 科技解锁模块用 `enable_equipment_modules = { <module> ... }`（`Technology_modding` 页，空白分隔）；
- 模块的设计经验消耗可由 `module_<module type>_design_cost_factor` 改（`Modifiers` 页）；
- 机体整体的设计经验消耗由 `<equipment archetype>_design_cost_factor` 改，例：
  `strat_bomber_equipment_design_cost_factor = 0.3`、`ship_hull_heavy_design_cost_factor = -0.2`。

#### 设计器界面（interface/equipmentdesigner/planes）

原文要点：

- 界面文件在 `interface/equipmentdesigner/<type>`，type 是 `tanks` / `ships` / `planes`；文件名随意，靠命名挂接。
- 挂接靠 `containerWindowType` 的 4 种命名：
  `equipment_designer_` + `EQUIPMENT_TYPE` + `_` + `COUNTRY_TAG`（指定国家的指定装备）、
  `equipment_designer_` + `EQUIPMENT_ARCHETYPE` + `_` + `COUNTRY_TAG`、
  `equipment_designer_` + `EQUIPMENT_TYPE`、
  `equipment_designer_` + `EQUIPMENT_ARCHETYPE`。
- 窗口内层必须有一个叫 `module_slots` 的容器；每个槽一个同名子容器（名字必须与 `module_slots` 里的槽名一致）；
  槽容器里再列可装该槽的模块容器，容器内放 `iconType` 等元素。
- 用了模块的装备**必须**有设计器窗口，否则退回旧的 upgrade 系统。

#### equipment_bonus 的对应关系

`equipment_bonus = { ... }` 写在 idea / 国家精神 / 角色特质里（`Character modding` 630 行、`Idea_modding` 77 行），
指向装备 archetype 或装备类型：

- 括号里的键 = `common/units/equipment/*.txt` 里的 archetype 名；
- 或用 `type = { ... }` / `type = <archetype_type>` 指定类型集合（如 `artillery` 覆盖火炮、火箭炮、坦克炮）；
- **默认不立即生效**，要研究一项新科技才应用；在 archetype 块内加 `instant = yes` 才会立刻生效
  （设计器类 idea 原版就是这么写的）；
- `equipment_bonus` 不能用在 dynamic modifier 里（`Modifiers` 页第 57 行）。

#### 机体与模块的数值骨架（`Aircraft_designer` 页）

机体表列：Agility、Air Defense、Naval Attack、Naval Targeting、Air Superiority、Speed (km/h)、Range (km)、
Weight、Modules（如 `2/3`、`4/6`、`5/7` = 固定槽/自定义槽数量）、Service Manpower、Fuel Usage、
Production Cost、Resource Use per Factory、Prerequisites。所有机体默认 Reliability 80%（另有标注除外）。

Small 机体（6 种普通 + 5 种舰载）：Inter-war 35 机动 / 400 km/h / 400 km / 权重 3 / 2-3 槽 / 20 人力 / 0.05 燃料 / 成本 4；
到 Supersonic（GD，需 Supersonic Jet）65 机动、900 km/h、1400 km、5-5 槽、成本 14、4 铝 1 橡胶 5 铬。
Medium（5 种）：25→45 机动、200→500 km/h、750→1500 km、4-6 槽、40 人力、成本 6→14。
Large（5 种）：20→40 机动、200→400 km/h、1000→3600 km、4-7 槽、80 人力、0.16 燃料、成本 16→23。
Other（不能用设计器）：运输机 3 代、Intercontinental Bomber、Mothership Aircraft。

模块大类与关键列：

| 类别 | 列 | 备注 |
|---|---|---|
| Engine | Eligible Frames、Range、Agility、Max Speed、Thrust、Fuel Usage、Production Cost、Resource Use per Factory | 换引擎 6 空军经验；不换引擎数只升一级只花 3 |
| Fighter Weapons | Air Attack、Agility、Ground Attack、Weight、Production Cost、Design Cost、Allows Mission | 主武器决定机型分类（Fighter / Heavy Fighter） |
| CAS Weapons | 同类列 | 决定 CAS 分类 |
| Naval Bomber Weapons | Agility、Air Defense、Naval Attack、Naval Targeting、Weight、Cost、Design Cost、Allows Mission | 带任一此类武器会关掉其它武器对 Naval Strike / Port Strike 的条件效果 |
| Tactical / Strategic Bomber Weapons | …、Strategic Bombing、Naval Attack、Weight | 决定 Tactical / Strategic Bomber 分类 |
| Recon Equipment | Weight、Cost、Design Cost、Allows Mission | LAR，决定 Scout 分类 |
| Secondary Weapons | Minelaying、Weight、Cost | 不能当主武器，不影响分类 |
| Auxiliary → Special / Unique special / Naval / Electronics / Defense turrets | 各自列 | Special 可叠多个；Unique special、Naval、Electronics 每型限 1；Defense turrets 数量由机体决定 |

主武器决定机型：Small 机体按最左武器槽可出 Fighter / CAS / Naval Bomber；Medium 出 Heavy Fighter / Tactical Bomber / Scout；
Large 出 Strategic Bomber / Naval Patrol Bomber。

#### 常见错误

1. **给带模块的装备漏设计器窗口**：直接退回 upgrade 系统，设计器不出现。
2. **`module_slots` 里的槽名与界面里 `module_slots` 容器下的子容器名不一致**：界面空槽或错位。
3. **自定义槽用了 `fixed_` 前缀**，或该用 `fixed_` 的固定槽没加前缀：归类错乱。
4. **新变体没登记 `script_enums`**：`<archetype>_my_variant`、`_0`、`_1`… 全都要写进去，少一个就报错。
5. **想让 `equipment_bonus` 立刻生效却漏 `instant = yes`**：要等下一项相关科技。
6. **想用 `equipment_bonus` 改设计器加成却写进 dynamic modifier**：不支持。
7. **`interface_category` 与 `type` 混用**：前者决定生产界面分类（`interface_category_air`），后者决定谁能装备（`fighter` 等）。

---

## 第 17 章 单位定义与编制

### 单位定义（sub_units）

来源：https://hoi4.paradoxwikis.com/index.php?title=Unit_modding&action=raw

单位文件在 `common/units/*.txt`，顶层容器 `sub_units = { ... }`。单位是"硬编码单位类型的子单位"（原文：Internally, units are actually sub-units of the hardcoded unit types, such as infantry, cavalry, fighter, etc.）。

### 17.1 完整结构

```
sub_units = {
    <unit name> = {
        sprite = <entity>              # 指向 gfx/entities/*.asset 的 <name>_entity
        map_icon_category = <type>
        priority = <int>               # 多个同类型 subunit 时用哪个图标
        ai_priority = <int>
        active = yes / no              # 是否无需科技解锁即可用
        cavalry = yes
        special_forces = yes
        marines = yes
        can_exfiltrate_from_coast = yes # 可无海军基地直接离岸
        mountaineers = yes
        can_be_parachuted = yes
        affects_speed = yes            # 是否拖慢模板速度；支援连 set to no
        transport = <equipment>        # 由装备决定速度；motorized/mechanized 用
        group = <group>                # 师级分组（决定 Support 页签）
        type = { <type> }
        categories = { <categories> }
        essential = { <equipment> }    # active = no 时必需装备
        need = { <equipment> }         # 生产所需装备，缺则不可用
        <modifiers>
        <terrain> = { <modifiers> }    # 仅特定地形生效
    }
}
```

### 17.2 字段语义表

| 字段 | 取值 | 作用 |
|---|---|---|
| `sprite` | entity 名 | 地图上显示的模型；默认取 `<sprite>_entity` |
| `map_icon_category` | `infantry` / `armored` / `other` / `ship` / `transport` / `uboat` | 地图图标类别，**不能新增** |
| `priority` | int | 同类型 subunit 并存时用哪个图标 |
| `ai_priority` | int | AI 选择偏好 |
| `active` | `yes`/`no` | `no` 时需科技 `enable_subunits` 解锁 |
| `cavalry` | `yes` | 骑兵判定（影响战术/加成） |
| `special_forces` | `yes` | 特种部队判定（受特种部队上限约束） |
| `marines` | `yes` | 陆战队判定 |
| `can_exfiltrate_from_coast` | `yes` | 无海军基地也能离岸 |
| `mountaineers` | `yes` | 山地兵判定 |
| `can_be_parachuted` | `yes` | 可空降 |
| `affects_speed` | `yes`/`no` | 是否拖慢模板速度；支援连 `no` |
| `transport` | equipment 名 | 用装备速度决定单位速度（摩托化/机械化） |
| `group` | `infantry`/`support`/`mobile`/`armor`/自定义 | 师设计器页签分组；空海军不用 |
| `type` | 内部类型（见 3.3） | 硬编码单位类型 |
| `categories` | 类别名 | 科技按类别批量加成 |
| `essential` | equipment 列表 | `active = no` 时的必需装备 |
| `need` | equipment 列表 | 生产所需装备；缺则不可用（manpower/equipment 双约束） |

`group` 的值**可以新增**（内部类型与地图图标类型不能新增）。新增 group 的三步：

1. 在任一单位文件里写 `group = <group name>`；
2. 本地化 `localisation/unit_I_english.yml` 加 `group_<group name>_title:0 "Group name here"`；
3. `interface/subuniticons.gfx` 加 sprite：

```
spriteType = { name = "GFX_group_<group name>_icon"  textureFile = "gfx/interface/counters/divisions_large/<icon file name>.dds" noOfFrames = 2 }
```

### 17.3 内部类型（type）

`infantry`、`support`、`artillery`、`anti_tank`、`anti_air`、`armor`、`fighter`、`cas`、`naval_bomber`、`interceptor`、`suicide`、`tactical_bomber`、`strategic_bomber`、`air_transport`、`missile`、`submarine`、`screen_ship`、`capital_ship`、`carrier`、`motorized`、`mechanized`、`flame`、`amphibious`

### 17.4 group 合法值

`infantry`、`support`、`mobile`、`armor`（另可自定义，见 3.2）

### 17.5 地图图标类型

`infantry`、`armored`、`other`、`ship`、`transport`、`uboat`

### 17.6 单位属性（modifier）

陆军几乎总用这几项：

```
manpower = <int>
max_strength = <int>
training_time = <int>
weight = <float>
default_morale = <float>
max_organisation = <int>
combat_width = <int>
supply_consumption = <float>
```

vanilla 参考值（原文）：`max_organisation` = infantry support 20 / armor 10 / armor support 0 / ship 40 / cavalry 70；`combat_width` = infantry 0 / artillery 0 / armor support 1 / armor 2。

其余可用修正与装备同一套，按组记：Base（`max_organisation`、`reliability`、`weight`、`maximum_speed`、`supply_consumption`、`default_morale`、`combat_width`）、Costs（`lend_lease_cost`、`build_cost_ic`、`manpower`、`training_time`）、Offensive（`attack`、`soft_attack`、`hard_attack`、`air_attack`、`ap_attack`、`breakthrough`）、Defensive（`defense`、`max_strength`、`armor_value`、`hardness`、`entrenchment`）、Unique（`movement`、`experience_loss_factor`、`casualty_trickleback`、`suppression_factor`、`reliability_factor`、`recon`、`initiative`）、Boolean（`can_be_parachuted`、`can_license`、`is_convertable`、`carrier_capable`）、Navy 与 Air 见 2.10。

`maximum_speed` 在**单位**上是乘算 bonus：`<base speed> * (1 + maximum_speed)`。写 0.5 = 快 50%，写 2 = 快 200%。装备上的同名项是绝对速度（默认 4）。两者语义不同，混用是最常见的一类数值错误。

### 17.7 单位本地化与图标

```
<unit>: ""
<unit>_desc: ""
```

新单位在师设计器里出现"随机图标"（防空炮弹图标之类）的原因是单位没有图标。修法：在 `interface/subuniticons.gfx` 里为该单位加三个 spriteType：

```
spriteTypes = {
   spriteType = {
     name = "GFX_unit_<your unit name>_icon_medium"
     textureFile = "gfx/interface/counters/divisions_large/<your unit name>_icon.dds"
     noOfFrames = 2
   }
   spriteType = {
     name = "GFX_unit_<your unit name>_icon_medium_white"   # 不能省 medium
     textureFile = "gfx/interface/counters/divisions_small/onmap_unit_<your unit name>_icon.dds"
     noOfFrames = 2
   }
   spriteType = {
     name = "GFX_unit_<your unit name>_icon_small"
     texturefile = "gfx/texticons/unit_<your unit name>_icon_small.dds"
     legacy_lazy_load = no
     noOfFrames = 2
   }
}
```

### 17.8 模型（entity）优先级链

`sprite = SPRITE` 默认对应 entity `<SPRITE>_entity`。可按前缀覆盖，优先级从低到高：默认名 → graphical culture → 国家 → cosmetic tag。

```
entity = {
	name = SPRITE_entity
	pdxmesh = example_mesh
	default_state = idle
	state = { name = attack  animation = attack  animation_blend_time = 0.0 animation_speed = 1.0 }
	state = { name = defend  animation = defend  animation_blend_time = 0.3 animation_speed = 1.0 }
	state = { name = support_attack animation = support_attack animation_blend_time = 0.3 animation_speed = 1.0 }
	state = { name = move    animation = move    animation_blend_time = 1.0 animation_speed = 1.0 }
	state = { name = retreat animation = retreat animation_blend_time = 0.3 animation_speed = 1.0 }
	state = { name = death   animation = death   animation_blend_time = 0.3 animation_speed = 1.0 }
	state = { name = idle    animation = idle    animation_blend_time = 0.3 animation_speed = 1.0 }
	state = { name = training animation = training animation_blend_time = 0.3 animation_speed = 1.0 }
	scale = 0.8
}
entity = { name = middle_eastern_gfx_SPRITE_entity  clone = SPRITE_entity  pdxmesh = middle_eastern_example_mesh }
entity = { name = BHR_SPRITE_entity                 clone = SPRITE_entity  pdxmesh = BHR_example_mesh }
entity = { name = COSMETICTAG_SPRITE_ENTITY         clone = BHR_SPRITE_entity }
```

后三个分别演示按 graphical culture、按国家、按 cosmetic tag 覆盖。

### 17.9 单位类别（unit categories）

定义在 `common/unit_tags/00_categories.txt`。单位在 `categories = { ... }` 里引用；科技用类别做批量加成：

```
category_all_infantry = {
    hard_attack = 0.25
    ap_attack = 1
}
```

---

## 第 18 章 海空军与 OOB

### 海空军独立规则

wiki 上没有 `Naval_modding` / `Air_modding` 页面（404）。海空内容分布在三处：`Division_modding` 的 OOB 章节（脚本结构）、`Ship` 与 `Naval_missions`（船体与任务）、`Air_warfare` / `Air_missions`（联队与任务）。分两层写：可 modding 的脚本结构，和只能引用不能新增的硬编码任务与常量。

### 18.1 舰队 / task force / ship（MTG）

```
units = {
    fleet = {
        name = "Fleet De Custom"
        naval_base = 10980
        task_force = {
            name = "Fleet De Custom"
            location = 10980
            ship = {
                name = "NRB Minas Gerasis"
                pride_of_the_fleet = yes
                definition = battleship
                equipment = {
                    ship_hull_heavy_1 = {
                        amount = 1
                        owner = BRA
                        version_name = "Minas Geras Class"
                    }
                }
            }
        }
        task_force = {
            name = "Fleet De Submarine"
            location = 10980
            ship = {
                name = "NRB Humayta"
                definition = submarine
                equipment = {
                    ship_hull_submarine_2 = { amount = 1  owner = BRA  version_name = "Humayta Class" }
                }
            }
        }
    }
}
```

| 字段 | 说明 |
|---|---|
| `fleet` | 开始一个舰队，可含多个 `task_force` |
| `naval_base` | 母港 province id |
| `task_force` → `name` / `location` | task force 名与出生地 |
| `ship` → `name` | 舰名 |
| `pride_of_the_fleet` | 旗舰标记，同时只能一个，可选 |
| `definition` | `battleship` / `carrier` / `destroyer` / `battle_cruiser` / `heavy_cruiser` / `light_cruiser` / `submarine` |
| `equipment` | `amount` 保持 1；`owner` 造出并接收；`creator` owner 未解锁科技时指定制造方，可选；`version_name` 自定义舰级，可选 |

两条 wiki 明确警告：① owner / creator 必须已解锁对应科技，且 `version_name` 必须存在于其国家历史；② `owner` 可省，但同一船体有多个舰级时（如 `ship_hull_cruiser_2`）会忽略 `version_name`，改用该国历史里最后定义的舰级。

非 MTG 写法只差 equipment 段：`ship_hull_heavy_1` → 成品装备 `battleship_1`，`ship_hull_submarine_2` → `submarine_1`（船体+模块 → 整舰装备）。

### 18.2 船体 → 舰种

| Hull type | Ship type(s) |
|---|---|
| Destroyer hull | Destroyer |
| Cruiser hull / Torpedo Cruiser hull | Light cruiser / Heavy cruiser |
| Panzerschiff hull / Coastal Defense Ship hull | Large cruiser |
| Heavy ship hull | Battlecruiser / Battleship |
| Super Heavy Battleship hull | Super heavy battleship |
| Carrier hull | Carrier / Escort carrier |
| Converted cruiser carrier hull | Escort carrier |
| Submarine hull / Cruiser submarine hull | Submarine |
| Fleet submarine hull | Submarine / Ballistic missile submarine |
| Nuclear Submarine hull | Nuclear submarine / Nuclear ballistic missile submarine |

同一船体装不同模块得到不同舰种（巡洋舰船体：重炮 = 重巡，轻炮 = 轻巡）。这是"模块化装备改变舰种"的官方说明，也解释了 `definition` 与 `ship_hull_*` 不一致的写法。缩写：BB / BC / SHBB / CA / CB / CV / CVE / CL / DD / SS / SSN / SSB / SSBN。

### 18.3 海军任务（task force 级，硬编码）

任务在 task force 上指定，作战区域在 fleet 上指定（原文：missions can be assigned at the task force level, the operating area for the mission is defined at the fleet level）。

| 任务 | 关键规则 |
|---|---|
| Naval exercises | 最近港口相邻海域演习，每日得 navy experience；燃料 `NNavy.MISSION_FUEL_COSTS`（示例 8%）；有 accident 风险 |
| Patrol | 搜索敌舰；**一个 task force 只能巡逻一个 strategic region**；发现后 spotting，100% 才能交战 |
| Strike force | patrol 完全 spotting 后自动出击；**不必同 fleet**；平时留港省油；受 engagement rule 限制；可被动投射 naval supremacy |
| Convoy raiding | 每个 raiding TF 只能有效覆盖 **1.5** 个 strategic region |
| Convoy escort | 保护 convoy；escort efficiency 100% 时一支 TF 立即驰援，低于 100% 会迟到 |
| Minelaying | 战时；铺到 `NNavy.NAVAL_MINES_IN_REGION_MAX`/区域；区域越多单区速率越低 |
| Minesweeping | 需 `Minesweeping Gear`；驱逐舰可用 |
| Naval invasion support | 护送登陆船团，登陆后近岸 shore bombardment，战斗结束返港 |
| Hold | 普通点击回最近港口；按 `ctrl` 点击原地停留（不耗燃料，可封锁海域连接） |

Shore bombardment：每点 heavy gun damage 贡献 `NNavy.HEAVY_GUN_ATTACK_TO_SHORE_BOMBARDMENT`，每点 light gun damage 贡献 `NNavy.LIGHT_GUN_ATTACK_TO_SHORE_BOMBARDMENT`，总减免上限 `NNavy.SHORE_BOMBARDMENT_CAP`；可暴击，重创要塞与海岸要塞。

任务枚举在 wiki 里全部是 `{{rd|NNavy|...}}` 形式的 define 引用，**脚本里用的 mission id 常量没有列出** `（wiki 未明确）`，能确认的只有行为与 UI 名称。

### 18.4 空军：air wing（OOB 脚本）

```
air_wings = {
    500 = {
        fighter_equipment_0 = { owner = "BRA"  amount = 10 }
    }
}
```

键 `500` 是**州 id**（该州需有 air base），值块是机型 + `owner` + `amount`；`owner` 不必是写文件的国家。

编制规则：陆基 wing **100** 架，舰载为 `NAir.CARRIER_SIZE_STAT_INCREMENT`；同一 wing 必须同类型或可执行相同任务，**不能混战斗机与轰炸机**，可混同类型不同代；新建 wing 需 `NAir.AIR_DEPLOYMENT_DAYS` 天到位，期间可下任务但不执行；解散的飞机回库存；基地容量 = 每级 `NBuildings.AIRBASE_CAPACITY_MULT`，超编每 1% 触发 `-NAir.CAPACITY_PENALTY`，超到 `100/CAPACITY_PENALTY`% 时 -100%，完全不能起飞。

### 18.5 空军任务与可用机型（硬编码）

| 任务 | 可用机型 |
|---|---|
| Pilot exercises | 除 rocket interceptors、transport planes、scout planes 外全部；开启后禁用其它任务 |
| Air superiority / escort | Fighter、Heavy Fighter、Jet Fighter |
| Close air support | CAS、Tactical Bomber、Jet Tactical Bomber |
| Interception | Fighter、Heavy Fighter、Jet Fighter、Rocket Interceptor |
| Strategic bombing | Strategic Bomber、Jet Strategic Bomber、Tactical Bomber、Jet Tactical Bomber |
| Naval strike | Naval Bomber、CAS、Tactical Bomber、Jet Tactical Bomber |
| Kamikaze strike | Fighter（需国家规则解锁） |
| Port strike | Naval Bomber、CAS、Tactical Bomber、Jet Tactical Bomber |
| Logistics strike | CAS、Tactical Bomber、Jet Tactical Bomber（NSB） |
| Air supply | Transport plane |
| Naval minelaying | Naval Bomber、Tactical Bomber、Jet Tactical Bomber、Strategic Bomber、Jet Strategic Bomber |
| Naval minesweeping | Naval Bomber、Tactical Bomber、Jet Tactical Bomber |
| Air recon | Scout Planes（LAR） |
| Naval patrol | Naval Bomber（另有 Scout Plane 版） |

多任务优先序（从上往下第一个条件成立者执行）：`Pilot Exercises`（always）→ `Air Superiority`（always）→ `Close Air Support`（有陆战）→ `Interception`（侦测到敌轰炸机）→ `Strategic Bombing`（有未损毁建筑）→ `Naval Strike`（侦测到敌舰）→ `Kamikaze Strike`（同上）→ `Port Strike`（敌 TF 在港）→ `Logistics Strike`（敌单位从补给节点取补给）→ `Air Supply`（有非零补给的己方师）→ `Naval Minelaying`（always）→ `Naval Minesweeping`（always）→ `Air Recon`（always）。

前两条 always，多勾任务时后面的不会执行；要并行就拆成多个小 wing 各管一个任务。

### 18.6 制空权重

| 机型 | Superiority Power |
|---|---|
| Heavy Fighter | 1.25 |
| Fighter / Carrier Fighter / Jet Fighter / CAS / Carrier CAS / NAV / Carrier NAV / TAC / Jet TAC | 1.00 |
| Strategic Bomber / Jet Strategic Bomber | 0.01 |

单 wing air power = 飞机数 × 上表权重 × mission efficiency。

### OOB 文件写法

来源：`Division_modding` + `Country_creation`（OOB 章节）。文件在 `history/units/*.txt`，文件名任意，但必须与加载处写的名字一致（省略 `.txt`）。

### 18.7 加载方式（国家历史里）

| 写法 | 类型 | 说明 |
|---|---|---|
| `oob = "SCO_1936"` | history **参数** | 不能放进 `if` 等 effect 块 |
| `set_oob = "SCO_1936"` | effect | 等价，可用于 `if`（按 DLC 分支时必须用它） |
| `set_naval_oob` / `set_air_oob` | effect | 海/空军 OOB，覆盖同类型先前定义 |
| `load_oob = "..."` | effect | **不推荐在 history 用**；立即加载，可能因科技未就绪报错、含师时崩溃；适合追加或复用模板 |

海军 MTG、空军 BBA 必须分文件（两套系统互不兼容）：

```
if = { limit = { has_dlc = "Man the Guns" }          set_naval_oob = "SCO_1936_naval_mtg" }
if = { limit = { NOT = { has_dlc = "Man the Guns" } } set_naval_oob = "SCO_1936_naval_legacy" }
if = { limit = { has_dlc = "By Blood Alone" }        set_air_oob = "SCO_1936_air_bba" }
if = { limit = { NOT = { has_dlc = "By Blood Alone" } } set_air_oob = "SCO_1936_air_legacy" }
```

陆军涉及坦克装备引用时也拆分：

```
if = {
    limit = { has_dlc = "No Step Back" }
    set_oob = "TAG_1936_nsb"
    else = { set_oob = "TAG_1936_legacy" }
}
```

### 18.8 师模板

```
division_template = {
    name = "Blueskirt Division"
    regiments = {
        infantry = { x = 0 y = 0 }
        infantry = { x = 0 y = 1 }
        artillery_brigade = { x = 1 y = 0 }
        artillery_brigade = { x = 1 y = 1 }
    }
    support = {
        artillery = { x = 0 y = 0 }
    }
}
```

`regiments` = 战斗营，`support` = 支援连；坐标笛卡尔，`(0,0)` 左上，x 左→右，y 上→下；支援连的单位必须 `group = support`，战斗营必须是别的 group，**同一 y 列 group 不能变**；默认上限 `NMilitary.MAX_DIVISION_BRIGADE_WIDTH` × `MAX_DIVISION_BRIGADE_HEIGHT` 与 `MAX_DIVISION_SUPPORT_WIDTH` × `MAX_DIVISION_SUPPORT_HEIGHT`，索引从 0 起。可选：`division_names_group`、`is_locked`、`force_allow_recruiting`、`division_cap`、`priority`（0 预备 / 1 默认 / 2 精锐）、`template_counter`（用 `GFX_div_templ_<n>_large` / `_small`）、`override_model`。

### 18.9 师布置

```
units = {
    division= {
        name = "1st Blueskirt Division"
        location = 9392                       # province id
        division_template = "Blueskirt Division"
        start_experience_factor = 0.2
        start_equipment_factor = 0.3
    }
    division= {
        division_name = { is_name_ordered = yes  name_order = 35 }
        location = 6488
        division_template = "Infanterie-Division"
        force_equipment_variants = { infantry_equipment_0 = { owner = "SCO" } }
        officer = {
            name = SCO_officer_1
            portraits = { army = { large = GFX_SCO_officer_1  small = GFX_SCO_officer_generic_small } }
        }
    }
}
```

命名二选一：`name = "..."`；或 `division_name = { is_name_ordered = yes  name_order = 35 }`（`is_name_ordered` 必填；`name_order` 命中名字组 `ordered = { ... }` 用该条目，否则用 `fallback_name`）。必填 `location`（province id）与 `division_template`。可选 `start_experience_factor`（0–1，默认 0）、`start_equipment_factor`（默认 1，**不从库存扣**）、`start_manpower_factor`（默认从库存扣到上限）、`force_equipment_variants`、`officer`。`force_equipment_variants` 每项可含 `owner`（应等于获得 OOB 的国家）、`creator`（决定变体，默认同 owner）、`amount`、`version_name`（该装备类型必须带变体时必填，如 NSB 坦克）。

### 18.10 起始装备生产

```
instant_effect = {
    add_equipment_production = {
        equipment = { type = infantry_equipment_0  creator = "ARG" }
        requested_factories = 1
        progress = 0.19
        efficiency = 100
    }
}
```

`equipment`：`creator` + `type`（须由 creator 已研究科技解锁）+ `version_name`（MTG 船 / BBA 飞机必填）；`requested_factories` 军工厂/船坞数，不足进队列；`progress` 单件完成度；`efficiency` 0–100 初始生产效率。

### 18.11 OOB 里放什么

起始装备生产可放 OOB 的 `instant_effect`，装备变体习惯放国家历史；OOB 的 `instant_effect` 本身就是 effect 块，两边可互换。OOB 可记录"当前正在做的国策"，**已完成**的国策必须写进国家历史。没有 OOB 的国家会出现"建筑坏了"：通过 effect 建造的建筑不会立即归属，直到消费品比例变化或读档。

### 18.12 装备变体（create_equipment_variant，通常放国家历史）

```
# MTG：模块制
create_equipment_variant = {
    name = "Celtic Series"
    type = ship_hull_submarine_1
    name_group = SCO_SS_HISTORICAL
    modules = {
        fixed_ship_torpedo_slot = ship_torpedo_sub_1
        fixed_ship_engine_slot = sub_ship_engine_1
        rear_1_custom_slot = empty
    }
    obsolete = yes
}

# 非 MTG：升级项制
create_equipment_variant = {
    name = "Celtic Series"
    type = submarine_1
    upgrades = {
        ship_reliability_upgrade = 1
        sub_engine_upgrade = 1
        sub_stealth_upgrade = 1
        sub_torpedo_upgrade = 1
    }
    obsolete = yes
}
```

`name_group` 在 `common/units/names_ships/`；模块槽位名由装备定义（`common/units/equipment`）给出，模块本身在 `common/units/equipment/modules`；升级项在 `common/units/equipment/upgrades`。

---

## 第 19 章 国家创建

### 国家创建（Country creation）

官方 checklist（wiki "Quick checklist"）依次是 9 步，对应下面 1.1–1.9。

### 19.1 最小文件集合

| # | 文件 | 必需 | 作用 |
|---|---|---|---|
| 1 | `common/country_tags/*.txt` | 是 | 声明 3 字符 tag 指向 country 文件 |
| 2 | `common/countries/NAME.txt` | 是 | graphical culture + 默认颜色 |
| 3 | `common/characters/*.txt` | 领袖必需 | 国家领袖（可含顾问、将领） |
| 4 | `history/countries/TAG - name.txt` | 是 | 开局历史（effect block） |
| 5 | `history/units/NAME.txt` | 有军队必需 | OOB；**缺了建筑不会被正确分配** |
| 6 | `localisation/english/*_l_english.yml` | 是 | 国名，UTF-8-BOM |
| 7 | `gfx/flags/` 三张 TGA | 是 | 大/中/小旗，每意识形态一套 |
| 8 | `history/states/*.txt` | 想上地图则必需 | 给州设 owner |
| 9 | `common/names/*.txt`、`portraits/*.txt` | 可选 | 随机人名、随机头像池 |

### 19.2 tag：`common/country_tags/*.txt`

```
SCO = "countries/Scotland.txt"
```

`countries/Scotland.txt` 指向 `common/countries/` 下的文件；**多个国家可共用同一 country 文件**。文件内写 `dynamic_tags = yes` 可把该文件后续所有国家标成 dynamic country（内战自动分支用）；**dynamic tag 数量不足会崩**，日志最后读取文件显示 `map/cities.txt` 或存档。

禁用作 tag：`NOT`（flow control）、`AND`（flow control）、`TAG`（`tag` 条件）、`OOB`（历史参数名）、`LOG`（effect/trigger）、`NUM`（数组计数，破坏抵抗系统）、`RED`（自定义地图模式红色通道恒 0）、纯数字（与 state ID 混淆；游戏禁止 tag 以数字开头，`D01` 可用）。

### 19.3 country 文件：`common/countries/NAME.txt`

```
graphical_culture = commonwealth_gfx
graphical_culture_2d = commonwealth_2d
color = rgb { 2  10  222 }
```

`graphical_culture` 是单位贴图集，`graphical_culture_2d` 是王牌与通用顾问头像集（可选值见 `common/graphicalculturetype.txt`）。`color` 必须带 `rgb` 或 `hsv`：RGB 可 0–255 或 0–1，HSV 三项 0–1。读入后 HSV 的 saturation/value 分别乘 0.6 / 0.8（`NDefines.NGraphics.COUNTRY_COLOR_SATURATION_MODIFIER = 0.6`、`COUNTRY_COLOR_BRIGHTNESS_MODIFIER = 0.8`），想得到纯红可写 `color = hsv { 0 1.66 1.25 }`。控制台 `tag_color` 不加这两个修正。

`common/countries/colors.txt`（**文件名必须叫 colors.txt**，会覆盖原版）：

```
SCO = {
    color = rgb { 2  10  222 }
    color_ui = rgb { 255 255 155 }
}
```

`color` 覆盖政治地图色；`color_ui` 用于 ctrl+F10 出图、`tools/history_viewer/`、师计数器背景。未写 `color_ui` 默认灰。

### 19.4 国家历史：`history/countries/TAG - name.txt`

文件名**前三个字母必须是 tag**（不分大小写），其后任意（`SCO - Bahrain.txt` 也能被 SCO 加载）。一个国家可有多个历史文件，都会被读。文件本身是 effect block，绝大多数 effect 可用；**执行顺序按 country_tags 里的国家顺序**；**任何多余右括号会让文件提前终止**。

```
capital = 121
set_research_slots = 3
set_stability = 0.7
set_war_support = 0.5

add_ideas = {
    henschel
    war_economy
    extensive_conscription
}

set_technology = {
    infantry_weapons = 1
    gw_artillery = 1
    interwar_antiair = 1
    fuel_silos = 1
    basic_train = 1
}

recruit_character = SCO_ronald_mcdonald
```

| 字段 | 说明 |
|---|---|
| `capital = 121` | **state ID 不是 province ID**；州内 VP 最高省当首都，并列取最小 province ID |
| `set_research_slots` | 未写默认 2 |
| `add_ideas` | national spirit / 设计公司 / 法案；未指定法案时默认 volunteer only + export focus + civilian economy |
| `set_technology` | 科技 ID 见 `common/technologies/`；DLC 科技要包在 `if = { limit = { has_dlc = "..." } }` |
| `recruit_character` | 必须在 `set_politics` 之前；同党派多领袖时先招募者上位；**不能是文件最后一行**（后面至少还要一行，空行也算） |

OOB 加载：

```
oob = "SCO_1936"                 # 参数不是 effect，不能放进 if
set_oob = "SCO_1936"             # effect，可放进 if
set_naval_oob = "SCO_1936_naval_mtg"
set_air_oob = "SCO_1936_air_bba"
load_oob = "my_template_shared"  # effect，立即加载；history 里不推荐（顺序/崩溃风险）
```

指向 `history/units/文件名.txt`，**省略 .txt**；文件名任意，只要与历史里写的一致。海军（MtG）与空军（BBA）要按 DLC 分两套：

```
if = {
    limit = { has_dlc = "Man the Guns" }
    set_naval_oob = "SCO_1936_naval_mtg"
}
if = {
    limit = { NOT = { has_dlc = "Man the Guns" } }
    set_naval_oob = "SCO_1936_naval_legacy"
}
```

history 里 `else` 只能用嵌套形式。

外交：

```
ENG = {
    if = {
        limit = { has_dlc = "Together for Victory" }
        set_autonomy = { target = SCO autonomous_state = autonomy_integrated_puppet }
    }
    else = { puppet = SCO }
}
create_faction = localisation_key
add_to_faction = IRE
add_to_tech_sharing_group = my_tech_group
```

附庸逻辑优先写在**附庸自己**的历史文件，否则宗主国后加载会重置附庸政治；`set_autonomy` 必须在设党派与支持度之前。自治等级见 `common/autonomous_states/*.txt`，科技共享组见 `common/technology_sharing/*.txt`。

政治：

```
set_popularities = { democratic = 80 communism = 10 fascism = 10 }
set_politics = {
    ruling_party = neutrality
    last_election = "1932.11.8"
    election_frequency = 48   # 单位：月
    elections_allowed = yes
}
```

`set_popularities` **合计必须正好 100**，否则整块不生效；未列出的意识形态按 0。

起始装备改型：

```
create_equipment_variant = {
    name = "Celtic Series"
    type = ship_hull_submarine_1
    name_group = SCO_SS_HISTORICAL
    modules = {
        fixed_ship_torpedo_slot = ship_torpedo_sub_1
        fixed_ship_engine_slot = sub_ship_engine_1
        rear_1_custom_slot = empty
    }
    obsolete = yes
}
```

无 MtG 时改用 `type = submarine_1` + `upgrades = { ship_reliability_upgrade = 1 ... }`。

日期块（多开局差异）：

```
1939.1.1 = {
    oob = "SCO_1939"
    set_technology = { atomic_research = 1 nuclear_reactor = 1 nukes = 1 }
}
```

格式 `YYYY.MM.DD = { ... }`，仅当开局日期**严格晚于**该日期才执行；日期块里的 `oob =` 是**替换**，`set_technology` 是追加。常用后续 effect：`unlock_national_focus`（跳过不给奖励）、`complete_national_focus`（完整完成给奖励）、`diplomatic_relation`（取消保障/军通）、`remove_ideas`、`promote_character = TAG_character_name`（角色须先招募且有 country_leader 角色）。

### 19.5 角色：`common/characters/*.txt`

```
characters = {
    SCO_ronald_mcdonald = {
        name = SCO_ronald_mcdonald
        portraits = {
            civilian = { large = GFX_SCO_ronald_mcdonald }
        }
        country_leader = {
            ideology = socialism
            traits = { scary_clown }
        }
    }
}
```

`ideology` 必须是 **ideology type**（社区称 sub-ideology），不能写 `democratic` 这类 group。头像走 spriteType，放 `interface/*.gfx`：

```
spriteTypes = {
    spriteType = {
        name = GFX_SCO_ronald_mcdonald
        texturefile = gfx/leaders/SCO/ronald_mcdonald.dds
    }
}
```

本地化：`SCO_ronald_mcdonald:0 "Ronald McDonald"`，描述用 `_desc`。只有被 `recruit_character` 招募才出现；`set_politics` 之后再招募的领袖不会立刻上台。军团长、元帅、海军将领、顾问在引擎里同样是 character。

### 19.6 旗帜：`gfx/flags` 命名与规格

- 每国至少 3 张：standard / medium / small。格式为**未压缩 32-bit ARGB TGA**；24-bit 能加载但报错并提示拖慢游戏；原点必须左下，否则图上下翻转。
- 命名两种：`SCO_neutrality.tga`（意识形态组专用，起始优先级最高）与 `SCO.tga`（通用兜底）。二者都可缺，但每国应有能覆盖其所有意识形态组的旗。

| 类型 | 尺寸 | 文件大小 |
|---|---|---|
| Standard | 82x52 px | 16.6 / 17.1 KiB |
| Medium | 41x26 px | 4.2 / 4.69 KiB |
| Small | 10x7 px | 324 / 819 bytes |

对应 `NDefines.NGraphics.COUNTRY_FLAG_TEX_WIDTH/HEIGHT` 等。**medium/small 要生效需要足够 dynamic country tag**：medium 约 10 个、small 约 20 个；不够时全部国家的中/小旗透明且 `logs/error.log` 无任何提示。分尺寸放 `gfx/flags` 子目录。

### 19.7 国名本地化

```yaml
l_english:
 SCO: "Scotland"
 SCO_DEF: "Scotland"
 SCO_ADJ: "Scottish"
 SCO_democratic: "Republic of Scotland"
 SCO_democratic_DEF: "the Republic of Scotland"
 SCO_democratic_ADJ: "Scottish"
```

key 格式 `TAG_ideology`。后缀语义：无后缀 = 地图与 `[TAG.GetName]`；`_ADJ` = `[TAG.GetAdjective]`；`_DEF` = `[TAG.GetNameDef]` 与地图上州 owner/controller 悬停，通用事件/决议大量使用，**基本必须定义**。

修饰型国名（可叠加，顺序必须是 country-ideology-autonomy）：

```yaml
 SCO_liberalism: "Federal Republic of Scotland"
 SCO_subject: "$OVERLORDADJ$ Scotland"
 SCO_IRE_subject: "Alba"
 SCO_autonomy_dominion: "Dominion of Scotland"
 SCO_IRE_democratic_autonomy_integrated_puppet: "Most Northern Ireland"
 COUNTRY_SCO_autonomy_dominion: "Comhairle nan $NONIDEOLOGY$"
```

生效优先级（高→低）：特定宗主国的自治等级 > 自治等级 > 特定宗主国的附庸 > 附庸 > ideology type > ideology group > TAG > COUNTRY。附庸名可嵌 `$NONIDEOLOGY$`、`$NONIDEOLOGYADJ$`、`$NONIDEOLOGYDEF$`、`$OVERLORD$`、`$OVERLORDADJ$`、`$OVERLORDNAMEDEF$`（注意是 NAME），只能在国名里用。

其他支持国家前缀的 key：党派 `TAG_ideology_party` / `TAG_ideology_party_long`（长名缺省复用短名）；装备 `TAG_infantry_equipment_1`，短名再加 `_short`；装备模块、师经验称号、idea/顾问名同理。

### 19.8 上地图

只要 country_tags 有条目国家就"存在"但无地。要开局出现，改 `history/states/*.txt` 的 owner（可只 core）；要中途出现，在任意 effect block 里用 `add_state_core` / `transfer_state`（在该国 scope 内）。

### 19.9 随机人名与随机头像（可选）

`common/names/*.txt` 里以 `TAG = { ... }` 块给随机人名，四个子块：`male = { names = { ... } }`、`female = { names = { ... } }`、`surnames = { ... }`、`callsigns = { ... }`；名字含空格要用引号（`Name "Name with multiple words"`）。`portraits/*.txt` 给随机头像池，分 `navy`/`army`/`operative`/`political` 与 `male`/`female`，political 下每个 ideology group 要单列；陆军人像需同名 `_small` 的 spriteType（军官团用）。

---

## 第 20 章 州与地图

### 州（States）

文件 `history/states/*.txt`，整州包在 `state = { ... }`。**文件名不参与解析**，只解析内容；因此别改原版已存在文件的文件名（否则原版与 mod 都被读，除非用 `replace_path`）。

### 20.1 字段

| 字段 | 必需 | 说明 |
|---|---|---|
| `id = 123` | 是 | 整数。**必须从 1 连续**，1 到最大 ID 之间每个数字都要有州；不连续且未开 debug → 加载崩。删州要把后续 ID 依次前移并全库改引用 |
| `name = STATE_123` | 是 | 本地化 key，英文默认文件 `state_names_l_english.yml` |
| `manpower = 500000` | 是 | 开局总人口。每个场景额外跑一次月度增长（`NCountry.POPULATION_YEARLY_GROWTH_BASE = 0.015`，约 0.125%/月） |
| `state_category = large_town` | 是 | 决定州修正（含初始共用槽）与州视图配色 |
| `provinces = { 123 456 }` | 是 | 省 ID 列表，空白分隔 |
| `impassable = yes` | 否 | 不可通行；省会归最近可通行省的 controller；不能建省级建筑；`impassable` 触发为真 |
| `resources = { steel = 10 aluminium = 20 }` | 否 | 原版资源：`oil`、`aluminium`（英式拼写）、`rubber`、`tungsten`、`steel`、`chromium` |
| `local_supplies = 8.3` | 否 | 1 单位 = 0.2 补给；未写按 0 |
| `buildings_max_level_factor = 0.5` | 否 | 额外乘算共用槽；官方建议改用 state_category |

### 20.2 history 块

| 字段 | 说明 |
|---|---|
| `owner = POL` | 初始所有者。**无 owner 不报错，但对它执行几乎任何 effect（如转手）会崩** |
| `controller = LIT` | 可选，仅当与控制者不同 |
| `victory_points = { 1234 10 }` | 一行只能一个省；多个省写多行。VP 本地化 key `VICTORY_POINTS_<province_id>`，默认文件 `victory_points_l_english.yml`；图标位置在 `map/unitstacks.txt` |
| `buildings = { ... }` | `建筑ID = 等级`，可嵌 `省ID = { ... }` 写省级建筑；未列出的保持不变化。内陆州的沿海专属建筑不能写，写 0 也不行 |
| `add_core_of = POL` / `add_claim_by = LIT` | history 本身是 effect block，任意 effect 可用 |
| `YYYY.MM.DD = { ... }` | 日期块，仅当开局日期严格晚于该日期执行 |

### 20.3 模板

最小：

```
state = {
    id = 123
    name = STATE_123
    manpower = 50000
    state_category = large_town

    history = {
        owner = ITA
    }

    provinces = {
        1234 5678
    }
}
```

带资源/建筑/VP/日期块：

```
state = {
    id = 124
    name = STATE_124
    manpower = 50035
    state_category = megalopolis

    resources = {
        oil = 10
        chromium = 50
    }

    history = {
        owner = SWI
        add_core_of = SWI
        buildings = {
            infrastructure = 3
            industrial_complex = 1
            arms_factory = 1
            dockyard = 10
            7777 = {
                coastal_bunker = 5
                naval_base = 10
            }
        }
        victory_points = { 5555 15 }
        victory_points = { 6666 10 }
        1939.1.1 = {
            controller = ITA
            set_state_name = ITA_STATE_124
            buildings = {
                infrastructure = 4
            }
        }
    }

    provinces = { 1111 2222 3333 4444 5555 6666 7777 8888 9999 }

    local_supplies = 10
}
```

### 20.4 state_category 与槽位

| 显示名 | 内部名 | 共用槽 |
|---|---|---|
| Wasteland / Enclave / Tiny island | `wasteland` / `enclave` / `tiny_island` | 0 |
| Pastoral region | `pastoral` | 1 |
| Small island | `small_island` | 1 |
| Rural region | `rural` | 2 |
| Developed Rural Region | `town` | 4 |
| Sparse Urban Region | `large_town` | 5 |
| Urban Region | `city` | 6 |
| Dense Urban Region | `large_city` | 8 |
| Metropolis Region | `metropolis` | 10 |
| Megalopolis Region | `megalopolis` | 12 |

自定义放 `common/state_category/*.txt`：

```
state_categories={
    my_state_category = {
        color = { 0 255 0 }
        local_building_slots = 14
    }
    my_second_category = {
        color = { 255 0 0 }
        local_building_slots = 4
        resistance_growth = 0.1
    }
}
```

state category 是 modifier block，任意 state scope 修正可用（原版只用 `local_building_slots`）。`color` 为 RGB 0–255，控制州视图配色。运行时换类用 `set_state_category = category_id`。

### 地图（Map）

### 20.5 文件职责

| 文件 | 用途 |
|---|---|
| `map/provinces.bmp` | 省边界（24-bit RGB，一色一省） |
| `map/definition.csv` | 省属性：类型、地形、大洲、沿海 |
| `map/terrain.bmp` | 图形地形（8-bit indexed） |
| `map/heightmap.bmp` | 高度（8-bit 灰度/indexed），决定水下 |
| `map/world_normal.bmp` | 法线（24-bit RGB） |
| `map/terrain/colormap_rgb_cityemissivemask_a.dds` | 世界底色 + 城市灯光 alpha |
| `map/terrain/colormap_water_0.dds` | 海洋配色 |
| `map/buildings.txt` | 建筑模型位置 + 海军基地/浮动港的相邻海域省 |
| `map/unitstacks.txt` | 单位模型位置朝向、VP 图标位置 |
| `map/rivers.bmp` / `map/trees.bmp` | 河流 / 树木（8-bit indexed） |
| `map/supply_nodes.txt` / `map/railways.txt` | 开局补给节点与铁路 |
| `map/adjacencies.csv` / `map/adjacency_rules.txt` | 省对特殊关系 / 海峡规则 |
| `map/ambient_object.txt` | 常在 3D 装饰（含南北地框） |
| `map/cities.txt` + `cities.bmp` | 城市模型分布 |
| `map/default.map` | 指定各用途用哪个文件（如换 provinces bitmap 名） |
| `map/continent.txt` | 大洲列表 |
| `map/strategicregions/*.txt` | 战略区 |
| `map/weatherpositions.txt` | 天气对象位置 |
| `map/airports.txt`、`map/rocketsites.txt` | **1.15 起废弃并移除** |

`map/default.map`：wiki 只说明它用于更改某用途所用的文件名，**具体字段列表 wiki 未明确**。

### 20.6 BMP 规则

- 24-bit RGB：`provinces`、`world_normal`。8-bit greyscale/indexed：`heightmap`。8-bit indexed：`cities`、`rivers`、`terrain`、`trees`。
- 不允许任何压缩。indexed 图读的是**调色板索引**而非颜色，调色板一变即毁图。
- Paint.net / MS Paint 会重建调色板 → **不能编 indexed 图，也不能编 heightmap**。GIMP 导出必须勾 "do not write colour space information"（否则写 BITMAPV5HEADER，引擎不认）。
- `provinces.bmp` 必须 24-bit（32-bit 报 `We do not support bitdepth at 32` 并崩；格式错报 `X4008: floating point division by zero`）；宽高都必须是 **256 的倍数**，总像素 ≤ 约 **13 238 272**。
- 修坏图流程：留 24-bit 副本 → 内容粘回原版文件 → 正确设置导出（Photoshop 用 `Image → Mode → Color Table` 存 `.ACT` 再 Load；新版 GIMP 用 Indexed 模式的 "Use Custom Palette" → "Colormap of Image#..."）。

### 20.7 坐标系

X = provinces.bmp 水平像素（左→右，地图水平环绕）；Y = heightmap 数值 ×10，0 为纯黑、25.5 为纯白，水面在 Y = 9.5（`static const float WATER_HEIGHT = 9.5f;` in `gfx/FX/constants.fxh`）；Z = provinces.bmp 垂直像素（下→上，即南→北），多数图像编辑器的 Y 轴与它相反。

### 20.8 definition.csv

```
Province ID; R value; G value; B value; Province type (land|sea|lake); Coastal status (true/false); Terrain; Continent (integer)
```

```
7;212;179;179;sea;true;ocean;0
114;40;15;15;land;false;plains;1
260;170;235;235;land;true;urban;1
```

- RGB 每省唯一（0–255）；海省 continent 必须 0，湖省可为 0；湖省 terrain 必须 `lakes`，海省必须 `ocean`。
- `coastal` 对陆/海都表示"是否与对方类型接壤"；位图与 csv 冲突时**以位图为准**，该列是 1.11 前遗留。
- **省 ID 必须连续**：中间缺号不崩，但缺号之后所有省会套用下一个 ID 省的地形/类型/沿海/大洲（位图色仍按自己的）。省总数按原版约 13000–14000；超过约 21000 后同屏边界整数溢出（上限 65536 条）。
- 必须 CRLF 行尾，否则 `Prov 12345 has no continent`。
- 定义不全时游戏会在用户目录生成 `map/definition.csv.fixed`，改完原文件后可能要删它。

### 20.9 地形

省级地形写在 `definition.csv`（陆省），海域地形写在战略区的 `naval_terrain = terrain_name`。地形定义在 `common/terrain/*.txt` 的 `categories = { ... }`：

```
categories = {
    my_terrain_1 = {
        color = { 100 120 140 }
        movement_cost = 1.0
        units = { attack = 0.1 }
        combat_width = 78
        combat_support_width = 24
        supply_flow_penalty_factor = 0.2
        match_value = 8
        ai_terrain_importance_factor = 8.0
        buildings_max_level = { bunker = 4 }
    }
}
```

| 字段 | 说明 |
|---|---|
| `color = { 100 120 140 }` | "Simplified terrain" 地图模式颜色，RGB 0–255 |
| `sound_type = forest` | 环境音（似乎未使用） |
| `movement_cost = 1.0` | 移动速度，越大越慢 |
| `units = { ... }` | 该地形内所有陆军/舰船的战斗 unit scope 修正 |
| `<subunit> = { units = { ... } ... }` | 针对兵种，如 `carrier = { units = { attack = -0.2 } navy_fuel_consumption_factor = 0.2 }` |
| 任意 provincial modifier | 地形本身即 modifier block（`attrition`、`positioning`、`navy_visibility` 等） |
| `is_water = yes` + `naval_terrain = yes` | 水域；后者才能被战略区当海军地形引用 |
| `combat_width` / `combat_support_width` | 仅陆地：基础战斗宽度 / 超宽后仍可参战但受罚的宽度 |
| `supply_flow_penalty_factor` | 补给流惩罚 |
| `match_value` | `state_and_terrain_strategic_value` 与和会成本 |
| `ai_terrain_importance_factor` | AI 认为的可防御程度 |
| `buildings_max_level = { bunker = 4 }` | 省级建筑等级上限 |

图形地形另在 `common/terrain/*.txt` 的 `terrain = { ... }` 块（含 `GFX_terrain_*` 的昼/夜/雨/雪/风暴贴图变体）。

### 20.10 战略区 `map/strategicregions/*.txt`

逐省加入；**每省必须有战略区**，且同州所有省必须在同一战略区，否则可能开局崩。海军战略区可写 `naval_terrain = terrain_name`。天气块：

```
weather={
		period={
			between={ 0.0 30.11 }
			temperature={ -6.0 12.0 }
			no_phenomenon=0.500
			rain_light=1.000
			rain_heavy=0.150
			snow=0.200
			blizzard=0.000
			arctic_water=0.000
			mud=0.300
			sandstorm=0.000
			min_snow_level=0.000
		}
    }
```

`between = { day month }` 日和月**从 0 起算**且两端包含；`temperature = { min max }`；其余为该区每省出现该天气的概率（前提 `no_phenomenon` 判负），可多种同时发生，按日结算；`min_snow_level` 控制积雪视觉。

`map/weatherpositions.txt`：`strategic region ID;X position;Y position;Z position;size`，例 `1;2781.24;9.90;1571.49;small`；size 只有 `small`/`large`，两种至少各一条，否则可能崩。

### 20.11 河流 `map/rivers.bmp`

8-bit indexed，按索引值定宽度：0 最细纹理；1–3 细；4 = (0,200,255) 窄；5 = (0,150,255)；6 = (0,100,255) 宽；7–9 中间档；10 = (0,0,150)；11 = (0,0,100) 最宽。机制上 `NDefines.NMilitary.RIVER_SMALL_START_INDEX = 0` 到 `RIVER_SMALL_STOP_INDEX = 6` 为小河，`RIVER_LARGE_STOP_INDEX = 11` 为大河；其他索引不参与机制，可当注释描省界。两省中心连线压到至少一个河像素即算渡河；压到多种类型时行为由实现决定。

### 20.12 铁路与补给

`map/supply_nodes.txt`：`Level; Province`（实际不写分号，例 `1 1234`）。等级上限 1（`common/buildings/00_buildings.txt`）。

`map/railways.txt`：`Level; Amount of provinces; List of provinces`，例 `4 4 693 1444 12 11`。等级上限 5（`NDefines.NSupply.MAX_RAILWAY_LEVEL = 5`）。definitions 指向不存在/无州省、或铁路极度断裂 → 开单机或 nudger 的 Supply 面板崩溃。

1.11 之前是 supply area：`supply_area={ id=1 name="SUPPLYAREA_1" value=12 states={ 5 85 } }`，No Step Back 后废弃。

### 20.13 建筑模型 `map/buildings.txt`

```
State ID (integer); building ID (string); X position; Y position; Z position; Rotation; Adjacent sea province (integer)
```

省级建筑也填**州 ID**，一州多条靠 XYZ 判断省归属；浮动港 building ID 为 `floating_harbor`；Rotation 弧度（正逆时针，一圈 2π ≈ 6.28）；Adjacent sea province 仅海军基地与浮动港需要，其他填 0。**整文件为空会崩**（内容无所谓）。某个海军基地/浮动港缺条目 → AI 评估该省时死循环吃满 CPU/内存后崩，崩溃日志最后读取 `client_ping` 或 `hourly_ping`。

1.15 前 `map/airports.txt`、`map/rocketsites.txt` 格式为 `123 = { 4321 }`（州 ID = 省 ID），现已移除。

### 20.14 单位与 VP 位置 `map/unitstacks.txt`

```
Province ID; Type; X position; Y position; Z position; Rotation; Offset
```

Offset 用来错开动画。Type 为 0–38：0 Standstill；1–8 Moving 0–7；9 Attacking；10 Defending；11–18 Disembarck 0–7；19 Ship in port；20 Ship in port moving；21 Standstill RG；22–29 Moving 0–7 RG；30–37 Disembarck 0–7 RG；38 Victory point（RG = regrouping）。VP 图标位置在此；VP 是否存在/名称/分值由州历史与本地化决定。

### 20.15 相邻关系

`map/adjacencies.csv`：

```
Start province ID;End province ID;Adjacency type;Through province ID;Starting X position;Starting Y position;Ending X position;Ending Y position;Adjacency rule;Comment
```

```
6891;3838;sea;5579;-1;-1;-1;-1;;Sardinia-Corsica
10910;12807;impassable;-1;-1;-1;-1;-1;;Himalayas
3314;6336;sea;2752;2885;1578;2890;1581;;Afsluitdijk
```

type 只有 `sea` 与 `impassable`（未填默认 sea）；sea 必须同类型相接（海-海或陆-陆），陆-陆且不直接接壤时必须填 Through 中转省（敌方控制该省即禁用）；`impassable` 不能跨省、无坐标、不配规则，其余留 -1。X/Y 用 X/Z 坐标，-1 = 自动取两省中心。**末行必须是** `-1;-1;-1;-1;-1;-1;-1;-1;-1`，否则读取不终止。

`map/adjacency_rules.txt`（UTF-8 无 BOM）：

```
adjacency_rule =
{
	name = "BOSPHORUS_STRAIT"
	contested = { army = no navy = no submarine = no trade = no }
	enemy     = { army = no navy = no submarine = no trade = no }
	friend    = { army = yes navy = yes submarine = yes trade = yes }
	neutral   = { army = no navy = no submarine = no trade = yes }
	required_provinces = { 9833 11829 }
	is_disabled = {
		has_country_flag = BOSPHORUS_STRAIT_BLOCKED_FOR_COUNTRY
		tooltip = bosporus_strait_blocked_tt
	}
	icon = 9833
	offset = { -2 0 -9 }
}
```

friend = 附庸/军通/同阵营；contested = 双方在 `required_provinces` 内各控不同省；enemy = 交战；neutral = 无特定关系。`required_provinces` 至少两省，不必同州同国。`is_disabled` 是 trigger。`icon` 一般给海省，`offset` 顺序为 `{ X Z Y }`。

### 20.16 环境物件 `map/ambient_object.txt`

```
type = {
    type = my_entity
    use_animation = no
    scale = 1000
    always_visible = yes
    object = { name = my_entity_name position={ 420.090 10.000 382.670 } rotation={ 0.000 0.000 0.000 } }
}
```

字段：`type`（引用 `gfx/entities/*.asset` 的实体）、`use_animation`、`time_duration`、`scale`（默认 1）、`always_visible`、`object = { name / position / rotation }`。nudger 能改已有物件但不能新建。

### 20.17 其它地图文件要点

- `map/continent.txt`：`continents = { ... }` 为简单列表，ID 按定义顺序从 1 起（`europe` = 1）。所有陆省必须有大洲；用于 `is_on_continent`、AI area、随机头像池。
- `map/trees.bmp` 8-bit indexed，默认每边为 provinces bitmap 的 75/256；索引 2/3 棕榈、5/6 森林、11 不可通行丛林、28/29 丛林；索引 N 对应 pdxmesh `mapobject_N`。
- 调试：必须开 `-debug`，否则任何 `MAP_ERROR` 都会导致无法加载（唯一例外是 rivers.bmp 调色板错误），且主菜单进不了 nudger；部分地图错误只在选国后才写全。

### 地形（Terrain）

#### 页面归属（重要）

`Terrain modding` **不是独立页**，`action=raw` 返回全文只有一行：

```
#REDIRECT [[Map_modding#Terrain]]
```

真正内容在 `Map modding` 的 Terrain 章（`section=11`，含 Terrain / Provincial terrain / Graphical terrain 三小节）。
任务里提到的 `map/terrain.txt` 在 wiki 上**不存在**；wiki 里所有地形定义都在 `common/terrain/*.txt`。

#### 两套地形，两个文件

| 层 | 存储位置 | 作用 |
|---|---|---|
| provincial（省级，影响玩法） | `common/terrain/*.txt` 的 `categories = { ... }` | 给省份挂修正、定义陆战/海战参数 |
| graphical（图形，只影响外观） | `common/terrain/*.txt` 的 `terrain = { ... }` | 地图贴图；不改变任何实际数值 |

分配方式：

- 陆地省的 provincial 地形写在 `map/definition.csv`；
- 海洋省的 provincial 地形写在 **strategic regions**（不是 definition.csv）；
- graphical 地形由 `map/terrain.bmp` 决定，该文件是 8-bit indexed 图，尺寸必须与 `map/provinces.bmp` 一致；
- nudger 的 database 段有开关，可按 graphical 地形批量生成 provincial 地形。

判定依据是 **colourmap ID**，不是 RGB。原版那套 RGB 只是默认值：同一 ID 位置换成别的颜色，游戏行为不变。

#### provincial 地形字段

`categories = { <terrain_name> = { ... } }`，块名即地形 ID。

通用字段：

| 字段 | 说明 |
|---|---|
| `color = { 100 120 140 }` | 该地形在「Simplified terrain」地图模式下的颜色，RGB 0–255 |
| `sound_type = forest` | 环境音，wiki 注明「appears to be unused」 |
| `movement_cost = 1.0` | 移动消耗，值越大师/船在该地形移动越慢 |
| `units = { ... }` | 战斗内的单位级修正，如 `attack = 0.1`、`defence = -0.1`，作用于该省所有陆军师/舰船 |
| `<subunit> = { ... }` | 按兵种细分：块内 `units = { ... }` 只作用于战斗，块内其他键作用于战斗外 |
| `is_water = yes` | 标记为水域，只能给海/湖用 |
| `naval_terrain = yes` | 标记为海战地形，可被 strategic region 使用（需与 is_water 一起） |
| 任意省级 modifier | 地形块本身就是 modifier 块，可塞任何 provincial modifier |

`<subunit>` 写法示例：

```
carrier = {
    units = {
        attack = -0.2
    }
    navy_fuel_consumption_factor = 0.2
}
```

仅陆地的字段：

| 字段 | 说明 |
|---|---|
| `combat_width = 78` | 基础战斗宽度，此宽度内的部队无惩罚参战 |
| `combat_support_width = 24` | 超出 combat_width 后还能参战的额外宽度，但有惩罚 |
| `supply_flow_penalty_factor = 0.2` | 穿过该地形的补给流量惩罚 |
| `match_value = 8` | 地形战略值，供 `state_and_terrain_strategic_value` 触发器/变量与和平会议计价 |
| `ai_terrain_importance_factor = 8.0` | AI 眼中的可防守程度，越高越当要地 |
| `buildings_max_level = { bunker = 4 }` | 覆盖省级建筑上限 |

常用 modifier（wiki 点名）：

- `attrition = 0.1` 基础损耗
- `enemy_army_bonus_air_superiority_factor = -0.1` 改进攻方从制空权拿到的加成
- `sickness_chance = 1.0` 该省作战可能让将领生病
- `positioning = 0.1` 海军阵位（海省）
- `navy_visibility = -0.2` 舰队可见度（海省）

#### 战斗宽度与攻防修正（原版数值）

| 内部名 | 类型 | 最优战斗宽度 | 对师攻击的影响 |
|---|---|---|---|
| `unknown` | land | — | 新省默认 |
| `plains` | land | 90 | — |
| `desert` | land | 90 | — |
| `forest` | land | 84 | −15% |
| `jungle` | land | 84 | −30% |
| `hills` | land | 80 | −25% |
| `marsh` | land | 78 | −40% |
| `mountain` | land | 75 | −50% |
| `urban` | land | 96 | −30% |
| `ocean` | sea | — | 海省默认 |
| `lakes` | sea | — | 湖省默认 |
| `water_fjords` | naval | — | 战巡/战列/重巡/航母 −20% 攻防与移动、−20% 可见度、阵位 −15% |
| `water_shallow_sea` | naval | — | 潜艇可见度 +100%、阵位 −5% |
| `water_deep_ocean` | naval | — | 驱逐 −20% 攻/移/防，轻巡 −10%；潜艇 −15% 可见度、速度 −25%；触雷概率减半 |

改攻防用 `units = { attack = ... defence = ... }`；改宽度用 `combat_width` / `combat_support_width`。
移动消耗只有 `movement_cost` 一个入口，没有「按兵种改移动」的字段。

#### graphical 地形字段

```
terrain = {
    my_terrain = {
        type = urban
        color = { 23 }
        texture = 1
        spawn_city = yes
    }
    my_terrain = { type = plains color = { 24 } texture = 2 }
}
```

| 字段 | 说明 |
|---|---|
| `type = urban` | nudger 自动生成 provincial 地形时用的目标类型 |
| `color = { 23 }` | colourmap 索引列表（可多个），**不是 RGB** |
| `texture = 1` | atlas 里的贴图序号，从 0 起 |
| `spawn_city = yes` | 自动生成城市模型 |
| `perm_snow = yes` | 该区域永久积雪 |

块名无意义，可以重名（示例里两个块都叫 `my_terrain`）。

atlas 文件：`map/terrain/atlas0.dds` 与 `map/terrain/atlas_normal0.dds`，必须正方形。
默认 4×4 格（`MAP_NUM_TILES = 4.0f`），每格 512×512（`TEXELS_PER_TILE = 512.0f`，均在 `gfx/FX/constants.fxh`），
编号从左到右、从上到下：

```
0  1  2  3
4  5  6  7
8  9  10 11
12 13 14 15
```

所以 `texture = 11` 是右下偏中的那格。`atlas1`/`atlas2` 给远视角降质用，尺寸分别是 atlas0 的 1/2 和 1/4；
`atlas_normal0/1/2` 是法线图。

原版 graphical 地形 ID 表（ID → 颜色 → nudger 生成类型）要点：
0 plains / 1 forest（密林）/ 4 forest（疏林）/ 5 plains（农田）/ 2、17 hills / 3、7、8、12 desert /
6、10、11、18、20、27、31 mountain / 9 marsh / 13 urban（自动生成城市）/ 15 ocean /
16 mountain（永久积雪）/ 19 plains（永久积雪）/ 21、22 jungle / 14 lakes（原版从未使用，指向无效贴图，湖实际用 ocean）。

#### 本地化与 sprite

本地化键 = 地形 ID：

```
my_terrain_1: "My terrain"
my_terrain_1_desc: ""
```

陆地地形要 2 张 sprite：`GFX_terrain_<name>` 与 `GFX_terrain_<name>_winter`（下雪时替换）。
海军地形要 10 张：day/night × 晴/雨/暴风/雪/雪暴，命名 `GFX_terrain_<name>_day`、`_day_rain`、`_day_storm`、
`_day_snow`、`_day_snow_storm`、`_night`、`_night_rain`、`_night_storm`、`_night_snow`、`_night_snow_storm`。
贴图放 `gfx/interface/terrains/`。

#### 常见错误

1. **拿 RGB 当判定依据**：改 `terrain.bmp` 颜色不改 colourmap ID 才安全；改了 ID 顺序等于全图地形重排。
2. **在 `map/terrain.bmp` 里做玩法调整**：那层只管外观，战斗修正永远在 `common/terrain/*.txt` 的 `categories`。
3. **漏 winter sprite**：陆地地形只定义一个 sprite，下雪时贴图会丢。
4. **海军地形漏 10 张 sprite 中的几张**，或忘写 `naval_terrain = yes` 导致 strategic region 里选不到。
5. **atlas 不是正方形 / 没生成 mipmap / 没用 DXT5**，游戏直接读不到。
6. **新省忘设地形**：`unknown` 是默认值，会有默认修正而不是你想要的那套。
7. **想把 `is_water` 地形给陆地省**：只对海、湖有效。

---

## 第 21 章 剧本起点（Bookmarks）

### 剧本起点（Bookmarks）

根块 `bookmarks = { ... }`，内含多个 `bookmark = { ... }`。

| 属性 | 说明 |
|---|---|
| `name = loc_key` / `desc = loc_key` | 名字 / 描述；缺省不显示 |
| `date = 1936.1.1.12` | `YYYY.MM.DD.HH`；默认 `2.1.1.1`，不能更早 |
| `picture = GFX_select_date_1936` | spriteType，定义在 `interface/*.gfx`；默认纯黑 |
| `default = yes` | 默认书签（主菜单预载其条件），只应有一个 |
| `default_country = GER` | 默认选中国家，必须在 interesting countries 里 |
| `effect = { ... }` | 选中书签时执行（history 之后、玩家选国之前）；常用 `randomize_weather` |
| `TAG = { ... }` | interesting country 条目；`"---"` 表示"其他国家"入口；同一国可写多条 |

`TAG = { ... }` 内部：`history = loc_key`（选中国家时显示的历史）、`ideology = neutrality`（起始 ideology group，决定领袖/图标/国名/旗帜）、`minor = yes`（显示在下方小旗栏，且需该国焦点树没有 `default = yes`）、`available = { has_dlc = "..." }`（trigger，通常只用于 DLC 检查）、`ideas = { A B C }`（展示用 national spirit，默认最多 3 条，由 `ideas_grid` 槽位决定）、`focuses = { A B C }`（默认最多 3 条，由 `focus_grid` 决定）。

```
bookmarks = {
    bookmark = {
        name = example_bookmark_1
        desc = example_bookmark_1_desc
        date = 1936.1.1.12
        picture = GFX_select_date_1936
        "---" = { history = OTHER_SCENARIO1_DESC }
        effect = { randomize_weather = 1228 }
    }
    bookmark = {
        name = example_bookmark_2
        desc = example_bookmark_2_desc
        date = 1936.1.1.12
        picture = GFX_select_date_1936
        default = yes
        default_country = BHR
        BHR = {
            history = BHR_SCENARIO2_DESC
            ideology = neutrality
            focuses = { BHR_focus_1 }
            ideas = { BHR_idea_1 BHR_idea_2 }
        }
        QAT = {
            history = QAT_SCENARIO2_DESC
            ideology = democratic
            minor = yes
            available = { NOT = { has_dlc = "Arms Against Tyranny" } }
        }
        QAT = {
            history = QAT_SCENARIO2_DESC
            ideology = democratic
            minor = yes
            focuses = { QAT_focus_1 QAT_focus_2 }
            available = { has_dlc = "Arms Against Tyranny" }
        }
        "---" = { history = OTHER_SCENARIO2_DESC }
        effect = {
            randomize_weather = 45768
            321 = { transfer_state_to = QAT }
        }
    }
}
```

UI 与注意点：书签图默认 180×104 像素，底部留缺口（约半径 35 像素、中心在左+90/上+130 处挖圆）以免压边框；布局在 `interface/frontendgamesetupview.gui`（`bookmarks_grid`/`bookmark_entry`，三个 `countries_grid` 分别对应 `countries`、`countries_medium`、`countries_mini`，第 9 个次要国后切换）。只有 1 个书签会跳过书签选择且无法返回主菜单，规避办法是保留第二个书签但给 gridbox 加 `max_slots_horizontal = 1` 隐藏。开局日期不能早于公元 2 年，改最早日期要动 `NGame.START_DATE`、`NGame.END_DATE`、`NDiplomacy.TENSION_TIME_SCALE_START_DATE`（override 文件）。同一日期要不同局面用 `effect`，或国家/州历史里写日期块（`1937.1.1 = { owner = DEF }`）。书签按日期排序，同日期按求值顺序；interesting countries 按书写顺序。

---

## 第 22 章 游戏规则（Game Rules）

### 游戏规则（Game rules）

位置：`common/game_rules/*.txt` 与 `common/difficulty_settings/*.txt`。**任一类型没有有效条目，玩家打不开规则菜单。**

### 22.1 difficulty_settings（滑块）

```
difficulty_settings = {
    difficulty_setting = {
        key = "custom_diff_strong_bhr"
        modifier = diff_strong_ai_generic
        countries = { BHR }
        multiplier = 2.0
    }
    difficulty_setting = {
        key = "custom_diff_weak_arab"
        modifier = diff_weak_ai_generic
        countries = { BHR QAT OMA YEM SAU }
        multiplier = 4.0
    }
}
```

`key` = 菜单名字的本地化 key；`modifier` = static modifier；`countries` = 施加国列表；`multiplier` = 滑块最右端的乘数，5 档线性从 0 到该值（`stability_factor = 0.4` + `multiplier = 2.0` → 0/20/40/60/80%）。滑块顺序：文件夹内文件名 ASCII 序，再按文件内定义顺序。这与"难度"本身无关——难度对每国施加 static modifier（`diff_very_easy_player`…`diff_very_hard_player`、`diff_very_easy_ai`…`diff_very_hard_ai`）。

### 22.2 game_rules（下拉选项）

每个规则是根级块，块名即规则 ID：

```
allow_new_diplo_option = {
    name = "RULE_ALLOW_SCRIPTED_DIPLO_OPTION"
    group = "RULE_GROUP_GENERAL_FOREIGN_POLICY"
    icon = "GFX_new_icon"
    default = {
        name = "ALLOWED"
        text = "RULE_OPTION_ALLOWED"
        desc = "RULE_ALLOW_SCRIPTED_DIPLO_OPTION_ALLOWED_DESC"
    }
    option = {
        name = "BLOCKED"
        text = "RULE_OPTION_BLOCKED"
        desc = "RULE_ALLOW_SCRIPTED_DIPLO_OPTION_BLOCKED_DESC"
    }
}
BHR_ai_behavior = {
    name = "BHR_AI_BEHAVIOR"
    group = "RULE_GROUP_AI_BEHAVIOR"
    default = { name = DEFAULT text = "RULE_OPTION_DEFAULT" desc = "RULE_OPTION_DEFAULT_AI_DESC" }
    option = { name = COMMUNIST text = "RULE_OPTION_COMMUNIST" desc = "..." }   # 同理再加 DEMOCRATIC / FASCIST / RANDOM 三条
}
```

| 规则级字段 | 说明 |
|---|---|
| `name = loc_key` | 规则名（本地化常含 `@TAG` 国旗或 `£icon` 文字图标） |
| `group = group_id` | 分组；**无需另外定义**，用到即自动创建；group ID 同时是本地化 key |
| `icon = GFX_example_sprite` | 图标 spriteType，原版约 32×32 |
| `required_dlc = "Wojtek Expansion Pack"` | 该 DLC 存在才创建此规则；缺失则规则完全不存在，引用它的 trigger 在 error.log 报错 |
| `exclude_dlc` | 与上相反 |
| `default = { ... }` | 默认选项（自动允许成就） |
| `option = { ... }` | 其他选项，可多个 |

| 选项级字段 | 说明 |
|---|---|
| `name = option_name` | 选项 ID，`has_game_rule = { name = rule_id value = option_name }` 用它 |
| `text = loc_key` | 显示名 |
| `desc = loc_key` | 悬停说明 |
| `allow_achievements = yes` | 选中该选项不禁用成就；**只能写在 `option` 里**；mod 改 checksum 本来就没成就，此项在 mod 内无实际作用 |

三类实现方式：① 开局一次性改动（通常 `on_startup`）；② 机制性改动（反复查规则值，如 `allow_branch` 里查、diplomacy scripted trigger、AI strategy plan 里查，随机线用 `on_startup` + `random_list` 设 country flag）；③ 完全硬编码（值在二进制里判，只能删规则或删选项，例如陆上要塞等级上限）。

`Custom_difficulty` 页是这些规则在**玩家界面**上的取值与成就开关清单（Wargoals / Military Access / Release Nations / Production Licenses / Lend Lease / Volunteers / Guarantee / Revoke / Leave-Kick-Takeover Faction / Coups / Party Popularity / Paradrops / Fort Level 1–9 / Scorched Earth / 各国 AI 行为 / 各洲去殖民化 / 各国碎裂状态 / Show obsolete branches / Peace Score Distribution），只提供"要哪几档选项"的参考，不含脚本语法。

---

## 第 23 章 on_actions 钩子

### on_actions 钩子

位置 `common/on_actions/*.txt`，根块 `on_actions = { ... }`，每个钩子独立块。每个钩子最多两个参数：`effect = { ... }`（触发时执行）与 `random_events = { ... }`（仅默认作用域为国家的钩子可用，按权重比例随机触发一个事件；写 `0` 表示抽到则什么都不发生；事件 `trigger` 为假时不会触发，此时作用域与钩子一致）。多个 `random_events` 块则每块各抽一个。**钩子只在游戏开始后执行**——history 文件或 bookmark 的 `effect` 里做 `set_politics` 等不会触发。`effect` 行必须写，用来和 `random_events` 区分。

```
on_actions = {
    on_startup = {
        effect = {
            every_country = {
                limit = { is_ai = no }
                country_event = welcome_event.1
            }
            ENG = {
                country_event = { id = new_year.1 days = 365 }
            }
        }
    }
    on_state_control_changed = {
        random_events = {
            1 = germany_state_control.1
            1 = germany_state_control.2
            3 = 0                    # 60% 概率什么都不发生
        }
        effect = {
            if = {
                limit = {
                    tag = ITA
                    FROM = { tag = FRA }
                    FROM.FROM = { state = 735 }
                }
                FROM.FROM = { set_resistance = 60 }
            }
        }
    }
}
```

### 23.1 通用

| 钩子 | 时机 | 作用域/备注 | 版本 |
|---|---|---|---|
| `on_startup` | 新游戏第一天（选国后）；读档不触发 | **默认作用域 none**，必须手动 scope | 1.3.3 |
| `on_daily` | 每天，**每国各一次** | 性能敏感；等于每天在 every_country 里跑一次 | 1.5.2 |
| `on_daily_TAG` | 每天，仅指定国家 | 仅当该国存在 | 1.9 |
| `on_weekly` | 每周，每国各一次 | `num_days` 能被 7 整除那天的开始 | 1.9 |
| `on_weekly_TAG` | 每周，仅指定国家 | 同上 | 1.9 |
| `on_monthly` | 每月，每国各一次 | | 1.9 |
| `on_monthly_TAG` | 每月，仅指定国家 | | 1.9 |

### 23.2 政治

| 钩子 | 时机 | 作用域 | 版本 |
|---|---|---|---|
| `on_stage_coup` | 非 LaR 政变被策划 | ROOT 策划国，FROM 目标 | 1.0 |
| `on_coup_succeeded` | 非 LaR 政变成功 | ROOT 政变国，FROM 策划国 | 1.0 |
| `on_government_change` | 政府更换 | 含 `set_politics`、`start_civil_war`（双方），不含被傀儡；总会同时触发 `on_ruling_party_change` | 1.0 |
| `on_ruling_party_change` | 意识形态更换 | 临时变量 `old_ideology_token` 存旧意识形态；含被傀儡与控制台改意识形态 | 1.9 |
| `on_new_term_election` | 选举或被 `hold_election` 调用 | | 1.0 |
| `on_before_peace_conference_start` | 投降后、和会前 | ROOT 胜者，FROM 败者（每个胜者对每个败者） | 1.15.2 |
| `on_peaceconference_ended` | 和会结束 | ROOT 胜者，FROM 败者；`white_peace` 或接受有条件投降也触发 | 1.5 |
| `on_peaceconference_started` | 和会开始 | 同上 | 1.12.3 |

### 23.3 外交 / 战争

| 钩子 | 时机 | 作用域 | 版本 |
|---|---|---|---|
| `on_send_volunteers` | 派遣志愿军 | ROOT 派出国，FROM 接收国 | 1.9 |
| `on_border_war_lost` | 输掉边境界战（`set_border_war`） | 默认作用域是输掉的州 | 1.0 |
| `on_war_relation_added` | 两国进入交战 | ROOT 攻击方，FROM 防守方 | 1.9.3 |
| `on_declare_war` | 宣战 | ROOT 宣战国，FROM 目标 | 1.0 |
| `on_war` | 从和平进入战争 | THIS 是刚入战国 | 1.7 |
| `on_peace` | 不再处于战争 | THIS 是该国 | 1.7 |
| `on_capitulation` | 投降过程中段 | ROOT 投降国，FROM 胜者；删单位/转装备已执行 | 1.0 |
| `on_capitulation_immediate` | 投降过程开始 | ROOT 投降国，FROM 胜者 | 1.11.5 |
| `on_uncapitulation` | 恢复未投降 | ROOT 受影响国 | 1.4 |
| `on_annex` | 被吞并 | ROOT 胜者，FROM 被吞并者；内战还触发 `on_civil_war_end` | 1.3.3 |
| `on_civil_war_end_before_annexation` | FROM 被吞并之前 | ROOT 胜者；之后还会触发 `on_annex` 与 `on_civil_war_end` | 1.6 |
| `on_civil_war_end` | 内战结束 | ROOT 胜者，FROM 被吞并者；也触发 `on_annex` | 1.0 |
| `on_puppet` | **仅和会**傀儡 | ROOT 被傀儡国，FROM 宗主 | 1.0 |
| `on_liberate` | **仅和会**解放 | ROOT 被解放国，FROM 解放者领袖 | 1.0 |
| `on_release_as_free` | 被释放 | ROOT 新国家，FROM 释放者 | 1.3 |
| `on_release_as_puppet` | 和平时占领区菜单傀儡/非核心自有地释放 | ROOT 被释放国，FROM 宗主 | 1.3 |
| `on_guarantee` | 保障独立 | ROOT 保障国，FROM 被保障国 | — |
| `on_military_access` | 军通请求被接受 | ROOT 请求国，FROM 接受国 | — |
| `on_offer_military_access` | 军通提议被接受 | ROOT 提议国，FROM 接受国 | — |
| `on_call_allies` | 战争召唤被接受 | ROOT 召唤国，FROM 加入国 | — |
| `on_join_allies` | 加入盟友战争 | ROOT 加入国，FROM 被加入方 | — |
| `on_lend_lease` | 租借被接受 | ROOT 提供国，FROM 接受国 | — |
| `on_incoming_lend_lease` | 被请求的租借被接受 | ROOT 接受国，FROM 请求国 | — |
| `on_send_expeditionary_force` | 派遣远征军被接受 | ROOT 派遣国，FROM 接受国 | — |
| `on_return_expeditionary_forces` | 归还远征军 | ROOT 部队所有国，FROM 接收国 | — |
| `on_request_expeditionary_forces` | 请求远征军 | ROOT 请求国，FROM 目标国 | — |
| `on_ask_for_state_control` | 州控制权请求被接受 | ROOT 请求者，FROM 当前控制者 | — |
| `on_give_state_control` | 被给予州控制权 | ROOT 给与者，FROM 接收者 | — |
| `on_peace_proposal` | 有条件投降被接受 | ROOT 发送方，FROM 接收方 | — |
| `on_send_attache` | 武官被接受 | 默认作用域发送方，FROM 接收方 | — |

`on_recall_volunteers` 在旧文档里出现过，但二进制里不存在，写了无效。

### 23.4 阵营 / 自治 / 流亡政府

| 钩子 | 时机 | 作用域 | 版本 |
|---|---|---|---|
| `on_create_faction` | 创建阵营 | FROM 加入者 | 1.0 |
| `on_faction_formed` | 阵营形成 | | 1.0 |
| `on_offer_join_faction` | 受邀加入 | FROM 被邀请国，THIS 与 ROOT 为阵营领袖 | 1.0 |
| `on_join_faction` | 申请加入后，在领袖处触发 | FROM 阵营领袖，ROOT 与 THIS 为加入国 | 1.0 |
| `on_assume_faction_leadership` | 接管领导权 | ROOT 新领袖，FROM 旧领袖 | 1.7 |
| `on_leave_faction` | 退阵营 | FROM 阵营领袖，ROOT 退出国 | 1.0 |
| `on_subject_annexed` | 附庸被吞并 | ROOT 附庸，FROM 宗主 | 1.0 |
| `on_subject_free` | 傀儡被给自由 | ROOT 附庸，FROM 原宗主 | 1.0 |
| `on_subject_autonomy_level_change` | 自治等级变化 | ROOT 附庸，FROM 宗主 | 1.0 |
| `on_government_exiled` | 成为流亡政府 | ROOT 流亡政府，FROM 接待国 | 1.6 |
| `on_host_changed_from_capitulation` | 接待国投降后改换 | ROOT 流亡政府，FROM 新接待国，FROM:FROM 旧接待国 | 1.6 |
| `on_exile_government_reinstated` | 流亡政府回国 | ROOT 流亡政府，FROM 接待国 | 1.6 |

### 23.5 州 / 战争目标

| 钩子 | 时机 | 作用域 | 版本 |
|---|---|---|---|
| `on_state_control_changed` | 州控制者变化 | ROOT 新控制者，FROM 旧控制者，FROM.FROM 是州 | 1.4 |
| `on_generate_wargoal` | 生成战争目标 | ROOT 目标所有者，FROM 目标国 | — |
| `on_justifying_wargoal_pulse` | 被正当化期间每天检查 | FROM 目标国 | 1.0 |
| `on_wargoal_expire` | 战争目标过期 | FROM 目标所有者 | 1.0 |

写法要点：`FROM.FROM = { ... }` 才是州 scope；重命名用 `set_state_name` + `set_province_name`，还原用 `reset_state_name = yes` 与 `reset_province_name = 1234`。

### 23.6 将领 / 军事

| 钩子 | 时机 | 作用域 | 版本 |
|---|---|---|---|
| `on_unit_leader_created` | 陆军将领创建 | FROM 所属国，ROOT 将领 | 1.5 |
| `on_army_leader_daily` | 将领每日 | 同上 | 1.0 |
| `on_army_leader_won_combat` | 赢得战斗 | 同上 | 1.0 |
| `on_army_leader_lost_combat` | 输掉战斗 | 同上 | 1.0 |
| `on_unit_leader_level_up` | 升级 | 同上 | 1.0 |
| `on_army_leader_promoted` | 军长晋升元帅 | 同上 | 1.0 |
| `on_unit_leader_promote_from_ranks_veteran` | 部队指挥官晋升将军（老兵） | FROM 部队，OWNER 所属国，ROOT 将领 | 1.12 |
| `on_unit_leader_promote_from_ranks_green` | 同上（新兵） | 同上 | 1.12 |
| `on_nuke_drop` | 投核弹 | ROOT 投掷国，FROM 被炸的州 | 1.0 |
| `on_pride_of_the_fleet_sunk` | 舰队荣耀被击沉 | FROM 击沉国，ROOT 失去国 | 1.6 |
| `on_naval_invasion` | 海上登陆 | THIS 被登陆州，ROOT 入侵国，FROM 出发州 | 1.9 |
| `on_paradrop` | 空降（每单位一次） | THIS 被空降州，ROOT 空降国，FROM 出发州 | 1.9 |
| `on_units_paradropped_in_state` | 空降（每次空降一次） | ROOT 被空降州，FROM 空降国 | — |
| `on_add_history` | 单位获得历史条目 | ROOT 单位 | 1.12 |

### 23.7 王牌 / 情报 / MIO / 特殊项目

| 钩子 | 时机 | 作用域 | 版本 |
|---|---|---|---|
| `on_ace_promoted` | 王牌产生 | FROM 王牌 | 1.0 |
| `on_ace_killed` | 王牌阵亡 | FROM 王牌 | 1.0 |
| `on_ace_killed_on_accident` | 我方王牌事故死亡 | FROM 死亡王牌 | 1.9 |
| `on_non_ace_killed_other_ace` | 非王牌击落敌王牌 | FROM 敌王牌 | 1.9 |
| `on_ace_killed_by_ace` | 王牌被王牌击落（阵亡方） | FROM 我方王牌，PREV 敌王牌 | 1.0 |
| `on_ace_killed_other_ace` | 王牌被王牌击落（生还方） | FROM 我方王牌，PREV 敌王牌 | 1.0 |
| `on_aces_killed_each_other` | 同归于尽 | FROM 王牌，PREV 敌王牌 | 1.0 |
| `on_operation_completed` | 行动完成（结果 effect 与暴露判定之前） | THIS 行动，ROOT 发起国，FROM 目标国 | 1.9 |
| `on_operative_detected_during_operation` | 行动中被发现 | THIS 特工，ROOT 击杀国（可选），FROM 所属国，FROM.FROM 行动州 | 1.9 |
| `on_operative_on_mission_spotted` | 进攻性任务被发现 | THIS 特工，FROM 所在国，ROOT 所属国 | 1.9 |
| `on_operative_captured` | 特工被捕 | THIS 特工，ROOT 执行国，FROM 所属国 | 1.9 |
| `on_operative_created` | 特工创建 | THIS 特工，FROM 创建国 | 1.9.1 |
| `on_operative_death` | 特工死亡 | THIS 特工，ROOT 击杀国（可选），FROM 所属国 | 1.9 |
| `on_operative_recruited` | 特工被招募 | THIS 特工，FROM 创建国 | 1.9.1 |
| `on_fully_decrypted_cipher` | 完全破译对方密码 | THIS 被破译国，FROM 破译国 | 1.9 |
| `on_activated_active_decryption_bonuses` | 激活主动破译加成 | THIS 目标国，FROM 激活国 | 1.9 |
| `on_mio_size_increased` | MIO 升级 | ROOT MIO，FROM 拥有国 | 1.13 |
| `on_mio_design_team_assigned_to_tech` | MIO 分配到科技 | 同上 | 1.13 |
| `on_mio_design_team_assigned_to_variant` | MIO 分配到改型 | 同上 | 1.13 |
| `on_mio_industrial_manufacturer_assigned` | MIO 分配到生产线 | 同上 | 1.13 |
| `on_mio_industrial_manufacturer_unassigned` | MIO 从生产线撤下 | 同上 | 1.13 |
| `on_project_completion` | 项目完成 | ROOT 国家，FROM 项目 | 1.15 |

`on_mio_tech_research_cancelled` 与 `on_mio_tech_research_completed` 仍出现在原版文件里但**不生效**。

---

## 第 24 章 defines 常量

### defines 常量

位置 `common/defines/*.lua`。Defines 是 Lua 数组，逐成员改，不必复制整文件：

```lua
NDefines.NGame.START_DATE = "1936.1.2.12" -- 多余的逗号会导致启动崩溃
NDefines.NGraphics.COUNTRY_FLAG_TEX_MAX_SIZE = 2048
```

行尾**不加逗号**（逗号是数组元素分隔符，不是语句分隔符）。自己的修改放在单独新文件，按文件名 ASCII 序在原版之后求值——`0` 的 ASCII 最小，几乎任何文件名都可以。原版在文件最后一行把图形 defines 合并进 NDefines，但 Lua 不复制表，`NDefines` 与 `NDefines_Graphics` 指向同一批元素，改哪个都行。**mod 里绝不要带 `00_defines.lua` / `00_graphics.lua`**：官方小版本也常改这两个文件，缺 define 会不稳定甚至启动崩溃。

| define | 默认 | 用途 |
|---|---|---|
| `NGame.START_DATE` | `"1936.1.1.12"` | 默认开局日期 |
| `NGame.END_DATE` | `"1949.1.1.1"` | 结算日（除非仍有大战） |
| `NGame.MAP_SCALE_PIXEL_TO_KM` | `7.114` | 位图像素距离 → 游戏公里 |
| `NGame.SAVE_VERSION` | `25` | 存档兼容版本 |
| `NGame.GAME_SPEED_SECONDS` | `{ 2.0, 0.5, 0.2, 0.1, 0.0 }` | 每档速度秒数，必须 5 项且末项 0 |
| `NGame.EVENT_TIMEOUT_DEFAULT` | `13` | 事件默认超时天数 |
| `NGame.MAJOR_PARTICIPANTS_FOR_MAJOR_WAR` | `3` | 判定"大战"的主要国数 |
| `NGame.FUEL_RESOURCE` | `"oil"` | 提供燃料的资源（改后要同步本地化 `FUEL_DAILY_GAIN_FROM_OIL`） |
| `NGame.MAX_EFFECT_ITERATION` | `1000` | 循环 effect 最大迭代 |
| `NGame.MAX_SCRIPTED_LOC_RECURSION` | `30` | scripted localisation 最大递归 |
| `NGame.HANDS_OFF_START_TAG` | `"HAI"` | `-hands_off` 观战的玩家国 |
| `NDiplomacy.BASE_SURRENDER_LEVEL` | `1.0` | 投降阈值（0–1） |
| `NDiplomacy.BASE_TRUCE_PERIOD` | `180` | 停战期天数 |
| `NDiplomacy.TRUCE_BREAK_COST_PP` | `200` | 破停战政治点基数（按剩余比例乘） |
| `NDiplomacy.TENSION_DECAY_DAILY` | `0.005` | 世界紧张度日衰减 |
| `NDiplomacy.TENSION_TIME_SCALE_START_DATE` | `"1936.1.1.12"` | 紧张度按时间缩放起点 |
| `NDiplomacy.VOLUNTEERS_DIVISIONS_REQUIRED` | `30` | 可派志愿军所需师数 |
| `NCountry.POPULATION_YEARLY_GROWTH_BASE` | `0.015` | 年人口增长（月度人力） |
| `NProduction.MAX_CIV_FACTORIES_PER_LINE` | `15` | 单线最多民用工厂 |
| `NProduction.MAX_MIL_FACTORIES_PER_LINE` | `150` | 单线最多军用工厂 |
| `NProduction.BASE_FACTORY_SPEED_MIL` | `4.50` | 每军工厂基础产出系数 |
| `NTechnology.BASE_TECH_COST` | `110` | 科技基础花费 |
| `NTechnology.BASE_YEAR_AHEAD_PENALTY_FACTOR` | `2` | 超前研究惩罚基数 |
| `NPolitics.BASE_POLITICAL_POWER_INCREASE` | `2` | 每周政治点 |
| `NPolitics.ARMY_LEADER_COST` | `5` | 招募将领指挥点系数 |
| `NBuildings.MAX_BUILDING_LEVELS` | `15` | 建筑最高等级 |
| `NBuildings.AIRBASE_CAPACITY_MULT` | `200` | 每级空军基地容量 |
| `NBuildings.MAX_SHARED_SLOTS` | `25` | 共用槽上限 |
| `NBuildings.INFRASTRUCTURE_RESOURCE_BONUS` | `0.2` | 每级基础设施资源加成 |
| `NDeployment.BASE_DEPLOYMENT_TRAINING` | `1` | 每天训练进度 |
| `NMilitary.RIVER_SMALL_START_INDEX` / `RIVER_SMALL_STOP_INDEX` / `RIVER_LARGE_STOP_INDEX` | `0` / `6` / `11` | 河流宽度索引分界 |
| `NMilitary.MAX_LEADERS_TO_SHOW` | `50` | 军官列表上限 |
| `NGraphics.COUNTRY_COLOR_SATURATION_MODIFIER` / `..._BRIGHTNESS_MODIFIER` | `0.6` / `0.8` | 国家色修正 |
| `NGraphics.COUNTRY_FLAG_TEX_WIDTH`/`HEIGHT` | `82`/`52` | 标准旗尺寸 |
| `NGraphics.COUNTRY_FLAG_MEDIUM_TEX_WIDTH`/`HEIGHT` | `41`/`26` | 中旗尺寸 |
| `NGraphics.COUNTRY_FLAG_SMALL_TEX_WIDTH`/`HEIGHT` | `10`/`7` | 小旗尺寸 |
| `NGraphics.MINIMUM_PROVINCE_SIZE_IN_PIXELS` | （wiki 用宏引用，正文未给数值） | 省最小像素数 |
| `NSupply.MAX_RAILWAY_LEVEL` | `5` | 铁路最高等级 |

---

## 第 25 章 本地化

### 本地化（Localisation）

### 25.1 语言代码与文件命名

位置 `localisation/`，子目录可任意嵌套（深度不限）。文件名必须含语言内部名，否则不加载：

| 代码 | 例子 |
|---|---|
| `l_english` | `localisation/english/filename_l_english.yml` |
| `l_french` | `localisation/french/mod_file_l_french.yml` |
| `l_german` | `localisation/german/state_names_l_german.yml` |
| `l_spanish` | `localisation/spanish/mod_germany_l_spanish.yml` |
| `l_braz_por` | `localisation/braz_por/bahrain_l_braz_por.yml` |
| `l_polish` | `localisation/polish/myfile_l_polish.yml` |
| `l_russian` | `localisation/russian/siberia_l_russian.yml` |
| `l_japanese` | `localisation/japanese/kuril_l_japanese.yml` |
| `l_simp_chinese` | `localisation/simp_chinese/khalkha_l_simp_chinese.yml` |
| `l_korean` | `localisation/korean/victory_points_l_korean.yml` |

当前语言在用户目录 `pdx_settings.txt` 里选；除上述语言外无法新增。

### 25.2 硬性要求

1. `.yml` 扩展名（Windows 默认隐藏扩展名，要打开）。
2. 文件名含语言内部名，**`l` 是小写 L**。
3. **UTF-8-BOM**（文件头 EF BB BF）；不满足会写 error.log。
4. 首行是语言名加冒号（`l_english:`）；所有后续 key 归入该语言数据库，直到下一个数据库行或文件结束。一个文件可含多语言数据库，但文件名要含这些语言名。
5. key 行 `localisation_key:0 "Localisation value"`：key 只能用英文字母、下划线、点、连字符、数字；空格、变音字母、非拉丁文字会破坏其后全部内容（报 `Expected colon(:) at line <...>`）。可选版本号只能由数字组成。值必须用成对直引号（U+0022）包裹且**整条只占一行**；换行用 `\n`（反斜杠，其后别加空格），要输出引号用 `\"`。
6. 有 key 却没有对应语言数据库行，可能触发 `0xC0000005(3221225477)` 崩溃。

### 25.3 `key:0 "值"` 与 `key: "值"`

`0` 是版本号，Paradox 内部翻译追踪用，**游戏从不读取**，可完全省略，语义不变：

```yaml
l_english:
 infantry_equipment: "Infantry Equipment"
 infantry_equipment_short: "Inf. Eq."
 infantry_equipment_desc: "This is infantry equipment"
```

省略后标准 YAML 高亮可能不适配（`key:0` 本身不是合法 YAML）。版本号只能是数字。

### 25.4 覆盖与 `replace` 文件夹

同名 key 重复定义会记进 `logs/text.log`，取值规律不一致，看起来偏向原版文件。放在名为 `replace` 的文件夹里（如 `localisation/english/replace`，仍须在 `localisation` 内）会优先于非 replace 条目——可只覆盖个别 key 而不必整文件复制：

```yaml
l_english:
 POLITICS_ADD_POLITICAL_POWER: "New mana: $VAL|=+0$."
```

### 25.5 颜色代码

格式 `§` + 单字母 + 文本 + `§!`；**结束标记必须写**，否则颜色延续到下一条文本。Windows 下 `Alt`+`21` 输入 `§`。

| 代码 | 效果 | 颜色 |
|---|---|---|
| `§!` | 结束当前格式 | — |
| `§C` | 青色 | (35,206,255) |
| `§L` | 脏橙灰（标称 lilac） | (195,176,145) |
| `§W` | 白 | (255,255,255) |
| `§B` | 蓝 | (0,0,255) |
| `§G` | 绿 | (0,159,3) |
| `§R` | 红 | (255,50,50) |
| `§b` | 黑 | (0,0,0) |
| `§g` | 浅灰 | (176,176,176) |
| `§Y` | 黄 | (255,189,0) |
| `§H` | 黄（header） | (255,189,0) |
| `§T` | 白（Title） | (255,255,255) |
| `§O` | 橙 | (255,112,25) |
| `§0`–`§9`、`§t` | 渐变步进 0–10：紫(203,0,203)、淡紫(128,120,211)、蓝(81,112,243)、灰蓝(81,143,220)、浅蓝(90,190,231)、暗青(63,181,194)、青绿(119,204,186)、浅绿(153,209,153)、橙黄(204,163,51)、白橙(252,169,125)、亮红(255,76,77) | — |

自定义：扩 `interface/core.gfx` 的 `textcolors = { ... }`；颜色 key **不能超过一个字母**，且会覆盖首字母相同的既有 key。也可在字体的 bitmapfont 定义里让某字母在该字体下显示别的颜色。

颜色报错（不含文件名，只能全目录搜）：`Could not find coloring for character 'M'`（某处写了 `§M`；字符是空格则是 `§ `）；`Could not find coloring for character id '17'`（给的是可打印 Unicode 序号；`id '0'` 特指 `§` 后什么都没有，搜 `§"`）；多字节字符游戏只读最后一个字节，报错会指向毫不相干的字符。

### 25.6 变量与格式符

`$VAR$` 四种用法：① 嵌套其他 key（`"$modifier_production_speed_infrastructure_factor$: §R-10%§!"`；写在界面 `pdx_tooltip` 里不生效，要改走 scripted localisation）；② 输出美元符号（`"This option costs $$100"`）；③ 嵌套 **boundable variable**（1.15 起，`"My name is $NAME$."`，由 modder 在 effect / trigger / scripted GUI 里绑定）；④ 嵌套游戏内部变量（只在该 key 内有效，如 `§H$FOCUS_NAME$§!`、`"$OVERLORDADJ$ $NONIDEOLOGY$"`）。

方括号形式 `[?var]` / `[TAG.GetName]` 是 namespace / 变量命令。变量可加格式符（写在 `|` 之后）：

| 格式符 | 作用 |
|---|---|
| `*` 或 `^` | SI 单位（K/M），默认 2 位小数 |
| `=` | 正数加 `+`，负数加 `-` |
| `0`–`9` | 小数位（最多 5） |
| `%` | ×100 并加 `%`，默认 2 位小数 |
| `%%` | 不乘、只加 `%` |
| `+` | 正绿/零黄/负红 |
| `-` | 正红/零黄/负绿 |

未识别符号静默忽略；冲突时最后一个生效；静态颜色优先级低于动态颜色（`[?var|+Y]` 等同 `[?var|+]`）；`%%` 覆盖 `%`。

```yaml
l_english:
 loc_key: "Democratic party popularity: [?party_popularity@democracy|%G0]"
 loc_key_2: "Modifier token's value: [?modifier@my_modifier|.1%%+]"
 pol_power_trigger_tt: "Has more than [?var_name|Y] political power"
```

### 25.7 国旗与文字图标

`@TAG` 在字符串里插国旗（`gfx/flags/TAG.tga`）；不支持 namespace 的场合（自定义 modifier tooltip、game rules）用它，其余优先 `[TAG.GetFlag]`。`£icon_name` 插文字图标，spriteType 定义在 `interface/*.gfx`：

```
	spriteType = {
		name = "GFX_my_text_icon"
		texturefile = "gfx/texticons/filename.dds"
		legacy_lazy_load = no
	}
```

本地化里写 `£my_text_icon`（去掉 `GFX_`）。多帧图标用 `£icon_name|1` 取第 1 帧，**必须** `legacy_lazy_load = no`。

### 25.8 Scripted localisation（`common/scripted_localisation/*.txt`）

```
defined_text = {
    name = mod_scripted_loc
    text = {
        trigger = { tag = FRA }
        localization_key = FRA_localization_key
    }
    text = {
        localization_key = mod_localization_key
    }
}
```

**取第一个 trigger 成立的 `text`**，所以具体的要写在前面；`localization_key` 是**美式拼写 Z**。trigger 里设的临时变量在该 key 显示时仍有效，可运算、可递归。调用：`some_localisation: "[mod_scripted_loc]"`。

随机：

```
defined_text = {
    name = mod_scripted_loc
    text = {
        random_list = {
            30 = { localization_key = mod_localization_key_1 }
            20 = { localization_key = mod_localization_key_2 }
        }
    }
}
```

动态 key：`localization_key = "mod_localization_version_[?my_variable]"`。临时变量显示用双美元符号区分 key 调用：`trillions: "$$[?temp_display_T|2]T"`。

### 25.9 Bindable localisation（1.15+）

```yaml
my_bindable_tooltip: "Hello $NAME|Y$. I am $USRNAME$. Good $TIME$"
```

绑定方式：`custom_effect_tooltip = { localization_key = my_bindable_tooltip NAME = "John" USRNAME = "George" TIME = "Morning" }`，渲染为 `Hello John. I am George. Good Morning.`。可用于 `custom_effect_tooltip`、`custom_trigger_tooltip`、GUI 的 `bound_tooltip`。值可递归成另一个 `{ localization_key = COLOR_YELLOW DATA = "Morning" }`，也可直接引用既有 key（`IDEA_NAME = GER_mefo_bills`）。Localization formatters 用 `<formatter>|<token>`，如 `localization_key = building_state_modifier|dam` 配 `INDENT = "    "`。Context-aware tooltip 用 `context_aware_tooltip`，上下文由游戏代码给，且递归传给子对象。

冷门 key：`WAR_NAME_TAG1_TAG2:""`（TAG1 攻击方、TAG2 防守方，支持 `$FIRST$` / `$SECOND$`，等价各自 `GetAdjective`）；`DIVISION_EXPERIENCE_TITLE_ARMY_EXPERIENCE_0` … `_4`（原版 Brigadier → Lieutenant-General）。

---

## 第 26 章 界面（.gui）

### 界面（Interface）

URL：https://hoi4.paradoxwikis.com/index.php?title=Interface_modding&action=raw

### 26.1 文件组织

- GUI 元素定义在 `interface/*.gui`，整个文件被一个 `guiTypes = { ... }` 块包住。
- `.gui` 只决定"元素摆在哪、怎么排"；给新建元素挂效果要用 scripted GUI（见第 3 节）。原版自带 GUI 的效果是硬编码的，不可直接改行为。
- 渲染顺序 = 文件里的定义顺序：后定义的盖在前面定义的上面。
- 所有非容器元素必须放在容器里，容器可以嵌套。
- Gridbox（`gridBoxType`）用来把同一个容器克隆多次，每份可以给不同参数。

### 26.2 顶层结构骨架

```
guiTypes = {
    containerWindowType = {
        name = "my_container"
        position = { x = 100 y = 100 }
        size = { width = 300 height = 200 }
        orientation = center
        origo = upper_left

        background = {
            name = "Background"
            spriteType = "GFX_tiled_window"
        }

        iconType = { ... }
        instantTextBoxType = { ... }
        buttonType = { ... }
    }
}
```

### 26.3 containerWindowType（容器）

容器 = `containerWindowType = { ... }`。独立容器（不在任何容器里）默认不会在游戏里显示，必须绑到某个功能（scripted GUI 的 `window_name`、新科技文件夹、音乐电台等）。

常用参数（wiki 原字段）：

| 字段 | 含义 |
|---|---|
| `name = "my_container"` | 容器名，用于把功能绑到容器。独立容器名字必须唯一；嵌套容器重名虽然允许，但会破坏 scripted GUI 的 `parent_window_name` 定位 |
| `size = { width = 100 height = 210 }` | 包围盒；可写像素或相对父容器的百分比（独立容器相对整屏）。父容器里的滚动条只用这个 size，不看内部元素 |
| `background = { ... }` | 容器背景；滚动条必须有它才生效。内部 `name = "Background"`、`spriteType = "GFX_tiled_window"` 或 `quadTextureSprite = "GFX_tiled_window_transparent"`（指向 `corneredTileSpriteType`，会自动拉伸适配） |
| `clipping = yes` | 超出包围盒的部分裁掉，默认 yes；滚动条必须为 yes |
| `position = { x = 100 y = 100 }` | 相对 orientation/origo 的像素坐标 |
| `orientation = center` | 坐标原点锚在父容器/屏幕的哪个位置，如 `upper_left`、`center_down`、`lower_right` |
| `origo = center` | 元素自身的基准点 |
| `moveable = yes` | 玩家可以用鼠标拖动该窗口 |
| `fullScreen = yes` | 视为覆盖全屏 |

动画参数：

| 字段 | 含义 |
|---|---|
| `show_position = { x = 300 y = 100 }` | show 动画结束后的屏幕位置 |
| `hide_position = { x = 100 y = 100 }` | hide 动画的目标位置 |
| `show_animation_type = linear` | `decelerated` 或 `linear` |
| `hide_animation_type = accelerated` | `accelerated` 或 `linear` |
| `animation_type = decelerated` | show/hide 用同一类型时的简写；`accelerated`、`decelerated`、`linear` |
| `animation_time = 1000` | 毫秒 |
| `show_sound = menu_open_window` | show 时播放的音效 |
| `hide_sound = menu_close_window` | hide 时播放的音效 |
| `fade_time = 300` | 淡入毫秒数 |
| `fade_type = linear` | `accelerated` 或 `linear` |

### 26.4 滚动（scrollbar）

启用滚动的前提：`size` 在滚动方向上必须用像素（不可用百分比，否则会被拉伸到容纳全部元素）；`clipping` 为 yes 或留空；必须有 `background`。

| 字段 | 含义 |
|---|---|
| `verticalScrollbar = scrollbar_name` | 指定外部 ExtendedScrollbarType 作竖向滚动条；该滚动条定义里不可有 `horizontal = yes` |
| `horizontalScrollbar = scrollbar_name` | 横向滚动条；定义里必须有 `horizontal = yes` |
| `drag_scroll = { left middle right }` | 拖动滚动；同轴必须有滚动条才生效，实测只有 `left` 有效；单键可写成 `drag_scroll = left` |
| `margin = { top = 10 bottom = 10 left = 20 right = 20 }` | 该区域算窗口边框，不受滚动条影响 |
| `autohide_scrollbars = no` | 默认元素放得下就不显示滚动条；设为 no（false）则常驻 |
| `scroll_wheel_factor = 40` | 一格滚轮滚动量 |
| `smooth_scrolling = yes` | 平滑滚动 |

### 26.5 scrollbarType

```
scrollbarType = {
    name = ...
    slider = ...
    track = ...
    leftbutton = ...
    rightbutton = ...
    position = { ... }
    size = { ... }
    priority = ...
    borderSize = { ... }
    maxValue = ...
    minValue = ...
    stepSize = ...
    startValue = ...
    horizontal = 0|1
}
```

字段含义（wiki 原文）：`slider` 滑块按钮、`track` 轨道按钮、`leftbutton`/`rightbutton` 增量按钮、`priority` 相对其他元素的绘制优先级、`maxValue`/`minValue` 控制增量范围、`stepSize` 单次增量、`startValue` 滑块初始大小、`horizontal` 1 横 0 竖。

### 26.6 元素类型

可分三类（wiki 原文分类）：

可以在 scripted GUI 里自由新增并使用：
- `iconType` —— 静态图片
- `instantTextBoxType` —— 文本
- `buttonType` —— 按钮

依赖内部代码（可以加，但不会被数据填充）：
- `smoothListboxType`、`listboxType`、`checkboxType`、`OverlappingElementsBoxType`、`editBoxType`、`shieldtype`

legacy（遗留）：
- `guiButtonType` 等同 `buttonType`；`textBoxType` 等同 `instantTextBoxType`；`eu3dialogtype` 等同 `windowType`；`shieldtype` 只在 `eu3dialogtype` 内使用。

元素默认继承所在容器的 orientation，除非元素自己再写一个。

### 控件类型 1.7–1.9：iconType / instantTextBoxType / buttonType

三类元素字段（★ = 仅该类型有）：

| 字段 | 含义 |
|---|---|
| `name` / `position` / `orientation` | 名字；位置；position 的参考原点 |
| `spriteType` / `quadTextureSprite` / `frame` | 静态 sprite；动态或多帧 sprite（旗帜等）；多帧图用第几帧 |
| `alwaystransparent` | 允许点击穿透（点到它后面的元素） |
| `hint_tag` | hover 时的 hint key |
| `pdx_tooltip` / `pdx_tooltip_delayed` | tooltip / 延迟 tooltip，取 localization key |
| `centerposition` ★icon | position 是否从图标中心算起 |
| `text` / `font` ★text | 显示文本；字体 |
| `maxWidth` / `maxHeight` / `format` / `fixedsize` / `borderSize` ★text | 显示区域像素尺寸；对齐 `left`/`center`/`right`；超界是否截断；边框包围盒 |
| `scrollbarType` ★text | 用哪种滚动条（如 `standardtext_slider`） |
| `buttonText` / `buttonFont` ★button | 按钮文字；按钮字体 |
| `shortcut` / `clicksound` / `oversound` | 快捷键；点击音效；hover 音效（oversound 仅 button） |
| `scale` ★button | 缩放按钮尺寸 |
| `web_link` ★button | 用浏览器打开的 URL |
| `tooltip` / `tooltipText` / `delayedTooltipText` | 从不使用 |

`instantTextBoxType` 里有 `textureFile`——wiki 写明"从不用于任何东西"。部分文本（如 `regiment_count`）由内部代码生成，除非暴露成 localized string，否则改不了。

### 26.10 列表、复选框、编辑框

`smoothListboxType` / `listboxType` 共同字段：`name`、`position`、`orientation`、`size`、`spacing`、`horizontal`（1 横 0 竖）、`scrollbartype`、`bordersize`、`alwaystransparent`；`background` 从不使用。

`checkboxType`：在 `buttonType` 的字段基础上（`name`、`position`、`orientation`、`spriteType`、`quadTextureSprite`、`frame`、`alwaystransparent`、`buttonText`、`buttonFont`、`shortcut`、`clicksound`、`hint_tag`、`pdx_tooltip`、`pdx_tooltip_delayed`、`scale`），实际勾选效果硬编码。

`editBoxType`：`name`、`position`、`orientation`、`text`、`font`、`maxWidth`、`maxHeight`、`format`、`fixedsize`、`borderSize`、`alwaystransparent`、`ignore_tab_navigation`。

`OverlappingElementsBoxType`：`name`、`position`、`orientation`、`size`、`spacing`、`horizontal`、`bordersize`、`alwaystransparent`；`textureFile` 从不使用。

### 26.11 定位与 orientation 合法值

`orientation` 决定锚点：`orientation = UPPER_LEFT` 时 `position = { x = 0 y = 0 }` 就是屏幕/容器左上角；`LOWER_RIGHT` 时是右下角。`position` 是相对该锚点的偏移（`LOWER_RIGHT` 下 x 向左、y 向上）。

合法值（大小写不敏感）：
`CENTER`、`CENTER_UP`（可能等于 `CENTER_UPPER`）、`CENTER_DOWN`（可能等于 `CENTER_LOWER`）、`CENTER_LEFT`、`CENTER_RIGHT`、`UPPER_LEFT`、`LOWER_LEFT`、`UPPER_RIGHT`、`LOWER_RIGHT`。

### 26.12 可用字体

`Arial12`、`Arial12_bold`、`cg_16b`、`cg_18b`、`garamond_12`、`garamond_14`、`garamond_14_bold`、`garamond_16`、`garamond_16_bold`、`garamond_24`、`hoi_16mbs`、`hoi_16tooltip3`、`hoi_18`、`hoi_18b`、`hoi_18mbs`、`hoi_20b`、`hoi_20bs`、`hoi_22tech`、`hoi_24header`、`hoi_26mbs`、`hoi_30header`、`hoi_33`、`hoi_36header`、`hoi4_typewriter16`、`hoi4_typewriter22`、`hoi_mapfont4`、`hoi_arrow_font`、`newsfeed_body`、`newsfeed_title`、`standard`、`standard_18`、`standard_22`、`tahoma_20_bold`、`vic_18`、`vic_18_grey`、`vic_18s`、`vic_22`、`vic_22_bl`、`vic_22s`、`vic_36`、`vic_36s`。

wiki 提醒：部分字体不支持游戏已翻译的所有语言。

### 26.13 替换原版界面元素的实操路径

wiki 给出的可操作路径（Interface 页 + Modding 页合并）：

1. 用 `gui` 控制台命令（等同 debug 模式下主菜单按 ` 键）读出鼠标所指元素的 sprite 名（`GFX_` 前缀）和元素名。
2. 在 `interface/` 目录里全局搜索该名字，定位到定义它的 `.gfx`（sprite 定义，含 `texturefile` 图片路径）或 `.gui`（界面元素）文件。
3. 把该文件复制进 mod 的 `interface/` 同名路径，只改需要改的部分；同名文件按加载顺序覆盖原版（见第 7 节 replace_path 说明）。
4. `reloadinterface` 重载整个界面，或 `reload <单个文件名>` 只重载某个 `.gui`。
5. 换图时只改 `texturefile` 指向的图片文件即可，但要保证 sprite 名不变。

注意：原版元素的点击效果是硬编码的，改 `.gui` 只能改外观与位置；新元素要行为必须写 scripted GUI。

### 26.14 `gui` 命令与相关调试

- `guibounds`（别名 `gui`）：切换 GUI 边界调试，便于测试不同窗口尺寸；同时会给出鼠标所指 sprite（`GFX_` 前缀）与界面元素的名字。这就是定位原版元素定义的入口。
- debug 模式（`-debug` 启动）下，主菜单按 ` 键也能得到同样的界面信息（名称、位置、所用 sprite）。
- hover 任意 GUI 元素按 `Ctrl+Alt+右击`，会弹出调试菜单，可直接跳到定义该元素的那个 GUI 文件（来自 Modding 页 debug 优势列表）。

---

## 第 27 章 图形资源

### 图形资源（Graphical assets）

URL：https://hoi4.paradoxwikis.com/index.php?title=Graphical_asset_modding&action=raw

### 27.1 基本关系

- 图片本身不直接进界面：先在 `interface/*.gfx` 里用 sprite 定义把图片绑到一个脚本名（约定 `GFX_` 前缀），再在 `.gui` 里引用这个脚本名。
- `.gfx` 里的 `texturefile` 路径是相对游戏根目录（`gfx/...`），只用 `/` 分隔。
- 同一资源可按 tag 或 graphical culture 覆盖：`GFX_ENG_<name>` 只对该 tag 生效并覆盖同名基础资源；同理 `GFX_african_<name>`。
- 不需要 `.gfx` 定义的只有：`gfx/flags/` 下的国旗、`gfx/loadingscreens/` 的加载图（但主菜单背景是 sprite 定义的）、角色肖像（可以直接链文件）。
- `.dds` 单文件大小上限约 16MB。

### 27.2 spriteType

```
spriteTypes = {
    spriteType = {
        name = "GFX_<name>"
        texturefile = gfx/interface/folder/filename.dds
        noOfFrames = 5
        effectFile = <path>

        allwaystransparent = <bool>
        legacy_lazy_load = <bool>
        transparencecheck = <bool>

        animation = {
            animationmaskfile = <path>
            animationtexturefile = <path>
            animationrotation = <float>
            animationlooping = <bool>
            animationtime = <float>
            animationdelay = <float>
            animationblendmode = add|multiply|overlay
            animationtype = scrolling|rotating|pulsing
            animationrotationoffset = { x = <float> y = <float> }
            animationtexturescale = { x = <float> y = <float> }
            animationframes = { <int> <int> }
        }
    }
}
```

字段语义：

| 字段 | 含义 |
|---|---|
| `name` | 资源名，可带前缀段（如 idea 图用 `idea` 段） |
| `texturefile` | 图片路径，相对根目录，不含根目录名 |
| `noOfFrames` | 图内帧数。例：`GFX_unit_level` 内含 5 张，写 `noOfFrames = 5` |
| `effectFile` | 图片效果状态（如按钮按下效果），效果在 `gfx/FX/*.lua`；可写多个 |
| `allwaystransparent` | 为 yes 时图片不可点击、无 tooltip |
| `legacy_lazy_load` | 是否惰性加载 |
| `transparencecheck` | 点击判定是否受 alpha 通道约束；否则用图片矩形 |
| `animationmaskfile` | 动画遮罩图 |
| `animationtexturefile` | 动画颜色图 |
| `animationrotation` | 旋转角度，默认 -90 顺时针 |
| `animationlooping` | 是否循环 |
| `animationtime` | 动画时长，秒 |
| `animationdelay` | 循环间隔，秒 |
| `animationblendmode` | `add` / `multiply` / `overlay` |
| `animationtype` | `scrolling` / `rotating` / `pulsing` |
| `animationrotationoffset` | 旋转偏移 x/y |
| `animationtexturescale` | 动画图缩放 |
| `animationframes` | 动画帧数 |

### 27.3 frameAnimatedSpriteType

```
spriteTypes = {
    frameAnimatedSpriteType = {
        name = "GFX_<name>"
        texturefile = "<path>"
        noOfFrames = <int>
        effectFile = "<path>"

        animation_rate_fps = <int>
        looping = <bool>
        play_on_show = <bool>
        pause_on_loop = <float>

        allwaystransparent = <bool>
    }
}
```

`animation_rate_fps` 播放帧率；`looping` 是否循环；`play_on_show` 可见时才开始播；`pause_on_loop` 每次循环后停顿长度；`allwaystransparent` 在 frameAnimated 里定义为"点击判定是否受 alpha 约束，否则用矩形"。

### 27.4 progressbartype

```
spriteTypes = {
    progressbartype = {
        name = "GFX_<name>"
        textureFile1 = "<path>"   # 进度条本体
        textureFile2 = "<path>"   # 进度条背景
        color = { <r> <g> <b> [<a>] }      # 未推进颜色，十进制 RGBA，alpha 可省
        colortwo = { <r> <g> <b> [<a>] }   # 已推进颜色
        size = { x = <int> y = <int> }
        effectFile = <path>
        horizontal = <bool>                 # 默认横向
        steps = <int>                       # 精度/分帧数，默认 100
    }
}
```

### 27.5 corneredTileSpriteType

用于"平铺填充到界面元素尺寸"的九宫格类贴图，容器背景就用它。

```
spriteTypes = {
    corneredTileSpriteType = {
        name = "GFX_<name>"
        texturefile = "<path>"
        noOfFrames = <int>
        size = { x = <int> y = <int> }         # 平铺单元尺寸
        borderSize = { x = <int> y = <int> }   # 边框尺寸
        effectFile = <path>

        allwaystransparent = <bool>
        tilingCenter = <bool>                  # 用中心而不是左上角做平铺基准

        looping = <bool>
        animation_rate_spf = <int>
    }
}
```

### 27.6 maskedShieldType（国家盾徽）

```
spriteTypes = {
    maskedShieldType = {
        name = "GFX_<name>"
        textureFile1 = <path>   # 盾徽背景
        textureFile2 = <path>   # 盾徽遮罩
        effectFile = <path>
    }
}
```

（wiki 该段示例代码块里把块名误写成 `corneredTileSpriteType`，字段列表仍按 maskedShieldType 描述背景+遮罩两张图。）

### 27.7 objectTypes：animatedmaptext

```
objectTypes = {
    animatedmaptext = {
        name = <name>
        speed = <float>
        textblock = {
            text = <string>
            color = { <r> <g> <b> }
            font = <path>
            position = { x = <int> y = <int> }
            size = { x = <int> y = <int> }
            format = <type>
            cull_distance = <float>f
        }
    }
}
```

`name` 不可自定义新的（wiki：不可新增自定义项）；`speed` 是文字淡出时间。

### 27.8 字体定义（bitmapfonts）

`textcolors`：给 localisation 里 `§` 符号配色，`<symbol> = { <r> <g> <b> }`（整数 RGB）。

```
bitmapfonts = {
    bitmapfont = {
        name = <name>
        path = gfx/fonts/<file>
        color = <hex>
        border_color = <hex>
        fontfiles = { <path> <path> }
        textcolors = { <symbol> = { <r> <g> <b> } }
        cursor_offset = { <int> <int> }
    }
}
```

`fontfiles` 用于一个字体多套字图（如同时支持英文与西里尔）；`cursor_offset` 先 x 后 y。

```
bitmapfonts = {
    bitmapfont_override = {
        name = <name>
        fontfiles = { <path> <path> }
        languages = { <language> }
    }
}
```

`bitmapfont_override` 按语言覆盖某字体（`languages` 指定生效语言）。

### 27.9 贴图格式、尺寸、mipmap、alpha

来自 Modding 页 `GFX` 小节（Graphical asset modding 页本身没写格式细节）：

- 多数图片用 `DDS`，通常是 ARGB8（有的图片编辑器叫 A8R8G8B8），**不带 mipmaps**。
- 格式不严格：一般 `DDS`、`TGA`、`PNG`、`BMP` 都能用，只要 sprite 定义里的信息对得上。
- 明确例外：国旗（`gfx/flags/`）必须是 **32-bit TGA、无 RLE 编码、左下原点（bottom-left origin）**；`map/` 目录下的文件同样有专门要求。
- 尺寸必须是 2 的幂：**（wiki 未明确）**。wiki 只在 `.dds` 处给了 16MB 文件上限，以及地图 bmp 的 256 整除/40MiB 限制（见第 7 节）。
- alpha：`transparencecheck` 决定点击判定是否按 alpha 通道；不写就用整张图的矩形。`allwaystransparent` 让整张图不可交互。alpha 与"图透明但仍存在"的排错关系见第 7 节。

### 27.10 命名约定

- sprite 名以 `GFX_` 开头，后面接名字；`GFX_ENG_xxx` / `GFX_african_xxx` 为 tag / graphical culture 专用覆盖。
- 焦点图标必须额外有一张"闪光"图，sprite 名 = 原图标名 + `_shine`，例如 `GFX_focus_icon_shine`（National focus modding 页明确：只认 sprite 名，把定义放进文件名带 `shine` 的文件既不必要也不充分；闪光不生效最常见的原因就是没遵守这个命名）。
- `.gfx` 里路径分隔符必须是 `/`，不可用 `\`。

---

## 第 28 章 scripted GUI

### 脚本化界面（Scripted GUI）

URL：https://hoi4.paradoxwikis.com/index.php?title=Scripted_GUI_modding&action=raw（`Scripted_GUI` 重定向至此）

### 28.1 定位与文件

- 定义在 `common/scripted_guis/*.txt`（目录名必须复数）。
- 写成 `scripted_gui = { <ID> = { ... } }`，块名即内部 ID。
- 作用于 `containerWindowType` 内部的所有元素；容器必须是**完全独立**的容器（不可嵌在别的容器里），否则不可绑定。
- 常用实现手法：按钮点击 set flag，窗口 visible 依赖该 flag。

### 28.2 最小可用模板

```
scripted_gui = {
    <name> = {
        window_name = <string>
        context_type = <type>
        parent_window_token = <string>

        visible = { <triggers> }

        effects = {
            <element>_click = { <effects> }
            <element>_<modifier>_click = { <effects> }
        }

        triggers = {
            <element>_click_enabled = { <triggers> }
            <element>_visible = { <triggers> }
        }

        properties = {
            <element> = {
                image = <string>
                frame = <var>
                x = <var>
                y = <var>
            }
        }

        ai_enabled = { <triggers> }

        ai_test_parent = <string>
        ai_test_interval = <int>
        ai_test_variance = <float>
        ai_test_scopes = <type>

        ai_check = { <triggers> }
        ai_check_scope = { <triggers> }
        ai_max_weight_taken_per_test = <int>

        ai_weights = {
            <element>_<modifiers>_click = {
                ai_will_do = {
                    base = <int>
                    factor = <float>
                    add = <float>
                    modifier = { factor = <float> add = <float> <triggers> }
                }
                ignore_lower_weights = { factor = <float> }
            }
        }
    }
}
```

（另有 `dirty = <variable>` 与 `dynamic_lists = { ... }`，见 3.5 / 3.6。）

### 28.3 window_name / parent window

- `window_name = example_container`：绑定到同名独立容器。绑定后该容器内所有元素（含更深层嵌套容器里的）都受这个 scripted GUI 控制。
- 父窗口两种写法：
  - `parent_window_token = top_bar`：绑到原版以 token 标识的窗口。可用 token 列表（wiki 给出）：`top_bar`、`decision_tab`、`technology_tab`、`trade_tab`、`construction_tab`、`production_tab`、`deployment_tab`、`logistics_tab`、`diplomacy_tab`（未选国家时）、`national_focus`、`politics_tab`、`selected_country_view`、`selected_state_view`、`selected_country_view_info`、`selected_country_view_diplomacy`、`army_ledger`、`navy_ledger`、`civilian_ledger`、`air_ledger`、`tech_infantry_folder`、`tech_support_folder`、`tech_armor_folder`、`tech_artillery_folder`、`tech_land_doctrine_folder`、`tech_naval_folder`、`tech_naval_doctrine_folder`、`tech_air_techs_folder`、`tech_air_doctrine_folder`、`tech_electronics_folder`、`tech_industry_folder`。
  - `parent_window_name = container_name`：绑到指定名字的容器。父容器是独立容器时直接写名字；父容器是嵌套容器时必须加 `_instance` 后缀（如 `politics_anchor_instance`）。`parent_window_name` 不接受被 `gridBoxType` 使用的容器。
- 绑父窗口后：只在父窗口可见时可见、绘制顺序贴在父元素之上、跟随父窗口动画。
- `top_bar` 绘制顺序低于多数弹窗，所以绑 top_bar 的 GUI 会被国策选择、政治页等弹窗遮住；top_bar 容器本身覆盖全屏，因此不会把内容裁掉。
- 常用技巧：在原版窗口内放一个空的"锚"容器（`politics_anchor`），scripted GUI 用 `parent_window_name = politics_anchor_instance` 把内容精确插到指定层级（例如让国家精神盖在脚本 GUI 之上）。

### 28.4 context_type

不写 context 时 UI 拿不到任何游戏状态，不可产生效果也不可动态化（含本地化）。写了任何 context 才能用 effects / triggers / scopes 改状态。

每种 context 中 `ROOT` 恒为"看到这个 GUI 的国家"，默认 scope 随 context 变：

| context_type | 默认 scope 与行为 |
|---|---|
| `player_context` | 基线；默认 scope = 玩家国家（可能由 AI 控制） |
| `selected_country_context` | 默认 scope = 当前选中国家；未选国家则不显示。AI 默认对每个其他国家求值，除非被 `ai_test_scopes` 限制 |
| `selected_state_context` | 默认 scope = 当前选中州；未选州则不显示。AI 默认对每个州求值，除非被限制 |
| `decision_category` | 读一个 decision category 作为 context，以便嵌进其描述；需要 category 上写 `scripted_gui` 属性。此类型不应设父窗口；临时数据结构不保证正常 |
| `diplomatic_action` | 读一个 scripted diplomatic action 作为 context，选中时发给目标；需在 `common/scripted_diplomatic_actions/*.txt` 里绑定 |
| `national_focus_context` | 挂到目标国家的国策视图 |
| `country_mapicon` | 世界地图上每个国家旁边显示；默认 scope = 该国家 |
| `state_mapicon` | 世界地图上每个州旁边显示；默认 scope = 该州 |

默认 scope 不等于 ROOT 时，用 `PREV` 回指。

### 28.5 dirty

``` 
 dirty = example_variable
```

默认每个 tick 刷新，大 GUI 很吃性能。用 dirty 变量后只在变量值变化时刷新。注意：dirty 只影响属性刷新，不影响 GUI 本身的可见性。

### 28.6 effects（按钮点击）

`<element>_click = { ... }`；可在 `click` 前叠加修饰键，可串联：

- `right`、`alt`、`control`、`shift`

例：`my_button_alt_right_click = { }`。

### 28.7 triggers（可点/可见）

- `<element>_<modifiers>_click_enabled`：该元素是否可点。
- `<element>_click_enabled` 会覆盖更具体的 `<element>_right_click_enabled`。
- `<element>_visible`：该元素是否可见，任何界面元素都能用（图标、文本）。
- 元素不可见时 AI 也点不到。

triggers 里还能设临时变量/临时数组，供 `properties` 与 `dynamic_lists` 使用：

```
triggers = {
    my_temp_array_calculator_click_enabled = {
        clear_temp_array = my_temp_array
        all_of = {
            array = my_array
            add_to_temp_array = { my_temp_array = v }
        }
    }
    my_element_click_enabled = {
        if = { limit = { has_completed_focus = my_focus } set_temp_variable = { my_temp_var = 1 } }
        else = { set_temp_variable = { my_temp_var = 2 } }
    }
}
properties = {
    my_element = { frame = my_temp_var }
}
dynamic_lists = {
    my_gridbox = {
        array = my_temp_array
        entry_container = "my_entry_container"
    }
}
```

### 28.8 dynamic_lists + gridBoxType

数组每个元素在同一名字的 gridbox 位置各画一份 `entry_container` GUI。

```
dynamic_lists = {
    Example_Grid_Box = {
        array = Example_Array      # 每个 index 调一次 GUI
        value = v                  # 当前值，默认 v
        index = i                  # 当前下标，默认 i
        change_scope = no          # yes 则 scope 切到该值
        entry_container = "Example_GUI_Array"
    }
}
```

对应 `.gui` 里 gridbox 写法（wiki 例子）：

```
gridBoxType = {
    name = "Example_Grid_Box"
    position = { x = 50 y = 0}
    size = { width = 100% height = 100% }
    Orientation = upper_left
    slotsize = { width = 400 height = 50 }
    format = "UPPER_LEFT"
    max_slots_horizontal = 1
    #max_slots_vertical = 1
}
```

条目容器里用 `[?v]` / `[?i]` 显示当前值与下标，例如 `buttonText = "v: [?v] i: [?i]"`。

### 28.9 properties

运行时改元素的贴图、帧、坐标：

```
properties = {
    my_icon = {
        image = "GFX_my_texture"   # 也可用 scripted localisation: "[get_my_icon_texture]"
        frame = <var>
        x = <var>
        y = <var>
    }
}
```

`image` 接受 scripted localisation 字符串，因此可以用 `defined_text` 按条件给出不同 `GFX_` 名：

```
defined_text = {
    name = get_my_icon_texture
    text = { trigger = { <triggers> } localization_key = "GFX_my_texture_1" }
    text = { trigger = { <triggers> } localization_key = "GFX_my_texture_2" }
}
```

### 28.10 AI 相关

| 字段 | 语义 |
|---|---|
| `ai_enabled = { <triggers> }` | 初始化时检查一次，失败就永不再检查（最优化的写法，但只查一次） |
| `ai_test_interval = <int>` | 检查间隔（小时），默认 24 |
| `ai_test_variance = <float>` | 间隔波动百分比（上下各除以 2），默认 0.2。100 配 0.2 → 每 90–110 小时检查一次 |
| `ai_check = { <triggers> }` | 每个间隔 tick 检查，false 则该 tick 忽略此 GUI |
| `ai_test_scopes = <type>` | AI 的目标范围。不写会遍历所有国家/州，性能很差 |
| `ai_check_scope = { <triggers> }` | 对目标做过滤 |
| `ai_weights` | 每个可点元素一组 `ai_will_do`；权重 > 0 才会尝试点击 |
| `ai_max_weight_taken_per_test = <int>` | 默认每 tick 只点一个（分数最高的）；此值放宽动作数量上限 |
| `ai_test_parent = <string>` | 让多个 scripted GUI 的 AI 一起处理（共享资源时限制更准确） |
| `ignore_lower_weights = { factor = <float> }` | 权重大于 0 时忽略权重更低的动作，便于"攒资源" |
| `ai_will_do` 内 `weight` | 动作成本，默认每动作权重 1 |

`selected_country_context` 的 `ai_test_scopes` token：`test_self_country`、`test_enemy_countries`、`test_ally_countries`、`test_neighbouring_countries`、`test_neighbouring_ally_countries`、`test_neighbouring_enemy_countries`。

`selected_state_context` 的 token：`test_self_owned_states`、`test_enemy_owned_states`、`test_ally_owned_states`、`test_self_controlled_states`、`test_enemy_controlled_states`、`test_ally_controlled_states`、`test_neighbouring_states`、`test_neighbouring_enemy_states`、`test_neighbouring_ally_states`、`test_our_neighbouring_states`、`test_our_neighbouring_states_against_allies`、`test_our_neighbouring_states_against_enemies`、`test_contesded_states`（原文拼写如此）。

另可加 `test_if_only_major`（只限主要国家/其拥有的州）、`test_if_only_coastal`（只限沿海国家/州）。

### 28.11 脚本本地化与已知坑

- tooltip 里显示某元素效果：`[!<element>_<action>]`，例 `MY_TOOLTIP: "[!test_button_click]"`。
- 显示该元素触发器判断：`[!<element>_<action>_enabled]`，例 `MY_TOOLTIP: "[!test_button_click_enabled]"`。
- `human_ai` 命令让 AI 接管玩家国家，并把脚本 GUI 的 AI 检查与结果写进 `scripted_ai.log`。
- **event target 在 scripted GUI 里不可用，会连锁破坏一切**；改用 variable scope。
- scripted effects / scripted triggers 可以用，适合把 GUI 逻辑与玩法逻辑分离。

---

## 第 29 章 AI

### AI

URL：https://hoi4.paradoxwikis.com/index.php?title=AI_modding&action=raw

### 29.1 MTTH 块与 ai_will_do 权重语义

- MTTH 块在 `common/mtth/`，用于给"国家能否拿到某国策""事件平均触发时间""某数据库条目的 AI 权重"等赋动态值。
- 多数场景（标 `ai_will_do`）的做法：在 0 与该块值之间取一个十进制随机数，取最高者；之后再乘上 AI strategy plans 或 defines 里的修正。
- 事件选项用 `ai_chance`，按概率-规模比例抽样，最终以 d00 掷骰决定，因此概率只能是 1/100 的整数倍；各选项权重和不必是 100。例：一个选项 1、另一个 999，前者被选中概率是 1%，不是 0.1%。
- 起始假设值 = 1，然后：
  - `base = 10`：直接把值设为 10（相当于乘 0 再加 10），通常写在最前；
  - `add = 5`：加；
  - `factor = 0.3`：乘。
- 条件修正用 `modifier = { ... }`，它同时是 trigger 块，默认 scope（也是 ROOT）= 被求值的国家；部分 MTTH 块另有 FROM / FROM.FROM。
- 值修正参数可以写在 `modifier` 内任何位置（开头、中间、末尾都行）。
- 可以用变量；若在 `modifier` 里定义临时变量再用于值修正，该修正必须写在使用之后。

示例（wiki 原样）：

```
ai_will_do = {
    base = 10.5
    modifier = { tag = GER factor = 0 }
    modifier = { is_major = yes add = 1 }
    modifier = { factor = 3 add = 2.5 tag = FRA }
    factor = 2
    modifier = {
        set_temp_variable = { t = num_of_civilian_factories }
        add_to_temp_variable = { t = num_of_military_factories }
        divide_temp_variable = { t = 10 }
        round_temp_variable = t
        add = t
    }
}
```

结果（GER、FRA 均为主要国家）：GER 0；FRA 74；其他主要国家 23；小国 21。之后再加上"（民用+军用工厂数）/10 取整"——FRA 43 厂 → +4，合计 78。

### 29.2 ai_strategy（common/ai_strategy/*.txt）

策略条目块名任意（可重复），只出现在 AI dump 里；若影响外交选项，玩家 hover 会看到 `COUNTRY has strategic reasons to be ...`。

```
BHR_invade_qatar = {
    allowed = { original_tag = BHR }
    enable = { country_exists = QAT }
    abort = { has_war_with = QAT }
    abort_when_not_enabled = yes
    ai_strategy = {
        type = invade
        id = QAT
        value = 200
    }
}
```

条目级参数：

| 参数 | 语义 |
|---|---|
| `allowed = { ... }` | **只在开局检查一次**，永久允许/禁止该策略。通常只放国家检查（`tag = OMA`）或永不可变的 DLC 检查 |
| `enable = { ... }` | 启用条件，持续检查；默认不满足不会取消已生效的策略 |
| `abort_when_not_enabled = yes` | 让 `enable` 不满足时取消策略 |
| `abort = { ... }` | 满足即移除策略；不满足时也不会被添加 |
| `ai_strategy = { type = ... }` | 实际策略，唯一公共参数是 `type` |

反向策略（`reversed = yes`）：把 `id = TAG` 的方向翻转——策略变成"TAG 对满足 `enable` 的国家生效"。还需要 `enable_reverse = { ... }`（没有默认 scope，必须自己 scope 进国家）。

```
BHR_support_neutrals = {
    allowed = { NOT = { original_tag = BHR } }
    enable = { has_government = neutrality }
    enable_reverse = { BHR = { has_government = neutrality } }
    reversed = yes
    abort_when_not_enabled = yes
    ai_strategy = { type = support id = BHR value = 100 }
}
```

上例若不写 `reversed = yes`，会变成"每个中立国都支持 BHR"；写了才是"BHR 支持每个中立国"。

`value` 可正可负，负值降低 AI 的意愿。

`add_ai_strategy` effect 可以在任意 effect 块里加永久策略；`common/ai_strategy/*.txt` 里的则是自动开关的。完整策略清单在游戏本体 `common/ai_strategy/documentation.info`。

wiki 表格列出的 `type`（68 个，按 wiki 顺序）：

`alliance`、`antagonize`、`asking_foreign_garrison`、`befriend`、`conquer`、`consider_weak`、`contain`、`declare_war`、`diplo_action_acceptance`、`diplo_action_desire`、`dont_join_wars_with`、`ignore`、`ignore_claim`、`protect`、`support`、`send_lend_lease_desire`、`send_volunteers_desire`、`invade`、`naval_invasion_focus`、`prepare_for_war`、`area_priority`、`strategic_air_importance`、`dont_defend_ally_borders`、`force_defend_ally_borders`、`front_armor_score`、`front_control`、`force_concentration_front_factor`、`front_unit_request`、`invasion_unit_request`、`garrison`、`garrison_reinforcement_priority`、`ignore_army_incompetence`、`put_unit_buffers`、`spare_unit_factor`、`theatre_distribution_demand_increase`、`naval_avoid_region`、`naval_convoy_raid_region`、`naval_mission_threshold`、`strike_force_home_base`、`agency_ai_base_num_factories_factor`、`agency_ai_per_upgrade_factories_factor`、`intelligence_agency_branch_desire_factor`、`intelligence_agency_usable_factories`、`operation_equipment_priority`、`operative_mission`、`operative_operation`、`become_spymaster`、`added_military_to_civilian_factory_ratio`、`air_factory_balance`、`dockyard_to_military_factory_ratio`、`railway_gun_divisions_ratio`、`build_building`、`building_target`、`factory_build_score_factor`、`equipment_production_factor`、`equipment_production_min_factories`、`equipment_variant_production_factor`、`equipment_stockpile_surplus_ratio`、`build_army`、`force_build_armies`、`production_upgrade_desire_offset`、`role_ratio`、`unit_ratio`、`min_wanted_supply_trains`、`min_wanted_supply_trucks`、`scorched_earth_prio`、`land_xp_spend_priority`、`pp_spend_amount`、`pp_spend_priority`、`research_weight_factor`。

重点类型的参数（wiki 表格原文摘要）：

- `invade`：`value`、`id = <country>` —— 让 AI 对该国组织登陆。
- `area_priority`：`value`、`id = <AI area>` —— 在该 AI area 放更多部队。
- `strategic_air_importance`：`id = <strategic_region>`、`value` —— 改该战略区的"Strategic Importance"分（AI 用它排空袭优先级）。战略区 ID 可在 `map/strategicregions/*.txt` 或游戏内 `tdebug` 查；分数用 `observe` + `aiview` + Strategic Air 地图模式看；分数规模常在数万到十几万。
- `front_control`：`state` / `tag` / `strategic_region` / `area` / `country_trigger` / `state_trigger`、`ratio`（启用所需的战线占比，默认 0）、`priority`（冲突时高者生效）、`ordertype = front|invasion`、`execution_type = careful|balanced|rush|rush_weak`（仅 front）、`execute_order = <bool>`、`manual_attack = <bool>`（默认 true，仅 front）。多个目标类型同时写则必须全部满足；只改已有战线的命令，不改分到该战线的兵力数量。
- `dont_defend_ally_borders` / `force_defend_ally_borders`：`id = <country>`（后者也接受 AI area）；前者是严格二元——总值正数就绝不放兵。
- `protect`：总值负数 → AI 永不保障该国。
- `diplo_action_acceptance` / `diplo_action_desire`：多一个 `target = <diplomatic action>`；外交动作名通常来自 `localisation/english/diplomacy_l_english.yml` 的标题 key（`DIPLOMACY_SEND_VOLUNTEERS_TITLE` → `send_volunteers`）。
- `ignore_claim`：值当布尔用（写 1）。
- `role_ratio`：决定 AI 想要每个 role 多少师。
- `front_control` / `force_concentration_front_factor` 的目标可用 `state`、`strategic_region`、`area`、`country_trigger`、`state_trigger`，可写多个。

### 29.3 ai_areas（common/ai_areas/*.txt）

只被部分 ai_strategy 使用（如 `area_priority`）。一个省可以属于多个 area，也可以不属于任何 area。debug 模式下 hover 省份可看到所属 area。

```
my_ai_area = {
    continents = {
        europe
        africa
    }
    strategic_regions = {
        53  # Caribbean
        189 # Burma
    }
}
```

- `continents`：大陆名（`map/continent.txt` 定义，`map/definition.csv` 分配给省），要写**全名**而不是省定义里的 ID。
- `strategic_regions`：战略区 ID 列表。
- 多个来源并列时，省属于其中任意一个即可。

### 29.4 ai_focuses（common/ai_focuses/*.txt）

告诉游戏：AI 当前走的国策会影响它选哪些科技类别、哪些国策（本页只有一句，细节在独立页 `AI focuses`）。

### 29.5 ai_strategy_plans（common/ai_strategy_plans/*.txt）

用于按形势给 AI 定优先级的"计划"：选顾问、选科技、套 ai_strategy、定国策路线。一个国家的多个计划可同时生效。

计划级参数：

| 参数 | 语义 |
|---|---|
| `name = "..."` / `desc = "..."` | 只给 `aiview` 用，不给玩家看，无需本地化 |
| `allowed = { ... }` | **只在开局检查一次**（限制国家、DLC） |
| `enable = { ... }` | 每天检查；一旦满足即绑定到该 AI（之后变 false 也不解除）。常用 `has_game_rule`、`is_historical_focus_on`，随机性靠 `on_startup` + `random_list` 设国家 flag |
| `abort = { ... }` | 每天检查，满足则停止使用该计划；且必须为 false 计划才能被选中 |
| `ai_national_focuses = { TAG_focus_name_1 TAG_focus_name_2 }` | 国策顺序表（空格分隔）。按顺序尝试，取不到的跳过；跟顺序时**忽略** `ai_will_do` 值；全部不可用时才回落到 `ai_will_do` |
| `focus_factors = { TAG_focus_name = 3 }` | 给指定国策的 `ai_will_do` 乘系数（再乘计划 weight）。写 0 即永不选该焦点（除非写进 `ai_national_focuses`） |
| `research = { artillery = 3 }` | 给某科技类别内所有科技的 `ai_will_do` 乘系数 |
| `ideas = { ... }` / `traits = { ... }` | 同格式；ideas 针对单个 idea（法律、设计局）或顾问（用 idea_token），traits 针对国家领袖特质 |
| `ai_strategy = { ... }` | 计划启用时套用的 ai_strategy |
| `weight = { ... }` | MTTH 块，给整个计划一个总权重，乘到计划内每个 factor 上（如 1.25 会把 4 变 5） |

示例（wiki 原样，两条计划）：

```
BHR_historical = {
    name = "Historical plan for BHR"
    desc = "4 focuses in a specific order"
    allowed = { tag = BHR }
    enable = {
        OR = {
            AND = {
                is_historical_focus_on = yes
                has_game_rule = { rule = BHR_ai_behavior option = DEFAULT }
            }
            has_country_flag = BHR_AI_RANDOM_HISTORICAL
            has_game_rule = { rule = BHR_ai_behavior option = HISTORICAL }
        }
    }
    abort = {
        OMA = {
            OR = { has_government = fascism has_government = communism }
        }
    }
    ai_national_focuses = {
        BHR_focus_name_1
        BHR_focus_name_2
        BHR_focus_name_3
        BHR_focus_name_4
    }
    ideas = { BHR_advisor = 3 }
    traits = { fascist_demagouge = 0 }
    ai_strategy = { type = invade id = OMA value = 200 }
}
BHR_alternate = {
    name = "Alternative plan for BHR"
    desc = "AI is just set to never do BHR_focus_name_2 and be more likely to do BHR_focus_name_5, especially if after 1937"
    enable = {
        OR = {
            has_country_flag = BHR_AI_RANDOM_ALTERNATE
            has_game_rule = { rule = BHR_ai_behavior option = ALTERNATE }
        }
    }
    focus_factors = { BHR_focus_name_2 = 0 BHR_focus_name_5 = 2 }
    weight = { modifier = { factor = 2 date > 1937.1.1 } }
    research = { artillery = 2 }
}
```

### 29.6 ai_templates（common/ai_templates）

AI 升级师编制时追求的"目标模板"（target template）。按 role 组织，一个 role 可有多个目标模板，AI 按脚本优先级选一个作为"currently targeted template"，然后拿现有师模板算 match score（100% = 1.0），升级时**复制**最匹配的模板再改（AI 从不原地改模板）。

role 级参数：

| 参数 | 语义 |
|---|---|
| `role =` | 目标 role token，由脚本定义，被 `role_ratio` 策略引用 |
| `blocked_for = { ... }` | 限定哪些国家用这个 role 条目；与 `available_for` 二选一，两个都用或都不用行为未定义。一般每个国家每个 role 只应有一个 role 条目 |
| `upgrade_prio = { ... }` | MTTH 块，AI 选"升哪个 role"时按权重随机；设 0 即不花 XP 升级该 role。例：A/B/C 的 upgrade prio 为 1/2/1 → 概率 25%/50%/25% |
| `enable = { ... }` | 可选，国家 scope；false 时视作该目标模板不存在 |

目标模板级参数：

| 参数 | 语义 |
|---|---|
| `reinforce_prio =` | 补充优先级，驻军类用 0，精锐用 2，默认 1 |
| `custom_icon =` | 是否给结果模板用自定义图标 |
| `division_names_group =` | 师名组，默认沿用"分叉来源"的模板 |
| `upgrade_prio = { ... }` | 决定哪个目标模板成为当前目标（确定性，无随机） |
| `enable = { ... }` | 可选，国家 scope |
| `can_upgrade_in_field = { ... }` | 可选，国家 scope；决定是否允许在战场上升级匹配该模板的师 |
| `target_template = { support = { ... } regiments = { ... } }` | 模板本体：想要的支援连与线列团，研究允许时 AI 会加 |
| `replace_at_match =` / `replace_with =` / `target_min_match =` | 替换链：当前目标匹配度 ≥ `replace_at_match`，且最佳匹配与 `replace_with` 目标之间的匹配度 ≥ `target_min_match` 时，把当前目标换成 `replace_with` |

同 `upgrade_prio` 的两个目标模板，排前面的优先（顺序有意义）。

```
infantry_generic = {
    blocked_for = { GER JAP }
    role = infantry
    upgrade_prio = { factor = 1 modifier = { factor = 5 } }

    infantry_1 = {
        reinforce_prio = 0
        custom_icon = 7
        division_names_group = GER_MEC_01
        upgrade_prio = { factor = 1 modifier = { factor = 1.5 } }
        enable = { date < 1940.3.14 }
        can_upgrade_in_field = { has_equipment = { infantry_equipment > 3000 } }
        target_template = {
            support = { engineer = 1 anti_air = 1 artillery = 1 }
            regiments = { infantry = 6 }
        }
        replace_at_match = 0.9
        replace_with = infantry_2
        target_min_match = 0.9
    }

    infantry_2 = {
        upgrade_prio = { factor = 1 modifier = { factor = 1 } }
        target_template = {
            support = { engineer = 1 recon = 1 field_hospital = 1 anti_air = 1 anti_tank = 1 }
            regiments = { infantry = 9 artillery_brigade = 2 }
        }
    }
}
```

### 29.7 ai_equipment（common/ai_equipment/*.txt）

定义 AI 给坦克/舰船挂模块时追求的具体variant。

role 模板级：`category = <land|naval|air>`、`roles = { ... }`（供 `role_ratio` 用）、`available_for`、`blocked_for`、`priority`（MTTH，决定花经验改哪个）。

设计级：`name`（设了才能作预设用）、`role_icon_index`（仅舰船，图标在 `gfx/army_icons/army_icons.txt` 的 `naval_equipment_role`）、`priority`、`enable`、`allowed_types`（不列出的子单元永不添加）、`target_variant`（`match_value`、`type`、`modules` 每槽位要求、`upgrades`）、`requirements`、`allowed_modules`。

槽位要求写法：`main_armament_slot = tank_flamethrower`（可写模块类别、具体模块或 `empty`）；用 `>` / `<` 表示"更新/更旧"的模块（按模块年份）；`empty` 配 `>` 表示"必须非空"。也可写 `{ module = ... any_of = { ... } upgrade = current }`。

```
BHR_light_tanks = {
    category = land
    available_for = {BHR}
    roles = { land_light_tank }
    priority = { factor = 1000 }

    great_war_tank_default = {
        priority = {
            factor = 1
            modifier = { has_tech = basic_light_tank_chassis factor = 0 }
        }
        target_variant = {
            match_value = 1000
            type = light_tank_chassis_0
            modules = {
                main_armament_slot = tank_heavy_machine_gun
                turret_type_slot = tank_light_one_man_tank_turret
                suspension_type_slot = tank_bogie_suspension
                armor_type_slot = tank_riveted_armor
                engine_type_slot = tank_gasoline_engine
                special_type_slot_1 = empty
                special_type_slot_2 = empty
                special_type_slot_3 = empty
                special_type_slot_4 = empty
            }
            upgrades = {
                tank_nsb_engine_upgrade = 3
                tank_nsb_armor_upgrade = { base = 1 modifier = { add = 1 has_war = yes } }
            }
        }
        allowed_modules = {
            tank_heavy_machine_gun
            tank_light_one_man_tank_turret
            tank_bogie_suspension
            tank_riveted_armor
            tank_gasoline_engine
        }
    }
}
```

---

## 第 30 章 控制台命令

### 控制台命令（Console commands）

URL：https://hoi4.paradoxwikis.com/index.php?title=Console_commands&action=raw

### 30.1 打开方式与前提

- 非铁人局可用 `^`、`°` 或 `~` 打开控制台（随键盘布局不同）；up/down 翻历史命令。
- 部分命令再执行一次可关闭；有时需重载存档或重启游戏。
- **必须用 `-debug` 启动游戏才能用控制台**（wiki 原文）。
- 控制台快捷键也可为 Shift+2、`§`、`\`、`` ` ``、`"`、`º`、`Alt+2+1`、Shift+3。
- 参数写法约定：`command(alias)` 括号内是别名；`[arg]` 是可选参数；`[<arg>]` 是必填参数。
- `debug` 控制台命令只给"最后 4 项 debug 优势"（见第 6 节）；启动项 `-debug` 给全部。

### 30.2 常用命令

| 命令 | 参数 | 用途 |
|---|---|---|
| `help` | `[command name]` | 列出全部命令或某命令说明 |
| `tag` | `[<Country tag>]` | 切换控制的国家 |
| `event` | `[<event id>] [Target country tag]` | 触发事件；若事件有 `trigger` 会回报哪些满足/不满足 |
| `finish_decision` | `[<decision id>]` 或 `all` | 立刻完成限时任务 |
| `add_ideas` | `[<idea name>]` | 加 idea（可替换法律） |
| `remove_ideas` | `[<idea name>]` | 移除 national idea |
| `energy_ratio`（`er`） | `[<ratio>]` | 设置 0–1 的能源比例（不耗煤工厂） |
| `FI` | `[amount}` | 加阵营主动权（`FI 5` 加 5） |
| `mastery` | `[<mastery amount>], [track name]` | 给学说掌握度，全局或指定 track |
| `gain_xp` | `[<amount>]` | 给选中将领经验（`gain_xp 100000`，等级上限 9） |
| `gain_xp` | `[<trait>]` | 给选中将领可获得的特质（如 `gain_xp seawolf`；对新建通用将领需改存档 `max_traits=0.000` 后补 `in_progress={...}` 块并以 ANSI 保存） |
| `cp` | `[<amount>]` | 加指挥点（上限 100） |
| `st` | `[<amount>]` | 加稳定度（上限 100） |
| `add_war_support`（`ws`） | `[<amount>]` | 加战争支持度（上限 100） |
| `reduce_opinion` | `[<country tag>]` | 降低双向好感 |
| `allowtraits` | — | 自由分配将领特质 |
| `add_equipment`（`ae`） | `[<amount>] [<equipment name>]` | 加装备（只限已研究、不支持海军装备，运输船除外 `ae 1000 convoy_1`；改型装备要写全名） |
| `add_latest_equipment`（`ale`） | `[<amount>]` | 给最新型号装备 |
| `addfunds` | — | 所有 MIO 加 1000 资金 |
| `addTaskCapacity` | `[number]`（或 `[<MIO id>] [number]`） | 给 MIO 加任务容量，默认 1 |
| `addSize` | `[number]`（或 `[<MIO id>] [number]`） | 给 MIO 加特质点，默认 1 |
| `add_cic_bank` | `[number]` | 国际市场加经济容量盈余，默认 1 |
| `whitepeace`（`wp`） | `[<country tags>]` | 与指定国家白和 |
| `teleport`（`tp`） | — | 开启传送工具（选部队后右击省份） |
| `allowdiplo`（`adiplo`,`nocb`） | — | 无视规则使用所有外交动作（无理由宣战） |
| `debug_crash`（`crash`） | — | 让游戏崩溃 |
| `instantconstruction`（`ic`） | — | 瞬时建造（影响 AI，舰船也瞬时） |
| `research` | `[<slot id>]` 或 `all` | 研究某槽位或全部科技 |
| `research_on_icon_click`（`roic`） | — | 点科技树图标即研究（可跳过前置/互斥） |
| `toggle_hidden_techs`（`tht`） | — | 显示/隐藏隐藏科技 |
| `sp_breakthrough`（`sp_br`） | `[<number>]`，可加 `<specialisation>` | 加特殊项目突破点（`sp_br 20 specialization_land`）；specialization 有 `specialization_land` / `specialization_air` / `specialization_naval` / `specialization_nuclear`（mod 的在 `common/special_projects/specialization`） |
| `sp_fast` | — | 跳过原型阶段、推进迭代阶段 |
| `sp_instant` | — | 自动完成当前特殊项目 |
| `sp_available` | — | 解锁/锁定有未满足研究前置的特殊项目 |
| `sp_unlock_all` | — | 所有特殊项目始终可见可用 |
| `sp_research_all`（`sp_ra`） | — | 研究所有特殊项目（无科学家则创建一个） |
| `sp_prototype_reward` | — | 触发指定原型奖励 |
| `sp_add_scientist` | `[<level>] [<specialisation>]` | 加通用科学家（`sp_add_scientist 3 nuclear`） |
| `sp_add_mastermind` | — | 加全专精满级科学家 |
| `sp_set_selected_scientist_level` | `[<level>]` | 设科学家等级（须打开设施界面） |
| `sp_add_selected_scientist_trait` | `[<trait>]` | 给科学家加特质（特质在 `common/scientist_traits/00_traits.txt`） |
| `annex` | `[<Target Country Tag>]` 或 `all` | 吞并（`annex USA`、`annex d01`、`annex all`） |
| `puppet` | `[<Puppeteer>] [<Puppet Target>]` | 设为傀儡（`puppet GER CZE`） |
| `manpower` | `[amount]` | 加人力，默认 1000 万 |
| `add_opinion` | `[<Country tag>]` | 双向加 100 好感 |
| `add_legitimacy` | `[<Country tag>] [<value>]` | 加合法性（`add_legitimacy POL 22`） |
| `observe`（`spectator`） | — | 不控制任何国家（会干扰 AI 表现） |
| `tdebug` | — | 开调试信息（查 tag、ID） |
| `occupationpaint`（`op`） | `[tag]` | 切换占领着色，带 tag 时给其全部拥有地着色 |
| `setowner` | `[<country tag>]` | 设州归属（用点击选州） |
| `setcontroller` | `[<country tag>] [province id]` | 设省控制者 |
| `xp` | `[<XP amount>]` | 加陆海空经验（每天一次） |
| `pp`（`fuhrer_mana`,`political_power`） | `[PP amount]` | 加（或减）政治点，默认 1000 |
| `fuel` | `[<amount>]` | 加油，超容量反而减少 |
| `civilwar` | `[<ideology>] [<target country tag>]` | 引发内战（`civilwar fascism ENG`；可用 `communism`/`democratic`/`neutrality`） |
| `add_party_popularity` | `<ideology group> <value>` | 加政党支持度（原版组名简写 `d f n c`） |
| `set_ruling_party` | `<ideology group>` | 设执政党 |
| `Focus.AutoComplete`（`fa`） | — | 国策瞬时完成（影响 AI） |
| `Focus.NoChecks` | — | 忽略国策条件（影响 AI） |
| `Focus.IgnorePrerequisites` | — | 忽略国策前置（影响 AI） |
| `freefocuses`（`ff`） | — | 上述三条的组合 |
| `Decision.FastRemove` | — | 决议缩短到 1 天 |
| `Decision.NoChecks` | — | 忽略决议条件（同时免花费，影响 AI） |
| `instant_prepare` | — | 瞬时准备登陆（仅 debug 模式） |
| `instanttraining`（`it`） | — | 瞬时训练师与舰（影响 AI） |
| `nuke` | `[number]` | 加核弹 |
| `ai_accept`（`yesman`） | — | AI 接受一切外交提议 |
| `add_core` | `<state_id>` | 加核心 |
| `Agency.Instant` | — | 情报局全瞬时（等同上四条组合） |
| `Agency.InstantSlotUnlock` | — | 特工招募无冷却 |
| `Agency.Autocomplete` | — | 瞬时完成情报局升级 |
| `prevent_operative_detection` | — | 特工永不被发现 |
| `force_operative_detection` | — | 特工必被发现 |
| `Operation.instant` | — | 瞬时完成所有行动（影响 AI） |
| `agency.keepexcessoperatives` | — | （wiki 无说明） |
| `deleteallunits`（`delall`） | `[country]` | 删指定国家全部陆军与舰队 |
| `deleteallunitsbut`（`delallbut`） | `[country]` | 删所有国家军队，仅保留一个 |
| `add_autonomy` | `[<Target Country Tag>] [num]` | 改自治度（`add_autonomy PHI -200`） |
| `resistance` | — | 提高选中省抵抗度 |
| `compliance` | — | 提高选中省顺从度 |
| `add_intel` | `[<Tag1>] [Tag2]` 或 `[<Tag>]` + `army=20` 等 | 设情报（永久静态值）；可写 `civilian,army,navy,airforce` |
| `add_mines` | — | 把玩家在选中海域的水雷拉满 |
| `acclimization` | `[<climate type>] [<number>]` | 设选中师对某气候的适应度（同时把相反气候归零） |
| `debug_smooth` | — | 切换帧平滑（通常提速 10–35%） |

### 30.3 改 mod 时有用的命令

| 命令 | 参数 | 用途 |
|---|---|---|
| `guibounds`（`gui`） | — | GUI 边界调试；给出鼠标所指 sprite 名与界面元素名，用来反查定义文件 |
| `set_var` | `[<variable>] [<value>]` | 改变量值 |
| `get_var` | `[<variable>]` | 控制台打印变量值 |
| `list_vars` | — | 列出当前 scope 的变量 |
| `set_country_flag` | `[<Country Flag>]` | 给当前国家加 flag（带别国 tag 无效） |
| `set_global_flag` | `[<Global Flag>]` | 加全局 flag |
| `list_flags` | — | 列出当前生效 flag（按当前 scope 区分 global/country/state） |
| `fast_forward` | `[<days>], [observer]` | 快进指定天数 |
| `list_hidden_focuses` | — | 列出某国隐藏国策 |
| `show_focuses` | — | 显示所有隐藏国策 |
| `trigger` | `[<scripted_trigger_name>]` | 检查 scripted trigger 真假 |
| `eval_trigger` | `[<trigger code block>]` | 在当前 scope 求值一段 trigger 代码 |
| `effect`（`e`） | `[<scripted_effect_name>]` | 在当前 scope 执行 scripted effect |
| `eval_effect` | `[<effect code block>]` | 在当前 scope 执行一段 effect 代码（如 `eval_effect load_focus_tree = german_focus`） |
| `ai` | `[country tag...]` | 开关 AI（无参数=所有国家；带参数=对列出的国家取反）；可用来确认崩溃是否 AI 相关 |
| `aiview` | — | 开 AI 调试信息 |
| `human_ai` | — | 让 AI 与玩家共同控制玩家国家，并写 `logs/scripted_ai.log` |
| `set_cosmetic_tag` | `[<country tag>] [<cosmetic tag>]` | 改国名与国旗（`set_cosmetic_tag USA SOV`） |
| `reload` | `[<type>]` | 重载某类文件，也接受 `interface/` 下单个文件名；等值于 debug 模式下保存覆盖文件时的自动重载。例：`reload loc`、`reload focus`、`reload landcombat.gui` |
| `reloadoob` | `[<Target Country Tag>]` | 重载 OOB |
| `reloadinterface` | — | 重载整个界面 |
| `reloadtechnologies` | — | 重载科技库 |
| `updateequipments` | — | 更新装备库 |
| `updatesubunits` | — | 更新 sub-unit 库 |
| `update_loc` | `[localization tag]` | 更新某 localisation tag 文件 |
| `error` | — | 打开 error log；路径含特殊字符时无效；等值于点"错误狗" |
| `imgui` | （`imgui show`） | ImGui 调试界面，含脚本性能分析、AI 调试、角色列表等 |
| `goto_province` | `[province id]` | 镜头移到省 |
| `goto_state` | `[state id]` | 镜头移到州 |

### 30.4 其他游戏内命令

以下按主题分组，格式 `命令`（参数）——用途；标「开发者」的是 wiki 标注 only for developers。

**UI / 窗口 / 截图**：`window`（`wnd`）`[open|close] [window gui name]` 开关指定窗口；`tweakergui` 生成 tweaker GUI；`debug_nogui` 开关整个 GUI；`nopausetext` 关暂停横幅；`nomapicons` 开关地图图标；`fullscreen` 切换全屏；`browser`（`[url]`）显示浏览器窗口；`browser_base_url`（`[url]`）设 base url；`toggle_silhouette_portraits` 剪影肖像（开发者）；`helphelp` 彩蛋。

**镜头 / 地图显示**：`mapmode`（`[Mapmode type (int)]`）切地图模式；`mapnames` 开关地名；`fronts` 显示外国战线；`traderoutes` 显示贸易路线；`province_ids`（`pid`）显示省 ID；`cameraclamp` 开关镜头夹取；`debug_zoom` 放大；`debug_lockcamera` 锁定镜头；`moveunit`（`[<Unit ID>] [<Province ID>]`）移动部队；`spawnactor`（`[<Actorname>] [<Province ID>] [<Animation>]`）生成 actor；`massconquer`（`massc`）批量征服（开发者）；`cityreload` 重载城市；`gbreload` 重载渐变边界（开发者）；`gbpaint`（`[layer] [channel]`）渐变边界绘制。

**渲染 / 画面**：`rendertype` 报告渲染后端；`reloadfx`（`[map/mapname/postfx]` 或 `*.fx`）重载 shader；`3dstats`；`hdr`、`hdr_debug`；`srgb`；`bloom`；`debug_bloom`；`debug_postfx`；`debug_sky`；`PostEffectVolumes.Default`（`[posteffect_values name]`）；`night`（1.01 起似乎无效）；`debug_terrain`、`debug_water`、`debug_trees`、`debug_rivers`、`debug_borders`、`debug_cities` 城市绘制、`debug_lines`、`debug_entities`、`debug_particle`、`debug_wireframe`、`debug_textures`（写贴图信息进日志）、`debug_texture`（画 bloom 类贴图）、`collision`（`debug_collision`）法线/包围盒/碰撞、`deltat`（`[<speed factor>]`）动画速度；`createlean` 生成 LEAN 贴图；`flagsoutput`（`[<path>]`）导出贴图图集；`particle_editor` 粒子编辑器；`normals`（wiki 不明，开发者）；`ShowTechBonus`（wiki 不明，开发者）；`filewatcher` 文件监视。

**天气 / 地图数据**：`weather` 开关天气模拟；`reloadweather`（`[<randomseed>]`）重新生成天气；`reloadsupply`（`relsup`）重初始化补给；`building_health`（`bhealth`）`[<building type>] [<state or prov id>] [<building level>] [<health to add>]`；`nudge` 进 nudge；`analyzetheatres`（`anth`）分析战区错误；`aircombat`（`airc`）多参数生成空战（开发者）。

**AI / 战线调试**：`fow`（`debug_fow`）`[Province ID]` 关战争迷雾；`provtooltipdebug`（`tdebug`）省 tooltip 调试；`debug_fronts` 插值战线；`debug_off_front_snap`（`dbg_fsnap`）进攻战线吸附；`ai_front_dump`（`aifrontdump`）导出 AI 战线（需选中部队）；`ai_front_id` 取战线 debug ID；`debug_ai_budget`（`[CountryTag]`）AI 预算；`debug_air_vs_land`（`dbg_cas`）空对地调试；`debug_tactics` 战术 tooltip；`ai_invasion`、`ai_pp_log`、`ai_idea_desire_log`、`ai_force_template`、`ai_force_equipment`。

**事件 / 数据统计**：`poll` 轮询有效事件；`testevent`（`[<Event ID>] [<Character ID>]`）测试事件；`debug_show_event_ID`；`debug_events`、`debug_dumpevents`；`debug_diploactions`、`debug_dumpdiploactions`；`debug_commands`（命令计数进 message.log）；`debug_types`（打印动态引用类型，需 RTTI）；`debug_assert` 开关断言；`debug_info`；`trigger_docs`（`effect_docs`、`scripting_docs`、`docs`）把 trigger/effect/文档打到 game.log；`helplog` 把全部命令打到 game.log；`profilelog` 性能分析写 time.log；`run` 执行命令文件；`oos` 制造不同步（开发者）；`debug_achievements_clear`（开发者）；`PrintSynchStuff` 打印随机数与种子；`SetRandomCount`；`savegame` 存档；`savecheck` 存 Test_01 → 载入 → 存 Test_02 比对；`resign` 退出对局；`version` 显示版本；`time` 当前时间；`IP` 显示本机 IP；`requestgamestate` 向主机请求 gamestate；`morehumans`（`humans`）`[num]` 加人类玩家；`pause_in_hours` X 小时后暂停；`fast_forward` 在 5.3；`nextsong` 切歌；`combatsound` 战斗音效频率 0–50；`debug_volume`（`[<Volume Delta>]`）音乐音量；`hsv` RGB→HSV；`tag_color` 测国家颜色。

**已被移除 / 无效**：`winwars`（1.9.1 起移除）；`debug_nuking`（1.15.1 起移除）；`night`（1.01 起似乎无效）；`remove_core`（wiki 标"命令不工作"）。

**外交 / 阵营 / 杂项**：`add_interest` / `remove_interest`（`[<Country tag>]`）；`add_diplo` 加外交通道；`threat`（`[Threat amount]`）加/查本国造成的世界紧张度，`threat 999999999` 归零；`random_seed` 重掷 AI 随机种子；`eval_effect <tag> = { create_faction = "..." }` 建阵营；`{ dismantle_faction = yes }` 解散；`{ add_to_faction = <tag2> }` / `{ remove_from_faction = <tag2> }`；`{ set_faction_name = "..." }` 改名；`InternationalMarket.AddSubsidyForTags`（`[<economic capacity>] [<equipment>] [<country tag>]`）加买方补贴；`instant_wargoal` 瞬时战争理由；`allowideas` 无视 idea 的 `available`/`visible`（不覆盖 `allowed`）；`release`（`[<country tag>]`）释放国家；`armageddon` 全球建筑 100% 损伤（播放核爆动画但不给 Nuclear Fallout 修正）；`airealism` 彩蛋。

---

## 第 31 章 调试与日志

### 调试（Debugging）

### 31.1 `-debug` 启动项

两种加法（Modding 页）：

- Steam：库中右击游戏 → Properties → General 底部 Launch Options，空格分隔，如 `-checksum -debug`。
- Windows 快捷方式：目标写成 `"C:\...\hoi4.exe" -debug -start_tag=ALB`（引号后至少一个空格）。

`-debug` 带来的好处（wiki 全部列出）：

1. **Automatic loading**：mod 内文件改动直接进游戏，不用 `reload`；出错也会自动进 error log。只对启动时已存在的文件有效（例外：被直接路径引用的文件，如 `load_oob = "TAG_my_oob"`、GFX sprite 引用的图片）；对 `history/countries/`、`history/states/`、`map/` 无效（后两者部分可用 nudge）。图片热载不解压，会出现扭曲或黑底，重启才正常。
2. **No map definition crash**：地图有 MAP_ERROR 时正常启动时崩，debug 下能继续加载。
3. **Extended error log**：部分错误只有 debug 才写日志。
4. **Ease of error log opening**：有错误时自动打开日志；进游戏后右下角"错误狗"也能点开。用户目录路径含非 ASCII 字符时会报 "The system cannot find the path specified"。
5. **Ease of nudge access**：主菜单出现 Nudge! 按钮。
6. **Graphical interface information in the main menu**：主菜单按 ` 得到界面元素名、位置、所用 sprite（等同 `gui` 命令）。
7. **Expanded information**：hover 省/州/国家显示 ID、owner/controller tag、cosmetic tag 等。
8. **Access to more console commands**：解锁部分仅开发者命令（不是全部）。
9. **Ease of access to GUI files**：hover GUI 元素 + `Ctrl+Alt+右击` 打开调试菜单，可跳到定义该元素的 GUI 文件。
10. **Automatic saving on peace deals**：每次和会结束自动存档。

控制台 `debug` 命令只给第 4–10 项中的后 4 项；启动项 `-debug`（或 `-crash_data_log`，后者不开自动加载）给全部，但会禁多人并降低性能。

### 31.2 日志位置与用途

Windows：`Documents\Paradox Interactive\Hearts of Iron IV\logs\`；Linux：`~/.local/share/Paradox Interactive/Hearts of Iron IV/logs`。每次启动覆盖。

高价值：`error.log`（非致命错误，`common` 相关的基本都该修）、`game.log`（国家行为；`log` effect/trigger 输出在此）、`setup.log`（各阶段加载完成情况，定位崩在哪个文件）、`memory.log`（加载期内存）。

中等：`time.log`（各加载步骤耗时与 tick 间隔）、`system_debug.log`（界面错误）、`text.log`（localisation 重复定义/断言）、`ai.log`（AI 决策）。

低：`exceptions.log`（崩溃栈）、`ai_trace.log`、`executedcommands.log`、`graphics.log`、`message.log`、`postedcommands.log`、`random.log`、`receivedcommands.log`、`sentcommands.log`、`system.log`（系统与图形信息；带 `-checksum` 时输出校验和，可对比两人差异）。

`human_ai` 另写 `logs/scripted_ai.log`。

### 31.3 `-crash_data_log`

- 与崩溃日志同目录的 `meta.yml`（直接在 `crashes/` 下，不在 `logs/` 子目录）会记录崩溃前最后读到的代码行，并开启 debug 模式。
- 例：`LastRead: map/supply_nodes.txt (727)`、`LastRead: client_ping (1)`。
- 显著降速，只能在排查崩溃时用。
- 若记录行正好是文件最后一行，很可能是崩在**下一个**文件，难以定位。
- 它开的 debug 不包含自动加载；要两者都写启动项。

### 31.4 nudger（地图编辑器）

打开方式：`nudge` 控制台命令，或 debug 模式下主菜单的 Nudge! 按钮。启动后显示默认 bookmark 的世界状态；没有默认 bookmark 时地图没有国家。

输出目录：**用户目录**（如 `C:/Users/<user>/Documents/Paradox Interactive/Hearts of Iron IV/`）。默认情况下这些文件会被原版游戏加载，可能造成崩溃或地图定义错误（不开 debug 会直接自己关掉），涉及 `history/states/`、`map/`、`localisation/english/`。

分区与作用：

| 分区 | 作用与产物 |
|---|---|
| States | 改州历史（边界、名字）。产物写入 `history/states/`、`map/strategicregions/`、`localisation/english/state_names_l_english.yml` |
| Supply areas | 1.11（NSB）后移除，按钮已失效 |
| Strategic regions | 改战略区边界；海域还能改地形与修正 |
| Ambient objects | 改地图常驻 3D 模型（南北边界等） |
| Database | 改 `map/definition.csv`（省定义）；产物是 `map/definition.csv.cache` 与 `map/definition.csv.fixed.csv`（后者优先于 `definition.csv`） |
| Weather | 改战略区天气概率与天气粒子位置；产物 `map/strategic_regions/`、`map/weatherpositions.txt` |
| Buildings | 建筑模型位置、海军基地/浮港对应的相邻海域省、每州空军基地与火箭基地所在省。**新建州不调整会崩** |
| Units | 单位模型位置与胜利点 |
| Supply | 补给枢纽与铁路的初始位置与等级；产物 `map/supply_nodes.txt`、`map/railways.txt` |
| Leave nudge | 回主菜单；若是用控制台进的 nudge，会崩 |

States 区的已知坑（wiki 明写）：

- **会删掉州文件里的引号**（`name` 属性除外），可能破坏其中的 `has_dlc` 等检查，导致整个州失效。
- 无版本号的 localisation 会被当作版本 -1 写出，之后 localisation 报 `Expected quotation mark (") at line ...`。
- 新建州名只能用**可用作文件名的 ASCII 字符**，否则直接崩（Windows 禁用 `\ / : * " < > |`）。
- shift+点击把不属于任何州的省并入时，可能被重复写进同一战略区或写进两个战略区，必须手工修。
- 按钮：`Create state`、`Open file`、`Delete state`、`Delete all empty`、`Find collision`、`Update`、`Save`。`Find collision` 专门找"同属多个州"的省。
- `Save` 只写"自上次读取以来变更过"的文件；被 mod 文件覆盖时看起来像回滚，其实用户目录里已写入。

Database 区：没开始过任何对局时多数按钮会崩，建议先进一局再退回主菜单进 nudge；用控制台进可避免该崩溃，但离开时会崩。按钮：`Generate RGB`、`Save`、`Cancel`、`Type`、`Coastal`（含 `Generate`）、`Continent`、`Show colors`。

Supply 区：`supply_nodes.txt` / `railways.txt` 里引用不存在或不在任何州的省会崩。编辑模式需按住 `Ctrl`。`Update` 只重读 `supply_nodes.txt` 且**不可删已有枢纽**；`Save` 写用户目录。

Weather 区：周期（period）不是按战略区存的，改周期影响所有战略区；`Check errors` 查"某些天没有周期覆盖/多个周期重叠"；预览粒子必须在画面设置里开启天气。

### 31.5 `debug_nogui` 与其他调试开关

- `debug_nogui`：整个 GUI 开关。录干净画面素材、截图、排查是否是 UI 层问题时用。
- `debug_zoom`、`debug_lockcamera`、`nomapicons`、`nopausetext`：镜头与截图相关。
- `debug_textures` / `debug_texture` / `debug_wireframe` / `debug_entities` / `debug_lines` / `debug_particle`：渲染层排查。
- `debug_ai_budget [CountryTag]`、`aiview`、`ai`、`ai_front_dump`、`ai_pp_log`、`ai_idea_desire_log`：AI 行为排查。
- `guibounds`（`gui`）、`reloadinterface`、`reload <file>.gui`：界面热调。
- `helplog`：把所有命令写进 game.log，用来核对版本间命令增删。

---

## 第 32 章 常见错误汇编

### 军事、装备与科技

### 32.1 目录/结构

1. **装备写进 `common/units/*.txt`**：那是 sub_units 目录。装备必须在 `common/units/equipment/*.txt`。
2. **OOB 写了但没加载**：`history/units/` 下的文件必须被 `oob` / `set_oob` / `set_naval_oob` / `set_air_oob` 引用，否则一个单位都不会出现。
3. **OOB 缺失导致建筑异常**：没 OOB 的国家，effect 建的东西不立即归属。
4. **忘记 `interface/countrytechtreeview.gui`**：新科技/新文件夹不写 GUI 就不显示。新 folder 必须同时补 tab、folder 容器、item 容器。
5. **科技无 gridbox**：没有 path 连入、又没定义 gridboxType，整条分支不出现。
6. **两条 path 到同一科技触发** `Found multiple potential grid boxes for tech`：次要连线加 `ignore_for_layout = yes`。

### 32.2 触发器/执行顺序

7. **`oob =` 写进 `if`**：它是 history 参数不是 effect，必须换 `set_oob`。
8. **history 里 `else` 写法**：只支持嵌套式 `if = { ... else = { ... } }`。
9. **history 文件名前三位不是 tag**：不加载（大小写不敏感，后面内容随便写）。
10. **多余的 `}`**：history 文件会在此处停止执行，后面全部不读。症状是"文件后半段全没生效"。
11. **`add_ideas` 后跟 `recruit_character` 放在最后一行**：招募会失败，文件末尾必须至少还有一行（哪怕空行）。
12. **`set_politics` 之前没招募领袖**：领袖不会上位；同一党派多个领袖时第一个招募的成为领袖。
13. **附属关系写在宗主国历史里**：`set_autonomy` 必须在被附庸国的政治设置之前，否则附庸会重置政治；建议写在被附庸国自己的历史里。
14. **`set_popularities` 加起来不是 100**：设置失败。

### 32.3 装备/单位

15. **`archetype` 与 `is_archetype = yes` 同时写**：互斥，只能二选一。
16. **`parent` 指向 archetype**：不允许，`parent` 只能是具体型号。
17. **archetype 上忘写 `is_buildable = no`**：原型会被当成品生产。
18. **模块化装备没配 equipment designer 容器**：设计器打不开，走不了模块体系。
19. **`instant = yes` 写进装备文件**：它属于 idea 的 `equipment_bonus`，写在装备里无效。
20. **把 `maximum_speed` 的两种语义搞混**：装备上是绝对 km/h（默认 4），单位上是乘算 bonus（0.5 = +50%）。
21. **新单位没图标**：师设计器里显示随机图标（防空炮弹等），要在 `interface/subuniticons.gfx` 加 3 个 spriteType，其中 white 版**不能省 `medium`**。
22. **`group` 写成内部 `type` 值**：`group` 只有 `infantry`/`support`/`mobile`/`armor`（或自定义），`type` 才是单位内部类型；两者混用会让师设计器页签错乱。
23. **支援连 `affects_speed` 忘了设 `no`**：会拖慢整个模板速度。
24. **新增 group 只写了 `group =`**：缺 `group_<name>_title` 本地化与 `GFX_group_<name>_icon` 贴图，界面显示空白。
25. **变体没进 `script_enums`**：由模块派生的新装备类型必须在 scripted_enums 列全（含 `_0`、`_1` 后缀），且至少一个 battalion 使用它。
26. **`need` 与 `essential` 混用**：`need` 是生产所需装备（缺则不可用），`essential` 是 `active = no` 时的必需装备。

### 32.4 海军/空军

27. **同船体多舰级却不写 `owner`**：会忽略 `version_name`，用国家历史里最后定义的那个舰级。
28. **`owner` / `creator` 国家未解锁科技**：OOB 里的舰/机造不出来，或版本不存在时报错。
29. **`amount` 不写 1**：船/机的 equipment `amount` 应保持 1。
30. **以为能新增 mission 类型**：海军任务、空军任务、`map_icon_category`、单位内部 `type` 都是硬编码，不能新增；能新增的只有 `group`。
31. **一个 wing 勾多个任务指望同时执行**：只执行优先序最高的那个；要并行就拆 wing。
32. **把 `air_wings` 的键当装备名**：键是**州 id**，州里必须有 air base。

### 32.5 科技

33. **科技没写 `categories` 里任一类别到 `common/ai_focuses/*.txt`**：AI 永远不会研究它。
34. **互斥只写一边**：`XOR` 必须在每个互斥科技里都列出其它项。
35. **隐藏科技只用 GUI 隐藏**：AI 仍会研究，必须用 `allow = { always = no }` 之类挡住。
36. **指望 `set_technology = { X = 0 }` 干净取消**：解锁数据库对象的科技取消后对象仍可用到重启；互斥科技可能取消失败。
37. **`enable_building` 的 `level` 当成"加 N 级"**：它是"解锁到该等级上限"，且不能超过建筑定义里的 max level。
38. **`research_cost` 当成天数**：1 = 100 天（默认科研速度、无修正）。

### 国家、州、地图与本地化

**国家**
- country 文件 `color` 不带 `rgb`/`hsv` → 颜色不生效。
- 用 `NOT/AND/TAG/OOB/LOG/NUM/RED` 或纯数字 tag → 各类隐性故障。
- dynamic tag 不足 → 中/小旗透明（无日志）或崩溃。
- `recruit_character` 在 `set_politics` 之后 → 领袖不换人；在文件最后一行 → 招募失败。
- 历史文件多余 `}` → 后续内容不执行。
- 无 OOB → effect 建的建筑不生效（要等消费品比例变化或读档）。
- 旗为 24-bit 无 alpha 或原点在左上 → 报错或图像翻转。
- 只写 `TAG` 不写 `_DEF` → 大量通用事件/决议显示异常。

**州与地图**
- state ID 不连续 → 未开 debug 时加载崩；删州必须移位并全库改引用。
- 省 ID 有缺口 → 后续省套用错误地形/类型/大洲。
- `definition.csv` 用 LF 行尾 → `Prov X has no continent`。
- 省宽高非 256 倍数、总面积超限、provinces.bmp 为 32-bit → 启动崩。
- 8-bit indexed 图被 Paint.net / MS Paint 重存 → 调色板重建，地图错乱。
- GIMP 导出未勾 "do not write colour space information" → BITMAPV5HEADER 不被识别。
- 州跨战略区 → MAP_ERROR，未开 debug 直接崩。
- `map/buildings.txt` 为空或缺海军基地/浮动港条目 → 启动崩或数小时后死循环崩。
- `adjacencies.csv` 缺末行 `-1;...` → 加载卡住。
- `supply_nodes.txt` / `railways.txt` 指向不存在或无州的省 → 开单机/nudger 补给面板崩。
- nudger 编州：州名含多字节字符会崩；州历史里的引号会被清掉，破坏 `has_dlc = "..."`。
- `weatherpositions.txt` 缺 small 或 large → 崩。
- `rivers.bmp` 的 `MAP_ERROR: Palette ...` 可忽略（唯一不阻断非 debug 启动的 MAP_ERROR）。

**书签与规则**
- 只有 1 个书签 → 跳过选择且无法回主菜单；规避用第二个书签 + `max_slots_horizontal = 1` 隐藏。
- `default = yes` 写了多个 → 行为不确定（只应有一个）。
- `default_country` 不在 interesting countries 里 → 无效。
- `minor = yes` 但焦点树是 `default = yes` → 不显示。
- difficulty_settings 与 game_rules 都为空 → 规则菜单打不开。
- game rule 的 `required_dlc` 不满足 → 规则被整个删除，引用它的 trigger 报错。
- `allow_achievements = yes` 写在 `default` 块 → 无意义。

**on_actions**
- `on_startup` 默认作用域 `none`，不手动 scope 大量 effect 无效。
- `on_daily` 对每国各跑一次，里面再写 `GER = { ... }` 会放大上百倍。
- `on_recall_volunteers`、MIO 的两个 tech 钩子 → 静默无效。
- 想靠 history 的 `set_politics` 触发 `on_government_change` → 不会。

**defines**
- 行尾加逗号 → 启动崩。
- mod 自带 `00_defines.lua` / `00_graphics.lua` → 官方更新后缺 define。
- 改 `START_DATE` 不改 `END_DATE` / `TENSION_TIME_SCALE_START_DATE` → 时间逻辑错乱。

**本地化**
- 无 BOM、文件名不含语言代码、首行不是 `l_english:` → 不加载；有 key 无数据库行可能 `0xC0000005` 崩溃。
- key 含空格/变音/中文 → 从该处起整个文件失效。
- 值真换行 → 文件失效，要用 `\n`。
- `§` 后字符非法 → 只报字符不报文件，需全目录搜。
- 漏写 `§!` → 颜色外溢到下一条文本；同语言重复定义同一 key 又没放 `replace` → 取值不确定，通常原版胜。

### 界面、AI 与加载期崩溃

### 32.6 加载期崩溃（崩溃日志指向的文件）

| 指向文件 | 常见原因 |
|---|---|
| `common/countries/cosmetic.txt` | 整个覆盖了 `common/national_focus/` 或 `common/continuous_focus/` |
| `map/rocketsites.txt` | 整个覆盖了 `history/states/` 或 `common/unit_leader/`（州没有"通用文件"，应手工补） |
| `common/national_focus/*.txt` | 国策树写了 `shared_focus = my_focus` 但该共享国策不存在（且是文件夹里最后一个文件的最后一行） |
| `gfx/models/supply/railroad.shader` | 地图 bmp 有问题：`provinces.bmp` 尺寸不可被 256 整除、超过 40 MiB、各 bmp 尺寸不一致（`trees.bmp` 例外）、DIB 头格式不对（用了编码或用 BITMAPV5HEADER 而非 BITMAPINFOHEADER） |
| `history/general/*.txt` / `history/countries/*.txt` / `map/rocketsites.txt` | 某州的 `victory_points = { ... }` 指向不存在的省 |
| `savegame.hoi4` 或 `map/cities.txt` | 定义的国家很多但动态国家很少（<40–80 范围），通常是粗暴覆盖 `common/country_tags` 或动态国家文件过期 |
| `numbers.pr` / `career_profile_*.pr` | 战略区损坏（大量省没有战略区） |

选国家阶段：

| 现象/文件 | 原因 |
|---|---|
| `set_controller` | bookmark 里的国家在 `history/countries/TAG*.txt` 没有合法首都 |
| `history/units/filename.txt` | OOB 里航母内直接写 airwings（1.11 及更早写法），需按 1.12 改 |
| `history/units/filename.txt` / `map/railways.txt` | 国家有师模板但找不到任何 `common/ai_templates` 条目来扩展 |
| `map/supply_nodes.txt` / `map/railways.txt` | 建筑类型放在非法省（不在州里的省）；或与 nudge 补给菜单冲突 |
| `tutorial/tutorial.txt` | 教程文件坏了（引用不存在的州 ID，或完全没有 `tutorial = { ... }`）；把内容改成 `tutorial = { }` 可解决 |

游戏中：

| 现象 | 原因 |
|---|---|
| `client_ping` / `hourly_tick` | AI 引发。常见：师模板无 ai_templates（`blocked_for`/`available_for` 写错或 replace_path 粗暴覆盖）；某州在历史文件里没有 owner（AI 试图对该州评估空袭任务就崩）；`map/buildings.txt` 不完整（海军基地/浮港找不到出海省，会死循环到 CPU/GPU 过载）；某装备没有 sub-unit（覆盖 `common/units` 或用了 replace_path） |

`map/buildings.txt` 不完整时 error.log 会出现：`Province 12345 is setup as coastal but has no port building in the nudger. This will likely crash the game.`

### 32.7 error.log 常见项与判读

- `error.log` 只记录"开发者预料到的"错误，通常**不含**导致崩溃的那条，别把它当崩溃原因清单。
- 所有 `MAP_ERROR` 都必须开 debug 才出现（唯一例外 `MAP_ERROR: Palette in rivers.bmp is probably not correct`，它不阻止不开 debug 启动）。
- 空文件会被整份跳过，所以同一个崩溃可能显示成别的文件——排查前先清空 error.log。
- 排查手法：二分法增删 mod 文件；除 `history/states/`、`map/strategicregions` 外可以去掉 replace_path。replace_path 必须两个 `.mod` 文件都写。

### 32.8 图形相关三类现象

| 现象 | 含义 |
|---|---|
| sprite 完全透明 | sprite 存在但图片加载不了：`texturefile` 路径/文件名不对，或图片损坏；常伴随 `Texture Handler encountered missing texture file` |
| sprite 被替换成默认图 | sprite 名对不上：拼错，或没遵守命名格式（最常见：国策图标闪光图漏了 `_shine` 后缀） |
| 角色用随机肖像 | 上述两种情况之一（sprite 非法或文件缺失） |

另有默认兜底图 `GFX_default`（原版是那只错误狗）；极少数场合没有兜底图，例如 balance of power 里指定不存在的 sprite 会让该侧完全没图标。

### 32.9 脚本/结构类高频错误

- **括号多余**：解释到不匹配的 `}` 就整份停止，后面全部不执行。在 `history/countries` 这类没有根块的目录里最致命（不会有 token 报错，直接静默截断）。
- **同名文件（大小写不敏感）**：如 `events/Generic.txt` 与 `events/GENERIC.txt` 同时存在 → 文件被加载两次；即使所在目录被 replace_path 卸载，这条仍成立。
- **缩进错位**（不报错但语义错）：括号闭合层级与开启层不一致时，后续条目被塞进上一个块内。常见四种：少缩进一级、闭合括号与开头同级、开括号后不缩进、相邻两行差 ≥2 级。
- **mod 描述文件问题**：launcher 里同名 mod 只有先加载的生效；`path` 用反斜杠（`mod\my_mod`）无效，必须 `/`；`path` 含非 ASCII 字符 mod 加载失败；`dependencies` 名字必须与主 mod 的 `.mod` 里完全一致（含特殊破折号）。
- **`replace_path`**：只卸载指定文件夹内直接文件（不含子目录）；不改加载顺序（顺序靠 `dependencies`）；对"直接引用路径"的文件无效（如 `history/units` 的 OOB、`gfx/flags` 的国旗、`gfx/loadingscreens`——主菜单背景仍是 sprite 直接引用）。粗放使用会造成崩溃或莫名奇妙的报错（如国策、scripted trigger 相关系统被误触发）。两个 `.mod` 都必须写。
- **编码**：文本文件 UTF-8 无 BOM；`.yml` localisation 必须 UTF-8-BOM，首行 `l_english:`。
- **路径**：mod 路径、用户目录路径只要含非 ASCII 就可能加载失败或不可打开 error.log；可用 `launcher-settings.json` 的 `gameDataPath` 改用户目录。
- **AI 模板缺条目**：`common/ai_templates` 里 `blocked_for` / `available_for` 只能二选一，混用行为未定义；每个国家每个 role 至多一个 role 条目。

---

## 第 33 章 音乐与音效

### 音乐（Music）

#### 1.1 文件位置与格式

| 项 | 内容 |
|---|---|
| 音频目录 | `music/` 或任意子文件夹 |
| 音频格式 | `*.ogg`（wiki 唯一认可的格式） |
| 曲目定义 | `*.asset`，必须与对应 `.ogg` 同目录 |
| 电台分配 | `*.txt`，与 `.asset`、`.ogg` 同目录 |
| 电台 UI | `interface/*.gui` |
| 电台封面 sprite | `interface/*.gfx` |

`Modding.wiki` 对文件夹职责的界定：`music/` 定义「在电台中播放的曲目，以及 weighted shuffle 里的候选」；`sound/` 定义「其它地方播放的音效，通常挂在 GUI 元素上，也包含师级语音」。

wiki 未给出音乐文件的采样率/位深要求（与音效不同，音乐页只写了格式 `*.ogg`）。

#### 1.2 `song` 条目（`music = { }` in `*.asset`）

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 曲目 ID，同时是本地化 key。本地化写法 `song_name:0 "Song's Name"`。**长度上限 63 字符** |
| `file` | string | 文件名，**含 `.ogg` 扩展名** |
| `volume` | float | 单独调整该 ogg 的音量，无需改音频文件（示例 `0.65`） |

```
music = {
    name = "song_name"
    file = "song_file.ogg"
    volume = 0.65
}
```

#### 1.3 分配到电台（`*.txt`）

文件首行（在任何曲目定义之前）必须先声明所属电台，可多文件指向同一电台：

```
music_station = "station_name"
```

注意：wiki 的写法是**单行字符串赋值**，不是 `music_station = { name = ... }` 块结构。

单曲分配条目：

| 字段 | 说明 |
|---|---|
| `song` | `*.asset` 里 `music.name` 的 ID |
| `chance` | 仅在播放模式为 **Weighted Shuffle** 时生效 |
| `chance.base` | 直接替换概率 |
| `chance.factor` | 乘算 |
| `chance.add` | 加算 |
| `chance.modifier = { }` | 内部 `factor`/`add` 仅在所有 trigger 满足时生效 |

```
music = {
    song = "song_name"
    chance = {
        base = 1
        modifier = {
            factor = 0
            has_war = no
        }
    }
}
```

#### 1.4 电台（station）定义

电台是 UI 文件 `interface/*.gui`，`guiTypes` 下必须包含两个 `containerWindowType`，名字里 `<MUSIC STATION>` 换成电台名：

| 容器 | 必需名 | 尺寸 | 内含控件 |
|---|---|---|---|
| 播放面板 | `<MUSIC STATION>_faceplate` | 590 × 46 | `iconType` `musicplayer_header_bg`；`instantTextboxType` `track_name`(font `hoi_20b`) / `track_elapsed`(font `hoi_18b`) / `track_duration`(font `hoi_18b`)；`buttonType` `prev_button` / `play_button` / `next_button` / `shuffle_button`；`extendedScrollbarType` `volume_slider` |
| 电台条目 | `<MUSIC STATION>_stations_entry` | 162 × 130 | `checkBoxType` `select_station_button`，`quadTextureSprite = "<SPRITE>"` |

按钮贴图：`GFX_musicplayer_previous_button`、`GFX_musicplayer_play_pause_button`、`GFX_musicplayer_next_button`、`GFX_toggle_shuffle_buttons`、`GFX_musicplayer_header_bg`；按钮字体 `Main_14_black`，`Orientation = "LOWER_LEFT"`，`clicksound = click_close`，tooltip `MUSICPLAYER_PREV` / `MUSICPLAYER_NEXT`。

音量滑块参数：`maxValue = 100`、`minValue = 0`、`stepSize = 1`、`startValue = 50`、`horizontal = yes`、`orientation = lower_left`、`origo = lower_left`、`setTrackFrameOnChange = yes`；`slider` 用 `GFX_scroll_drager`，`track` 用 `GFX_volume_track`，两者 tooltip `MUSICPLAYER_ADJUST_VOL`。

电台本地化：`localisation/<language>/*_l_<language>.yml` 中 `<MUSIC STATION>:0 "Music station's name"`。

#### 1.5 封面 sprite

`interface/*.gfx`：

```
spriteType = {
    name = "<SPRITE>"
    texturefile = "gfx//interface//topbar//musicplayer//<FILE NAME>.dds"
    noOfFrames = 2
}
```

`.dds` 必须**横向切成 2 帧**：未选中态 + 选中态。该 sprite 名写进 `select_station_button` 的 `quadTextureSprite`。

#### 1.6 替换原版曲目 / 新增曲目的两种做法

**新增**：放新 `.ogg` + 新 `.asset` + 分配用 `.txt`，三者同目录，全程不动原版文件。

**替换**：同路径同文件名覆盖（`music/xxx.asset`、`music/xxx.txt` 与曲目分配文件），依据 `Modding.wiki`：同名同路径文件按加载顺序取后者，mod 晚于本体加载，所以 mod 版生效；文件夹整体不参与覆盖。

#### 1.7 与描述符 / DLC 音乐的关系

- DLC 是**独立加载源**，优先级高于本体、低于 mod。`modname/dlc/` 及其子目录**完全无效**。
- 改 DLC 曲目必须按 DLC 内部的真实路径在 mod 里重建同名文件。wiki 原例：要改 `../dlc/dlc023_man_the_guns/music/mtg_music.txt`，mod 里须放 `modname/music/mtg_music.txt`。
- `replace_path` 只负责「卸载某文件夹内先前加载的所有内容」，**不改变加载顺序**；mod 之间顺序由描述符文件名（及 `dependencies = { }`）决定。
- wiki 的音乐页**未**给出任何 mod 描述符专属的音乐字段。

### 音效（Sound）

#### 2.1 位置与格式

定义全部在 `sound/`，所有定义文件必须是 `*.asset`。

音频格式（wiki 原文）：保存为 **WAV**，Stereo，mono channel，**44100 Hz**，**32-bit float**。

原文 "in Stereo, as a mono channel" 自身矛盾（立体声 vs 单声道）。可确定的硬指标只有：WAV 容器、44100 Hz、32-bit float；声道数按用途定（3D 定位音效需单声道，`is3d = yes`）。

#### 2.2 `sound` —— 单个音频文件

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 供其它文件引用的名字 |
| `file` | string | 相对 `sound/` 的路径 |
| `always_load` | bool | 是否常驻内存 |
| `volume` | float | 音量 |

#### 2.3 `soundeffect` —— 播放逻辑

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | soundeffect 名，脚本与 GUI 里引用的就是它 |
| `falloff` | name | 引用 `falloff = { }` 条目名 |
| `sounds` | block | 内含 `sound = <name>` 或 `weighted_sound = { sound = <name> weight = int }` |
| `loop` | bool | 是否循环 |
| `is3d` | bool | 是否启用 3D 声 |
| `random_sound_when_looping` | bool | 循环时随机取 `sounds` 内条目，而非顺序迭代 |
| `max_audible` | int | 同一时刻该音效最大实例数 |
| `max_audible_behaviour` | type | 超出上限时的行为，**wiki 注明恒为 `fail`** |
| `volume` | float | 音量 |
| `fade_in` | float | 淡入时长 |
| `fade_out` | float | 淡出时长 |
| `looping_delay_random_offset` | bool | wiki 标 `???`，语义未明 |
| `delay_random_offset` | {float, float} | 循环间延迟的随机区间（min, max） |
| `looping_playbackrate_random_offset` | bool | wiki 标 `???`，语义未明 |
| `playbackrate_random_offset` | {float, float} | 循环间播放速率随机区间 |
| `volume_random_offset` | {float, float} | 循环间音量随机区间 |
| `prevent_random_repetition` | bool | 防止刚播过的同一条目立刻重播 |

wiki 的 `soundeffect` **没有** `pitch` 字段；音高变化只能通过 `playbackrate_random_offset` 随机扰动。

#### 2.4 `falloff`

| 字段 | 说明 |
|---|---|
| `name` | 条目名 |
| `min_distance` | 开始衰减前的距离，即最大音量范围 |
| `max_distance` | 完全听不到的距离 |
| `height_scale` | 声源与摄像机高度差的缩放系数 |

#### 2.5 `category` 与 compressor

`category = { name; soundeffects = { <name> ... }; compressor = { enabled, pregain, postgain, ratio, threshold, attacktime, releasetime } }`。

两个全局 compressor：`master_compressor`（声音）、`music_compressor`（音乐）。单独定义 compressor 时用 `<name> = { pregain postgain ratio threshold attacktime releasetime }`。

#### 2.6 调用方式

脚本 effect（`Effect.wiki`）：

| effect | 写法 | 范围 |
|---|---|---|
| `sound_effect` | `sound_effect = "boom"` | 播放一次，**所有国家都听得到** |
| `scoped_sound_effect` | `scoped_sound_effect = "boom"` | 播放一次，仅当前国家听得到 |

`play_song` / `scoped_play_song` 走音乐通道，参数是 `*.asset` 里的曲目名，且**该曲目必须已分配到某个 station 才生效**：`play_song = "general_peace_1"`。

GUI 调用：按钮 / 复选框的 `clicksound = <name>`（`buttonType`、`checkBoxType` 均支持），例如电台按钮的 `clicksound = click_close`。

---

## 第 34 章 3D 模型与实体

### 模型、实体与动画

#### 3.1 文件分工

| 内容 | 位置 |
|---|---|
| `pdxmesh`（mesh 定义） | `gfx/entities/*.gfx` |
| `entity`（实体定义） | `gfx/entities/*.asset` |
| `animation`（动画条目） | `gfx/models/` 及子文件夹，`*.asset` |
| `.mesh` 模型本体 | `gfx/models/*.mesh` |
| `.anim` 动画数据 | `gfx/models/*.anim` |

`Entity_modding` 页明确：`.gfx` 与 `.asset` 都在 `gfx/entities/`；动画 `.asset` 在 `gfx/models/`。

#### 3.2 `pdxmesh`（加 mesh）

```
objectTypes = {
    pdxmesh = {
        name = "name_of_mesh"
        file = "gfx/models/name_of_mesh.mesh"
        animation = { id = "idle" type = "name_of_animation" }
        scale = 1.0
    }
}
```

| 字段 | 说明 |
|---|---|
| `name` | mesh 名，被 `.asset` 里的 entity 引用 |
| `file` | 到 `.mesh` 的相对路径 |
| `animation` | 每个动画一个 scope |
| `animation.id` | 在 pdxmesh 内部的动画名 |
| `animation.type` | 指向 `.asset` 中真正定义的 animation 名 |
| `scale` | 模型尺寸缩放 |

#### 3.3 `entity`（加实体）

```
entity = {
    name = "name_of_entity"
    pdxmesh = "mesh_to_use"
    scale = 1.0
    cull_radius = 100

    default_state = "idle"
    get_state_from_parent = yes

    locator = { name = "example"  position = { 0.0 0.0 0.0 } }

    state = {
        name = "idle"
        state_time = 0.0
        animation = "idle"
        animation_blend_time = 0.0
        animation_speed = 1.0
        looping = yes
        next_state = "idle"
        chance = 2
        propagate_state = { node = "idle" }
        event = {
            time = 1.0
            trigger_once = yes
            node = "example_node"
            light = "example_light"
            particle = "example_particle"
            keep_particle = yes
            sound = { soundeffect = "example_soundeffect" }
        }
    }

    attach = {
        name = "name"
        <node> = "example_entity"
    }
}
```

| 字段 | 说明 |
|---|---|
| `name` | 实体名，`ambient_objects.txt` 等脚本处引用，单位则在 `sprite` 侧引用 |
| `pdxmesh` | 关联的 mesh |
| `scale` | 实体尺寸缩放 |
| `cull_radius` | 超过该距离停止渲染（剔除） |
| `default_state` | 默认动画状态 |
| `get_state_from_parent` | 继承父实体状态（例：士兵挂载的武器实体） |
| `state` | 每个动画状态一个 scope |
| `locator` | 给实体加节点，`name` + `position`（x y z） |
| `attach` | 把另一实体挂到当前实体骨架节点上：`<node>` 为骨架节点名，值为实体名 |

注意：可用状态取决于实体被用在哪里——单位实体会有战斗状态，建筑实体有建筑状态；所有实体共有 `idle`。

**本页没有 `texturefile` 字段，也没有 `.mesh`/`.dds` 贴图挂接说明**。贴图随 `.mesh` 自身引用，`Graphical_asset_modding` 的 `texturefile` 只属于 sprite/字体体系（`interface/*.gfx`），与 entity 无关。

#### 3.4 `state` 字段

| 字段 | 说明 |
|---|---|
| `name` | 状态名；所有模型都有 `idle` |
| `state_time` | 当前状态持续时长 |
| `looping` | 是否循环 |
| `event` | 内部触发粒子/音效的 scope |
| `animation` | 播哪个动画状态（来自 pdxmesh） |
| `animation_blend_time` | 与指定动画之间的混合时间 |
| `animation_speed` | 播放速率 |
| `next_state` | 下一个状态 |
| `chance` | 多个同名 state 条目时的抽取权重（例：训练动作选俯卧撑/开合跳） |
| `propagate_state` | 把当前状态传播到指定节点 |

#### 3.5 `event` / `sound` / `locator`

`event`：`time`（秒）、`particle`、`keep_particle`（粒子是否延续到事件结束后）、`trigger_once`、`sound`（scope）、`node`（定位节点或模型节点，作为事件原点）、`light`。

`sound`：仅 `soundeffect`（要播的音效名）。

`locator`：`name`、`position`（x y z）。

#### 3.6 `animation` 条目

```
animation = {
    name = "animation_name"
    file = "animation_name.anim"
}
```

`name` 被 `pdxmesh` 引用，`file` 为 `.anim` 的相对路径。

#### 3.7 脚本操作实体（`Effect.wiki`，均标注 1.11）

| effect | 参数 | 作用 |
|---|---|---|
| `create_entity` | `entity = <gfx_entry>`（`gfx/entities/*.asset` 中的 entity 名） | 生成实体 |
| | `id = int` / `var = <variable>` | 供后续 effect 引用的 ID，后者把 ID 存进变量 |
| | `x` `y` `z` = int | 坐标 |
| | `province` / `state` = int | 用省/州中心作为位置 |
| | `rotation` = decimal | 弧度 |
| | `scale` = decimal | 尺寸 |
| | `min_zoom` = decimal | 可见所需最小缩放级别（默认最近 50，最远 3000） |
| | `visible` = scripted_trigger | 哪个国家能看到 |
| `destroy_entity` | `destroy_entity = 123` | 按 ID 删除 |
| `set_entity_position` | `id` + `x` `y` `z` / `province` / `state` | 改位置 |
| `set_entity_rotation` | `id` + `rotation` | 改朝向（弧度，正值逆时针，360°≈6.28） |
| `set_entity_scale` | `id` + `scale` | 改尺寸 |
| `set_entity_animation` | `id` + `animation = "shoot_lasers"` | 换动画，动画须定义在 `gfx/models/**/*.asset` |
| `set_entity_movement` | `id`、`start = { x y z / province / state }`、`target = { ... }`、`ratio`（0~1 起止间的位置比例）、`rotation`（定位后再施加的角度） | 在两点之间摆位 |

坐标系与地图一致（`Map modding#Coordinate system`）。

#### 3.8 单位模型 ↔ `common/units/*.txt` 的对应写法

`Unit_modding` §Units：单位用 `sprite` 指定模型。

```
sub_units = {
    <unit name> = {
        sprite = <entity>   # 指向 gfx/entities/*.asset 里的 <name>_entity
        map_icon_category = <type>
        priority = <int>
        ...
    }
}
```

规则（`Unit_modding` §Models）：

1. `sprite = SPRITE` 默认匹配实体名 **`SPRITE_entity`**，且该模型只给「师模板中该 sub-unit 占多数」的单位使用。
2. 可按前缀覆盖，优先级从低到高：默认名 → graphical culture 前缀（`middle_eastern_gfx_SPRITE_entity`）→ 国家 tag（`BHR_SPRITE_entity`）→ cosmetic tag（`COSMETICTAG_SPRITE_ENTITY`）。
3. 变体用 `clone = <基础 entity>` 复用全部字段，只改 `pdxmesh`：

```
entity = {
    name = SPRITE_entity
    pdxmesh = example_mesh
    default_state = idle
    state = { name = attack  animation = attack  animation_blend_time = 0.0 animation_speed = 1.0 }
    state = { name = defend  animation = defend  animation_blend_time = 0.3 animation_speed = 1.0 }
    state = { name = support_attack animation = support_attack animation_blend_time = 0.3 animation_speed = 1.0 }
    state = { name = move    animation = move    animation_blend_time = 1.0 animation_speed = 1.0 }
    state = { name = retreat animation = retreat animation_blend_time = 0.3 animation_speed = 1.0 }
    state = { name = death   animation = death   animation_blend_time = 0.3 animation_speed = 1.0 }
    state = { name = idle    animation = idle    animation_blend_time = 0.3 animation_speed = 1.0 }
    state = { name = training animation = training animation_blend_time = 0.3 animation_speed = 1.0 }
    scale = 0.8
}
```

单位实体的标准状态集：`attack`、`defend`、`support_attack`、`move`、`retreat`、`death`、`idle`、`training`；`default_state = idle`。

#### 3.9 常见错误（模型不显示 / 贴图丢失 / 动画名错）

wiki **没有**记录这些故障的专门章节（`Troubleshooting.wiki` 无 entity/model 条目，仅有 `gfx/models/supply/railroad.shader` 报错→地图 bmp 尺寸问题）。以下为按 wiki 字段语义可确定的失配点，标注为推断：

- **模型不显示**：① `sprite = X` 但 `gfx/entities/*.asset` 里没有 `X_entity`（名字少/多 `_entity` 后缀）；② entity 的 `pdxmesh` 名与 `.gfx` 里 `pdxmesh.name` 不一致；③ `.gfx` 没放进 mod 或路径不在 `gfx/entities/`；④ 单位所属师模板中该 sub-unit 不占多数，走了默认模型；⑤ `create_entity` 的 `min_zoom` 设得比当前缩放更近，实体被过滤。
- **贴图丢失**：entity/`.gfx` 层没有贴图字段，贴图由 `.mesh` 自带引用——丢贴图要在 `.mesh` 与 `.dds` 侧查，`Entity_modding` 不涉及。
- **动画名写错**：`state.animation` 写的是 **pdxmesh 的 `animation.id`**，不是 `animation.type`，也不是 `.asset` 里的 `animation.name`；三者混淆即表现为动作不播或 T-pose。`set_entity_animation` 的参数则直接对应 `gfx/models/**/*.asset` 的动画，两者引用层不同。

---

## 第 35 章 情报机构与突袭

### 情报机构（Intelligence agency）

#### 页面归属

两个页面都要看：

- `Intelligence agency`（pageid 5604）：**玩法页**，讲 operative/mission/升级/密码学/Spy Master/logo，无脚本字段。
- `Intelligence agency modding`（pageid 17284）：**真正的 modding 页**，但只覆盖「外观三件套」。

#### 文件位置

| 内容 | 路径 |
|---|---|
| 机构外观定义 | `<yourmod>/common/intelligence_agencies`，原版默认 `00_intelligence_agencies.txt` |
| 升级项 | `common/intelligence_agency_upgrades`（由 Effect 页 `upgrade_intelligence_agency` 注明） |
| 行动 token | `common/operation_tokens/*`（由 Effect 页 `add_operation_token` 注明） |
| 机构图标 gfx | `interface/countryintelligenceagencyview.gfx` |
| 图标贴图 | `gfx/interface/operatives/agencies` |
| operative 特质 | `common/unit_leader/*.txt` |

wiki 明说不要覆盖原版 `00_intelligence_agencies.txt`，另建文件。

#### 机构定义模板

```
intelligence_agency = {
    picture = GFX_intelligence_agency_NOR_old_norse
    names = { "Hugin" "Munin" }

    default = {
        tag = NOR
    }
    available = {
        original_tag = NOR
    }
}
```

| 字段 | 作用 |
|---|---|
| `picture` | 图标 sprite |
| `names = { ... }` | 候选名列表，可写死字符串或本地化 scope（原版多写死）。调用 `create_intelligence_agency` 时随机取一个，除非 effect 里另行指定名字 |
| `default = { <triggers> }` | 该国创建机构时的默认选择（如英国默认 MI6 图标 + SIS/MI6 名） |
| `available = { <triggers> }` | 手动创建时可选的候选项。**只影响图标**，因为机构系统的运作方式如此 |

纯通用图标也要定义：

```
intelligence_agency = {
    picture = GFX_intelligence_agency_mod_generic_1
    names = { "Svalbard Intelligence Group" }   # 不会显示，但留一个更安全
    default = { always = yes }                   # 进随机池，'Rooke' 通常优先
    available = { always = yes }
}
```

#### 图标 GFX（易错）

选中态**不会自动生成**，必须自己做两帧：

```
spriteType = {
    name = "GFX_intelligence_agency_NOR_old_norse"
    textureFile = "gfx/interface/operatives/agencies/agency_logo_NOR_old_norse.dds"
    noOfFrames = 2
}
```

- `noOfFrames = 2` 表示沿 X 轴切两帧；机构图标除 `noOfFrames` 与两张帧图外不需别的配置。
- 单图尺寸 **234×119**（宽×高），两帧中线在 X=117。
- 左帧未选中，右帧选中态。原版选中态是 2px 描边（白到机构主色的渐变）+ 快速衰减的投影。

#### 升级项（5 条支线，1.16 数值）

每级消耗若干民用工厂，投入 `AGENCY_UPGRADE_DAYS` 天；雇 Illusive Gentleman 顾问可 −15%（有效 25 天）。

Intelligence：Economy/civilian、Army、Naval、Airforce 各 5 厂，对应情报 +25%（相对值，不是叠加）。

Defense：
- Passive defense 5 厂 — Counter intelligence +1.5 / +1.25 / +1 / +1（第 1–4 级）
- Anti-partisan 5 厂 — Root Out Resistance 效果 +25%（第 1、2 级）

Operations：
- Blueprint stealing 5 厂 — Steal Blueprint 效率 +25%
- Portable radios 8 厂（需 Radio）— Coordinated Strike 效率 +100%
- Invisible Ink 5 厂 — operative/被渗透资产给的情报 +20%，Steal Blueprint 风险 −25%
- Plastic explosives 8 厂 — Targeted Sabotage +25%，Strengthen Resistance +25%
- Suicide pills 5 厂 — 被俘即死几率 +10%，自身 operative 被发现概率 −0.05%

Operative Training：
- Localized training centers 10 厂 — 敌国/被占友国国籍招募几率各 +25%，招募选项 +1，解锁 Local Agent Recruitment 决议
- Commando training 5 厂 — 招到 Commando 特质几率 +100%（实际约 +900%，因为无此升级时特质权重 ×0.2），隐藏效果：可积累该特质经验
- Interrogation techniques 5 厂 — 敌 operative 捕获率 +100%，情报榨取率 +25%
- Diplomatic Training 5 厂 — Control Trade / Diplomatic Pressure 效果各 +25%
- Psychological Warfare 8 厂 — Propaganda / Boost Ideology 效果各 +25%

Cryptology Department：
- Form Department 8 厂 — Decryption power +25、Cryptology level +1、解锁该部门
- Radio Interception Group 5 厂 — Decryption power +25 / +10
- Machine-Assisted Decryption 10 厂（需 Mechanical Computing + 前置全满）— +25 / +15 / +10
- Government Cypher School 5 厂 — Cryptology level +1 ×3 级
- Machine-Assisted Encryption 15 厂（需 Mechanical Computing + 前置全满）— Cryptology level +2 ×3 级

密码学公式（wiki 原文）：

```
Total Cryptology strength = 12000 + 4250 * Cryptology level
```

`CRYPTO_BASE_CRYPTO_LEVEL` 起步、`CRYPTO_CRYPTO_LEVEL_PER_CRYPTO_UPGRADE` 每级增量；
同时解多国密码会把 Decryption power 均分；非交战国 Decryption power −50%（`common/modifiers/00_static_modifiers.txt`）。
破译后被动加成：Air detection +5%、Interception Mission Efficiency +25%、四类 Cipher Bonus 各 +10%；
公开破译结果额外 30 天主动加成（Invasion Penalty −15%、Planning Speed +50%、对目标国 Defense/Breakthrough +15%、
Invasion Preparation Speed +50%、四类 Cipher Bonus 各 +50%）。

#### 行动（operation）定义：wiki 的边界

`common/operations/*.txt` 的脚本键名（phase / cost / outcome / equipment / risk 的写法）**wiki 未覆盖**。
`Category:Modding` 全表没有 Operations modding 页；`Operations` 页（5646）是玩法页。

wiki 能提供的行动数据结构（1.17，来自 `Operations` 页）：

| 维度 | 内容 |
|---|---|
| phase | 每个行动 3 段：infiltration → execution → exfiltration；每段从池里随机抽，受科技、operative 技能、可用装备影响 |
| phase 例外 | Plant False Intelligence 没有潜入/撤离，改为 3 段 execution；Orchestrate Coup、Coordinated Strike 没有撤离段，改成额外一段 execution |
| cost | 装备（Infantry/Support Equipment、Transport Plane、Small Airframe）或「N 个民用工厂 × N 天」；各 phase cost 相加为总成本，已执行过的行动成本会缩放 |
| risk | 分档，由 `NOperatives` 的 `RISK_LEVELS` 决定；0%（Plant False Intelligence）到低/中/高三档；独特行动自行覆盖风险值（20%–50%） |
| 门槛 | operative 数量（1–3）、目标国 network strength、前置 focus/决议、是否交战中、抵抗度等 |
| 产出的 outcome | 独特行动各有专属 effect（事件链、转州、杀领袖、抵抗度变动等），通用行动走分类结果 |

独特行动表（`Operations` 页「Unique operations」）列出的字段：
DLC / Operation / Performed by / Target / Key prerequisites / Days / Operatives / Network / Cost / Risk / Effect on success。

#### operative 的创建与招募

口子在 Effect 页 3.22 Intelligence（country scope，1.9 起）：

```
create_operative_leader = {
    name = "Jacques Duclos"
    GFX = GFX_portrait_jacques_duclos
    traits = { operative_infiltrator operative_natural_orator }
    bypass_recruitment = no
    available_to_spy_master = yes
    nationalities = { FRA POL }
}
```

| 参数 | 说明 |
|---|---|
| `bypass_recruitment` | **唯一非可选**。`yes` 直接进可用列表，`no` 需玩家招募 |
| `available_to_spy_master` | 能否被 spy master 招募；用 true 时 `bypass_recruitment` 应为 `no` |
| `portrait_tag_override` | 随机头像时改用指定国家的头像池 |
| `name` | 名字 |
| `GFX` | 头像，必须在 `interface/*.gfx` 里定义成 `spriteType` |
| `nationalities = { <tag> }` | 国籍 |
| `traits = { ... }` | 初始特质，特质定义在 `common/unit_leader/*.txt` |
| `gender` | `male` / `female`，默认随机 |

配套 effect：`kill_operative`、`capture_operative`（可带 `ignore_death_chance`）、`free_operative`、
`free_random_operative`（`captured_by` / `all`）、`turn_operative`（策反，按死亡处理并触发对应 on_action）。

招募池本身受「Localized training centers」「Commando training」等升级影响（敌国国籍招募几率、特质权重、选项数 +1）。

#### 常见错误

1. **只写图标不写 `names`**：wiki 原文「you must give it at least one possible name, or else the definition won't be valid」。
2. **把图标当普通 sprite 用**：不写 `noOfFrames = 2` 就没有选中态，尺寸不是 234×119 会错位。
3. **`create_operative_leader` 的头像写成文件路径**（`gfx/leaders/TAG/x.dds`）——必须是 `spriteType`。
4. **`available` 里写了复杂 trigger 想区分机构功能**：原文说明它只影响图标。
5. **直接覆盖 `00_intelligence_agencies.txt`**：与 DLC、其它 mod 冲突，wiki 明确不建议。
6. **忘写 `bypass_recruitment`**：这是唯一必需参数。

### 突袭（Raids）

#### 页面归属与结论

- `Raids` → `#REDIRECT [[Raid]]`；`Raid`（pageid 17233）是**玩法页**，无脚本字段。
- `Category:Modding` 里没有 Raids modding 页；`allpages&apprefix=Raid` 只有 `Raid`、`Raiding coordination`、`Raids`；
  `Modding` 总页的 Game data 段也未列 raids。

**wiki 上没有 `common/raids/*.txt` 的模板与字段文档**。`units` / `count` / `duration` / `effects` / `ai_will_do`
这些字段名无法从 wiki 取得，此处不编。wiki 能给的只有：raid 的类型与数据维度、以及脚本侧可调用的 raid effect。

#### raid 的数据维度（`Raid` 页表格列名，1.16）

| 列 | 含义 |
|---|---|
| Name | 行动名 |
| Preparation Time | 准备天数（14 / 30 / 45 / 90 天） |
| Required Equipment | 需要的装备与数量（如 10 架战略或洲际轰炸机 + 1 枚核弹；70 架战术/战略轰炸机；1 支伞兵（≥3 营）+ 10 架运输机 + 200 支援装备） |
| Required Special Projects | 需要的特殊项目（Nuclear Fission Bomb / Nuclear Warheads / Air bouncing bomb / Earthshaker Bomb） |
| Starting Point | 起飞/发射点（Air Base、Rocket Site 或 Submarine） |
| Targets | 目标（敌方设施、运河、水坝、油田省（>24 oil）、超级炮、地标） |
| Additional Requirements | 独特 raid 的前置（交战国、完成的 focus、抵抗度 > 25 等） |
| Success Factors | `Base Success` + 一组加减项（Experience / Agility / Reliability / Air Defense / Air Superiority / Interception / Static anti-air / Radar coverage / Target information / Organization / Strength / Reconnaissance / Resistance / Enemy Units / Intel） |
| Base Critical Success | 大成功的基础概率（10% / 15%） |
| Effect | 按 **Failure / Limited Success / Success / Critical Success** 四档分列 |

四档结果对应图标：`Raid outcome failure icon.png`、`Raid outcome limited success icon.png`、
`Raid outcome success icon.png`、`Raid outcome critical success icon.png`。

#### 三类 raid 与原版数量

- Nuclear Raids 4 种：Nuclear Strike（30 天，Base 50%）、Nuclear Missile Strike（14 天，Base 80%）、
  Thermonuclear Strike（30 天，Base 50%）、Thermonuclear Missile Strike（14 天，Base 80%）。
  效果按档位给 `Fallout (Atomic)`（180/365/730 天）或 `Fallout (Thermonuclear)`（730 天），
  惩罚项：Army Defense、Army Speed、Maximum Entrenchment、Factory Repair Speed、Factory Free Repair Speed、Local Resources。
- Air Raids 5 种通用：Facility Strike、Lock Bombing Raid、Dam Busting、Oilfield Raid、Mega Gun Emplacement Strike
  （Preparation Time 45–90 天，Base 65%，Base Critical 15%）。
  另有 7 个独特 raid：Austria 的 Reichstag Bombing、UK 的 Reichstag Bombing、任意反德国家的 Operation Jericho、
  Germany 的 Big Ben Bombing / Statue of Liberty Bombing / Kremlin Bombing、China 的 Leaflet Dropping Over Japan。
  独特 raid **只能发一次**。
- Paratrooper Raids 2 种通用：Steel Mine Raid（90 天，Base 60%）、Pathfinder Raid（30 天，Base 60%，
  要求目标省有 ≥5% 准备度的登陆战），加 Germany 的独特 Eben Emael（30 天）。

代表数值（Oilfield Raid，可直接当模板参考）：
90 天 / 40 架战略轰炸机 / 目标为油 >24 的省 / Base 65% / Critical 15%；
Failure 损失 95% 轰炸机；Limited 损 65% + `Refinery lightly damaged` 90 天（−25% 当地石油）；
Success 损 25% + 10 空军经验 + `Refinery damaged` 180 天（−50%）；Critical 损 10% + 20 经验 + `Refinery critically damaged` 360 天（−75%）。

#### 脚本侧：raid effect（`Effect` 页，1.15）

state scope（4.4 Raids，仅 1 条）：

```
raid_reduce_project_progress_ratio = 0.1
```

减少该 state 内特殊项目的进度；root scope 是 raid instance scope；数值是「占完成所需的百分比」，0–1。

Raid scope（第 9 节，必须在 raid scope 内调用）：

| effect | 参数 | 说明 |
|---|---|---|
| `add_raid_history_entry` | `<bool>` | 往 raid 历史加一条 |
| `raid_add_unit_experience` | `<float>`（可用变量） | 给分派到该 raid 的任何单位（师、空军联队）经验；0.2 = 拿满级所需经验的 20% |
| `raid_damage_units` | `damage` / `org_damage` / `str_damage` / `plane_loss` / `ratio` | 对地面单位施加伤害；对飞机则是「损失多少架」；`ratio = yes` 时按当前量的比例扣 |

```
raid_damage_units = { damage = 0.5 ratio = yes }        # 单位 50% 伤害
raid_damage_units = { org_damage = 20 str_damage = 10 } # 强度 −10、组织度 −20
raid_damage_units = { plane_loss = 0.4 ratio = yes }    # 损失 40% 飞机
raid_damage_units = { plane_loss = 5 }                  # 损失 5 架
```

#### 与决议/任务的区别

wiki **没有** raid 与 decision / national focus 的字段级对照段落，只有玩法层的差异可读出来：

- raid 有独立的准备期（Preparation Time）与必备装备清单，决定/国策没有「押装备、等 N 天再掷骰」这套；
- raid 的结果是 **4 档**（Failure / Limited Success / Success / Critical Success），每档损失与效果都不同；
  决定/国策是二元的完成/未完成；
- raid 有 `Base Success` 与 `Base Critical Success` 两个基础概率，再叠一堆战场/情报修正；
- 独特 raid 只能触发一次，通用 raid 可重复；
- raid 的效果通过 raid scope / state scope 的专用 effect 实现（上表），而不是 decision 的 `complete_effect`。

---

## 附录 A 取材清单与已知缺口

### A.1 已抓取并使用的页面

原始 wikitext 全部落在 `work/tmp/wiki/`，可用文本编辑器直接查原文。

| 页面 | 落在 | 大小 | 用于 |
|---|---|---|---|
| Modding | `Modding.wiki` | 82,412 B | 第 1、2 章 |
| Scopes | `Scopes.wiki` | 74,265 B | 第 3 章 |
| Triggers | `Triggers.wiki` + `Triggers_s48_scripted_triggers.wiki` | 100,078 B + 10,334 B | 第 4、6 章 |
| Effect | `Effect.wiki` + 三节补充 | 100,089 B + 15,338 B | 第 5、6 章 |
| Data structures（Variables / Event targets） | `Variables.wiki`、`Event_target.wiki` | 52,012 B、4,185 B | 第 4、7 章 |
| Modifiers | `Modifiers.wiki` | 100,080 B | 第 8 章 |
| National_focus_modding | `National_focus_modding.wiki` | 76,734 B | 第 9 章 |
| Event_modding | `Event_modding.wiki` | 44,663 B | 第 10 章 |
| Decision_modding | `Decision_modding.wiki` | 32,168 B | 第 11 章 |
| Idea_modding | `Idea_modding.wiki` | 25,499 B | 第 12 章 |
| Character_modding | `Character_modding.wiki` | 57,897 B | 第 13 章 |
| Balance_of_power_modding | `Balance_of_power_modding.wiki` | 11,825 B | 第 14 章 |
| Achievements | `Achievements.wiki` | 100,299 B | 第 14 章 |
| Technology_modding | `Technology_modding.wiki` | 52,728 B | 第 15 章 |
| Equipment_modding | `Equipment_modding.wiki` | 16,278 B | 第 16 章 |
| Unit_modding | `Unit_modding.wiki` | 15,576 B | 第 17 章 |
| Division_modding | `Division_modding.wiki` | 20,247 B | 第 18 章 |
| Ship / Naval_missions / Air_missions / Air_warfare（摘录） | `Naval_Air_reference.wiki` | 14,817 B | 第 18 章 |
| Country_creation | `Country_creation.wiki` + `Country_creation_OOB.wiki` | 48,660 B + 13,821 B | 第 18、19 章 |
| State_modding | `State_modding.wiki` | 13,025 B | 第 20 章 |
| Map_modding | `Map_modding.wiki` | 82,646 B | 第 20 章 |
| Bookmark_modding | `Bookmark_modding.wiki` | 19,670 B | 第 21、22 章 |
| Custom difficulty | `Custom_difficulty.wiki` | 94,250 B | 第 22 章 |
| On_actions | `On_actions.wiki` | 37,241 B | 第 23 章 |
| Defines | `Defines.wiki` | 100,078 B | 第 24 章 |
| Localisation | `Localisation.wiki` | 67,112 B | 第 25 章 |
| Interface_modding | `Interface_modding.wiki` | 23,543 B | 第 26 章 |
| Graphical_asset_modding | `Graphical_asset_modding.wiki` | 13,056 B | 第 27 章 |
| Scripted_GUI_modding | `Scripted_GUI_modding.wiki` | 24,508 B | 第 28 章 |
| AI_modding | `AI_modding.wiki` | 79,144 B | 第 29 章 |
| Console_commands | `Console_commands.wiki` | 34,412 B | 第 30 章 |
| Troubleshooting | `Troubleshooting.wiki` | 17,192 B | 第 31、32 章 |
| Mods、Nudger | `Mods.wiki`、`Nudger.wiki` | 1,848 B、22,500 B | 第 1 章 |

### A.2 重定向页

下面这些标题是 `#REDIRECT`，正文在别处，已按重定向目标取材：

| 请求标题 | 实际位置 |
|---|---|
| `Scripted_effects` | `Effect#Scripted effects` |
| `Scripted_triggers` | `Triggers#Scripted triggers` |
| `Variables` | `Data structures#Variables` |
| `Event_target` | `Data structures#Event targets` |
| `Dynamic_modifiers`、`Static_modifiers` | `Modifiers` 对应分节 |
| `Scripted_GUI` | `Scripted_GUI_modding` |
| `Game_rules` | `Custom difficulty` |
| `Nudge` | `Nudger` |
| `Opinion` | `Diplomacy` |

### A.3 不存在的页面

`Characters`、`Opinion_modding`、`Opinions`、`Game_rules_modding`、`Naval_modding`、`Air_modding`、`Military_modding`、`Ship_modding`、`Modding_tools`。

对策：
- 海空军没有独立 modding 页，脚本规则只在 `Division_modding` 的 OOB 章节，任务类型与常量是硬编码，只能引用不能新增（见第 18 章）。
- 舆论没有独立页，`Opinion` 重定向到 `Diplomacy`，本文只写第 13 章末尾那一节能确证的内容。
- 游戏规则的脚本格式只在 `Bookmark_modding` 的 Game rules 一节（见第 22 章）。
- 工具清单只在 `Modding#Tools & utilities` 三条。

### A.4 已知缺口

| 缺口 | 影响 | 现状 |
|---|---|---|
| `Triggers` 第 26–52 节 | 已按 `action=raw&section=N` 分节补抓（27–47 节共 222 条条件已收入第 4 章） | 已补，见 A.6 |
| `Modifiers` 第 36–47 节 | 已补抓 272 个修正键，收入第 8 章 | 已补，见 A.6 |
| `Achievements`、`Custom_difficulty`、`Map_modding` 只用到与 mod 开发直接相关的部分 | 成就的完整触发条件表、地图的图形化流程未展开 | 需要时查原页 |
| 音乐、音效、3D 模型、entity | 已补：第 33、34 章 | 已补，见 A.6 |

### A.5 一手校验

除 wiki 外，写法已在本地工程上对照过：

- `mods/muvluvCNsub_xuerong`：110 个文件，含 `common/` 下 15 个子目录、`events/`、`interface/`、`localisation/{english,simp_chinese}`、`music/`，描述符 `supported_version="1.19.*"`、`dependencies={ "muvluvCN" "muvluvCNsub" }` 与第 1 章的结构规则一致。
- `focus_editor` 系列导出的国策树与 `common/national_focus/` 的字段用法一致（`x`/`y` 网格、`prerequisite`、`completion_reward`）。

### A.6 第二轮补抓（同日）

第一版留的缺口已按 `action=raw&section=N` 分节补齐，补抓结果如下。

| 内容 | 节号 | 产出 | 并入位置 |
|---|---|---|---|
| `Triggers` 国家作用域（情报 / AI / 角色 / 和平会议） | 27–30 | 52 条条件 | 第 4 章 |
| `Triggers` 阵营与州作用域（含抵抗与顺从） | 31–34 | 58 条条件 | 第 4 章 |
| `Triggers` 角色作用域（顾问 / 领袖 / 将领 / 特工 / 科学家） | 36–41 | 59 条条件 | 第 4 章 |
| `Triggers` 战斗、师、军工组织、合同、特殊项目、元条件 | 42–47 | 53 条条件 | 第 4 章 |
| `Modifiers` 战斗类（陆战 / 登陆 / 海战 / 航母 / 空战 / 针对性） | 36–42 | 190 个修正键 | 第 8 章 |
| `Modifiers` 州、将领、科学家、战略区作用域与叠加规则 | 43–47 | 82 个修正键 | 第 8 章 |
| `Music modding`、`Sound modding` | 整页 | 第 33 章 | 新增 |
| `Entity modding` | 整页 | 第 34 章 | 新增 |
| `Map_modding` 的地形节（`Terrain_modding` 是重定向） | 11 | 第 20 章 | 追加 |
| `Intelligence agency`、`Raids` | 整页 | 第 35 章 | 新增 |
| `Equipment_modding` 的机体与模块节 | — | 第 16 章 | 追加 |

补抓方法与第一轮相同，但有两个新约束：

- **必须按节抓**。整页 `action=raw` 超过 100 KB 会被截断，`section=N` 单节通常几 KB。
- **节之间有速率限制**。连续请求会返回 429，间隔 4–5 秒可稳定拿到 200；12 节连发会中途失败。

`section=N` 的 N 是页面解析出的 section index，取法：

```
https://hoi4.paradoxwikis.com/api.php?action=parse&page=Triggers&prop=sections&format=json&formatversion=2
```

返回的 `sections[].index` 就是可传给 `section=` 的值。注意二级标题（`== State scope ==`）展开时会一次返回整个块，子节编号因此可能与目录里的 `number` 不同——`Triggers` 的 `==Character scope==` 就属于这种情况，实际内容落在 `section=35`，其子节从 36 起。

### A.7 第二轮之后仍缺的部分

| 缺口 | 原因 | 替代做法 |
|---|---|---|
| `common/raids/*.txt` 的脚本字段（`units`、`count`、`duration`、`effects`、`ai_will_do`） | wiki 上 `Raids` 只有玩法说明，`Category:Modding` 全表、`allpages&apprefix=Raid`、`Modding` 总页三处都没有相应文档 | 读本体 `common/raids/` 内的真实文件；效果侧只能调用 `raid_damage_units`、`raid_add_unit_experience`、`add_raid_history_entry`、`raid_reduce_project_progress_ratio` |
| `common/operations/` 的脚本结构 | `Intelligence agency` 是玩法页，行动只有 phase / cost / risk 的玩法维度 | 同上，读本体文件 |
| `music_playlist`、音乐采样率要求、mod 描述符的音乐字段 | `Music modding` 页没有这些内容 | 只能按本体 `music/` 现有写法对照 |
| `soundeffect` 的 `pitch` 字段 | 该页没有此字段，音高只能靠 `playbackrate_random_offset` 随机扰动 | — |
| entity 的贴图挂接 | `Entity_modding` 完全没有 `texturefile` 与 `.mesh` 说明，贴图随 `.mesh` 自带 | 用 3D 软件侧解决 |
| `Model modding`、`3D models` | 两页均 404 | 模型内容只有 `Entity_modding` 一处来源 |

---

## 附录 B 路径速查与任务映射

### B.1 我要做什么 → 改哪里

| 目标 | 文件位置 | 详见 |
|---|---|---|
| 新建一个国家 | `common/country_tags/*.txt`、`common/countries/TAG.txt`、`history/countries/TAG - Name.txt`、`common/characters/` | 第 19 章 |
| 给国家加国策树 | `common/national_focus/*.txt` + `interface/goals.gfx` 里的 `GFX_*` 与 `GFX_*_shine` | 第 9 章 |
| 加一个事件 | `events/*.txt` + `localisation/*/` + `gfx/event_pictures/` 与 `interface/*.gfx` | 第 10 章 |
| 加一个决议 | `common/decisions/*.txt` + `common/decisions/categories/*.txt` | 第 11 章 |
| 加国家精神 / 法案 / 设计商 | `common/ideas/*.txt` + `common/idea_tags/*.txt` | 第 12 章 |
| 加领袖 / 将领 / 顾问 | `common/characters/*.txt`、`common/country_leader/*.txt`（特质） | 第 13 章 |
| 改力量平衡 | `common/balance_of_power/*.txt` | 第 14 章 |
| 加科技 | `common/technologies/*.txt` + `interface/countrytechtreeview.gui`（新 folder 才要） | 第 15 章 |
| 加装备（枪、坦克、飞机） | `common/units/equipment/*.txt` + `interface/equipmentdesigner/` | 第 16 章 |
| 加兵种（营） | `common/units/*.txt` + `common/unit_tags/00_categories.txt` + `interface/subuniticons.gfx` | 第 17 章 |
| 给国家配初始部队 | `history/units/*.txt` + `history/countries/` 里的 `oob =` | 第 18 章 |
| 改州（人口、建筑、归属） | `history/states/NNN-Name.txt` | 第 20 章 |
| 改地图 | `map/*`（见 20.5 起） | 第 20 章 |
| 改剧本起始日期与国家 | `common/bookmarks/*.txt` | 第 21 章 |
| 加游戏规则选项 | `common/game_rules/*.txt` | 第 22 章 |
| 在世界初始化 / 每月触发逻辑 | `common/on_actions/*.txt` | 第 23 章 |
| 改硬编码常数（起始日期、上限等） | `common/defines/*.lua` | 第 24 章 |
| 加文本 | `localisation/<语言>/*.yml`（UTF-8 **带 BOM**） | 第 25 章 |
| 改界面 / 换背景 | `interface/*.gui`、`interface/*.gfx` | 第 26 章 |
| 换图标与贴图 | `gfx/interface/`、`interface/*.gfx` 里的 `spriteType` | 第 27 章 |
| 做自定义面板 | `common/scripted_guis/*.txt` + `interface/*.gui` | 第 28 章 |
| 教 AI 怎么打 | `common/ai_strategy/*.txt`、`common/ai_strategy_plans/*.txt`、`common/ai_templates/*.txt` | 第 29 章 |
| 让 AI 研究新科技 | `common/ai_focuses/*.txt` | 第 15 章 15.8 |
| 复用一段效果 / 条件 | `common/scripted_effects/*.txt`、`common/scripted_triggers/*.txt` | 第 6 章 |
| 存一个 scope 供后面用 | `event_target`、变量，见第 4 章与第 7 章 | 第 4、7 章 |

### B.2 目录职责对照

| 目录 | 放什么 | 容错 |
|---|---|---|
| `common/` | 所有数据库定义 | 按文件名加载，任意命名 |
| `common/units/` 与 `common/units/equipment/` | 前者是 `sub_units`（师级营），后者是装备原型与型号 | **写反不报错，只是对象不出现** |
| `history/` | 开局状态：国家、州、部队 | `history/units/` 靠 `oob =` 点名加载，`replace_path` 对它无效 |
| `events/` | 事件 | 靠 `add_namespace` 分号段 |
| `interface/` | `.gui` 界面布局、`.gfx` sprite 定义 | sprite 名错 → 默认图；贴图路径错 → 全透明 |
| `gfx/` | 图片与模型 | 国旗在 `gfx/flags/`，名字有硬格式 |
| `localisation/<语言>/` | `.yml` | 必须带 BOM；`localisation/<语言>/replace/` 可只覆盖单个 key |
| `map/` | 地图位图与索引 | 尺寸、位深、CSV 换行符都有硬要求 |
| `sound/`、`music/` | 音频与 `.asset` 定义 | 见原版同名文件结构 |

### B.3 三个最容易放错的位置

1. **装备 vs 单位**：`common/units/equipment/` 是装备，`common/units/` 是营。放反了游戏不报错，只是「能造装备但没有可用营」或反之。
2. **原始国策图标与闪光图**：`GFX_x` 与 `GFX_x_shine` 必须成对定义在 `.gfx` 里，文件名带 `shine` 不算数。
3. **`history/units/` 的 OOB**：写了文件不等于生效，必须在国家历史里 `oob = "TAG_1936"` 点名，或者用 `set_oob`。

---

## 附录 C 开发纪律与自检清单

### C.1 每次提交前

1. **文件编码**：`.txt` / `.gui` / `.gfx` / `.asset` 无 BOM，`.yml` 带 BOM。用 `git diff` 看，二进制差异就是编码被改了。
2. **括号配平**：整个文件从头走一遍 `{` 与 `}`，数量相等且同级成对。多余 `}` 会让文件当场截断，症状是「后半段全部失效」。
3. **路径分隔符**：脚本里一律 `/`。`\\` 会被当转义符，在 `.gfx` 的 `texturefile` 里尤其致命（表现为图标全透明）。
4. **本地化键齐全**：新加的每个 id 都有对应的名字键与 `_desc` 键，且键名与代码里写的字符串**逐字符**一致（大小写敏感）。
5. **sprite 齐全**：每个 `GFX_` 引用都真实定义在某个 `.gfx` 里，且该 `.gfx` 的 `texturefile` 指向真实存在的图片。国策还要 `_shine`。
6. **`error.log` 干净**：进游戏、开一局、等 1 分钟、退出，读 `logs/error.log`。新出现的行必须能解释。

### C.2 结构纪律

| 做法 | 理由 |
|---|---|
| 新增文件而不是复制原版文件 | 版本更新时不用重新合并；覆盖原版文件是维护成本的主要来源 |
| 文件名带 mod 前缀 | 目录里所有 `.txt` 都会被读，用别人不会用的名字避免与其它 mod 撞名 |
| 子 mod 必须写 `dependencies` | 否则父 mod 的 `replace_path` 会连带卸掉你的文件；加载顺序也不会让位于你 |
| `replace_path` 只在必须时用，且两个 `.mod` 都写 | 它卸掉的是「直接子文件」，容易连累别的系统；漏写一处就不生效 |
| 不要修改游戏本体目录 | Steam 更新会静默覆盖 |
| 每个新 id 带国家 tag 前缀 | focus、decision、idea 的 id 全局共享命名空间，重名会造成静默串线 |

### C.3 性能纪律

`HOI4` 的脚本按求值频率分三档，写错档位是最常见的性能问题：

| 频率 | 位置 | 注意 |
|---|---|---|
| 开局 / 读档一次 | `allowed`、`focus_tree` 的 `country`、`ai_strategy_plan` 的 `allowed`、`bypass_if_unavailable` | 改完必须重开或重载，热改不生效 |
| 每天 | `on_daily`、决议 `available` 的背景检查、`remove_trigger`、`cancel_trigger`、`activation` | 逻辑重的东西别放这里 |
| 每帧 | 界面 `visible`、决议 `visible` | 只放最便宜的判断（`has_war`、flag 检查），别放数组遍历与 `any_` 扫描 |

具体规则：

- `on_daily` 会对**每个国家各跑一次**，块内再点名某个国家，等于把工作量乘以国家数。要限定国家就在 `on_actions` 里用 `effect = { TAG = { ... } }` 包一层（只跑一次块，但仍每国一次触发）。
- 能用 `target_root_trigger` 先筛掉大半目标的，别全部塞进 `target_trigger`。
- 自动事件每 20 天（`NCountry:EVENT_PROCESS_OFFSET`）才检查一次 `trigger`，把「某国完成某国策」这类事件做成自动事件，最坏要等 20 天且反复评估。改用焦点奖励里 `country_event = { id = ... hours = 6 }`。
- 大量 `every_country` 嵌套 `every_owned_state` 会明显掉帧；能改成遍历数组或提前算好 flag 的就改。

### C.4 数值口径纪律

同一字段在不同系统里语义相反，混用不报错但结果全错：

| 字段 | 语义 |
|---|---|
| 装备 `maximum_speed` | 绝对值（km/h） |
| 单位 `maximum_speed` | 乘算加成（`0.5` = +50%） |
| `factor` | 乘数（`factor = 0` 直接把权重清零） |
| `add` | 加数 |
| 修正里的比例 | 小数，`0.3` = 30% |
| `random_list` 的数字 | 权重，不必凑成 100 |
| `chance` / `random` 的整数 | 0–100 的百分数 |
| 变量 | 精度 0.00001，范围约 ±2.1e9 |

### C.5 发布前

1. `descriptor.mod` 与用户侧 `.mod` 的 `name`、`version`、`supported_version`、`dependencies` 一致，`path` 只在用户侧出现。
2. `replace_path` 两个文件都有，且被替换目录里至少有一个非空文件。
3. 缩略图 `thumbnail.png` 在 mod 根目录，< 1MB。
4. 用**全新存档**测一遍：开局、跑 1 年、读档、再看 `error.log`。
5. 关掉所有其它 mod 单测一次，再按实际播放集测一次。
6. 不把游戏本体文件、DLC 内容、别人的美术资源打进包里。

### C.6 三条反模式

- **用空文件覆盖原版文件**：能被用来「停用」某个定义，但同名文件在大小写不同的情况下会加载两次，且 `replace_path` 之后行为不一致。想停用就改扩展名。
- **在 `history/countries/` 里堆 effect**：历史文件的 effect 块没有 `FROM`，也没有 `on_add` 之类的钩子；写复杂逻辑要挪到 `on_startup` 或隐藏事件里。
- **靠 GUI 隐藏代替逻辑禁用**：被隐藏的对象照样能被 AI 使用、被脚本引用。禁用要在逻辑层（`allow`、`available`、`available = { always = no }`）。
