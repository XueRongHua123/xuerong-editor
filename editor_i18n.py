# -*- coding: utf-8 -*-
"""国际化文案（中文/English/日本語）与帮助页生成"""
import html as _html

LANGS = ("zh", "en", "ja")
LANG_NAMES = {"zh": "中文", "en": "English", "ja": "日本語"}

MASCOT = {
    "name": "雪绒",
    "greeting": {
        "zh": "指挥官，欢迎回来～今天也要改国策吗？",
        "en": "Welcome back, commander! Ready to edit some focus trees?",
        "ja": "おかえりなさい、指揮官。今日も国家方針を編集しますか？",
    },
    "tips": {
        "zh": [
            "cost 的单位是周哦：cost = 1 就是 7 天。",
            "改动前会自动生成 .bak，放心改。",
            "想加国家精神？在快捷效果里填 id 就行。",
            "导出覆盖包只会包含改动过的文件。",
            "每个国家只能有一棵 focus_tree 哦。",
            "点节点才会打开编辑面板，拖节点要先开编辑模式。",
            "保存精神前会检查花括号，不配对不会写回。",
            "改错了别慌，Ctrl+Z 可以撤销上一次保存。",
            "点保存会先弹 diff 预览，看清楚再确认。",
            "Ctrl+点击节点可以多选，然后批量改花费或图标。",
            "「自动排版」会按前置关系把树排整齐。",
            "「🔎 本地化」能列出还没写名字的焦点。",
            "「⚙ 树设置」可以改这棵树归哪些国家使用。",
            "想从零做 mod？「🆕 新建模组」会直接生成可用骨架。",
        ],
        "en": [
            "cost is measured in weeks: cost = 1 means 7 days.",
            "A .bak backup is created before every change.",
            "To add a national spirit, just type its id in Quick Effects.",
            "Export Patch only packs files you actually changed.",
            "Each country can have only one focus_tree.",
            "Click a node to open the panel; enable Edit Mode before dragging.",
            "Spirit saves validate braces first — unbalanced input is rejected.",
            "Made a mistake? Ctrl+Z undoes the last save.",
            "Saving shows a diff preview first — review before confirming.",
            "Ctrl+click nodes to multi-select, then set cost or icon in bulk.",
            "Auto layout arranges the tree by prerequisite levels.",
            "The 🔎 Localization check lists focuses that still have no name.",
            "⚙ Tree Settings controls which countries use this tree.",
            "Starting from scratch? 🆕 New Mod generates a working skeleton.",
        ],
        "ja": [
            "cost の単位は週です。cost = 1 は 7 日。",
            "変更前に .bak が自動作成されます。",
            "国家精神はクイック効果に ID を入れるだけ。",
            "パッチ出力は変更したファイルだけを含みます。",
            "1 国につき focus_tree は 1 つだけです。",
            "ノードをクリックで編集パネル。ドラッグは編集モードを ON に。",
            "精神の保存前に括弧を検査し、不一致は書き込みません。",
            "間違えたら Ctrl+Z で直前の保存を元に戻せます。",
            "保存時に diff プレビューが出るので、確認してから保存できます。",
            "Ctrl+クリックで複数選択し、コストやアイコンを一括変更できます。",
            "「自動整列」は前提関係に沿ってツリーを整理します。",
            "「🔎 ローカライズ」で名前が未設定のノードを一覧できます。",
            "「⚙ ツリー設定」でこのツリーを使う国を変更できます。",
            "ゼロから mod を作るなら「🆕 新しい mod」で雛形を生成できます。",
        ],
    },
}

