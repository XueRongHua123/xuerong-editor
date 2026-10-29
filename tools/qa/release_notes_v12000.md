## 雪绒的钢铁雄心编辑器 v1.20.0

三件事一起发：loader 层叠改造、州编辑补全、补给区增删改。

### 1. loader 层叠改造（架构级）

之前加载纯 submod 时，父 mod 的想法/科技/装备读不到——因为那批 loader 都是「扫 root 下一个目录」，
而 `ROOTS` 只有一个 submod 路径。

实测（submod 3829617696 单独加载）：

| | 改造前 | 改造后 | 父 mod 实际 |
|---|---|---|---|
| 想法 | 49 | **6868** | 6868 |
| 装备 | 25 | **454** | 454 |
| 科技 | 172 | **1049** | 1049 |
| 国家 | 116 | **475** | 475 |
| 州 | 818 | 818 | 818 |

改造方式：新增 `_layer_dirs(sub, root)`，把 `load_ideas` / `load_equipment` / `load_techs` /
`load_mod`（国策）/ `load_countries`（历史）/ `_state_file_for` 都改成沿 `mod_layers` 遍历。

**没有**改 `reload_data` 的循环——之前试过让它遍历链，结果 `load_states` 这类内部已处理整链的函数
被重复执行，州数从 818 涨到 1081。只改 loader 内部才安全。

州保持 818 是对的（CN 的 `replace_path="history/states"` 挡掉了原版）。

### 2. 州编辑补全

州视图点选后，除了原来的归属国，新增：

```
类别与人力
  [large_town ▾]  [322900]  [保存]

核心领土
  [GER POL]  [保存核心]

建筑位
  infrastructure        5
  arms_factory          2
  industrial_complex    1
  air_base              1
  …（共 12 种）
  [保存建筑]
```

后端 `state_save` 本来就支持这些字段，这次是补前端。

**修了一个后端缺陷**：`STATE_CATEGORIES` 缺 `large_town` 和 `city`，
这两个是 HOI4 1.19 真实存在的类别，导致这两类州保存时被拒。

实测四个字段全部可写：

```
category   → large_town
manpower   → 777000
cores      → ['GER', 'POL']
buildings  → {arms_factory: 2, infrastructure: 5, industrial_complex: 1, air_base: 1}
```

建筑位保存会**保留原有值**，不会把没填的项清空。

### 3. 补给区增删改

补给区面板新增：

```
区 1　价值 12　4 州        [删] [改]
区 9　价值 25　3 州        [删] [改]

新建 / 修改补给区
  [id] [value] [保存]
  [州号 空格分隔]
```

实测：新建 id=9（value=20，3 州）→ 改值 25 → 删除文件，全部通过。

删除只处理**当前 mod 层**的文件，原版或父 mod 的补给区不动（只读提示）。

### 4. 通用性审计工具

新增 `qa/audit_generic.py`，扫四类硬编码：

```
1. mod 名 / workshop id
2. 地图尺寸 / 省数
3. 特定 tag（H01-H20、mvlv、BETA）
4. 绕开 _layer_files 的裸路径拼接
```

改造前 30 处，改造后 **25 处**。剩下的是分析类函数（`_focus_refs`、`_flag_usage`、
`_scripted_defs`、`_loc_defined_set`），只影响「引用分析」的完整度，不影响读写。

### 回归

```
读接口：36/36（muvluvCN / 雪绒拓展 / 京都燃烧）
写接口：7/10
```

写接口 3 项失败都是已知的测试适配问题，不是新 bug：

- CN 的战略区覆盖全部省，「没有空闲省」
- 京都的省已是目标地形，「terrain.bmp 没变」
- 京都的 state 结构与 CN 不同（182 个州、省列表为空），测试选州逻辑需要按 mod 适配
