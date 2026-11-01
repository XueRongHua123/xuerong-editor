# 雪绒的钢铁雄心编辑器 · 方向评估与任务清单

日期：2026-11-02
基线版本：v1.23.35（2026-11-02 夜执行，P0/P1 已结）
适用对象：接手开发的执行方

---

## 一、现状

### 规模

```
focus_editor.py            18,415 行
focus_editor_index.html    12,501 行
qa/world_stubs.py             235 行（新）
合计                       31,151 行
```

### 能力面

| 维度 | 数量 | 说明 |
|---|---|---|
| HTTP 路由 | 199 | 覆盖国家、州、人物、决议、国策、事件、科技、精神、军队、海军、空军、剧本、本地化、地图 |
| 静态诊断 | 17 个检查函数 | schema 5 个块（误报 0.00227%）+ 引用检查 + map 格式 12 项 + replace 占位（本轮新增 1 个）|
| qa 工具脚本 | 156 个 | 生成器（mapgen 6 模块）、体检、回归、发布 |

### 已验证成立的能力

**地图生成**（这是核心，有硬证据）：

- `map/` 目录 12 项体检全 PASS
- 游戏实测 `Loaded 208 provinces` + `Executing History`
- error.log 里指向生成物的记录 0 条
- 40 陆省 + 167 海省，8 位图调色板逐字节照抄原版

**编辑能力**（真机验证过 14 项）：

国家 tag、人物、决议、剧本、科技开关、精神、政治、支持率、宣战、师团模板、开局部队、舰队、空军、已完成国策、州资源。

**一键建世界** `world_create`（**已能进游戏**）：

地图 → descriptor → 重载 → 建 tag → 建州（带 owner）→ 国家历史 → 师团模板 → 开局部队 →
本地化 → 剧本 → **目录占位** → **补给图**，12 步全 ok，151 个文件。

真机：`Loaded 208 provinces.` → `Resetting game` → `Executing History ×2`，常驻 100 秒不崩。

---

## 二、唯一的实质缺口

> **2026-11-02 夜：已解决。** 结论见第四节 P0-1。一句话版本：
> `replace_path="common/national_focus"` 之后本 mod 里没有一棵 `default = yes`
> 的国策树 → 开局给无树国家分配默认树时空指针。补一棵就进得去了。
> 旧的「replace 必须成组」判断方向错了，别再往加 replace 条数上使劲。

### 能加载，不能玩

`world_create` 的产物能进主菜单、能选国家、能看到地图和省份划分正确，但点「开始」进游戏时崩溃。

崩溃点：`game.log` 停在 `[[ Launching SINGLEPLAYER-game ]]` 之后，异常地址固定 `0x00007FF6BEED4300`。
`error.log` 里没有任何指向生成物的错误。

### 已经排除的

`oob` 空串、`popularities` 项数、`research_slots`、本地化 key、`supply_area` 州号。

### 已经定位的机理

**`replace_path` 必须成组**。

HOI4 的 `replace_path` 是整体屏蔽：声明 `common/ideas` 之后，这个目录只从本 mod 读。
如果只替换 `common/ideas` 而不替换引用它的 `common/on_actions`、`achievements.txt`、
`continuous_focus`、`special_projects`、`factions`，这些文件里的 `add_timed_idea`
就全线指向不存在的精神。

实测规模：

| replace_path 条数 | 结果 |
|---|---|
| 13（history + map + ai_* + bookmarks） | 进游戏崩溃 |
| 20（补 7 条） | 3879 条 `Invalid idea` |
| 50（补到 ES 量级） | `Loaded 208 provinces` 正常，进游戏仍崩 |

### 参照物：East Showdown

创意工坊 2948642461，能玩的局部战役 mod。

- **65 条 replace_path**
- `common/` 下 **74 个子目录全部自己写**
- 1447 个州 / 82 个国家 / 491 个 OOB / 完整国策树 / 完整事件 / 完整科技
- 体量 15 MB

这就是「能玩的新世界」的真实成本。

---

## 三、方向判断

### 三条候选路线

**A. 攻下「生成可加载的完整 mod」**

把 `world_create` 从「骨架」做到「能进游戏」。需要为 ES 那 65 条 replace_path 覆盖的每一类生成最小合法占位。

**B. 打磨现有编辑能力**

技术债（撤销备份 33 MB）、交互细节（批量进度、忽略表界面）、单文件接管。

**C. 扩展新编辑面**

BACKLOG 里的项基本已做完，剩下的是「曲线平滑省界」这类不适合编辑场景的东西。

### 结论：走 A

