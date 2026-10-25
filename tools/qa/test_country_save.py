# -*- coding: utf-8 -*-
"""v0.56 国家历史写回回归：只改目标键、保留注释/条件块/BOM/CRLF，并验证新建历史文件。

用法（先启动服务加载 qa/fixtures/country_mod）：
    python work/focus_editor.py --mod work/qa/fixtures/country_mod --port 8898
    python work/qa/test_country_save.py            # 每次重建 fixture 后测
    python work/qa/test_country_save.py --keep     # 不重建，直接测当前文件状态
"""
import io
import json
import os
import sys
import urllib.request

BASE = os.environ.get('TEST_BASE', 'http://127.0.0.1:8898')
HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, 'fixtures', 'country_mod')
HIST_DIR = os.path.join(MOD, 'history', 'countries')
HIST = os.path.join(HIST_DIR, 'TST - Testland.txt')


def build_fixture():
    for d in ('common/country_tags', 'common/countries', 'common/national_focus',
              'history/countries', 'localisation/simp_chinese'):
        os.makedirs(os.path.join(MOD, d), exist_ok=True)
    w = lambda p, t, enc='utf-8', nl='\n': io.open(
        os.path.join(MOD, p), 'w', encoding=enc, newline=nl).write(t)
    w('descriptor.mod', 'name="Fixture Country Mod"\nversion="0.1"\nsupported_version="1.19.*"\n')
    w('common/country_tags/test_countries.txt', 'TST = "countries/Test.txt"\nTSU = "countries/Test2.txt"\n')
    w('common/countries/Test.txt', 'graphical_culture = western_gfx\ncolor = { 20 40 60 }\n')
    w('common/countries/Test2.txt', 'graphical_culture = western_gfx\ncolor = { 200 100 50 }\n')
    w('common/national_focus/tst_focus.txt',
      'focus_tree = {\n\tid = tst_focus\n\tcountry = {\n\t\tfactor = 0\n\t\tmodifier = {\n'
      '\t\t\tadd = 10\n\t\t\ttag = TST\n\t\t}\n\t}\n\tfocus = {\n\t\tid = tst_root\n'
      '\t\tx = 0\n\t\ty = 0\n\t\tcost = 1\n\t}\n}\n')
    hist = ('\ufeffcapital = 100# 旧首都\n'
            'set_politics = {\n\truling_party = fascism\n\telections_allowed = no\n}\n'
            'add_political_power = 50\n'
            'if = {\n\tlimit = { has_dlc = "Man the Guns" }\n\tadd_stability = 0.1\n}\n'
            'add_ideas = {\n\told_idea_a\n\told_idea_b\n}\n')
    w('history/countries/TST - Testland.txt', hist, nl='\r\n')
    w('localisation/simp_chinese/test_l_simp_chinese.yml',
      '\ufeffl_simp_chinese:\n TST:0 "测试国"\n TST_ADJ:0 "测试的"\n TSU:0 "空壳国"\n')
    for fn in os.listdir(HIST_DIR):
        if fn.startswith('TSU'):
            os.remove(os.path.join(HIST_DIR, fn))


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=180) as r:
        return json.loads(r.read().decode())


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())


