# -*- coding: utf-8 -*-
"""v0.59.1 回归：拖动时保留 @宏 写法（值不变就不拍平成数字）。"""
import io
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_v059 as tech  # noqa: E402

BASE = os.environ.get('TEST_BASE', 'http://127.0.0.1:8898')
MOD = tech.MOD
TECH = tech.TECH


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

    tech.build()
    try:
        post('/api/unload_mod', {'root': MOD})
    except Exception:
        pass
    post('/api/load_mod', {'path': MOD})
    rel = 'common/technologies/test_tech.txt'

    # 1) 移到宏对应的值（@1936 = 2）→ y 应保持 @1936
    r = post('/api/tech_move', {'root': MOD, 'rel': rel, 'tid': 'test_tech_a', 'x': 1, 'y': 2})
    check('移动 ok', r.get('ok'), r.get('msg'))
    text = io.open(TECH, encoding='utf-8').read()
    seg = text.split('test_tech_a')[1][:260]
    check('y 保留 @1936', 'y = @1936' in seg, seg[:200])
    check('宏定义仍在', '@1936 = 2' in text)
    check('没有写成 y = 2', 'y = 2' not in seg, seg[:200])
    check('花括号平衡', text.count('{') == text.count('}'))

    # 2) 移到别的行（5）→ 写数字
    r2 = post('/api/tech_move', {'root': MOD, 'rel': rel, 'tid': 'test_tech_a', 'x': 1, 'y': 5})
    check('再移动 ok', r2.get('ok'), r2.get('msg'))
    text2 = io.open(TECH, encoding='utf-8').read()
    seg2 = text2.split('test_tech_a')[1][:260]
    check('y 改成数字 5', 'y = 5' in seg2, seg2[:200])
    check('不再有 @1936 在这个块里', '@1936' not in seg2, seg2[:200])

    # 3) 重建后测 x 轴：x 原本是数字 0，即便等于宏值也不该写成 @1936
    tech.build()
    post('/api/unload_mod', {'root': MOD})
    post('/api/load_mod', {'path': MOD})
    r3 = post('/api/tech_move', {'root': MOD, 'rel': rel, 'tid': 'test_tech_a', 'x': 2, 'y': 2})
    text3 = io.open(TECH, encoding='utf-8').read()
    seg3 = text3.split('test_tech_a')[1][:260]
    check('x 写数字而不是误用宏', 'x = 2' in seg3 and 'x = @1936' not in seg3, seg3[:200])
    check('y 保留原宏 @1936', 'y = @1936' in seg3, seg3[:200])

    print('\n结果：', '全部通过' if not fails else ('失败 ' + str(fails)))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
