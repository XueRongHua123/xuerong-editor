# 交接：新世界能进游戏了（v1.23.35）

版本：v1.23.35（未发布）
日期：2026-11-02
对象：接下来维护雪绒编辑器（`work/` 与 `xuerong-editor/`）的人
前置：`work/ROADMAP_2026H1.md` 是**方向与任务清单**（P0/P1 已结项），本文是**交接单**
（结论是什么、凭什么、怎么复验、哪里还没做）。两份一起看。

---

## 一、三十秒版本

`world_create` 的产物以前「能进主菜单、点开始就崩」，现在**能进游戏、历史正常执行**。

真凶不是「replace_path 加得不够多」，而是：

> `replace_path="common/national_focus"` 之后，本 mod 里没有一棵 **`default = yes`**
> 的国策树 → 开局给「`history/countries` 里没写 `load_focus_tree` 的国家」分配默认树时
> 空指针 → `Loaded N provinces` 之后 1–2 秒访问违例，**error.log 一条相关记录都没有**。

一句话结论：**占位不是「写点合法语法」就够，有的目录有硬性语义要求。
national_focus 的 `default = yes` 就是那条要求；补上一棵带它的树，50 条 replace 的世界直接能进。**

---

## 二、现在能做什么 / 不能做什么

| 场景 | 能不能 | 说明 |
|---|---|---|
| 一键建世界并**进游戏** | 能 | `world_create` 12 步全 ok，151 个文件，50 条 replace_path |
| 地图、省界、州、归属国、开局部队在游戏里正确 | 能 | `Loaded 208 provinces` + `Executing History ×2`，进程常驻 |
| 有国策树 | 只有一根节点 | 占位树（`zz_editor_tree`），**不是能玩的树**，A2 才做 |
| 有事件 | 不能 | `events/` 是空占位 |
| AI 会行动 | 不能 | `common/ai_*` 全是空占位，AI 退回默认/发呆 |
| 师团有番号 | 不能 | `common/units/names_divisions` 是空占位，`name_order` 取不到名字（不崩） |
| 精神 / 决议 / 人物 / 科技树 | 没有 | 全空；科技仍在（原版 `common/technologies` 故意没 replace） |
| 用别的 tag / 别的省份数量 | 能 | 全部由参数驱动：`tag` / `n_provinces` / `per_state` |
| 只想要地图、不建世界 | 能 | `map_generate(scaffold=False)`，此时不写 50 条 replace（也没有假补给区了） |

---

## 三、崩溃根因与证据

### 1. 崩溃形态

```
game.log   [01:04:24][no_game_date]: Loaded 208 provinces.
           ← 之后 1–2 秒进程消失，没有 Resetting game
error.log  没有任何指向生成物的记录
crashes/    EXCEPTION_ACCESS_VIOLATION
            堆栈 12 帧全是 PHYSFS_swapULE64（符号解析失败，看不出东西）
```

异常地址每次不同（`0x7FF6BEED4300` / `0x7FF766BEFD0D` …），**不要拿地址当线索**。

### 2. 对照实验（同一套 map + history，只改 national_focus 里的内容）

| national_focus 里的东西 | 结果 |
|---|---|
| `# placeholder`（一句话注释） | DIED 22 s |
| 一棵只匹配本 tag 的树（**无** `default = yes`） | DIED 21 s |
| 一棵带 `default = yes` 的树 | **ALIVE**，`Resetting game` + 历史执行 |
| 原版 `generic.txt`（它就是那棵 default 树） | ALIVE |
| 原版整套 81 个文件 | ALIVE |

### 3. 被推翻的旧结论

以前记的规律是「**replace 一个目录，必须同时 replace 所有引用它的目录**」，
并据此把 replace_path 从 13 条加到 50 条。实测证明这条**不是**崩溃原因：

- `common/ideas`、`characters`、`country_leader`、`on_actions`、`scripted_*`、
  `ai_*`、`decisions`、`events` 全部 replace 成空文件 → **不崩**（只刷日志）
- 只有 `national_focus` 崩

所以别再用「加更多 replace_path」去试。**方向错了。**

### 4. 两个「假象」要先排除

单独剥离目录时容易得出错误结论，因为混进了原版数据：

| 剥离方式 | 为什么是假象 |
|---|---|
| 只留 `map/`（不写 history） | 原版 13264 个州配 208 省的地图，本来就不成立 |
| 只留 `history/*`（不写 map） | 5 个州配原版 13413 省的地图，同样不成立 |

干净基准只有一种：**自己的地图 + 自己的 history**。这个组合实测 ALIVE，
崩溃才第一次变得可以归因。判据脚本：`qa/_bisect_common.py` 就是干这个的。

