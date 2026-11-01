# -*- coding: utf-8 -*-
"""用 GitHub API 建 Release 并上传附件（token 从 git credential 取，不落盘）。

用法：python work/qa/gh_release.py <tag> <title> <notes_file> <file1> [file2 ...]
例：  python work/qa/gh_release.py v0.59.0 "v0.59.0 科技位置编辑" work/qa/notes.md \
        work/packaging/....zip work/packaging/dist/x.exe
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

REPO = "XueRongHua123/xuerong-editor"
USER = "x-access-token"   # GitHub API 用 token 作密码，用户名随意
TOKEN = ""

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
    """调 GitHub API。

    用 curl 而不是 urllib：这台机器上 urllib 的 TLS 握手经常中途断
    （UNEXPECTED_EOF_WHILE_READING），连 GET 都会失败，而 curl 稳定。
    raw 参数保留兼容，但大文件请走 upload_asset。
    """
    import subprocess
    url = path if path.startswith("http") else API + path
    cmd = ["curl", "-s", "--retry", "5", "--retry-delay", "3", "--max-time", "600",
           "-u", "%s:%s" % (USER, TOKEN), "-X", method,
           "-H", "Accept: application/vnd.github+json",
           "-H", "User-Agent: xuerong-editor-release",
           "-w", "\n%{http_code}"]
    tmp = None
    if data is not None:
        tmp = os.path.join(os.environ.get("TEMP", "."), "_gh_body.json")
        open(tmp, "w", encoding="utf-8", newline="").write(json.dumps(data))
        cmd += ["-H", "Content-Type: application/json", "--data-binary", "@" + tmp]
    elif raw is not None:
        tmp = os.path.join(os.environ.get("TEMP", "."), "_gh_body.bin")
        open(tmp, "wb").write(raw if isinstance(raw, bytes) else bytes(raw))
        cmd += ["-H", "Content-Type: " + ctype, "--data-binary", "@" + tmp]
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=700,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "").strip().splitlines()
        code = 0
        body = "{}"
        if out:
            try:
                code = int(out[-1])
                body = "\n".join(out[:-1]) or "{}"
            except Exception:
                body = "\n".join(out)
        try:
            return code, json.loads(body)
        except Exception:
            return code, {"message": body[:200]}
    except Exception as e:
        return 0, {"message": str(e)[:200]}
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass

def upload_asset(upload_url, name, path):
    """上传附件。

    urllib 一次 POST 20MB+ 时，中间网络设备常把 SSL 连接掐断
    （UNEXPECTED_EOF_WHILE_READING），重试也没用。
    curl 的 --retry 加分段式发送能过，所以大文件走 curl。
    """
    import subprocess
    url = upload_url + "?name=" + urllib.parse.quote(name)
    try:
        r = subprocess.run(
            ["curl", "-s", "--retry", "5", "--retry-delay", "5", "--max-time", "900",
             "-u", "%s:%s" % (USER, TOKEN), "-X", "POST",
             "-H", "Content-Type: application/octet-stream",
             "--data-binary", "@" + path, url, "-w", "\n%{http_code}"],
            capture_output=True, text=True, timeout=1000,
            encoding="utf-8", errors="replace")
        out = (r.stdout or "").strip().splitlines()
        code = 0
        body = "{}"
        if out:
            try:
                code = int(out[-1])
                body = "\n".join(out[:-1]) or "{}"
            except Exception:
                body = "\n".join(out)
        return code, body
    except Exception as e:
        return 0, {"message": str(e)[:100]}


def main():
    global TOKEN
    TOKEN = token()
    if len(sys.argv) < 5:
        print(__doc__)
        return 2
    tag, title, notes_file = sys.argv[1], sys.argv[2], sys.argv[3]
    files = sys.argv[4:]
    notes = open(notes_file, encoding="utf-8").read() if os.path.exists(notes_file) else ""
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
    tag = rel.get("tag_name") or ""
    for f in files:
        local = os.path.basename(f)
        # GitHub 的 upload API 会把 URL 里的中文名压成 default/下划线，导致用户下载到 "default.exe"。
        # 统一用 ASCII 资产名：xuerong-editor-vX.Y.Z.exe / .zip
        ext = os.path.splitext(local)[1].lower()
        if ext in (".exe", ".zip"):
            name = "xuerong-editor-%s%s" % (tag or "latest", ext)
        else:
            name = re.sub(r"[^A-Za-z0-9._-]", "_", local)
        if name in have:
            print("已存在，跳过：", name)
            continue
        st, res = upload_asset(upload_url, name, f)
        print(("上传 %s ← %s → %s" % (name, local,
                                      "ok" if st in (200, 201) else str(res)[:80])))
    return 0


if __name__ == "__main__":
    import urllib.error
    import urllib.parse
    sys.exit(main())
