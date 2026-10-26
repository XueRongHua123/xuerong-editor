# -*- coding: utf-8 -*-
"""v0.68 回归：开局装备变体的新增与删除（fixture）。"""
import io
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_country_save as base  # noqa: E402

BASE = os.environ.get('TEST_BASE', 'http://127.0.0.1:8898')
MOD = base.MOD
HIST = base.HIST


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=180) as r:
        return json.loads(r.read().decode())


def main():
    fails = []

    def check(name, cond, extra=''):
        print(('PASS ' if cond else 'FAIL ') + name + (('  ' + str(extra)) if not cond else ''))
        if not cond:
            fails.append(name)

    base.build_fixture()
    try:
        post('/api/unload_mod', {'root': MOD})
    except Exception:
        pass
    post('/api/load_mod', {'path': MOD})

    d = get('/api/country_history?tag=TST')
    before = len((d.get('fields') or {}).get('variants') or [])
    check('起始没有变体', before == 0, before)

    r = post('/api/country_variant', {'tag': 'TST', 'action': 'add', 'name': 'TestJet',
                                      'type': 'fighter_equipment_0',
                                      'modules': {'fixed_main_weapon_slot': 'fighter_weapon_1'}})
    check('新增 ok', r.get('ok'), r.get('msg'))
    text = io.open(HIST, encoding='utf-8').read()
    check('文件里有块', 'create_equipment_variant' in text)
    check('name 写入', 'name = "TestJet"' in text, '')
    check('type 写入', 'type = fighter_equipment_0' in text)
    check('模块写入', 'fixed_main_weapon_slot = fighter_weapon_1' in text)
    check('花括号平衡', text.count('{') == text.count('}'), (text.count('{'), text.count('}')))
    check('原有注释保留', '# 旧首都' in text or 'capital' in text)

    d2 = get('/api/country_history?tag=TST')
    vs = (d2.get('fields') or {}).get('variants') or []
    check('回读 1 个变体', len(vs) == 1, vs)
    check('回读名称', vs and vs[0].get('name') == 'TestJet', vs[:1])
    check('回读模块数', vs and vs[0].get('modules') == 1, vs[:1])

    r2 = post('/api/country_variant', {'tag': 'TST', 'action': 'add', 'name': 'TestJet',
                                       'type': 'fighter_equipment_0', 'modules': {'x': 'y'}})
    check('重名被拒', r2.get('ok') is False, r2.get('msg'))

    r3 = post('/api/country_variant', {'tag': 'TST', 'action': 'add', 'name': 'Bad',
                                       'type': 'bad chassis!', 'modules': {'a': 'b'}})
    check('非法底盘格式被拒', r3.get('ok') is False, r3.get('msg'))
    post('/api/country_variant', {'tag': 'TST', 'action': 'del', 'name': 'TestJet2'})

    r4 = post('/api/country_variant', {'tag': 'TST', 'action': 'del', 'name': 'TestJet'})
    check('删除 ok', r4.get('ok'), r4.get('msg'))
    text2 = io.open(HIST, encoding='utf-8').read()
    check('TestJet 块已删除', 'name = "TestJet"' not in text2, text2[-260:])
    check('删后花括号平衡', text2.count('{') == text2.count('}'))
    check('删后其它内容还在', '# ' in text2 or 'capital' in text2)

    r5 = post('/api/country_variant', {'tag': 'TST', 'action': 'del', 'name': 'Nope'})
    check('删不存在的被拒', r5.get('ok') is False, r5.get('msg'))

    print('\n结果：', '全部通过' if not fails else ('失败 ' + str(fails)))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
