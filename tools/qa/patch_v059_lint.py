# -*- coding: utf-8 -*-
"""v0.59：体检扫描国策里的引用（add_ideas / has_idea / country_event）。幂等。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor.py')
MARK = "# v0.59 国策引用体检"

SCANNER = '''# v0.59 国策引用体检
def _focus_refs():
    """从 national_focus 原文里收集 add_ideas / has_idea / country_event 引用"""
    ideas, events = [], []
    for root in ROOTS:
        d = os.path.join(root, "common", "national_focus")
        if not os.path.isdir(d):
            continue
        name = os.path.basename(root.rstrip("\\\\/")) or root
        for fn in sorted(f for f in os.listdir(d) if f.endswith(".txt")):
            rel = os.path.join("common", "national_focus", fn)
            try:
                text = strip_comments(io.open(os.path.join(d, fn), encoding="utf-8", errors="replace").read())
            except Exception:
                continue
            for m in re.finditer(r'(?m)^[ \\t]*(?:focus|shared_focus)\\s*=\\s*\\{', text):
                b = text.find('{', m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                fid = _first(body, r'(?m)^[ \\t]*id\\s*=\\s*"?([A-Za-z0-9_.\\-]+)')
                if not fid:
                    continue
                tree = ""
                for tid, t in TREES.items():
                    if t.get("file") == rel and t.get("source") == name:
                        tree = tid
                        break
                for im in re.finditer(r'(?m)^[ \\t]*add_ideas\\s*=\\s*([A-Za-z0-9_]+)', body):
                    ideas.append({"focus": fid, "id": im.group(1), "where": "add_ideas",
                                  "file": rel, "tree": tree})
                for im in re.finditer(r'add_ideas\\s*=\\s*\\{([^}]*)\\}', body):
                    for iid in re.findall(r'[A-Za-z0-9_]+', im.group(1)):
                        ideas.append({"focus": fid, "id": iid, "where": "add_ideas",
                                      "file": rel, "tree": tree})
                for im in re.finditer(r'(?m)^[ \\t]*has_idea\\s*=\\s*([A-Za-z0-9_]+)', body):
                    ideas.append({"focus": fid, "id": im.group(1), "where": "has_idea",
                                  "file": rel, "tree": tree})
                for im in re.finditer(r'(?:country_event|news_event|state_event)\\s*=\\s*\\{\\s*id\\s*=\\s*"?([A-Za-z0-9_.\\-]+)', body):
                    events.append({"focus": fid, "id": im.group(1), "file": rel, "tree": tree})
    return {"ideas": ideas, "events": events}


def lint_project(limit=1500):'''


def main():
    s = io.open(P, encoding='utf-8').read()
    if MARK in s:
        print('已注入，跳过')
        return 0

    anchor = "def lint_project(limit=1500):"
    assert s.count(anchor) == 1
    s = s.replace(anchor, SCANNER, 1)

    old = '''    for it in missing_loc()[:limit]:'''
    new = '''    # v0.59：国策里的引用
    try:
        refs = _focus_refs()
    except Exception as e:
        refs = {"ideas": [], "events": []}
        print("focus refs fail:", e)
    for r in refs["ideas"]:
        if r["id"] not in IDEAS:
            add("warn", "focus", "国策 %s 的 %s 引用了不存在的国家精神 %s" % (r["focus"], r["where"], r["id"]),
                r["file"], {"type": "tree", "id": r["tree"]})
    for r in refs["events"]:
        if r["id"] not in EVENTS:
            add("warn", "focus", "国策 %s 触发了不存在的事件 %s" % (r["focus"], r["id"]),
                r["file"], {"type": "tree", "id": r["tree"]})

    for it in missing_loc()[:limit]:'''
    assert s.count(old) == 1
    s = s.replace(old, new, 1)

    # 省份列表放宽到 300
    s = s.replace('"provinces": s.get("provinces", [])[:80],', '"provinces": s.get("provinces", [])[:300],', 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(s)
    print('v0.59 体检扩展注入完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
