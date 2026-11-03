# -*- coding: utf-8 -*-
"""v0.58 前端：历史编辑面板加 oob / 科技 / 政党支持度。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "<!-- v0.58 历史编辑器补全 -->"

DOM = """          <!-- v0.58 历史编辑器补全 -->
          <div class="k">政党支持度（set_popularities，0-100；留空 = 不改）</div>
          <div class="hist-grid" style="grid-template-columns:repeat(4,1fr)">
            <label>democratic<input type="number" min="0" max="100" id="histPopD"></label>
            <label>fascism<input type="number" min="0" max="100" id="histPopF"></label>
            <label>communism<input type="number" min="0" max="100" id="histPopC"></label>
            <label>neutrality<input type="number" min="0" max="100" id="histPopN"></label>
          </div>
          <div class="k">部队编成 oob（相对路径，留空不改）</div>
          <input type="text" id="histOob" placeholder='例如 "AFR_1999"'>
          <div class="k">开局科技（每行一个 tech id；清空 = 不写 set_technology）</div>
          <textarea id="histTechs" style="height:104px" placeholder="infantry_weapons&#10;tech_support_weapons"></textarea>
"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    # DOM：插在科技树下拉那一行之后、"开局精神"之前
    old = """          <div class="k">开局精神（每行一个 idea id；清空 = 不写这一项）</div>"""
    assert h.count(old) == 1
    h = h.replace(old, DOM + old, 1)

    # 读取：填充三个新字段
    old2 = """  sel.value = f.focus_tree || '';
  document.getElementById('histSave').disabled = !d.writable;"""
    new2 = """  sel.value = f.focus_tree || '';
  const pops = f.popularities || {};
  document.getElementById('histPopD').value = pops.democratic != null ? pops.democratic : '';
  document.getElementById('histPopF').value = pops.fascism != null ? pops.fascism : '';
  document.getElementById('histPopC').value = pops.communism != null ? pops.communism : '';
  document.getElementById('histPopN').value = pops.neutrality != null ? pops.neutrality : '';
  document.getElementById('histOob').value = f.oob || '';
  document.getElementById('histTechs').value = (f.techs || []).join('\\n');
  document.getElementById('histSave').disabled = !d.writable;"""
    assert h.count(old2) == 1
    h = h.replace(old2, new2, 1)

    # 保存：组装新字段
    old3 = """    focus_tree: document.getElementById('histTree').value,
    ideas: ideasRaw.split(/\\r?\\n/).map(s=>s.trim()).filter(Boolean)
  };"""
    new3 = """    focus_tree: document.getElementById('histTree').value,
    ideas: ideasRaw.split(/\\r?\\n/).map(s=>s.trim()).filter(Boolean),
    oob: document.getElementById('histOob').value.trim(),
    techs: document.getElementById('histTechs').value.split(/\\r?\\n/).map(s=>s.trim()).filter(Boolean),
    popularities: {
      democratic: document.getElementById('histPopD').value,
      fascism: document.getElementById('histPopF').value,
      communism: document.getElementById('histPopC').value,
      neutrality: document.getElementById('histPopN').value
    }
  };"""
    assert h.count(old3) == 1
    h = h.replace(old3, new3, 1)

    # "什么都没填"的判断也要覆盖新字段
    old4 = """  if(!fields.capital && !fields.ruling_party && !fields.political_power && !fields.stability &&
     !fields.war_support && !fields.focus_tree && !fields.ideas.length){"""
    new4 = """  if(!fields.capital && !fields.ruling_party && !fields.political_power && !fields.stability &&
     !fields.war_support && !fields.focus_tree && !fields.ideas.length && !fields.oob &&
     !fields.techs.length && !Object.values(fields.popularities).some(v=>String(v).trim())){"""
    assert h.count(old4) == 1
    h = h.replace(old4, new4, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('v0.58 前端注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
