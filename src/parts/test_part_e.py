"""part_e.py 的差分测试：tile_order / tile_xy 随机对比 oracle，
deploy_from_bench_old / deploy_layout 用"录制器"对比调用序列、返回值与副作用。

用 3.11 运行：
    D:\\DSH\\SHP_Auto\\_tools\\py311\\python.exe test_part_e.py
"""
import random
import sys
import types

sys.path.insert(0, r'D:\DSH\SHP_Auto\_ref')
import orig_garrison

PART = r'D:\DSH\SHP_Auto\GarrisonFarmPC\src\parts\part_e.py'
ORACLE_NAMES = ('deploy_from_bench_old', 'tile_order', 'tile_xy', 'deploy_layout')

NAMES = ['维什戴尔', '望', '能天使', '初雪', '蕾缪安', '逻各斯', '冻河', '塔露拉', '星熊',
         '阿米娅', '预备干员-近卫', '无名小卒', '', '?', 'WEI']
SAFE_TABS = ('特质', '技能', '特性', '天赋')

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print('FAIL:', msg)


def load_new():
    ns = orig_garrison.load()
    exec(open(PART, encoding='utf-8').read(), ns)
    return ns


def load_orig():
    return orig_garrison.load()


# ---------------------------------------------------------------------------
# 0. 结构与字节码核对（归一化：LOAD_METHOD/LOAD_ATTR 视为等价，跳转只看是否跳转）
# ---------------------------------------------------------------------------
def norm_ins(code):
    import dis
    out = []
    for ins in dis.get_instructions(code):
        op, v = ins.opname, ins.argval
        if op == 'LOAD_METHOD':
            op = 'LOAD_ATTR'
        if op == 'EXTENDED_ARG':
            continue
        if isinstance(v, types.CodeType):
            v = ('<code>', v.co_name)
        if op.startswith(('JUMP', 'POP_JUMP', 'FOR_ITER')):
            v = 'target'
        out.append((op, v))
    return out


def cmp_code(a, b, path, diffs):
    for attr in ('co_varnames', 'co_names', 'co_cellvars', 'co_freevars', 'co_argcount'):
        if getattr(a, attr) != getattr(b, attr):
            diffs.append((path, attr, getattr(a, attr), getattr(b, attr)))
    ia, ib = norm_ins(a), norm_ins(b)
    if ia != ib:
        for i in range(max(len(ia), len(ib))):
            pa = ia[i] if i < len(ia) else None
            pb = ib[i] if i < len(ib) else None
            if pa != pb:
                diffs.append((path, 'ins@%d' % i, pa, pb))
                break
    ca = [c for c in a.co_consts if isinstance(c, types.CodeType)]
    cb = [c for c in b.co_consts if isinstance(c, types.CodeType)]
    if len(ca) != len(cb):
        diffs.append((path, 'nested-count', len(ca), len(cb)))
    for x, y in zip(ca, cb):
        cmp_code(x, y, path + '/' + x.co_name, diffs)
    return diffs


def test_structure(orig, new):
    for n in ORACLE_NAMES:
        diffs = cmp_code(orig[n].__code__, new[n].__code__, n, [])
        check(not diffs, 'bytecode %s: %r' % (n, diffs[:3]))
        check(orig[n].__doc__ == new[n].__doc__, 'docstring %s' % n)
    check(orig['deploy_from_bench_old'].__defaults__ == (False, None, False),
          'defaults deploy_from_bench_old %r' % (new['deploy_from_bench_old'].__defaults__,))
    # oracle 的 deploy_layout 没有 board 默认值，移植版按规格补了 board=None
    check(orig['deploy_layout'].__defaults__ == ('', 0, 0), 'oracle defaults deploy_layout')
    check(new['deploy_layout'].__defaults__ == (None, '', 0, 0),
          'defaults deploy_layout %r' % (new['deploy_layout'].__defaults__,))
    print('# structure/bytecode checked')


