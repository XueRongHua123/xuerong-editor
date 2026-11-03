# -*- coding: utf-8 -*-
"""v0.61：AI 面板与雪绒悬浮球迭代。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, '..', 'focus_editor.py')
HTML = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "/* ---------- v0.61 AI 面板与悬浮球 ---------- */"

CSS = """  /* ---------- v0.61 AI 面板与悬浮球 ---------- */
  #aiBubble.busy{border-color:var(--accent);animation:bubbleBusy 1.4s linear infinite}
  @keyframes bubbleBusy{0%{box-shadow:0 0 0 0 color-mix(in srgb,var(--accent) 55%,transparent)}
    100%{box-shadow:0 0 0 13px transparent}}
  #aiMenu{position:fixed;z-index:125;background:var(--panel);border:1px solid var(--line);border-radius:10px;
    box-shadow:var(--shadow);padding:6px;display:none;min-width:168px}
  #aiMenu.show{display:block}
  #aiMenu div{padding:7px 10px;border-radius:6px;font-size:12px;color:var(--text);cursor:pointer;
    display:flex;gap:8px;align-items:center}
  #aiMenu div:hover{background:var(--panel2);color:var(--accent)}
  .ai-tpl{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 6px}
  #aiHistory{margin:4px 0 6px;max-height:98px;overflow:auto}
  .ai-h{padding:4px 8px;border-radius:6px;font-size:11px;color:var(--muted);cursor:pointer;
    border-left:2px solid transparent;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .ai-h:hover{background:var(--panel2);color:var(--text);border-left-color:var(--accent)}
  #aiMeta{font-size:10.5px;color:var(--muted)}
"""

DOM = """      <div class="ai-tpl" id="aiTemplates">
        <span class="cm-chip" data-tpl="effect">写国策效果</span>
        <span class="cm-chip" data-tpl="translate">翻译三语</span>
        <span class="cm-chip" data-tpl="check">检查这段脚本</span>
        <span class="cm-chip" data-tpl="error">解释报错</span>
        <span class="cm-chip" data-tpl="event">写一个事件</span>
      </div>
"""

DOM_HEAD = """<button class="btn" id="aiTest" title="用当前配置发一条极短请求，验证连通性">🧪 测试</button><button class="btn" id="aiClearHistory" title="清空最近对话">🧹 清空</button>"""

DOM_HISTORY = """      <div id="aiHistory"></div>
"""

MENU = """<div id="aiMenu">
  <div data-act="ai">💬 AI 助手</div>
  <div data-act="cmd">⌘ 命令面板</div>
  <div data-act="lint">🩺 项目体检</div>
  <div data-act="country">🌍 国家中心</div>
  <div data-act="state">🗺 州 / 地块</div>
  <div data-act="hide">👀 隐藏雪绒</div>
</div>
"""

JS = """/* ---------- v0.61 AI 面板与悬浮球 ---------- */
const AI_TEMPLATES = {
  effect: '帮我写一段 HOI4 国策完成效果（completion_reward）：加 50 政治点、10% 稳定度，并解锁一个名为 my_new_idea 的国家精神。只返回效果脚本。',
  translate: '把下面这段内容翻译成中日英三语，格式：中文 / English / 日本語，各一行，不要解释。\\n\\n',
  check: '检查下面这段 HOI4 脚本有没有语法或逻辑错误（花括号、键名、作用域），指出具体行并给修正版。\\n\\n',
  error: '下面是 HOI4 的 error.log 片段，帮我判断根因并给出修复步骤，尽量引用具体文件与键名。\\n\\n',
  event: '帮我写一个 HOI4 事件：命名空间 my_ns，id my_ns.1，触发条件是国家有 my_flag，选项里加 20 政治点。只返回事件脚本。'
};
let AI_HISTORY = [];

function aiFillTemplate(kind){
  const t = AI_TEMPLATES[kind];
  if(!t) return;
  const box = document.getElementById('aiPrompt');
  box.value = t;
  box.focus();
  status('已填入模板，按「发送」提交');
}

function aiUpdateMeta(txt){
  const el = document.getElementById('aiMeta');
  if(el) el.textContent = txt || '';
}

async function aiTest(){
  const btn = document.getElementById('aiTest');
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = '测试中…';
  const t0 = Date.now();
  try{
    const r = await fetch('/api/ai_test', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const j = await r.json();
    aiUpdateMeta((j.ok ? '✓ ' : '✗ ') + (j.msg || '') + ' · ' + (Date.now() - t0) + 'ms');
    status(j.ok ? 'AI 连接正常' : ('AI 连接失败：' + (j.msg || '')), !j.ok);
  }catch(e){
    aiUpdateMeta('✗ ' + e.message);
    status('测试失败：' + e.message, true);
  }
  btn.disabled = false;
  btn.textContent = old;
}

function aiPushHistory(prompt, answer){
  AI_HISTORY.unshift({q: prompt, a: answer, t: new Date().toLocaleTimeString().slice(0, 5)});
  AI_HISTORY = AI_HISTORY.slice(0, 12);
  renderAIHistory();
}

function renderAIHistory(){
  const box = document.getElementById('aiHistory');
  if(!box) return;
  if(!AI_HISTORY.length){ box.innerHTML = ''; return; }
  box.innerHTML = '<div class="k" style="margin:2px 0 2px">最近提问（点一下回填）</div>' +
    AI_HISTORY.map((h, i)=>'<div class="ai-h" data-i="' + i + '">' + h.t + ' · ' + escapeHtml(h.q.slice(0, 60)) + '</div>').join('');
  box.querySelectorAll('.ai-h').forEach(el=>{
    el.onclick = ()=>{
      const h = AI_HISTORY[Number(el.dataset.i)];
      if(!h) return;
      document.getElementById('aiPrompt').value = h.q;
      document.getElementById('aiOut').textContent = h.a;
      aiUpdateMeta('来自历史记录');
    };
  });
}

function aiClearHistory(){
  AI_HISTORY = [];
  renderAIHistory();
  document.getElementById('aiOut').textContent = '';
  aiUpdateMeta('');
  status('已清空最近对话');
}

function aiToggleKey(){
  const el = document.getElementById('aiKey');
  el.type = el.type === 'password' ? 'text' : 'password';
}

/* 悬浮球菜单 */
function openAiMenu(x, y){
  const menu = document.getElementById('aiMenu');
  menu.classList.add('show');
  const w = menu.offsetWidth || 176, h = menu.offsetHeight || 220;
  menu.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, x)) + 'px';
  menu.style.top = Math.max(8, Math.min(window.innerHeight - h - 8, y)) + 'px';
}
function closeAiMenu(){ document.getElementById('aiMenu').classList.remove('show'); }

