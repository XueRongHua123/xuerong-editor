## 雪绒的钢铁雄心编辑器 v1.23.15

改单个州不再需要整目录接管。

### 原来的问题

原版环境下改一个州的资源，`state_save` 直接拒绝：

```
原版目录只读：请先复制到自己的模组再修改
```

要绕过去只能 `adopt_dir(mod, 'history/states')`，而它会：

- 复制全部 **1081 个州文件**
- 在 descriptor.mod 里写 `replace_path="history/states"`

`replace_path` 一写，**整个目录只读自己这一份**。漏复制任何一个州，那个州就从游戏里消失了。
CN + CNsub 那边踩过这个坑：CNsub 独占 `history/states` 后只提供 182 个州，
CN 的 821 个全部失效。

### HOI4 的两套加载规则

**不加 replace_path**：文件合并，同名覆盖。

```
你的 mod: history/states/1-France.txt      ← 覆盖原版同名文件
原版:     history/states/2-Germany.txt     ← 照常生效
结果：1081 个州，其中 1 个是你改的
```

**加了 replace_path**：整个目录只认 mod 这份，原版全丢。

### 新增 ensure_file_writable

```python
ensure_file_writable(root, sub, basename) -> (目标路径, 说明) | (None, 错误)
```

两种情形分开处理：

1. **目录被别的 mod 用 replace_path 独占** → 返回错误，说明必须整目录接管
   （独占时只有那一层的文件会被游戏读到，单文件复制没用）
2. **目录没被独占** → 只把要改的那一个文件复制到自己的 mod，**不写 replace_path**

`state_save` 改成走这条路。硬性的「原版目录只读」直接拒绝删掉了。

### 实测

```
原版州数: 1081
state_save: 已写入 1-France.txt
复制了 1 个文件: ['1-France.txt']
descriptor 有 replace_path 吗: False
```

改一个州只多 1 个文件，其余 1080 个州照常用原版。

### 适用范围

同一条路子可以套到其他单文件编辑上：

- `country_save`（改一个国家）
- `event_save`（改一个事件文件）
- 任何「一个文件对应一个实体」的场景

不需要整目录接管，也不该整目录接管。

### 回归

```
写接口  10/10
```