# ---------------------------------------------------------------------------
# 1. 纯函数：tile_order / tile_xy
# ---------------------------------------------------------------------------
def make_layout(rng):
    def pts(n):
        return [[rng.randrange(200, 1700), rng.randrange(120, 760)] for _ in range(n)]
    lay = {'safe': pts(rng.randint(0, 4)), 'path': pts(rng.randint(0, 4)),
           'lift': [760, 650]}
    if rng.random() < 0.8:
        lay['rest'] = pts(rng.randint(0, 3))
    return lay


def tile_names(lay):
    out = []
    for k in ('safe', 'path', 'rest'):
        for i in range(len(lay.get(k, []))):
            out.append('%s%d' % (k, i))
    return out


def safe_call(fn, *a):
    try:
        return ('ok', fn(*a))
    except Exception as e:  # noqa: BLE001
        return ('exc', type(e).__name__, str(e))


def test_pure(orig, new, rng):
    cases = []
    # 固定常量：PRIORITY 名 / SAFE_KEYS 名 / 未知名 / 空串 / 大小写与子串
    for nm in NAMES:
        cases.append(nm)
    for lay in (
        {'safe': [[1, 2]] * 3, 'path': [[3, 4]] * 2},
        {'safe': [], 'path': [], 'rest': []},
        {'safe': [[10, 20]] * 7, 'path': [], 'rest': [[30, 40]]},
        {'safe': [], 'path': [[5, 6]] * 9, 'rest': []},
    ):
        for nm in NAMES + ['维什戴尔·', '初雪', '望 ']:
            orig['LAYOUT'] = lay
            new['LAYOUT'] = lay
            for f in ('tile_order',):
                check(safe_call(orig[f], nm) == safe_call(new[f], nm),
                      '%s(%r) LAYOUT=%r' % (f, nm, lay))
            tn_list = tile_names(lay) + ['safe99', 'path99', 'rest99', 'foo0', 'safe', '',
                                         'path-1', 'SAFE0', 'safeX', 'rest1 ', 'safe01']
            for tn in tn_list:
                check(safe_call(orig['tile_xy'], tn) == safe_call(new['tile_xy'], tn),
                      'tile_xy(%r) LAYOUT=%r' % (tn, lay))
    # 随机
    for _ in range(200):
        lay = make_layout(rng)
        orig['LAYOUT'] = lay
        new['LAYOUT'] = lay
        nm = rng.choice(NAMES)
        check(orig['tile_order'](nm) == new['tile_order'](nm), 'tile_order rnd %r' % (nm,))
        tns = tile_names(lay)
        if tns:
            tn = rng.choice(tns)
            check(orig['tile_xy'](tn) == new['tile_xy'](tn), 'tile_xy rnd %r' % (tn,))
        for tn in ('zzz%d' % rng.randrange(9), 'safe%d' % rng.randrange(9)):
            check(safe_call(orig['tile_xy'], tn) == safe_call(new['tile_xy'], tn),
                  'tile_xy rnd exc %r' % (tn,))
    print('# tile_order/tile_xy checked')


# ---------------------------------------------------------------------------
# 2. 录制器：把副作用函数换成脚本化假实现
# ---------------------------------------------------------------------------
class Img:
    __slots__ = ('n',)

    def __init__(self, n):
        self.n = n

    def __repr__(self):
        return 'Img(%d)' % self.n


class FakeBoard:
    def __init__(self, used=(), hi_tiles=(), occ=None, pending=False):
        self.used = list(used)
        self.hi_tiles = list(hi_tiles)
        self.occ = dict(occ or {})
        self.pending = pending


class FakeTime:
    def __init__(self, rec):
        self.rec = rec

    def sleep(self, s):
        self.rec.append(('sleep', s))


