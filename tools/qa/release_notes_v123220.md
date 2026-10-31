## 雪绒的钢铁雄心编辑器 v1.23.22

海军接口加国家参数。

### 问题：船加到了阿根廷

`load_navy` 是按**文件名字母序**把所有 mod 的舰队摊平成一个列表的：

```
总舰队 270
[0] Armada Argentina   ARG_1936_naval_legacy.txt
[1] Armada Argentina   ARG_1936_naval_mtg.txt
[2] Armada Argentina   ARG_1939_naval_legacy.txt
...
[82] 德国舰队          GER_1936_naval.txt
```

`navy_add_ship(fi=0, ti=0)` 意思是「第一个舰队的第一支特遣队」，而第一个是**阿根廷的**。
想给德国加船，界面上的 `0` 根本指不到德国。

结果就是测试模组里海军写进了 `ARG_1936_naval_legacy.txt`，德国海军一条船都没加。

### 改法

`navy_add_ship` / `navy_add_tf` 加 `tag` 参数：

```python
navy_add_ship(root, fi=0, ti=0, tag="GER")
```

给了 tag 以后 `fi` 的含义变成「**该国的**第几支舰队」：

```python
idxs = 按文件名前缀过滤出该国的舰队索引   # GER_ → [82,83,84,85,86]
fi = idxs[fi]                              # 0 → 82
```

文件名的国家前缀就是 HOI4 判断归属的依据，和人物、部队那边同一个道理。

### 实测

```
总舰队: 270
GER 舰队索引: [82, 83, 84, 85, 86]
加船: 已在第 1 个特遣队加 1 艘 destroyer
写到: GER_1936_naval.txt
```

### 界面还没改

海军面板现在还是填裸序号，用户不知道该填 82 还是 0。
这一步要改前端：舰队列表上加国家过滤，或者直接把序号换成「点选舰队」。

### 回归

```
写接口  10/10
```
