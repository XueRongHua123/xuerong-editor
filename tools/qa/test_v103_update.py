"""一键更新端到端测试：v1.0.1 → 下载 v1.0.2 → 替换 → 重启。

在 work/tmp/updtest 的副本上跑，不碰正式 exe。
"""
import hashlib
import json
import os
import subprocess
import time
import urllib.request

TEST_DIR = os.path.join(os.getcwd(), "tmp", "updtest")
EXE = os.path.join(TEST_DIR, "雪绒的钢铁雄心编辑器.exe")
BAK = EXE + ".bak"
PORT = 8913


def md5(p):
    if not os.path.exists(p):
        return "缺失"
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()[:12]


def call(path, body=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path), data=data)
    if data:
        req.add_header("Content-Type", "application/json")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())


print("替换前：exe=%s  bak=%s" % (md5(EXE), md5(BAK)))
log = open(os.path.join(TEST_DIR, "run.log"), "w", encoding="utf-8", errors="replace")
proc = subprocess.Popen([EXE, "--port", str(PORT)], cwd=TEST_DIR, stdout=log, stderr=subprocess.STDOUT)
print("旧进程 PID:", proc.pid)
time.sleep(50)

try:
    a = call("/api/app_info", timeout=60)
    print("旧版本:", a.get("version"), "| frozen:", a.get("frozen"))
    # 显式指定下载目标版本，保证替换后版本号真的变化
    import urllib.request as _u
    _rel = json.loads(_u.urlopen("https://api.github.com/repos/XueRongHua123/xuerong-editor/releases/tags/v1.0.2",
                                 timeout=30).read().decode())
    _exe = next(a for a in _rel["assets"] if a["name"].lower().endswith(".exe"))
    print("下载目标:", _exe["name"], round(_exe["size"] / 1048576, 1), "MB")
    d = call("/api/update_apply", {"act": "download", "url": _exe["browser_download_url"],
                                   "size": _exe["size"]}, timeout=300)
    print("下载:", {k: d.get(k) for k in ("ok", "msg", "size")})
    if not d.get("ok"):
        raise SystemExit(1)
    p = call("/api/update_apply", {"act": "prepare"}, timeout=120)
    print("准备:", {k: p.get(k) for k in ("ok", "msg")})
    l = call("/api/update_apply", {"act": "launch"}, timeout=60)
    print("启动替换:", {k: l.get(k) for k in ("ok", "msg")})
except Exception as e:
    print("调用失败:", e)
    proc.kill()
    raise SystemExit(1)

print("等待替换（最多 60 秒）…")
for i in range(60):
    time.sleep(1)
    if os.path.exists(BAK):
        break
time.sleep(8)

print("\n=== 结果 ===")
print("exe :", md5(EXE))
print("bak :", md5(BAK))
print("旧进程存活:", proc.poll() is None)

# 新进程应该已经起来
try:
    a2 = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/api/app_info" % PORT, timeout=15).read().decode())
    print("新进程版本:", a2.get("version"))
except Exception as e:
    print("新进程未响应:", str(e)[:80])

# 收尾：杀掉测试进程
try:
    subprocess.run(["taskkill", "/F", "/IM", os.path.basename(EXE)], capture_output=True)
except Exception:
    pass
log.close()
