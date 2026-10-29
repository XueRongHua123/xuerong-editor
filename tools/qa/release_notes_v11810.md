## 雪绒的钢铁雄心编辑器 v1.18.1

跨 mod 回归跑出来的修复。

### 回归背景

新增两个回归脚本：

| 脚本 | 内容 | 覆盖 |
|---|---|---|
| `qa/regress_all.py` | 12 项读接口 | 14 个 mod |
| `qa/regress_write.py` | 5 项写接口（用副本） | 带地图的 mod |

读接口全部通过：**168/168**。

写接口跑出 1 个真 bug。

### 修的 bug：装备块定位错位

`equipment_edit` 从 v1.15.0 起一直在**写错位置**。

表面看是成功的——返回「已更新 xxx：reliability 0.8→0.88」，
但值写进了**别的装备块**里（文件第 151 行而不是目标块的第 270 行）。

两个原因叠加：

1. `top_items()` 的第三个返回值是「有没有 {} 块」的布尔值，不是字符偏移。
   代码里拿它当偏移用：`brace_match(text, True)` 会从位置 1 开始配对，
   结果定位到文件开头的某个块。

2. `strip_comments()` 会截断注释，导致去注释文本和原文的字符偏移不一致。
   `_equip_locate` 在去注释文本里算偏移，`equipment_edit` 却拿它去切原文。

修法：

- 新增 `_strip_keep_len()`：去注释但**保持字符长度不变**（注释替换成空格）。
  需要「在去注释文本里定位、再回到原文改写」的场景必须用它。
- `_equip_locate` 自己按 key 在块内定位 `{` 的偏移，再换算到全文坐标系。

验证：`CAS_equipment_1` 的 `reliability` 从 0.8 改成 0.88，
写在第 270 行（目标块内），再读得到 0.88。

### 回归里的其余失败项（不是缺陷）

| 项 | 现象 | 定性 |
|---|---|---|
| 改地形（muvluvCN） | 「terrain.bmp 与 provinces.bmp 不同源」 | **设计保护**。CN 换了地图没换地形图，改地形会错位，拒绝是对的 |
| 改地形（京都燃烧） | 「terrain.bmp 没变」 | 该省已是目标类型，`changed=false`；测试原本要求 md5 必变，判定过严 |
| 战略区（muvluvCN） | 「没有空闲省」 | CN 的战略区覆盖了全部省，新建需要先腾出省，属数据事实 |
| 州细化（京都燃烧） | 「这些省在地图上不存在」 | 京都的 `history/states` 结构与 CN 不同（182 个州、省列表为空），测试选州逻辑需要按 mod 适配 |

这四项要在测试脚本里做 mod 适配，不是编辑器的问题。

### 两个脚本的用法

```bash
python work/qa/regress_all.py              # 读接口，自动发现 14 个 mod
python work/qa/regress_write.py            # 写接口，每个 mod 用副本，不动原数据
python work/qa/regress_write.py <mod> ...  # 指定 mod
```

写测试会建最小副本（provinces / definition / terrain / railways / states /
equipment / strategicregions），跑完删掉。
