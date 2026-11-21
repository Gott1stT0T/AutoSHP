# -*- coding: utf-8 -*-
"""load_layout: prove the only deviation from the frozen bytecode is HERE -> _here().

Strategy: the part_d stream must be exactly the frozen stream with the single
`LOAD_GLOBAL HERE` replaced by `LOAD_GLOBAL _here` + `PRECALL 0` + `CALL 0`,
and every later offset / jump target shifted by the same constant.
"""
import dis
import sys
import types

sys.path.insert(0, r'D:\DSH\SHP_Auto\_ref')
import orig_garrison

ORIG = orig_garrison.load()
PRE = ('import json\nimport os\nimport re\nimport time\nimport unicodedata\n'
       'import cv2\nimport numpy as np\n')
SRC = open(r'D:\DSH\SHP_Auto\GarrisonFarmPC\src\parts\part_d.py', encoding='utf-8').read()
NEW = {}
exec(compile(PRE + SRC, 'part_d.py', 'exec'), NEW)


def stream(co):
    return [(i.offset, i.opname, i.arg, i.argval) for i in dis.get_instructions(co)]


o = stream(ORIG['load_layout'].__code__)
n = stream(NEW['load_layout'].__code__)
JREL = {dis.opname[op] for op in dis.hasjrel}

here_idx = [k for k, ins in enumerate(o) if ins[1] == 'LOAD_GLOBAL' and ins[3] == 'HERE']
assert here_idx == [1], here_idx

head_ok = (n[0][:3] == (0, 'RESUME', 0)
           and n[1][1] == 'LOAD_GLOBAL' and n[1][3] == '_here'
           and n[2][:3] == (14, 'PRECALL', 0)
           and n[3][:3] == (18, 'CALL', 0))
print('head replacement LOAD_GLOBAL HERE -> LOAD_GLOBAL _here; PRECALL 0; CALL 0:', head_ok)

shift = n[4][0] - o[2][0]
print('constant offset shift after substitution: %+d' % shift)

ok = head_ok
for k in range(2, len(o)):
    eo, eop, earg, eav = o[k]
    mo, mop, marg, mav = n[k + 2]
    if eop in JREL:
        eav = eav + shift
    if (eo + shift, eop, earg, eav) != (mo, mop, marg, mav):
        ok = False
        print('MISMATCH at orig[%d]=%r vs new[%d]=%r (expected offset %d)'
              % (k, o[k], k + 2, n[k + 2], eo + shift))
        break

print('instruction count: orig=%d new=%d (must differ by 2)' % (len(o), len(n)))
print('tail byte-identical under constant shift:', ok and len(n) == len(o) + 2)

oc, nc = ORIG['load_layout'].__code__, NEW['load_layout'].__code__
consts_ok = ([c for c in oc.co_consts if not isinstance(c, types.CodeType)] ==
             [c for c in nc.co_consts if not isinstance(c, types.CodeType)])
print('co_consts equal:', consts_ok, [c for c in nc.co_consts if not isinstance(c, types.CodeType)])
print('co_varnames equal:', oc.co_varnames == nc.co_varnames, nc.co_varnames)
print('co_names equal except HERE/_here:',
      oc.co_names[1:] == nc.co_names[1:], nc.co_names)
print('argcount/flags equal:', (oc.co_argcount, oc.co_flags) == (nc.co_argcount, nc.co_flags))
sys.exit(0 if (ok and len(n) == len(o) + 2 and consts_ok) else 1)