# 中文原文 -> 各语言
UI = {
    "国策树编辑器 - muvluvCN": {"en": "Focus Tree Editor - muvluvCN", "ja": "国家方針ツリーエディタ - muvluvCN"},
    "雪绒的钢铁雄心编辑器 - muvluvCN": {"en": "Xuerong's Hearts of Iron Editor - muvluvCN", "ja": "雪絨の鋼鉄の雄心エディタ - muvluvCN"},
    "欢迎使用雪绒的钢铁雄心编辑器": {"en": "Welcome to Xuerong's Hearts of Iron Editor", "ja": "雪絨の鋼鉄の雄心エディタへようこそ"},
    "专为 HOI4 社区打造的一款免费开源模组编辑器": {"en": "A free and open-source mod editor built for the HOI4 community", "ja": "HOI4コミュニティのための無料オープンソースMODエディタ"},
    "由开源模型 DeepSeek v4.1 flash 1017 开发 · 社区共有 · 禁止商业牟利": {
        "en": "Developed with the open-source model DeepSeek v4.1 flash 1017 · Community-owned · Non-commercial use only",
        "ja": "オープンソースモデル DeepSeek v4.1 flash 1017 による開発 · コミュニティ共有 · 商業利用禁止"},
    "特别鸣谢": {"en": "Special Thanks", "ja": "特別協力"},
    "能改国策、国家精神、装备、科技、事件；装备设计器、原版参考、多模组叠加、AI 辅助和自动校验都在同一个窗口里。": {
        "en": "Edit focus trees, national spirits, equipment, technology and events. The equipment designer, vanilla reference, multi-mod stacking, AI assistance and validation all live in one window.",
        "ja": "国家方針・国家精神・装備・技術・イベントを編集。装備デザイナー、バニラ参照、複数MODの重ね掛け、AI補助、自動検証を同じ画面で使えます。"},
    "选择 mod 文件夹时认准这一层：里面有 descriptor.mod（旁边通常还有 common）。原版目录是只读的，不会写坏游戏。": {
        "en": "Pick the mod folder that contains descriptor.mod (usually next to a common folder). The game directory is read-only and will not be modified.",
        "ja": "descriptor.mod があるフォルダを選択してください（通常は common と同じ階層）。ゲーム本体は読み取り専用で、書き換えません。"},
    "本体 + 子模组：先加载本体，再加载子模组；后加载的会覆盖同名内容。": {
        "en": "Base mod + sub-mod: load the base first, then the sub-mod; later loads override same-named content.",
        "ja": "本体＋サブMOD：本体を先に、サブMODを後に読み込みます。後に読み込んだ方が同名内容を上書きします。"},
    "跟随系统": {"en": "Follow system", "ja": "システムに合わせる"},
    "雪夜": {"en": "Snow Night", "ja": "雪夜"},
    "纸页": {"en": "Paper", "ja": "紙面"},
    "外观主题": {"en": "Theme", "ja": "テーマ"},
    "界面大小": {"en": "UI size", "ja": "画面サイズ"},
    "标准": {"en": "Normal", "ja": "標準"},
    "大": {"en": "Large", "ja": "大"},
    "小": {"en": "Small", "ja": "小"},
    "雪绒的钢铁雄心编辑器 使用教程": {"en": "Xuerong's Hearts of Iron Editor Tutorial", "ja": "雪絨の鋼鉄の雄心エディタ チュートリアル"},
    "国策树": {"en": "Focus Trees", "ja": "国家方針"},
    "搜索焦点 id / 名称...": {"en": "Search focus id / name...", "ja": "国家方針 ID / 名前を検索..."},
    "统计": {"en": "Statistics", "ja": "統計"},
    "拖动节点 = 改位置（需开启编辑模式）": {"en": "Drag node = move (enable Edit Mode)", "ja": "ノードをドラッグ = 移動（編集モードが必要）"},
    "点节点 = 打开编辑面板": {"en": "Click node = open editor panel", "ja": "ノードをクリック = 編集パネルを開く"},
    "滚轮缩放 · 空白处拖动平移": {"en": "Wheel zoom · drag empty space to pan", "ja": "ホイールでズーム・空白をドラッグで移動"},
    "适应屏幕": {"en": "Fit", "ja": "画面に合わせる"},
    "＋": {"en": "+", "ja": "＋"},
    "－": {"en": "-", "ja": "－"},
    "✏️ 编辑模式": {"en": "✏️ Edit Mode", "ja": "✏️ 編集モード"},
    "🔗 加前置": {"en": "🔗 Add Prereq", "ja": "🔗 前提を追加"},
    "🔗 加互斥": {"en": "🔗 Add Mutex", "ja": "🔗 排他を追加"},
    "➕ 新建节点": {"en": "➕ New Focus", "ja": "➕ 新規ノード"},
    "🌳 新建树": {"en": "🌳 New Tree", "ja": "🌳 新規ツリー"},
    "🗑 删除树": {"en": "🗑 Delete Tree", "ja": "🗑 ツリー削除"},
    "💾 保存全部": {"en": "💾 Save All", "ja": "💾 すべて保存"},
    "📦 导出覆盖包": {"en": "📦 Export Patch", "ja": "📦 パッチ出力"},
    "显示互斥": {"en": "Show Mutex", "ja": "排他を表示"},
    "❓ 教程": {"en": "❓ Guide", "ja": "❓ ガイド"},
    "ID：": {"en": "ID: ", "ja": "ID："},
    "文件：": {"en": "File: ", "ja": "ファイル："},
    "原始坐标（相对定位时为偏移）": {"en": "Raw coords (offset if relative)", "ja": "元の座標（相対指定時はオフセット）"},
    "前置：每组 OR，组内 + 表示 AND": {"en": "Prereq: groups = OR, + inside = AND", "ja": "前提：グループは OR、+ は AND"},
    "互斥（逗号分隔）": {"en": "Mutex (comma separated)", "ja": "排他（カンマ区切り）"},
    "完成效果 completion_reward（脚本原文）": {"en": "Completion reward (raw script)", "ja": "完了効果 completion_reward（スクリプト原文）"},
    "选择效果 select_effect（可留空）": {"en": "Select effect (optional)", "ja": "選択効果 select_effect（空欄可）"},
    "快捷效果（填数字，0/空 = 不添加）": {"en": "Quick effects (numbers; 0/empty = skip)", "ja": "クイック効果（数値入力。0/空欄は追加なし）"},
    "政治点": {"en": "Political power", "ja": "政治ポイント"},
    "稳定度(%)": {"en": "Stability (%)", "ja": "安定度(%)"},
    "战争支持(%)": {"en": "War support (%)", "ja": "戦争支持(%)"},
    "人力(千)": {"en": "Manpower (thousand)", "ja": "人的資源(千)"},
    "指挥点": {"en": "Command power", "ja": "指揮ポイント"},
    "陆军经验": {"en": "Army XP", "ja": "陸軍経験値"},
    "空军经验": {"en": "Air XP", "ja": "空軍経験値"},
    "海军经验": {"en": "Navy XP", "ja": "海軍経験値"},
    "保存快捷效果": {"en": "Save Quick Effects", "ja": "クイック効果を保存"},
    "清空常见效果": {"en": "Clear Common Effects", "ja": "一般効果をクリア"},
    "高级：直接编辑效果原文": {"en": "Advanced: edit raw effect", "ja": "上級：効果の原文を編集"},
    "国家精神": {"en": "National Spirits", "ja": "国家精神"},
    "🧠 国家精神编辑器": {"en": "🧠 National Spirit Editor", "ja": "🧠 国家精神エディタ"},
    "关闭": {"en": "Close", "ja": "閉じる"},
    "搜索国家精神 id / 名称": {"en": "Search spirit id / name", "ja": "国家精神 ID / 名前を検索"},
    "脚本原文（保存会重写该块，注释会丢失）": {"en": "Raw script (block is rewritten; comments lost)", "ja": "スクリプト原文（保存時に書き換え。コメントは失われます）"},
    "保存国家精神": {"en": "Save National Spirit", "ja": "国家精神を保存"},
    "＋ 新建精神": {"en": "+ New Spirit", "ja": "＋ 新規精神"},
    "🗑 删除精神": {"en": "🗑 Delete Spirit", "ja": "🗑 精神削除"},
    "一键添加：国家精神 / 装备": {"en": "One-click: national spirit / equipment", "ja": "ワンクリック：国家精神 / 装備"},
    "添加精神": {"en": "Add Spirit", "ja": "精神を追加"},
    "添加装备": {"en": "Add Equipment", "ja": "装備を追加"},
    "国家精神 id": {"en": "Spirit id", "ja": "国家精神 ID"},
    "装备 id 如 infantry_equipment_1": {"en": "Equipment id, e.g. infantry_equipment_1", "ja": "装備 ID 例: infantry_equipment_1"},
    "欢迎使用国策树编辑器": {"en": "Welcome to the Focus Tree Editor", "ja": "国家方針ツリーエディタへようこそ"},
    "选择你要编辑的 mod 文件夹。认准这一层：里面有一个 descriptor.mod 文件（通常旁边还有 common 文件夹）。": {
        "en": "Choose the mod folder you want to edit. Look for the folder that contains descriptor.mod (usually next to a common folder).",
        "ja": "編集する mod フォルダを選びます。descriptor.mod がある階層を選んでください（通常 common フォルダも同じ場所にあります）。"},
    "如果同时用本体和子模组：先加载本体，再加载子模组即可；后加载的会覆盖同名国策树。": {
        "en": "If you use a base mod plus a sub-mod: load the base first, then the sub-mod; later ones override same-named focus trees.",
        "ja": "本体とサブ mod を併用する場合：先に本体、次にサブ mod を読み込みます。後から読み込んだ方が同名ツリーを上書きします。"},
    "选择 mod 文件夹（推荐）": {"en": "Choose mod folder (recommended)", "ja": "mod フォルダを選択（推奨）"},
    "手动输入路径": {"en": "Enter path manually", "ja": "パスを手入力"},
    "选错了或想追加？进入界面后点左侧「＋ 添加 mod」就行。": {
        "en": "Picked the wrong one, or want to add another? Click “+ Add mod” in the sidebar later.",
        "ja": "間違えた場合や追加したい場合は、左の「＋ mod を追加」からいつでも選べます。"},
    "先随便看看": {"en": "Just look around", "ja": "とりあえず見る"},
    "＋ 添加 mod": {"en": "+ Add mod", "ja": "＋ mod を追加"},
    "🆕 新建模组": {"en": "🆕 New Mod", "ja": "🆕 新しい mod"},
    "新建模组": {"en": "New Mod", "ja": "新しい mod を作成"},
    "保存位置": {"en": "Save location", "ja": "保存先"},
    "模组文件夹名": {"en": "Mod folder name", "ja": "mod フォルダ名"},
    "显示名称": {"en": "Display name", "ja": "表示名"},
    "版本": {"en": "Version", "ja": "バージョン"},
    "游戏版本": {"en": "Game version", "ja": "ゲームバージョン"},
    "创建示例国策树（直接基于原版做 mod）": {"en": "Create a sample focus tree (vanilla-based mod)", "ja": "サンプル国家方針ツリーを作成（バニラをベースに）"},
    "国策树 ID": {"en": "Focus tree ID", "ja": "国家方針ツリー ID"},
    "国家 TAG": {"en": "Country TAG", "ja": "国家 TAG"},
    "不会替换原版文件，只在 common/national_focus 里新增一棵树；创建后自动加载。": {
        "en": "No vanilla files are replaced; one tree is added under common/national_focus, then loaded automatically.",
        "ja": "バニラのファイルは置き換えず、common/national_focus にツリーを 1 つ追加します。作成後は自動で読み込みます。"},
    "创建模组": {"en": "Create Mod", "ja": "mod を作成"},
    "取消": {"en": "Cancel", "ja": "キャンセル"},
    "选择 mod 文件夹": {"en": "Choose mod folder", "ja": "mod フォルダを選択"},
    "直接粘贴路径，回车跳转": {"en": "Paste a path and press Enter", "ja": "パスを貼り付けて Enter"},
    "选择此文件夹": {"en": "Choose this folder", "ja": "このフォルダを選択"},
    "未选择文件夹": {"en": "No folder selected", "ja": "フォルダ未選択"},
    "选择盘符或输入路径": {"en": "Pick a drive or enter a path", "ja": "ドライブを選択、またはパスを入力"},
    "选择图标": {"en": "Choose Icon", "ja": "アイコンを選択"},
    "搜索图标名（GFX_...）": {"en": "Search icon name (GFX_...)", "ja": "アイコン名を検索（GFX_...）"},
    "没有匹配的图标": {"en": "No matching icons", "ja": "一致するアイコンがありません"},
    "树设置": {"en": "Tree Settings", "ja": "ツリー設定"},
    "country 块（原始脚本，控制哪些国家使用这棵树）": {
        "en": "country block (raw script controlling which countries use this tree)",
        "ja": "country ブロック（どの国がこのツリーを使うかを制御するスクリプト）"},
    "保存树设置": {"en": "Save Tree Settings", "ja": "ツリー設定を保存"},
    "改花费": {"en": "Set cost", "ja": "コスト変更"},
    "改图标": {"en": "Set icon", "ja": "アイコン変更"},
    "自动排版": {"en": "Auto layout", "ja": "自動整列"},
    "取消选择": {"en": "Clear selection", "ja": "選択解除"},
    "确认修改": {"en": "Confirm Changes", "ja": "変更を確認"},
    "确认保存": {"en": "Save", "ja": "保存する"},
    "缺失本地化": {"en": "Missing Localization", "ja": "未ローカライズ"},
    "游戏 error.log（最近相关行）": {"en": "Game error.log (recent related lines)", "ja": "ゲーム error.log（関連する最近の行）"},
    "没有缺失本地化的焦点。": {"en": "No focuses with missing localization.", "ja": "ローカライズが不足しているノードはありません。"},
    "没有发现相关的报错行。": {"en": "No related error lines found.", "ja": "関連するエラー行は見つかりませんでした。"},
    "撤销": {"en": "Undo", "ja": "元に戻す"},
    "重做": {"en": "Redo", "ja": "やり直し"},
    "树设置": {"en": "Tree Settings", "ja": "ツリー設定"},
    "花费 / 图标": {"en": "Cost / Icon", "ja": "コスト / アイコン"},
    "中文名称 / 描述": {"en": "Chinese name / description", "ja": "中国語名 / 説明"},
    "English name / description": {"en": "English name / description", "ja": "英語名 / 説明"},
    "保存此节点": {"en": "Save Node", "ja": "ノード保存"},
    "保存名称/描述": {"en": "Save Name/Desc", "ja": "名前/説明を保存"},
    "还原": {"en": "Revert", "ja": "元に戻す"},
    "删除节点": {"en": "Delete Node", "ja": "ノード削除"},
    "焦点数：": {"en": "Focuses: ", "ja": "ノード数："},
    "前置边：": {"en": "Prereq edges: ", "ja": "前提エッジ："},
    "循环依赖：": {"en": "Cycles: ", "ja": "循環："},
    "坐标重叠：": {"en": "Overlaps: ", "ja": "座標重複："},
    "悬空前置：": {"en": "Missing prereq: ", "ja": "存在しない前提："},
    "未保存改动：": {"en": "Unsaved: ", "ja": "未保存："},
    "连线模式：": {"en": "Link mode: ", "ja": "リンクモード："},
    "前置": {"en": "prerequisite", "ja": "前提"},
    "互斥": {"en": "mutex", "ja": "排他"},
}