class Harness:
    """把模块里的 shot/tap/... 换成脚本化假实现，并录制调用序列。"""

    def __init__(self, mod, script, layout):
        self.mod = mod
        self.script = script
        self.rec = []
        self.nimg = 0
        mod['LAYOUT'] = layout
        mod['LAST_TIER'] = [1]
        mod['LAST_NAME'] = ['']
        mod['LAST_TILE'] = [None]
        self._install()

    def _get(self, key, k, default):
        d = self.script.get(key)
        if d is None:
            return default
        return d.get(k, default)

    def _install(self):
        mod, rec, script = self.mod, self.rec, self.script
        add = rec.append

        def shot():
            add(('shot',))
            img = Img(self.nimg)
            self.nimg += 1
            return img

        def slots_left(img):
            add(('slots_left', img.n))
            return self._get('slots_left', img.n, None)

        def touch(kind, x, y):
            add(('touch', kind, x, y))

        def tap(x, y, wait=0.6):
            add(('tap', x, y, wait))

        def drag_path(x1, y1, x2, y2, steps=12):
            add(('drag_path', x1, y1, x2, y2, steps))

        def swipe(x1, y1, x2, y2, ms=500, wait=0.8):
            add(('swipe', x1, y1, x2, y2, ms, wait))

        def ocr(img, box=None):
            add(('ocr', img.n, box))
            return list(self._get('ocr', (img.n, box), []))

        def save(img, tag=''):
            add(('save', img.n, tag))

        def log(*args):
            add(('log',) + args)

        def yellow_ratio(img, box):
            add(('yellow_ratio', img.n, box))
            return self._get('yellow_ratio', (img.n, box), 0.0)

        def green_tiles(img):
            add(('green_tiles', img.n))
            return list(self._get('green_tiles', img.n, []))

        def right3(tiles, img):
            add(('right3', tuple(tiles), img.n))
            return list(self._get('right3', img.n, []))

        def new_bench_slot(before, after):
            add(('new_bench_slot', before.n, after.n))
            return self._get('new_bench_slot', (before.n, after.n), None)

        def sell_at(*a):
            add(('sell_at',) + tuple(a))
            return self._get('sell_at', tuple(a), True)

        def set_facing(x, y):
            add(('set_facing', x, y))

        def drag_name(img):
            add(('drag_name', img.n))
            return self._get('drag_name', img.n, '')

        def is_green(img, pt, r=22):
            add(('is_green', img.n, tuple(pt)))
            return self._get('is_green', (img.n, tuple(pt)), False)

        for name, fn in (('shot', shot), ('slots_left', slots_left), ('touch', touch),
                         ('tap', tap), ('drag_path', drag_path), ('swipe', swipe),
                         ('ocr', ocr), ('save', save), ('log', log),
                         ('yellow_ratio', yellow_ratio), ('green_tiles', green_tiles),
                         ('right3', right3), ('new_bench_slot', new_bench_slot),
                         ('sell_at', sell_at), ('set_facing', set_facing),
                         ('drag_name', drag_name), ('is_green', is_green)):
            mod[name] = fn
        mod['time'] = FakeTime(rec)

    def state(self, board):
        m = self.mod
        return (m['LAST_TIER'][0], m['LAST_NAME'][0], m['LAST_TILE'][0],
                board.occ, board.pending, board.used, board.hi_tiles)


def run_case(orig, new, fn_name, args_spec, board_spec, script, layout):
    out = []
    for mod in (orig, new):
        h = Harness(mod, script, layout)
        board = None if board_spec is None else FakeBoard(*board_spec)
        args = [board if a is SB else a for a in args_spec]
        try:
            ret = ('ok', mod[fn_name](*args))
        except Exception as e:  # noqa: BLE001
            ret = ('exc', type(e).__name__, str(e))
        state = None if board is None else (board.occ, board.pending, board.used, board.hi_tiles)
        out.append((h.rec, ret, state))
    return out[0], out[1]


SB = object()  # 占位：替换成 board


def compare_case(orig, new, fn_name, args_spec, board_spec, script, layout, tag):
    a, b = run_case(orig, new, fn_name, args_spec, board_spec, script, layout)
    if a != b:
        msg = ['%s [%s]' % (fn_name, tag)]
        for i, (x, y) in enumerate(zip(a[0], b[0])):
            if x != y:
                msg.append('  first rec diff @%d: orig=%r new=%r' % (i, x, y))
                break
        else:
            if len(a[0]) != len(b[0]):
                msg.append('  rec len %d vs %d' % (len(a[0]), len(b[0])))
        if a[1] != b[1]:
            msg.append('  ret orig=%r new=%r' % (a[1], b[1]))
        if a[2] != b[2]:
            msg.append('  state orig=%r new=%r' % (a[2], b[2]))
        check(False, '\n'.join(msg))