**理由**：

1. **B 和 C 的空间已经很小**。199 个路由、17 项诊断，编辑能力接近饱和。BACKLOG 里 32 项，绝大多数已打勾，未完成的三项里两项是显示问题。
2. **A 是产品从「地图工具」变成「世界工具」的分界线**。现在能生成地图，但用户拿到地图后仍然要自己写几百个文件。跨过这条线，产品定位就变了。
3. **A 的工作量是可估的，不是无底洞**。74 个目录的占位 ≠ 74 个完整内容，占位只需要「语法合法、不引用空目录」。

### A 的风险与前提

**前提**：先找到进游戏崩溃的**确切原因**。现在只知道「replace 引用链」这个机理，不知道具体是哪一条引用导致引擎访问违例。没有这个定位，后面生成占位是盲目的。

**风险**：即使占位齐全，游戏进去后可能是「一个空世界」——没有国策、没有事件、没有科技树、AI 不会行动。那不是「能玩」，只是「能加载」。

**所以 A 要分两步**：

- **A1**：能做到「进游戏不崩」，看到地图上有国家、有省份、有部队
- **A2**：能做到「有基本玩法」——至少要有一棵能走的国策树和一个能触发的事件

A1 是这一期的目标，A2 是下一期。

---

## 四、任务清单

### P0 · 定位崩溃（阻塞全部，必须先做）—— ✅ 已完成

#### 任务 0-1 · 二分定位进游戏崩溃的确切原因 —— ✅ 完成（2026-11-02 夜）

**一句话结论**

> 崩溃是因为 `common/national_focus` 被 `replace_path` 整体接管后，本 mod 里
> 没有任何 **`default = yes`** 的国策树。开局时引擎要给「history/countries 里
> 没写 `load_focus_tree` 的国家」分配默认树，默认树不存在 → 空指针访问违例。

**证据**

```
# 崩溃形态（zi 026 差异只有 national_focus）
game.log   [01:04:24] Loaded 208 provinces.      ← 之后 1–2 秒进程消失
error.log  无任何相关记录
crash      EXCEPTION_ACCESS_VIOLATION，堆栈 12 帧全是 PHYSFS_swapULE64
```

对照实验（同一套 map + history，只改 national_focus 里的内容）：

| national_focus 里的东西 | 结果 |
|---|---|
| `# placeholder`（注释） | DIED 22 s |
| 一棵只匹配本 tag 的树（无 default） | DIED 21 s |
| 一棵带 `default = yes` 的树 | **ALIVE，历史执行** |
| 原版 `generic.txt` | ALIVE |
| 原版整套 81 个文件 | ALIVE |

剥离到只剩 `map/` 或只剩 `history/*` 时的崩溃是**假象**：拿原版地图配 5 个州，
或者拿原版 13264 个州配 208 省的地图，本来就不成立。干净基准只能是
「自己的地图 + 自己的 history」，这个组合实测 ALIVE。

**原结论作废的部分**

第二节那张「replace 条数 → 结果」的表把相关当成了因果。实测
`common/ideas`、`common/characters`、`common/on_actions`、`common/scripted_*`、
`common/ai_*` 全部 replace 成空文件**不崩**（只刷日志）。只有 `national_focus` 崩。

**成本修正**

真机验证原来估 150 秒/轮（含人工点开始）。实际崩溃发生在 `Loaded N provinces`
之后 1–2 秒、**不需要任何人点**，所以一轮 45–55 秒、全自动。46 轮约 40 分钟。

**工具**

| 脚本 | 作用 |
|---|---|
| `qa/_hoi4_probe.py` | 装候选 mod（白/黑名单目录）+ 起游戏 + 判定 ALIVE/DIED |
| `qa/_bisect_probe.py` | 按下标跑一批目录组合 |
| `qa/_bisect_common.py` | 干净基准上逐个加 common 目录 |

#### 任务 0-2 · 给诊断器加「能不能进游戏」的静态推断 —— ✅ 完成

新检查项 `_diag_replace_stub`（检查函数 16 → 17），三件事：

1. 声明了 replace_path 但目录是空的 → warning（`national_focus` / `history/states` 升 error）
2. `common/national_focus` 里没有 `default = yes` → **error**，复刻本次崩溃
3. `common/ai_strategy` 里写了裸 `ai_strategy = { }` → warning

验收：对 `tmp/_world5`（旧产物）报 1 条 `replace.focus_no_default`；
对 `tmp/_world6`（新产物）0 条；3 个真实 mod 上 error 级 0 条。


---