MSG = {
    "已保存": {"en": "Saved", "ja": "保存しました"},
    "本地化已保存": {"en": "Localization saved", "ja": "ローカライズを保存しました"},
    "名称/描述已保存": {"en": "Name/description saved", "ja": "名前/説明を保存しました"},
    "没有未保存的改动": {"en": "No unsaved changes", "ja": "未保存の変更はありません"},
    "已存在这条前置": {"en": "Prerequisite already exists", "ja": "この前提は既に存在します"},
    "不能连自己": {"en": "Cannot link to itself", "ja": "自分自身にはリンクできません"},
    "编辑模式已开启：拖动节点改位置": {"en": "Edit Mode on: drag nodes to move", "ja": "編集モード ON：ノードをドラッグで移動"},
    "编辑模式已关闭": {"en": "Edit Mode off", "ja": "編集モード OFF"},
    "已退出连线模式": {"en": "Exited link mode", "ja": "リンクモードを終了"},
    "效果花括号不匹配，未保存": {"en": "Effect braces are unbalanced; not saved", "ja": "効果の括弧が一致しないため保存しません"},
    "快捷效果已保存": {"en": "Quick effects saved", "ja": "クイック効果を保存しました"},
    "国家精神已保存": {"en": "National spirit saved", "ja": "国家精神を保存しました"},
    "请先填国家精神 id": {"en": "Enter a national spirit id first", "ja": "先に国家精神 ID を入力してください"},
    "请先填装备 id": {"en": "Enter an equipment id first", "ja": "先に装備 ID を入力してください"},
}

