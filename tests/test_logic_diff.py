"""独立差分测试：把还原后的业务逻辑与原程序字节码逐函数对比。

运行：
    D:\\DSH\\SHP_Auto\\_tools\\py311\\python.exe tests\\test_logic_diff.py [section]

section: const|pure|image|trace|all（默认 all）
"""
from __future__ import annotations

import random
import sys
import types
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, r'D:\DSH\SHP_Auto\_ref')
sys.path.insert(0, str(ROOT / 'src'))

import orig_garrison  # noqa: E402

LOGIC = ROOT / 'src' / 'garrison_pc' / 'logic' / 'garrison.py'
LAYOUT = {
    'safe': [[1195, 445], [1210, 548]],
    'path': [[1305, 345], [1192, 345], [1305, 445]],
    'rest': [[1305, 548], [1318, 650], [1440, 650]],
    'lift': [760, 650],
}

FAILS: list[str] = []
CHECKS = 0


def pair():
    orig = orig_garrison.load()
    new = orig_garrison.load()
    exec(compile(LOGIC.read_text(encoding='utf-8'), str(LOGIC), 'exec'), new)
    import cv2 as real_cv2
    import numpy as real_np
    for ns in (orig, new):
        # oracle 载入时用的是 cv2/numpy 桩模块，这里换回真实实现
        ns['cv2'] = real_cv2
        ns['np'] = real_np
        ns['LAYOUT'] = LAYOUT
        ns['LAST_TIER'] = [1]
        ns['LAST_TILE'] = [None]
        ns['LAST_NAME'] = ['']
        ns['GOLD_FAIL'] = [0]
    return orig, new


def check(name: str, a, b, extra=''):
    global CHECKS
    CHECKS += 1
    same = (a == b)
    if isinstance(a, float) and isinstance(b, float):
        same = abs(a - b) <= 1e-9
    if isinstance(a, tuple) and isinstance(b, tuple):
        same = a == b
    if not same:
        FAILS.append(f'{name}: orig={a!r} new={b!r} {extra}')
        return False
    return True


def section(title: str) -> None:
    print(f'\n=== {title} ===')


# ---------------------------------------------------------------------------
def test_const(orig, new):
    section('常量')
    skip = {'__name__', '__doc__', '__file__', '__builtins__', 'RUNTIME', 'HERE',
            'ocr_engine', 'LAYOUT', 'CHECKS'}
    names = [k for k, v in orig.items()
             if not k.startswith('__') and not isinstance(v, (types.FunctionType,
                                                              types.ModuleType, type))
             and k not in skip]
    for k in names:
        a, b = orig.get(k), new.get(k)
        if isinstance(a, set) and isinstance(b, set):
            check(f'const {k}', sorted(a), sorted(b))
        else:
            check(f'const {k}', repr(a), repr(b))


# ---------------------------------------------------------------------------
def images(rng, count: int):
    yield np.zeros((1080, 1920, 3), np.uint8)
    yield np.full((1080, 1920, 3), 255, np.uint8)
    for _ in range(count):
        if int(rng.integers(0, 2)):
            img = np.full((1080, 1920, 3), int(rng.integers(0, 256)), np.uint8)
        else:
            img = rng.integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
        # 随机在若干区域涂绿色 / 黄色，命中颜色判定分支
        for _ in range(int(rng.integers(0, 6))):
            x1, y1 = int(rng.integers(0, 1800)), int(rng.integers(100, 700))
            w, h = int(rng.integers(30, 200)), int(rng.integers(20, 120))
            color = [(80, 220, 120), (60, 200, 255), (0, 0, 0), (255, 255, 255)][int(rng.integers(0, 4))]
            img[y1:y1 + h, x1:x1 + w] = color
        yield img


