# -*- coding: utf-8 -*-
"""把 work/ 根目录的历史垃圾归档到 work/_archive/，不动活跃资产。

分类依据（已通过两道审计确认）：
  * import 审计：只有 editor_i18n / focus_editor 被别的目录 import
  * 字符串审计：只有 check_ui_elements / smoke_test 被文档或工具提到，
    mascot_card / mascot_face 被打包脚本引用
其余 work/ 根目录的 .py、图片、日志都是历史产物，归档后根目录从 295 个文件降到 50 上下。

用法：
    python work/qa/_tidy_workdir.py --dry-run   # 只列清单
    python work/qa/_tidy_workdir.py             # 执行
    python work/qa/_tidy_workdir.py --undo      # 全部移回原位
"""
import io
import os
import re
import shutil
import sys

WD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # work/
ARCHIVE = os.path.join(WD, '_archive')

# 保留在 work/ 根目录，不归档
KEEP = {
    # 核心工具
    'verify_mod.py', 'focus_editor.py', 'editor_i18n.py', 'balance.py',
    # 被 xuerong-editor/docs 或 packaging/README 引用
    'check_ui_elements.py', 'smoke_test.py',
    # 被打包脚本引用的素材
    'mascot_card.png', 'mascot_face.png',
    # 非 .py 的配置
    '.gitignore', 'qa_decision_timing_probe.mod',
}

# 归档子目录；顺序有意义，先匹配的优先
RULES = [
    ('parts',    r'^part(\d+|_).*\.py$'),
    ('patches',  r'^patch(\d+|_.*)\.py$'),
    ('fixes',    r'^fix_.*\.py$'),
    ('checks',   r'^check_.*\.py$'),
    ('scripts',  r'^(overlap|refcheck)\.py$'),
    ('scripts',  r'^(test_|probe_|rollback_|final_|revert_|clean_|compare_|copy_|crop_|make_|set_|write_|add_|analyze_|audit_|dump_|strip_|mark_|merge_|rename_|state_|sum_|thumbnail_|topbar_|un_|zi_|lowercase_|doctrine_|bookmark_|capital_|btn_|country_|ctx|db_|diff_|err|error_|gui|hist_|loc_|nuke_|overlap_|playset_|pos_|refcheck_|verify_fixed|conv_|convert_|focus_|export_).*\.py$'),
    ('scripts',  r'^(active_playset|append_test|build_cnsub_test|find_elec_positions|gen_all_raids|gen_raids|grep_main|pdf_outline|pdf_probe|show_msgs)\.py$'),
    ('images',   r'.*\.(png|jpg|jpeg|webp|bmp)$'),
    ('logs',     r'.*\.(log|txt|out|diff|pdf|csv)$'),
    ('logs',     r'^verify_report\.json$'),
]


def target_for(name):
    for sub, pat in RULES:
        if re.match(pat, name, re.I):
            return sub
    return None


def collect():
    plan = {}
    for name in sorted(os.listdir(WD)):
        full = os.path.join(WD, name)
        if not os.path.isfile(full) or name in KEEP:
            continue
        sub = target_for(name)
        if sub:
            plan.setdefault(sub, []).append(name)
    return plan


def show(plan, dry):
    total, size = 0, 0
    for sub in sorted(plan):
        items = plan[sub]
        s = sum(os.path.getsize(os.path.join(WD, f)) for f in items)
        total += len(items)
        size += s
        print('\n=== %s : %d 个, %.1f MB ===' % (sub, len(items), s / 1048576))
        for f in items:
            print('   ' + f)
    keep = [f for f in sorted(os.listdir(WD))
            if os.path.isfile(os.path.join(WD, f)) and f not in
            sum(plan.values(), [])]
    print('\n--- 合计归档 %d 个, %.1f MB ---' % (total, size / 1048576))
    print('--- 留在 work/ 根目录 %d 个 ---' % len(keep))
    for f in keep:
        print('   ' + f)
    return total


def do_archive(plan):
    moved = 0
    for sub, items in plan.items():
        dst_dir = os.path.join(ARCHIVE, sub)
        os.makedirs(dst_dir, exist_ok=True)
        for f in items:
            src = os.path.join(WD, f)
            dst = os.path.join(dst_dir, f)
            if os.path.exists(dst):
                print('  跳过（目标已存在）: %s' % f)
                continue
            shutil.move(src, dst)
            moved += 1
    print('已归档 %d 个文件到 %s' % (moved, ARCHIVE))
    # 写清单，方便日后追溯
    manifest = os.path.join(ARCHIVE, 'MANIFEST.txt')
    with io.open(manifest, 'w', encoding='utf-8') as fh:
        fh.write('work/ 根目录归档清单\n')
        for sub in sorted(plan):
            fh.write('\n[%s]\n' % sub)
            for f in plan[sub]:
                fh.write('  %s\n' % f)
    print('清单: %s' % manifest)


def undo():
    n = 0
    for sub in sorted(os.listdir(ARCHIVE)) if os.path.isdir(ARCHIVE) else []:
        d = os.path.join(ARCHIVE, sub)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            src = os.path.join(d, f)
            dst = os.path.join(WD, f)
            if not os.path.isfile(src):
                continue
            if os.path.exists(dst):
                print('  跳过（work/ 已有同名）: %s' % f)
                continue
            shutil.move(src, dst)
            n += 1
    print('已移回 %d 个文件' % n)


def main():
    dry = '--dry-run' in sys.argv
    if '--undo' in sys.argv:
        undo()
        return 0
    plan = collect()
    total = show(plan, dry)
    if dry:
        print('\n（--dry-run，未移动任何文件）')
    elif total:
        do_archive(plan)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
