# -*- coding: utf-8 -*-
"""v0.70 命令面板「最近使用」。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "/* ---------- v0.70 命令面板最近使用 ---------- */"

JS = """/* ---------- v0.70 命令面板最近使用 ---------- */
const CP_RECENT_KEY = 'fe_cmd_recent';

function cpRecentList(){
  try{
    const a = JSON.parse(localStorage.getItem(CP_RECENT_KEY) || '[]');
    return Array.isArray(a) ? a.filter(x=>x && x.cat && x.label) : [];
  }catch(e){ return []; }
}

function cpRecentPush(cat, label){
  if(!cat || !label) return;
  const list = cpRecentList().filter(x=>!(x.cat === cat && x.label === label));
  list.unshift({cat, label});
  try{ localStorage.setItem(CP_RECENT_KEY, JSON.stringify(list.slice(0, 8))); }catch(e){}
}

"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    # 1) CP_CAT_ORDER 前面加「最近使用」
    old_order = "const CP_CAT_ORDER = ['操作','国策树','焦点','国家精神','装备','科技','事件'];"
    new_order = "const CP_CAT_ORDER = ['最近使用','操作','国策树','焦点','国家精神','装备','科技','事件'];"
    assert h.count(old_order) == 1
    h = h.replace(old_order, new_order, 1)

    # 2) 注入函数（放在 cpScore 之前）
    anchor = "function cpScore(q, s){"
    assert h.count(anchor) == 1
    h = h.replace(anchor, JS + anchor, 1)

    # 3) cpRender：无输入时把最近项塞到最前面
    old_head = """  const all = cpCache || (cpCache = cpBuild());
  const curId = (curTree() || {}).id;"""
    new_head = """  let all = cpCache || (cpCache = cpBuild());
  const curId = (curTree() || {}).id;
  if(!q){
    const seen = {};
    const rec = [];
    cpRecentList().forEach(r=>{
      const key = r.cat + '\\u0001' + r.label;
      if(seen[key]) return;
      seen[key] = 1;
      const it = all.find(x=>x.cat === r.cat && x.label === r.label);
      if(it) rec.push(Object.assign({}, it, {cat: '最近使用', hint: it.cat}));
    });
    if(rec.length) all = rec.concat(all);
  }"""
    assert h.count(old_head) == 1, 'cpRender 头部结构不符'
    h = h.replace(old_head, new_head, 1)

    # 4) cpRun：记录最近使用
    old_run = """function cpRun(i){
  const it = cpItems[i]; if(!it) return;
  closeCmd();"""
    new_run = """function cpRun(i){
  const it = cpItems[i]; if(!it) return;
  cpRecentPush(it.cat === '最近使用' ? (it.hint || '操作') : it.cat, it.label);
  closeCmd();"""
    assert h.count(old_run) == 1
    h = h.replace(old_run, new_run, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('v0.70 最近使用注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
