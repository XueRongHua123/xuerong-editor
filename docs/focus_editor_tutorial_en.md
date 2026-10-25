# Focus Tree Editor - Tutorial

A local tool to view and edit HOI4 focus trees. It reads/writes mod files directly and can export a patch ZIP.

## 1. Start

- Double-click the exe (or run `python focus_editor.py`).
- The editor page opens first; on the welcome screen click **Choose mod folder** to open the in-page folder browser, navigate or paste a path, then click **Choose this folder**.
- To append a sub-mod later, click **+ Add mod** in the sidebar (later mods override the same tree IDs).

### Create a new mod (vanilla-based)

Click **🆕 New Mod** in the sidebar:

- Enter the mod folder name, display name, version and game version;
- Optionally create a sample focus tree and set its tree ID and country TAG;
- The tool generates `descriptor.mod`, a sample focus tree (`common/national_focus`) and Chinese/English localization;
- If the save location is the HOI4 `mod` folder, a launcher `.mod` file is created too;
- The mod is loaded automatically. Vanilla files are not replaced — ideal for adding content on top of vanilla.
- To load a base mod plus sub-mod, pass them in load order:

```
FocusTreeEditor.exe --mod "base mod folder" --mod "sub mod folder"
```

Later mods override the same tree IDs, matching in-game load order.

Optional: `--port 8765`, `--game "HOI4 install folder"` (for vanilla icons).

## 2. Browsing

- Left list: all focus trees with focus count and source mod.
- **Wheel** = zoom, **drag empty space** = pan, **Fit** = auto zoom.
- Search box finds focus IDs or names.
- Nodes show icon, ID, name and cost. Arrows = prerequisites, red dashed lines = mutex, cycles are red.
- Statistics panel: focus count, prerequisite edges, cycles, coordinate overlaps, missing prerequisites, unsaved changes.

## 3. Editing a focus

1. Turn on **Edit Mode**.
2. Drag nodes to change x/y (relative-positioned focuses are converted automatically).
3. Click a node to open the right panel:
   - X / Y coordinates;
   - Prerequisites: groups separated by `|`, `+` inside a group means AND;
   - Mutex (comma separated);
   - Cost (unit: weeks; cost = 1 means 7 days);
   - Icon GFX name;
   - Chinese / English name and description.
4. Use **Save Node** / **Save Name-Desc**; the first change creates a `.bak` backup.

### Undo / Redo / Icons / Tree settings

- **Undo**: `Ctrl+Z` or the **↶ Undo** button; **Redo**: `Ctrl+Y` or **↷ Redo**;
- A snapshot is stored before every write, so undo returns to the previous saved state;
- **🖼 Choose Icon** in the node panel opens the icon library (search and click a GFX icon);
- **⚙ Tree Settings** in the toolbar edits the current tree's `country` block and `default` field (which countries use the tree).

### Focus effects (completion_reward / select_effect)

- **Quick effects**: fill numbers directly in the panel — political power, stability (%), war support (%), manpower (thousand), command power, army/air/navy XP — then click **Save Quick Effects**. No scripting needed;
- **One-click national spirit / equipment**: enter a spirit id (with suggestions) or an equipment id + amount, then click **Add Spirit** / **Add Equipment** to append `add_ideas` / `add_equipment_to_stockpile`;
- 0 or empty = skip that entry; **Clear Common Effects** removes them all at once;
- For advanced needs, expand **Advanced: edit raw effect** to write events, `add_tech_bonus`, etc.;
- **Select effect**: optional effect on selection; leave empty to remove the block;
- Braces are validated before saving; unbalanced input is rejected;
- The effect is written back as raw text, so **script comments inside it are lost** (keep a backup if comments matter).

## 4. Batch editing

| Button | Action |
|---|---|
| + New Focus | Create a focus in the current tree |
| New Tree | Create a new focus tree (`common/national_focus/zz_focus_editor_trees.txt`) |
| Delete Tree | Delete the current focus tree |
| Add Prereq / Add Mutex | Click two nodes to create a relation |
| Save All | Write all unsaved changes |

## 5. Export

**Export Patch** creates a ZIP with only the changed files. Extract it over the same relative paths in the mod folder.

## 6. National Spirit Editor

Left sidebar → "National Spirits" → "🧠 National Spirit Editor":

- Search and select an existing national spirit, view/edit its raw script (modifier, picture, allowed, ...);
- Edit its Chinese name and description;
- **+ New Spirit**: enter an id to create a national spirit (written to `common/ideas/zz_focus_editor_ideas.txt`);
- **Delete Spirit**: remove the selected national spirit;
- Braces are validated; a `.bak` backup is created automatically;
- Saving rewrites the spirit block (comments inside it are lost).

