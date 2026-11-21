"""Assemble src/garrison_pc/logic/garrison.py from 00_header.py + parts/part_*.py."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PARTS = os.path.join(ROOT, 'src', 'parts')
OUT = os.path.join(ROOT, 'src', 'garrison_pc', 'logic', 'garrison.py')

with open(os.path.join(PARTS, '_constants_generated.txt'), encoding='utf-8') as f:
    consts = f.read().strip()

# 集合字面量顺序在 repr 中不稳定；排序保证生成结果可复现
m = re.search(r'^DPS = \{(.*)\}$', consts, re.MULTILINE)
if m:
    items = sorted(x.strip() for x in m.group(1).split(',') if x.strip())
    consts = consts[:m.start()] + 'DPS = {' + ', '.join(items) + '}' + consts[m.end():]

with open(os.path.join(PARTS, '00_header.py'), encoding='utf-8') as f:
    header = f.read()

if '%s' in header:
    header = header.replace('%s', consts, 1)
else:  # 已替换过
    pass

part_names = ['part_a.py', 'part_b.py', 'part_c.py', 'part_d.py', 'part_e.py',
              'part_f.py', 'part_g.py']
chunks = [header]
missing = []
for name in part_names:
    path = os.path.join(PARTS, name)
    if not os.path.exists(path):
        missing.append(name)
        continue
    with open(path, encoding='utf-8') as f:
        body = f.read().strip()
    chunks.append('\n\n# ' + '=' * 70 + '\n# %s\n# ' % name + '=' * 70 + '\n\n' + body)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n\n'.join(chunks) + '\n')
print('wrote', OUT, os.path.getsize(OUT), 'bytes')
if missing:
    print('WARNING missing parts:', ', '.join(missing))
