# 技术参考

开发前先查这里的清单：**有参考就学，没参考再自己想办法**。新采用的方案在代码注释里标 `# ref:` 指向对应条目。

## 使用规则

1. 动手前先扫一遍本文件，看有没有现成的做法。
2. 学来的东西要写清楚**来源 + 借鉴了什么 + 改了什么**，不只写"参考了 X"。
3. 自己解决的方案，做完补一条到这里，写明为什么没有可参考的。
4. 不整段复制别人代码（许可证问题），只学思路和参数。

---

## 地图与省份

### HOI4 Province Editor（ScottyThePilot）

- 链接：https://github.com/ScottyThePilot/hoi4_province_editor
- 类型：桌面地图编辑器（Python + pywebview），本项目的对照基准
- 许可证：未确认（README 未见明确条款，不要复制代码）

**优势**

| 项 | 说明 |
|---|---|
| 图层体系 | 地形 / 省份 / 大洲 / 战略区 / 州 / 边界 / 细化目标 / 铁路 / 河流 / 海峡，每层独立透明度滑块 |
| 地形表现 | 真实地表纹理 + 立体阴影，不是纯色块 |
| 悬停信息 | 省号、RGB 十六进制、类型、沿海标记、面积、大洲名、州名+ID、战略区名+ID、地形 |
| 交互 | Shift+点击加入/移出选择集、整片描边；面板内写明操作语义 |
| 结构 | 右侧 Tab 分页：地图 / 分析 / 细化 / 检查 / 编辑 / 报告 |
| 输出隔离 | 所有改动写 `output/`，不碰源 mod |
| 多 mod | 启动器 playset 顺序叠加 |

**已采用**

- v1.0.6 图层独立透明度、高饱和省色、细边界
- v1.0.7 快捷键、悬停补 RGB/类型/名称
- v1.0.9 播放集编辑器、Shift 多选
- v1.1.0 右侧 Tab（图层 / 编辑 / 细化）
- v1.1.1 输出目录模式
- v1.2.1 地形亮度归一化
- v1.3.0 省份细化

**未采用**

- 矢量化省界：实测它放大 8.6 倍也是锯齿（位图必然），不是矢量，所以不做

---

## 脚本校验与语言服务

### CWTools（tboby）

- 链接：https://marketplace.visualstudio.com/items?itemName=tboby.cwtools-vscode
- 仓库：https://github.com/cwtools/cwtools
- 类型：VS Code 扩展，Paradox 语言服务
- 安装量：14.5 万，4.5 星
- 许可证：MIT

**它的校验器清单**（可从 marketplace 描述确认）

- 本地化键是否已定义
- effects / triggers / modifiers 是否存在
- **scope 上下文是否正确**（这个位置的 scope 能不能用这个 effect）
- scripted effects / triggers 的使用
- weights / AI_chance 等条目格式
- **event_targets 是否先保存后使用**
- **引用的 sprite / graphics 文件是否存在**
- 大量针对性校验

**其他能力**

- 语法错误即时高亮
- 输入时自动补全（带描述）
- 悬停显示：相关本地化、元素文档、当前位置的 scope
- **Code action：为缺失的本地化一键生成 .yml**
- 跳转到定义 / 查找所有引用
- 多 mod workspace（按加载顺序）

**可借鉴到我们这里**

| 项 | 我们的现状 | 借鉴方式 |
|---|---|---|
| 缺失本地化键 → 生成 yml | **v1.3.1 已采用**：检查面板「本地化」页，扫国策/事件/精神三类引用，生成占位到 `zz_xuerong_autogen_l_simp_chinese.yml` | 已实现（占位值=键名；只覆盖三类，装备/科技/GUI 未做） |
| 引用的 gfx/sprite 是否存在 | **v1.3.2 已采用**：检查面板「贴图」页，查引用未定义 + 定义但贴图缺失两类 | 已实现（只认 GFX_ 前缀） |
| 跳转到定义 / 查找引用 | 日志行号跳转还没做 | 日志分析结果点一行跳到对应文件行号 |
| scope 上下文校验 | 无 | 工作量大，暂不做 |
| 规则文件驱动校验 | 检查项是硬编码的 | 长期：把检查规则抽成数据（YAML/JSON），符合通用性原则 |

