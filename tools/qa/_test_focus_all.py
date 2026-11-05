# -*- coding: utf-8 -*-
"""国策编辑器全线功能测试。

覆盖：改属性、前置、互斥、快捷效果、新建节点、加前置、删除节点。
每次写操作后都核对磁盘上的文件真的变了。

v1.24.2（R3-4）：不再拿 XRT1 当靶子。以前每跑一次就往
XRT1/common/national_focus/ 塞 MVLV_UNI.txt + .bak（只读层接管的产品行为），
跑三轮留三轮。现在开头现造一个一次性目录 tmp/_feat_<pid>，
全部写操作都落在它里面，finally 里 rmtree——XRT1 一个文件都不碰。

需要服务先跑在 8765：
    python focus_editor.py
"""
import json
import os
import re
import shutil
import urllib.request

BASE = 'http://127.0.0.1:8765'
W = r'E:\SteamLibrary\steamapps\workshop\content\394360\2800380626'   # 只读层（接管测试用）
M = r'C:\Users\33206\Documents\Paradox Interactive\Hearts of Iron IV\mod'
XRT1 = M + r'\XRT1'              # 只用来「确认没被碰」，不写

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(os.path.dirname(HERE), 'tmp', '_feat_%d' % os.getpid())
REL = 'common/national_focus/zz_focus_test.txt'
TREE_ID = 'ZTEST_tree'
DST = os.path.join(TMP, REL.replace('/', os.sep))

PASS, FAIL = [], []


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=300))


def get(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=300))


