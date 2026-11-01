# -*- coding: utf-8 -*-
"""replace 断链一键补齐的验收脚本。

对应交接文档 `work/HANDOVER_REPLACE_FIX.md` 第四节。自建样本、自己清理，
不碰任何真实 mod。

用法：
    python work/qa/_check_replace_fixup.py          # 建样本后跑全部检查
    python work/qa/_check_replace_fixup.py --keep   # 跑完保留样本，方便手工看

样本：`work/tmp/_fixup_test`（40 省，13 条 replace_path，基线诊断 0 条断链）。
每次运行前整个删掉重建，所以重复跑结果一致。

退出码：全部 PASS 为 0，有任何 FAIL 为 1。
"""
import io
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
if WORK not in sys.path:
    sys.path.insert(0, WORK)

import focus_editor as fe

ROOT = os.path.join(WORK, "tmp", "_fixup_test")
DESC = os.path.join(ROOT, "descriptor.mod")

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name,
                        ("　" + detail) if detail else ""))
    return ok


def read_desc():
    return io.open(DESC, encoding="utf-8-sig", errors="replace").read()


def add_replace(sub):
    txt = read_desc()
    if ('replace_path="%s"' % sub) in txt:
        return
    if not txt.endswith("\n"):
        txt += "\n"
    fe._atomic_write(DESC, (txt + 'replace_path="%s"\n' % sub).encode("utf-8"))
    fe._invalidate_layers()


def dangling():
    return [f for f in fe._diag_replace_refs(ROOT)
            if f.get("code") == "replace.dangling_refs"]


def build_sample():
    print("建样本：%s" % ROOT)
    shutil.rmtree(ROOT, ignore_errors=True)
    r = fe.world_create(ROOT, width=1024, height=512, n_provinces=40, seed=11,
                        tag="ZZV", country_name="补齐测试")
    if not r.get("ok"):
        bad = [s for s in r.get("steps", []) if not s.get("ok")]
        print("样本生成失败：%s" % (bad[0].get("msg") if bad else r.get("msg")))
        print("（地图生成需要 numpy：pip install numpy）")
        return False
    fe.ROOTS = [ROOT]
    fe._invalidate_layers()
    os.makedirs(os.path.dirname(fe._REPLACE_IGNORE_FILE), exist_ok=True)
    fe._atomic_write(fe._REPLACE_IGNORE_FILE, b"[]")
    return True


