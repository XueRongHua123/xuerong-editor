## 雪绒的钢铁雄心编辑器 v0.96.0

体检新增**编码规范检查**（BOM）。

### 规则（HOI4 的硬性要求）

| 文件类型 | 要求 | 违反后果 |
|---|---|---|
| `localisation/*.yml` | 必须带 UTF-8 BOM | 游戏读不到本地化，界面显示 key 名 |
| `common` / `history` / `events` 下的 `.txt` | 不应带 BOM | 首行可能被当成非法 token，或静默忽略 |

### 实测两个真实 mod

| mod | yml | txt | 问题 |
|---|---|---|---|
| muvluvCN_1.19 | 149（全部合规） | 856 | **126 个 txt 带多余 BOM** |
| 2438003901 | 527 | 2131 | **1 个 yml 缺 BOM**（`TNO_TT_caribbean_l_english.yml`）+ 124 个 txt 带 BOM |

典型例子：`common/names/*.txt` 一批文件带 BOM。这类问题在游戏里表现为莫名其妙的解析错误，
以前只能靠翻 error.log 找，现在体检直接列出文件路径。

### 检查量

- 只扫 `localisation` 与 `common/history/events` 三处，单次约 1 秒
- 命中项在体检里以「编码规范问题」一条汇总，附前 5 个文件路径
