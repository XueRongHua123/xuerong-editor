# -*- coding: utf-8 -*-
"""v0.56 后端：history/countries 的读取与字段级写回。幂等注入。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'focus_editor.py')
MARK = "# ---------------- 国家历史写回（v0.56） ----------------"

BLOCK = r'''# ---------------- 国家历史写回（v0.56） ----------------
PARTIES = ("democratic", "fascism", "communism", "neutrality")

HIST_KEYS = {
    "capital": "capital",
    "political_power": "add_political_power",
    "stability": "add_stability",
    "war_support": "add_war_support",
}


def _hist_path(tag):
    c = COUNTRIES.get(tag)
    if not c:
        return None, None, None
    root = c.get("root") or ""
    rel = c.get("history_file") or ""
    p = os.path.join(root, rel) if rel else ""
    return c, root, p


def _read_bom_text(path):
    raw = io.open(path, "rb").read()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    return raw.decode("utf-8-sig", "replace"), has_bom


def _write_bom_text(path, text, has_bom):
    data = text.encode("utf-8")
    if has_bom:
        data = b"\xef\xbb\xbf" + data
    io.open(path, "wb").write(data)


def _first_in(text, pat):
    m = re.search(pat, text, re.M)
    return m.group(1).strip() if m else ""


def country_history_raw(tag):
    c, root, p = _hist_path(tag)
    if not c:
        return {"ok": False, "msg": "没有这个国家 tag"}
    writable = bool(root) and not is_under_game(root)
    if not p or not os.path.exists(p):
        return {"ok": True, "exists": False, "writable": writable, "file": c.get("history_file", ""),
                "root": root, "text": "", "fields": {}}
    text, _ = _read_bom_text(p)
    body = strip_comments(text)
    fields = {
        "capital": _first_in(body, r'(?m)^\s*capital\s*=\s*(\d+)'),
        "ruling_party": _first_in(body, r'(?m)^\s*ruling_party\s*=\s*(\w+)'),
        "political_power": _first_in(body, r'(?m)^\s*add_political_power\s*=\s*(-?[\d.]+)'),
        "stability": _first_in(body, r'(?m)^\s*add_stability\s*=\s*(-?[\d.]+)'),
        "war_support": _first_in(body, r'(?m)^\s*add_war_support\s*=\s*(-?[\d.]+)'),
        "ideas": (COUNTRIES.get(tag) or {}).get("ideas", []),
        "focus_tree": ((COUNTRIES.get(tag) or {}).get("focus_trees") or [""])[0],
    }
    return {"ok": True, "exists": True, "writable": writable, "file": c.get("history_file", ""),
            "root": root, "text": text[:60000], "fields": fields}


def _hist_set_scalar(text, key, value, at_end=False):
    """有就替换第一处（保留缩进），没有就插到开头或末尾"""
    pat = re.compile(r'(?m)^(\s*)%s\s*=\s*[^\s#\r\n]+' % re.escape(key))
    line = "%s = %s" % (key, value)
    if pat.search(text):
        return pat.sub(lambda m: (m.group(1) or "") + line, text, count=1)
    if at_end:
        return text.rstrip() + "\n" + line + "\n"
    return line + "\n" + text.lstrip("\r\n")


def _hist_strip_key(text, key):
    """删掉 key 的单值行与块（用于 add_ideas / load_focus_tree 的整体替换）"""
    text = remove_block(text, key)
    text = re.sub(r'(?m)^\s*%s\s*=\s*[^{\s#][^\r\n]*\r?\n?' % re.escape(key), "", text)
    return text


def _hist_put_block(text, key, inner_lines):
    text = _hist_strip_key(text, key)
    if not inner_lines:
        return text
    body = "\n".join("\t" + x for x in inner_lines)
    return text.rstrip() + "\n" + "%s = {\n%s\n}\n" % (key, body)


def _hist_set_party(text, party):
    m = re.search(r'(?m)^([ 	]{0,4})set_politics\s*=\s*\{', text)
    if not m:
        return "set_politics = {\n\truling_party = %s\n}\n" % party + text.lstrip("\r\n")
    b = text.find('{', m.end() - 1)
    e = brace_match(text, b)
    body = text[b + 1:e - 1]
    pat = re.compile(r'(?m)^(\s*)ruling_party\s*=\s*[^\s#\r\n]+')
    if pat.search(body):
        body2 = pat.sub(lambda mm: (mm.group(1) or "\t") + "ruling_party = " + party, body, count=1)
    else:
        body2 = body.rstrip() + "\n\truling_party = %s\n" % party
    return text[:b + 1] + body2 + text[e - 1:]


def country_history_save(tag, fields):
    """只改 fields 里给出的键，其余原文一律保留；写前 snapshot()"""
    c, root, p = _hist_path(tag)
    if not c:
        return {"ok": False, "msg": "没有这个国家 tag"}
    if not root:
        return {"ok": False, "msg": "这个国家没有来源目录"}
    if is_under_game(root):
        return {"ok": False, "msg": "原版目录只读：请先复制到自己的模组再修改"}

    warnings = []
    party = (fields.get("ruling_party") or "").strip().lower()
    if party and party not in PARTIES:
        return {"ok": False, "msg": "执政党只能是 " + " / ".join(PARTIES)}
    capital = (fields.get("capital") or "").strip()
    if capital and not capital.isdigit():
        return {"ok": False, "msg": "首都必须是州数字 id"}

    ideas = [x.strip() for x in (fields.get("ideas") or []) if x and x.strip()]
    for i in ideas:
        if i not in IDEAS:
            warnings.append("国家精神 %s 目前不存在（先写进去也可以，记得后面补定义）" % i)
    tree = (fields.get("focus_tree") or "").strip()
    if tree and tree not in TREES:
        warnings.append("国策树 %s 目前不存在" % tree)

    diff = []
    exists = bool(p) and os.path.exists(p)
    if exists:
        text, has_bom = _read_bom_text(p)
        before = strip_comments(text)
        old = {
            "capital": _first_in(before, r'(?m)^\s*capital\s*=\s*(\d+)'),
            "ruling_party": _first_in(before, r'(?m)^\s*ruling_party\s*=\s*(\w+)'),
            "political_power": _first_in(before, r'(?m)^\s*add_political_power\s*=\s*(-?[\d.]+)'),
            "stability": _first_in(before, r'(?m)^\s*add_stability\s*=\s*(-?[\d.]+)'),
            "war_support": _first_in(before, r'(?m)^\s*add_war_support\s*=\s*(-?[\d.]+)'),
            "ideas": ",".join(c.get("ideas", [])),
            "focus_tree": (c.get("focus_trees") or [""])[0],
        }
        new = dict(old)
        for key, mlkey in HIST_KEYS.items():
            val = (fields.get(key) or "").strip()
            if not val:
                continue
            text = _hist_set_scalar(text, mlkey, val, at_end=(key != "capital"))
            new[key] = val
        if party:
            text = _hist_set_party(text, party)
            new["ruling_party"] = party
        if fields.get("ideas") is not None:
            text = _hist_put_block(text, "add_ideas", ideas)
            new["ideas"] = ",".join(ideas)
        if fields.get("focus_tree") is not None:
            text = _hist_put_block(text, "load_focus_tree", ["tree = " + tree] if tree else [])
            new["focus_tree"] = tree
        shown = {"capital": "首都", "ruling_party": "执政党", "political_power": "政治点",
                 "stability": "稳定度修正", "war_support": "战争支持修正", "ideas": "开局精神", "focus_tree": "国策树"}
        for k, label in shown.items():
            if old.get(k, "") != new.get(k, ""):
                diff.append({"key": k, "label": label, "old": old.get(k, ""), "new": new.get(k, "")})
        if not diff:
            return {"ok": True, "msg": "没有改动", "diff": [], "warnings": warnings}
        snapshot(p)
        _write_bom_text(p, text, has_bom)
    else:
        name = c.get("history_display") or tag
        rel = os.path.join("history", "countries", "%s - %s.txt" % (tag, name))
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lines = []
        if capital:
            lines.append("capital = " + capital)
        if party:
            lines.append("set_politics = {\n\truling_party = %s\n}" % party)
        for key, mlkey in HIST_KEYS.items():
            if key == "capital":
                continue
            val = (fields.get(key) or "").strip()
            if val:
                lines.append("%s = %s" % (mlkey, val))
        if ideas:
            lines.append("add_ideas = {\n" + "\n".join("\t" + x for x in ideas) + "\n}")
        if tree:
            lines.append("load_focus_tree = {\n\ttree = %s\n}" % tree)
        if not lines:
            return {"ok": False, "msg": "没有任何要写入的字段"}
        text = "\n".join(lines) + "\n"
        io.open(path, "w", encoding="utf-8", newline="\r\n").write(text)
        diff = [{"key": "create", "label": "新建文件", "old": "", "new": rel}]

    reload_data()
    link_countries()
    return {"ok": True, "msg": "已写入 " + (c.get("history_file") or tag), "diff": diff, "warnings": warnings}


'''

def main():
    s = io.open(P, encoding='utf-8').read()
    if MARK in s:
        print('已注入，跳过')
        return 0
    anchor = "def lint_project(limit=1500):"
    assert s.count(anchor) == 1
    s = s.replace(anchor, BLOCK + anchor, 1)

    # 路由：GET 原始内容 + POST 保存
    old_get = '''        elif path_only == "/api/lint":'''
    new_get = '''        elif path_only == "/api/country_history":
            qs = parse_qs(urlparse(self.path).query)
            self._send(country_history_raw(qs.get("tag", [""])[0]))
        elif path_only == "/api/lint":'''
    assert s.count(old_get) == 1
    s = s.replace(old_get, new_get, 1)

    old_post = '''        elif self.path == "/api/idea_save":'''
    new_post = '''        elif self.path == "/api/country_save":
            self._send(country_history_save(body.get("tag", ""), body.get("fields") or {}))
        elif self.path == "/api/idea_save":'''
    assert s.count(old_post) == 1
    s = s.replace(old_post, new_post, 1)

    io.open(P, 'w', encoding='utf-8', newline='').write(s)
    print('注入完成：', P)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