> Sidebar sections "Focus Trees / National Spirits / Statistics" are collapsible; the UI uses a low-contrast warm dark theme for less eye strain.

## 7. Mascot "Xuerong"

- Floats over the UI with her **full artwork**; drag the card anywhere (she sways slightly while dragging);
- **Click** her to pop a speech bubble and cycle a random usage tip (current UI language);
- A new tip fades in about every 25 seconds; a greeting appears on first open;
- **⤢** toggles size, **×** closes;
- Position, size and visibility are remembered;
- After hiding, click "❄ 雪绒" in the sidebar to bring her back;
- The exe and window icon also use her avatar.

## 8. Notes

- HOI4 allows **one focus tree per country**. A new tree for a country that already has one will not appear; add nodes to the existing tree instead.
- cost is measured in weeks: cost = 1 means 7 days.
- A `.bak` backup is created before writing; restore manually if needed.
- Only `common/national_focus` and localization files are modified.
- UI language can be switched in the top-right: 中文 / English / 日本語.

## Xuerong Wardrobe (outfits)

- Click "❄ 雪绒" in the sidebar to open the wardrobe;
- 7 outfits: classic, winter, running, flowers, classroom, cafe, snow;
- Click a thumbnail to switch instantly; the choice is remembered;
- Buttons inside can show/hide her; dragging, size and click bubbles still work.

## v0.39 / v0.40 新功能速查

- 科技树：组标签、节点详情浮层、搜索高亮、按 folder position 布局、拖线建前置、自动虚线补全
- 装备设计器：按底盘 module_slots 生成槽位、模块/槽位本地化名称、属性合计、生成 create_equipment_variant、插入当前国策、写入目标选择
- 原版参考：只读加载原版，禁止写入游戏目录；复制树/科技/精神/装备/事件到自己的模组
- 引用查询：查看某个 ID 被哪些国策/事件/科技引用
- AI：雪绒悬浮窗，支持 OpenAI/DeepSeek/Claude/Gemini/Ollama；结果可复制或插入编辑器原文
- 校验：花括号检测与一键修复、模组 replace_path 冲突、事件 namespace、缺失本地化
- 备份：文件级备份历史与恢复

## v0.51 Command palette & shortcuts

- Ctrl+K (or the Command button at the right end of the toolbar) opens the command palette: one input searches commands, focus trees, focuses, ideas, equipment, technologies and events;
- Arrow keys to move, Enter to run, Esc to close; with an empty input it groups frequent commands, the current tree's focuses and content entries;
- Shortcuts: Ctrl+S save all, Ctrl+Z / Ctrl+Y undo and redo, F fit to screen, H or Shift+? opens the shortcut sheet;
- In edit mode Delete removes the selected focus (the diff confirmation still appears); Esc closes the focus panel or leaves link mode;
- The sidebar search is now a result list of every matching focus (current tree first); click one to jump there and center it.

## v0.52 Colors and parser fixes

- All colors now go through design tokens, so the paper theme no longer paints dark-theme colors on a light background;
  body text reaches WCAG AA (4.5:1) in both themes.
- Paper accent darkened from #8a6a2f to #7c5d24 so large headings stay legible.
- Long ids in the equipment and technology lists are truncated with an ellipsis instead of breaking the sidebar.
- Parser fix: ids containing "-" (e.g. tsf_equipment_F-15SE) used to be truncated to "15SE";
  equipment goes from 342 to 348 and technologies from 676 to 753.

## v0.53 Unloading what you loaded

- "- Unload mod / vanilla" opens a list of loaded roots: name, full path, and a tag showing
  "editable" or "vanilla - read-only".
- Click Unload on a row to drop it from the editor. This only affects the current session; no files are deleted.
- Vanilla reference can be unloaded too: after that only your own mod content remains, and
  "Load vanilla reference" brings it back.
- It used to be impossible for the vanilla layer because the read-only guard also blocked the unload request.

## v0.54 Focus tree zoom

- Wheel zoom is now **cursor-anchored**: whatever node is under the pointer stays under the pointer,
  instead of drifting to the top-left corner.
- New toolbar switch `Mouse zoom / Screen zoom` (remembered): screen mode zooms around the canvas center.
- The zoom percentage shows live in the toolbar (e.g. `52%`), updated by wheel, buttons and Fit.
- Coordinate math after zoom was fixed too: dragging used to be inaccurate at 50% zoom; now the node
  follows the pointer 1:1 regardless of zoom level.
