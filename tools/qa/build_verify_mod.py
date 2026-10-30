# -*- coding: utf-8 -*-
"""建最小测试 mod（dependencies = muvluvCN），改三组内容，输出生成的文件。

测试 mod 只有自己的增量：州文件、战略区、补给区。CN 一个字节都不动。
"""
import sys
import io
import os
import shutil

sys.path.insert(0, r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work')
import focus_editor as fe

fe.GAME = r'E:\SteamLibrary\steamapps\common\Hearts of Iron IV'
MODDIR = r'C:\Users\33206\Documents\Paradox Interactive\Hearts of Iron IV\mod'
NAME = 'muvluvCN_verify'
OUT = os.path.join(MODDIR, NAME)

shutil.rmtree(OUT, ignore_errors=True)
for d in ('history/states', 'map/strategicregions', 'map/supplyareas'):
    os.makedirs(os.path.join(OUT, d.replace('/', os.sep)), exist_ok=True)

# descriptor：依赖 CN，不写 replace_path
DESC = '''name="muvluvCN_verify"
version="0.1.0"
tags={
\t"Alternative History"
}
supported_version="1.19.*"
dependencies={
\t"muvluvCN"
}
'''
io.open(os.path.join(OUT, 'descriptor.mod'), 'wb').write(b'\xef\xbb\xbf' + DESC.encode('utf-8'))
# 外部 .mod
EXT = DESC + 'path="%s"\n' % OUT.replace('\\', '/')
io.open(os.path.join(MODDIR, NAME + '.mod'), 'wb').write(b'\xef\xbb\xbf' + EXT.encode('utf-8'))
print('建立测试 mod:', OUT)

# 让编辑器加载它（子 mod 继承了 CN）
fe.ROOTS = [OUT]
fe.load_game_loc()
fe.reload_data()

print('\n=== 叠加链 ===')
for x in (fe.mod_layers(OUT) or []):
    print('   ', x)
print('国家 %d  州 %d' % (len(fe.COUNTRIES), len(fe.STATES)))

# ---- 第 1 组：州编辑 ----
print('\n=== 第 1 组：州编辑 ===')
before = fe.STATES.get(1) or {}
print('改前: owner=%s category=%s manpower=%s' % (
    before.get('owner'), before.get('category'), before.get('manpower')))
r1 = fe.state_save(1, {
    'owner': 'SOV',
    'category': 'large_town',
    'manpower': '123456',
    'cores': ['SOV'],
    'buildings': {'infrastructure': 7, 'arms_factory': 3},
})
print('返回:', r1.get('msg'))
after = fe.STATES.get(1) or {}
print('改后: owner=%s category=%s manpower=%s cores=%s buildings=%s' % (
    after.get('owner'), after.get('category'), after.get('manpower'),
    after.get('cores'), str(after.get('buildings'))[:70]))
print('落点: root=%s file=%s' % (
    os.path.basename(after.get('root') or ''), after.get('file')))

# ---- 第 2 组：地形 ----
print('\n=== 第 2 组：地形 ===')
fe._ensure_prov_rgb(OUT)
# 州 1 的省
provs1 = after.get('provinces') or []
print('州 1 的省:', provs1[:6])
tpid = provs1[0] if provs1 else None
if tpid:
    types = fe.terrain_types(OUT)
    w = [x for x in (types.get('items') or []) if x.get('writable')]
    want = 'desert'
    have = [x for x in (types.get('items') or []) if x.get('writable') and x.get('type') == want]
    if have:
        r2 = fe.prov_terrain_set(tpid, want, OUT)
        print('省 %s → %s: %s' % (tpid, want, r2.get('msg')))

# ---- 第 3 组：战略区 + 补给区 ----
print('\n=== 第 3 组：战略区 + 补给区 ===')
sr = fe.strategic_regions_list(OUT)
used = set()
for x in (sr.get('items') or []):
    used.update(x.get('provinces') or [])
free = [p for p in (fe.PROV_RGB or {}) if int(p) > 0 and int(p) not in used][:3]
if free:
    r3 = fe.strategic_region_create(OUT, None, 'VERIFY_REGION', free)
    print('战略区:', r3.get('msg'))
sts = provs1[:2] if len(provs1) >= 2 else provs1
if sts:
    # 补给区按"州号"关联，不是省号
    r4 = fe.supply_area_save(99, 15, [1, 2], 'VERIFY_AREA', OUT)
    print('补给区:', r4.get('msg'))

# ---- 输出生成的文件 ----
print('\n=== 生成的文件 ===')
for dp, _dn, fs in os.walk(OUT):
    for f in sorted(fs):
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, OUT)
        print('\n--- %s (%d 字节) ---' % (rel, os.path.getsize(p)))
        if f.endswith('.txt') or f.endswith('.mod'):
            head = io.open(p, encoding='utf-8-sig', errors='replace').read()
            print(head[:900])