# ---------------------------------------------------------------------------
# 2a. deploy_from_bench_old 定向场景
# ---------------------------------------------------------------------------
BOX_TIER = (20, 328, 58, 362)
BOX_TABS = (0, 520, 700, 600)
BOX_LV = (0, 262, 330, 380)
BOX_POP = (300, 0, 1700, 820)


def layout_basic():
    return {'safe': [[820, 180], [900, 180], [820, 260], [900, 260]],
            'path': [[500, 300], [560, 300], [620, 300]],
            'rest': [[300, 500], [360, 500]],
            'lift': [760, 650]}


def scenarios_old():
    """deploy_from_bench_old 的定向场景：(args, board_spec, script, tag)"""
    S = []
    L = layout_basic()

    # A: 有空格，一次成功（attempt 0），无交换
    S.append(dict(
        args=((300, 980),), board_spec=((), (), {}, False),
        script={'slots_left': {0: 4, 1: 3, 2: 4},
                'yellow_ratio': {(0, BOX_TIER): 0.0},
                'green_tiles': {0: [(1200, 300), (1300, 300)]},
                'right3': {0: [(1200, 300), (1300, 300)]},
                'ocr': {(1, BOX_POP): [(10, 10, '点击取消')]}},
        tag='A-free'))

    # B: 没找到可拖目标，quiet=False -> 记日志 + save
    S.append(dict(
        args=((300, 980), False), board_spec=((), (), {}, False),
        script={'slots_left': {0: 4},
                'yellow_ratio': {(0, BOX_TIER): 0.0},
                'green_tiles': {0: []}, 'right3': {0: []}},
        tag='B-notiles'))

    # C: 没找到可拖目标，quiet=True -> 不记日志不 save
    S.append(dict(
        args=((300, 980), True), board_spec=((), (), {}, False),
        script={'slots_left': {0: 4}, 'yellow_ratio': {(0, BOX_TIER): 0.0}},
        tag='C-quiet'))

    # D: hi=True，右3列满 -> 从 used+cand 里挑最右低星格交换
    S.append(dict(
        args=((300, 980), False, SB, True),
        board_spec=([(1200, 300)], [(1400, 300)], {}, False),
        script={'slots_left': {0: 4, 1: 3},
                'yellow_ratio': {(0, BOX_TIER): 0.0},
                'green_tiles': {0: [(1200, 300), (1250, 320)]},
                'right3': {0: [(1200, 300), (1250, 320)]},
                'ocr': {(1, BOX_POP): [(10, 10, '取消')]},
                'new_bench_slot': {(0, 1): (520, 950)}},
        tag='D-hi-swap'))

    # E: hi 由 yellow_ratio 触发（LAST_TIER>=5），交换后 new_bench_slot 返回 None -> 用 (bx,by)
    S.append(dict(
        args=((300, 980),), board_spec=([(1200, 300)], [], {}, False),
        script={'slots_left': {0: 4, 1: 4},
                'yellow_ratio': {(0, BOX_TIER): 0.5},
                'green_tiles': {0: [(1200, 300)]},
                'right3': {0: [(1200, 300)]},
                'ocr': {(1, BOX_POP): [(10, 10, '点击取消')]}},
        tag='E-yellow-hi'))

    # F: 第一次 attempt 放置失败（没有取消按钮），第二次成功
    S.append(dict(
        args=((300, 980),), board_spec=None,
        script={'slots_left': {0: 4, 1: 3, 4: 3},
                'yellow_ratio': {(0, BOX_TIER): 0.0, (1, BOX_TIER): 0.0},
                'green_tiles': {0: [(1200, 300)], 1: [(1250, 320)]},
                'right3': {0: [(1200, 300)], 1: [(1250, 320)]},
                'ocr': {(1, BOX_POP): [], (4, BOX_POP): [(1, 2, '点击取消')]}},
        tag='F-retry'))

    # G: 空格够但 bench 名额反而变多（意外交换）且不是 hi/swap -> 标记占用并返回 None
    S.append(dict(
        args=((300, 980),), board_spec=((), (), {}, False),
        script={'slots_left': {0: 3, 1: 4},
                'yellow_ratio': {(0, BOX_TIER): 0.0},
                'green_tiles': {0: [(1200, 300)]},
                'right3': {0: [(1200, 300)]},
                'ocr': {(1, BOX_POP): [(1, 2, '点击取消')]}},
        tag='G-unexpected-swap'))

    # H: 空格已满但 used 里的点已被 hi_tiles 覆盖 -> targets 为空
    S.append(dict(
        args=((300, 980), False, SB, True),
        board_spec=([(1200, 300)], [(1200, 300)], {}, False),
        script={'slots_left': {0: 4},
                'yellow_ratio': {(0, BOX_TIER): 0.0},
                'green_tiles': {0: [(1200, 300)]},
                'right3': {0: [(1200, 300)]}},
        tag='H-hi-none'))

    # I: board 的 used 里已有目标格 -> 不重复 append；且左右剩余相等不触发交换
    S.append(dict(
        args=((300, 980),), board_spec=([(1200, 300)], (), {}, False),
        script={'slots_left': {0: 4, 1: 4},
                'yellow_ratio': {(0, BOX_TIER): 0.0},
                'green_tiles': {0: [(1200, 300), (900, 400)]},
                'right3': {0: [(1200, 300), (900, 400)]},
                'ocr': {(1, BOX_POP): [(1, 2, '点击取消')]}},
        tag='I-used-hit'))
    return S


