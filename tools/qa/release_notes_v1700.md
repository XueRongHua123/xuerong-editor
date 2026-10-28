## 雪绒的钢铁雄心编辑器 v1.7.0

事件树现在能就地改 title / desc / option，新建命名空间时会自动生成本地化。

### 1. 事件树右侧多了一栏编辑区

点节点 → 右侧加载这个事件：

```
事件详情  mvlv_generic.0    events\MVLV_generic.txt
title 键  [mvlv_generic.0.t]
          ＜简史＞（1944～1999）
desc 键   [mvlv_generic.0.d]
          1944年：日本有条件投降，大东亚战争结束n1945年；被核…
选项 1
  name 键   [mvlv_generic.0.a]
  触发事件  [               ]

[保存到文件]  [打开完整编辑器]
```

- title / desc 显示**键名**和**翻译后的文本**，改哪个都行
- 每个 option 的 name 键和触发目标都能改
- 「保存到文件」只替换匹配到的行，不动其它内容；改前 snapshot
- 外部引用节点（不在本 mod 的）不加载编辑区

实测：把 `mvlv_generic.0` 的 title 从 `.t` 改成 `.t2`、desc 改成 `.d2` →
`changed: ['title', 'desc']`，文件里两行确实变了，其它内容原样。

参数没变化时会返回「没有实际改动」，不会误写。

### 2. 新建命名空间自动生成本地化

之前只提示"记得补 xxx.t / .d / .a"，现在直接写好：

```
events/zz_xuerong_<ns>.txt
localisation/simp_chinese/zz_xuerong_<ns>_l_simp_chinese.yml

l_simp_chinese:
 <ns>.1.t:0 "【未命名事件】"
 <ns>.1.d:0 "（在这里写事件描述）"
 <ns>.1.a:0 "确定"
```

实测：`创建 autoLoc → locFile: zz_xuerong_autoLoc_l_simp_chinese.yml`。

### 说明

就地编辑只改**键名**和**触发目标**，不直接改中文文本——文本在 yml 里，
按 CWTools 的思路，文本编辑该用本地化那一套，而不是把文本塞回事件文件。