---

## 四、代码改动点

行号会漂移，**以函数名 / 文件名为准**。

### 1. 新增 `work/qa/world_stubs.py`（235 行）

| 符号 | 作用 |
|---|---|
| `REPLACE_DIRS` | 50 条要 replace 的目录，带逐条注释（为什么这条要 replace） |
| `BLOCK_STUBS` | 需要写「块名 = { }」的目录 → 块名映射 |
| `STUB_NAME` | `zz_editor_stub.txt`，占位文件名统一 |
| `focus_tree_stub(tag, tree_id)` | 生成带 `default = yes` 的默认国策树，**这是崩溃的解** |
| `write_all(mod_dir, tag, dirs=None)` | 写 50 个占位文件，返回相对路径列表 |
| `check(mod_dir, dirs=None)` | 静态复查，返回 `[{"dir","level","msg"}]`，`[]` 表示齐了 |

`check()` 只报两件事：目录空（`national_focus` / `history/states` 升 error，其余 warning）、
`national_focus` 缺 `default = yes`（error）、`ai_strategy` 写裸 `ai_strategy = { }`（warning）。

### 2. `work/qa/mapgen_scaffold.py`

| 位置 | 改动 |
|---|---|
| 顶部 | `REPLACE_DIRS` 不再本地定义，改为 `world_stubs.REPLACE_DIRS`（13 → 50 条） |
| `write_states()` | 新增 `with_map=True`，返回 `(州数, [(州号, [省号...])])`；补给图要用真实州号 |
| `build()` | 末尾追加两步：`world_stubs.write_all()` 写占位、`write_supply_graph()` 重写补给图；返回体多一个 `problems` 键，有 error 时 `ok=False` |
| `write_ai_stubs()` | 标记为「已被 world_stubs 取代」，保留只为兼容老脚本 |

### 3. `work/qa/mapgen_write.py`

新增 `write_supply_graph(map_dir, states, per_area=60)`：

- `supplyareas/*.txt` 的 `states = { }` 写**真实州号**（旧代码把省号抄进去，
  5 个州的地图写出 1..207，其中 202 个不存在）
- 重写 `map/supply_nodes.txt`（旧代码里它是 **0 字节**），格式照原版：
  每行 `州号 省号`，一个州至少一个节点

`write_supply_areas()` 保留但降级为「只给纯地图预览用」，并在 docstring 里写明会被覆盖。

### 4. `work/qa/mapgen.py`

走 `scaffold=True` 时不再写「省号当州号」的假补给区，交给 scaffold 建完州后重写。

### 5. `work/focus_editor.py`

| 位置 | 改动 |
|---|---|
| `world_create()` | `steps` 从 10 步 → **12 步**：新增「目录占位」「补给图」；建州循环里记 `state_map`（州号↔省号） |
| `_diag_replace_stub()`（追加在 `_diag_replace_refs()` 之后） | 新增检查，检查函数 16 → 17 |
| `diagnose()` 的检查列表 | 注册 `_diag_replace_stub` |

新检查的 finding code：

| code | 级别 | 含义 |
|---|---|---|
| `replace.empty_dir` | error（`national_focus` / `history/states`）/ warning（其余） | 声明了 replace 但这层目录是空的 |
| `replace.no_txt` | warning | 目录里有文件但没有 `.txt`，引擎读不到数据 |
| `replace.focus_no_default` | **error** | 复刻本轮崩溃：没有 `default = yes` 的国策树 |
| `replace.ai_strategy_bare` | warning | 裸 `ai_strategy = { }`，引擎会把块名当策略名 |

### 6. 新增真机工具（`work/qa/`）

| 脚本 | 作用 | 一轮耗时 |
|---|---|---|
| `_hoi4_probe.py` | 装候选 mod（可白/黑名单目录）+ 起游戏 + 判定 ALIVE/DIED | 45–55 s |
| `_bisect_probe.py` | 按下标跑一批目录组合（`python qa/_bisect_probe.py 6-16 17-27`） | 每组 50 s |
| `_bisect_common.py` | 干净基准上逐个加 common 目录（`python qa/_bisect_common.py 6-49 --drop 6`） | 每组 50 s |
| `_hoi4_launch.ps1` | 起游戏 + 定时截图（人工看图用） | — |
| `_check_world_stubs.py` | 占位自检 7 项，**不开游戏** | 2 s |

`_hoi4_probe.py` 会把候选装到 `Documents/Paradox Interactive/Hearts of Iron IV/mod/zz_probe`，
并把 `dlc_load.json` 改成只启它。**跑完记得恢复**：`python qa/_hoi4_probe.py --restore`。

