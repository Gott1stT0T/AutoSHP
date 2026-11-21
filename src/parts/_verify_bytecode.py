"""结构对照：把 part_a.py 编译出的字节码与 oracle 的函数逐指令比较（不是差分测试，是更强的一致性检查）。"""
import dis
import sys
import types

sys.path.insert(0, r'D:\DSH\SHP_Auto\_ref')
import orig_garrison

ORIG = orig_garrison.load()
NEW = dict(ORIG)
# 最终模块（00_header.py）顶部有 import cv2/import numpy as np；CPython 对"import 进来的模块"
# 的属性调用会编译成 LOAD_GLOBAL NULL + cv2 / LOAD_ATTR（而不是 LOAD_METHOD），
# 因此这里用同样前缀编译 part_a，才能与冻结版（3.11.5 编译）的字节码对齐。
PRE = 'import json\nimport os\nimport re\nimport time\nimport unicodedata\nimport cv2\nimport numpy as np\n'
SRC = open(r'D:\DSH\SHP_Auto\GarrisonFarmPC\src\parts\part_a.py', encoding='utf-8').read()
exec(compile(PRE + SRC, 'part_a.py', 'exec'), NEW)

NAMES = ['ocr', 'find', 'numrec', 'num', 'yellow_ratio', 'has_color_badge',
         'has_badge', 'passed_count', 'grid_shift']


def norm_const(c):
    if isinstance(c, types.CodeType):
        return ('code', c.co_name)
    return c


def sig(co):
    ins = []
    for i in dis.get_instructions(co):
        av = i.argval
        if isinstance(av, types.CodeType):
            av = ('code', av.co_name)
        ins.append((i.opname, av))
    consts = tuple(norm_const(c) for c in co.co_consts
                   if not isinstance(c, types.CodeType))
    nested = [sig(c) for c in co.co_consts if isinstance(c, types.CodeType)]
    return (co.co_argcount, co.co_posonlyargcount, co.co_kwonlyargcount,
            co.co_flags & ~0x10, tuple(co.co_names), tuple(co.co_varnames),
            tuple(co.co_freevars), tuple(co.co_cellvars),
            consts, tuple(ins), tuple(nested))


def firstdiff(a, b, path=''):
    diffs = []
    if a[:9] != b[:9]:
        labels = ['argcount', 'posonly', 'kwonly', 'flags', 'names', 'varnames',
                  'freevars', 'cellvars', 'consts']
        for label, x, y in zip(labels, a[:9], b[:9]):
            if x != y:
                diffs.append('%s %s: orig=%r new=%r' % (path, label, x, y))
    if a[9] != b[9]:
        la, lb = a[9], b[9]
        for idx in range(max(len(la), len(lb))):
            x = la[idx] if idx < len(la) else None
            y = lb[idx] if idx < len(lb) else None
            if x != y:
                diffs.append('%s ins[%d]: orig=%r new=%r' % (path, idx, x, y))
                break
        if len(la) != len(lb):
            diffs.append('%s nins: orig=%d new=%d' % (path, len(la), len(lb)))
    if len(a[10]) != len(b[10]):
        diffs.append('%s nnested: orig=%d new=%d' % (path, len(a[10]), len(b[10])))
    for k in range(min(len(a[10]), len(b[10]))):
        diffs.extend(firstdiff(a[10][k], b[10][k], path + '/nested[%d]' % k))
    return diffs


ok = True
for n in NAMES:
    fa, fb = ORIG[n], NEW[n]
    if n == 'passed_count':
        print('SKIP bytecode compare for %s (authoritative v1.2 source)' % n)
        continue
    d = firstdiff(sig(fa.__code__), sig(fb.__code__), n)
    if d:
        ok = False
        print('MISMATCH', n)
        for line in d[:12]:
            print('   ', line)
    else:
        print('BYTE-IDENTICAL structure:', n)
print('ALL OK' if ok else 'HAS MISMATCH')
