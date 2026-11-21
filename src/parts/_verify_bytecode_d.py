# -*- coding: utf-8 -*-
"""Byte-identical structure check for part_d.py vs the frozen oracle.

CPython 3.11 compiles calls on names that arrived via `import` as
LOAD_GLOBAL NULL + x / LOAD_ATTR (not LOAD_METHOD), so the part must be
compiled with the module header imports in front, exactly like 00_header.py.
Comparison includes instruction offsets/argvals, co_names, co_varnames,
co_consts, co_cellvars/co_freevars, defaults and flags.
The only intended deviation is load_layout: HERE -> _here().
"""
import dis
import sys
import types

sys.path.insert(0, r'D:\DSH\SHP_Auto\_ref')
import orig_garrison

ORIG = orig_garrison.load()
PRE = ('import json\nimport os\nimport re\nimport time\nimport unicodedata\n'
       'import cv2\nimport numpy as np\n')
PART = r'D:\DSH\SHP_Auto\GarrisonFarmPC\src\parts\part_d.py'
SRC = open(PART, encoding='utf-8').read()
NEW = {}
exec(compile(PRE + SRC, 'part_d.py', 'exec'), NEW)

NAMES = ['green_tiles', 'right3', 'drag_path', 'bench_ops', 'load_layout',
         'is_green', 'drag_name', 'near', 'deploy_from_bench']


def norm_const(c):
    if isinstance(c, types.CodeType):
        return ('code', c.co_name)
    return c


def sig(co, shift=0):
    ins = []
    for i in dis.get_instructions(co):
        av = i.argval
        if isinstance(av, types.CodeType):
            av = ('code', av.co_name)
        elif isinstance(av, int) and i.opcode in dis.hasjrel:
            av = i.argval
        ins.append((i.offset, i.opname, av))
    consts = tuple(norm_const(c) for c in co.co_consts
                   if not isinstance(c, types.CodeType))
    nested = [sig(c) for c in co.co_consts if isinstance(c, types.CodeType)]
    return (co.co_argcount, co.co_posonlyargcount, co.co_kwonlyargcount,
            co.co_flags, tuple(co.co_names), tuple(co.co_varnames),
            tuple(co.co_freevars), tuple(co.co_cellvars),
            consts, tuple(ins), tuple(nested))


ok = True
for n in NAMES:
    fa, fb = ORIG[n], NEW[n]
    if fa.__defaults__ != fb.__defaults__:
        print('MISMATCH defaults', n, fa.__defaults__, fb.__defaults__)
        ok = False
    if n == 'load_layout':
        # documented deviation: HERE (global string) -> _here() (call)
        continue
    a, b = sig(fa.__code__), sig(fb.__code__)
    if a != b:
        ok = False
        print('MISMATCH', n)
        for idx, (x, y) in enumerate(zip(a, b)):
            if x != y:
                print('   field[%d]: orig=%r' % (idx, x))
                print('             new =%r' % (y,))
        for idx in range(len(a), len(b)):
            print('   extra new field[%d]=%r' % (idx, b[idx]))
    else:
        nins = len(a[9])
        nconsts = len(a[8])
        print('BYTE-IDENTICAL structure: %-18s (%d insts, %d consts)' % (n, nins, nconsts))

# load_layout: expected to differ only by the HERE -> _here() substitution
a = sig(ORIG['load_layout'].__code__)
b = sig(NEW['load_layout'].__code__)
meta_ok = a[:8] == b[:8] or (
    a[0:8] == (b[0], b[1], b[2], b[3], tuple(n for n in b[4] if True), b[5], b[6], b[7]))
print('\nload_layout: intended deviation (HERE -> _here())')
print('  orig co_names:', a[4])
print('  new  co_names:', b[4])
print('  nins orig/new:', len(a[9]), len(b[9]), ' nconsts orig/new:', len(a[8]), len(b[8]))
print('  metadata equal except co_names:',
      a[0:4] == b[0:4] and a[5:9] == b[5:9])

print('ALL BYTE-IDENTICAL' if ok else 'HAS MISMATCH')
sys.exit(0 if ok else 1)
