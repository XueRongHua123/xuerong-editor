// 01-state：全局状态（P4：原有 13 行 + 从内联脚本搬来的 53 个顶层 let/const）
// 原来这些声明散在 11,328 行内联脚本的各处；现在集中到这里。
// 只声明、不求值。多个普通 <script> 共享同一个 global lexical environment，
// 所以它们仍是 let/const 互见，没有改成 var。声明整体提前 = TDZ 只会变短，不会变长。

let NODE_W = 136, NODE_H = 58, SCALE = 110;
let DATA = null, current = 0, selId = null, editMode = false;
let dirty = new Map();
let view = {x:0, y:0, k:1};
let _lastFitTree = null, _viewReady = false;
let linkMode = null, linkSrc = null;
const svg = document.getElementById('svg');
const vp = document.getElementById('viewport');
const panel = document.getElementById('panel');
const treeList = document.getElementById('treeList');
const statusEl = document.getElementById('status');


/* ---------- v1.24.1 常驻引导条（画布顶部） ----------
   只回答「走到哪了」，具体怎么做还是看左下角 #guideBox（两套不重复）。
   四步的判定全部复用 gbState()，各步独立判断——不要求「前一步做完」才点亮下一步，
   因为熟手可能直接点节点，硬卡顺序只会让人烦。 */
const STEP_LABELS = ['加载 mod', '选一棵树', '改个节点', '保存'];

const STEP_DESCS = [
  '点左上「＋ 添加 mod」，选里面有 descriptor.mod 的那一层（不是它的上一级）。',
  '在左侧「国策树」列表里点一棵，画布上会显示它的节点。',
  '点画布上任意节点，右侧属性面板能改名字、成本、前置、图标。',
  '改完点顶部「💾 保存」或按 Ctrl+S。'
];

let treePicked = false;

   // ② 用户主动点过树列表（只看「有没有树」会把 ② 直接判成完成）
let nodePicked = false;

   // ③ 点过节点。必须粘住：loadData 会把 selId 清空，
                          //    保存完不算「没改过」，不然刚存完又跳回「改个节点」
let savedOnce  = false;


