## 雪绒的钢铁雄心编辑器 v1.23.14

剧本本地化按游戏语言生成。

### 问题

上一版已经生成了 `localisation/zz_editor_bookmarks_l_english.yml`，但进游戏后
剧本名和各国简介仍然显示裸 key（`XTT_VSTART`、`GER_DESC`）。

原因：**HOI4 只加载和界面语言匹配的 localisation 文件**。这台机器的
`settings.txt` 里是 `language="l_simp_chinese"`，写 `l_english` 的文件完全不生效。

### 改法

新增 `_game_language()`，从 `Documents/Paradox Interactive/Hearts of Iron IV/settings.txt`
读 `language=` 的值，按实际语言写文件名：

```
localisation/zz_editor_bookmarks_l_simp_chinese.yml
```

顺便修了重复 key：name 和 desc 相同时只写一条，已有内容里出现过的 key 也不重复写。

### 实测

```
游戏语言: l_simp_chinese
已新建剧本 XTT_VSTART（1936.1.1.12，2 个国家可选）

文件: localisation/zz_editor_bookmarks_l_simp_chinese.yml
l_simp_chinese:
 XTT_VSTART:0 "XTT_VSTART"
 GER_DESC:0 "GER"
 SOV_DESC:0 "SOV"
```

### 这一版修好的完整链条

从「生成剧本」到「进游戏能选国家」，一共修了四处：

| # | 问题 | 表现 |
|---|---|---|
| 1 | 日期只写三段 | 显示「148月,1939」 |
| 2 | 没有国家块 | 选国家界面全空 |
| 3 | `default = yes` 缺失 | 不被当成默认剧本 |
| 4 | 本地化语言不对 | 剧本名、国家简介显示裸 key |

四条全修完后，原版 HOI4 里能看到：

```
选择剧本 → 三个卡片（其中第二个是我们建的，11月1936）
选择国家 → 德国 / 苏联 / 美国 / 英国 / 法国 五个头像
          领袖、意识形态、执政党全部正确
```

### 回归

```
写接口  10/10
```
