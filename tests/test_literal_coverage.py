"""字面量/名字覆盖检查：对比原字节码与还原源码，找出可能漏掉的分支。

原理：把原函数（含嵌套 code object）的 co_consts 与 co_names 取出，
再扫描还原源码里同一函数体内出现的常量与名字；原版有、源码里没有的字面量，
往往意味着漏了一个分支/一个坐标/一条文案。
"""
from __future__ import annotations

import ast
import marshal
import sys
import types
import zlib
from pathlib import Path

sys.path.insert(0, r'D:\DSH\SHP_Auto\_ref')
import orig_garrison  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LOGIC = ROOT / 'src' / 'garrison_pc' / 'logic' / 'garrison.py'

SKIP_NAMES = {
    '__name__', '__module__', '__qualname__', 'self', 'args', 'kwargs',
}
IGNORE_LITERALS = {None, True, False, 0, 1, 2, 3, 4, 5, 6, -1, 8, 10, 20, 40,
                   60, 100, 120, 180, 500, '', ' ', '.', '_', '(', ')', '%s', '%',
                   'utf-8', 'nt', 'w', 'a', 'r', 'utf-8-sig'}


def walk_code(co):
    yield co
    for c in co.co_consts:
        if isinstance(c, types.CodeType):
            yield from walk_code(c)


def collect_literals(co):
    lits, names = set(), set()
    for code in walk_code(co):
        for c in code.co_consts:
            if isinstance(c, (str, int, float)) and not isinstance(c, bool):
                lits.add(c)
            elif isinstance(c, tuple):
                for item in c:
                    if isinstance(item, (str, int, float)) and not isinstance(item, bool):
                        lits.add(item)
        names.update(code.co_names)
    return lits, names


def source_funcs(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    out[f'{node.name}.{sub.name}'] = sub
    return out


def func_literals(node):
    lits, names = set(), set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, (str, int, float)):
            lits.add(sub.value)
        elif isinstance(sub, ast.Name):
            names.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            names.add(sub.attr)
    return lits, names


def main() -> int:
    module = orig_garrison.load()
    funcs = source_funcs(LOGIC)
    problems = 0
    for name, obj in module.items():
        if not isinstance(obj, types.FunctionType):
            continue
        key = name
        if key not in funcs:
            print(f'[缺失函数] {name}')
            problems += 1
            continue
        lits, names = collect_literals(obj.__code__)
        slits, snames = func_literals(funcs[key])
        missing_lits = {x for x in lits - slits if x not in IGNORE_LITERALS}
        # 只关心有意义的缺失名字（函数/模块级名字）
        missing_names = {x for x in names - snames if x not in SKIP_NAMES}
        if missing_lits or missing_names:
            print(f'\n[{name}] 原版 {len(lits)} 字面量 / {len(names)} 名字')
            if missing_lits:
                shown = sorted(map(repr, missing_lits))[:20]
                print('  源码里没有的字面量:', ', '.join(shown))
            if missing_names:
                print('  源码里没有的名字:', ', '.join(sorted(missing_names)[:25]))
            problems += 1
    print(f'\n检查完成，可疑函数 {problems} 个')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