function aiMenuAction(act){
  closeAiMenu();
  if(act === 'ai') return openAI();
  if(act === 'cmd') return openCmd();
  if(act === 'lint') return openLint();
  if(act === 'country') return openCountry();
  if(act === 'state') return openStates();
  if(act === 'hide'){
    const box = document.getElementById('mascotFloat');
    if(box) box.style.display = 'none';
    try{ localStorage.setItem('mascotFloatState', JSON.stringify({hidden: true})); }catch(e){}
    status('已隐藏雪绒，可从左侧「❄ 雪绒」重新显示');
  }
}

function aiBubbleBusy(on){
  const b = document.getElementById('aiBubble');
  if(b) b.classList.toggle('busy', !!on);
}

"""


def main():
    s = io.open(PY, encoding='utf-8').read()
    h = io.open(HTML, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    # 后端：测试连接
    if '/api/ai_test' not in s:
        old = '''        elif self.path == "/api/ai_chat":'''
        new = '''        elif self.path == "/api/ai_test":
            cfg = load_ai_config()
            t0 = time.time()
            ok, msg = ai_chat(cfg, "ping，只回复 ok", "")
            self._send({"ok": ok, "msg": (msg or "")[:200],
                        "ms": int((time.time() - t0) * 1000)})
        elif self.path == "/api/ai_chat":'''
        assert s.count(old) == 1
        s = s.replace(old, new, 1)
        io.open(PY, 'w', encoding='utf-8', newline='').write(s)
        print('后端 /api/ai_test 注入完成')

    # CSS
    anchor_css = "  /* ---------- v0.60 数据源 ---------- */"
    assert h.count(anchor_css) == 1
    h = h.replace(anchor_css, CSS + anchor_css, 1)

    # 头部按钮
    old_head = '<button class="btn" id="aiSettingsBtn" title="AI 配置">⚙</button><button class="btn" id="aiSave">保存配置</button>'
    new_head = '<button class="btn" id="aiSettingsBtn" title="AI 配置">⚙</button>' + DOM_HEAD + '<button class="btn" id="aiSave">保存配置</button>'
    assert h.count(old_head) == 1
    h = h.replace(old_head, new_head, 1)

    # Key 眼睛（在 API Key 输入后加按钮不容易，改成双击标签切换：用 aiKey 的 dblclick）
    # 模板行 + 历史
    old_prompt = '''      <label>提问<textarea id="aiPrompt"'''
    assert h.count(old_prompt) == 1
    h = h.replace(old_prompt, DOM + DOM_HISTORY + old_prompt, 1)

    # 结果区前加 meta 行：放在 aiOut 前
    old_out = '''      <pre id="aiOut" class="ai-out"></pre>'''
    new_out = '''      <div id="aiMeta"></div>
      <pre id="aiOut" class="ai-out"></pre>'''
    assert h.count(old_out) == 1
    h = h.replace(old_out, new_out, 1)

    # 球菜单 DOM：放在 aiBubble 之后
    old_bubble = '<div id="aiBubble" title="雪绒 AI 助手"><img src="/mascot_face.png" alt="雪绒"><span>雪绒</span></div>'
    assert h.count(old_bubble) == 1
    h = h.replace(old_bubble, old_bubble + "\n" + MENU, 1)

    # JS
    anchor_js = "/* ---------- v0.60 数据源与加载进度 ---------- */"
    assert h.count(anchor_js) == 1
    h = h.replace(anchor_js, JS + anchor_js, 1)

    # sendAI：记录历史 + 错误提示
    old_send = """  out.textContent = '请求中…';
  const r = await fetch('/api/ai_chat', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({prompt, context: document.getElementById('aiContext').value})});
  const j = await r.json();
  out.textContent = j.ok ? (j.msg || '') : ('失败：' + (j.msg || '未知错误'));
}"""
    new_send = """  out.textContent = '请求中…';
  aiUpdateMeta('请求中…');
  const t0 = Date.now();
  try{
    const r = await fetch('/api/ai_chat', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({prompt, context: document.getElementById('aiContext').value})});
    const j = await r.json();
    out.textContent = j.ok ? (j.msg || '') : ('失败：' + (j.msg || '未知错误'));
    aiUpdateMeta((j.ok ? '✓' : '✗') + ' ' + (Date.now() - t0) + 'ms · ' + (j.ok ? '已返回' : '可点「测试」看连通性'));
    if(j.ok) aiPushHistory(prompt, j.msg || '');
  }catch(e){
    out.textContent = '失败：' + e.message;
    aiUpdateMeta('✗ 网络错误');
  }
}"""
    assert h.count(old_send) == 1
    h = h.replace(old_send, new_send, 1)

    # 绑定
    anchor_b = "document.getElementById('aiBubble')"
    bind = """document.getElementById('aiTest').onclick = aiTest;
