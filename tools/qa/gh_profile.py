import json
import subprocess
import urllib.request

REPO = "XueRongHua123/xuerong-editor"

DESC = ("Free open-source HOI4 mod editor: focus trees, spirits, equipment, tech, events, "
        "plus a full map editor with province painting, state editing, integrity checks "
        "and submod layering. Windows single-file exe, 20 MB.")

TOPICS = ["hoi4", "hearts-of-iron-4", "hoi4-mod", "mod-editor", "map-editor",
          "paradox-interactive", "python", "pyinstaller", "windows", "game-modding"]


def token():
    p = subprocess.run(["git", "credential", "fill"],
                       input=b"protocol=https\nhost=github.com\n\n",
                       capture_output=True, cwd=".")
    for line in p.stdout.decode().splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    return ""


def call(method, path, tok, data=None, preview=""):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(f"https://api.github.com{path}", data=body, method=method)
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "xuerong-profile")
    if preview:
        req.add_header("Accept", preview)
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"msg": e.read().decode()[:300]}


def main():
    tok = token()
    if not tok:
        print("没有 token")
        return 1
    st, old = call("GET", f"/repos/{REPO}", tok)
    print("旧简介长度:", len(old.get("description") or ""))
    print("新简介长度:", len(DESC))
    st, res = call("PATCH", f"/repos/{REPO}", tok, {"description": DESC})
    print("更新 description:", "ok" if st == 200 else res)
    st, res = call("PUT", f"/repos/{REPO}/topics", tok, {"names": TOPICS},
                   preview="application/vnd.github.mercy-preview+json")
    print("更新 topics:", "ok" if st == 200 else res, "|", (res.get("names") if st == 200 else ""))
    st, now = call("GET", f"/repos/{REPO}", tok)
    print("\n=== 现在的简介 ===")
    print(now.get("description"))
    return 0


if __name__ == "__main__":
    import urllib.error
    raise SystemExit(main())
