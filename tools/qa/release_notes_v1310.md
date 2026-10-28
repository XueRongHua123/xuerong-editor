## 雪绒的钢铁雄心编辑器 v1.3.1

检查面板新增「本地化」页：找出脚本里引用、但没有任何 yml 定义过的本地化键，可一键生成占位。

参考 [CWTools](https://marketplace.visualstudio.com/items?itemName=tboby.cwtools-vscode) 的 "Code actions to generate .yml for missing localisation"。

### 查哪三类

只查有明确命名规则的引用，避免误报：

| 类型 | 从哪读 | 推论 |
|---|---|---|
| 国策 | `common/national_focus/*.txt` 的 `focus = { id = X }` | `X` 与 `X_desc` |
| 事件 | `events/*.txt` 的 `country_event = { id = X }` | 读它自己的 `title = ` / `desc = ` 字段 |
| 国家精神 | `common/ideas/*.txt` 的顶层键 | `X` 与 `X_desc` |

事件这一条尤其重要：HOI4 的事件 id 和本地化键**是分开的**：

```hoi4
country_event = {
    id = BETA.1
    desc = BETA.1.d
    title = BETA.1.t
}
```

本地化键是 `BETA.1.d` / `BETA.1.t`，不是 `BETA.1.desc`。第一版我按 `id + ".title"` 硬套，muvluvCN 报出 598 个假缺失；改成读 `title` / `desc` 字段后降到 354 个，抽验 `BETA.1.t` 在整个 localisation 目录搜不到，确认是真缺。

### 只查 mod 自己的脚本

第一版把原版两千多个事件文件也扫进来了，报出 **37577** 个缺失——原版本地化本来就不全，查它只有一屏无意义的红字。

现在只遍历 mod 根目录下的 `common/national_focus`、`events`、`common/ideas`。

### 一键生成

点「生成占位」写入 `localisation/simp_chinese/zz_xuerong_autogen_l_simp_chinese.yml`：

```yaml
l_simp_chinese:
 BETA.1.d:0 "BETA.1.d"
 BETA.1.t:0 "BETA.1.t"
 BETA.10.d:0 "BETA.10.d"
```

占位值就是键名——游戏里会显示成 `BETA.1.t` 这样的键名，一眼能看出还没翻译。

已经存在的行不会被覆盖（保留你改过的内容），只追加新键。带 UTF-8 BOM，没 BOM 游戏读不到。

### 实测（muvluvCN 1.19）

```
引用 1662 个本地化键，缺 354 个
国策 47 · 事件 289 · 精神 18
耗时 117ms
```

生成的文件 12.8 KB，354 行。

### 已知限制

只覆盖三类引用。装备、科技、决议、MIO、GUI 里的本地化键没查——它们的命名规则各不相同，硬猜会误报。后续可以按类型逐个加。