document.getElementById('aiClearHistory').onclick = aiClearHistory;
document.querySelectorAll('#aiTemplates .cm-chip').forEach(el=>{
  el.onclick = ()=>aiFillTemplate(el.dataset.tpl);
});
document.getElementById('aiKey').addEventListener('dblclick', aiToggleKey);
document.getElementById('aiMenu').addEventListener('click', e=>{
  const row = e.target.closest('[data-act]');
  if(row) aiMenuAction(row.dataset.act);
});
document.addEventListener('click', e=>{
  if(!e.target.closest('#aiMenu') && !e.target.closest('#aiBubble')) closeAiMenu();
});
window.addEventListener('resize', closeAiMenu);
"""
    assert h.count(anchor_b) >= 1
    h = h.replace(anchor_b, bind + anchor_b, 1)

    # 悬浮球：右键菜单 + 双击命令面板
    old_click = """  bubble.addEventListener('pointerdown', e=>{"""
    new_click = """  bubble.addEventListener('contextmenu', e=>{
    e.preventDefault();
    openAiMenu(e.clientX - 8, e.clientY - 8);
  });
  bubble.addEventListener('dblclick', e=>{
    e.preventDefault();
    closeAiMenu();
    openCmd();
  });
  bubble.addEventListener('pointerdown', e=>{"""
    assert h.count(old_click) == 1
    h = h.replace(old_click, new_click, 1)

    # startLoading / stopLoading 联动球的忙碌状态
    old_sl = """  const st = document.getElementById('srcState');
  if(st){
    st.classList.add('busy');"""
    new_sl = """  aiBubbleBusy(true);
  const st = document.getElementById('srcState');
  if(st){
    st.classList.add('busy');"""
    assert h.count(old_sl) == 1
    h = h.replace(old_sl, new_sl, 1)

    old_sp = """function stopLoading(msg, isErr){
  clearInterval(loadTimer); loadTimer = null;"""
    new_sp = """function stopLoading(msg, isErr){
  aiBubbleBusy(false);
  clearInterval(loadTimer); loadTimer = null;"""
    assert h.count(old_sp) == 1
    h = h.replace(old_sp, new_sp, 1)

    io.open(HTML, 'w', encoding='utf-8', newline='').write(h)
    print('v0.61 前端注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