def test_image(orig, new, rng, nprng):
    section('图像函数')
    imgs = list(images(nprng, 12))
    boxes = [(0, 0, 100, 100), (680, 890, 1100, 1310), (1700, 700, 1920, 900),
             (10, 1030, 200, 1079)]
    # 图像类函数里的 OCR 一律返回空：只测图像分支
    for ns in (orig, new):
        ns['ocr'] = lambda img, box=None: []
    for i, img in enumerate(imgs):
        for box in boxes:
            a = safe_call(orig, 'yellow_ratio', img, box)
            b = safe_call(new, 'yellow_ratio', img, box)
            if a[0] == 'ok' and b[0] == 'ok':
                a, b = ('ok', round(a[1], 9)), ('ok', round(b[1], 9))
            check(f'yellow_ratio img{i} {box}', a, b)
        for gx, gy in ((680, 370), (1100, 790), (1300, 1000), (0, 0)):
            for fn in ('has_badge', 'has_color_badge'):
                check(f'{fn} img{i} {gx},{gy}',
                      safe_call(orig, fn, img, gx, gy), safe_call(new, fn, img, gx, gy))
        for fn, args in (
            ('grid_shift', (imgs[i - 1] if i else img, img)),
            ('detect_rows', (img,)),
            ('green_tiles', (img,)),
            ('slots_left', (img,)),
            ('in_facing_mode', (img,)),
            ('bench_ops', (img,)),
            ('drag_name', (img,)),
        ):
            check(f'{fn} img{i}', safe_call(orig, fn, *args), safe_call(new, fn, *args))
        check(f'right3 img{i}', safe_call(orig, 'right3', orig['green_tiles'](img), img),
              safe_call(new, 'right3', new['green_tiles'](img), img))
        for pt in ((1195, 445), (500, 300), (1919, 1079)):
            check(f'is_green img{i} {pt}',
                  safe_call(orig, 'is_green', img, pt), safe_call(new, 'is_green', img, pt))
    # 位移/占位检测：同一图像 + 平移图
    base = imgs[2]
    for dy in (0, 30, 120, 400):
        shifted = np.roll(base, dy, axis=0)
        for fn in ('locate_new', 'new_bench_slot'):
            check(f'{fn} dy{dy}', safe_call(orig, fn, base, shifted),
                  safe_call(new, fn, base, shifted))


# ---------------------------------------------------------------------------
def safe_call(ns, fn, *args):
    try:
        return ('ok', ns[fn](*args))
    except Exception as exc:
        return ('exc', type(exc).__name__)


def test_pure(orig, new, rng):
    section('纯函数')
    names = [t for _, t in orig['PRIORITY_FULL']] + [t for _, t in orig['PRIORITY_LOW']] + \
            list(orig['DPS']) + list(orig['HEALERS']) + \
            ['', '未知干员', '塔露拉X', 'X塔露拉', '维什戴尔·改', '凯尔希', '能天使', '阿米娅',
             '12F', 'Lancet-2', 'THRM-EX', 'Castle-3', 'Stormeye', 'Sharp', 'ABC', '一']
    for nm in names:
        for tier in (0, 1, 3, 5, 6):
            for fn in ('rank', 'prio_index', 'is_safe_op', 'is_healer', 'is_dps'):
                check(f'{fn} {nm!r}/{tier}', orig[fn](nm, tier) if fn == 'rank' else orig[fn](nm),
                      new[fn](nm, tier) if fn == 'rank' else new[fn](nm))
        for key in ('塔', '维什戴尔', '望', '临光', '能天使', 'x'):
            check(f'match_key {nm!r}/{key!r}', orig['match_key'](nm, key), new['match_key'](nm, key))
        check(f'tile_order {nm!r}', orig['tile_order'](nm), new['tile_order'](nm))
    for tn in ('safe0', 'safe1', 'path0', 'path2', 'rest0', 'rest2', 'lift0'):
        check(f'tile_xy {tn}', safe_call(orig, 'tile_xy', tn), safe_call(new, 'tile_xy', tn))
    for _ in range(300):
        t = (rng.randrange(-50, 2000), rng.randrange(-50, 1200))
        lst = [(rng.randrange(0, 2000), rng.randrange(0, 1200)) for _ in range(rng.randrange(0, 6))]
        d = rng.choice([0, 10, 95, 200])
        check(f'near {t} {d}', orig['near'](t, lst, d), new['near'](t, lst, d))
    panels = [
        [],
        [(100, 100, '通过 3 次')],
        [(100, 100, '通过模拟 6 次')],
        [(100, 100, '通关 5 次')],
        [(100, 100, '通过 0 次'), (100, 900, '通过 9 次')],
    ]
    for i, panel in enumerate(panels):
        check(f'passed_count panel{i}', orig['passed_count'](panel), new['passed_count'](panel))
    # v1.2 有意改变：旧版对"已通过"（无数字）返回 1，新版返回 None 触发重试
    check('passed_count 无数字', None, new['passed_count']([(100, 100, '已通过'), (100, 400, '3')]))
    # v1.2 修复的特殊字符 / 拆分数字（原版会抛 ValueError 或读错）
    check('passed_count ①', 1, new['passed_count']([(100, 100, '通过①次')]))
    check('passed_count 全角', 12, new['passed_count']([(100, 100, '通过'), (100, 200, '１２次')]))
    items = [(10, 20, '开始模拟'), (30, 40, '返回主页'), (50, 60, 'abc')]
    for kw in (('开始模拟',), ('返回',), ('zzz',), ('开始模拟', '返回'), ()):
        check(f'find {kw}', orig['find'](items, *kw), new['find'](items, *kw))
    cards = [
        [dict(i=0, name='维什戴尔', hi=True, cost=5, emcty=False),
         dict(i=1, name='', hi=False, cost=3, empty=True)],
        [],
        [dict(i=2, name='塔露拉', hi=False, cost=4, empty=False)],
        [dict(i=1, name='A', hi=True, cost=6, empty=False),
         dict(i=2, name='B', hi=True, cost=6, empty=False)],
    ]
    for i, c in enumerate(cards):
        check(f'shop_signature {i}', safe_call(orig, 'shop_signature', c),
              safe_call(new, 'shop_signature', c))
    for profile in ('full', 'low'):
        o = orig_garrison.load()
        n = orig_garrison.load()
        exec(compile(LOGIC.read_text(encoding='utf-8'), str(LOGIC), 'exec'), n)
        o['set_profile'](profile)
        n['set_profile'](profile)
        check(f'set_profile {profile} PROFILE', o['PROFILE'], n['PROFILE'])
        check(f'set_profile {profile} PRIORITY', o['PRIORITY'], n['PRIORITY'])
        check(f'set_profile {profile} SAFE', o['SAFE_KEYS'], n['SAFE_KEYS'])


