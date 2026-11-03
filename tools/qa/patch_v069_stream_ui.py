# -*- coding: utf-8 -*-
"""v0.69 前端：AI 流式输出 + 停止按钮。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor_index.html')
MARK = "/* ---------- v0.69 AI 流式 ---------- */"

JS = """/* ---------- v0.69 AI 流式 ---------- */
let aiAbort = null;

async function sendAI(){
  const out = document.getElementById('aiOut');
  const prompt = document.getElementById('aiPrompt').value.trim();
  if(!prompt){ status('先输入问题'); return; }
  out.textContent = '';
  aiUpdateMeta('请求中…');
  const t0 = Date.now();
  aiAbort = new AbortController();
  const stopBtn = document.getElementById('aiStop');
  if(stopBtn) stopBtn.style.display = '';
  let acc = '', finished = false;
  try{
    const r = await fetch('/api/ai_chat', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({prompt, context: document.getElementById('aiContext').value, stream: true}),
      signal: aiAbort.signal});
    if(!r.ok || !r.body){ throw new Error('HTTP ' + r.status); }
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while(true){
      const step = await reader.read();
      if(step.done) break;
      buf += dec.decode(step.value, {stream: true});
      let idx;
      while((idx = buf.indexOf('\\n\\n')) >= 0){
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const line = chunk.split('\\n').find(l=>l.indexOf('data:') === 0);
        if(!line) continue;
        let obj;
        try{ obj = JSON.parse(line.slice(5).trim()); }catch(e){ continue; }
        if(obj.d){
          acc += obj.d;
          out.textContent = acc;
          out.scrollTop = out.scrollHeight;
        }
        if(obj.end){
          finished = true;
          if(!obj.ok){
            out.textContent = acc || ('失败：' + (obj.msg || '未知错误'));
            aiUpdateMeta('✗ ' + (obj.msg || ''));
          } else {
            aiUpdateMeta('✓ ' + (Date.now() - t0) + 'ms · 流式');
            if(acc) aiPushHistory(prompt, acc);
          }
        }
      }
    }
    if(!finished && acc){ aiUpdateMeta('✓ ' + (Date.now() - t0) + 'ms · 流式'); aiPushHistory(prompt, acc); }
  }catch(e){
    if(e.name === 'AbortError'){
      aiUpdateMeta('已停止');
      if(acc) aiPushHistory(prompt, acc);
    } else {
      out.textContent = '失败：' + e.message;
      aiUpdateMeta('✗ 网络错误');
    }
  }
  if(stopBtn) stopBtn.style.display = 'none';
  aiAbort = null;
}

function stopAI(){
  if(aiAbort){ aiAbort.abort(); }
}

"""


def main():
    h = io.open(P, encoding='utf-8').read()
    if MARK in h:
        print('已注入，跳过')
        return 0

    start = h.index("async function sendAI(){")
    end = h.index("\nasync function ", start + 10) + 1
    old = h[start:end]
    assert "out.textContent = '请求中…'" in old, old[:160]
    h = h[:start] + JS + h[end:]

    # 停止按钮
    old_btn = '''<button class="btn primary" id="aiSend">发送</button>'''
    new_btn = '''<button class="btn primary" id="aiSend">发送</button><button class="btn" id="aiStop" style="display:none">停止</button>'''
    assert h.count(old_btn) == 1
    h = h.replace(old_btn, new_btn, 1)

    # 绑定
    anchor = "document.getElementById('aiTest').onclick = aiTest;"
    assert h.count(anchor) == 1
    h = h.replace(anchor, anchor + "\ndocument.getElementById('aiStop').onclick = stopAI;", 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(h)
    print('v0.69 前端注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
