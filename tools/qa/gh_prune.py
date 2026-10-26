# -*- coding: utf-8 -*-
"""清理 GitHub Release：只保留最新 N 个（tag 保留）。

用法：python work/qa/gh_prune.py [keep]
"""
import json
import os
import subprocess
import sys
import urllib.request

REPO = "XueRongHua123/xuerong-editor"
API = "https://api.github.com"


def token():
    p = subprocess.run(["git", "credential", "fill"], input=b"protocol=https\nhost=github.com\n\n",
                       capture_output=True, cwd=os.path.dirname(os.path.abspath(__file__)))
    for line in p.stdout.decode("utf-8", "replace").splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    return ""


def call(method, path, tok):
    req = urllib.request.Request(API + path, method=method)
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "xuerong-prune")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode() or "{}"
            return r.status, json.loads(body)
    except urllib.error.HTTPError as e:
        return e.code, {"msg": e.read().decode()[:200]}


def main():
    keep = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    tok = token()
    if not tok:
        print("没有 token")
        return 1
    st, rels = call("GET", "/repos/%s/releases?per_page=100" % REPO, tok)
    if st != 200:
        print("列取失败", st, rels)
        return 1
    rels.sort(key=lambda r: r.get("published_at") or r.get("created_at") or "", reverse=True)
    print("共 %d 个 Release，保留最新 %d 个" % (len(rels), keep))
    for r in rels[keep:]:
        st2, res = call("DELETE", "/repos/%s/releases/%s" % (REPO, r["id"]), tok)
        print(("  删除 %-10s %s" % (r["tag_name"], "ok" if st2 == 204 else res)))
    for r in rels[:keep]:
        print("  保留 %-10s %s" % (r["tag_name"], r.get("published_at", "")))
    return 0


if __name__ == "__main__":
    import urllib.error
    sys.exit(main())
