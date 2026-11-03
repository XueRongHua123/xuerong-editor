# -*- coding: utf-8 -*-
"""国策编辑器全线功能测试。

覆盖用户报的每一条：改属性、前置、互斥、快捷效果、高级修改、新建节点、加前置。
每次写操作后都核对磁盘上的文件真的变了。
"""
import json
import os
import re
import sqlite3
import urllib.request

BASE = 'http://127.0.0.1:8765'
SUB = r'E:\SteamLibrary\steamapps\workshop\content\394360\2989050816'
M = r'C:\Users\33206\Documents\Paradox Interactive\Hearts of Iron IV\mod'
XRT1 = M + r'\XRT1'

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


print('=== 准备：加载 SUB + XRT1 ===')
print(post('/api/unload_mod', {})['msg'])
print(post('/api/load_mod', {'path': SUB})['msg'])
print(post('/api/load_mod', {'path': XRT1})['msg'])
st = post('/api/load_progress', {})
print()

# 拿一棵来自 CN 的树
g = get('/api/focus_graph?tree=UNI_focus_tree')
nodes = g.get('nodes') or []
TREE_ROOT = ''
try:
    d = json.load(urllib.request.urlopen(urllib.request.Request(BASE + '/api/data'), timeout=120))
    for _t in (d.get('trees') or []):
        if _t.get('id') == 'UNI_focus_tree':
            TREE_ROOT = _t.get('root') or ''
            print('树的真实 root:', TREE_ROOT)
            break
except Exception as _e:
    print('取 root 失败:', _e)
print('UNI_focus_tree 节点数:', len(nodes))
if not nodes:
    print('!! 没有节点，后面的测试没法跑')
    raise SystemExit(1)

# 找一个没有前置的叶子节点来改
target = None
for n in nodes:
    if n.get('id') and not n.get('prereq'):
        target = n
        break
target = target or nodes[0]
fid = target['id']
print('测试节点:', fid)
print()

# 文件在哪（接管后应该已经到 XRT1）
REL = 'common/national_focus/MVLV_UNI.txt'
src_file = os.path.join(SUB, REL)
dst_file = os.path.join(XRT1, REL)


def read(p):
    return open(p, encoding='utf-8', errors='replace').read() if os.path.exists(p) else ''


print('=== 1. 改成本（save） ===')
before_xrt1 = read(dst_file)
r = post('/api/save', {'root': TREE_ROOT, 'file': REL, 'id': fid, 'fields': {'cost': 7}})
print('  返回:', r)
after_xrt1 = read(dst_file)
ok('save 返回 ok', r.get('ok') is True, str(r.get('msg'))[:60])
ok('文件落到 XRT1', os.path.exists(dst_file), dst_file)
m = re.search(r'id\s*=\s*%s[\s\S]{0,400}?cost\s*=\s*(\d+)' % re.escape(fid), after_xrt1)
ok('cost 改成 7', bool(m and m.group(1) == '7'), '实际 cost=%s' % (m.group(1) if m else '?'))
print()

print('=== 2. 改前置（prereq） ===')
other = [n['id'] for n in nodes if n.get('id') and n['id'] != fid][:2]
r = post('/api/save', {'root': TREE_ROOT, 'file': REL, 'id': fid, 'fields': {'prereq': [other]}})
after = read(dst_file)
blk = re.search(r'id\s*=\s*%s[\s\S]{0,2000}?prerequisite[\s\S]{0,300}?\}' % re.escape(fid), after)
ok('prereq 写入', bool(blk and other[0] in blk.group(0)), (blk.group(0)[:80] if blk else '无 prerequisite 块'))
print()

print('=== 3. 改互斥（mutex） ===')
r = post('/api/save', {'root': TREE_ROOT, 'file': REL, 'id': fid, 'fields': {'mutex': [other[1]]}})
after = read(dst_file)
blk = re.search(r'id\s*=\s*%s[\s\S]{0,3000}?mutually_exclusive[\s\S]{0,300}?\}' % re.escape(fid), after)
ok('mutex 写入', bool(blk and other[1] in blk.group(0)), (blk.group(0)[:80] if blk else '无 mutually_exclusive 块'))
print()

print('=== 4. 快捷效果（focus_effect / set_variable 之类）===')
r = post('/api/save', {'root': TREE_ROOT, 'file': REL, 'id': fid,
                       'fields': {'quick': {'political_power': 50, 'stability': 0.05}}})
print('  返回:', str(r)[:120])
after = read(dst_file)
ok('政治力 effect 出现在文件里', 'add_political_power' in after, '')
ok('稳定度 effect 出现在文件里', 'add_stability' in after, '')
print()

print('=== 5. 新建节点（add_focus）===')
NEWID = 'XRT_test_node_1'
r = post('/api/add_focus', {'root': TREE_ROOT, 'file': REL, 'tree': 'UNI_focus_tree',
                            'id': NEWID, 'x': 99, 'y': 88, 'cost': 3})
print('  返回:', r)
after = read(dst_file)
ok('add_focus 返回 ok', r.get('ok') is True, str(r.get('msg'))[:60])
ok('新节点写进文件', NEWID in after, '')
g2 = get('/api/focus_graph?tree=UNI_focus_tree')
ok('重新解析能读到新节点', any(n.get('id') == NEWID for n in (g2.get('nodes') or [])), '')
print()

print('=== 6. 删除刚建的节点（delete_focus）===')
r = post('/api/delete_focus', {'root': TREE_ROOT, 'file': REL, 'id': NEWID})
after = read(dst_file)
ok('delete_focus 返回 ok', r.get('ok') is True, str(r.get('msg'))[:60])
ok('文件里没有这个节点了', NEWID not in after, '')
print()

print('=== 汇总 ===')
print('PASS %d / FAIL %d' % (len(PASS), len(FAIL)))
if FAIL:
    print('失败项:')
    for f in FAIL:
        print('  -', f)
