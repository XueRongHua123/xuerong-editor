# -*- coding: utf-8 -*-
"""三条 replace 修复路由的 HTTP 冒烟。

对应交接文档 `work/HANDOVER_REPLACE_FIX.md` 第四节。起一个真服务（随机空闲端口），
把 `/api/replace_drop`、`/api/replace_fix_all`、`/api/replace_ignore` 各打一次，
然后关掉。

用法：
    python work/qa/_smoke_replace_api.py

为什么不用 curl：本机 curl 走 HTTP 代理，打 127.0.0.1 会被代理拦掉
（报 `upstream connect failed`）。这里直接开 ProxyHandler({}) 直连。

退出码：全部 PASS 为 0，否则 1。
"""
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
if WORK not in sys.path:
    sys.path.insert(0, WORK)

import focus_editor as fe

ROOT = os.path.join(WORK, "tmp", "_fixup_api")
DESC = os.path.join(ROOT, "descriptor.mod")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name,
                        ("　" + detail) if detail else ""))
    return ok


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    shutil.rmtree(ROOT, ignore_errors=True)
    r = fe.world_create(ROOT, width=1024, height=512, n_provinces=40, seed=11,
                        tag="ZZV", country_name="接口冒烟")
    if not r.get("ok"):
        print("样本生成失败（地图生成需要 numpy）：%s" % r.get("msg"))
        return 1
    txt = io.open(DESC, encoding="utf-8-sig").read()
    fe._atomic_write(DESC, (txt.rstrip("\n") + '\nreplace_path="common/ideas"\n').encode("utf-8"))

    port = free_port()
    base = "http://127.0.0.1:%d" % port
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def post(path, payload):
        req = urllib.request.Request(base + path,
                                     data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with opener.open(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))

    srv = subprocess.Popen([sys.executable, os.path.join(WORK, "focus_editor.py"),
                            "--mod", ROOT, "--port", str(port)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        t0 = time.time()
        d = None
        while time.time() - t0 < 240:
            try:
                d = post("/api/diagnose", {})
                break
            except Exception:
                time.sleep(2)
        check("[1] 服务起来并能诊断", d is not None, "用时 %.0fs" % (time.time() - t0))
        if d is None:
            return summary()

        dg = [f for f in d["findings"] if f["code"] == "replace.dangling_refs"]
        check("[2] 诊断里有 replace.dangling_refs", len(dg) > 0,
              "%d 条 / 总 %d 条" % (len(dg), d["count"]))
        check("[3] HTTP 返回的 finding 带 fix",
              bool(dg) and (dg[0].get("fix") or {}).get("kind") == "replace_dangling")

        r = post("/api/replace_drop", {"sub": "common/ideas"})
        check("[4] /api/replace_drop", r.get("ok") and r.get("removed") == 1,
              r.get("msg", ""))

        txt = io.open(DESC, encoding="utf-8-sig").read()
        fe._atomic_write(DESC, (txt.rstrip("\n") + '\nreplace_path="common/ideas"\n').encode("utf-8"))
        d2 = post("/api/diagnose", {})
        pick = [f for f in d2["findings"] if f["code"] == "replace.dangling_refs"
                and "adopt_ref_dir" in (f["fix"].get("options") or [])]
        if pick:
            ref = pick[0]["fix"]["ref_dir"]
            r = post("/api/replace_fix_all",
                     {"kind": "adopt_ref_dir", "subs": [ref], "force": True})
            check("[5] /api/replace_fix_all 接管", r.get("ok") and r.get("done"),
                  r.get("msg", ""))
        else:
            check("[5] /api/replace_fix_all 接管", False, "没有可接管分组")

        d3 = post("/api/diagnose", {})
        k = [f for f in d3["findings"] if f["code"] == "replace.dangling_refs"][0]["fix"]
        n0 = len([f for f in d3["findings"] if f["code"] == "replace.dangling_refs"])
        r = post("/api/replace_ignore", {"subs": k["subs"], "ref_dir": k["ref_dir"],
                                         "group": k["group"]})
        d4 = post("/api/diagnose", {})
        n1 = len([f for f in d4["findings"] if f["code"] == "replace.dangling_refs"])
        check("[6] /api/replace_ignore 生效", r.get("ok") and n1 == n0 - 1,
              "%d -> %d" % (n0, n1))
        post("/api/replace_ignore", {"subs": k["subs"], "ref_dir": k["ref_dir"],
                                     "group": k["group"], "remove": True})

        r = post("/api/replace_fix_all", {"kind": "drop_replace"})
        d5 = post("/api/diagnose", {})
        left = len([f for f in d5["findings"] if f["code"] == "replace.dangling_refs"])
        check("[7] /api/replace_fix_all 全部撤销后归零", left == 0,
              "%s（left=%d）" % (r.get("msg", ""), left))
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=15)
        except Exception:
            srv.kill()
        shutil.rmtree(ROOT, ignore_errors=True)
    return summary()


def summary():
    bad = [r for r in RESULTS if not r[1]]
    print("\n" + "=" * 50)
    print("总计 %d 项：PASS %d / FAIL %d" % (len(RESULTS), len(RESULTS) - len(bad), len(bad)))
    print("总判定 %s" % ("PASS" if not bad else "FAIL"))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
