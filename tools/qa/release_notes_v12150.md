## 雪绒的钢铁雄心编辑器 v1.21.5

科技树预览。

### 之前是什么情况

国策树有预览（`focus_tree_graph` + SVG），事件有图（`event_graph`），
**科技树没有** —— 只有 `tech_move` / `tech_link` 两个改坐标的接口，看不到整棵树。

`TECHS` 里其实早就有 `fx` / `fy`（解析 technologies 定义时读的 x/y），只是没接出来。

### 新增

```
POST /api/tech_graph   {folder}        只给 folder 列表
POST /api/tech_graph   {folder, tag}   节点 + 连线（带该国解锁状态）
```

返回：

```
infantry_folder：43 个节点、35 条连线
  节点: {id, name, x, y, year, cost, on}
  连线: [[父, 子], ...]   ← 来自 leads_to_tech
```

### 界面

「编辑」tab → 国家初始科技 → **科技树预览**：

```
[infantry_folder (43) ▾] [画]

infantry_folder：43 个节点、35 条连线
┌────────────────────────┐
│  [1936]                │
│    │                   │
│  [1918]───[1914]       │
│    │         │         │
│  [1936]   [1936]       │
│    │                   │
│  [1938]                │
└────────────────────────┘
```

- 已解锁的节点绿色（如果填了 TAG 并载入过）
- 未解锁的深灰
- 悬停显示完整 id 和名称
- 每个目录一个独立视图

### 数据实测

```
科技总数 962
有 fx/fy: 811（84%）
有前置: 595
有后继: 482
目录: 18 个（UNI_tsf_folder 163 / MVLV_tsf_folder 135 / infantry_folder 43 …）
```

**151 个科技没有坐标**（多半是 mod 加的、没写 x/y），预览时跳过，接口会在 msg 里报「N 个无坐标已跳过」。

### 浏览器实测

```
hasSel=true hasSvg=true 目录下拉 14 项
画 infantry_folder → 43 节点、35 连线、宽 304px
problems: []
```

### 还能改的

- 节点现在显示年份，格子只有 34px 宽，显示不下科技名
- 没有缩放/拖拽（国策树预览有 `makePannable`，这里没接）
- 没有高亮前置链

### 回归

```
写接口  10/10
```
