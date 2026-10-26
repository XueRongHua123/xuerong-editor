## 雪绒的钢铁雄心编辑器 v0.78.0

跨 mod 兼容性修复：政治视图在部分第三方 mod 上整图无配色的情况。

### 问题现象

加载某些第三方 mod（本书以 workshop `2438003901` 为例）后，只勾选「政治（按国家）」图层，地图几乎全灰，仅个别国家有色。

### 两个根因

**1. 颜色语法覆盖不足**

这类 mod 普遍使用 `color = rgb { 60 60 60 }` 写法（HOI4 同时支持 `{ r g b }` 与 `rgb { r g b }`），旧正则只允许 `=` 后可选的 `{`，遇到 `rgb` 直接失配，导致国家无颜色，全部落到 fallback 灰。

现在同时支持：

- `color = { r g b }`
- `color = rgb { r g b }`
- `color = hsv { h s v }`（内部转换为 rgb）

**2. mod 覆盖的国家定义文件可能只写 graphical_culture**

该类 mod 的 `common/countries/Italy.txt` 仅包含：

```
graphical_culture = western_european_gfx
graphical_culture_2d = ITA
```

没有 color。旧逻辑读到该文件即 `break`，不再尝试原版同名文件，导致颜色缺失。

现在：缺少 color 时继续到原版（游戏本体）的同名文件查找，命中即采用。

### 修复后的实测（同一 mod）

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 政治层不同颜色数 | 6 | 26 |
| fallback 灰占比 | 31.9% | 24.3% |
| 意大利 | 灰 | 绿（67 127 63 系） |

剩余 24.3% 的灰是「原版与 mod 均未定义 color」的国家，67% 的深灰是海域及未归属州省，两类均符合预期。

### 顺带修正

`def_path` 之前少拼接 `common` 目录，导致路径显示错误，现指向实际文件。

### 验证

- 该 mod：州 1 owner=ITA、州 5/50 GER、州 400 VYT、州 500 BRA，归属解析正确
- 政治层 26 种颜色，意大利为绿色
- muvluvCN 复测：BETA 巢穴区域保持黑色，v0.77 的修复未回退