PREFIX = [
    ("已保存：", {"en": "Saved: ", "ja": "保存："}),
    ("保存失败：", {"en": "Save failed: ", "ja": "保存失敗："}),
    ("新建失败：", {"en": "Create failed: ", "ja": "作成失敗："}),
    ("删除失败：", {"en": "Delete failed: ", "ja": "削除失敗："}),
    ("已新建 ", {"en": "Created ", "ja": "作成 "}),
    ("已删除 ", {"en": "Deleted ", "ja": "削除 "}),
    ("已移动 ", {"en": "Moved ", "ja": "移動 "}),
    ("覆盖包已导出：", {"en": "Patch exported: ", "ja": "パッチ出力："}),
    ("导出失败：", {"en": "Export failed: ", "ja": "出力失敗："}),
    ("已添加前置：", {"en": "Prerequisite added: ", "ja": "前提を追加："}),
    ("已添加互斥：", {"en": "Mutex added: ", "ja": "排他を追加："}),
    ("已选起点：", {"en": "Source selected: ", "ja": "始点を選択："}),
    ("点击目标节点", {"en": "click target node", "ja": "対象ノードをクリック"}),
    ("连线模式：", {"en": "Link mode: ", "ja": "リンクモード："}),
    ("（未保存）", {"en": " (unsaved)", "ja": "（未保存）"}),
]