const FLOWS = {
  edit: {
    label: '做一个能进游戏的 submod',
    steps: [
      {t: '加载本体 mod',
       d: '点左上「＋ 添加 mod」，选你那个大 mod 的目录——认准里面有 descriptor.mod 的那一层，不是它的上一级。选完等进度条走完。',
       ok: s => s.roots.length > 0,
       btn: {txt: '去添加本体', act: 'add'}},
      {t: '准备你自己的 submod 目录',
       d: '已经有了就直接「添加 mod」选它，没有才「新建模组」现建一个（文件夹名英文小写，⚠️ 把「创建示例国策树」的勾去掉）。两种都算过——左边「数据源」显示 2 就对了。',
       ok: s => s.roots.length >= 2,
       btns: [{txt: '用已有的', act: 'add'}, {txt: '新建一个', act: 'new'}]},
      {t: '看看要改的目录归谁管',
       d: '点左侧「🩺 诊断」，翻到「replace 断链」那一项。本体如果 replace 了某个目录，你直接往里写是不生效的——得先点「接管该目录」把它整份复制到你自己的 mod 里。',
       ok: s => s.trees.length > 0},
      {t: '选一棵国策树',
       d: '左侧「国策树」列表里点一行，画布上就出来了。列表右侧标着来源，认准是本体那一层的。',
       ok: s => !!s.tree},
      {t: '点画布上的节点，改点东西',
       d: '点任意一个节点，右侧弹出属性面板：名字、图标、前置、成本、效果都能改。改完节点会变成高亮，顶部「未保存」计数会加一。',
       ok: s => !!s.selId},
      {t: '加一个新节点（可选）',
       d: '顶部「新建节点」，然后在画布空白处点一下。填 id（英文，别和现有的重名）、名称、图标、成本。做完连线：点「加前置」，依次点两个节点。',
       ok: s => s.nFocus > 0 && s.selId},
      {t: '点「保存全部」写进文件',
       d: '顶部那个紫色的「💾 保存全部」。改动直接写进你自己的 mod 目录，本体一个字都不动。写完顶部「未保存」要变成 0 才算进去。',
       ok: s => s.dirty === 0},
      {t: '补中文名字和描述',
       d: '打开「本地化」面板，会列出所有缺名字的节点。逐条填中文名和描述，否则游戏里显示的是裸 key。',
       ok: s => s.dirty === 0 && !!s.tree},
      {t: '跑一遍体检与诊断',
       d: '点「🩺 体检」看脚本/引用错误，再点「🩺 诊断」处理 replace 断链与缺失引用，直到没有严重 error。',
       ok: s => false,
       btns: [{txt: '🩺 打开诊断', act: 'diag'}]},
      {t: '一键进游戏检查与打包发布',
       d: '先确认游戏目录已设置，点「🎮 进游戏检查」自动拉起 HOI4 核对 error.log 差分；确认无误后点「📦 打包发布」直接输出工坊就绪目录。',
       ok: s => false,
       btns: [{txt: '📁 设置游戏目录', act: 'game_dir'}, {txt: '🎮 进游戏检查', act: 'game_verify'}, {txt: '📦 打包发布', act: 'publish'}]}
    ]
  },
  new: {
    label: '做一个全新 mod',
    steps: [
      {t: '新建模组',
       d: '填文件夹名和显示名称。空目录起步，不用先有 mod。',
       ok: s => s.roots.length > 0,
       btn: {txt: '去新建', act: 'new'}},
      {t: '留一棵默认国策树',
       d: '新建时勾上「创建示例国策树」并填 TAG。没有 default = yes 的树，进游戏会直接崩。',
       ok: s => s.trees.length > 0},
      {t: '在树上加节点',
       d: '左侧选那棵树，画布空白处右键或顶部「新建节点」。',
       ok: s => !!s.tree && s.tree.focuses && s.tree.focuses.length > 0},
      {t: '补上精神、科技、事件',
       d: '侧栏各自的面板，加完记得保存。',
       ok: s => false}
    ]
  },
  world: {
    label: '创造一个新世界',
    steps: [
      {t: '生成一套新世界',
       d: '填输出目录和 TAG，会连同地图、州、国家、部队、国策一起生成。',
       ok: s => s.roots.length > 0,
       btn: {txt: '去生成', act: 'world'}},
      {t: '这一步现在进不去游戏',
       d: '地图文件本身合规、游戏能读到省份，但点「开始」会崩在 PHYSFS。正在修。',
       ok: s => false}
    ]
  }
};

let designerSel = {};

let designerPicker = '';

let designerArch = '';

let designerTarget = '';

let iconSource = 'focus';

let iconPickTarget = null;

let iconCache = {};

let equipSel = null;

/* v1.24.1 列表行：id 等宽 / 名字占满 / 来源标签贴右。
   来源是「这个文件在哪一层」，不是「当前加载的 mod 叫什么」——后端已经按层填好。 */
/* v1.24.2 接管提示前移：打开编辑器那一刻就问后端「这条会写到哪」。
   缓存按 root|file|layer，同一文件反复打开不打后端。 */
const _srcCache = new Map();

let techSel = null;

let eventSel = null;

let eventOptionBlocks = [];

let ttView = {x:0, y:0, k:1}, ttFolder = '', ttDrag = null;

/* ---------- v0.67 脚本检查面板 ---------- */
let SCRIPT_DATA = null;



/* ---------- v0.61 AI 面板与悬浮球 ---------- */
const AI_TEMPLATES = {
  effect: '帮我写一段 HOI4 国策完成效果（completion_reward）：加 50 政治点、10% 稳定度，并解锁一个名为 my_new_idea 的国家精神。只返回效果脚本。',
  translate: '把下面这段内容翻译成中日英三语，格式：中文 / English / 日本語，各一行，不要解释。\n\n',
  check: '检查下面这段 HOI4 脚本有没有语法或逻辑错误（花括号、键名、作用域），指出具体行并给修正版。\n\n',
  error: '下面是 HOI4 的 error.log 片段，帮我判断根因并给出修复步骤，尽量引用具体文件与键名。\n\n',
  event: '帮我写一个 HOI4 事件：命名空间 my_ns，id my_ns.1，触发条件是国家有 my_flag，选项里加 20 政治点。只返回事件脚本。'
};

let AI_HISTORY = [];


/* ---------- v0.60 数据源与加载进度 ---------- */
let loadTimer = null, loadStartedAt = 0, busyTimer = null, progTimer = null;


