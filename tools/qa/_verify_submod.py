# -*- coding: utf-8 -*-
"""submod 静态验证：路径自检 / 花括号 / gfx 图片 / 本地化 key / 覆盖关系。

与旧版的区别：
  * 路径统一从 _paths.py 取（换机器只改一处，或设环境变量）
  * gfx 图片查五个根（OUT/CN/SUB/HIS/GAME），分清「未随包但上层有」和「五根都没有」
  * 覆盖关系多查一项：submod 副本与基座 md5 是否真的不同（相同 = 白拷，可删）
  * 末尾给 PASS/FAIL 总结论，退出码 0/1，便于挂 CI 或批处理

用法：
    python work/qa/_verify_submod.py
"""
import hashlib
import io
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _paths import (CN, CHG, GAME, HIS, MODDIR, OUT, OUT_WORK, SUB,  # noqa: E402
                    WORKSHOP_ID, check_roots, p)

FAIL = []


def fail(msg):
    FAIL.append(msg)
    print('  [!] ' + msg)


def brace_ok(text):
    """花括号配平（跳过 # 行注释）"""
    text = re.sub(r'#[^\n]*', '', text)
    d = 0
    for ch in text:
        if ch == '{':
            d += 1
        elif ch == '}':
            d -= 1
            if d < 0:
                return False, d
    return d == 0, d


