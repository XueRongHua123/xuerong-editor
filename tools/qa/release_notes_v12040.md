## 雪绒的钢铁雄心编辑器 v1.20.4

**改 owner 不生效**的修复。v1.20.3 的真机验证结论作废——那个「苏联」看错了。

### 问题

`state_save` 改 owner 时只改了 `history` 直接子级：

```hoi4
history = {
    1999.1.1 = {
        owner = EUR      ← 没改
    }
    owner = SOV          ← 只改了这个
}
```

HOI4 的语义是**日期块覆盖直接子级**。muvluvCN 的开局是 1999.8.7，
1999.1.1 那个日期块生效，所以游戏里显示 **欧洲联盟**，不是改的苏联。

真机验证时 DEBUG 面板写着 `Owner = ( ) 欧洲联盟`，与文件里的 `owner = SOV` 并存——
这一条当时看漏了。

### 修法

新增 `_set_owner_all(body, owner, hb, he)`：

1. 先改所有**日期块内**的 `owner`（depth == 2）
2. 再改 `history` 直接子级（depth == 1），没有就插入

两处都改，无论开局日期落在哪个区间都生效。

**验证**（重建测试 mod）：

```
改后文件
  11: owner = SOV    ← 1999.1.1 日期块内
  13: owner = SOV    ← history 直接子级
```

### 同类问题可能还有

`state_save` 里其他字段也是同样的「先 depth=1 再 depth=2」结构：

- `add_core_of`（cores）—— 用 `_drop_in_scope`，只删 (1,2) 两层，逻辑是对的
- `buildings`、`victory_points`、`manpower`、`state_category` —— 走 `_set_in_scope`，可能也有日期块覆盖问题

**这次只修了 owner**，其余字段在 muvluvCN 上没发现日期块写法，先不动。

### 回归

```
写接口  10/10
```

### 真机验证状态

v1.20.3 那次验证的结论作废。下次验证要重新看：

1. `owner` 是否真的变成 SOV
2. `manpower` 显示值（上次设 123456 显示 323.30K，也可能是日期块覆盖）
3. DEBUG 面板要对着看，不能只看州面板

### 关于进不去游戏

测试时 `CN + CNsub` 组合卡在「G弹开发中」（加载阶段），
这是 mod 版本兼容问题，与编辑器无关。