# ---------------------------------------------------------------------------
class FakeTime:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []
        self.stamps = []

    def sleep(self, s):
        self.sleeps.append(round(float(s), 4))
        self.now += float(s)

    def time(self):
        self.now += 0.001
        return self.now

    def strftime(self, fmt):
        return '00:00:00'


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, tuple(sorted(kwargs.items()))))


def instrument(ns, shots, panels, nums):
    rec = Recorder()
    ns['time'] = FakeTime()
    shot_rec = {'i': 0}
    img = np.zeros((1080, 1920, 3), np.uint8)

    def shot():
        shot_rec['i'] += 1
        idx = min(shot_rec['i'] - 1, len(shots) - 1)
        return shots[idx]

    panel_rec = {'i': 0}

    def ocr(img_, box=None):
        panel_rec['i'] += 1
        idx = min(panel_rec['i'] - 1, len(panels) - 1)
        return panels[idx]

    num_rec = {'i': 0}

    def numrec(img_, box):
        num_rec['i'] += 1
        idx = min(num_rec['i'] - 1, len(nums) - 1)
        return nums[idx]

    for name in ('tap', 'swipe', 'touch', 'drag_path', 'log', 'save', 'scroll_grid',
                 'set_facing', 'pick_squad', 'handle_popups', 'deploy_bench',
                 'deploy_from_bench_old', 'buy_and_deploy', 'sell_lowest', 'new_bench_slot',
                 'read_gold', 'gold_now', 'shop_cards', 'read_shop', 'buy', 'is_green',
                 'green_tiles', 'right3', 'slots_left', 'yellow_ratio', 'drag_name'):
        ns[name] = rec
    ns['shot'] = shot
    ns['ocr'] = ocr
    ns['numrec'] = numrec
    ns['num'] = rec
    ns['passed_count'] = lambda panel: 0
    ns['_dummy_img'] = img
    return rec


def trace(orig, new, fn, args):
    rec_o, rec_n = Recorder(), Recorder()
    for ns, rec in ((orig, rec_o), (new, rec_n)):
        instrument(ns, [np.zeros((1080, 1920, 3), np.uint8)], [[]], [None])
    try:
        ro = orig[fn](*args)
    except Exception as exc:
        ro = f'EXC {exc!r}'
    try:
        rn = new[fn](*args)
    except Exception as exc:
        rn = f'EXC {exc!r}'
    check(f'trace {fn}', (ro, orig_calls(orig)), (rn, orig_calls(new)))


def orig_calls(ns):
    out = []
    for name in ('tap', 'swipe', 'touch', 'drag_path', 'log', 'save', 'scroll_grid',
                 'set_facing', 'pick_squad', 'handle_popups', 'deploy_bench'):
        fn = ns.get(name)
        if isinstance(fn, Recorder):
            out.append((name, fn.calls))
    return out


def main(argv):
    sections = sys.argv[1:] or ['all']
    rng = random.Random(20261120)
    nprng = np.random.default_rng(20261120)
    orig, new = pair()
    if 'all' in sections or 'const' in sections:
        test_const(orig, new)
    if 'all' in sections or 'pure' in sections:
        test_pure(orig, new, rng)
    if 'all' in sections or 'image' in sections:
        test_image(orig, new, rng, nprng)
    print(f'\n总检查 {CHECKS}，失败 {len(FAILS)}')
    for f in FAILS[:40]:
        print('  FAIL', f)
    if len(FAILS) > 40:
        print(f'  ... 还有 {len(FAILS) - 40} 条')
    return 1 if FAILS else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