def scenarios_layout():
    S = []
    L = layout_basic()

    # A: 什么都没拿起 -> 放回，直接返回
    S.append(dict(
        args=((300, 980), SB), board_spec=((), (), {}, False),
        script={'slots_left': {0: 4}}, tag='A-not-picked'))

    # B: 拿起的是装备（tab 只有"技能"）-> 放回并记日志
    S.append(dict(
        args=((300, 980), SB), board_spec=((), (), {}, False),
        script={'slots_left': {0: 4},
                'ocr': {(1, BOX_TABS): [(5, 5, '技能')]},
                'drag_name': {1: '某装备'}},
        tag='B-equipment'))

    # C: depth>=1 且 tier<5 -> 卖掉
    S.append(dict(
        args=((300, 980), SB, '', 0, 1), board_spec=((), (), {}, False),
        script={'slots_left': {0: 4},
                'ocr': {(1, BOX_TABS): [(5, 5, '特质')]},
                'drag_name': {1: '无名小卒'},
                'yellow_ratio': {(1, BOX_TIER): 0.0}},
        tag='C-depth-sell'))

    # D: 正常部署到 safe 位（安全干员优先 safe），无交换
    S.append(dict(
        args=((300, 980), SB, '维什戴尔'), board_spec=((), (), {}, False),
        script={'slots_left': {0: 4, 3: 4},
                'ocr': {(1, BOX_TABS): [(5, 5, '天赋')],
                        (2, BOX_POP): [(1, 2, '点击取消')]},
                'drag_name': {1: '维什戴尔'},
                'yellow_ratio': {(1, BOX_TIER): 0.0},
                'is_green': {(1, (820, 180)): True}},
        tag='D-deploy-safe'))

    # E: 非安全干员但 safe 全被占 -> 换下低星（swap_out[1]<5 -> 卖掉）
    occ = {'safe0': ('某甲', 3, False), 'safe1': ('某乙', 2, False),
           'safe2': ('某丙', 1, False), 'safe3': ('某丁', 4, False),
           'path0': ('某戊', 6, False), 'path1': ('某己', 6, False),
           'path2': ('某庚', 6, False), 'rest0': ('某辛', 6, False),
           'rest1': ('某壬', 6, False)}
    S.append(dict(
        args=((300, 980), SB, '塔露拉'), board_spec=((), (), occ, False),
        script={'slots_left': {0: 4, 3: 4},
                'ocr': {(1, BOX_TABS): [(5, 5, '特质')],
                        (2, BOX_POP): [(1, 2, '点击取消')]},
                'drag_name': {1: '塔露拉'},
                'yellow_ratio': {(1, BOX_TIER): 0.0},
                'new_bench_slot': {(0, 3): (520, 950)},
                'sell_at': {(520, 950): True}},
        tag='E-swap-sell'))

    # F: 换下的是高星（swap_out[1]>=5）且 depth==0 -> 递归部署
    occ2 = dict(occ)
    occ2['safe0'] = ('某甲', 6, False)
    S.append(dict(
        args=((300, 980), SB, '塔露拉'), board_spec=((), (), occ2, False),
        script={'slots_left': {0: 4, 3: 4},
                'ocr': {(1, BOX_TABS): [(5, 5, '特质')],
                        (2, BOX_POP): [(1, 2, '点击取消')],
                        (4, BOX_TABS): [(5, 5, '特质')],
                        (4, BOX_TABS): [(5, 5, '特质')]},
                'drag_name': {1: '塔露拉', 4: '某戊'},
                'yellow_ratio': {(1, BOX_TIER): 0.0},
                'new_bench_slot': {(0, 3): (520, 950)}},
        tag='F-swap-recursion'))

    # G: 没有可用位置
    S.append(dict(
        args=((300, 980), SB, '塔露拉'), board_spec=((), (), occ, False),
        script={'slots_left': {0: 4},
                'ocr': {(1, BOX_TABS): [(5, 5, '特质')]},
                'drag_name': {1: '塔露拉'},
                'yellow_ratio': {(1, BOX_TIER): 0.0}},
        tag='G-no-target'))

    # H: 放置失败（没有取消按钮）
    S.append(dict(
        args=((300, 980), SB, '维什戴尔'), board_spec=((), (), {}, False),
        script={'slots_left': {0: 4},
                'ocr': {(1, BOX_TABS): [(5, 5, '特质')]},
                'drag_name': {1: '维什戴尔'},
                'yellow_ratio': {(1, BOX_TIER): 0.0},
                'is_green': {(1, (820, 180)): True}},
        tag='H-place-fail'))

    # I: 意外交换 -> swap_out=('?',5) -> depth==0 递归
    S.append(dict(
        args=((300, 980), SB, '维什戴尔'), board_spec=((), (), {}, False),
        script={'slots_left': {0: 3, 3: 4},
                'ocr': {(1, BOX_TABS): [(5, 5, '特质')],
                        (2, BOX_POP): [(1, 2, '点击取消')]},
                'drag_name': {1: '维什戴尔'},
                'yellow_ratio': {(1, BOX_TIER): 0.0},
                'is_green': {(1, (820, 180)): True},
                'new_bench_slot': {(0, 3): (520, 950)}},
        tag='I-unexpected-swap'))

    # J: name_hint 生效 + tier_hint 生效 + 优先干员强制 5 星
    S.append(dict(
        args=((300, 980), SB, '初雪', 3, 0), board_spec=((), (), {}, False),
        script={'slots_left': {0: 4, 3: 4},
                'ocr': {(1, BOX_TABS): [(5, 5, '特质')],
                        (2, BOX_POP): [(1, 2, '取消')]},
                'drag_name': {1: ''},
                'yellow_ratio': {(1, BOX_TIER): 0.5},
                'is_green': {(1, (820, 180)): True, (1, (900, 180)): False}},
        tag='J-hints'))
    return S


