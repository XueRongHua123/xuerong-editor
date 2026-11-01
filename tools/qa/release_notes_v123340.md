## 雪绒的钢铁雄心编辑器 v1.23.34

把诊断器报出的 replace 断链做成一键可修。

---

### 一、背景

HOI4 的 `replace_path` 是整体屏蔽：声明 `common/ideas` 之后，这个目录只从本 mod 读，
原版的整个目录失效。但原版的 `achievements.txt`、`on_actions`、`special_projects`、
`factions` 里还写着 `add_timed_idea = xxx`，于是加载期刷出海量 `Invalid idea`。

上一版（v1.23.33）能**报出**「谁在引用被 replace 掉的东西」，但只给一句建议，
没有可点的动作。这一版把它接成可执行。

---

### 二、三种修复动作

诊断面板里每条 `replace.dangling_refs` 现在带按钮：

| 动作 | 做什么 | 什么时候用 |
|---|---|---|
| **撤销 replace** | 从 `descriptor.mod` 删掉那条 `replace_path` | 误加了 replace、其实需要原版内容时（推荐） |
| **接管该目录** | 把引用方目录整个复制进本 mod 并写 replace_path | 换了地图、必须整体替换时，需要一份可编辑副本 |
| **忽略** | 标记为已知，不再提示（只存本地，不改 mod） | 确认那些引用执行不到 |

面板顶部有汇总条：「全部撤销 replace」和「全部接管（N 个）」，N 只统计真能接管的。
接管前有 `confirm()`，因为会往 mod 里复制几百个文件。

**做不到的**（面板里不给按钮，理由写在 note 里）：

- 引用方是 `common` / `events` 根下的单个文件时只能撤销或忽略，不能接管
- replace_path 是上一层 mod 声明的，本 mod 删不掉，要改得去那边
- `music` / `gfx/flags` / `portraits` / `gfx/loadingscreens` / `common/units` /
  `common/technologies` / `common/country_tags` 禁止接管——这几类换空会让游戏起不来
- 接管只是把原版内容拷过来，按省号/州号写的引用仍然要自己改

---

### 三、新增接口

```
POST /api/replace_drop       {sub}
POST /api/replace_fix_all    {kind, subs, force}
POST /api/replace_ignore     {subs, ref_dir, group, remove}
```

`replace_fix_all` 的 `kind` 取 `drop_replace` 或 `adopt_ref_dir`。多个引用目录指向
同一个被 replace 目录时，`drop_replace` 只执行一次；`adopt_ref_dir` 按引用方目录去重。
失败不中断，全部做完再重扫一次给出剩余数量。

---

### 四、修掉 `adopt_dir` 三处旧缺陷

这个函数以前就有，但一直有问题，这次一并修了：

**1. 源层可能解析成它自己**

原来源层从链顶开始找，链顶就是自己，`shutil.copyfile` 抛 `SameFileError`，
被 `except: pass` 吞掉，结果是「拷贝 0 个文件」却照样写了 replace_path，
看起来成功实则什么都没做。

现在源层跳过 `top`；`_replace_owner` 返回 `top` 时视为没有上层来源。

**2. 允许接管顶层桶目录**

`adopt_dir("common")` 会拷 2267 个原版文件并写 `replace_path="common"`，
等于把整个游戏数据换成一份残缺副本，加载期直接崩。

现在 `sub` 不含 `/` 直接拒绝。

**3. 只查全局 `ROOTS`**

脚本调用（`world_create` 编排、qa 脚本）时 `ROOTS` 是空的，全报
「找不到可写的 mod 目录」。改用 `_top_mod(mod_root)` 解析链顶。

---

### 五、改 descriptor 的两处细节

**保留原格式**：读的时候记 `has_bom`，按 `splitlines(True)` 逐行处理，
CRLF 的 descriptor 改完还是 CRLF，带 BOM 的还是带 BOM。

**两级缓存都要清**：`mod_layers` 有 `_LAYERS_CACHE`，`_mod_descriptor` 有
`_DESC_CACHE`。只清一个，撤销完 `_replace_owner` 还拿旧列表判断。

---

### 六、验证

```
python qa/_check_replace_fixup.py     23 项 PASS 23 / FAIL 0   72.1s
python qa/_smoke_replace_api.py        7 项 PASS 7  / FAIL 0   60s
python qa/regress_all.py             180/180（15 个真实 mod）
```

两个脚本都在 `work/tmp/` 里自建样本、跑完自己删，不碰任何真实 mod。

**真机验证的结论**：用 50 条 replace 的样本跑游戏，撤销 `common/ideas` 前后
`error.log` 完全一致（`Invalid idea` 7 条 / 总计 1900 行）。那 7 条来自原版自身：
`special_project_consumer_costs_high` 这类 idea 定义在 `ideas = { hidden_ideas = { } }`
里，而隐藏精神不能用 `add_timed_idea` 添加。样本本身 50 条 replace 已经把引用链切断了，
所以撤销看不出差异——**功能正确，验证样本选得太完整**。

---

### 七、升级建议

- 之前手工改 `descriptor.mod` 删 replace_path 的人：现在有按钮了，不用手改
- 忽略记录存在 `work/cache/replace_ignore.json`，换机器会丢，属于预期行为
- 接管后文件变多，`descriptor.mod` 里的 replace_path 也会增加，提交前看一眼 diff