def main():
    t0 = time.time()
    if not build_sample():
        return 1

    print("\n[1] 诊断能报出断链，且每条带可执行动作")
    check("[1a] 基线（13 条 replace_path）不误报", len(dangling()) == 0,
          "dangling=%d" % len(dangling()))
    add_replace("common/ideas")
    d = dangling()
    check("[1b] 加 replace_path=common/ideas 后报出危险目录", len(d) > 0,
          "%d 个目录，耗时 %.1fs" % (len(d), 0))
    if not d:
        return summary()
    f0 = d[0]
    fx = f0.get("fix") or {}
    check("[1c] finding 带 fix 且字段齐全",
          fx.get("kind") == "replace_dangling" and fx.get("subs") and fx.get("ref_dir"),
          "subs=%s ref_dir=%s" % (fx.get("subs"), fx.get("ref_dir")))
    check("[1d] ref_dir 已去掉 vanilla/ 前缀",
          not (fx.get("ref_dir") or "").startswith("vanilla/"),
          fx.get("ref_dir") or "")

    print("\n[2] 单条「撤销 replace」")
    r = fe.replace_fix_all(ROOT, kind="drop_replace", subs=fx["subs"])
    check("[2a] 接口返回成功", r.get("ok") and r.get("done"),
          r.get("msg", ""))
    check("[2b] descriptor 里那条 replace_path 已删除",
          'replace_path="common/ideas"' not in read_desc())
    check("[2c] 该组 finding 消失", len(dangling()) == 0,
          "dangling=%d" % len(dangling()))

    print("\n[3] 加两条再「全部撤销 replace」")
    add_replace("common/ideas")
    add_replace("common/characters")
    d = dangling()
    before = fe.diagnose(ROOT)["count"]
    check("[3a] 撤销前有断链", len(d) > 0, "dangling=%d diagnose=%d" % (len(d), before))
    r = fe.replace_fix_all(ROOT, kind="drop_replace")
    after = fe.diagnose(ROOT)["count"]
    check("[3b] 全部撤销后归零", len(dangling()) == 0, r.get("msg", ""))
    check("[3c] diagnose 总数下降", after < before, "%d -> %d" % (before, after))

    print("\n[4] descriptor 完整性")
    txt = read_desc()
    lines = txt.splitlines()
    reps = [x.strip() for x in lines if x.strip().startswith("replace_path")]
    check("[4a] 没有空行", not [x for x in lines if not x.strip()])
    check("[4b] replace_path 无重复", len(reps) == len(set(reps)), "%d 条" % len(reps))
    check("[4c] 原有 13 条 replace_path 原样保留", len(reps) == 13)
    check("[4d] name / version 等其它行未被破坏",
          'name="补齐测试"' in txt and 'version="1.0.0"' in txt)

    print("\n[5] 连跑 3 次「全部撤销」必须幂等")
    msgs = []
    for _ in range(3):
        r = fe.replace_fix_all(ROOT, kind="drop_replace")
        msgs.append(r.get("msg") or "")
    check("[5a] 三次都不报错且不动文件", 'replace_path="common/ideas"' not in read_desc(),
          " | ".join(msgs))

    print("\n[6] 「接管该目录」")
    add_replace("common/ideas")
    d = dangling()
    bucket = [x for x in d if "/" not in (x["fix"].get("ref_dir") or "")]
    check("[6a] 顶层桶分组不给接管选项",
          all("adopt_ref_dir" not in x["fix"]["options"] for x in bucket),
          "桶分组 %d 个：%s" % (len(bucket), [x["fix"]["ref_dir"] for x in bucket]))
    pickable = [x for x in d if "adopt_ref_dir" in (x["fix"].get("options") or [])]
    check("[6b] 存在可接管的子目录分组", bool(pickable))
    if pickable:
        ref = pickable[0]["fix"]["ref_dir"]
        src = None
        for lay in fe.mod_layers(ROOT):
            if os.path.abspath(lay) == os.path.abspath(ROOT):
                continue
            p = os.path.join(lay, ref.replace("/", os.sep))
            if os.path.isdir(p):
                src = p
                break
        src_n = sum(len(fs) for _, _, fs in os.walk(src)) if src else 0
        r = fe.replace_fix_all(ROOT, kind="adopt_ref_dir", subs=[ref], force=True)
        dst = os.path.join(ROOT, ref.replace("/", os.sep))
        dst_n = sum(len(fs) for _, _, fs in os.walk(dst)) if os.path.isdir(dst) else 0
        check("[6c] 目录已拷进本 mod 且文件数一致", src_n > 0 and dst_n == src_n,
              "%s：%d / %d" % (ref, src_n, dst_n))
        check("[6d] descriptor 写入 replace_path",
              ('replace_path="%s"' % ref) in read_desc())

    print("\n[7] 危险动作被拒绝")
    r = fe.adopt_dir(ROOT, "common")
    check("[7a] 拒绝接管顶层目录 common", not r.get("ok"), (r.get("msg") or "")[:60])
    blocked = fe._replace_adopt_block("common/units/equipment")
    check("[7b] 禁止接管 common/units/equipment", bool(blocked), blocked)

    print("\n[8] 忽略 / 恢复")
    d = dangling()
    if d:
        k = d[0]["fix"]
        n0 = len(d)
        fe.replace_ignore(ROOT, sub=k["sub"], ref_dir=k["ref_dir"],
                          subs=k["subs"], group=k["group"])
        n1 = len(dangling())
        fe.replace_ignore(ROOT, sub=k["sub"], ref_dir=k["ref_dir"], subs=k["subs"],
                          group=k["group"], remove=True)
        n2 = len(dangling())
        check("[8a] 忽略后少一条", n1 == n0 - 1, "%d -> %d" % (n0, n1))
        check("[8b] 恢复后回到原数", n2 == n0, "%d" % n2)
    else:
        check("[8a] 忽略 / 恢复", False, "没有可用的分组")

    print("\n耗时 %.1fs" % (time.time() - t0))
    return summary()


def summary():
    bad = [r for r in RESULTS if not r[1]]
    print("\n" + "=" * 50)
    print("总计 %d 项：PASS %d / FAIL %d" % (len(RESULTS), len(RESULTS) - len(bad), len(bad)))
    for name, _ok, detail in bad:
        print("  FAIL %s　%s" % (name, detail))
    print("总判定 %s" % ("PASS" if not bad else "FAIL"))
    return 0 if not bad else 1


if __name__ == "__main__":
    keep = "--keep" in sys.argv
    code = main()
    if not keep:
        shutil.rmtree(ROOT, ignore_errors=True)
        print("样本已清理（--keep 可保留）")
    sys.exit(code)
