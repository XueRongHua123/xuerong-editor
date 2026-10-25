# 雪绒的钢铁雄心编辑器

> 专为 HOI4 社区打造的一款免费开源模组编辑器

本地运行的 HOI4 模组编辑器。Python 服务 + 浏览器界面，打包后是单文件 exe，不需要安装，也不依赖在线服务。

> 本软件由开源模型 **DeepSeek v4.1 flash 1017** 参与开发，是面向《钢铁雄心 IV》模组制作社区的共有财富。  
> 任何人不得将本软件或其修改版用于商业牟利。

![雪绒](mascot_card.png)

## 能做什么

- **国策树**：可视化编辑、拖拽、前置/互斥连线、效果编辑、批量操作、自动布局、保存差异预览
- **国家精神**：名称/描述（中/日/英）、modifier 表格、图标、allowed/trigger、新建/删除
- **装备**：属性表单、图标、archetype、upgrades、module_slots、模块解析
- **装备设计器**：按底盘槽位选模块，实时合计属性，生成 `create_equipment_variant` 脚本
- **科技**：编辑/树视图、按 folder 真实坐标布局、拖线建前置、搜索高亮、新建/删除
- **事件**：新建/删除/复制、选项表单、trigger/immediate/picture
- **原版参考**：只读加载游戏目录，禁止写入；可把原版国策树/科技/精神/装备/事件复制到自己的模组
- **多模组**：本体 + 子模组叠加，检测 `replace_path` 冲突
- **校验与修复**：缺本地化、悬空前置、事件 namespace、花括号不平衡检测与一键修复
- **备份与撤销**：文件级备份历史、Ctrl+Z / Ctrl+Y
- **AI**：雪绒悬浮窗，支持 OpenAI / DeepSeek / Anthropic / Gemini / Ollama / OpenAI 兼容接口
- **三语界面**：中文 / English / 日本語
- **双主题**：雪夜（低对比暗色）/ 纸页（暖白浅色）/ 跟随系统

## 下载

到 [Releases](../../releases) 下载最新的 `雪绒的钢铁雄心编辑器.exe`，双击运行。

首次打开先选择 mod 文件夹：认准里面有 `descriptor.mod` 的那一层。

## 从源码运行

```bash
pip install -r requirements.txt
python focus_editor.py --mod "你的mod目录"
```

不带 `--mod` 会先打开页面，再在页面里选择 mod。

游戏目录默认自动探测常见 Steam 路径，也可以用 `--game` 指定：

```bash
python focus_editor.py --game "E:\SteamLibrary\steamapps\common\Hearts of Iron IV"
```

## 打包

Windows：

```powershell
.\build.ps1
```

产物在 `dist/`。

## AI 配置

AI 的 API Key 只保存在本机 `ai_config.json`，不会上传。该文件已被 `.gitignore` 排除，不要提交。

## 目录

```text
focus_editor.py           服务端
focus_editor_index.html   前端界面
editor_i18n.py            三语文本
mascot/                   雪绒立绘与图标
docs/                     三语教程
tools/                    检查与冒烟测试脚本
```

## 隐私与安全

- 所有文件读写都在本机完成，不上传任何 mod 文件；
- 游戏目录和原版参考层是只读的，保存请求会被拒绝；
- 修改前会生成 `.bak` 和快照。

## 免责声明

本项目是非官方社区工具，与 Paradox Interactive 无关，不包含《Hearts of Iron IV》游戏本体或任何模组内容。使用本工具修改的模组版权归各自作者所有。

雪绒形象与立绘版权归本项目作者所有，未经许可请勿用于商业用途。

## 特别鸣谢

- 梁武峰
- 大肥鱼
- 雪绒

## 开发说明

- 本软件由开源模型 **DeepSeek v4.1 flash 1017** 参与开发；
- 专注于《钢铁雄心 IV》模组制作，国策、精神、装备、科技、事件等编辑能力都围绕模组工作流设计；
- 属于 HOI4 模组社区的共有财富，源代码公开，欢迎共同维护；
- **禁止任何形式的商业牟利**：不得出售、付费墙、广告植入、捆绑付费服务，或把本软件功能作为收费服务的一部分。

## 许可

[雪绒社区非商业许可 1.0](LICENSE)

允许免费使用、修改、分发和非商业再发布；禁止商业牟利。  
因为限制商业使用，这不是 OSI 定义下的“开源许可”，而是“源代码公开的非商业许可”。

雪绒形象与立绘仅可用于本软件及其非商业衍生作品，未经作者书面许可不得用于商业项目。