def tr_ui(text, lang):
    if lang == "zh":
        return text
    v = UI.get(text)
    return v.get(lang, text) if v else text

def loc_msg(msg, lang):
    if lang == "zh" or not msg:
        return msg
    if msg in MSG:
        return MSG[msg][lang]
    for zh, tr in PREFIX:
        if msg.startswith(zh):
            return tr[lang] + msg[len(zh):]
    import re
    m = re.match(r"已保存 (\d+) 个节点", msg)
    if m:
        return ("Saved %s nodes" if lang == "en" else "%s 個のノードを保存") % m.group(1)
    return msg

def inject(html, lang):
    import json
    payload = {"ui": UI, "msgs": MSG, "prefix": PREFIX, "lang": lang,
               "langNames": LANG_NAMES, "mascot": MASCOT}
    tag = '<script id="i18n-data">window.__I18N__=%s;window.__LANG__="%s";</script>' % (
        json.dumps(payload, ensure_ascii=False), lang)
    html = html.replace('<html lang="zh-CN">', '<html lang="%s">' % lang)
    return html.replace("<!--I18N-->", tag)

HELP = {
    "zh": [
        ("h1", "雪绒的钢铁雄心编辑器 使用教程"),
        ("p", "本工具用于可视化查看和编辑 HOI4 国策树，支持直接读写 mod 文件，并可导出覆盖包分享给他人。"),
        ("h2", "1. 启动与选择 mod"),
        ("p", "双击 exe（或命令行运行 python focus_editor.py）。不带参数时会弹出文件夹选择框：选择 mod 根目录（含 descriptor.mod 的那一层）。"),
        ("p", "需要同时加载本体和子模组时，用命令行：--mod \"本体目录\" --mod \"子模组目录\"，后加载的同 ID 国策树会覆盖前者。"),
        ("h2", "2. 浏览国策树"),
        ("p", "左侧列表选择国策树；鼠标滚轮缩放，空白处拖动平移；点「适应屏幕」可自动缩放；搜索框可查找焦点 ID 或名称。"),
        ("p", "节点显示图标、ID、名称与花费；箭头为前置关系，红色虚线为互斥；循环依赖会标红。"),
        ("h2", "3. 编辑节点"),
        ("p", "开启「编辑模式」后，直接拖动节点即可修改 x/y 坐标（相对定位节点会自动换算偏移）。"),
        ("p", "点击节点打开右侧面板，可修改：X/Y、前置（每组一行，组内用 + 表示 AND，组之间用 | 表示 OR）、互斥、花费、图标 GFX 名、中文/英文名称与描述。"),
        ("p", "改完点「保存此节点」或「保存名称/描述」；首次修改会自动生成 .bak 备份。"),
        ("h2", "4. 批量编辑"),
        ("p", "「➕ 新建节点」：输入 ID 与坐标，在当前树中新建焦点。"),
        ("p", "「🌳 新建树」「🗑 删除树」：新建/删除整棵国策树。"),
        ("p", "「🔗 加前置」「🔗 加互斥」：开启后点两个节点即可建立关系。"),
        ("p", "移动多个节点后点「💾 保存全部」一次性写回。"),
        ("h2", "5. 导出与分享"),
        ("p", "「📦 导出覆盖包」会只打包改动过的文件为 ZIP，解压覆盖到相同相对路径即可；不会改动未编辑的文件。"),
        ("h2", "6. 注意事项"),
        ("p", "• HOI4 每个国家只能有一棵 focus_tree，给已有国策树的国家新建树不会生效，应把节点加进现有树。"),
        ("p", "• cost 的单位是「周」：cost = 1 表示 7 天。"),
        ("p", "• 保存前会生成 .bak 备份；误操作时可手动还原。"),
        ("p", "• 工具只修改 common/national_focus 与本地化文件，不碰其他内容。"),
        ("h2", "新功能速查"),
        ("p", "撤销 / 重做：Ctrl+Z / Ctrl+Y；Ctrl+点击可多选节点，批量改花费、图标，或一键自动排版。"),
        ("p", "保存节点前会弹出 diff 预览；节点面板的「🖼 选择图标」打开图标库。"),
        ("p", "工具栏还有「⚙ 树设置」（country/default）、「🔎 本地化」缺失检查、「🧾 报错」查看 error.log；侧栏「🆕 新建模组」可直接生成基于原版的可用 mod。"),
    ],
    "en": [
        ("h1", "Focus Tree Editor - Guide"),
        ("p", "A local tool to view and edit HOI4 focus trees. It reads and writes mod files directly and can export a patch ZIP."),
        ("h2", "1. Start & choose mod"),
        ("p", "Run the exe (or python focus_editor.py). Without arguments it opens a folder picker: choose the mod root (the folder containing descriptor.mod)."),
        ("p", "To load a base mod plus a sub-mod, use: --mod \"base\" --mod \"sub\". Later mods override the same tree IDs."),
        ("h2", "2. Browse trees"),
        ("p", "Pick a tree on the left. Wheel = zoom, drag empty space = pan, Fit = auto zoom. Search finds focus IDs or names."),
        ("p", "Nodes show icon, ID, name and cost. Arrows are prerequisites; red dashed lines are mutual exclusions; cycles are marked red."),
        ("h2", "3. Edit a focus"),
        ("p", "Enable Edit Mode to drag nodes and change x/y (relative-positioned nodes are converted automatically)."),
        ("p", "Click a node to open the panel: X/Y, prerequisites (groups separated by |, AND with +), mutex, cost, icon GFX name, Chinese/English names and descriptions."),
        ("p", "Use Save Node / Save Name-Desc. The first change creates a .bak backup."),
        ("h2", "4. Batch editing"),
        ("p", "New Focus: enter ID and coordinates to create a focus in the current tree."),
        ("p", "New Tree / Delete Tree: create or remove an entire focus tree."),
        ("p", "Add Prereq / Add Mutex: click two nodes to create the relation."),
        ("p", "After moving several nodes, use Save All."),
        ("h2", "5. Export"),
        ("p", "Export Patch packs only the changed files into a ZIP. Extract it over the same relative paths in the mod folder."),
        ("h2", "6. Notes"),
        ("p", "• HOI4 allows one focus tree per country. Adding a new tree for a country that already has one has no effect; add nodes to the existing tree instead."),
        ("p", "• cost is in weeks: cost = 1 means 7 days."),
        ("p", "• A .bak backup is created before writing; restore manually if needed."),
        ("p", "• Only common/national_focus and localization files are touched."),
        ("h2", "New features"),
        ("p", "Undo / redo: Ctrl+Z / Ctrl+Y. Ctrl+click to multi-select nodes, then set cost/icon in bulk or auto-layout the tree."),
        ("p", "Saving a node shows a diff preview first; the 🖼 Choose Icon button opens the icon library."),
        ("p", "Toolbar also has ⚙ Tree Settings (country/default), 🔎 missing-localization check and 🧾 error.log viewer; 🆕 New Mod in the sidebar creates a ready vanilla-based mod."),
    ],
    "ja": [
        ("h1", "国家方針ツリーエディタ ガイド"),
        ("p", "HOI4 の国家方針ツリーを表示・編集するローカルツールです。mod ファイルを直接読み書きし、パッチ ZIP を出力できます。"),
        ("h2", "1. 起動と mod の選択"),
        ("p", "exe を実行（または python focus_editor.py）。引数なしの場合はフォルダ選択が開きます。descriptor.mod がある mod ルートを選んでください。"),
        ("p", "本体とサブ mod を同時に読み込む場合：--mod \"本体\" --mod \"サブ\"。後に読み込んだ方が同じツリー ID を上書きします。"),
        ("h2", "2. ツリーの閲覧"),
        ("p", "左の一覧からツリーを選択。ホイールでズーム、空白をドラッグで移動、「画面に合わせる」で自動調整。検索で ID や名前を探せます。"),
        ("p", "ノードにはアイコン・ID・名前・コストが表示されます。矢印は前提、赤い破線は排他、循環は赤で表示されます。"),
        ("h2", "3. ノードの編集"),
        ("p", "編集モードを有効にするとノードをドラッグして x/y を変更できます（相対指定ノードは自動換算）。"),
        ("p", "ノードをクリックすると右パネルが開き、X/Y・前提（| でグループ、+ で AND）・排他・コスト・アイコン GFX 名・中国語/英語の名前と説明を編集できます。"),
        ("p", "「ノード保存」「名前/説明を保存」で書き込み。初回変更時に .bak が作成されます。"),
        ("h2", "4. 一括編集"),
        ("p", "「新規ノード」：ID と座標を入力して現在のツリーに追加します。"),
        ("p", "「新規ツリー」「ツリー削除」：ツリー全体の作成/削除。"),
        ("p", "「前提を追加」「排他を追加」：2 つのノードをクリックして関係を作成。"),
        ("p", "複数ノードを移動した後は「すべて保存」で一括書き込み。"),
        ("h2", "5. エクスポート"),
        ("p", "「パッチ出力」は変更したファイルだけを ZIP にします。mod フォルダの同じ相対パスに上書きしてください。"),
        ("h2", "6. 注意"),
        ("p", "• HOI4 は 1 国につき 1 つの focus_tree のみ。既存ツリーがある国に新しいツリーを作っても表示されません。既存ツリーにノードを追加してください。"),
        ("p", "• cost の単位は週：cost = 1 は 7 日です。"),
        ("p", "• 書き込み前に .bak が作成されます。必要なら手動で復元してください。"),
        ("p", "• 変更するのは common/national_focus とローカライズのみです。"),
        ("h2", "新機能"),
        ("p", "元に戻す / やり直し：Ctrl+Z / Ctrl+Y。Ctrl+クリックで複数選択し、コストやアイコンの一括変更、自動整列ができます。"),
        ("p", "ノード保存時に diff プレビューが表示されます。🖼 アイコンを選択でアイコン一覧が開きます。"),
        ("p", "ツールバーには ⚙ ツリー設定（country/default）、🔎 ローカライズ不足チェック、🧾 error.log 表示もあります。サイドバーの 🆕 新しい mod でバニラベースの mod を作成できます。"),
    ],
}

