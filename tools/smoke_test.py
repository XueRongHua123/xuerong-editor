# -*- coding: utf-8 -*-
"""编辑器冒烟测试：启动服务，检查核心接口，退出码 0 表示通过。
用法：python work/smoke_test.py --mod "E:\\...\\mod" [--port 8890]
"""
import argparse, json, os, subprocess, sys, time, urllib.request, urllib.parse

def get(url, timeout=180):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mod", required=True)
    ap.add_argument("--port", type=int, default=8890)
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(here, "focus_editor.py")
    proc = subprocess.Popen([args.python, script, "--mod", args.mod, "--port", str(args.port)],
                            cwd=here, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % args.port
    ok = False
    try:
        for _ in range(60):
            time.sleep(2)
            try:
                d = get(base + "/api/data", 60)
                ok = True
                break
            except Exception:
                pass
        if not ok:
            print("FAIL: server did not start")
            return 1
        checks = []
        checks.append(("trees", len(d.get("trees", [])) > 0))
        checks.append(("techs", len(d.get("techs", [])) > 0))
        checks.append(("modules", len(d.get("modules", [])) > 0))
        icons = get(base + "/api/icons?kind=focus", 120)
        checks.append(("icons", len(icons.get("list", [])) > 0))
        trees = [t for t in d.get("trees", []) if t.get("focuses")]
        if trees:
            t = trees[0]
            fd = get(base + "/api/focus?tree=" + urllib.parse.quote(t["id"]) +
                     "&id=" + urllib.parse.quote(t["focuses"][0]["id"]), 60)
            checks.append(("focus_detail", "effect" in fd))
        else:
            checks.append(("focus_detail", False))
        for name, passed in checks:
            print(("PASS " if passed else "FAIL ") + name)
        return 0 if all(p for _, p in checks) else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    sys.exit(main())