def ok(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('%-6s %-38s %s' % ('PASS' if cond else 'FAIL', name, detail))
    return cond


def read(p):
    return open(p, encoding='utf-8', errors='replace').read() if os.path.exists(p) else ''


def snapshot(root):
    """目录里全部相对路径（残留检查用）。"""
    out = set()
    for dp, _dn, fns in os.walk(root):
        for fn in fns:
            out.add(os.path.relpath(os.path.join(dp, fn), root).replace(os.sep, '/'))
    return out


def make_target():
    """一次性靶子：descriptor + 一棵 3 节点（另带 1 个 shared_focus）的最小树。"""
    if os.path.isdir(TMP):
        shutil.rmtree(TMP)
    os.makedirs(os.path.join(TMP, 'common', 'national_focus'))
    open(os.path.join(TMP, 'descriptor.mod'), 'w', encoding='utf-8').write(
        'name="feat_test"\nversion="0.1"\nsupported_version="1.19.*"\n')
    open(os.path.join(TMP, REL.replace('/', os.sep)), 'w', encoding='utf-8').write(
        'focus_tree = {\n'
        '\tid = ZTEST_tree\n'
        '\tcountry = {\n\t\tfactor = 0\n\t}\n'
        '\tshared_focus = {\n'
        '\t\tid = ZTEST_shared\n'
        '\t\ticon = GFX_goal_generic_national_unity\n'
        '\t\tx = 1\n\t\ty = 0\n\t\tcost = 5\n'
        '\t}\n'
        '\tfocus = {\n'
        '\t\tid = ZTEST_a\n'
        '\t\ticon = GFX_goal_generic_national_unity\n'
        '\t\tx = 5\n\t\ty = 0\n\t\tcost = 5\n'
        '\t}\n'
        '\tfocus = {\n'
        '\t\tid = ZTEST_b\n'
        '\t\ticon = GFX_goal_generic_national_unity\n'
        '\t\tx = 6\n\t\ty = 0\n\t\tcost = 5\n'
        '\t}\n'
        '\tfocus = {\n'
        '\t\tid = ZTEST_c\n'
        '\t\ticon = GFX_goal_generic_national_unity\n'
        '\t\tx = 6\n\t\ty = 1\n\t\tcost = 5\n'
        '\t\tprerequisite = { focus = ZTEST_b }\n'
        '\t}\n'
        '}\n'
    )


fid = 'ZTEST_a'


def main():
    print('=== 准备：清空已加载，造一次性靶子 %s ===' % os.path.basename(TMP))
    xrt1_before = snapshot(XRT1) if os.path.isdir(XRT1) else set()
    print('XRT1 快照：%d 个文件' % len(xrt1_before))
    # 逐个卸载已加载的 root。unload_mod 要显式 root——
    # 旧脚本 post('/api/unload_mod', {}) 空 body 其实什么都没卸，
    # ROOTS 越积越多，_writable_top() 会指向上一次的靶子目录。
    d0 = get('/api/data')
    for _r in (d0.get('roots') or []):
        print(post('/api/unload_mod', {'root': _r.get('path')})['msg'])
    make_target()
    print(post('/api/load_mod', {'path': TMP})['msg'])
    print()

    g = get('/api/focus_graph?tree=' + TREE_ID)
    nodes = g.get('nodes') or []
    print('ZTEST_tree 节点数:', len(nodes))
    if not ok('靶子树能被解析', any(n.get('id') == fid for n in nodes), TREE_ID):
        print('!! 靶子树都没解析出来，后面的测试没法跑')
        raise SystemExit(1)
    print()

    print('=== 1. 改成本（save） ===')
    r = post('/api/save', {'root': TMP, 'file': REL, 'id': fid, 'fields': {'cost': 7}})
    print('  返回:', r)
    after = read(DST)
    ok('save 返回 ok', r.get('ok') is True, str(r.get('msg'))[:60])
    m = re.search(r'id\s*=\s*%s[\s\S]{0,400}?cost\s*=\s*(\d+)' % re.escape(fid), after)
    ok('cost 改成 7', bool(m and m.group(1) == '7'), '实际 cost=%s' % (m.group(1) if m else '?'))
    print()

    print('=== 2. 改前置（prereq） ===')
    r = post('/api/save', {'root': TMP, 'file': REL, 'id': fid, 'fields': {'prereq': [['ZTEST_b']]}})
    after = read(DST)
    blk = re.search(r'id\s*=\s*%s[\s\S]{0,2000}?prerequisite[\s\S]{0,300}?\}' % re.escape(fid), after)
    ok('prereq 写入', bool(blk and 'ZTEST_b' in blk.group(0)), (blk.group(0)[:80] if blk else '无 prerequisite 块'))
    print()

    print('=== 3. 改互斥（mutex） ===')
    r = post('/api/save', {'root': TMP, 'file': REL, 'id': fid, 'fields': {'mutex': ['ZTEST_c']}})
    after = read(DST)
    blk = re.search(r'id\s*=\s*%s[\s\S]{0,3000}?mutually_exclusive[\s\S]{0,300}?\}' % re.escape(fid), after)
    ok('mutex 写入', bool(blk and 'ZTEST_c' in blk.group(0)), (blk.group(0)[:80] if blk else '无 mutually_exclusive 块'))
    print()

    print('=== 4. 快捷效果（照前端 saveFxQuick 的真实做法：拼 effect 文本）===')
    # 注意：旧版这里发 {'quick': {...}}，后端不认这个键、静默忽略，
    # 旧的 PASS 是假阳性——MVLV_UNI.txt 原文里本来就有 add_political_power。
    # 前端真实行为是把输入拼成 effect 原文（saveFxQuick），照抄。
    r = post('/api/save', {'root': TMP, 'file': REL, 'id': fid,
                           'fields': {'effect': 'add_political_power = 50\nadd_stability = 0.05'}})
    print('  返回:', str(r)[:120])
    after = read(DST)
    blk = re.search(r'id\s*=\s*%s[\s\S]{0,4000}?(?=\n\tfocus\s*=|\n})' % re.escape(fid), after)
    seg = blk.group(0) if blk else after
    ok('政治力 effect 写进节点', 'add_political_power = 50' in seg, '')
    ok('稳定度 effect 写进节点', 'add_stability = 0.05' in seg, '')
    print()

    print('=== 5. 新建节点（add_focus）===')
    NEWID = 'ZTEST_test_node_1'
    r = post('/api/add_focus', {'root': TMP, 'file': REL, 'tree': TREE_ID,
                                'id': NEWID, 'x': 99, 'y': 88, 'cost': 3})
    print('  返回:', r)
    after = read(DST)
    ok('add_focus 返回 ok', r.get('ok') is True, str(r.get('msg'))[:60])
    ok('新节点写进文件', NEWID in after, '')
    g2 = get('/api/focus_graph?tree=' + TREE_ID)
    ok('重新解析能读到新节点', any(n.get('id') == NEWID for n in (g2.get('nodes') or [])), '')
    print()

    print('=== 6. 删除刚建的节点（delete_focus）===')
    r = post('/api/delete_focus', {'root': TMP, 'file': REL, 'id': NEWID})
    after = read(DST)
    ok('delete_focus 返回 ok', r.get('ok') is True, str(r.get('msg'))[:60])
    ok('文件里没有这个节点了', NEWID not in after, '')
    print()

    print('=== 7. 接管路径（往只读层写 → 复制进靶子目录）===')
    # 靶子是链里唯一的可写层，所以接管目标就是它自己——正好验证 R2-2 的机制，
    # 而且残渣全落在 finally 会删掉的 TMP 里。
    uni = os.path.join(W, 'common', 'national_focus', 'MVLV_UNI.txt')
    if os.path.isfile(uni):
        txt = open(uni, encoding='utf-8', errors='replace').read()
        # 先去掉整行注释：这文件开头一大段被注释掉的示例 focus（# focus = { ...），
        # 不去掉的话取到的是注释里的 id，save 会正确地报「未找到焦点」。
        mfid = re.search(r'focus\s*=\s*\{[^{}]*?id\s*=\s*"?([A-Za-z0-9_]+)"?',
                         re.sub(r'(?m)^\s*#.*$', '', txt))
        wmd5_before = read(uni)
        r = post('/api/save', {'root': W, 'file': 'common/national_focus/MVLV_UNI.txt',
                               'id': mfid.group(1) if mfid else 'X', 'fields': {'cost': 6}})
        print('  返回:', str(r)[:160])
        ok('接管写返回 ok', r.get('ok') is True, str(r.get('msg'))[:60])
        ok('adopted_to 指向靶子目录', r.get('adopted_to') == os.path.basename(TMP.rstrip('\\/')),
           str(r.get('adopted_to')))
        ok('副本落在靶子目录', os.path.isfile(os.path.join(TMP, 'common', 'national_focus', 'MVLV_UNI.txt')))
        ok('只读层原文件没被改', read(uni) == wmd5_before, W)
    else:
        print('  跳过（没有 %s）' % uni)
    print()

    print('=== 8. XRT1 零残留 ===')
    xrt1_after = snapshot(XRT1) if os.path.isdir(XRT1) else set()
    extra = sorted(xrt1_after - xrt1_before)
    ok('XRT1 一个文件都没多', not extra, ('多了: ' + ', '.join(extra[:4])) if extra else
       ('%d 个文件，前后一致' % len(xrt1_after)))
    print()


try:
    main()
finally:
    if os.path.isdir(TMP):
        shutil.rmtree(TMP, ignore_errors=True)
        print('已清理靶子目录 %s' % TMP)
    # 把靶子从服务的 ROOTS 里也卸掉，别留一个指向已删目录的死层
    try:
        print(post('/api/unload_mod', {'root': TMP})['msg'])
    except Exception as _e:
        print('（服务已停，跳过卸载：%s）' % _e)

print()
print('=== 汇总 ===')
print('PASS %d / FAIL %d' % (len(PASS), len(FAIL)))
if FAIL:
    print('失败项:')
    for f in FAIL:
        print('  -', f)