/* ---------- v1.24.0 数据源：完整加载链 ---------- */
const SRC_REASON = {game:'原版', dep:'依赖', launcher:'启动器', manual:'手动', auto:'自动'};


/* ---------- v0.59 科技树位置编辑 ---------- */
let ttEdit = false, ttOrigin = null, ttDirty = new Map(), ttDragNode = null;

/* ---------- v0.69 AI 流式 ---------- */
let aiAbort = null;

let contentFilter = '';

let fpDir = '', fpSelPath = '', fpParent = '', fpMode = 'mod';


let drag = null;

let multiSel = new Set();

let batchIconMode = false;

let pendingSave = null;

let ideaSel = null;


let pan = null;


let zoomAnchor = 'mouse';

/* ---------- v0.51 指挥台 ---------- */
const CP_CAT_ORDER = ['最近使用','操作','国策树','焦点','国家精神','装备','科技','事件'];

const CP_KEYS = [
  ['Ctrl+K', '命令面板（搜命令 / 焦点 / 内容）'],
  ['Ctrl+S', '保存全部改动'],
  ['Ctrl+Z / Ctrl+Y', '撤销 / 重做'],
  ['Ctrl+点击', '多选节点（批量改花费/图标）'],
  ['F', '适应屏幕'],
  ['Delete', '删除选中节点（编辑模式）'],
  ['H 或 Shift+?', '打开这份快捷键表'],
  ['滚轮 / 空白拖动', '缩放 / 平移画布'],
  ['↑ ↓ / Enter / Esc', '命令面板内选择、执行、关闭']
];

let cpCache = null, cpItems = [], cpIdx = 0;

/* ---------- v0.72 节点密度与窄屏 ---------- */
const NODE_SIZE = {compact: [118, 50, 96], normal: [136, 58, 110], comfy: [156, 66, 126]};



/* ---------- v0.71 地图面板 ---------- */
const MAP = {x: 0, y: 0, k: 0.24, w: 5632, h: 2048, meta: null, ready: false, idCanvas: null, idx: null, centers: null};


// v1.3.1 缺失本地化（参考 CWTools 的 code action）
let LOC_MISS = null;


const MAP_MODE_TEXT = {view: '浏览', state: '改州归属', paint: '涂色（开发中）', pick: '吸管（开发中）'};


let MAP_LAST_PID = null, MAP_LAST_STATE = null;


/* ---------- v0.70 命令面板最近使用 ---------- */
const CP_RECENT_KEY = 'fe_cmd_recent';


/* ---------- v0.55 国家中心与项目体检 ---------- */
let COUNTRY_DATA = null, countrySel = null;

/* ---------- v0.57 州 / 地块 ---------- */
let STATE_DATA = null, stateSel = null;


/* ---------- v1.23.48 开局建筑 / 战略资源（面板） ---------- */
// 预设：点一下整套填进去，再手动微调。数值是给人用的起点，不是原版规则。
const BLD_PRESETS = {
  industrial: {label:'工业中心', buildings:{infrastructure:60, industrial_complex:8, arms_factory:4}},
  farm:       {label:'农业州',   buildings:{infrastructure:40, industrial_complex:2}},
  port:       {label:'军港',     buildings:{infrastructure:50, industrial_complex:3, naval_base:8, dockyard:4, anti_air_building:2}},
  airbase:    {label:'空军基地', buildings:{infrastructure:50, industrial_complex:3, air_base:8, radar_station:2}},
  resource:   {label:'资源产地', buildings:{infrastructure:30, industrial_complex:2}},
  wild:       {label:'荒芜',     buildings:{infrastructure:10}}
};

const SEA_BUILDINGS = ['naval_base', 'dockyard', 'naval_supply_hub'];


/* ---------- v1.23.48 附庸 / 外交 ---------- */
let DIPLO = null;



/* ---------- v0.56 国家历史编辑 ---------- */
let histTag = null;


/* ---------- 项目体检 ---------- */
let LINT_DATA = null;


const LINT_KIND_NAMES = {tree:'国策树', country:'国家', state:'州', idea:'国家精神', event:'事件', loc:'本地化'};


const LV_NAME = {error:'错误', warn:'警告', info:'提示'};