---

## 五、怎么复验

### 环境

- 地图生成需要 **numpy**：用 `C:\Users\33206\AppData\Local\Programs\Python\Python312\python.exe`，
  默认的 `python` 是 3.13 轻量版，没有 numpy，`world_create` 第一步就返回「地图生成器不可用」
- 游戏 `E:\SteamLibrary\steamapps\common\Hearts of Iron IV`，用户目录
  `C:\Users\33206\Documents\Paradox Interactive\Hearts of Iron IV`
- 跑真机前**先确认没有 hoi4.exe 在跑**（探针会自己等/杀，但别手动抢）

### 三条不开游戏的命令（每次改动都跑）

```bash
cd "D:/大肥鱼工作区/HOI4 MUVLUVsub mod 制作/work"

python qa/_check_world_stubs.py     # 期望：7 过 / 0 挂（2 秒）
python qa/regress_all.py            # 期望：15 个真实 mod 全 12/12，总计 180/180
python qa/check_no_chat.py          # 期望：无残留
```

### 一次完整的世界生成（需要 numpy）

```bash
"C:/Users/33206/AppData/Local/Programs/Python/Python312/python.exe" - <<'PY'
import sys
sys.path.insert(0, "."); sys.path.insert(0, "qa")
import focus_editor as E
r = E.world_create(r"D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work\tmp\_world_new",
                   width=1024, height=512, n_provinces=40, per_state=8,
                   tag="ZZV", country_name="新世界", mod_name="新世界")
print(r["ok"], r["provinces"], r["states"])
for s in r["steps"]:
    print(("  OK  " if s["ok"] else "  FAIL"), s["step"], s["msg"])
PY
```

期望 12 步全 OK，末两步是「目录占位 50 个目录」「补给图 1 个补给区 / 5 个补给节点」。
产物体检：

```bash
cd tmp/_world_new
grep -c replace_path descriptor.mod                  # 50
grep -c "default = yes" common/national_focus/zz_editor_stub.txt   # 1
cat map/supplyareas/1-SupplyArea.txt                 # states 里是 1..5（州号，不是省号）
cat map/supply_nodes.txt                             # 5 行「州号 省号」
```

### 真机验收（50 秒一轮）

```bash
cd "D:/大肥鱼工作区/HOI4 MUVLUVsub mod 制作/work"
python qa/_hoi4_probe.py --src "tmp/_world_new" --tag accept --timeout 75
```

期望输出：

```
结果: ALIVE  75.0s
  log| [..] Loaded 208 provinces.
  log| [..] Resetting game
  log| [..] Executing History from -1.1.1.1 to  2.1.1.1
  log| [..] Executing History from 2.1.1.1 to  1936.1.1.12
```

`DIED` 且日志停在 `Loaded N provinces` → 先看是不是国策树又缺 `default = yes`
（跑 `_check_world_stubs.py` 或直接 `world_stubs.check(产物目录)`）。

跑完别忘了 `python qa/_hoi4_probe.py --restore` 把用户原配置还回去。

---

## 六、踩过的坑

1. **mod 显示名重复 → 引擎把两个都丢掉**。两个 `.mod` 里 `name=` 相同时，启动后
   **两个都不加载**，游戏按原版跑（`Loaded 13414 provinces` 就是原版）。现象极迷惑：
   文件都在、`dlc_load.json` 也对。排查：`logs/setup.log` 里有没有你 mod 的文件名。
   `_hoi4_probe.py` 现在强制给每个候选一个唯一显示名。
2. **`path=` 要写在 `supported_version` 后面**。追加到 replace_path 那一片之后，
   整条 mod 被静默忽略（同样表现为「按原版加载」）。
3. **`dlc_load.json` 会在游戏退出时被写回**。手动改成只启测试 mod 后，退出时游戏会写回
   它本次实际加载的列表。恢复用户配置要等进程真退了再 `cp`（本轮被覆盖过一次）。
4. **空目录不一定崩**。`muvluvCN` 就把 `common/ai_equipment`、`common/bop` 有意 replace
   成空目录，游戏照进。所以 `replace.empty_dir` 默认只报 warning。
5. **判「空」要数所有文件，不只 `.txt`**。`gfx/loadingscreens` 里是 `.dds`，
   只数 `.txt` 会误报。
6. **真机验证比原估的便宜**：崩溃不需要点「开始」，一轮 50 秒全自动。
   原估的 150 秒/轮是含人工点击的。
7. **截图脚本要存成 UTF-8 带 BOM**。`_hoi4_launch.ps1` 若存成无 BOM，PowerShell 5.1
   按 ANSI 读，中文路径会变乱码，截图落在乱码目录里找不到。
