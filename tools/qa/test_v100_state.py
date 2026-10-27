import io
import os
import sys

sys.path.insert(0, '.')
import focus_editor as fe

fe.GAME = r"E:\SteamLibrary\steamapps\common\Hearts of Iron IV"
MOD = r"D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work\tmp\statetest"
fe.ROOTS = [MOD]
fe.load_states(MOD)

r = fe.state_create([221, 222, 223], MOD, name='雪绒测试州', category='town', manpower=88000)
print('结果:', {k: r.get(k) for k in ('ok', 'id', 'name', 'display', 'loc', 'provinces', 'file')})
print('note:', r.get('note'))

if r.get('loc'):
    p = os.path.join(MOD, r['loc'].replace('/', os.sep))
    raw = open(p, 'rb').read()
    print('loc 路径:', r['loc'])
    print('BOM 前 3 字节:', raw[:3].hex(), '(应为 efbbbf)')
    print('内容:', raw.decode('utf-8-sig').strip()[:80])

st = os.path.join(MOD, 'history', 'states')
print('\n州文件列表:')
for fn in sorted(os.listdir(st)):
    print('  ', fn)
    if fn.startswith(str(r.get('id'))):
        print('  内容:')
        for line in io.open(os.path.join(st, fn), encoding='utf-8').read().splitlines():
            print('    ' + line)

# 再读一遍，确认能解析回去
fe.STATES.clear()
fe.load_states(MOD)
back = fe.STATES.get(r.get('id')) or {}
print('\n重新载入:', r.get('id'), '→', back.get('name'), back.get('provinces'), back.get('category'))