### HOI4 Mod Utilities（Chaofan）

- 链接：https://marketplace.visualstudio.com/items?itemName=Chaofan.hoi4modutilities
- 类型：VS Code 扩展
- 安装量：7.6 万，4.9 星

**能力**

- 世界地图预览 + 编辑
- **国策树预览**（画成树）
- **事件树预览**（含 `after` 链）
- **科技树预览**
- MIO（军工组织）预览
- **GUI 预览**（`interface/*.gui` 渲染成实际界面）
- `.gfx` 文件预览（sprite 可视化）
- `.dds` / `.tga` 图片预览

**可借鉴到我们这里**

| 项 | 我们的现状 | 借鉴方式 |
|---|---|---|
| 国策树预览 | 有国策树编辑，不确定有没有图形预览 | 若没有，加一个只读预览视图（节点连线 + 图标） |
| 事件树预览 | 有事件编辑，无树形预览 | event 之间靠 `after` / `option` 关联，可画成流程图 |
| GUI 预览 | 完全没有 | 工作量大，优先级低 |
| DDS 图片预览 | 后端已能读 DDS（地形贴图用了） | 界面上加"看图标"功能：点 equipment/idea 显示实际图片 |

已知问题（它自己列的）：世界地图边缘线和色块边界对不齐 —— 我们用 `prov_id.png` 逐像素取省号，没有这个问题。

---

## 官方与社区资料

### HOI4 Modding Tools 目录

- 链接：https://lesmiserablesmod.github.io/hoi4-modding-tools/zh-CN/docs/catalog
- 类型：工具索引站，按用途分类（地图 / 国策树 / 本地化 / GFX / 脚本 / 校验 / 创意工坊 / 通用）
- 用途：找参考工具的第一站

### 游戏自带数据

做地图功能时的第一手参考，比第三方工具更权威：

| 文件 | 用途 |
|---|---|
| `map/default.map` | 地图尺寸、definitions 引用、各种子图路径 |
| `map/definition.csv` | 省号、RGB、类型、沿海、地形 |
| `map/terrain.txt` | `terrain_N = { type, color, texture }` |
| `common/terrain/00_terrain.txt` | 地形类别与 `color = { r g b }` |
| `map/terrain/atlas0.dds` | 8×8 = 64 格、每格 256px 的地形贴图集（DXT5） |
| `map/heightmap.bmp` | 高度图，做山体阴影 |
| `map/railways.txt` | 铁路（块式与行式两种写法） |
| `map/supplyareas/*.txt` | 补给区 |
| `map/strategicregions/*.txt` | 战略区 |

---

## 自己解决的（无外部参考）

| 功能 | 做法 | 为什么没有可参考的 |
|---|---|---|
| BMP 原位编辑 | 解析头 + 按行跨距写 3 字节/像素 | 第三方工具都整图重存，我们为了 33MB 文件不重存 |
| 区块级撤销 | 只备份改动矩形的原像素 | 别人用整文件备份，太占盘 |
| 多 mod playset 叠加 | `--mod` 多次传参 + 顺序叠加，不靠 dependencies | 启动器的 playset 语义，第三方工具只做单 mod |
| 地形索引可信度判断 | `terrain.bmp` 与 `provinces.bmp` 同源才用像素级地形 | 没见别人处理"换了地图没换地形图"的情况 |
| 同步水位生长切分 | 每轮各长一层，到预算停 | 常规是 KMeans（不保连通）或 BFS（不均），见 v1.3.0 的三种对比 |
