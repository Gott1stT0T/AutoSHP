#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""part_b.py 差分测试：与 orig_garrison 冻结模块（3.11 字节码 oracle）逐函数对比。

运行：
    D:\\DSH\\SHP_Auto\\_tools\\py311\\python.exe src\\parts\\test_part_b.py

覆盖：
  match_key / prio_index / is_safe_op / rank / set_profile  —— 全笛卡尔积 + 固定种子随机
  strategy_name                                            —— 构造 panel 列表
  detect_rows                                              —— numpy 合成图（不同分割线位置）
  pick_strategy                                            —— 录制器：shot/tap/ocr/log/time/
                                                              scroll_grid/detect_rows/grid_shift
                                                              全部脚本化假实现

pick_strategy 的 oracle 是 patch_v12.md 里 v1.2 版的权威源码（原仓库运行期 exec 替换），
不是字节码里的旧版；旧版会在最后单独跑一遍，断言二者行为不同（证明用的是 v1.2）。
"""
import ast
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PART = os.path.join(HERE, 'part_b.py')
PATCH = os.path.join(HERE, 'patch_v12.md')
REF = r'D:\DSH\SHP_Auto\_ref'
DEPS = r'D:\DSH\SHP_Auto\_tools\py311-deps'
if os.path.isdir(DEPS):
    sys.path.insert(0, DEPS)
sys.path.insert(0, REF)

import numpy as np          # noqa: E402
import cv2                  # noqa: E402
import orig_garrison        # noqa: E402

TALLY = []
FAILS = []


def record(name, cases, bad):
    TALLY.append((name, cases, bad))
    if bad:
        FAILS.append(name)


def fresh_ns():
    ns = orig_garrison.load()
    ns['cv2'] = cv2
    ns['np'] = np
    return ns


def call(fn, args):
    try:
        return ('ok', fn(*args))
    except Exception as exc:                      # noqa: BLE001
        return ('exc', type(exc).__name__, str(exc))


def cmp_pure(name, cases):
    o, n = ORIG[name], NEW[name]
    bad = 0
    shown = 0
    for args in cases:
        ra, rb = call(o, args), call(n, args)
        if ra != rb:
            bad += 1
            if shown < 5:
                shown += 1
                print('  [FAIL] %s%r\n         orig=%r\n         new =%r' % (name, args, ra, rb))
    return bad


# ---------------------------------------------------------------------------
# 命名空间：ORIG = 冻结模块原样；NEW = 冻结模块 + part_b.py 覆盖
# ---------------------------------------------------------------------------
ORIG = fresh_ns()
NEW = fresh_ns()
with open(PART, encoding='utf-8') as _f:
    PART_SRC = _f.read()
exec(compile(PART_SRC, PART, 'exec'), NEW)

for _name in ('detect_rows', 'scroll_grid', 'strategy_name', 'pick_strategy',
              'set_profile', 'match_key', 'prio_index', 'is_safe_op', 'rank'):
    assert NEW[_name].__code__.co_filename == PART, _name
    assert NEW[_name] is not ORIG[_name], _name
print('loaded part_b.py: %d functions overridden' % 9)


# ---------------------------------------------------------------------------
# 1) match_key / prio_index / is_safe_op / rank / set_profile
# ---------------------------------------------------------------------------
class Weird:
    def __contains__(self, other):
        return isinstance(other, str) and other.startswith('维')


names = []
keys = []
for prof in ('PRIORITY_FULL', 'PRIORITY_LOW'):
    for k, full in ORIG[prof]:
        if k not in keys:
            keys.append(k)
        names.extend([k, full, ' ' + full + ' ', '  ' + full,
                      '【' + full + '】', '★' + full, full + '·', 'x' + full,
                      full + 'y', full[:-1], full[1:]])
for name in ORIG['SAFE_KEYS_FULL'] + ORIG['SAFE_KEYS_LOW']:
    if name not in keys:
        keys.append(name)
    names.append(name)
names += ['', ' ', '  ', '\t\n', '未知干员', 'ABC', 'abc', '123', '一', '拉', '塔露',
          '望x', '望xy', '望 x', 'x望', '维什戴尔号', '维什戴尔 号', '·', '【】',
          '史尔特尔X', '圣聆初雪', '初雪', '逻各斯.', 'Logic', '％', '·']
keys += ['', ' ', 'x', '一', '望', '锏', '霜', '塔露', 'ABC', '未知', '·',
         '维', '初雪', '逻各斯', '％']
names = list(dict.fromkeys(names))
keys = list(dict.fromkeys(keys))

match_cases = [(nm, kk) for nm in names for kk in keys]
rng = random.Random(20240614)
pool = list(names) + ['未知%d' % i for i in range(8)]
for _ in range(300):
    nm = rng.choice(pool)
    if rng.random() < 0.25 and nm:
        kk = rng.choice(list(nm))
    else:
        kk = rng.choice(keys)
    match_cases.append((nm, kk))
match_cases += [(123, '望'), (123, '维什戴尔'), (None, '望'), (0, 'x'), (Weird(), '维什戴尔')]
bad = cmp_pure('match_key', match_cases)
print('match_key: %d cases, %s' % (len(match_cases), 'PASS' if not bad else 'FAIL'))
record('match_key', len(match_cases), bad)

prio_cases = [(nm,) for nm in names] + [(123,), (None,), (Weird(),), ('未知干员',)]
bad_p = cmp_pure('prio_index', prio_cases)
bad_s = cmp_pure('is_safe_op', prio_cases)
print('prio_index: %d cases, %s' % (len(prio_cases), 'PASS' if not bad_p else 'FAIL'))
print('is_safe_op: %d cases, %s' % (len(prio_cases), 'PASS' if not bad_s else 'FAIL'))
record('prio_index', len(prio_cases), bad_p)
record('is_safe_op', len(prio_cases), bad_s)

tiers = [-1, 0, 1, 2, 3, 4, 5, 6, 7, 10, 99]
rank_cases = [(nm, t) for nm in names for t in tiers]
for _ in range(300):
    rank_cases.append((rng.choice(pool), rng.choice(tiers)))
rank_cases += [('塔露拉', 5), ('未知干员', 5), ('未知干员', 6), ('维什戴尔', 4),
               ('史尔特尔', 5.5), ('未知干员', 'x'), (None, 5), (123, 5)]
bad_r = cmp_pure('rank', rank_cases)
print('rank: %d cases, %s' % (len(rank_cases), 'PASS' if not bad_r else 'FAIL'))
record('rank', len(rank_cases), bad_r)


def state(ns):
    return (ns['PROFILE'],
            ns['PRIORITY'] is ns['PRIORITY_LOW'],
            ns['PRIORITY'] is ns['PRIORITY_FULL'],
            ns['PRIORITY'] == ns['PRIORITY_LOW'],
            ns['SAFE_KEYS'] is ns['SAFE_KEYS_LOW'],
            ns['SAFE_KEYS'] is ns['SAFE_KEYS_FULL'])


prof_cases = ['low', 'full', '', 'LOW', 'Full', 'low ', ' other', None, 0]
bad_sp = 0
detail = []
for prof in prof_cases:
    ra, rb = call(ORIG['set_profile'], (prof,)), call(NEW['set_profile'], (prof,))
    sa, sb = state(ORIG), state(NEW)
    if ra != rb or sa != sb:
        bad_sp += 1
        detail.append((prof, ra, rb, sa, sb))
    ORIG['set_profile']('full')
    NEW['set_profile']('full')
# 切换后 prio_index / is_safe_op / rank 的一致性（low 档优先级表不同）
for prof in ('low', 'full'):
    ORIG['set_profile'](prof)
    NEW['set_profile'](prof)
    for nm in names:
        for fn in ('prio_index', 'is_safe_op'):
            if call(ORIG[fn], (nm,)) != call(NEW[fn], (nm,)):
                bad_sp += 1
                detail.append((prof, fn, nm))
        for t in (4, 5, 6):
            if call(ORIG['rank'], (nm, t)) != call(NEW['rank'], (nm, t)):
                bad_sp += 1
                detail.append((prof, 'rank', nm, t))
ORIG['set_profile']('full')
NEW['set_profile']('full')
for d in detail[:5]:
    print('  [FAIL] set_profile', d)
print('set_profile: %d cases, %s' % (len(prof_cases) + 2 * len(names) * 5,
                                     'PASS' if not bad_sp else 'FAIL'))
record('set_profile', len(prof_cases) + 2 * len(names) * 5, bad_sp)


# ---------------------------------------------------------------------------
# 2) strategy_name —— 构造 panel 列表
# ---------------------------------------------------------------------------
CH = '一二三生命通过【】策略ABCabc0123 ·％★鿿'


def rand_text(rng):
    r = rng.random()
    s = ''.join(rng.choice(CH) for _ in range(rng.randint(0, 12)))
    if r < 0.20:
        s = '【' + s + '生命' + s + '通过'
    elif r < 0.35:
        s = s + '生命通过【'
    elif r < 0.45:
        s = '生命' + s + '通过' + s + '【'
    elif r < 0.60:
        s = '【策略名' + str(rng.randint(0, 20)) + '】'
    elif r < 0.70:
        s = '策略名' + s + 'X'
    return s


MARKED = '生命通过【'
PLAIN = '策略名'
strat_cases = [([],),
               ([('x', 600, MARKED)],),
               ([('x', 600, PLAIN)],),
               ([('x', 600, '【策略名】')],),
               ([('x', 600, '策略 名')],),
               ([('x', 600, '策略·名')],),
               ([('x', 600, '策略％名')],),
               ([('x', 600, '维什戴尔')],),
               ([('x', 600, 'ABC')],),
               ([('x', 600, '')],),
               ([('x', 600, ' ')],),
               ([('x', 600, '，。')],),
               ([('x', 519, PLAIN)],),
               ([('x', 520, PLAIN)],),
               ([('x', 521, PLAIN)],),
               ([('x', 584, PLAIN)],),
               ([('x', 649, PLAIN)],),
               ([('x', 650, PLAIN)],),
               ([('x', 651, PLAIN)],),
               ([('x', 600, '生命')],),
               ([('x', 600, '通过')],),
               ([('x', 600, '【')],),
               ([('x', 600, '【】')],),
               ([('x', 600, ['策略名'])],),
               ([('x', 600, ['生命', '通过', '【'])],),
               ([('x', 600, ('策略名',))],),
               ([('x', 600, ['策略名', 'X'])],),
               ([('x', 600, '策略名'), ('y', 610, MARKED)],),
               ([('x', 600, MARKED), ('y', 610, PLAIN)],),
               ([('x', 600, PLAIN), ('y', 700, '另一个')],),
               ([('x', 700, '另一个'), ('y', 600, PLAIN)],),
               ([('x', 519, 'A策略'), ('y', 600, PLAIN)],),
               ([('x', 600, None)],),
               ([('x', 600)],),
               ([('x', 600, PLAIN, 'extra')],),
               (None,),
               ([[600, PLAIN]],),
               ([('x', '600', PLAIN)],),
               ([('x', 600, PLAIN), None],)]
rng = random.Random(777)
for _ in range(300):
    panel = []
    for _ in range(rng.randint(0, 6)):
        x = rng.choice([1440, 1500, 1600, 1800])
        y = rng.choice([500, 519, 520, 521, 584, 585, 649, 650, 651, 700, 1080])
        panel.append((x, y, rand_text(rng)))
    strat_cases.append((panel,))
bad_st = cmp_pure('strategy_name', strat_cases)
print('strategy_name: %d cases, %s' % (len(strat_cases), 'PASS' if not bad_st else 'FAIL'))
record('strategy_name', len(strat_cases), bad_st)


# ---------------------------------------------------------------------------
# 3) detect_rows —— numpy 合成图
# ---------------------------------------------------------------------------
def build_img(segs, h=1080, w=1920):
    """segs: [(y0, y1, amp)] 行 [y0, y1) 的第一列带 (620:740) 以 std≈amp 抖动。"""
    band = np.full((h, 120), 100, np.uint8)
    for y0, y1, amp in segs:
        for y in range(max(0, y0), min(h, y1)):
            if amp <= 0:
                band[y, :] = 100
            else:
                band[y, ::2] = 0
                band[y, 1::2] = min(255, amp * 2)
    img = np.full((h, w, 3), 100, np.uint8)
    img[:, 620:740, :] = band[:, :, None]
    return img


row_cases = [
    [],
    [(300, 400, 127)],
    [(300, 359, 127)],          # 59 行：太短
    [(300, 360, 127)],          # 恰好 60 行
    [(300, 361, 127)],
    [(190, 300, 127)],          # 起点在 range(GRID_TOP-60) 上
    [(190, 260, 127)],          # 中心 < GRID_TOP -> 丢弃
    [(190, 250, 127)],
    [(200, 300, 127)],
    [(250, 400, 127)],
    [(300, 400, 17)],           # std 未过阈值 18
    [(300, 400, 18)],
    [(300, 400, 19)],
    [(300, 400, 0)],
    [(900, 1069, 127)],         # 结束于 range 末行（GRID_BOTTOM+19）
    [(900, 1080, 127)],
    [(1000, 1069, 127)],        # 中心 1034 > GRID_BOTTOM-20 -> 丢弃
    [(1000, 1060, 127)],
    [(300, 400, 127), (410, 500, 127)],
    [(300, 400, 127), (401, 500, 127)],
    [(300, 400, 127), (400, 900, 127)],
    [(1069, 1080, 127)],
    [(150, 190, 127)],
    [(190, 400, 127)],
    [(300, 400, 127)],          # h=1080
]
rng = random.Random(4242)
for _ in range(250):
    segs = []
    y = rng.randint(120, 320)
    while y < 1070:
        n = rng.choice([1, 3, 5, 20, 40, 59, 60, 61, 80, 120, 200, 300, 500])
        amp = rng.choice([0, 5, 17, 18, 19, 25, 60, 100, 127, 200])
        segs.append((y, min(y + n, 1080), amp))
        y += n + rng.choice([0, 1, 2, 5, 20, 60])
    row_cases.append(segs)

bad_dr = 0
shown = 0
for segs in row_cases:
    img = build_img(segs)
    ra = call(ORIG['detect_rows'], (img,))
    rb = call(NEW['detect_rows'], (img,))
    if ra != rb:
        bad_dr += 1
        if shown < 5:
            shown += 1
            print('  [FAIL] detect_rows segs=%r\n         orig=%r\n         new =%r'
                  % (segs, ra, rb))
# 高度不足 / 空图 -> 同样抛错
for segs, h in (([(300, 400, 127)], 1069), ([], 0), ([], 1)):
    img = build_img(segs, h=h)
    ra = call(ORIG['detect_rows'], (img,))
    rb = call(NEW['detect_rows'], (img,))
    if ra != rb:
        bad_dr += 1
        print('  [FAIL] detect_rows h=%d\n         orig=%r\n         new =%r' % (h, ra, rb))
print('detect_rows: %d cases, %s' % (len(row_cases) + 3, 'PASS' if not bad_dr else 'FAIL'))
record('detect_rows', len(row_cases) + 3, bad_dr)

# 语义自检（oracle 与实现都应是这些值）：行中心 = (起+止)//2，过短/越界丢弃
sanity = [([(300, 400, 127)], [350]),
          ([(300, 359, 127)], []),          # 59 行太短
          ([(300, 360, 127)], [330]),       # 正好 60 行
          ([(190, 260, 127)], []),          # 中心 225 < GRID_TOP
          ([(250, 400, 127)], [325]),
          ([(1000, 1069, 127)], []),        # 中心 1034 > GRID_BOTTOM-20
          ([(900, 1069, 127)], [984]),      # 末尾行强制收尾
          ([(300, 400, 127), (410, 500, 127)], [350, 455]),
          ([(300, 400, 17)], [])]           # std 未过 18
bad_sanity = 0
for segs, want in sanity:
    img = build_img(segs)
    got_o = ORIG['detect_rows'](img)
    got_n = NEW['detect_rows'](img)
    if got_o != want or got_n != want:
        bad_sanity += 1
        print('  [FAIL] detect_rows 语义 segs=%r want=%r orig=%r new=%r'
              % (segs, want, got_o, got_n))
print('detect_rows 语义自检: %d cases, %s' % (len(sanity), 'PASS' if not bad_sanity else 'FAIL'))
if bad_sanity:
    FAILS.append('detect_rows/semantics')


# ---------------------------------------------------------------------------
# 4) pick_strategy —— 录制器
# ---------------------------------------------------------------------------
class Panel(list):
    """带脚本属性的 OCR 结果列表（[(cx, cy, text)]）。"""
    count = None
    name = ''


def mk_panel(has=True, count=None, name='', spaced=False, name_text=None, name_y=600):
    rows = []
    if has:
        rows.append((1500, 200, '初 始 生 命 值' if spaced else '初始生命值'))
    if name_text is not None:
        rows.append((1500, name_y, name_text))
    p = Panel(rows)
    p.count = count
    p.name = name
    return p


NO_PANEL = mk_panel(has=False)


def fill(spec=None, cells=None):
    """补满 GRID_X × GRID_Y，未指定的格子用无面板（count=None）。"""
    cells = dict(cells or {})
    for gx in ORIG['GRID_X']:
        for gy in ORIG['GRID_Y']:
            cells.setdefault((gx, gy), [spec] if spec is not None else [NO_PANEL])
    return cells


def install(ns, rec, sc):
    st = {'cell': None, 'attempt': 0, 'shot': 0, 'shift': 0, 'rows': 0}
    cells = sc['cells']
    shifts = sc.get('shifts', [5])
    rows = sc.get('rows', [[]])
    ns['TARGET'] = sc.get('target', 3)
    fake_strategy = sc.get('fake_strategy', True)

    def tap(x, y, wait=0.6):
        rec.append(('tap', x, y, wait))
        st['cell'] = (x, y)
        st['attempt'] = 0

    def shot():
        rec.append(('shot',))
        st['shot'] += 1
        return ('IMG', st['shot'])

    def ocr(img, box=None):
        rec.append(('ocr', img, box))
        seq = cells.get(st['cell'], [NO_PANEL])
        i = st['attempt']
        st['attempt'] += 1
        return seq[min(i, len(seq) - 1)]

    def log(*args):
        rec.append(('log',) + args)

    def scroll_grid():
        rec.append(('scroll_grid',))
        st['cell'] = None

    def grid_shift(a, b):
        rec.append(('grid_shift', a, b))
        i = st['shift']
        st['shift'] += 1
        return shifts[min(i, len(shifts) - 1)]

    def detect_rows(img):
        rec.append(('detect_rows', img))
        i = st['rows']
        st['rows'] += 1
        return list(rows[min(i, len(rows) - 1)])

    ns['tap'] = tap
    ns['shot'] = shot
    ns['ocr'] = ocr
    ns['log'] = log
    ns['scroll_grid'] = scroll_grid
    ns['grid_shift'] = grid_shift
    ns['detect_rows'] = detect_rows
    ns['passed_count'] = lambda panel: panel.count
    if fake_strategy:
        ns['strategy_name'] = lambda panel: panel.name

    class FakeTime:
        @staticmethod
        def sleep(s):
            rec.append(('sleep', s))

    ns['time'] = FakeTime()


def make_ns(kind):
    ns = fresh_ns()
    if kind == 'new':
        exec(compile(PART_SRC, PART, 'exec'), ns)
    elif kind == 'patch':
        exec(compile(PATCH_SRC['pick_strategy'], '<patch_v12:pick_strategy>', 'exec'), ns)
    elif kind == 'old':
        ns['has_color_badge'] = lambda img, x, y: False
        ns['has_badge'] = lambda img, x, y: False
    else:
        raise AssertionError(kind)
    return ns


def run_pick(kind, sc):
    ns = make_ns(kind)
    rec = []
    install(ns, rec, sc)
    res = call(ns['pick_strategy'], (None,))
    return rec, res


# patch_v12.md 里 v1.2 的权威源码（作为 pick_strategy 的 oracle）
def load_patch():
    src = open(PATCH, encoding='utf-8').read()
    start = src.index('```python') + len('```python')
    end = src.index('```', start)
    block = src[start:end]
    tree = ast.parse(block)
    out = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            out[node.name] = ast.get_source_segment(block, node)
    return out


PATCH_SRC = load_patch()
assert 'pick_strategy' in PATCH_SRC and 'passed_count' in PATCH_SRC, PATCH_SRC.keys()

GX0, GX1 = ORIG['GRID_X'][0], ORIG['GRID_X'][1]
GY0 = ORIG['GRID_Y'][0]
CELL0 = (GX0, GY0)
CELL1 = (GX1, GY0)

scenarios = []
# 全部已满 3 次：走完 16 格 -> 滚动 -> shift 过小 -> 退出
scenarios.append(dict(cells=fill(mk_panel(count=3, name='甲'))))
# 第一格命中
scenarios.append(dict(cells=fill(mk_panel(count=3), {CELL0: [mk_panel(count=1, name='策略甲')]})))
# 面板读不出来（无"初始生命值"）：3 次尝试后跳过
scenarios.append(dict(cells=fill(mk_panel(count=3), {CELL0: [NO_PANEL]})))
# 第一次 count=None，第二次成功
scenarios.append(dict(cells=fill(mk_panel(count=3),
                                {CELL0: [mk_panel(count=None, name=''),
                                         mk_panel(count=2, name='策略乙')]})))
# 名字识别不出 -> 占位 label 返回
scenarios.append(dict(cells=fill(mk_panel(count=3), {CELL0: [mk_panel(count=0, name='')]})))
# 空格变体面板
scenarios.append(dict(cells=fill(mk_panel(count=3),
                                {CELL0: [mk_panel(count=1, name='策略丙', spaced=True)]})))
# 第二格命中
scenarios.append(dict(cells=fill(mk_panel(count=3), {CELL1: [mk_panel(count=0, name='策略丁')]})))
# 多页：第一页全满，shift 大 -> detect_rows 返回新行 -> 第二页命中
scenarios.append(dict(cells=fill(mk_panel(count=3)),
                      shifts=[100, 5], rows=[[400, 600]]))
# shift 返回 None -> 用 detect_rows
scenarios.append(dict(cells=fill(mk_panel(count=3)), shifts=[None], rows=[[400, 600]]))
# detect_rows 返回空 -> break
scenarios.append(dict(cells=fill(mk_panel(count=3)), shifts=[None], rows=[[]]))
# 8 页都滚不到底（shift 一直很大）
scenarios.append(dict(cells=fill(mk_panel(count=3)), shifts=[100], rows=[[400, 600]]))
# TARGET=1：count=1 已达标
scenarios.append(dict(cells=fill(mk_panel(count=1, name='甲')), target=1))
# 最后一格命中
scenarios.append(dict(cells=fill(mk_panel(count=3),
                                {(ORIG['GRID_X'][-1], ORIG['GRID_Y'][-1]):
                                 [mk_panel(count=0, name='策略戊')]})))
# 第一格 count=3 恰好达标
scenarios.append(dict(cells=fill(mk_panel(count=3), {CELL0: [mk_panel(count=3, name='甲')]})))
# 面板先读不出、后读出但 count 一直 None
scenarios.append(dict(cells=fill(mk_panel(count=3),
                                {CELL0: [NO_PANEL, mk_panel(count=None),
                                         mk_panel(count=None)]})))
# 集成：不假 strategy_name，用各命名空间自己的实现，名字由 panel 文本决定
scenarios.append(dict(cells=fill(mk_panel(count=3),
                                {CELL0: [mk_panel(count=1, name_text='策略己')]}),
                      fake_strategy=False))
scenarios.append(dict(cells=fill(mk_panel(count=3),
                                {CELL0: [mk_panel(count=0, name_text='【策略庚】')]}),
                      fake_strategy=False))
scenarios.append(dict(cells=fill(mk_panel(count=3),
                                {CELL0: [mk_panel(count=0, name_text='ABC')]}),
                      fake_strategy=False))
scenarios.append(dict(cells=fill(mk_panel(count=3),
                                {CELL0: [mk_panel(count=2, name_text='策略辛', spaced=True,
                                                  name_y=521)]}),
                      fake_strategy=False))

bad_pick = 0
total_rec = 0
for i, sc in enumerate(scenarios):
    rec_ref, res_ref = run_pick('patch', sc)
    rec_new, res_new = run_pick('new', sc)
    total_rec += len(rec_new)
    if (rec_ref, res_ref) != (rec_new, res_new):
        bad_pick += 1
        print('  [FAIL] pick_strategy scenario #%d' % i)
        for a, b in zip(rec_ref, rec_new):
            if a != b:
                print('         first diff: ref=%r new=%r' % (a, b))
                break
        print('         ref len=%d new len=%d res ref=%r new=%r'
              % (len(rec_ref), len(rec_new), res_ref, res_new))
print('pick_strategy: %d scenarios (%d 调用记录), %s'
      % (len(scenarios), total_rec, 'PASS' if not bad_pick else 'FAIL'))
record('pick_strategy', len(scenarios), bad_pick)

# 分支覆盖：所有 log 文案 / 返回占位名都应出现过
all_logs = set()
all_res = set()
for sc in scenarios:
    rec, res = run_pick('new', sc)
    for item in rec:
        if item[0] == 'log':
            all_logs.add(item[1])
    all_res.add(str(res))
expect_logs = ['通关次数读取失败', '无法识别名称', '跳过策略:', '选择策略: ',
               '策略列表下滑，继续查找（本页 ', '没有找到通关次数未达标的策略']
missing = [m for m in expect_logs if not any(l.startswith(m) for l in all_logs)]
if missing:
    FAILS.append('pick_strategy/branch-coverage')
    print('  [FAIL] 未覆盖的日志分支:', missing)
print('pick_strategy 分支覆盖: %d 种日志文案, 返回 %d 种结果'
      % (len(all_logs), len(all_res)))
for line in sorted(all_logs):
    print('    log:', line[:70])
if not any('无法识别名称[' in r for r in all_res):
    FAILS.append('pick_strategy/placeholder-label')
    print('  [FAIL] 未出现无法识别名称占位 label')

# 证明用的是 v1.2 而不是字节码旧版：同样场景下调用序列必然不同
diff_proof = False
for sc in scenarios[:6]:
    rec_old, res_old = run_pick('old', sc)
    rec_ref, res_ref = run_pick('patch', sc)
    if (rec_old, res_old) != (rec_ref, res_ref):
        diff_proof = True
        break
print('pick_strategy 与旧字节码版本行为不同（确认为 v1.2）:', 'YES' if diff_proof else 'NO')
if not diff_proof:
    FAILS.append('pick_strategy/v12-proof')
    print('  [FAIL] 无法区分 v1.2 与旧版')


# ---------------------------------------------------------------------------
# 5) scroll_grid —— 录制器（纯副作用函数，无返回值）
# ---------------------------------------------------------------------------
sc_rec = []


def _mk_ns_for_scroll():
    ns = fresh_ns()
    ns['touch'] = lambda kind, x, y: sc_rec.append(('touch', kind, x, y))
    ns['drag_path'] = lambda x1, y1, x2, y2, steps: sc_rec.append(
        ('drag_path', x1, y1, x2, y2, steps))

    class T:
        @staticmethod
        def sleep(s):
            sc_rec.append(('sleep', s))

    ns['time'] = T
    return ns


del sc_rec[:]
n1 = _mk_ns_for_scroll()
r_o = call(n1['scroll_grid'], ())
rec_o = list(sc_rec)
del sc_rec[:]
n2 = _mk_ns_for_scroll()
r_n = call(n2['scroll_grid'], ())
rec_n = list(sc_rec)
bad_sg = 0 if (rec_o, r_o) == (rec_n, r_n) else 1
SCROLL_WANT = [('touch', 'DOWN', 1000, 900),
               ('drag_path', 1000, 900, 1000, 480, 14),
               ('sleep', 0.5),
               ('touch', 'UP', 1000, 480),
               ('sleep', 0.8)]
if bad_sg:
    print('  [FAIL] scroll_grid\n         orig=%r\n         new =%r' % (rec_o, rec_n))
if rec_n != SCROLL_WANT:
    bad_sg = 1
    FAILS.append('scroll_grid/expected')
    print('  [FAIL] scroll_grid 序列与规格不符:', rec_n)
print('scroll_grid: %d calls, %s' % (len(rec_n), 'PASS' if not bad_sg else 'FAIL'),
      rec_n)
record('scroll_grid', 1, bad_sg)


# ---------------------------------------------------------------------------
# 6) 结构等价：逐指令对比复现源码与原始字节码（唯一差异应为 attr/method 编码）
# ---------------------------------------------------------------------------
import builtins     # noqa: E402
import dis          # noqa: E402


def code_sig(code):
    consts = tuple(('<code:%s>' % c.co_name) if hasattr(c, 'co_code') else c
                   for c in code.co_consts)
    ins = []
    for i in dis.get_instructions(code):
        op = i.opname
        if op in ('LOAD_ATTR', 'LOAD_METHOD'):
            op = '<attr-or-method>'
        av = i.argval
        if hasattr(av, 'co_code'):
            av = ('<code>', av.co_name)
        ins.append((op, av))
    sub = tuple(code_sig(c) for c in code.co_consts if hasattr(c, 'co_code'))
    return (code.co_name, code.co_argcount, code.co_varnames, code.co_names,
            consts, tuple(ins), sub)


bytecode_bad = []
for _n in ('detect_rows', 'scroll_grid', 'strategy_name', 'set_profile',
           'match_key', 'prio_index', 'is_safe_op', 'rank'):
    sig_o, sig_n = code_sig(ORIG[_n].__code__), code_sig(NEW[_n].__code__)
    if sig_o != sig_n:
        bytecode_bad.append(_n)
        for k, (a, b) in enumerate(zip(sig_o, sig_n)):
            if a != b:
                if k == 5:
                    for j, (x, y) in enumerate(zip(a, b)):
                        if x != y:
                            print('  [DIFF] %s instr#%d %r != %r' % (_n, j, x, y))
                            break
                else:
                    print('  [DIFF] %s field#%d\n         orig=%r\n         new =%r'
                          % (_n, k, a, b))
                break
print('结构等价（逐指令/常量/变量名，attr-method 视为同一编码）: %d/%d 完全相同'
      % (8 - len(bytecode_bad), 8))
if bytecode_bad:
    print('  差异函数:', bytecode_bad)
# LOAD_ATTR/LOAD_METHOD 的原始取舍（参考用，不影响行为）
attr_sites = []
for _n in ('detect_rows', 'scroll_grid'):
    for i in dis.get_instructions(ORIG[_n].__code__):
        if i.opname in ('LOAD_ATTR', 'LOAD_METHOD'):
            attr_sites.append((_n, i.opname, i.argval))
print('  原始字节码里模块属性调用的编码:', attr_sites)

# pick_strategy 必须与 patch_v12.md 的 v1.2 源码 AST 完全一致（不是旧字节码版本）
def _fn_ast(src, name):
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError('missing ' + name)


mine_ast = _fn_ast(PART_SRC, 'pick_strategy')
patch_ast = _fn_ast(PATCH_SRC['pick_strategy'], 'pick_strategy')
same_ast = ast.dump(mine_ast) == ast.dump(patch_ast)
print('pick_strategy 与 patch_v12.md v1.2 源码 AST 一致:', 'YES' if same_ast else 'NO')
if not same_ast:
    FAILS.append('pick_strategy/ast-mismatch')
    print('  [FAIL] pick_strategy 与 patch_v12.md 不一致')

# 文件形状：只放 9 个函数定义，按序，无 import/常量/其他语句
want_order = ['detect_rows', 'scroll_grid', 'strategy_name', 'pick_strategy',
              'set_profile', 'match_key', 'prio_index', 'is_safe_op', 'rank']
top = ast.parse(PART_SRC).body
bad_shape = [type(n).__name__ for n in top if not isinstance(n, ast.FunctionDef)]
got_order = [n.name for n in top if isinstance(n, ast.FunctionDef)]
shape_ok = not bad_shape and got_order == want_order
print('part_b.py 形状: 仅函数定义/顺序正确:', 'YES' if shape_ok else 'NO', got_order)
if not shape_ok:
    FAILS.append('part_b/shape')
    print('  [FAIL] 文件形状不符, 非函数节点:', bad_shape)

# 所有引用的全局名都必须由 00_header.py + 常量提供 / 或为内建
HEADER = os.path.join(HERE, '00_header.py')
CONSTS = os.path.join(HERE, '_constants_generated.txt')
with open(HEADER, encoding='utf-8') as _f:
    HEADER_SRC = _f.read()
with open(CONSTS, encoding='utf-8') as _f:
    CONSTS_SRC = _f.read().strip()
assert '%s' in HEADER_SRC
asm = {'__name__': 'logic_asm', '__file__': 'garrison.py'}
exec(compile(HEADER_SRC.replace('%s', CONSTS_SRC, 1), HEADER, 'exec'), asm)
exec(compile(PART_SRC, PART, 'exec'), asm)


def collect_names(code, acc):
    acc.update(code.co_names)
    for c in code.co_consts:
        if hasattr(c, 'co_code'):
            collect_names(c, acc)
    return acc


needed = set()
for _n in want_order:
    collect_names(asm[_n].__code__, needed)
missing = sorted(n for n in needed if n not in asm and not hasattr(builtins, n))
print('装配检查: 引用全局名 %d 个, 缺失 %s' % (len(needed), missing or '无'))
if missing:
    FAILS.append('part_b/unresolved-names')
    print('  [FAIL] 未解析的全局名:', missing)
# 装配后行为抽样（与冻结模块对照）
asm_ok = 0
asm_bad = 0
for nm in ['塔露拉', '维什戴尔', '未知干员', '', '史尔特尔']:
    for t in (1, 5, 6):
        if asm['rank'](nm, t) == ORIG['rank'](nm, t):
            asm_ok += 1
        else:
            asm_bad += 1
asm['set_profile']('low')
if asm['PRIORITY'] is not asm['PRIORITY_LOW']:
    asm_bad += 1
print('装配后行为抽样: %d OK, %d BAD' % (asm_ok, asm_bad))
if asm_bad:
    FAILS.append('part_b/asm-behavior')


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
print('=' * 74)
for name, cases, bad in TALLY:
    print('%-16s cases=%-6d %s' % (name, cases, 'PASS' if bad == 0 else 'FAIL(%d)' % bad))
print('=' * 74)
if FAILS:
    print('RESULT: FAIL', FAILS)
    sys.exit(1)
print('RESULT: ALL PASS')
