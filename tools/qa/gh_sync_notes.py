# -*- coding: utf-8 -*-
"""用本地 notes 文件更新 GitHub Release 正文（去对话痕迹等）。"""
import io
import json
import os
import re
import subprocess
import sys
import urllib.request

REPO = "XueRongHua123/xuerong-editor"
API = "https://api.github.com"
HERE = os.path.dirname(os.path.abspath(__file__))


def token():
    p = subprocess.run(["git", "credential", "fill"], input=b"protocol=https\nhost=github.com\n\n",
                       capture_output=True, cwd=HERE)
    for line in p.stdout.decode("utf-8", "replace").splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    return ""


def call(method, path, tok, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(API + path, data=body, method=method)
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "xuerong-notes")
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"msg": e.read().decode()[:200]}


def main():
    tok = token()
    if not tok:
        print("没有 token")
        return 1
    st, rels = call("GET", "/repos/%s/releases?per_page=100" % REPO, tok)
    if st != 200:
        print("列取失败", st, rels)
        return 1
    changed = 0
    for r in rels:
        tag = r.get("tag_name") or ""
        m = re.match(r"^v(\d+)\.(\d+)\.(\d+)$", tag)
        if not m:
            continue
        fname = "release_notes_v%d%d%d.md" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        path = os.path.join(HERE, fname)
        if not os.path.exists(path):
            continue
        body = io.open(path, encoding="utf-8").read()
        if body.strip() == (r.get("body") or "").strip():
            continue
        st2, res = call("PATCH", "/repos/%s/releases/%s" % (REPO, r["id"]), tok, {"body": body})
        print(("  更新 %-10s %s" % (tag, "ok" if st2 == 200 else res)))
        if st2 == 200:
            changed += 1
    print("共更新", changed, "个 Release")
    return 0


if __name__ == "__main__":
    import urllib.error
    sys.exit(main())
