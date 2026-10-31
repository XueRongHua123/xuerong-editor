# -*- coding: utf-8 -*-
""".cwt 规则解析器（最小可用）。

只做一件事：从规则里提取「块名 → 允许的字段名集合」。

设计取舍：宁松勿严。跨层级把所有字段都收进来，宁可白名单大一点少报，
也不要因为漏解析某个写法而误报。

规则来源：cwtools/cwtools-hoi4-config（MIT）。
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')

# 这些顶层块是元数据，不是 schema
SKIP_BLOCKS = {'types', 'enums', 'localisation'}

# 这些前缀是规则的元语法，里面的标识符不是数据字段
_META = ('enum[', 'alias_name[', 'single_alias[', 'value_set[',
         'type[', 'scope[', 'target[', 'alias_match_left[', 'alias_match_right[')

_CACHE = {}
_FIELD_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_.]*)\s*[=<>]')


def _strip_comments(text):
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith('#'):
            continue
        out.append(ln)
    return '\n'.join(out)


def _brace_blocks(text):
    """遍历文本里的 `名字 = {` 块（顶层，不含嵌套），产出 (名字, 块内文本)。"""
    i = 0
    n = len(text)
    pat = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{')
    while i < n:
        m = pat.search(text, i)
        if not m:
            return
        start = m.end() - 1
        depth = 0
        j = start
        while j < n:
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth != 0:
            return
        yield m.group(1), text[start + 1:j]
        i = j + 1


def _fields_of(block_text):
    """块里出现的所有字段名（不分层级）。

    不区分层级是有意的：`.cwt` 用 `subtype[xxx] = { }` 分组，
    同名字段在不同分组里出现很正常。跨层收集只会让白名单变大，不会漏。
    """
    out = set()
    for ln in block_text.splitlines():
        s = ln.strip()
        if not s or s.startswith('#'):
            continue
        # 跳过元语法行（enum[...] = ... / alias_name[...] = ...）
        if s.startswith(_META):
            continue
        m = _FIELD_RE.match(s)
        if not m:
            continue
        name = m.group(1)
        if name in ('subtype',):
            continue
        out.add(name)
    return out


def load_rules(verbose=False):
    """读全部 .cwt，返回 {块名: set(字段)}。同名块跨文件合并。"""
    if _CACHE:
        return _CACHE
    rules = {}
    if not os.path.isdir(RAW):
        return rules
    files = []
    for root, _dirs, fs in os.walk(RAW):
        for fn in sorted(fs):
            if fn.endswith('.cwt'):
                files.append(os.path.join(root, fn))
    for p in files:
        try:
            text = io.open(p, encoding='utf-8-sig', errors='replace').read()
        except Exception:
            continue
        text = _strip_comments(text)
        for name, body in _brace_blocks(text):
            if name in SKIP_BLOCKS:
                continue
            flds = _fields_of(body)
            if not flds:
                continue
            rules.setdefault(name, set()).update(flds)
    if verbose:
        print('规则块数: %d（来自 %d 个 .cwt）' % (len(rules), len(files)))
    _CACHE.update(rules)
    return _CACHE


def allowed_fields(block, rules=None):
    """某个块允许的字段；块不存在返回 None（表示不检查）。"""
    r = rules if rules is not None else load_rules()
    return r.get(block)


def load_trigger_effect_names():
    """提取所有 trigger / effect 的名字。

    这两个不用块定义，是 `alias[trigger:if] = ...` / `alias[effect:add_x] = ...`，
    所以要单独扫一遍。有了这张表，检查字段时就能放过 trigger/effect 关键字。
    """
    global _TRIG_CACHE
    if '_TRIG_CACHE' in globals() and _TRIG_CACHE:
        return _TRIG_CACHE
    names = set()
    if not os.path.isdir(RAW):
        _TRIG_CACHE = names
        return names
    pat = re.compile(r'alias\[(trigger|effect):([A-Za-z_][A-Za-z0-9_]*)\]')
    for root, _dirs, fs in os.walk(RAW):
        for fn in sorted(fs):
            if not fn.endswith('.cwt'):
                continue
            try:
                text = io.open(os.path.join(root, fn), encoding='utf-8-sig',
                               errors='replace').read()
            except Exception:
                continue
            for m in pat.finditer(text):
                names.add(m.group(2))
    _TRIG_CACHE = names
    return names


if __name__ == '__main__':
    r = load_rules(verbose=True)
    print()
    te = load_trigger_effect_names()
    print('trigger/effect 名字: %d 个' % len(te))
    print('   样例:', ', '.join(sorted(te)[:10]))
    print()
    for k in ('oob', 'character', 'bookmark', 'country', 'division_template', 'decision', 'idea'):
        f = r.get(k)
        if f:
            print('%-20s %3d 个字段' % (k, len(f)))
            print('     ', ', '.join(sorted(f)[:12]))
        else:
            print('%-20s 没有' % k)
