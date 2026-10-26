## 雪绒的钢铁雄心编辑器 v0.78.0

跨 mod 兼容性修复：政治视图在别的 mod 上全灰的问题。

### 你遇到的现象

加载 `2438003901`（The New Order 类 mod）只勾「政治（按国家）」，整张图几乎全灰，只有伊朗是蓝色。

### 两个真 bug

**1. 颜色语法只认 `color = { 67 127 63 }`，不认 `color = rgb { 60 60 60 }`**

那个 mod 普遍使用 `rgb { }` 写法（HOI4 两种都支持），旧正则在 `=` 后面只允许可选的 `{`，
遇到 `rgb` 直接失配 → 全国无颜色 → 统一 fallback 灰。

现在同时支持 `color = { r g b }`、`color = rgb { r g b }`、`color = hsv { h s v }`（hsv 会转成 rgb）。

**2. mod 覆盖的国家文件可能只写 graphical_culture，不写 color**

例如该 mod 的 `common/countries/Italy.txt` 只有三行：

```
graphical_culture = western_european_gfx
graphical_culture_2d = ITA
```

没有 color。旧逻辑读到这个文件就 `break`，永远不去原版找 → 意大利无颜色。

现在：缺 color 时继续往原版（游戏本体）的同名文件找，找到就用。

### 修完的实测（同一个 mod）

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 政治层不同颜色数 | 6 | **26** |
| fallback 灰占比 | 31.9% | **24.3%** |
| 意大利 | 灰 | **绿（67 127 63 系）** |

剩下 24.3% 的灰是那些**在原版和 mod 里都没有 color 定义**的国家（游戏里同样没有自定义色），
67% 的深灰是海域 / 不属于任何州的省——这两类是对的。

### 顺带修正

`def_path` 之前少拼了 `common` 目录（显示错位），现在指向真实文件。

### 验证

- `2438003901`：州 1 owner=ITA、州 5/50 GER、州 400 VYT、州 500 BRA，归属解析正确
- 政治层 26 种颜色，意大利为绿色
- `muvluvCN` 复测：苏联区域仍是 BETA 巢穴黑色（v0.77 的修复未回退）
