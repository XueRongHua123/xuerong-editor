## 雪绒的钢铁雄心编辑器 v1.20.7

**接管完整性校验**：接管目录后检查有没有漏拷的文件。

### 为什么需要

`replace_path` 接管后，上级 mod 的同名目录**不再被读取**。
接管时少拷一个文件，游戏里就永久少一份数据——而且没有任何报错。

### 新增

```
verify_adopt(mod_root, sub)      校验单个目录
verify_all_adopted(mod_root)     校验所有已接管的目录
POST /api/verify_adopt           不传 sub 时校验全部
```

校验三件事：

1. **数量**：源目录几个文件、自己的副本几个
2. **漏拷**：源里有、自己没的（致命）
3. **内容差异**：同名文件哈希不同的（正常，说明改过）

`adopt_dir` 接管后**自动跑一次校验**，结果附在返回值的 `check` 字段里。

### 实测

空 mod 接管 `map/strategicregions`：

```
已从 2800380626 接管 map/strategicregions：拷贝 226 个文件，并写入 replace_path
源 226 个文件，自己 226 个
校验 ok=True  缺 0  不同 0
```

故意删掉一个文件后：

```
源 226 个文件，自己 225 个；缺 1 个
校验 ok=False
缺失列表: ['1-Southern England.txt']
```

全局校验：

```
接管 1 个目录，1 个有问题
  map/strategicregions  ok=False  源 226 个文件，自己 225 个；缺 1 个
```

### 界面

地图页 → 诊断 → **校验接管**：

```
map/strategicregions
  ⚠ 源 226 个文件，自己 225 个；缺 1 个
  缺：1-Southern England.txt
```

接管成功时也会直接显示校验结果；漏拷的文件名红字列出。

### 顺带修的

`/api/write_targets` 在 POST 分支里用了 `self.q`（GET 参数），取不到 root 导致抛异常、
前端一直显示「失败」。改成从 `body` 取。

### 回归

```
写接口  10/10
```
