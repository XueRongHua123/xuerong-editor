# -*- coding: utf-8 -*-
"""联合国机制的本地化审计：引用键 ↔ 定义键、编码、重复、未使用。

只管 mvlv_un_* / mvlv119_un.* 这一套，不碰基座。
用法：
    python work/qa/_audit_un_loc.py
    python work/qa/_audit_un_loc.py --base <包目录>
退出码 1 = 有缺失或重复。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

LANGS = {
    'simp_chinese': 'localisation/simp_chinese/replace/zz_mvlv119_un_l_simp_chinese.yml',
    'english': 'localisation/english/replace/zz_mvlv119_un_l_english.yml',
}
FILES = [
    'events/zz_mvlv119_un_events.txt',
    'common/scripted_localisation/zz_mvlv119_un_loc.txt',
    'common/decisions/zz_mvlv119_un_decisions.txt',
    'common/decisions/categories/zz_mvlv119_un_categories.txt',
    'common/dynamic_modifiers/zz_mvlv119_un_modifiers.txt',
]


def load_keys(path):
    keys, dup = {}, []
    bad = []
    for ln in io.open(path, encoding='utf-8-sig', errors='replace'):
        s = ln.strip()
        if not s:
            continue
        if s in ('l_simp_chinese:', 'l_english:'):
            continue
        m = re.match(r'([A-Za-z0-9_.\-]+):(\d*)\s+"(.*)"$', s)
        if m:
            k = m.group(1)
            if k in keys:
                dup.append(k)
            keys[k] = m.group(2)
        else:
            # 非空、非头、不符合单行格式 = 坏行（多半是值里混进了真实换行）
            bad.append(s[:60])
    return keys, dup, bad


def check_bytes(path):
    raw = open(path, 'rb').read()
    issues = []
    if not raw.startswith(b'\xef\xbb\xbf'):
        issues.append('缺 BOM')
    if b'\r\n' not in raw:
        issues.append('换行不是 CRLF')
    return issues


def collect_refs(base):
    refs = {}
    for rel in FILES:
        p = os.path.join(base, rel)
        if not os.path.exists(p):
            continue
        t = io.open(p, encoding='utf-8-sig', errors='replace').read()
        # 事件/选项（scripted_localisation 里的 name 是 defined_text 名，不是 loc 键）
        if rel != FILES[1]:
            for m in re.finditer(r'(?m)^\s*(?:title|desc|name)\s*=\s*([A-Za-z0-9_.]+)', t):
                refs.setdefault(m.group(1), rel)
        # scripted loc
        for m in re.finditer(r'localization_key\s*=\s*([A-Za-z0-9_.]+)', t):
            refs.setdefault(m.group(1), rel)
        # tooltip
        for m in re.finditer(r'\btooltip\s*=\s*([A-Za-z0-9_.]+)', t):
            refs.setdefault(m.group(1), rel)
    # 决议 id 与分类 id
    dec = os.path.join(base, FILES[2])
    if os.path.exists(dec):
        t = io.open(dec, encoding='utf-8-sig', errors='replace').read()
        for m in re.finditer(r'(?m)^\t(mvlv_un_[a-z0-9_]+)\s*=\s*\{', t):
            refs.setdefault(m.group(1), FILES[2])
            refs.setdefault(m.group(1) + '_desc', FILES[2])
    cat = os.path.join(base, FILES[3])
    if os.path.exists(cat):
        t = io.open(cat, encoding='utf-8-sig', errors='replace').read()
        for m in re.finditer(r'(?m)^(mvlv_un_[a-z0-9_]+)\s*=\s*\{', t):
            refs.setdefault(m.group(1), FILES[3])
            refs.setdefault(m.group(1) + '_desc', FILES[3])
    # 动态修正
    mod = os.path.join(base, FILES[4])
    if os.path.exists(mod):
        t = io.open(mod, encoding='utf-8-sig', errors='replace').read()
        for m in re.finditer(r'(?m)^(mvlv_un_[a-z0-9_]+)\s*=\s*\{', t):
            refs.setdefault(m.group(1), FILES[4])
            refs.setdefault(m.group(1) + '_desc', FILES[4])
    return refs


def main():
    base = sys.argv[sys.argv.index('--base') + 1] if '--base' in sys.argv else None
    if base is None:
        from _paths import OUT, OUT_WORK  # noqa: E402
        base = OUT_WORK if os.path.isdir(OUT_WORK) else OUT
    print('包目录:', base)

    refs = collect_refs(base)
    all_keys = {}
    fail = False
    for lang, rel in LANGS.items():
        p = os.path.join(base, rel)
        if not os.path.exists(p):
            print('  [!] 缺语言文件:', rel)
            fail = True
            continue
        keys, dup, bad = load_keys(p)
        all_keys[lang] = keys
        issues = check_bytes(p)
        print('  %-12s %d 键%s' % (lang, len(keys), '' if not issues else '  [' + '、'.join(issues) + ']'))
        if issues:
            fail = True
        for s in bad[:10]:
            print('  [!] %s 坏行（值疑似跨行）: %s' % (lang, s))
            fail = True
        if len(bad) > 10:
            print('  [!] %s 还有 %d 行坏行未列出' % (lang, len(bad) - 10))
        for k in sorted(set(dup)):
            print('  [!] %s 重复键: %s' % (lang, k))
            fail = True
        missing = sorted(k for k in refs if k not in keys)
        for k in missing:
            print('  [!] %s 缺键: %s（%s 引用）' % (lang, k, refs[k]))
            fail = True

    if len(all_keys) == 2:
        a, b = (set(all_keys['simp_chinese']), set(all_keys['english']))
        only_zh = sorted(a - b)
        only_en = sorted(b - a)
        if only_zh or only_en:
            print('  [!] 中英键集合不一致：仅中 %d，仅英 %d' % (len(only_zh), len(only_en)))
            for k in only_zh[:10]:
                print('      仅中:', k)
            for k in only_en[:10]:
                print('      仅英:', k)
            fail = True
        else:
            print('  中英键集合一致（%d 键）' % len(a))
        unused = sorted(k for k in a if k not in refs)
        print('  未被脚本引用 %d 键（事件选项/预留键属正常）' % len(unused))

    print('\n结论:', 'FAIL' if fail else 'PASS')
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
