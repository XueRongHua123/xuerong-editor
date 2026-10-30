## 雪绒的钢铁雄心编辑器 v1.21.0

新增一类编辑能力：**开局部队**（`history/units`）。

### 能做什么

**读**：

```
模板 55 个，部队 1752 支（muvluvCN）
```

- `division_template`：名称、是否锁定、编制（regiments 的 unit/x/y）、支援（support）
- `units` 里的 `division`：名称、所在省号、使用的模板、经验系数、装备系数
- 按省聚合，算出每个省有多少支部队

**写**：

```
POST /api/unit_add     {location, template, name?, exp?, eq?}
POST /api/unit_delete  {location, index}
POST /api/unit_move    {location, index, to}
GET  /api/units        模板 + 部队 + 按省聚合
```

### 安全护栏

`history/units` 常被某一层用 `replace_path` 独占（muvluvCN 就是）。
直接往独占层写就是改坏别人的 mod，所以：

```
未接管时：
  history/units 被 2800380626 的 replace_path 独占，直接写进去会改坏它。
  请先在「诊断 → 目录写入目标」里接管该目录

接管后：
  已从 2800380626 接管 history/units：拷贝 102 个文件
  已在省 6103 布置 1 支 331
```

### 实测

| 操作 | 结果 |
|---|---|
| 加部队 | 6103: 80 → 82 |
| 移动 | 6103 第 1 支 → 9999：6103 剩 80，9999 有 1 |
| 删除 | 9999 第 1 支 → 剩 0 |
| CN 是否被污染 | 否，`zz_units.txt` 只在自己 mod 里 |

### 配合

布置部队前需要：

1. 「诊断 → 检查写入层」看 `history/units` 被谁独占
2. 点「接管」把它拷进自己的 mod
3. 再布置部队

### 还没做

- 地图上的部队叠加图层（可视化标记每省部队数）
- 点省面板里增删改的界面
- `division_template` 本身的编辑（编制/支援的增删）

后端接口已就绪，界面在下一版接。

### 回归

```
写接口  10/10
```
