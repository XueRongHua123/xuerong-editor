## 雪绒的钢铁雄心编辑器 v1.23.35

**一键建世界现在能进游戏了。** 但「能进」不等于「能玩」，边界见第四节。

---

### 一、崩溃的真凶

前几版一直卡在这一步：`world_create` 的产物能进主菜单、能选国家、能看到地图和省份划分正确，
点「开始」进游戏时进程消失，`Loaded N provinces` 之后 1–2 秒访问违例，
**error.log 里一条相关记录都没有**。

真凶是：

> `replace_path="common/national_focus"` 之后，本 mod 里没有一棵 **`default = yes`**
> 的国策树。开局给「`history/countries` 里没写 `load_focus_tree` 的国家」分配默认树时，
> 引擎拿不到那棵树，空指针。

对照实验（同一套 map + history，只改 `national_focus` 里的内容）：

| national_focus 内容 | 结果 |
|---|---|
| 一句话注释 | 崩 |
| 一棵只匹配本 tag 的树，**无** `default = yes` | 崩 |
| 一棵带 `default = yes` 的树 | **进游戏** |
| 原版 `generic.txt`（它就是那棵 default 树） | 进游戏 |
| 原版整套 81 个文件 | 进游戏 |

补上一棵带 `default = yes` 的占位树之后，50 条 replace_path 的世界直接能进：

```
Loaded 208 provinces.
Resetting game
Executing History from -1.1.1.1 to  2.1.1.1
Executing History from 2.1.1.1 to  1936.1.1.12
```

`Resetting game` 这一行是关键——以前崩在这里之前，从来没有过。

---

### 二、推翻一条旧结论

上一版及以前的文档里记着「replace 一个目录，必须同时 replace 所有引用它的目录，
否则引用链断裂」，并据此把 replace_path 从 13 条加到 50 条。

**这条不是崩溃原因。**

实测：`common/ideas`、`characters`、`country_leader`、`on_actions`、`scripted_*`、
`ai_*`、`decisions`、`events` 全部 replace 成空文件——**都不崩**，只刷日志。
只有 `national_focus` 崩。

刷日志和崩进程是两件事。之前把 `Invalid idea` 那几千条当成了崩溃信号，方向带偏了。

---

### 三、改了什么

**新增 `qa/world_stubs.py`（235 行）**

为 50 个被 replace 的目录各写一个最小合法占位，重点是 `focus_tree_stub(tag, tree_id)`
生成带 `default = yes` 的默认国策树。另带 `check()` 做静态复查，只报三件事：
目录空、`national_focus` 缺 `default = yes`、`ai_strategy` 写裸块。

**50 条 replace_path**

照 East Showdown 的 65 条裁掉 14 条，每条都有实测理由：

- `common/units` / `common/units/equipment` / `common/technologies`：被引用的一端，
  换空让师团模板和 `set_technology` 失效
- `music` / `music/hoi3` / `music/hoi2`：纯资源，换空后引擎报
  `Could not find music named maintheme`，停在地图加载前的 `4489 defines loaded`
- `gfx/flags` / `gfx/flags/medium` / `gfx/flags/small` / `gfx/loadingscreens` / `portraits`：
  纯资源，同理
- `gfx/interface/equipmentdesigner/graphic_db` / `interface/countrytechtreeview.gui` /
  `common/combat_tactics.txt`：单文件，用同名覆盖就够

**修补给区**

旧代码把**省号**写进 `supplyareas/*.txt` 的 `states = { }`，5 个州的地图写出 1..207，
其中 202 个不存在。新增 `write_supply_graph()` 用真实州号重写，同时重写
`map/supply_nodes.txt`（旧代码里它是 0 字节，格式是每行「州号 省号」）。

**`world_create` 从 10 步变成 12 步**

新增「目录占位」和「补给图」两步，建州循环里记下州号↔省号的映射供补给图使用。

**诊断第 17 项 `_diag_replace_stub`**

| code | 级别 | 含义 |
|---|---|---|
| `replace.empty_dir` | error（`national_focus` / `history/states`）/ warning（其余） | 声明了 replace 但这层目录是空的 |
| `replace.no_txt` | warning | 目录里有文件但没有 `.txt` |
| `replace.focus_no_default` | **error** | 复刻本轮崩溃：没有 `default = yes` 的国策树 |
| `replace.ai_strategy_bare` | warning | 裸 `ai_strategy = { }`，引擎会把块名当策略名 |

**新增四个真机工具**

`_hoi4_probe.py`（装 mod + 起游戏 + 判定 ALIVE/DIED，50 秒一轮）、
`_bisect_probe.py`（按目录组合批量跑）、`_bisect_common.py`（干净基准上逐个加目录）、
`_check_world_stubs.py`（占位自检 7 项，不开游戏，2 秒）。

---

### 四、能做什么 / 不能做什么

**能**：

- 一键建世界并进游戏，12 步全成功，151 个文件
- 地图、省界、州、归属国、开局部队在游戏里正确
- 参数驱动：`tag` / `n_provinces` / `per_state` 都能改
- 只想要地图、不建世界：`map_generate(scaffold=False)`，不写 50 条 replace

**不能**：

| 项 | 现状 |
|---|---|
| 国策树 | 只有一根节点，占位树，不是能玩的树 |
| 事件 | `events/` 空占位 |
| AI | `common/ai_*` 全空，AI 发呆 |
| 师团番号 | `name_order` 取不到名字（不崩，只是没名字） |
| 精神 / 决议 / 人物 / 科技树 | 全空；科技仍在（`common/technologies` 故意没 replace） |

**换句话说：能进游戏看世界，但没有可玩内容。** 下一步（A2）是给生成器加一棵几十节点的国策树，
再加一条 `on_startup` 触发的事件。

---

### 五、验证

```
python qa/_check_world_stubs.py            7 过 / 0 挂        2s
python qa/regress_all.py                  180/180            15 个真实 mod
python qa/check_no_chat.py                无残留
python qa/_hoi4_probe.py --src tmp/_world6 --tag sanity     ALIVE 90s
```

真机那一轮是本版唯一的硬证据。跑完记得 `python qa/_hoi4_probe.py --restore`
把 `dlc_load.json` 还回去——它会在游戏退出时被写回，不等进程真退了再 cp 会被覆盖。

---

### 六、踩过的坑

1. **mod 显示名重复 → 引擎把两个都丢掉**。两个 `.mod` 里 `name=` 相同时，启动后两个都不加载，游戏按原版跑（`Loaded 13414 provinces`）。排查看 `logs/setup.log` 里有没有你的文件名。
2. **`path=` 要写在 `supported_version` 后面**。追加到 replace_path 那一片之后，整条 mod 被静默忽略。
3. **空目录不一定崩**。`muvluvCN` 就把 `common/ai_equipment`、`common/bop` 有意 replace 成空目录，游戏照进。
4. **判「空」要数所有文件**。`gfx/loadingscreens` 里是 `.dds`，只数 `.txt` 会误报。
5. **`exception.txt` 堆栈没用**。全是 `PHYSFS_swapULE64` + `(function-name not available)`，符号没解析。异常地址每次不同，别拿它当线索。
6. **真机验证比原估的便宜**。崩溃不需要点「开始」，一轮 50 秒全自动，原估的 150 秒/轮是含人工点击的。