8. **`exception.txt` 堆栈没用**。全是 `PHYSFS_swapULE64` + 一堆
   `(function-name not available)`，符号没解析，别在上面花时间。

---

## 七、没做的 / 下一步

| # | 事项 | 说明 |
|---|---|---|
| 1 | **A2：能玩的国策树** | 现在占位树只有一根节点（`zz_editor_tree_root`，加 5 政治点）。要做到「能走」，得给生成器加一棵几十节点的树，并且 `history/countries` 里 `load_focus_tree` 指过去 |
| 2 | **A2：能触发的事件** | `events/` 空占位。最小可用：一条 `on_startup` 触发的事件 + 本地化 |
| 3 | 师团番号 | `common/units/names_divisions` 空占位 + OOB 用 `name_order = 1` → 不崩但名字空。要么给番号组并在模板写 `division_names_group`，要么改 OOB 用固定名 |
| 4 | AI | `common/ai_*` 全空，AI 不会行动。最低限度得给 `ai_strategy` 一条「防守本土」的合法策略 |
| 5 | 本地化 | `STATE_n` / 州名 / 国名只有英文占位，中文全靠 `localisation/` 里那张表，UI 生成入口还没做 |
| 6 | 地图生成 UI | 仍然只能走 `/api/world_create` 或脚本，前端没有入口 |
| 7 | P2 三项 | 单文件接管、忽略表界面、批量接管进度（见 ROADMAP 第四节） |
| 8 | P3 两项 | 撤销备份按省增量、事件树循环层级（技术债） |
| 9 | 发布 | v1.23.35 未写 release notes、未打包、未推 GitHub、`xuerong-editor/` 镜像未同步 |

---

## 八、文件地图

| 文件 | 说明 |
|---|---|
| `work/qa/world_stubs.py` | **新增**，50 目录占位 + 静态复查 |
| `work/qa/mapgen_scaffold.py` | REPLACE_DIRS 迁到 world_stubs；build 末尾写占位与补给图 |
| `work/qa/mapgen_write.py` | 新增 `write_supply_graph()` |
| `work/qa/mapgen.py` | 走 scaffold 时不再写假补给区 |
| `work/focus_editor.py` | `world_create` 12 步；新增 replace 占位检查；18415 行 |
| `work/qa/_hoi4_probe.py` | **新增**，真机探针（装 mod + 起游戏 + 判定） |
| `work/qa/_bisect_probe.py` / `_bisect_common.py` | **新增**，真机二分跑批 |
| `work/qa/_check_world_stubs.py` | **新增**，占位自检 7 项 |
| `work/qa/_hoi4_launch.ps1` | **新增**，起游戏 + 定时截图 |
| `work/tmp/_world6` | 本轮验收产物（151 文件 / 50 条 replace），可直接 `--src` 复跑 |
| `work/_archive/deployed_20261102/` | 归档的旧测试 mod（`zz_mapval`，全替换但会崩的那份） |
| `work/ROADMAP_2026H1.md` | 方向与任务清单，P0/P1 已结项 |
| `work/SESSION_STATE.md` | 顶部「新世界能进游戏了」一节 |
| `work/DEV_LESSONS.md` | 末尾 2026-11-02 夜那节，8 条坑 |
| `work/PROJECT_LOG.md` | 末尾 v1.23.35 那节 |

**游戏侧现场状态**

```
Documents/Paradox Interactive/Hearts of Iron IV/mod/xuerong_world      ← 新世界，显示名「雪绒新世界」
Documents/Paradox Interactive/Hearts of Iron IV/mod/xuerong_world.mod
dlc_load.json                                                          ← 已恢复成 MUVLUV 三件套原配置
```

想在游戏里看这个新世界：启动器里勾「雪绒新世界」即可（它自带 50 条 replace_path，
不需要和 MUVLUV 一起开，一起开反而会被上层的 replace 盖住）。

---

## 九、接手第一件事

1. 跑第五节的三条命令，确认 7/7、180/180、无残留都对得上
2. `python qa/_hoi4_probe.py --src "tmp/_world6" --tag sanity` 跑一次真机，
   确认 `ALIVE` + `Executing History ×2`（这是本轮唯一的硬证据，别只信文档）
3. 决定 A2 先做哪一半：**国策树**还是**事件**。建议先国策树 ——
   它是「能玩」的骨架，事件靠 `on_startup` 挂上去更快，但没树的话玩家开局无事可做
4. 动 `REPLACE_DIRS` 之前先读 `world_stubs.py` 开头：那 14 条「故意不 replace」的目录
   每一条都有实测理由，加回去会重新打开已经关掉的坑
