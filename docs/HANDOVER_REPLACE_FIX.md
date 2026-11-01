# 交接：replace 断链的一键补齐（v1.23.34）

版本：v1.23.34（未发布）
日期：2026-11-02
对象：接下来维护雪绒编辑器（`work/` 与 `xuerong-editor/`）的人
前置：`work/HANDOVER_FIXUP.md` 是**任务书**（要做什么、为什么），本文是**交接单**
（做成了什么、怎么验、哪里还没做）。两份一起看。

---

## 一、三十秒版本

HOI4 的 `replace_path` 是整体屏蔽：声明 `common/ideas` 之后，这个目录只从本 mod 读，
原版的整个目录失效。但原版的 `achievements.txt`、`on_actions`、`special_projects` 里
还写着 `add_timed_idea = xxx`，于是加载期刷出海量 `Invalid idea`（40 省样本实测 3879 条）。

诊断器能报出「谁在引用被 replace 掉的东西」，但只给一句建议，没有可点的动作。本轮把它
接成可执行：**撤销 replace / 接管该目录 / 忽略**，单条能点，也能一键批量。

一句话结论：**误加的 replace 能一键撤；确实要整体替换时，能一键把引用方目录接管进来。
但内容本身修不了** —— 接管只是把原版内容拷过来，按省号/州号写的引用仍然要自己改。

---

## 二、现在能做什么

| 场景 | 能不能 | 怎么点 |
|---|---|---|
| 只是误加了 replace，其实要原版内容 | 能，推荐 | 诊断面板 → 该条 → [撤销 replace]；或顶部 [全部撤销 replace] |
| 换了地图，必须整体替换，需要一份可编辑副本 | 能 | 该条 → [接管该目录]；或顶部 [全部接管（N 个）] |
| 那些引用确认执行不到 | 能 | 该条 → [忽略]（本地记录，不写进 mod） |
| 引用方是 `common` / `events` 根下的单个文件 | **不能接管** | 只给 [撤销 replace] [忽略]，理由写在 note 里 |
| replace_path 是上一层 mod 声明的 | **不能撤** | 会明确报「要去那边改」 |
| `music` / `gfx/flags` / `portraits` / `gfx/loadingscreens` / `common/units*` / `common/technologies` / `common/country_tags` | **禁止接管** | 选项里不给按钮 |
| 接管之后的引用仍然是断的 | 本来如此 | 拷过来的是原版内容，该改还得改 |

---

## 三、代码改动点

行号会随改动漂移，**以函数名为准**。

### 1. 诊断侧（`work/focus_editor.py`）

| 位置 | 改动 |
|---|---|
| `_finding()`（4782 附近） | 新增可选参数 `fix`，返回值多一个 `"fix"` 键。16 个检查项都用默认空 dict，不影响既有调用 |
| `_diag_replace_refs()`（5390 附近） | 每条 `replace.dangling_refs` 填 `fix`；按忽略表过滤；不给接管的场合加 `note` |

`fix` 的结构：

```json
{
  "kind": "replace_dangling",
  "sub": "common/ideas",                 // 被 replace 掉的目录（取第一个）
  "subs": ["common/ideas"],              // 同一分组涉及的多个被 replace 目录
  "ref_dir": "common/on_actions",        // 引用方目录，已去掉 vanilla/ 前缀
  "group": "vanilla/common/on_actions",  // 原始分组键，忽略表用它做唯一键
  "note": "",                             // 为什么不能接管（空串=能）
  "options": ["drop_replace", "adopt_ref_dir", "ignore"]
}
```

### 2. 修复侧（新增，5500–5800 区间）

| 函数 | 作用 |
|---|---|
| `replace_drop(root, sub)` | 从链顶 mod 的 `descriptor.mod` 删掉一条 `replace_path`。行级精确匹配（容忍空格/引号写法、保留行尾注释），保留原 BOM 与 CRLF，写前 `snapshot()` 备份，落盘走 `_atomic_write()`，改完清缓存 |
| `replace_fix_all(root, kind, subs, force)` | 批量执行。`kind="drop_replace"` 或 `"adopt_ref_dir"`；`subs` 既是「被 replace 目录」也是「引用方目录」的过滤词；失败不中断，全部做完重扫一次给出 `left` |
| `replace_ignore(root, sub, ref_dir, subs, group, remove)` | 忽略表的增删。存 `work/cache/replace_ignore.json`，只影响提示，不改 mod |
| `_invalidate_layers()` | 同时清 `_LAYERS_CACHE` 与 `_DESC_CACHE`。少清一个，撤销完 `_replace_owner` 还拿旧列表判断 |
| `_replace_adopt_block(sub)` | 判断某目录能不能接管，返回空串或原因 |

