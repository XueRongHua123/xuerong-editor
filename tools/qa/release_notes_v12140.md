## 雪绒的钢铁雄心编辑器 v1.21.4

三件事：模板编辑区挪位、支援连格子重做、国家初始科技。

### 1. 模板编辑区挪到「编辑」tab

之前挂图层面板下方，要滚动才能看到。现在进地图页 →「编辑」tab，第一块就是。

### 2. 支援连改成 5 个固定槽位

原来是 5×1 网格 + 弹框手输兵种 id。现在：

```
支援连（最多 5 个，师级）
1  [— 空 — ▾]
2  [engineer ▾]
3  [— 空 — ▾]
4  [— 空 — ▾]
5  [— 空 — ▾]
```

每个槽位是下拉框，选项按兵种 `group` 分组（infantry / support / armor / tsf …）。
选中后格子变暖色边框，取消回到「空」。

### 3. 国家初始科技（列表式）

「编辑」tab 里新增：

```
国家初始科技
[TAG] [载入]

MVLV_tsf_folder            43/135
├─ [✓] MVLV_tsf_basic       1936
├─ [ ] MVLV_tsf_adv         1939
│  …
UNI_tsf_folder             19/163
│  …
```

- 按科技文件的 `path`（folder）分组，`<details>` 折叠
- 已解锁的复选框勾上，未解锁的灰字
- 点复选框直接切换，调 `/api/country_tech_toggle`

### 后端

```
POST /api/country_techs         {tag}        已解锁 + 全部科技分组
POST /api/country_techs_raw     {tag}        只要已解锁列表
POST /api/country_tech_toggle   {tag, tech, on}
```

### 实测（muvluvCN）

```
读 AFR：251 项科技（5 个 set_technology 块），分 18 组
  MVLV_tsf_folder   135 项，已解锁 43
  UNI_tsf_folder    163 项，已解锁 19
未接管 → history/countries 被 replace_path 独占，拒绝写入
接管 → 拷贝 41 个文件
加 panzerschiffe → 251 → 252
删 panzerschiffe → 252 → 251
CN 未被改动
```

### 关于日期块

之前 `state_save` 踩过「日期块覆盖直接子级」的坑，所以这次先查了
CN 的 `set_technology` 有没有被日期块包着——**41 个文件全部在顶层**，不受影响。

### 回归

```
写接口  10/10
```

### 还没做

科技树可视化（B 方案）。`TECHS` 里已经有 `fx` / `fy` 坐标，可以直接画。
