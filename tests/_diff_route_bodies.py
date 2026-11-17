# -*- coding: utf-8 -*-
"""核对某次 handler 改写「只把裸名字换成 LG.x / import 来的名字，逻辑没变」。

用法：
    python tests/_diff_route_bodies.py                     # 比全部 8 个 handler 与 HEAD
    python tests/_diff_route_bodies.py ai_h map_h          # 只比指定的
    python tests/_diff_route_bodies.py --rev HEAD~3        # 换基准提交

判定：把 `LG.x` 与裸 `x` 都归一成同一个占位符之后，改前改后的函数体 AST 文本必须逐字相同。
这一条能同时挡住「改多」（多加了一层调用、改了参数、删了分支）和「改少」（漏改某个引用）。

退出码：0 = 全部一致；1 = 有差异（会打印差异片段）。
"""
import ast
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HANDLERS = os.path.join(ROOT, "xuerong", "api", "handlers")
REL = "xuerong/api/handlers/%s.py"

DEFAULT_FILES = ["ai_h", "content_h", "focus_h", "map_h", "misc_h",
                 "state_country_h", "system_h", "world_mod_h"]


def git_show(rev, rel):
    r = subprocess.run(["git", "show", "%s:%s" % (rev, rel)], cwd=ROOT,
                       capture_output=True)
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", "replace")


def top_fns(src):
    return [(n.name, n) for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)]


class Normalize(ast.NodeTransformer):
    """`LG.x` 与裸 `x` 归一成同一个占位名，其它结构原样保留。

    注意遍历顺序：先看 Attribute 再递归，否则 `LG` 那个 Name 会先被换成占位符，
    属性判断就匹配不上了。
    """

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "LG":
            return ast.copy_location(
                ast.Name(id="REF_" + node.attr, ctx=ast.Load()), node)
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        return ast.copy_location(
            ast.Name(id="REF_" + node.id, ctx=node.ctx), node)


def norm(fn):
    return ast.unparse(Normalize().visit(ast.parse(ast.unparse(fn))))


def facade_public_names():
    """门面顶层 def / class 的名字，用来查"还有没有裸引"。"""
    src = open(os.path.join(ROOT, "focus_editor.py"), encoding="utf-8").read()
    out = set()
    for n in ast.parse(src).body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
    return out


def bare_facade_refs(src, facade):
    """改后文件里仍然裸引门面名字的地方（应当为 0）。"""
    local = set()
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                local.add(a.asname or a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                local.add(a.asname or a.name)
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            local.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    local.add(t.id)
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) \
                and n.id in facade and n.id not in local:
            hits.append((n.id, n.lineno))
    return sorted(set(hits))


def compare(stem, rev, facade):
    old_src = git_show(rev, REL % stem)
    if old_src is None:
        print("  %-18s 基准提交里没有这个文件，跳过" % stem)
        return True
    new_path = os.path.join(HANDLERS, stem + ".py")
    new_src = open(new_path, encoding="utf-8").read()

    old_fns, new_fns = top_fns(old_src), top_fns(new_src)
    ok = True
    if [a for a, _ in old_fns] != [a for a, _ in new_fns]:
        print("  %-18s 函数名序列不一致：%s -> %s"
              % (stem, [a for a, _ in old_fns], [a for a, _ in new_fns]))
        ok = False

    diffs = 0
    for (on, of), (nn, nf) in zip(old_fns, new_fns):
        a, b = norm(of), norm(nf)
        if a != b:
            diffs += 1
            print("  %-18s %s 函数体不一致" % (stem, on))
            import difflib
            for line in list(difflib.unified_diff(a.splitlines(), b.splitlines(),
                                                 lineterm="", n=0))[2:8]:
                print("       " + line[:150])
    bare = bare_facade_refs(new_src, facade)
    if bare:
        print("  %-18s 仍裸引门面名字 %d 处：%s" % (stem, len(bare), bare[:6]))
        ok = False
    if diffs or not ok:
        return False
    print("  %-18s %d 个函数，归一后全一致，无裸引" % (stem, len(new_fns)))
    return True


def main(argv):
    rev = "HEAD"
    if "--rev" in argv:
        i = argv.index("--rev")
        rev = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    files = argv or DEFAULT_FILES
    facade = facade_public_names()
    print("基准 %s / 门面顶层名字 %d 个" % (rev, len(facade)))
    results = [compare(s, rev, facade) for s in files]
    print()
    print("RESULT =", "PASS" if all(results) else "FAIL")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
