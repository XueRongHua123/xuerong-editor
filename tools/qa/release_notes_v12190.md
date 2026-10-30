## 雪绒的钢铁雄心编辑器 v1.21.9

国家 TAG 增删（`common/country_tags`）。

### 数据形态

```hoi4
BET = "countries/BETA.txt"
H00 = "countries/H00.txt"
...
dynamic_tags  = yes          # 特殊行，不是 tag
```

muvluvCN：**116 个 tag**，分两个文件（`MVLV_countries.txt` + `zz_dynamic_countries.txt`）。

配套的 `common/countries/X.txt` 定义颜色和文化：

```hoi4
graphical_culture = commonwealth_gfx
graphical_culture_2d = commonwealth_2d

color = { 152  130  191 }
```

### 新增接口

```
POST /api/country_tags              {}                    全部 tag
POST /api/country_tag_add           {tag, color, culture} 加 tag（自动建定义文件）
POST /api/country_tag_delete        {tag}                 删 tag（带引用检查）
POST /api/country_tag_refs          {tag}                 查引用
```

### 加 tag 会做两件事

1. 在 `common/country_tags/zz_editor_tags.txt` 追加 `TST = "countries/TST.txt"`
2. 在 `common/countries/TST.txt` 生成定义（颜色 + 文化）
   - 颜色不填就按 tag 的 md5 生成一个稳定色

### 删 tag 前先查引用

```
AFR 被引用 196 处（州归属 63、核心 131、国家历史 1、国策树 1）
```

有引用就拒绝删除，返回 `need_confirm` 和明细。
强行删会在游戏里留下悬空引用（州指向不存在的国家）。

### 实测

```
未接管 common/country_tags → 拒绝写入
接管 → 加 TST（颜色 200,80,60，asian_gfx）
  生成 zz_editor_tags.txt: TST = "countries/TST.txt"
  生成 countries/TST.txt: graphical_culture = asian_gfx / color = { 200 80 60 }
  TST 出现在列表里
删 TST → 成功，TST 消失
删 AFR → 被挡（136 处引用：州归属 3、核心 131、国家历史 1、国策树 1）
CN 的 country_tags 和 countries 都未被改动
```

（两次引用的数字不同：第一次是刚加载完，第二次在接管并重载后。以第二次为准。）

### 界面

「编辑」tab → 国家 TAG：

```
[载入] [过滤____]

AFR   countries/Africa.txt          [删]
BET   countries/BETA.txt            [删]
H00   countries/H00.txt             [删]
…

新增
[TAG] [r,g,b] [加]
```

### 一个待改的地方

C 族国家的 color 定义在 `common/countries` 里是**共享文件**（42 个文件对应 116 个 tag），
新增的 tag 会单独建一个同名文件。如果之后要在国策里给新 tag 做旗子，还得手动加 gfx。

### 回归

```
写接口  10/10
```
