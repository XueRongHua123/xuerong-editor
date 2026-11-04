# 版本变更记录

雪绒的钢铁雄心编辑器，按版本从新到旧。

每个版本的完整说明在 `work/qa/release_notes_vXXXXX.md`，
这里只留一句结论，方便查「某一版做了什么」和「某个功能是哪一版加的」。

重跑 `python work/tools/gen_changelog.py` 会按 `qa/release_notes_v*.md` 重新生成；
「未发布」那段是手工维护的，脚本会原样保留。

共 162 个已发布版本，最新 v1.23.45。

## 未发布（开发中）

已写进代码、还没打包推 GitHub 的内容。发版后并进下面那张表。

暂无。


## 已发布

| 版本 | 摘要 |
|---|---|
| [v1.23.45](work/qa/release_notes_v123450.md) | 以前加载一个子 mod，编辑器只跟它 descriptor.mod 里写的 dependencies 走。问题在于 dependencies 不是游戏的加载链——它只是启动器用… |
| [v1.23.44](work/qa/release_notes_v123440.md) | 这三个 bug 是同一族：mapgen 里有一批写法是 arr[labels == 0] = 海底的东西，但我们的海是真省（id 从 n+1 开始），labels 里根本没有 … |
| [v1.23.43](work/qa/release_notes_v123430.md) | common/ 下那批共享国策（common_refugee_tech_sharing、common_adopt_powered_suits、common_experience… |
| [v1.23.42](work/qa/release_notes_v123420.md) | 修复一批「改了不生效」的问题，根因是树被记到了错误的层。 |
| [v1.23.41](work/qa/release_notes_v123410.md) | 修了一个加载链的 bug：先加父 mod 再加子 mod 时，子 mod 依赖的中间层会整层丢失。 |
| [v1.23.40](work/qa/release_notes_v123400.md) | 本次更新集中在第一次用的人怎么上手，以及四个实际使用中撞出来的 bug。 |
| [v1.23.35](work/qa/release_notes_v123350.md) | 前几版一直卡在这一步：world_create 的产物能进主菜单、能选国家、能看到地图和省份划分正确， |
| [v1.23.34](work/qa/release_notes_v123340.md) | 把诊断器报出的 replace 断链做成一键可修。 |
| [v1.23.33](work/qa/release_notes_v123330.md) | 建世界流程打通到产出文件，同时修掉 5 个真实缺陷、补 3 项静态检查。 |
| [v1.23.32](work/qa/release_notes_v123320.md) | 国策树检查做了又撤回，五个检查项误报率稳定在 0.002%。 |
| [v1.23.31](work/qa/release_notes_v123310.md) | 修决议深度 + 接国家精神，误报率降到 0.002%。 |
| [v1.23.30](work/qa/release_notes_v123300.md) | 人物类型块内部字段 + 决议字段检查。 |
| [v1.23.29](work/qa/release_notes_v123290.md) | 人物字段检查，误报率实测 0%。 |
| [v1.23.28](work/qa/release_notes_v123280.md) | 接入 CWTools 的 HOI4 规则，加 schema 字段检查。 |
| [v1.23.27](work/qa/release_notes_v123270.md) | 诊断检查项从 4 个补到 8 个。 |
| [v1.23.26](work/qa/release_notes_v123260.md) | 三件事：原子写入、黄金测试、诊断面板。 |
| [v1.23.25](work/qa/release_notes_v123250.md) | 按 set_oob 定位 OOB 文件，并修两处图标名。 |
| [v1.23.24](work/qa/release_notes_v123240.md) | 补上界面缺的国家参数。 |
| [v1.23.23](work/qa/release_notes_v123230.md) | 部队和模板的两个问题。 |
| [v1.23.22](work/qa/release_notes_v123220.md) | 海军接口加国家参数。 |
| [v1.23.21](work/qa/release_notes_v123210.md) | 人物头像。 |
| [v1.23.20](work/qa/release_notes_v123200.md) | 人物删除时同步清掉 recruit_character。 |
| [v1.23.19](work/qa/release_notes_v123190.md) | 新建人物现在会同时写「招募」。 |
| [v1.23.18](work/qa/release_notes_v123180.md) | 人物类型可以在界面上改了。 |
| [v1.23.17](work/qa/release_notes_v123170.md) | 新建人物不再覆盖原版同名文件。 |
| [v1.23.16](work/qa/release_notes_v123160.md) | 人物、部队、空军现在会写到正确的国家文件里。 |
| [v1.23.15](work/qa/release_notes_v123150.md) | 改单个州不再需要整目录接管。 |
| [v1.23.14](work/qa/release_notes_v123140.md) | 剧本本地化按游戏语言生成。 |
| [v1.23.13](work/qa/release_notes_v123130.md) | 修 bookmark_add 的三个问题。这三个是真机验证暴露出来的：生成的文件格式没错， |
| [v1.23.12](work/qa/release_notes_v123120.md) | 真机验证挖出来的 4 个 bug，全部修复。 |
| [v1.23.11](work/qa/release_notes_v123110.md) | 技术债第 2 项：循环依赖的节点不再叠在一起。 |
| [v1.23.10](work/qa/release_notes_v123100.md) | 技术债第 1 项：撤销备份不再按包围盒存。 |
| [v1.23.9](work/qa/release_notes_v12390.md) | 高程笔刷。地图生成那条线的最后一块（第 16 项）。 |
| [v1.23.8](work/qa/release_notes_v12380.md) | 人物与决议都能新建了。 |
| [v1.23.7](work/qa/release_notes_v12370.md) | 左侧导航加「开局数据与编辑」直达入口。 |
| [v1.23.6](work/qa/release_notes_v12360.md) | 「编辑」tab 加面板索引条。 |
| [v1.23.5](work/qa/release_notes_v12350.md) | 城市区域从 GeoJSON 生成。 |
| [v1.23.4](work/qa/release_notes_v12340.md) | 修好了 terrain_map 来源的河流提取。现在只给一张真实地图图片，河道能被自动识别。 |
| [v1.23.3](work/qa/release_notes_v12330.md) | 河流从 GeoJSON 生成。 |
| [v1.23.2](work/qa/release_notes_v12320.md) | rivers.bmp 与 cities.bmp 的格式修正。 |
| [v1.23.1](work/qa/release_notes_v12310.md) | 地形提示真正写进 terrain.bmp。 |
| [v1.23.0](work/qa/release_notes_v12300.md) | 地图生成加到六种来源，开放给玩家自己选。 |
| [v1.22.1](work/qa/release_notes_v12210.md) | 地图生成的两处实质改进：省大小均衡、战略区按地理位置聚类。 |
| [v1.22.0](work/qa/release_notes_v12200.md) | 一次产出 24 项文件，和原版 map/ 完全对应： |
| [v1.21.19](work/qa/release_notes_v12119.md) | 决议编辑（common/decisions）。 |
| [v1.21.18](work/qa/release_notes_v12118.md) | 人物编辑（common/characters）。第三层第一项。 |
| [v1.21.17](work/qa/release_notes_v12117.md) | 州资源编辑。第二层（开局剧本配置）最后一项。 |
| [v1.21.16](work/qa/release_notes_v12116.md) | 开局剧本（common/bookmarks）。 |
| [v1.21.15](work/qa/release_notes_v12115.md) | 开局已完成国策（complete_national_focus / mark_focus_tree_completed）。 |
| [v1.21.14](work/qa/release_notes_v12114.md) | 开局政治与外交（set_politics / set_popularities / declare_war_on）。 |
| [v1.21.13](work/qa/release_notes_v12113.md) | 开局空军（air_wings）。 |
| [v1.21.12](work/qa/release_notes_v12112.md) | 舰队补齐：加船、加特遣队、改舰船属性。 |
| [v1.21.11](work/qa/release_notes_v12111.md) | 开局舰队（history/units 的 fleet 段）。 |
| [v1.21.10](work/qa/release_notes_v12110.md) | 图标导入，外加清理仓库。 |
| [v1.21.9](work/qa/release_notes_v12190.md) | 国家 TAG 增删（common/country_tags）。 |
| [v1.21.8](work/qa/release_notes_v12180.md) | 国家离岸建筑（add_offsite_building）。 |
| [v1.21.7](work/qa/release_notes_v12170.md) | 国家精神（add_ideas）。 |
| [v1.21.6](work/qa/release_notes_v12160.md) | 科技树预览的四条改进。 |
| [v1.21.5](work/qa/release_notes_v12150.md) | 科技树预览。 |
| [v1.21.4](work/qa/release_notes_v12140.md) | 三件事：模板编辑区挪位、支援连格子重做、国家初始科技。 |
| [v1.21.3](work/qa/release_notes_v12130.md) | 师团模板编辑界面 + 编制格可视化。 |
| [v1.21.2](work/qa/release_notes_v12120.md) | 省面板部队增删改 + division_template 编辑后端。 |
| [v1.21.0](work/qa/release_notes_v12100.md) | 新增一类编辑能力：开局部队（history/units）。 |
| [v1.20.7](work/qa/release_notes_v12070.md) | replace_path 接管后，上级 mod 的同名目录不再被读取。 |
| [v1.20.6](work/qa/release_notes_v12060.md) | 这是 CNsub 对 CN 做法的自动化——复制、修改、接管。 |
| [v1.20.5](work/qa/release_notes_v12050.md) | HOI4 的 replace_path 是独占的：某个 mod 声明后，该目录只从这个 mod 读， |
| [v1.20.4](work/qa/release_notes_v12040.md) | state_save 改 owner 时只改了 history 直接子级： |
| [v1.20.3](work/qa/release_notes_v12030.md) | state_save 用 STATES[sid]["root"] + ["file"] 定位目标文件。 |
| [v1.20.2](work/qa/release_notes_v12020.md) | 做「真实游戏内验证」的第一步：新增游戏可读性校验 qa/check_game_readable.py， |
| [v1.20.1](work/qa/release_notes_v12010.md) | 按上一版整理的技术债清单做验证，查出并修了三个数据层缺陷，写回归从 7/10 到 10/10。 |
| [v1.20.0](work/qa/release_notes_v12000.md) | 三件事一起发：loader 层叠改造、州编辑补全、补给区增删改。 |
| [v1.19.0](work/qa/release_notes_v11900.md) | 两个功能：孤儿 tag 诊断、政治图严格模式。 |
| [v1.18.3](work/qa/release_notes_v11830.md) | 政治图大面积灰色的真正原因找到了——不是无主地块，是国家颜色查不到。 |
| [v1.18.2](work/qa/release_notes_v11820.md) | 政治图两个显示问题的修复。 |
| [v1.18.1](work/qa/release_notes_v11810.md) | 跨 mod 回归跑出来的修复。 |
| [v1.18.0](work/qa/release_notes_v11800.md) | 州细化。用省份细化那套算法，把一个大州拆成几个小州。 |
| [v1.17.0](work/qa/release_notes_v11700.md) | 州视图能改了：直接改归属国、批量增减省。 |
| [v1.16.0](work/qa/release_notes_v11600.md) | AI 助手能记住上下文了。 |
| [v1.15.0](work/qa/release_notes_v11500.md) | 装备变体能直接改了。新增「装备」页，找装备、看属性、改数值、删变体。 |
| [v1.14.0](work/qa/release_notes_v11400.md) | 河流能看了，海峡能改了。 |
| [v1.13.0](work/qa/release_notes_v11300.md) | 战略区能建了：列表、新建、改范围、删除。 |
| [v1.12.1](work/qa/release_notes_v11210.md) | 地形编辑补齐三项：批量改、按类型全改、画笔。 |
| [v1.12.0](work/qa/release_notes_v11200.md) | 地形能改了。选中一个省，下拉选新地形，点应用——definition.csv 和 terrain.bmp 一起写，图层自动重建。 |
| [v1.11.0](work/qa/release_notes_v11100.md) | 铁路这一块做完整了：读取、可视化、改等级、增删省、补给区。 |
| [v1.10.0](work/qa/release_notes_v11000.md) | 铁路能看了。新增「铁路」预设，地图上用折线画出全部铁路，断连的标红。 |
| [v1.9.6](work/qa/release_notes_v1960.md) | 还完最后两项技术债：日志行号跳转、国家字段补全。 |
| [v1.9.5](work/qa/release_notes_v1950.md) | 继续还技术债，两项。 |
| [v1.9.4](work/qa/release_notes_v1940.md) | 两件事：州视图下双击能下钻到省；撤销备份从 31.9 MB 降到 1.3 KB。 |
| [v1.9.3](work/qa/release_notes_v1930.md) | 预设现在会绑定左键点选的对象——看什么视图，点出来就是什么。 |
| [v1.9.2](work/qa/release_notes_v1920.md) | 图层面板加了预设，一键切换常用视图组合。 |
| [v1.9.1](work/qa/release_notes_v1910.md) | 细化不再留下孤儿地块：新省自动加入原州，细化前会提示风险。 |
| [v1.9.0](work/qa/release_notes_v1900.md) | 省界改成 canvas 矢量描边，800% 下是 1px 细线，不再是 8px 粗的模糊带。 |
| [v1.8.1](work/qa/release_notes_v1810.md) | 三件事：缩放上限、事件树并入事件栏目、事件文本可直接改。 |
| [v1.8.0](work/qa/release_notes_v1800.md) | 细化现在能看形状了，而且把切分算法抽成了一套通用逻辑。 |
| [v1.7.1](work/qa/release_notes_v1710.md) | 放大地图不再糊。 |
| [v1.7.0](work/qa/release_notes_v1700.md) | 事件树现在能就地改 title / desc / option，新建命名空间时会自动生成本地化。 |
| [v1.6.1](work/qa/release_notes_v1610.md) | 修预览的四个问题，其中两个是同一个根因。 |
| [v1.6.0](work/qa/release_notes_v1600.md) | 国策预览有了缩放拖动，事件树从「预览」升级成「编辑」，能新建和删除命名空间。 |
| [v1.5.1](work/qa/release_notes_v1510.md) | 移除编辑器工具栏里那个旧的「🎮 预览」按钮。 |
| [v1.5.0](work/qa/release_notes_v1500.md) | 参考 [HOI4 Mod Utilities](https://marketplace.visualstudio.com/items?itemName=Chaofan.hoi4… |
| [v1.4.1](work/qa/release_notes_v1410.md) | 把国策树预览和编辑器打通：预览里点一个节点，直接在编辑器里定位到它。 |
| [v1.4.0](work/qa/release_notes_v1400.md) | 国策树图形预览：把一棵树画成节点图，节点带真实图标、位置按 x/y 网格排、前置与互斥用连线表示。 |
| [v1.3.2](work/qa/release_notes_v1320.md) | 检查面板新增「贴图」页：查脚本引用的 sprite 有没有 gfx 定义，以及定义的贴图文件是否真的存在。 |
| [v1.3.1](work/qa/release_notes_v1310.md) | 检查面板新增「本地化」页：找出脚本里引用、但没有任何 yml 定义过的本地化键，可一键生成占位。 |
| [v1.3.0](work/qa/release_notes_v1300.md) | 右侧新增「细化」页： |
| [v1.2.2](work/qa/release_notes_v1220.md) | 地形层叠上游戏自己的地表贴图（map/terrain/atlas0.dds）。 |
| [v1.2.1](work/qa/release_notes_v1210.md) | 修两个把地形图压暗/弄错的问题，两个都是所有 mod 都受影响的真 bug。 |
| [v1.2.0](work/qa/release_notes_v1120.md) | 地形层换成游戏配色 + 高度图山体阴影，全过程用 Pillow 的 C 操作，0.44 秒完成。 |
| [v1.1.1](work/qa/release_notes_v1110.md) | 第三批第二项：输出目录模式。改动写到独立目录，源 mod 一个字节不动。 |
| [v1.1.0](work/qa/release_notes_v1100.md) | 第三批第一项：面板结构整理。把浮在画布上的图层面板收进右侧栏，用 Tab 切换。 |
| [v1.0.9](work/qa/release_notes_v1090.md) | 三件事：每层独立透明度、播放集编辑器、Shift 多选。 |
| [v1.0.8](work/qa/release_notes_v1080.md) | 编辑器只认单个 mod：--mod 传一个，然后沿 descriptor.mod 的 dependencies 往上找父 mod。 |
| [v1.0.7](work/qa/release_notes_v1070.md) | 交互第二批：修点穿 bug + 快捷键 + 悬停信息 + 状态栏。 |
| [v1.0.6](work/qa/release_notes_v1060.md) | 观感改进第一批：配色、边界、地形纹理、缩放渲染。 |
| [v1.0.5](work/qa/release_notes_v1050.md) | 一键修复新增第二项：十字交叉像素。 |
| [v1.0.4](work/qa/release_notes_v1040.md) | 这类省常见于：删过省份没清 csv、合并后残留、从别的 mod 抄了 csv 但没抄地图。 |
| [v1.0.3](work/qa/release_notes_v1030.md) | 我先做了「退出 → 替换 exe → 重启」的版本，实测下来问题很多： |
| [v1.0.2](work/qa/release_notes_v1020.md) | 地图检查面板顶部新增两个按钮：检查 / 省份排行。 |
| [v1.0.1](work/qa/release_notes_v1010.md) | 2. 顶栏右侧有个版本胶囊：v1.0.1。有新版本时变成 v1.0.1 → v1.0.2 并高亮 |
| [v1.0.0](work/qa/release_notes_v1000.md) | 涂色面板下方「新建州」： |
| [v0.99.0](work/qa/release_notes_v0990.md) | 用 33 MB 的 provinces.bmp 副本完整走了一遍前端流程： |
| [v0.97.0](work/qa/release_notes_v0970.md) | 体检新增科技前置引用闭环检查。 |
| [v0.96.0](work/qa/release_notes_v0960.md) | 体检新增编码规范检查（BOM）。 |
| [v0.95.0](work/qa/release_notes_v0950.md) | 2. 右侧填「目标省号」（涂成哪个省） |
| [v0.94.0](work/qa/release_notes_v0940.md) | 地图编辑的地基：原位写 BMP + 区块撤销。这是涂色改省界的前置，本版只做引擎，界面下一版接。 |
| [v0.93.0](work/qa/release_notes_v0930.md) | 第一批地基：地图定义一致性校验 + 州/国家接入叠加链。 |
| [v0.92.0](work/qa/release_notes_v0920.md) | 把 mod 叠加链显示出来——之前它只在后台跑，界面上无处可查。 |
| [v0.91.0](work/qa/release_notes_v0910.md) | 支持 submod 的 submod：子 mod 没有地图时，自动沿依赖链用父 mod 的地图。 |
| [v0.90.0](work/qa/release_notes_v0900.md) | 通用性审计：确认编辑器不依赖任何特定 mod，并把"多 mod 冒烟"变成例行检查。 |
| [v0.89.0](work/qa/release_notes_v0890.md) | 修的是编辑器自身的问题，不是 mod 的。 |
| [v0.88.0](work/qa/release_notes_v0880.md) | 日志检查加了文件归属判定：分清哪些报错是你的 mod 的，哪些不是。 |
| [v0.87.0](work/qa/release_notes_v0870.md) | 日志检查加一层保险：每次体检自动快照 error.log。 |
| [v0.86.0](work/qa/release_notes_v0860.md) | 接入游戏日志检查：跑完一局游戏，编辑器直接告诉你日志里在报什么。 |
| [v0.85.0](work/qa/release_notes_v0850.md) | 地图层 3 的前置：地形层、大洲层、1:1、地图检查。 |
| [v0.84.0](work/qa/release_notes_v0840.md) | 地图界面的可读性修复：图层面板不再是"看不清的黑框"。 |
| [v0.83.0](work/qa/release_notes_v0830.md) | 视觉层次：让界面上的元素分得出主次，而不是平铺。 |
| [v0.82.0](work/qa/release_notes_v0820.md) | 修掉一个影响所有可拖拽区域的交互问题，并把结论写成了设计纲要。 |
| [v0.81.0](work/qa/release_notes_v0810.md) | 地图界面重构，为后续的涂色编辑功能准备好结构。 |
| [v0.80.0](work/qa/release_notes_v0800.md) | 地图层 2 第三项：战略区图层。 |
| [v0.79.0](work/qa/release_notes_v0790.md) | 政治视图：没有颜色定义的国家不再显示为统一灰色。 |
| [v0.78.0](work/qa/release_notes_v0780.md) | 跨 mod 兼容性修复：政治视图在部分第三方 mod 上整图无配色的情况。 |
| [v0.77.0](work/qa/release_notes_v0770.md) | 修正州归属解析：history 里带日期块的 owner 现在按开局日期生效。 |
| [v0.76.0](work/qa/release_notes_v0760.md) | 地图层 2 第二项：在地图上改省归属。 |
| [v0.75.0](work/qa/release_notes_v0750.md) | 地图层 2 第一项：政治视图——按国家给地图上色。 |
| [v0.74.0](work/qa/release_notes_v0740.md) | 地图面板加了「清理地图缓存」。 |
| [v0.73.1](work/qa/release_notes_v0731.md) | 包体瘦身：exe 24.2 MB → 20.1 MB，zip 23.9 MB → 19.8 MB。 |
| [v0.73.0](work/qa/release_notes_v0730.md) | 地图可以选来源了：不同 mod、原版，各看各的。 |
| [v0.72.0](work/qa/release_notes_v0720.md) | 节点密度可调、窄屏工具栏收拢，三语教程补到最新。 |
| [v0.71.0](work/qa/release_notes_v0710.md) | 地图来了：只看不改的省 / 州地图预览，和州面板联动。 |
| [v0.70.0](work/qa/release_notes_v0700.md) | 命令面板加入「最近使用」。 |
| [v0.69.0](work/qa/release_notes_v0690.md) | AI 面板支持流式输出。 |
| [v0.68.0](work/qa/release_notes_v0680.md) | 历史编辑器里的「开局装备变体」从只读变成可增可删。 |
| [v0.67.0](work/qa/release_notes_v0670.md) | 新增「脚本检查」面板：scripted trigger / effect 的定义清单 + 全项目引用计数。 |
| [v0.66.0](work/qa/release_notes_v0660.md) | 项目体检新增「全局 flag 配对」检查。 |
| [v0.65.0](work/qa/release_notes_v0650.md) | 小版本：州面板的省份列表支持「显示全部」。 |
| [v0.64.0](work/qa/release_notes_v0640.md) | 历史编辑器新增「开局装备变体」只读区块。 |
| [v0.63.0](work/qa/release_notes_v0630.md) | 修三处交互问题，都是截图里遇到的。 |
| [v0.62.0](work/qa/release_notes_v0620.md) | 悬浮球、看板娘、AI 面板、列表弹窗一起改。 |
| [v0.61.0](work/qa/release_notes_v0610.md) | AI 面板和雪绒悬浮球一起迭代。 |
| [v0.60.0](work/qa/release_notes_v0600.md) | 把"数据源"从国策树里搬出来，放到侧栏最上面，并给所有需要读盘的操作配了进度。 |
| [v0.59.1](work/qa/release_notes_v0591.md) | 修正科技树位置写回对 @宏 的处理。 |
| [v0.59.0](work/qa/release_notes_v0590.md) | 这一版把"国策 → 国家 → 州 → 省份 → 科技"这条链补齐了，全部是本地读写，不联任何在线服务。 |