### P1 · 让新世界能进游戏 —— ✅ 已完成（A1 达成）

#### 任务 1-1 · 生成全套 replace_path —— ✅ 完成

`REPLACE_DIRS` 落在 `qa/world_stubs.py`，共 **50 条**。ES 的 65 条去重后是 63 条，
我们少的 14 条全是**故意不 replace** 的（下表；`common/country_tags` ES 也没 replace，一并列在这里）：

| 不 replace | 原因 |
|---|---|
| `music` / `music/hoi2` / `music/hoi3` | 纯资源，换空 = 没音乐 |
| `gfx/flags` / `flags/medium` / `flags/small` | 纯资源，换空 = 国旗空白 |
| `portraits` / `gfx/loadingscreens` | 纯资源 |
| `gfx/interface/equipmentdesigner/graphic_db` | 装备外观，换空 = 图标全没 |
| `interface/countrytechtreeview.gui` | 换空 = 科技树界面崩 |
| `common/units` / `common/units/equipment` / `common/technologies` | 被引用的一端：师团模板、`set_technology` 全靠它 |
| `common/country_tags` | 换空让原版 383 个 tag 全失效，error.log 九成是 `Unknown trigger-type` |
| `common/combat_tactics.txt` | 不按 id 引用，换空只会把战斗搞坏，没有收益 |

另加 ES 漏写的 `common/operation_tokens`。50 条这份清单是**实测能进游戏**的那份，
别再加。

#### 任务 1-2 · 为每个被 replace 的目录生成最小合法占位 —— ✅ 完成

`qa/world_stubs.py`：`write_all(mod_dir, tag)` 写 50 个文件，`check(mod_dir)` 静态复查。
关键一条：`focus_tree_stub(tag)` 生成的树必须带 `default = yes`，这是本次崩溃的解。

踩过的三个反例都写进代码注释了：空注释国策树、无 default 的树、裸 `ai_strategy = { }`。

#### 任务 1-3 · 把「能进游戏」接进 `world_create` —— ✅ 完成

`steps` 从 10 步变 12 步，新增「目录占位」「补给图」，全部 `ok: true`。

顺带修的真 bug：补给区一直把**省号**写进 `states = { }`（5 个州的地图写出 1..207，
其中 202 个不存在），`map/supply_nodes.txt` 一直是 0 字节。新增
`mapgen_write.write_supply_graph(map_dir, states)`，建完州之后按真实州号重写。

**A1 验收（真机）**

```
装 151 个文件 / 50 条 replace_path
Loaded 208 provinces. → Resetting game → Executing History ×2
进程常驻 100 秒 / 2.4 GB / 无新崩溃目录
```

### P2 · 配套能力

#### 任务 2-1 · 单文件接管

**做什么**

`replace.dangling_refs` 里有一类引用方是 `common/achievements.txt` 这种根下单个文件，
现在只能「撤销 replace」或「忽略」，不能接管。加一个「只接管这一个文件」的动作。

**技术方案**：`ensure_file_writable(root, sub, basename)` 已有单文件复制能力，
返回值是 `(目标路径, 说明)`，接上去即可。

**验收**

- 对单个文件的 finding 出现「接管这个文件」按钮
- 点完只多一个文件，不写 replace_path
- 六组验收脚本 23 项仍全 PASS

#### 任务 2-2 · 忽略表的查看与清空

**做什么**

忽略记录存在 `work/cache/replace_ignore.json`，现在只能从 finding 上点，看不到自己按过什么，也不能清空。

**验收**

- 诊断面板有「已忽略（N）」入口
- 能列出每条：目录 + 引用方 + 时间
- 能单条恢复、全部清空

#### 任务 2-3 · 批量接管的进度显示

**做什么**

一次接管几十个目录时前端只有一个「正在接管…」，不知道到哪了。

**技术方案**：两条路，选简单的：

- 后端 `replace_fix_all` 改成流式响应（每处理完一个目录回一行）
- 或者前端按 `done` 数组逐条渲染，后端一次返回全部（现在就是这样）

先确认现在的延迟到底有多大（冷盘扫描 24.8 秒），如果主要耗时在扫描而非接管，那进度条意义不大，改成「先扫描后执行」两阶段提示更实际。

**验收**

- 用户能看到「正在处理 3/28」
- 冷盘首次点击的等待时间有明确提示，不是无限转圈

---

### P3 · 技术债

#### 任务 3-1 · 撤销备份改成按省增量

**现状**：一次地图编辑的 undo 存整个包围盒，散布型改动单次可达 33 MB。

**目标**：只存被改动的像素坐标与原值。

