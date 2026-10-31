## 雪绒的钢铁雄心编辑器 v1.23.12

真机验证挖出来的 4 个 bug，全部修复。

### 1. `ai_test` 调用了不存在的函数

路由里写的是 `load_ai_config()`，模块里定义的却是 `load_ai()`。
NameError 让整条路由崩掉，前端只看到「连接被断开」，连原因都看不到。

改了两处：
- 函数名改对
- 配置不全时立刻返回，不发请求。原来会卡满 90 秒的 HTTP 超时，
  用户看到的就是一个转圈然后断开

现在 33ms 返回「配置不全：API Key（在「AI」面板里填）」。

### 2. 新建文件带 UTF-8 BOM

编辑器新建文件时无条件写 BOM。HOI4 的 `common/decisions` 会把 BOM 吃进第一个
token，类别名变成 `﻿XTT_category`，整个类别失效并刷报错。

改成一律不加 BOM（HOI4 读无 BOM 的 UTF-8 完全正常）。
`localisation/*.yml` 那些需要 BOM 的场景不走这条路径。

### 3. `decision_add` 新建类别没注册

HOI4 1.13 起，`common/decisions/categories/` 里必须先注册类别，
否则加载时报 `Unknown category` 并把该类别下的决议全部忽略。

新增 `_dec_category_register()`，新建类别时同步写注册文件：

```hoi4
XTT_category = {
	icon = GFX_decision_category_generic
	visible = { always = yes }
	allowed = { always = yes }
}
```

### 4. `adopt_dir` 不递归复制子目录（最严重）

```python
for fn in os.listdir(src_d):
    if not os.path.isfile(sp):
        continue          # ← 跳过所有子目录
```

接管 `common/decisions` 时，父 mod 的 `categories/` 子目录（34 个文件）
一个都没搬过来，导致父 mod 自己的决议全部报：

```
Invalid Decision Category lar_local_recruitment
```

改成 `os.walk` 递归复制。实测接管 `common/decisions` 的文件数从 1029 涨到 1063，
`categories/` 下 34 个文件全部到位。

这个 bug 从 `adopt_dir` 实现起就在。之前接管 `history/countries` 这类
没有子目录的目录时碰巧正常，所以一直没暴露。

### 怎么发现的

这 4 个都不是接口测试能发现的。接口测试只验证「返回 ok」，
第 2、3、4 个都属于「接口返回 ok，但产物在游戏里无效」。

发现方式是：用编辑器生成一个测试模组，装进 HOI4 实际加载，看 `error.log`。
加载时报的错误指向父 mod 的文件名（`lar_local_recruitment` 是 muvluvCN 的），
一开始还以为是父 mod 自己的问题。

### 还没解决的

测试模组装进游戏后仍然在加载末尾崩溃，还剩一个
`Invalid Decision Category`，需要单独排查。

### 回归

```
写接口  10/10
```
