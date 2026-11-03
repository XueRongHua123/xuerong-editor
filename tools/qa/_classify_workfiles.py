# -*- coding: utf-8 -*-
"""把 work/ 根目录那 295 个文件按用途归类，输出可执行的分组计划。

只读。分类规则写在 PATTERNS 里，改规则就能改分组。
"""
import collections
import io
import os
import re

WD = r'D:\大肥鱼工作区\HOI4 MUVLUVsub mod 制作\work'

# 顺序有意义：先匹配的优先
PATTERNS = [
    ('一次性补丁 partNN_*',      r'^part\d+.*\.py$'),
    ('一次性补丁 fix_*',         r'^fix_.*\.py$'),
    ('一次性补丁 patch_*',       r'^patch_.*\.py$'),
    ('一次性补丁 check_*',       r'^check_.*\.py$'),
    ('一次性补丁 test_*',        r'^test_.*\.py$'),
    ('一次性补丁 probe_*',       r'^probe_.*\.py$'),
    ('一次性补丁 misc',          r'^(rollback_|final_|revert_|clean_|compare_|copy_|crop_|make_|set_|write_|add_|analyze_|audit_|dump_|strip_|mark_|merge_|rename_|state_|sum_|thumbnail_|topbar_|un_|zi_|lowercase_|doctrine_|balance_|bookmark_|capital_|btn_|country_|ctx|db_|diff_|err|error_|gui|hist_|loc_|nuke_|overlap|playset_|pos_|refcheck|smoke_|verify_|conv_|convert_|clean_probe|focus_|export_).*\.py$'),
    ('核心工具 verify_mod.py',    r'^verify_mod\.py$'),
    ('核心工具 focus_editor.py',  r'^focus_editor\.py$'),
    ('核心工具其他',              r'^(focus_viewer|focus_viewer_build|editor_i18n|balance|make_diff|patch_designer|patch_slots|patch_techtree|patch_snapshot|patch_viewer|refcheck|smoke_test)\.py$'),
    ('图片素材',                 r'.*\.(png|jpg|jpeg|webp)$'),
    ('文档',                     r'.*\.md$'),
    ('日志与临时输出',            r'.*\.(log|txt|out|diff|json|html|pdf|csv)$'),
    ('编辑器网页',                r'.*\.html$'),
    ('PowerShell 脚本',          r'.*\.ps1$'),
    ('mod 描述',                 r'.*\.mod$'),
    ('无扩展名',                 r'^[^.]*$'),
]


def main():
    files = [f for f in os.listdir(WD) if os.path.isfile(os.path.join(WD, f))]
    groups = collections.OrderedDict((k, []) for k, _ in PATTERNS)
    groups['未归类'] = []
    for f in files:
        for name, pat in PATTERNS:
            if re.match(pat, f, re.I):
                groups[name].append(f)
                break
        else:
            groups['未归类'].append(f)

    total = 0
    for name, items in groups.items():
        if not items:
            continue
        size = sum(os.path.getsize(os.path.join(WD, f)) for f in items)
        total += size
        print('\n=== %s : %d 个, %.1f MB ===' % (name, len(items), size / 1048576))
        for f in sorted(items)[:200]:
            print('   ' + f)
        if len(items) > 200:
            print('   ... 还有 %d 个' % (len(items) - 200))

    print('\n总计 %d 个文件, %.1f MB' % (len(files), total / 1048576))


if __name__ == '__main__':
    main()
