# -*- coding: utf-8 -*-
"""HOI4 脚本文本的解析与原子写入。

纯函数：只依赖 io / os / re。不读全局状态，不 import 上层。
从 focus_editor.py 原样搬过来（P0-2），行为一字未改。
"""
import io
import os
import re


def _strip_keep_len(text):
    """去注释但**保持字符长度不变**：注释内容替换成空格。

    需要「在去注释文本里定位、再回到原文改写」的场景必须用它，
    否则 strip_comments 截断注释会让偏移全错。"""
    out = []
    for line in text.splitlines(True):
        buf, instr, hit = [], False, False
        for c in line:
            if c == '"':
                instr = not instr
            if c == '#' and not instr:
                hit = True
            buf.append(' ' if (hit and c not in '\r\n') else c)
        out.append("".join(buf))
    return "".join(out)


def strip_comments(text):
    out = []
    for line in text.splitlines():
        buf, instr = [], False
        for c in line:
            if c == '"':
                instr = not instr
            if c == '#' and not instr:
                break
            buf.append(c)
        out.append("".join(buf))
    return "\n".join(out)


def brace_match(s, i):
    depth = 0
    instr = False
    while i < len(s):
        c = s[i]
        if c == '"':
            instr = not instr
        elif not instr:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return i


def unq(v):
    v = (v or "").strip()
    return v[1:-1] if len(v) >= 2 and v[0] == '"' and v[-1] == '"' else v


def top_items(body):
    items = []
    i, n = 0, len(body)
    while i < n:
        if body[i] in " \t\r\n":
            i += 1
            continue
        m = re.match(r'([A-Za-z0-9_.\-]+)\s*=\s*', body[i:])
        if not m:
            i += 1
            continue
        key = m.group(1)
        j = i + m.end()
        if j < n and body[j] == '{':
            end = brace_match(body, j)
            items.append((key, body[j + 1:end - 1], True))
            i = end
        else:
            k, instr = j, False
            while k < n:
                c = body[k]
                if c == '"':
                    instr = not instr
                if c == '\n' and not instr:
                    break
                k += 1
            items.append((key, unq(body[j:k]), False))
            i = k
    return items


def find_blocks(text, key):
    out = []
    for m in re.finditer(r'(?m)^\s*%s\s*=\s*\{' % key, text):
        start = text.find('{', m.start())
        if start < 0:
            continue
        end = brace_match(text, start)
        out.append((start, end, text[start + 1:end - 1]))
    return out


def _atomic_write(path, data):
    """原子写文件：先写同目录临时文件，成功后 os.replace 覆盖。

    直接写目标路径在写到一半崩溃/断电时会留下半截文件，
    原来的内容也没了。临时文件 + rename 保证要么是旧内容，要么是新内容。
    """
    path = os.path.abspath(path)
    d = os.path.dirname(path) or "."
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    tmp = "%s.tmp%d" % (path, os.getpid())
    try:
        with io.open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        raise


def _bom_for(path):
    """新建文件一律不加 BOM。

    HOI4 的解析器会把 BOM 吃进第一个 token：common/decisions 里新建的文件
    如果带 BOM，类别名会变成 "\ufeffXTT_category"，整个类别失效并刷报错。
    实测 HOI4 读无 BOM 的 UTF-8 完全正常，所以这里统一返回空。
    已有文件的 BOM 由各写入函数自己用 utf-8-sig 读取时保留，不走这个函数。
    """
    return b""


def _read_text(path):
    with io.open(path, encoding="utf-8-sig", errors="replace") as _f:
        return strip_comments(_f.read())


# ---- P0-3 B0：脚本块改写工具（set_scalar / remove_block / set_raw_block ...）----
def _first(text, pat, default=""):
    """取第一个匹配的 group(1)，没有就返回 default（不 strip，调用方自己处理）。"""
    m = re.search(pat, text)
    return m.group(1) if m else default


def _first_in(text, pat):
    m = re.search(pat, text, re.M)
    return m.group(1).strip() if m else ""



def set_scalar(block, key, value):
    ek = re.escape(key)
    pat = re.compile(r'(?m)^([ \t]*)%s[ \t]*=[ \t]*(?!\{)[^\s#]+' % ek)
    if pat.search(block):
        return pat.sub(lambda m: "%s%s = %s" % (m.group(1), key, value), block, count=1)
    # 块内已有同名子块 key = { ... } 时，不破坏也不重复插入同名标量
    if re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % ek, block):
        return block
    # 插入到 id 行后
    m = re.search(r'(?m)^([ \t]*)id[ \t]*=[ \t]*[^\n]+', block)
    if not m:
        return block
    indent = m.group(1)
    return block[:m.end()] + "\n" + indent + "%s = %s" % (key, value) + block[m.end():]



def remove_block(block, key):
    # 删除 block 顶层 key = { ... }（不处理嵌套同名，MVP 足够）
    out = []
    i = 0
    while True:
        m = re.search(r'(?m)^\s*%s\s*=\s*\{' % key, block[i:])
        if not m:
            out.append(block[i:])
            break
        s = i + m.start()
        out.append(block[i:s])
        b = block.find('{', s)
        e = brace_match(block, b)
        i = e
    return "".join(out)



def braces_balanced(text):
    depth = 0
    instr = False
    for c in text or "":
        if c == '"':
            instr = not instr
        elif not instr:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth < 0:
                    return False
    return depth == 0 and not instr