批量动作的去重规则：多个引用目录指向同一个被 replace 目录时，`drop_replace` 只执行一次；
`adopt_ref_dir` 按引用方目录去重。

### 3. 顺手修的三处旧缺陷（`adopt_dir`，4086 附近）

| # | 原来 | 现在 |
|---|---|---|
| 1 | 源层解析从链顶开始，链顶就是自己 → `shutil.copyfile` 抛 `SameFileError` 被 `except: pass` 吞掉，报「拷贝 0 个文件」却照样写了 replace_path | 源层跳过 `top`；`_replace_owner` 返回 `top` 时视为没有上层来源 |
| 2 | 允许接管顶层桶目录 → `adopt_dir("common")` 会拷 2267 个原版文件并写 `replace_path="common"` | `sub` 不含 `/` 直接拒绝 |
| 3 | 只查全局 `ROOTS` → 脚本调用时全报「找不到可写的 mod 目录」 | 改用 `_top_mod(mod_root)` 解析链顶 |

### 4. 路由（`focus_editor.py` 17884 附近）

```
POST /api/replace_drop     {sub}
POST /api/replace_fix_all  {kind, subs, force}
POST /api/replace_ignore   {subs, ref_dir, group, remove}
```

### 5. 前端（`focus_editor_index.html`）

| 位置 | 改动 |
|---|---|
| 1120 附近 | 面板里新增 `<div id="diagFixBar">` 汇总条容器 |
| 12333 起整段 `// ---------- 诊断 ----------` | 重写：按钮渲染、`data-act` 事件委托、汇总条、操作结果消息 |

- 按钮只按后端 `fix.options` 渲染，前端只做名字翻译（`drop_replace→撤销 replace` 等），
  后端不给的选项前端不会凭空造
- 汇总条只在有 `replace.dangling_refs` 时出现；「全部接管（N 个）」的 N 只统计真能接管的
- 操作完自动重新请求 `/api/diagnose`，数量立刻下降
- **「全部接管」动手前有 `confirm()`**（会往 mod 里复制几百个文件）
- 操作结果消息在汇总条收起后仍然留在面板上（否则「撤销 3 条、还剩 0 个」会一闪而过）

---

## 四、怎么复验

### 环境

- Python 3.12，**地图生成需要 numpy**
- 本机游戏在 `E:\SteamLibrary\steamapps\common\Hearts of Iron IV`；`qa/regress_all.py` 里
  `GAME` 写死这个路径，换机器要改
- 别拿默认的 `python` 跑：本机默认解释器是轻量 3.13，没装 numpy，`world_create` 第一步
  就返回「地图生成器不可用」，后面的检查全成空转

### 两条命令

```bash
cd "D:/大肥鱼工作区/HOI4 MUVLUVsub mod 制作/work"

# 1) 六组验收：自建 40 省样本 → 加 replace_path → 修 → 检查 descriptor 完整性
python qa/_check_replace_fixup.py          # 期望：总计 23 项 PASS 23 / FAIL 0，总判定 PASS
                                           # 约 80 秒（含重建样本）；--keep 可保留样本手工看

# 2) 三条路由的 HTTP 冒烟：起真服务、打接口、关服务
python qa/_smoke_replace_api.py            # 期望：总计 7 项全 PASS，总判定 PASS
                                           # 约 60 秒（服务加载约 21 秒）
```

两个脚本都在 `work/tmp/` 里自建样本、跑完自己删，**不碰任何真实 mod**。

### 回归（每次改动都要跑）

```bash
python -c "import ast, io; ast.parse(io.open('focus_editor.py', encoding='utf-8').read()); print('语法 OK')"
python qa/regress_all.py        # 15 个真实 mod，期望 180/180
python qa/check_no_chat.py      # 文档里不能有对话指代，期望「无残留」
```

### 手工验 UI

启动后左侧「国家与州」→ 🩺 诊断。要看到按钮，mod 里得真有断链：往 `descriptor.mod`
加一条 `replace_path="common/ideas"` 再点「重新扫描」，应出现红色汇总条与 30 条左右
`replace.dangling_refs`。点完「全部撤销 replace」数量应归零，descriptor 里那条也没了。