**注意**：这个改过一版（按密度选择点级备份，1404 字节），但可能没覆盖所有编辑路径。先查现在还有哪些路径走包围盒。

**验收**

- 连续改 20 次地图，`mapundo/` 总体积 < 10 MB
- 撤销 20 次后地图与初始状态逐像素一致

#### 任务 3-2 · 事件树循环触发的层级

**现状**：A→B→A 会让同一批事件挤在同一层，图形难看。

**验收**

- 循环依赖的节点能横向错开显示
- 不改变事件本身的逻辑

---

## 五、明确不做的

写清楚避免返工：

| 事项 | 为什么不做 |
|---|---|
| 生成完整国策树/事件/科技树 | 这是 A2 的范围，需要先有 A1。且内容要按具体 mod 定制，通用生成器做不出有意义的东西 |
| 曲线平滑省界 | 会偏离真实省界，编辑场景不能用，只适合导出预览图 |
| 支持多张地图 | HOI4 引擎只有一张地图，不同剧本不能读不同地图 |
| 移植到别的游戏 | 不是当前目标 |
| 联网/云同步 | 单机工具，不需要 |

---

## 六、执行顺序与依赖

```
0-1（定位崩溃）        ✅ 2026-11-02
  ↓
0-2（诊断固化）        ✅ 2026-11-02
  ↓
1-1（全套 replace_path）✅ 50 条
1-2（目录占位）        ✅ qa/world_stubs.py
  ↓
1-3（接进 world_create）✅ 12 步全 ok
  ↓ A1 达成（能进游戏、历史正常执行）
2-1 / 2-2 / 2-3（配套）   ← 下一轮
3-1 / 3-2（技术债）       ← 随时可做
A2（一棵能走的国策树 + 能触发的事件）← 下一期目标
```

**每一期的交付标准**：

- 改完跑 `python qa/regress_all.py`，必须 180/180
- 改完跑 `python qa/check_no_chat.py`，必须无残留
- 涉及真机的，附 `game.log` 里的 `Loaded N provinces` 那一行
- 涉及「能不能进游戏」的，先跑 `python qa/_check_world_stubs.py`（2 秒），
  再上真机（`qa/_hoi4_probe.py`，一轮约 50 秒）
- 文档更新 `DEV_LESSONS.md` / `SESSION_STATE.md` / `PROJECT_LOG.md`

---

## 七、参考数据

### 本机环境

```
游戏本体      E:\SteamLibrary\steamapps\common\Hearts of Iron IV
游戏用户目录  C:\Users\33206\Documents\Paradox Interactive\Hearts of Iron IV
日志          logs/game.log（加载进度）、logs/error.log（错误）
崩溃          crashes/<时间戳>/exception.txt
```

**注意**：地图生成需要 numpy。本机默认 `python` 是 3.13 轻量版没装 numpy，
用 `C:\Users\33206\AppData\Local\Programs\Python\Python312\python.exe`。

### 关键文件

| 文件 | 作用 |
|---|---|
| `work/focus_editor.py` | 主服务，18415 行 |
| `work/focus_editor_index.html` | 前端，12501 行 |
| `work/qa/mapgen*.py` | 地图生成器，6 模块 |
| `work/qa/map_diag.py` | map 目录 12 项体检 |
| `work/qa/regress_all.py` | 15 个真实 mod 的接口回归 |
| `work/qa/world_stubs.py` | 50 个被 replace 目录的占位 + 静态复查 |
| `work/qa/_hoi4_probe.py` | 真机探针：装 mod、起游戏、判 ALIVE/DIED（一轮约 50 秒） |
| `work/qa/_bisect_probe.py` / `_bisect_common.py` | 真机二分的跑批器 |
| `work/qa/_check_world_stubs.py` | 占位自检 7 项，2 秒，不开游戏 |
| `work/HANDOVER_MAPGEN.md` | 地图生成的完整交接 |
| `work/HANDOVER_WORLD.md` | 本轮交接：崩溃根因、占位模块、真机复验流程 |
| `work/HANDOVER_REPLACE_FIX.md` | replace 断链修复的交接 |
| `work/DEV_LESSONS.md` | 踩坑记录 |
| `xuerong-editor/` | 公开镜像，自足可跑 |

### 参照 mod

```
East Showdown     E:\SteamLibrary\steamapps\workshop\content\394360\2948642461
                  65 条 replace_path，74 个 common 子目录全自建，15 MB

MUVLUV CN         ...\394360\2800380626
MUVLUV CNsub      ...\394360\3004109283
```