def _is_outer_script_block(block):
    """判断文本是否为外层命名块（如 idea_id = { ... }），区别于 focus.py 传入的内层体。"""
    s = (block or "").strip()
    m = re.match(r'^[A-Za-z0-9_.\-:]+\s*=\s*\{', s)
    if not m:
        return False
    b = s.find('{', m.start())
    return brace_match(s, b) == len(s)


def set_raw_block(block, key, content):
    """替换/删除/插入脚本块（支持外层命名块 idea/equip/tech/event 与 focus 内层体两种输入）。"""
    content = (content or "").strip("\n")
    m = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % key, block)
    if not content.strip():
        if m:
            start = m.start()
            b = block.find('{', m.start())
            e = brace_match(block, b)
            return block[:start] + block[e:]
        return block
    is_outer = _is_outer_script_block(block)
    outer_indent = "\t" if is_outer else "\t\t"
    inner_indent = outer_indent + "\t"
    lines = []
    for ln in content.splitlines():
        lines.append(inner_indent + ln.rstrip() if ln.strip() else "")
    newb = "%s%s = {\n%s\n%s}" % (outer_indent, key, "\n".join(lines), outer_indent)
    if m:
        start = m.start()
        b = block.find('{', start)
        e = brace_match(block, b)
        return block[:start] + newb + block[e:]
    if is_outer:
        last_rb = block.rfind("}")
        if last_rb != -1:
            return block[:last_rb].rstrip() + "\n" + newb + "\n" + block[last_rb:]
    return block.rstrip() + "\n" + newb + "\n\t"



# ---------------- 国家精神 ----------------
def apply_modifier_props(raw, props):
    mod_props = {
        k: v for k, v in (props or {}).items()
        if k and not str(k).endswith("_raw") and str(v).strip() != ""
    }
    if not mod_props:
        return raw
    m = re.search(r'(?m)^([ \t]*)modifier\s*=\s*\{', raw)
    if m:
        lead = m.group(1) or ""
        b = raw.find('{', m.start())
        e = brace_match(raw, b)
        inner = raw[b + 1:e - 1]
        lines = [ln.strip() for ln in inner.splitlines() if ln.strip()]
        for k, v in mod_props.items():
            pat = re.compile(r'^%s\s*=\s*[^\s#]+$' % re.escape(k))
            replaced = False
            for idx, ln in enumerate(lines):
                if pat.match(ln):
                    lines[idx] = "%s = %s" % (k, v)
                    replaced = True
                    break
            if not replaced:
                lines.append("%s = %s" % (k, v))
        body = "\n".join((lead + "\t" + ln) for ln in lines)
        new_block = "%smodifier = {\n%s\n%s}" % (lead, body, lead) if body else "%smodifier = {\n%s}" % (lead, lead)
        return raw[:m.start()] + new_block + raw[e:]

    # 块内原本没有 modifier = { ... } 时，插在最外层结尾 '}' 之前保持括号平衡
    block_lines = ["\tmodifier = {"]
    for k, v in mod_props.items():
        block_lines.append("\t\t%s = %s" % (k, v))
    block_lines.append("\t}")
    block_txt = "\n".join(block_lines)
    last_rb = raw.rfind("}")
    if last_rb != -1:
        return raw[:last_rb].rstrip() + "\n" + block_txt + "\n" + raw[last_rb:]
    return raw.rstrip() + "\n" + block_txt + "\n"


def brace_depth_at(text, pos):
    """计算无注释文本在 pos 处的花括号嵌套深度（忽略引号内字符）。"""
    d = 0
    instr = False
    for ch in text[:pos]:
        if ch == '"':
            instr = not instr
        elif not instr:
            if ch == '{':
                d += 1
            elif ch == '}':
                d -= 1
    return d


def date_block_spans(text):
    """返回顶层日期块 YYYY.MM.DD = { ... } 的起止区间列表。"""
    spans = []
    for m in re.finditer(r'(?m)^[ \t]*\d{3,4}\.\d+\.\d+[ \t]*=\s*\{', text):
        if brace_depth_at(text, m.start()) != 0:
            continue
        ob = text.find('{', m.end() - 1)
        if ob < 0:
            continue
        ce = brace_match(text, ob)
        if ce > ob:
            spans.append((m.start(), ce))
    return spans


def collect_top_blocks(text, key, include_date=False):
    """收集 key = { ... } 块，按 (depth == 0, 位置) 排序，可过滤日期块内部。"""
    dspans = date_block_spans(text)
    out = []
    for a, b, body in find_blocks(text, key):
        if not include_date and any(ds < a < de for ds, de in dspans):
            continue
        hdr = text.rfind(key, 0, a)
        depth = brace_depth_at(text, hdr if hdr >= 0 else a)
        out.append((depth, a, b, body))
    out.sort(key=lambda x: (0 if x[0] == 0 else 1, x[1]))
    return out, dspans


def append_into_block(raw, block_end_idx, line_text):
    """在块闭合 '}'（block_end_idx - 1）前追加一行，避免与 '}' 粘连。"""
    before = raw[:block_end_idx - 1].rstrip(" \t")
    nl = "" if (not before or before.endswith(("\n", "\r"))) else "\n"
    line = (line_text or "").rstrip("\r\n")
    return before + nl + line + "\n" + raw[block_end_idx - 1:]


def insert_before_date_or_end(raw, dspans, ins):
    """有顶层日期块时插在首个日期块之前，否则追加到文件末尾。"""
    if dspans:
        pos = dspans[0][0]
        return raw[:pos].rstrip(" \t") + "\n" + ins + "\n" + raw[pos:]
    return raw.rstrip() + "\n" + ins