def md5_of(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def png_size(path):
    """直接读 PNG 的 IHDR 拿宽高。

    原先用 PIL，本机没装时只打印一句「读不出尺寸」然后跳过检查，
    封面尺寸这项等于没查。PNG 头是固定格式，读 24 字节就够，不需要第三方库。
    """
    with open(path, 'rb') as fh:
        head = fh.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('文件头不是 PNG')
    if head[12:16] != b'IHDR':
        raise ValueError('缺 IHDR 块')
    return struct.unpack('>II', head[16:24])


def tree_index(base):
    """相对路径 -> md5。"""
    idx = {}
    for dp, _, fs in os.walk(base):
        for f in fs:
            full = os.path.join(dp, f)
            idx[os.path.relpath(full, base).replace(os.sep, '/')] = md5_of(full)
    return idx


def tree_diff(a, b):
    """两份目录的差异清单：只在一边、或两边内容不同。"""
    ia, ib = tree_index(a), tree_index(b)
    return sorted(set(ia) ^ set(ib) | {k for k in ia if k in ib and ia[k] != ib[k]})


def main():
    print('=== 0. 路径自检 ===')
    print('  OUT  = %s' % OUT)
    print('  CN   = %s' % CN)
    print('  SUB  = %s' % SUB)
    print('  HIS  = %s' % HIS)
    print('  GAME = %s' % GAME)
    if not check_roots():
        print('\n结论: FAIL（路径不全，先修 _paths.py）')
        return 1
    total = sum(len(fs) for _, _, fs in os.walk(OUT))
    size = sum(os.path.getsize(os.path.join(dp, f))
               for dp, _, fs in os.walk(OUT) for f in fs)
    print('  文件 %d 个, %.2f MB' % (total, size / 1048576))

    # 磁盘上有两份同名副本（维护链 mods\ 与包目录 mod\），日常改动落在维护链、
    # 本脚本校验的是包目录。两边一旦不同，校验结论就不覆盖刚改的东西，
    # 所以这里直接把差异数出来，不让它静默存在。
    if os.path.isdir(OUT_WORK) and os.path.abspath(OUT_WORK) != os.path.abspath(OUT):
        diff = tree_diff(OUT, OUT_WORK)
        print('  维护链 = %s' % OUT_WORK)
        if diff:
            print('  维护链与包目录差异 %d 个文件（本次校验只覆盖包目录）' % len(diff))
            for rel in diff[:10]:
                print('     %s' % rel)
            if len(diff) > 10:
                print('     ...（共 %d 个）' % len(diff))
        else:
            print('  维护链与包目录一致（md5 全同）')

    print('\n=== 1. 花括号配平 ===')
    bad = []
    for dp, _, fs in os.walk(OUT):
        for f in fs:
            if not f.endswith(('.txt', '.gfx', '.gui')):
                continue
            path = os.path.join(dp, f)
            rel = os.path.relpath(path, OUT)
            try:
                t = io.open(path, encoding='utf-8-sig', errors='replace').read()
            except Exception as e:
                fail('读不了 %s: %s' % (rel, e))
                continue
            ok, d = brace_ok(t)
            if not ok:
                bad.append((rel, d))
    if bad:
        for r, d in bad:
            fail('花括号不平: %s (depth=%d)' % (r, d))
    else:
        print('  全部配平')

    print('\n=== 2. gfx 引用的图片（五根）===')
    refs = {}
    for dp, _, fs in os.walk(OUT):
        for f in fs:
            if not f.endswith(('.gfx', '.gui')):
                continue
            t = io.open(os.path.join(dp, f), encoding='utf-8-sig',
                        errors='replace').read()
            for m in re.finditer(r'(?:texturefile|textureFile|picture)\s*=\s*"([^"]+)"', t):
                refs[m.group(1).replace('\\', '/')] = os.path.relpath(
                    os.path.join(dp, f), OUT)
    roots = (('OUT', OUT), ('CN', CN), ('SUB', SUB), ('HIS', HIS), ('GAME', GAME))
    nowhere, notpacked = [], []
    for r in sorted(refs):
        where = [k for k, v in roots if os.path.exists(p(v, r))]
        if not where:
            nowhere.append(r)
        elif 'OUT' not in where:
            notpacked.append((r, where))
    print('  引用 %d 个图片；随包 %d，未随包但上层有 %d，五根都没有 %d'
          % (len(refs), len(refs) - len(notpacked) - len(nowhere),
             len(notpacked), len(nowhere)))
    for r, where in notpacked:
        only_his = where == ['HIS']
        print('    未随包: %-56s %s%s' % (r, '+'.join(where),
                                         '  <-- 只有适配版有，必须随包' if only_his else ''))
        if only_his:
            fail('图片只在适配版里、没随包: ' + r)
    for r in nowhere:
        fail('图片五根都没有: %s（%s 引用）' % (r, refs[r]))

    print('\n=== 3. 本地化 key ===')
    defined = set()
    for dp, _, fs in os.walk(os.path.join(OUT, 'localisation')):
        for f in fs:
            if not f.endswith('.yml'):
                continue
            for ln in io.open(os.path.join(dp, f), encoding='utf-8-sig',
                              errors='replace'):
                m = re.match(r'\s*([A-Za-z0-9_.\-]+):\d*\s+"', ln)
                if m:
                    defined.add(m.group(1))
    print('  submod 定义 %d 个 key' % len(defined))

    base_keys = set()
    for base in (CN, SUB):
        ldir = os.path.join(base, 'localisation')
        for dp, _, fs in os.walk(ldir):
            for f in fs:
                if not f.endswith('.yml'):
                    continue
                try:
                    for ln in io.open(os.path.join(dp, f), encoding='utf-8-sig',
                                      errors='replace'):
                        m = re.match(r'\s*([A-Za-z0-9_.\-]+):\d*\s+"', ln)
                        if m:
                            base_keys.add(m.group(1))
                except Exception:
                    pass
    print('  基座定义 %d 个 key' % len(base_keys))

    used = set()
    namespaces = set()
    for dp, _, fs in os.walk(OUT):
        for f in fs:
            if not f.endswith(('.txt', '.gui')):
                continue
            t = io.open(os.path.join(dp, f), encoding='utf-8-sig',
                        errors='replace').read()
            for m in re.finditer(r'\b(mvlv119_[A-Za-z0-9_.\-]+|zz_mvlv[A-Za-z0-9_.\-]*)', t):
                used.add(m.group(1))
            for m in re.finditer(r'add_namespace\s*=\s*([A-Za-z0-9_\-]+)', t):
                namespaces.add(m.group(1))
    # 事件命名空间不是 loc key；事件 ID 形如 mvlv119_dust.3 也不是
    missing = [u for u in sorted(used)
               if u not in defined and u not in base_keys
               and u not in namespaces
               and not re.search(r'\.\d+$', u)]
    print('  代码引用 %d 个 mvlv 前缀标识符；其中事件命名空间 %d 个，缺 %d 个'
          % (len(used), len(namespaces), len(missing)))
    for m in missing[:20]:
        print('    缺: %s' % m)
    if missing:
        fail('loc key 缺失 %d 个' % len(missing))

    print('\n=== 4. %d 个覆盖文件 vs 基座 ===' % len(CHG))
    same, diff, noup = 0, 0, 0
    for rel in CHG:
        mine = p(OUT, rel)
        if not os.path.exists(mine):
            fail('声明覆盖但包里没有: ' + rel)
            noup += 1
            continue
        where = [n for n, v in (('SUB', SUB), ('CN', CN)) if os.path.exists(p(v, rel))]
        if not where:
            print('  %-52s 基座没有（等同新增）' % rel)
            noup += 1
            continue
        m_mine = md5_of(mine)
        identical = any(md5_of(p(v, rel)) == m_mine for v in (SUB, CN)
                        if os.path.exists(p(v, rel)))
        if identical:
            print('  %-52s 覆盖 %-7s 与基座完全相同（白拷，可删）'
                  % (rel, '+'.join(where)))
            same += 1
        else:
            print('  %-52s 覆盖 %-7s 有差异（确实改过）'
                  % (rel, '+'.join(where)))
            diff += 1
    print('  有差异 %d, 与基座相同 %d, 基座无此文件 %d' % (diff, same, noup))
    if same:
        print('  提示：与基座完全相同的副本可以直接删掉，减少日后合并负担')

    print('\n=== 6. 开局音乐链路 ===')
    # 6.1 触发链：on_actions 里有没有挂上，挂的事件有没有定义
    hook_ok = event_ids = 0
    for dp, _, fs in os.walk(p(OUT, 'common/on_actions')):
        for f in fs:
            if not f.endswith('.txt'):
                continue
            t = io.open(os.path.join(dp, f), encoding='utf-8-sig',
                        errors='replace').read()
            if re.search(r'on_startup\s*=', t):
                hook_ok += 1
    ev_defined = set()
    for dp, _, fs in os.walk(p(OUT, 'events')):
        for f in fs:
            if f.endswith('.txt'):
                t = io.open(os.path.join(dp, f), encoding='utf-8-sig',
                            errors='replace').read()
                for m in re.finditer(r'^\s*id\s*=\s*([A-Za-z0-9_.]+)', t, re.M):
                    ev_defined.add(m.group(1))
    fired = set()
    for dp, _, fs in os.walk(p(OUT, 'common/on_actions')):
        for f in fs:
            if f.endswith('.txt'):
                t = io.open(os.path.join(dp, f), encoding='utf-8-sig',
                            errors='replace').read()
                for m in re.finditer(r'country_event\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.]+)', t):
                    fired.add(m.group(1))
    orphan = sorted(e for e in fired if e not in ev_defined)
    print('  含 on_startup 的 on_action 文件 %d 个；触发的事件 %d 个，未定义 %d 个'
          % (hook_ok, len(fired), len(orphan)))
    for e in orphan:
        fail('on_action 触发的事件没有定义: ' + e)
    if not hook_ok:
        fail('common/on_actions 里没有 on_startup 钩子')

    # 6.2 歌曲本体：play_song 引用 vs music/*.asset 里的 name 定义
    used_songs = {}
    for dp, _, fs in os.walk(OUT):
        for f in fs:
            if not f.endswith(('.txt', '.asset')):
                continue
            t = io.open(os.path.join(dp, f), encoding='utf-8-sig',
                        errors='replace').read()
            for m in re.finditer(r'\b(?:scoped_play_song|play_song)\s*=\s*"([^"]+)"', t):
                used_songs[m.group(1)] = os.path.relpath(
                    os.path.join(dp, f), OUT)
    defined_songs = {}
    for base, label in ((OUT, 'OUT'), (CN, 'CN'), (SUB, 'SUB'), (GAME, 'GAME')):
        mdir = os.path.join(base, 'music')
        if not os.path.isdir(mdir):
            continue
        for dp, _, fs in os.walk(mdir):
            for f in fs:
                if not f.lower().endswith(('.asset', '.txt')):
                    continue
                t = io.open(os.path.join(dp, f), encoding='utf-8-sig',
                            errors='replace').read()
                for m in re.finditer(r'music\s*=\s*\{(.*?)\}', t, re.S):
                    blk = m.group(1)
                    nm = re.search(r'name\s*=\s*"([^"]+)"', blk)
                    if not nm:
                        continue      # music = { song = ... } 是播放列表项，不是本体
                    fl = re.search(r'file\s*=\s*"([^"]+)"', blk)
                    # file 相对「该 .asset 所在目录」，而不是 music/ 根
                    defined_songs[nm.group(1)] = (label, fl.group(1) if fl else None, dp)
    print('  代码引用 %d 首歌；四方 music/ 里注册了 %d 首'
          % (len(used_songs), len(defined_songs)))
    silent = sorted(s for s in used_songs if s not in defined_songs)
    for s in silent:
        fail('歌曲没有本体定义（会报 Could not find music named）: %s（%s 引用）'
             % (s, used_songs[s]))
    if not silent and used_songs:
        print('  引用的歌全部有本体定义')

    # 6.3 本包引用的歌，ogg 实体是否存在（只查自己引用的，基座曲库不归这里管）
    noloc = []
    for name in sorted(used_songs):
        if name not in defined_songs:
            continue
        label, file, asset_dir = defined_songs[name]
        if not file:
            continue
        # 惯例不统一：有的 mod 相对 music/ 根写，有的相对 .asset 所在目录写，两种都认
        cands = [os.path.join(asset_dir, file.replace('/', os.sep))]
        for b in (OUT, CN, SUB, GAME):
            cands.append(os.path.join(b, 'music', file.replace('/', os.sep)))
        if not any(os.path.exists(c) for c in cands):
            noloc.append((name, label, file))
    for name, label, file in noloc:
        print('    ogg 找不到: %-18s %s (%s 注册)' % (name, file, label))
    if noloc:
        fail('%d 首被引用的歌 ogg 缺失（播放时会静音）' % len(noloc))
    else:
        print('  引用的歌 ogg 全部就位')

    # 6.4 覆盖安全性：本包覆盖基座的音乐文件后，基座原有的条目有没有丢
    for rel in ('music/music.asset', 'music/_songs.txt'):
        base_p, mine = p(CN, rel), p(OUT, rel)
        if not (os.path.exists(base_p) and os.path.exists(mine)):
            continue
        key = 'name' if rel.endswith('.asset') else 'song'

        def songs_in(path):
            t = io.open(path, encoding='utf-8-sig', errors='replace').read()
            got = set()
            for m in re.finditer(r'music\s*=\s*\{(.*?)\}', t, re.S):
                k = re.search(r'%s\s*=\s*"([^"]+)"' % key, m.group(1))
                if k:
                    got.add(k.group(1))
            return got

        bn, mn = songs_in(base_p), songs_in(mine)
        lost = bn - mn
        if lost:
            fail('%s 覆盖后丢了基座的条目（基座更新过，重新跑 _build_submod.py）: %s'
                 % (rel, ', '.join(sorted(lost))))
        else:
            print('    %s 覆盖安全（基座 %d 项全在）' % (rel, len(bn)))

    print('\n=== 7. 上传创意工坊前置项 ===')
    # descriptor 必须有的字段
    desc = p(OUT, 'descriptor.mod')
    if not os.path.exists(desc):
        fail('缺 descriptor.mod（上传必需）')
    else:
        t = io.open(desc, encoding='utf-8-sig', errors='replace').read()
        for field, why in (('name=', '创意工坊标题'),
                           ('version=', '版本号'),
                           ('picture=', '缩略图声明'),
                           ('supported_version=', '游戏版本'),
                           ('dependencies=', '依赖声明')):
            if field not in t:
                fail('descriptor.mod 缺 %s（%s）' % (field.rstrip('='), why))
        nm = re.search(r'name\s*=\s*"([^"]+)"', t)
        print('  标题: %s' % (nm.group(1) if nm else '（读不到）'))
        rid = re.search(r'remote_file_id\s*=\s*"(\d+)"', t)
        if rid is None:
            print('  remote_file_id: 无（首次上传前正常，上传后由启动器回写）')
        elif rid.group(1) != WORKSHOP_ID:
            fail('descriptor 的 remote_file_id=%s 与 _paths.WORKSHOP_ID=%s 不一致，'
                 '上传会指向别的作品' % (rid.group(1), WORKSHOP_ID))
        else:
            print('  remote_file_id: %s（与 WORKSHOP_ID 一致）' % rid.group(1))

    # 外部 .mod：三个位置都可能承载，按「游戏实际读哪个」报告
    from _paths import STEAM_COPY, load_base  # noqa: E402
    ext_local = os.path.join(MODDIR, os.path.basename(OUT) + '.mod')
    ext_steam = os.path.join(MODDIR, 'ugc_%s.mod' % WORKSHOP_ID)
    print('  加载点: %s' % load_base())
    if os.path.isdir(STEAM_COPY):
        print('  工坊副本: %s（已订阅，游戏读这份）' % STEAM_COPY)
    if not (os.path.exists(ext_local) or os.path.exists(ext_steam)):
        fail('缺外部 .mod：%s 和 ugc_%s.mod 都不在，启动器里不会出现这个 mod'
             % (os.path.basename(ext_local), WORKSHOP_ID))
    else:
        for p_, label in ((ext_local, '本地自建'), (ext_steam, 'Steam 订阅')):
            if not os.path.exists(p_):
                continue
            t = io.open(p_, encoding='utf-8-sig', errors='replace').read()
            m = re.search(r'path\s*=\s*"([^"]+)"', t)
            print('  %s .mod: %s -> %s'
                  % (label, os.path.basename(p_), (m.group(1) if m else '缺 path=')))
            if m and not os.path.isdir(m.group(1).replace('/', '\\')):
                fail('%s 的 path 指向不存在的目录：%s' % (label, m.group(1)))

    # 缩略图
    thumb = p(OUT, 'thumbnail.png')
    if not os.path.exists(thumb):
        fail('缺 thumbnail.png（创意工坊封面）')
    else:
        try:
            w, h = png_size(thumb)
            ok = w == h and w >= 256
            print('  缩略图: %dx%d, %d bytes%s'
                  % (w, h, os.path.getsize(thumb),
                     '' if ok else '  <-- 建议正方形且不小于 256'))
            if not ok:
                fail('缩略图建议正方形，不小于 256x256')
        except Exception as e:
            fail('缩略图读不出尺寸（%s），无法确认封面合格' % e)

    print('\n=== 结论 ===')
    if FAIL:
        print('  FAIL：%d 项' % len(FAIL))
        for f in FAIL:
            print('   - ' + f)
        return 1
    print('  PASS：花括号全配平，图片引用全部可解析，loc key 无真缺，覆盖关系与清单一致')
    print('  校验对象：%s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
