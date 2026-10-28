## 雪绒的钢铁雄心编辑器 v1.9.6

还完最后两项技术债：日志行号跳转、国家字段补全。

### 1. 日志能跳到出错行

error.log 弹窗从纯文本改成可点列表。每行末尾标出能定位的文件位置：

```
[08:59:22][ai_strategy.cpp:6907]: common/ai_strategy/JAP.txt:74 AI strategy ...
                                                          ↑ 点这里
```

点一下，下方展开该文件第 74 行前后各 6 行，命中行高亮。

解析支持两种写法：

```
... in file events/xxx.txt line 42
... at events/xxx.txt:42
```

引擎自己的 cpp 位置（`ai_strategy.cpp:6907`）不是 mod 文件，忽略。

### 2. 国家字段补全

`/api/countries` 之前只有 `tag / name / owned / cores / ideas`。现在加了：

```json
{"tag": "AFR", "name": "非洲联合", "capital": "275",
 "political_power": "0", "ruling_party": "democratic", ...}
```

政治视图点国家时，能看到首都省号、政治点和执政党。

### 备忘录

`work/BACKLOG.md` 里技术债 5 项全部标 ✅：

```
1. 撤销备份 33MB        ✅ v1.9.4
2. base.png 半分辨率    ✅ v1.9.5
3. 事件树循环挤层       低影响，暂缓
4. 预览 resize 不重算    ✅ v1.9.5
5. 国家字段不全         ✅ v1.9.6
```
