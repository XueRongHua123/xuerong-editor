## 雪绒的钢铁雄心编辑器 v1.20.6

**接管目录**：把父 mod 的某个目录全量拷进自己的 mod，并自动写 `replace_path`。

这是 CNsub 对 CN 做法的自动化——复制、修改、接管。

### 界面

地图页 → 诊断 → **检查写入层**：

```
目录写入目标
  history/states          2989050816   独占  [接管]
  map/strategicregions    2800380626   独占  [接管]
  map/supplyareas         2989050816   可写
  common/ideas            2800380626   独占  [接管]
  common/national_focus   2800380626   独占  [接管]
  common/technologies     2800380626   独占  [接管]
  common/units/equipment  2989050816   独占  [接管]
  ...
```

点「接管」：从当前生效层全量拷贝该目录，并在自己的 `descriptor.mod` 里加 `replace_path`。

### 实测

空 mod 接管 `map/strategicregions`：

```
接管前  写入层 = 2800380626 (replace_path)
接管    已从 2800380626 接管 map/strategicregions：拷贝 226 个文件，并写入 replace_path
接管后  写入层 = _adopt (replace_path)，文件数 226

descriptor.mod
  name="adopt_test"
  replace_path="map/strategicregions"
```

接管后改战略区 1 的范围（43 省 → 42 省）：

```
落点: _adopt/map/strategicregions/1-Southern England.txt
在自己 mod 下: True
在 CN 下: False
```

**改动生效，CN 一个字节没动。**

### 新增接口

```
GET  /api/write_targets     每类资源的真实写入层
POST /api/adopt_dir         {sub, force} 接管某个目录
```

### 安全限制

- 只允许对**链顶 mod**操作，不会碰原版或父 mod
- 自己 mod 里已有该目录时要求二次确认
- 已有的 `replace_path` 不重复写

### 回归

```
写接口  10/10
```