def main():
    fails = []

    def check(name, cond, extra=''):
        print(('PASS ' if cond else 'FAIL ') + name + (('  ' + str(extra)) if not cond else ''))
        if not cond:
            fails.append(name)

    if '--keep' not in sys.argv:
        build_fixture()
        try:
            post('/api/unload_mod', {'root': MOD})
        except Exception:
            pass
        r = post('/api/load_mod', {'path': MOD})
        print('重载 fixture:', r.get('msg'))

    before = io.open(HIST, 'rb').read()
    check('原文件有 BOM', before.startswith(b'\xef\xbb\xbf'))
    check('原文件是 CRLF', b'\r\n' in before)

    d = get('/api/country_history?tag=TST')
    check('读取 ok', d.get('ok') and d.get('exists'))
    f = d.get('fields') or {}
    check('读到首都 100', f.get('capital') == '100', f.get('capital'))
    check('读到执政党 fascism', f.get('ruling_party') == 'fascism', f.get('ruling_party'))
    check('读到政治点 50', f.get('political_power') == '50', f.get('political_power'))
    check('可写标记', d.get('writable') is True)

    r = post('/api/country_save', {'tag': 'TST', 'fields': {
        'capital': '200', 'ruling_party': 'democratic', 'political_power': '120',
        'stability': '0.05', 'ideas': ['new_idea_one', 'new_idea_two'], 'focus_tree': 'tst_focus'}})
    check('保存 ok', r.get('ok'), r.get('msg'))
    check('返回 diff 5 条', len(r.get('diff') or []) >= 5, r.get('diff'))
    check('有"精神不存在"提示', any('不存在' in w for w in (r.get('warnings') or [])), r.get('warnings'))

    after = io.open(HIST, 'rb').read()
    text = after.decode('utf-8-sig')
    check('BOM 仍在', after.startswith(b'\xef\xbb\xbf'))
    check('仍是 CRLF', b'\r\n' in after)
    check('首都改成 200', 'capital = 200' in text, text[:60])
    check('旧注释保留', '# 旧首都' in text)
    check('执政党改成 democratic', 'ruling_party = democratic' in text)
    check('set_politics 里其它键保留', 'elections_allowed = no' in text)
    check('政治点改成 120', 'add_political_power = 120' in text)
    check('稳定度写到顶层', 'add_stability = 0.05' in text)
    check('条件块里的 add_stability 0.1 保留', 'add_stability = 0.1' in text)
    check('精神块被替换', 'new_idea_one' in text and 'old_idea_a' not in text)
    check('树写入块', 'load_focus_tree = {' in text and 'tree = tst_focus' in text)
    check('花括号平衡', text.count('{') == text.count('}'), (text.count('{'), text.count('}')))

    d2 = get('/api/country_history?tag=TST')
    f2 = d2.get('fields') or {}
    check('回读首都 200', f2.get('capital') == '200', f2.get('capital'))
    check('回读政治点 120', f2.get('political_power') == '120', f2.get('political_power'))
    c = get('/api/country?tag=TST')
    check('聚合里首都 200', c.get('capital') == '200', c.get('capital'))
    check('聚合里挂到 tst_focus', any(t['id'] == 'tst_focus' for t in c.get('trees', [])), c.get('trees'))

    r2 = post('/api/country_save', {'tag': 'TSU', 'fields': {
        'capital': '300', 'ruling_party': 'neutrality', 'ideas': ['only_one_idea']}})
    check('新建历史文件 ok', r2.get('ok'), r2.get('msg'))
    newp = None
    for fn in os.listdir(HIST_DIR):
        if fn.startswith('TSU'):
            newp = os.path.join(HIST_DIR, fn)
    check('文件已创建', bool(newp), newp)
    if newp:
        nt = io.open(newp, encoding='utf-8').read()
        check('新文件含首都', 'capital = 300' in nt, nt)
        check('新文件含政体', 'ruling_party = neutrality' in nt)
        check('新文件含精神块', 'only_one_idea' in nt)
    c2 = get('/api/country?tag=TSU')
    check('新国家首都进聚合', c2.get('capital') == '300', c2.get('capital'))

    bad = post('/api/country_save', {'tag': 'TST', 'fields': {'capital': 'abc'}})
    check('非法首都被拒', bad.get('ok') is False, bad.get('msg'))
    bad2 = post('/api/country_save', {'tag': 'TST', 'fields': {'ruling_party': 'monarchy'}})
    check('非法政体被拒', bad2.get('ok') is False, bad2.get('msg'))

    print('\n结果：', '全部通过' if not fails else ('失败 ' + str(fails)))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
