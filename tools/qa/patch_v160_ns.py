# -*- coding: utf-8 -*-
"""v1.6.0 事件命名空间的增设与删除。"""
import io
import os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'focus_editor.py')

BLOCK = '''def event_space_create(ns, root=None):
    """新建一个事件命名空间：写 events/zz_xuerong_<ns>.txt，含一个样板事件"""
    import re as _re
    ns = (ns or "").strip()
    if not _re.match(r'^[A-Za-z][A-Za-z0-9_]*$', ns):
        return {"ok": False, "msg": "命名空间只能用字母、数字、下划线，且字母开头：%s" % ns}
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "没有加载 mod"}
    if is_under_game(root):
        return {"ok": False, "msg": "这是原版目录，只读"}
    d = os.path.join(root, "events")
    os.makedirs(d, exist_ok=True)
    fn = os.path.join(d, "zz_xuerong_%s.txt" % ns)
    if os.path.exists(fn):
        return {"ok": False, "msg": "文件已存在：events/zz_xuerong_%s.txt" % ns}
    # 避免和已有命名空间撞名
    existing = event_graph("", root)
    for sp in existing.get("spaces") or []:
        if sp["id"] == ns:
            return {"ok": False, "msg": "命名空间 %s 已经有事件了" % ns}
    body = (
        "add_namespace = %s\\n\\n"
        "country_event = {\\n"
        "\\tid = %s.1\\n"
        "\\ttitle = %s.1.t\\n"
        "\\tdesc = %s.1.d\\n"
        "\\tis_triggered_only = yes\\n"
        "\\n"
        "\\toption = {\\n"
        "\\t\\tname = %s.1.a\\n"
        "\\t}\\n"
        "}\\n"
    ) % (ns, ns, ns, ns, ns)
    snapshot(fn) if os.path.exists(fn) else None
    io.open(fn, "wb").write(b"\\xef\\xbb\\xbf" + body.encode("utf-8"))
    _EVENT_GRAPH_CACHE.clear()
    return {"ok": True, "ns": ns, "file": "events/zz_xuerong_%s.txt" % ns,
            "msg": "已创建命名空间 %s（events/zz_xuerong_%s.txt），记得补本地化 %s.1.t / .d / .a" % (
                ns, ns, ns)}


def event_space_delete(ns, root=None):
    """删除某个命名空间的事件：从各 events/*.txt 里摘掉这些块，文件空了就删"""
    ns = (ns or "").strip()
    if not ns:
        return {"ok": False, "msg": "没有指定命名空间"}
    root = _map_pick(root)
    if not root:
        return {"ok": False, "msg": "没有加载 mod"}
    if is_under_game(root):
        return {"ok": False, "msg": "这是原版目录，只读"}
    d = os.path.join(root, "events")
    if not os.path.isdir(d):
        return {"ok": False, "msg": "没有 events 目录"}

    prefix = ns + "."
    removed = 0
    touched = []
    for _dp, _dn, files in os.walk(d):
        for fn in sorted(files):
            if not fn.endswith(".txt"):
                continue
            p = os.path.join(_dp, fn)
            try:
                raw = io.open(p, encoding="utf-8-sig", errors="replace").read()
            except Exception:
                continue
            text = strip_comments(raw)
            spans = []
            for m in re.finditer(r'(?m)^\\s*[a-z_]*_event\\s*=\\s*\\{', text):
                b = text.find("{", m.end() - 1)
                e = brace_match(text, b)
                if e <= b:
                    continue
                body = text[b + 1:e - 1]
                eid = re.search(r'(?m)^\\s*id\\s*=\\s*"?([A-Za-z0-9_.\\-]+)"?', body)
                if eid and eid.group(1).startswith(prefix):
                    # 用原文（去注释后的坐标）回到原始文本里删：按行号范围删更稳
                    spans.append((m.start(), e))
            if not spans:
                continue
            # 逐行处理：标记要删的行
            lines = raw.splitlines(True)
            offsets = []
            acc = 0
            for ln in lines:
                offsets.append(acc)
                acc += len(ln)
            drop = set()
            for (b, e) in spans:
                for i, off in enumerate(offsets):
                    if off >= b and off < e:
                        drop.add(i)
                    elif off < b and off + len(lines[i]) > b:
                        drop.add(i)
            if not drop:
                continue
            keep = [ln for i, ln in enumerate(lines) if i not in drop]
            new_text = "".join(keep)
            if new_text.strip() in ("", "l_english:", "l_simp_chinese:"):
                snapshot(p)
                os.remove(p)
                touched.append("%s（已删空，文件移除）" % os.path.relpath(p, root))
            else:
                snapshot(p)
                io.open(p, "wb").write(b"\\xef\\xbb\\xbf" + new_text.encode("utf-8"))
                touched.append("%s（删 %d 个块）" % (os.path.relpath(p, root), len(spans)))
            removed += len(spans)
    if not removed:
        return {"ok": False, "msg": "没有找到 %s.* 的事件" % ns}
    _EVENT_GRAPH_CACHE.clear()
    reload_data()
    return {"ok": True, "ns": ns, "removed": removed, "files": touched,
            "msg": "已删除命名空间 %s 的 %d 个事件" % (ns, removed)}


'''


def main():
    s = io.open(P, encoding='utf-8').read()
    if 'def event_space_create' in s:
        print('已注入，跳过')
        return 0
    anchor = 'def _terrain_colors(root):'
    assert s.count(anchor) == 1
    s = s.replace(anchor, BLOCK + anchor, 1)

    old = '''        elif path_only == "/api/event_spaces":'''
    new = '''        elif path_only == "/api/event_space_create":
            _q = parse_qs(urlparse(self.path).query)
            self._send(event_space_create(_q.get("ns", [""])[0], _q.get("root", [None])[0]))
        elif path_only == "/api/event_space_delete":
            _q = parse_qs(urlparse(self.path).query)
            self._send(event_space_delete(_q.get("ns", [""])[0], _q.get("root", [None])[0]))
        elif path_only == "/api/event_spaces":'''
    assert s.count(old) == 1
    s = s.replace(old, new, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(s)
    print('事件命名空间增删接口已注入')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