def help_html(lang):
    parts = ['<!DOCTYPE html><html lang="%s"><head><meta charset="utf-8"><title>%s</title>' % (
        lang, _html.escape(tr_ui("国策树编辑器 - muvluvCN", lang)))]
    parts.append('<style>body{font-family:system-ui,"Microsoft YaHei",sans-serif;background:#16191b;color:#d9d3c7;max-width:900px;margin:24px auto;padding:0 16px;line-height:1.75}'
                 'h1{color:#c2ae82}h2{color:#d8b878;margin-top:22px;border-bottom:1px solid #2b3234;padding-bottom:4px}p{color:#c9c3b7}'
                 'a{color:#9fbfb4}</style></head><body>')
    parts.append('<img src="/mascot_face.png" alt="雪绒" style="width:110px;border-radius:18px;float:right;margin:0 0 12px 16px">')
    for tag, text in HELP.get(lang, HELP["zh"]):
        if tag in ("h1", "h2", "p"):
            parts.append("<%s>%s</%s>" % (tag, _html.escape(text), tag))
    parts.append("<p><a href='/'>← %s</a></p>" % _html.escape("返回编辑器" if lang == "zh" else ("Back to editor" if lang == "en" else "エディタに戻る")))
    parts.append("</body></html>")
    return "".join(parts)
