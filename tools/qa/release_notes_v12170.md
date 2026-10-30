## 雪绒的钢铁雄心编辑器 v1.21.7

国家精神（`add_ideas`）。

### 数据形态

和 `set_technology` 不同，`add_ideas` 里**直接写 idea id，没有 `= 1`**：

```hoi4
add_ideas = {
    #初期国家精神を定義
    limited_exports
    limited_conscription
    partial_economic_mobilisation
    mvlv_nuclear_winter
}
```

### 新增接口

```
POST /api/country_ideas          {tag}          已启用 + 全部可选
POST /api/country_ideas_raw      {tag}          只要已启用列表
POST /api/country_idea_toggle    {tag, idea, on}
```

`country_ideas` 返回的 items 会把每项和 `IDEAS`（已解析的想法定义）对上，
拿到中文名；对不上的标 `orphan` 并注明「未在 ideas 里找到定义」。

### 界面

「编辑」tab → 国家精神：

```
[TAG] [载入]

已启用
  limited_exports                   [删]
  limited_conscription              [删]
  mvlv_nuclear_winter               [删]
  …

搜索添加
[输入 id 或名字过滤]
  □ mvlv_nuclear_winter
  □ mvlv_prominence_problem
  …
```

**为什么带搜索**：muvluvCN 的想法池有 **6860 项**，全列出来没法用。
空搜索显示前 40 项，输入关键词过滤到 60 项以内。

### 实测

```
AFR：11 项国家精神（1 个 add_ideas 块）
IDEAS 总数 6860
已启用列表里能对上名字的：
  AFR_eu_support   欧盟的积极支援
  AFR_eua          经济殖民地
  MVLV_UNF         国联分担金
浏览器：控件全在、载入 11 行、搜索 "mvlv" 命中 5 项
problems: []
```

### 顺手调的布局

科技树预览高度从 260px 调到 200px，给下面的国家精神面板让位置。

### 回归

```
写接口  10/10
```