# ---------------------------------------------------------------------------
# 2b. 随机 fuzz
# ---------------------------------------------------------------------------
def rand_script(rng, n_img=8):
    sc = {'slots_left': {}, 'yellow_ratio': {}, 'ocr': {}, 'green_tiles': {},
          'right3': {}, 'is_green': {}, 'drag_name': {}, 'new_bench_slot': {},
          'sell_at': {}}
    for n in range(n_img):
        sc['slots_left'][n] = rng.choice([None, 0, 1, 2, 3, 4, 5])
        sc['yellow_ratio'][(n, BOX_TIER)] = rng.choice([0.0, 0.05, 0.08, 0.1, 0.9])
        tabs = []
        for _ in range(rng.randint(0, 3)):
            tabs.append((rng.randrange(700), rng.randrange(100), rng.choice(
                SAFE_TABS + ('其他', ' 特质 ', '技能')))  )
        sc['ocr'][(n, BOX_TABS)] = tabs
        lv = []
        if rng.random() < 0.5:
            lv = [(rng.randrange(300), rng.randrange(100), rng.choice(['LV30', '某某LV', 'abc']))]
        sc['ocr'][(n, BOX_LV)] = lv
        pop = []
        r = rng.random()
        if r < 0.6:
            pop = [(rng.randrange(1400), rng.randrange(800), rng.choice(['点击取消', '取消', '其他']))]
        sc['ocr'][(n, BOX_POP)] = pop
        sc['drag_name'][n] = rng.choice(['', '', '维什戴尔', '望', '塔露拉', '某甲', '某乙'])
        sc['green_tiles'][n] = [(rng.randrange(800, 1600), rng.randrange(140, 740))
                                for _ in range(rng.randint(0, 4))]
        sc['right3'][n] = [(rng.randrange(200, 1700), rng.randrange(120, 760))
                           for _ in range(rng.randint(0, 4))]
        nb = [None, (520, 950), (600, 950)]
        for m in range(1, n_img):
            sc['new_bench_slot'][(n, m)] = rng.choice(nb)
        sc['sell_at'][(520, 950)] = rng.choice([True, False])
    return sc


