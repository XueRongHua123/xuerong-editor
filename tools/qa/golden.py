# -*- coding: utf-8 -*-
"""黄金测试跑批。

用例写在 qa/cases/*.json，加用例只改数据不改代码。

用法：
    python qa/golden.py               跑全部
    python qa/golden.py core          只跑 core.json
    python qa/golden.py -v            打印每个用例
"""
import io
import json
import os
import shutil
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
CASES = os.path.join(HERE, 'cases')
sys.path.insert(0, WORK)


def _load():
    if not os.path.isdir(CASES):
        return []
    out = []
    for fn in sorted(os.listdir(CASES)):
        if not fn.endswith('.json'):
            continue
        p = os.path.join(CASES, fn)
        try:
            d = json.load(io.open(p, encoding='utf-8'))
        except Exception as e:
            print('读不了 %s：%s' % (fn, e))
            continue
        for c in (d.get('cases') or []):
            c['_file'] = fn
            out.append(c)
    return out


def _make_fixture(spec):
    """把 {相对路径: 内容} 铺到临时目录，返回目录路径。"""
    d = tempfile.mkdtemp(prefix='golden_')
    for rel, content in (spec or {}).items():
        p = os.path.join(d, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(p) or d, exist_ok=True)
        io.open(p, 'w', encoding='utf-8', newline='').write(content)
    return d


def run(only=None, verbose=False):
    import focus_editor as fe
    cases = _load()
    if only:
        cases = [c for c in cases if only in c['_file']]

    ok = bad = 0
    fails = []
    for c in cases:
        name = c.get('name') or '(无名)'
        fn_name = c.get('fn')
        fn = getattr(fe, fn_name, None)
        if not fn:
            bad += 1
            fails.append((name, '没有函数 %s' % fn_name))
            print('  FAIL %-42s 没有函数 %s' % (name, fn_name))
            continue

        tmp = None
        try:
            args = list(c.get('args') or [])
            if 'fixture' in c:
                tmp = _make_fixture(c.get('fixture'))
                args = [tmp] + list(c.get('args_after_fixture') or [])
            got = fn(*args)

            if 'expect_bytes' in c:
                want = c['expect_bytes'].encode('utf-8')
                good = (got == want)
                detail = '' if good else '期望 %r，实际 %r' % (want, got)
            elif 'expect' in c:
                want = c['expect']
                good = (got == want)
                detail = '' if good else '期望 %r，实际 %r' % (want, got)
            elif 'expect_contains' in c:
                text = got if isinstance(got, str) else json.dumps(got, ensure_ascii=False)
                missing = [x for x in c['expect_contains'] if x not in text]
                good = not missing
                detail = '' if good else '缺少 %r' % missing
            else:
                good = True
                detail = ''

            if good:
                ok += 1
                if verbose:
                    print('  ok   %-42s %s' % (name, c.get('note', '')[:50]))
            else:
                bad += 1
                fails.append((name, detail))
                print('  FAIL %-42s %s' % (name, detail))
        except Exception:
            bad += 1
            tb = traceback.format_exc().strip().splitlines()[-1]
            fails.append((name, tb))
            print('  ERR  %-42s %s' % (name, tb))
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

    print()
    print('=' * 62)
    print('用例 %d | 通过 %d | 失败 %d' % (len(cases), ok, bad))
    if fails:
        print()
        for n, d in fails:
            print('  - %-42s %s' % (n, d))
    return 0 if not bad else 1


if __name__ == '__main__':
    argv = [a for a in sys.argv[1:] if not a.startswith('-')]
    only = argv[0] if argv else None
    sys.exit(run(only, '-v' in sys.argv))
