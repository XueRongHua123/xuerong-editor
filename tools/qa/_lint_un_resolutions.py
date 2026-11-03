# -*- coding: utf-8 -*-
"""议题注册表检查器：注册表 / 效果块 / 条件块 / 本地化 四者对齐。

为什么要有它：
  议题一旦多到 30 项，「注册表登记了但没写效果」「写了效果但没写 loc」「效果里顺手用了
  不在词汇表里的原语」这三类错会同时出现。靠人眼查不现实，靠游戏报错也查不出来
  （HOI4 对未知 effect 大多只是静默忽略）。

用法：
    python work/qa/_lint_un_resolutions.py
    python work/qa/_lint_un_resolutions.py --strict   # 游戏侧未实现也算失败

退出码 0 = 没有硬错误；1 = 有。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FAIL = []
WARN = []

# 议题效果块里允许出现的顶层键：五类原语 + 控制流。
# 超出这张表的，要么拆成别的效果块，要么在块里写一行 "# special: 原因"。
ALLOWED = {
    # 修正
    'add_dynamic_modifier', 'remove_dynamic_modifier', 'add_timed_idea',
    'add_ideas', 'remove_ideas', 'swap_ideas',
    # 资源
    'add_offsite_building', 'add_equipment_to_stockpile', 'add_manpower',
    'add_political_power', 'add_command_power', 'add_stability', 'add_war_support',
    # 科技
    'add_tech_bonus', 'set_technology',
    # 变量
    'add_to_variable', 'subtract_from_variable', 'set_variable',
    'multiply_variable', 'set_variable_to_random',
    # 表态
    'add_opinion', 'set_country_flag', 'clr_country_flag', 'set_global_flag',
    'clr_global_flag', 'country_event', 'news_event',
    # 控制流
    'if', 'else', 'else_if', 'limit', 'every_country', 'any_country',
    'random_list', 'random', 'tooltip', 'custom_effect_tooltip', 'custom_tooltip',
    'hidden_effect', 'log',
}

CONTROL = {'if', 'else', 'else_if', 'limit', 'every_country', 'any_country',
           'random_list', 'random', 'tooltip', 'custom_effect_tooltip',
           'custom_tooltip', 'hidden_effect', 'log'}


def fail(msg):
    FAIL.append(msg)
    print('  [!] ' + msg)


def warn(msg):
    WARN.append(msg)
    print('  [~] ' + msg)


def block_of(text, name):
    """取 `name = { ... }` 的块体，花括号配平；跳过注释和字符串。返回 (body, start, end)。"""
    m = re.search(r'(?m)^\s*%s\s*=\s*\{' % re.escape(name), text)
    if not m:
        return None, -1, -1
    i = text.index('{', m.start())
    depth, j, in_str = 0, i, False
    while j < len(text):
        ch = text[j]
        if ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == '#':
                nl = text.find('\n', j)
                j = len(text) if nl < 0 else nl
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[i + 1:j], m.start(), j
        j += 1
    return None, m.start(), -1


def top_keys(body):
    """块内第一层的键名。"""
    keys, depth = [], 0
    for raw in body.splitlines():
        line = raw.split('#', 1)[0]
        if not line.strip():
            continue
        if depth == 0:
            m = re.match(r'\s*([A-Za-z0-9_]+)\s*=', line)
            if m:
                keys.append(m.group(1))
        depth += line.count('{') - line.count('}')
    return keys


def load_package_text(base, sub):
    path = os.path.join(base, sub)
    out = []
    if not os.path.isdir(path):
        return None
    for dp, _, fs in os.walk(path):
        for f in fs:
            if f.endswith('.txt') or f.endswith('.yml'):
                out.append(io.open(os.path.join(dp, f), encoding='utf-8-sig',
                                   errors='replace').read())
    return '\n'.join(out)


def loc_keys(base):
    keys = set()
    ldir = os.path.join(base, 'localisation')
    if not os.path.isdir(ldir):
        return keys
    for dp, _, fs in os.walk(ldir):
        for f in fs:
            if not f.endswith('.yml'):
                continue
            for ln in io.open(os.path.join(dp, f), encoding='utf-8-sig', errors='replace'):
                m = re.match(r'\s*([A-Za-z0-9_.\-]+):\d*\s+"', ln)
                if m:
                    keys.add(m.group(1))
    return keys


def main():
    strict = '--strict' in sys.argv
    reg_path = os.path.join(HERE, 'un_resolutions.json')
    if not os.path.exists(reg_path):
        print('缺注册表：%s' % reg_path)
        return 1
    reg = json.load(io.open(reg_path, encoding='utf-8'))
    rules = reg.get('rules', {})
    types = set(rules.get('types', ['ga', 'sc']))
    members = set(rules.get('member_tags', []))
    items = reg.get('resolutions', [])

    print('=== 1. 注册表结构 ===')
    print('  议题 %d 项；类型 %s；会员国 %d 个' % (len(items), '/'.join(sorted(types)), len(members)))
    seen = set()
    for r in items:
        rid = r.get('id', '')
        if not re.match(r'^[a-z][a-z0-9_]*$', rid):
            fail('id 非法（只许小写字母数字下划线）：%r' % rid)
        if rid in seen:
            fail('id 重复：%s' % rid)
        seen.add(rid)
        if r.get('type') not in types:
            fail('%s: type=%r 不在 %s' % (rid, r.get('type'), sorted(types)))
        for k in ('cost', 'pp_cost', 'cooldown'):
            v = r.get(k)
            if not isinstance(v, int) or v < 0:
                fail('%s: %s 必须是非负整数，实际 %r' % (rid, k, v))
        if r.get('allow') != 'mvlv_un_allow_' + rid:
            fail('%s: allow 应命名为 mvlv_un_allow_%s' % (rid, rid))
        if r.get('effect') != 'mvlv_un_res_' + rid:
            fail('%s: effect 应命名为 mvlv_un_res_%s' % (rid, rid))
        loc = r.get('loc') or []
        want = ['mvlv_un_res_%s_%s' % (rid, s) for s in ('name', 'desc', 'yes', 'no')]
        if loc != want:
            fail('%s: loc 应为 %s' % (rid, want))
        interest = r.get('interest') or {}
        if 'default' not in interest or not isinstance(interest['default'], int):
            fail('%s: interest 缺 default 或不是整数' % rid)
        for tag, v in interest.items():
            if tag != 'default' and tag not in members:
                fail('%s: interest 里的 %s 不是会员国 tag' % (rid, tag))
            if not isinstance(v, int) or not -30 <= v <= 30:
                fail('%s: interest[%s]=%r 必须是 -30..30 的整数' % (rid, tag, v))
    if not FAIL:
        print('  结构检查通过')

    print('\n=== 2. 游戏侧对齐 ===')
    base = None
    if '--base' in sys.argv:
        base = sys.argv[sys.argv.index('--base') + 1]
    if base is None:
        try:
            from _paths import OUT, OUT_WORK  # noqa: E402
        except ImportError:
            fail('找不到 _paths.py，或改用 --base <包目录> 指定')
            return 1
        base = OUT_WORK if os.path.isdir(OUT_WORK) else OUT
    effects = load_package_text(base, 'common/scripted_effects')
    triggers = load_package_text(base, 'common/scripted_triggers')
    if effects is None or 'mvlv_un_res_' not in (effects or ''):
        print('  游戏侧还没有实现（找不到 mvlv_un_res_*）')
        if strict:
            fail('--strict：注册表有 %d 项，游戏侧 0 项' % len(items))
        else:
            print('  跳过；实现后重跑这项')
    else:
        for r in items:
            rid = r['id']
            body, _, end = block_of(effects, r['effect'])
            if body is None:
                fail('%s: 缺效果块 %s' % (rid, r['effect']))
                continue
            if end < 0:
                fail('%s: 效果块花括号不配平' % rid)
                continue
            if body.count(r['effect']) > 1:
                warn('%s: 效果块里出现同名调用，检查是不是递归' % rid)
            keys = [k for k in top_keys(body) if k not in CONTROL]
            bad = [k for k in keys if k not in ALLOWED and k not in members]
            if bad and '# special:' not in body:
                fail('%s: 用了词汇表外的 effect %s（要保留就写 "# special: 原因"）' % (rid, bad))
            if block_of(triggers or '', r['allow'])[0] is None:
                fail('%s: 缺条件块 %s' % (rid, r['allow']))
        locs = loc_keys(base)
        for r in items:
            miss = [k for k in r['loc'] if k not in locs]
            if miss:
                fail('%s: 缺 loc 键 %s' % (r['id'], miss))
        print('  对齐检查完成')

    print('\n=== 结论 ===')
    if FAIL:
        print('  FAIL：%d 项' % len(FAIL))
        return 1
    print('  PASS：注册表结构合法%s' % ('，游戏侧已对齐' if effects and 'mvlv_un_res_' in effects else '（游戏侧待实现）'))
    if WARN:
        print('  警告 %d 条' % len(WARN))
    return 0


if __name__ == '__main__':
    sys.exit(main())