def rand_case(rng, fn_name):
    lay = make_layout(rng)
    # 把 LAYOUT 的点全部放进 is_green 脚本（连同 tiles）
    script = rand_script(rng)
    tiles = []
    for k in ('safe', 'path', 'rest'):
        tiles += ['%s%d' % (k, i) for i in range(len(lay.get(k, [])))]
    for n in range(8):
        for tn in tiles:
            try:
                kind = tn.rstrip('0123456789')
                pt = lay[kind][int(tn[len(kind):])]
            except Exception:  # noqa: BLE001
                continue
            script['is_green'][(n, tuple(pt))] = rng.random() < 0.5
    used = [(rng.randrange(200, 1700), rng.randrange(120, 760)) for _ in range(rng.randint(0, 2))]
    hi_tiles = [(rng.randrange(200, 1700), rng.randrange(120, 760)) for _ in range(rng.randint(0, 2))]
    occ = {}
    for tn in tiles:
        if rng.random() < 0.7:
            occ[tn] = (rng.choice(NAMES), rng.randint(1, 6), rng.random() < 0.5)
    if fn_name == 'deploy_from_bench_old':
        args = ((rng.randrange(200, 1700), rng.randrange(900, 1050)),
                rng.random() < 0.5, SB, rng.random() < 0.5)
        bs = (used, hi_tiles, occ, False)
    else:
        r = rng.random()
        if r < 0.5:
            args = ((rng.randrange(200, 1700), rng.randrange(900, 1050)), SB,
                    rng.choice(NAMES), rng.choice([0, 3, 5]), rng.choice([0, 1]))
        elif r < 0.8:
            args = ((rng.randrange(200, 1700), rng.randrange(900, 1050)), SB, rng.choice(NAMES))
        else:
            args = ((rng.randrange(200, 1700), rng.randrange(900, 1050)), None, rng.choice(NAMES),
                    rng.choice([0, 5]), rng.choice([0, 1]))
        bs = (used, hi_tiles, occ, False)
    return args, bs, script, lay


def test_effects(orig, new, rng):
    for sc in scenarios_old():
        compare_case(orig, new, 'deploy_from_bench_old', sc['args'], sc['board_spec'],
                     sc['script'], layout_basic(), sc['tag'])
    for sc in scenarios_layout():
        compare_case(orig, new, 'deploy_layout', sc['args'], sc['board_spec'],
                     sc['script'], layout_basic(), sc['tag'])
    print('# targeted effect scenarios checked')

    for i in range(300):
        for fn in ('deploy_from_bench_old', 'deploy_layout'):
            args, bs, script, lay = rand_case(rng, fn)
            compare_case(orig, new, fn, args, bs, script, lay, 'fuzz#%d' % i)
    print('# fuzz 300x2 checked')


def main():
    rng = random.Random(20251120)
    orig = load_orig()
    new = load_new()
    test_structure(orig, new)
    test_pure(orig, new, rng)
    # 恢复被纯函数测试改动过的 LAYOUT 由 Harness 负责
    test_effects(orig, new, rng)
    print()
    if fails:
        print('FAILED %d' % len(fails))
        for f in fails[:10]:
            print('---')
            print(f)
        return 1
    print('ALL OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
