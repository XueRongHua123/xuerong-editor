## 雪绒的钢铁雄心编辑器 v1.23.33

建世界流程打通到产出文件，同时修掉 5 个真实缺陷、补 3 项静态检查。

### 一、修掉的 5 个缺陷

**1. `state_create` 不写 `history = { owner }`**

建出来的州是无主地，地图上不属于任何国家。现在加了 `owner` 参数，给了就同时写
`owner` 和 `add_core_of`，顺序照原版（在 `state_category` 之后、`provinces` 之前）。

**2. `country_tag_add` 不建 `history/countries`**

只写了 `common/country_tags` 和 `common/countries`，新国家在游戏里没有首都、
没有政府、没有科技。新增 `country_history_create`，照原版最简国家的格式写全
`capital` / `set_research_slots` / `set_technology` / `set_politics` / `set_popularities`。
另外按文件名里的 tag 查重——HOI4 认 tag 不认文件名，同一个 tag 有两个文件会互相打架。

**3. 五个写入层函数只查全局 `ROOTS`**

`_country_tags_write_base`、`write_base`、`_units_write_base`、
`_country_hist_write_base`、`_bookmark_write_base` 都只在 `ROOTS` 里找链顶 mod。
脚本直接调用时 `ROOTS` 是空的，五个全报「找不到可写的 mod 目录」，哪怕传入的
目录完全可写。改成优先用传入的 `root` 解析叠加链，再退回 `ROOTS`。

**4. `bookmark_add` 把中文名当本地化 key**

写出来的 yml 是 `新世界:0 "新世界"`，游戏报
`Invalid key name at line 2 and column 2`，剧本名也显示不出来。
改成用 `ZZ_EDITOR_BM_<hash>` 生成 ASCII key，中文名放在值那一侧。

**5. `_ensure_prov_rgb` 是懒加载，没人触发**

`load_mod` 不调用它，`PROV_RGB` 一直是空的，按省号建州时省的集合为空。

### 二、新增 `world_create`（实验性）

一个调用串起十个步骤，复用编辑器已有功能，不自己拼文件：

```
地图生成 → 写 descriptor → 重载地图 → 建国家 tag → 建州（带 owner）
→ 国家历史 → 师团模板 → 开局部队 → 本地化 → 剧本
```

40 省的地图产出 102 个文件，各步骤的成败逐条返回。

**这是骨架，不是可玩 mod。** 地图本身能加载（`Loaded 208 provinces`），
但点「开始」进入游戏时仍会崩。原因见下。

### 三、`replace_path` 必须成组

换地图等于换省号/州号，凡是按 id 引用的目录都要整体替换。实测规律：

> replace 一个目录，必须同时 replace 所有引用它的目录，否则引用链断裂。

- 只 replace 13 条（history + map + ai_* + bookmarks）→ 进游戏崩
- 补到 50 条 → 地图加载正常，但 **3879 条 `Invalid idea`**，因为
  `common/on_actions`、`achievements.txt`、`continuous_focus`、
  `special_projects`、`factions` 都在引用被换空的 `common/ideas`

两条配套的坑：

- **纯资源目录不能 replace**：`music` 换空后引擎报
  `Could not find music named maintheme`，停在地图加载前的 `4489 defines loaded`。
  `gfx/flags`、`portraits`、`gfx/loadingscreens` 同理。
- **被引用的一端不能换空**：`common/units`、`common/units/equipment`、
  `common/technologies` 换空后师团模板和 `set_technology` 全失效。

### 四、诊断新增 3 项（共 16 项）

| 检查 | 作用 | 实测 |
|---|---|---|
| `replace.drops_vanilla` | replace 掉原版数据后丢了多少 tag / trigger / effect / 精神 / 科技 | 一张 40 省测试图报出「原版 461 个 tag 丢了 461 个」 |
| `replace.dangling_refs` | 哪些目录还在引用被 replace 掉的内容 | 50 条 replace 的样本 1.1 秒报出 28 个危险目录 |
| `script.tag_undefined` | 引用了不存在的国家 tag | CN 仓库 0 条、子 mod 单独 6 条、叠加后 0 条 |

`replace.dangling_refs` 按目录归并输出，单个目录最多一条，总量上限 40 条，
避免把界面刷满。

### 五、升级建议

- 用编辑器建州的人：这一版之前建的州都是无主地，需要重新建一遍
- 用 `country_tag_add` 建过国家的人：那批国家缺 `history/countries`，需要补
- 建过剧本的人：旧 yml 里的中文 key 需要删掉重新生成
