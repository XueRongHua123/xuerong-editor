# -*- coding: utf-8 -*-
"""把 MediaWiki wikitext 清洗成可读 markdown（去 ref / 模板 / 链接标记）。

用法：
    python work/qa/_wiki2md.py <input.json> <output.md> [--toc]

input.json 是 action=parse&prop=wikitext&formatversion=2 的返回。
--toc 只打印各标题的字数概览，不写文件。
"""
import html
import io
import json
import re
import sys


def clean(text):
    # 引用/脚注
    text = re.sub(r'<ref[^>]*/\s*>', '', text)
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.S)
    text = re.sub(r'<references\s*/?>', '', text)
    # HTML 标签（保留 <br> 的换行语义）
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</?[a-zA-Z][^>]*>', '', text)
    # 模板：{{...}} 嵌套，反复剥
    for _ in range(6):
        new = re.sub(r'\{\{[^{}]*\}\}', '', text)
        if new == text:
            break
        text = new
    # 文件/分类链接整行丢掉
    text = re.sub(r'\[\[(?:File|Image|Category):[^\]]*\]\]', '', text, flags=re.I)
    # 内部链接 [[A|B]] -> B，[[A]] -> A
    text = re.sub(r'\[\[[^\]|]*\|([^\]]*)\]\]', r'\1', text)
    text = re.sub(r'\[\[([^\]]*)\]\]', r'\1', text)
    # 外部链接 [http://x y] -> y
    text = re.sub(r'\[https?://\S+\s+([^\]]*)\]', r'\1', text)
    text = re.sub(r'\[https?://\S+\]', '', text)
    # 粗斜体
    text = re.sub(r"'{2,5}", '', text)
    text = html.unescape(text)
    # 压缩空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def split_sections(w):
    """按标题切段，返回 [(level, title, body)]。"""
    parts = re.split(r'^(={2,4})\s*(.+?)\s*\1\s*$', w, flags=re.M)
    out = []
    # parts[0] 是首个标题前的导言
    if parts and parts[0].strip():
        out.append((0, '(导言)', parts[0]))
    for i in range(1, len(parts), 3):
        lvl = len(parts[i]) - 2
        title = parts[i + 1].strip()
        body = parts[i + 2] if i + 2 < len(parts) else ''
        out.append((lvl, title, body))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = sys.argv[1]
    d = json.load(io.open(src, encoding='utf-8'))
    page = d['parse']
    w = page['wikitext']
    secs = split_sections(w)

    if '--brief' in sys.argv:
        for lvl, title, body in secs:
            t = clean(body)
            if not t:
                continue
            print('\n## ' + title)
            for line in t.split('\n'):
                line = line.strip().lstrip('*-#').strip()
                if not line:
                    continue
                print('  - ' + (line[:60] + '…' if len(line) > 60 else line))
        return 0

    if '--toc' in sys.argv:
        total = 0
        for lvl, title, body in secs:
            t = clean(body)
            total += len(t)
            print('%s%-14s %5d 字' % ('  ' * lvl, title, len(t)))
        print('\n合计 %d 字，%d 节' % (total, len(secs)))
        return 0

    dst = sys.argv[2]
    lines = ['# %s' % page['title'], '',
             '来源：https://muvluv.fandom.com/wiki/%s' % page['title'].replace(' ', '_'), '']
    for lvl, title, body in secs:
        t = clean(body)
        if not t:
            continue
        if lvl == 0:
            lines += [t, '']
        else:
            lines += ['#' * (lvl + 1) + ' ' + title, '', t, '']
    io.open(dst, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
    print('写出 %s（%d 字节）' % (dst, len('\n'.join(lines))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