---

## 五、踩过的坑（细节见 `work/DEV_LESSONS.md` 2026-11-02 那节）

1. **诊断的分组键是目录，不能直接当接管目标**。原版有文件直接在 `common/` 根下，
   分组键折出来是 `common`。照它接管 = 拷 2267 个文件 + `replace_path="common"`，
   等于把整个游戏数据换成残缺副本。实测就这么把样本 descriptor 写坏过一次。
2. **`adopt_dir` 的源层可能是它自己**（见三.3），失败被吞、结果看起来成功。
3. **改 descriptor 要清两级缓存**，只清 `_LAYERS_CACHE` 不够。
4. **忽略键要带原始分组键**。只存折过的 `ref_dir`，`vanilla/common/ai_strategy` 与
   本 mod 的 `common/ai_strategy` 会撞键，点一次按掉两条（实测 31 → 29）。
5. **扫描耗时受磁盘缓存影响很大**：同一份样本冷盘 24.8 s、热盘 2.2 s。
   `HANDOVER_FIXUP.md` 里「1.1 秒」是 50 条 replace 的热盘数字，别当固定开销。
   「全部撤销」前后各扫一次，冷启动第一次点按钮要等五六秒。

---

## 六、没做的 / 下一步

| # | 事项 | 说明 |
|---|---|---|
| 1 | 发布 v1.23.34 | `qa/release_notes_v123340.md` 尚未写；`packaging/make_release.py` 尚未跑；GitHub 未推 |
| 2 | 镜像提交 | `xuerong-editor/` 两个文件已同步到工作区，**未 commit 未 push** |
| 3 | 单文件接管 | 顶层桶下的单个引用文件（`common/achievements.txt` 这类）现在只能撤销或忽略。要修得加一个「只接管这一个文件」的动作，`ensure_file_writable` 已有单文件复制能力，可以接 |
| 4 | 忽略表入口 | 现在只能从 finding 上点「忽略」，没有「查看/清空忽略列表」的界面。忽略记录多了会忘了自己按过什么 |
| 5 | 批量接管的进度 | 一次接管几十个目录时前端只有一个「正在接管…」，没有目录级进度 |
| 6 | 真机验证 | 本轮只做了静态与 HTTP 验证，**没进游戏看 `error.log` 是否真的少报**。这是交接口子的第一件事 |

---

## 七、文件地图

| 文件 | 说明 |
|---|---|
| `work/focus_editor.py` | 主服务，18286 行。本轮 +389 |
| `work/focus_editor_index.html` | 前端，12501 行。本轮 +122 |
| `work/qa/_check_replace_fixup.py` | 新增，六组验收 |
| `work/qa/_smoke_replace_api.py` | 新增，三条路由冒烟 |
| `work/cache/replace_ignore.json` | 忽略表，运行时创建（`cache/` 在 `.gitignore` 里，不入库） |
| `work/HANDOVER_FIXUP.md` | 任务书 + 第十节完成记录 |
| `work/HANDOVER_SUBMOD.md` | 长期交接，第十一节记本轮 |
| `work/SESSION_STATE.md` | 当前版本 / 已完成 / 修不了什么 |
| `work/DEV_LESSONS.md` | 踩坑记录，末尾 2026-11-02 那节 |
| `work/PROJECT_LOG.md` | 按版本分段，顶部 2026-11-02 那节 |
| `xuerong-editor/` | 公开镜像（44 MB，自足可跑），已同步两个文件 |

**要跑起来**，`focus_editor.py` 还不够：它 `import editor_i18n`，还要 `mascot/`、`icons/`、
`qa/`（地图生成走 `qa/mapgen.py`）。整目录给 `xuerong-editor/` 最省事，别给 `work/`
（里面有 2.5 GB 的 mods 副本和几十份历史文档）。

---

## 八、接手第一件事

1. 跑一遍第四节的三条命令，确认 23/23、7/7、180/180 都对得上
2. 进游戏加载一次带 replace_path 的 mod，看 `logs/error.log` 里 `Invalid idea` 是否真的
   随撤销而减少（本轮唯一没做的验证）
3. 决定第 3 项「单文件接管」要不要做 —— 它是「接管」这条路上剩下的唯一缺口
