# -*- coding: utf-8 -*-
"""用 GitHub API 建 Release 并上传附件（token 从 git credential 取，不落盘）。

用法：python work/qa/gh_release.py <tag> <title> <notes_file> <file1> [file2 ...]
例：  python work/qa/gh_release.py v0.59.0 "v0.59.0 科技位置编辑" work/qa/notes.md \
        work/packaging/....zip work/packaging/dist/x.exe
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
    out = p.stdout.decode("utf-8", "replace")
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    return ""


def call(method, path, data=None, raw=None, ctype="application/json"):
    url = path if path.startswith("http") else API + path
    body = None
    if raw is not None:
        body = raw
    elif data is not None:
        body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "xuerong-editor-release")
    if body is not None:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def main():
    global TOKEN
    if len(sys.argv) < 5:
        print(__doc__)
        return 2
    tag, title, notes_file = sys.argv[1], sys.argv[2], sys.argv[3]
    files = sys.argv[4:]
    notes = open(notes_file, encoding="utf-8").read() if os.path.exists(notes_file) else ""
    TOKEN = token()
    if not TOKEN:
        print("没有取到 GitHub token")
        return 1

    st, rel = call("GET", "/repos/%s/releases/tags/%s" % (REPO, tag))
    if st != 200:
        st, rel = call("POST", "/repos/%s/releases" % REPO,
                       {"tag_name": tag, "name": title, "body": notes,
                        "target_commitish": "main", "draft": False, "prerelease": False})
    if st not in (200, 201):
        print("建 Release 失败：", st, rel.get("message"))
        return 1
    print("Release:", rel.get("html_url"))
    upload_url = rel.get("upload_url", "").split("{")[0]

    have = {a.get("name") for a in (rel.get("assets") or [])}
    for f in files:
        name = os.path.basename(f)
        if name in have:
            print("已存在，跳过：", name)
            continue
        data = open(f, "rb").read()
        st, res = call("POST", upload_url + "?name=" + urllib.parse.quote(name),
                       raw=data, ctype="application/octet-stream")
        print(("上传 %s → %s" % (name, "ok" if st in (200, 201) else res.get("message", st))))
    return 0


if __name__ == "__main__":
    import urllib.error
    import urllib.parse
    sys.exit(main())
