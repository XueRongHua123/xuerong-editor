## 雪绒的钢铁雄心编辑器 v1.23.20

人物删除时同步清掉 `recruit_character`。

### 把人物编辑这条链补全

| 操作 | 改哪个文件 | 状态 |
|---|---|---|
| 新建 | `common/characters/<TAG>.txt` + `history/countries/<TAG> - *.txt` 的 `recruit_character` | ✅ v1.23.19 |
| 改类型 | `common/characters/<TAG>.txt` 的块名 | ✅ v1.23.18 |
| 删除 | 两处一起删 | ✅ 这一版 |

上一版只做了「新建写招募」，删除时只删了 `common/characters` 里的定义，
`history/countries` 里的 `recruit_character = XTT_Gen` 留着——游戏会引用一个不存在的人物。

### 实测（完整往返）

```
新建后 recruit 数: 136
删除: 已删除人物「测试将军」，并清掉了 GER - Germany.txt 里的 recruit_character
删后 recruit 数: 135（原版 135）
还有 XTT_Gen 吗: False
人物文件还有 XTT_Gen 吗: False
```

加进去 136 条，删完回到 135 条，两个文件都干净了。

### 顺带修一个 BOM 漏网

`character_delete` 里写文件用的是硬编码 `b"ï»¿"`，没走 `_bom_for`——
之前那次 BOM 统一修改只替换了调用 `_bom_for` 的地方，漏了这种直接写字面量的。
现在改成 `_bom_for(p)`。

### 回归

```
写接口  10/10
```
