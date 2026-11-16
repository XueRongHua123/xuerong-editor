// 00-i18n：I18N / LANG / T / locMsg / translateDom / applyTheme / applySize（P4 F2 原样搬出，非 module）
const I18N = window.__I18N__ || {ui:{}, msgs:{}, prefix:[], lang:'zh'};
const LANG = window.__LANG__ || 'zh';
(function(){
  try {
    if(location.search.indexOf('lang=') === -1){
      const saved = localStorage.getItem('fe_lang');
      const nav = (navigator.language || '').toLowerCase();
      const lang = saved || (nav.startsWith('ja') ? 'ja' : (nav.startsWith('en') ? 'en' : 'zh'));
      if(lang && lang !== 'zh'){
        const u = new URL(location.href);
        u.searchParams.set('lang', lang);
        location.replace(u.toString());
      }
    }
  } catch(e){}
})();

function applyTheme(mode){
  mode = mode || 'auto';
  const dark = mode === 'dark' || (mode === 'auto' && !window.matchMedia('(prefers-color-scheme: light)').matches);
  document.body.classList.toggle('theme-paper', !dark);
}
try {
  const savedTheme = localStorage.getItem('fe_theme') || 'auto';
  applyTheme(savedTheme);
} catch(e){ applyTheme('auto'); }

function applySize(mode){
  mode = mode || 'normal';
  document.body.classList.toggle('fs-large', mode === 'large');
  document.body.classList.toggle('fs-small', mode === 'small');
}
try { applySize(localStorage.getItem('fe_size') || 'normal'); } catch(e){ applySize('normal'); }
function T(zh){
  if(LANG === 'zh') return zh;
  const v = I18N.ui && I18N.ui[zh];
  return (v && v[LANG]) || zh;
}
function locMsg(m){
  if(LANG === 'zh' || !m) return m;
  const v = I18N.msgs && I18N.msgs[m];
  if(v && v[LANG]) return v[LANG];
  for(const p of (I18N.prefix || [])){
    if(m.startsWith(p[0])) return p[1][LANG] + m.slice(p[0].length);
  }
  const mt = m.match(/^已保存 (\d+) 个节点$/);
  if(mt) return LANG === 'en' ? ('Saved ' + mt[1] + ' nodes') : (mt[1] + ' 個のノードを保存');
  return m;
}
function translateDom(root){
  root = root || document.body;
  if(LANG === 'zh') return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while(walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(n=>{
    const s = n.nodeValue; const key = s.trim(); if(!key) return;
    const v = I18N.ui && I18N.ui[key];
    if(v && v[LANG]) n.nodeValue = s.replace(key, v[LANG]);
  });
  root.querySelectorAll('[placeholder]').forEach(el=>{
    const k = el.getAttribute('placeholder'); const v = I18N.ui && I18N.ui[k];
    if(v && v[LANG]) el.setAttribute('placeholder', v[LANG]);
  });
}
