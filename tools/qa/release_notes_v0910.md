## 雪绒的钢铁雄心编辑器 v0.91.0

支持 **submod 的 submod**：子 mod 没有地图时，自动沿依赖链用父 mod 的地图。

### 问题

`muvluvCNsub`（workshop 2989050816）只覆盖 `history/states`、`common/units` 等目录，
**自己没有 `map/provinces.bmp`**。之前编辑器把它当独立 mod，直接报「这个来源没有地图」。

### 现在：mod 叠加链

读 mod 的 `descriptor.mod`：

```
name="muvluvCNsub"
dependencies={ "muvluvCN" }
replace_path="history/states"
...
```

沿 `dependencies` 逐层向上找父 mod，得到叠加链（原版 → 父 → 子）。
实测启动 submod 服务后：

```
链: Hearts of Iron IV → 2800380626 → 2989050816
地图源: 2800380626
```

### 查找规则（按 HOI4 语义）

| 情况 | 行为 |
|---|---|
| 普通文件 | 从链尾往链首找，**第一个命中的生效**（子 mod 优先） |
| 落在 `replace_path` 目录下的文件 | 只在声明该 `replace_path` 的 mod 里找，**不往下合并** |
| 整条链都没有，原版也没有 | 报错，不静默编造 |

写入操作永远落在**链顶**（最具体的那个 mod），不会写到父 mod 或原版。

### 实测 5 个 mod 全部通过

| mod | 国家 | 州 | 地图 | 开局日期 |
|---|---|---|---|---|
| 原版 | 439 | 1081 | ok | 1936.1.1 |
| muvluvCN_1.19 | 117 | 818 | ok | 1999.8.7 |
| 2438003901 | 512 | 2525 | ok | 1962.1.1 |
| 2800380626（muvluvCN 工作坊版） | 116 | 818 | ok | 1999.8.7 |
| **2989050816（muvluvCNsub）** | 117 | 818 | **ok（地图来自父 mod）** | 1999.8.7 |

### 界面

地图顶栏的元信息会追加「地图来自 父mod名」，让人一眼看出地图不是这个 mod 自己的。

### 当前边界

- 叠加链已覆盖**地图**（provinces.bmp / definition.csv）
- 国家、州、战略区、铁路的解析目前仍是单层，下一步接入叠加
- 父 mod 定位靠 `descriptor.mod` 的 `name` 匹配，重名时可能找错，之后加手动指定
