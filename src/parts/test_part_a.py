"""part_a.py 差分测试：oracle（原始 3.11.5 冻结字节码）vs 还原源码。

运行： D:\\DSH\\SHP_Auto\\_tools\\py311\\python.exe test_part_a.py
"""
import random
import sys

sys.path.insert(0, r'D:\DSH\SHP_Auto\_ref')

import cv2
import numpy as np

import orig_garrison

PART = r'D:\DSH\SHP_Auto\GarrisonFarmPC\src\parts\part_a.py'

ORIG = orig_garrison.load()
NEW = orig_garrison.load()
exec(open(PART, encoding='utf-8').read(), NEW)

# orig_garrison.load() 在 exec 期间用桩模块顶替 cv2/numpy，模块里的 cv2 全局仍是桩对象；
# 图像类函数需要真实图像处理，因此两个命名空间都换成真实模块。
for ns in (ORIG, NEW):
    ns['cv2'] = cv2
    ns['np'] = np

RESULTS = []


def check(label, cond, detail=''):
    RESULTS.append((label, bool(cond), detail))
    if not cond:
        print('FAIL %s %s' % (label, detail))


def same(label, a, b):
    check(label, a == b, 'oracle=%r new=%r' % (a, b))


def both_raise(label, fa, fb, args):
    ea = eb = None
    try:
        fa(*args)
    except BaseException as exc:  # noqa: BLE001
        ea = type(exc)
    try:
        fb(*args)
    except BaseException as exc:  # noqa: BLE001
        eb = type(exc)
    check(label, ea is eb, 'oracle_exc=%r new_exc=%r' % (ea, eb))


class Exc:
    """把异常也当成可比较的返回值，用于比较"两边是否抛同类异常"。"""

    def __init__(self, exc_type):
        self.exc_type = exc_type

    def __eq__(self, other):
        return isinstance(other, Exc) and other.exc_type is self.exc_type

    def __repr__(self):
        return 'Exc(%s)' % self.exc_type.__name__


def call_both(name, *args):
    def invoke(fn):
        try:
            return fn(*args)
        except BaseException as exc:  # noqa: BLE001
            return Exc(type(exc))
    return invoke(ORIG[name]), invoke(NEW[name])


class Patch:
    """临时替换两个命名空间里的同名全局，退出时恢复。"""

    def __init__(self, **kw):
        self.kw = kw
        self.saved = {}

    def __enter__(self):
        for name, value in self.kw.items():
            self.saved[name] = (ORIG[name], NEW[name])
            ORIG[name] = value[0]
            NEW[name] = value[1]
        return self

    def __exit__(self, *exc):
        for name, (a, b) in self.saved.items():
            ORIG[name], NEW[name] = a, b
        return False


class FuncScript:
    """记录调用并返回固定值的假函数（双实例）。"""

    def __init__(self, value):
        self.value = value
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return self.value


class OcrScript:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def __call__(self, img, box=None):
        self.calls.append((img, box))
        return self.results.pop(0)


class EngineScript:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def __call__(self, img, **kw):
        self.calls.append((img, dict(kw)))
        out = self.outputs.pop(0)
        if isinstance(out, BaseException):
            raise out
        return out


# ---------------------------------------------------------------------------
# 1) find(items, *kw)
# ---------------------------------------------------------------------------
def test_find():
    fixed = [
        [],
        [(1, 2, '确认准备')],
        [(1, 2, '确认准备'), (3, 4, '返回主页')],
        [(1, 2, 'abc'), (3, 4, 'abd')],
        [(10, 20, '点击任意位置继续'), (30, 40, '极速模拟')],
        [(5, 6, '')],
        [(5, 6, '通过'), (7, 8, '模拟')],
        [(0, 0, '返回主页')],
        [(-1, -1, 'STRONGHOLD')],
        [(1, 2, 'ＡＢＣ'), (3, 4, 'abc')],
        [(9, 9, '断线重连'), (9, 9, '断线重连')],
    ]
    kwcases = [(), ('确认准备',), ('返回主页', '极速模拟'), ('STRONGHOLD',),
               ('不存在的关键词',), ('',), ('abc', 'STRONGHOLD')]
    n = 0
    for items in fixed:
        for kw in kwcases:
            a, b = call_both('find', items, *kw)
            same('find fixed %r %r' % (items, kw), a, b)
            n += 1
    # items 可以是任意可迭代对象（每次换一个新的迭代器）
    for maker in (list, tuple, lambda xs: iter(xs)):
        items = [(1, 2, '确认准备'), (3, 4, '返回主页')]
        a = ORIG['find'](maker(items), '返回主页')
        b = NEW['find'](maker(items), '返回主页')
        same('find iterable %r' % maker, a, b)
        n += 1
    # 解包错误 / 文本不是 str：两边应抛同样的异常
    both_raise('find bad unpack', ORIG['find'], NEW['find'], ([(1, 2)], 'x'))
    both_raise('find non-str t', ORIG['find'], NEW['find'], ([(1, 2, None)], 'x'))
    n += 2

    rnd = random.Random(20241120)
    texts = ['确认准备', '返回主页', '极速模拟', '断线重连', '点击任意位置继续',
             'STRONGHOLD', 'abc', 'ABC', '', '通过 3 次', '模拟完成', '放弃模拟',
             'ＡＢＣ', '·', '50％', '无法识别名称[680,370]']
    kws = ['确认准备', '返回主页', '极速模拟', 'STRONGHOLD', 'abc', 'ＡＢＣ', '模拟', '·', '']
    for _ in range(300):
        cnt = rnd.randrange(0, 6)
        items = [(rnd.randrange(-5, 2000), rnd.randrange(-5, 2000), rnd.choice(texts))
                 for _ in range(cnt)]
        kw = tuple(rnd.choice(kws) for _ in range(rnd.randrange(0, 4)))
        a, b = call_both('find', items, *kw)
        same('find random %r %r' % (items, kw), a, b)
        n += 1
    return n


# ---------------------------------------------------------------------------
# 2) num(img, box)：ocr 是模块全局，替换成脚本化假函数
# ---------------------------------------------------------------------------
def make_img(h=40, w=60):
    arr = np.arange(h * w * 3, dtype=np.uint32).reshape(h, w, 3) % 251
    return arr.astype(np.uint8)


def test_num():
    fixed = [
        [],
        [(0, 0, '')],
        [(0, 0, '3')],
        [(0, 0, '12'), (0, 0, '7')],
        [(0, 0, '7'), (0, 0, '12')],
        [(0, 0, 'abc')],
        [(0, 0, '１２３')],
        [(0, 0, '١٢٣')],
        [(0, 0, '2 0 2 4')],
        [(0, 0, '通过3次')],
        [(0, 0, '3'), (0, 0, '45'), (0, 0, '６')],
        [(0, 0, ''), (0, 0, '')],
        [(0, 0, '㊷')],
        [(0, 0, '²')],
    ]
    img = make_img()
    n = 0
    for res in fixed:
        ra, rb = OcrScript([res]), OcrScript([res])
        with Patch(ocr=(ra, rb)):
            a, b = call_both('num', img, (1, 2, 30, 40))
        same('num fixed %r' % (res,), a, b)
        same('num img passed', ra.calls[0][0] is img, rb.calls[0][0] is img)
        same('num box passed', ra.calls[0][1], rb.calls[0][1])
        same('num box exact', ra.calls[0][1], (1, 2, 30, 40))
        n += 1
    # ocr 返回 None -> for 迭代抛 TypeError
    with Patch(ocr=(OcrScript([None]), OcrScript([None]))):
        both_raise('num ocr None', ORIG['num'], NEW['num'], (img, (0, 0, 1, 1)))
        n += 1

    rnd = random.Random(7)
    chars = '0123456789１２３٤٥abc中文· 次模拟％'
    for _ in range(300):
        panels = []
        for _ in range(rnd.randrange(0, 4)):
            panels.append((rnd.random(), rnd.random(),
                           ''.join(rnd.choice(chars) for _ in range(rnd.randrange(0, 12)))))
        ra, rb = OcrScript([panels]), OcrScript([panels])
        with Patch(ocr=(ra, rb)):
            box = (rnd.randrange(0, 100), rnd.randrange(0, 100),
                   rnd.randrange(100, 200), rnd.randrange(100, 200))
            a, b = call_both('num', img, box)
        same('num random %r' % (panels,), a, b)
        n += 1
    return n


# ---------------------------------------------------------------------------
# 3) numrec(img, box)
# ---------------------------------------------------------------------------
def test_numrec():
    img = make_img(120, 200)
    box = (10, 20, 60, 80)
    fixed = [
        None,
        [],
        [['3', 0.9]],
        [['3', 0.39]],
        [['１２', 0.8]],
        [['abc', 0.99]],
        [['', 0.99]],
        [['7', 0.4]],
        [['㊷', 0.9]],
    ]
    n = 0
    for res in fixed:
        ea, eb = EngineScript([(res, None)]), EngineScript([(res, None)])
        na, nb = FuncScript(42), FuncScript(42)
        with Patch(ocr_engine=(ea, eb), num=(na, nb)):
            a, b = call_both('numrec', img, box)
        same('numrec fixed %r' % (res,), a, b)
        same('numrec kwargs', ea.calls[0][1], eb.calls[0][1])
        same('numrec kwargs exact', ea.calls[0][1],
             {'use_det': False, 'use_cls': False, 'use_rec': True})
        same('numrec img equal', np.array_equal(ea.calls[0][0], eb.calls[0][0]), True)
        same('numrec img shape', ea.calls[0][0].shape, (box[3] - box[1], box[2] - box[0], 3))
        # 文字里有数字且置信度 >= 0.4 时不回退；否则回退到 num
        text = res[0][0] if res else ''
        digits = any(ch.isdigit() for ch in text)
        high = bool(res) and res[0][1] >= 0.4
        should_fallback = not (digits and high)
        same('numrec fallback %r' % (res,), len(na.calls) == len(nb.calls), True)
        same('numrec fallback count %r' % (res,), len(na.calls), 1 if should_fallback else 0)
        n += 1

    # 引擎抛 Exception -> 返回 None，且不回退
    for exc in (RuntimeError('x'), ValueError('y')):
        ea, eb = EngineScript([exc]), EngineScript([exc])
        na, nb = FuncScript(42), FuncScript(42)
        with Patch(ocr_engine=(ea, eb), num=(na, nb)):
            a, b = call_both('numrec', img, box)
        same('numrec exception %r' % (exc,), a, b)
        same('numrec exception returns None', a, None)
        same('numrec exception no fallback', (len(na.calls), len(nb.calls)), (0, 0))
        n += 1

    rnd = random.Random(11)
    chars = '0123456789１３٤abc中文· '
    for _ in range(200):
        if rnd.random() < 0.85:
            txt = ''.join(rnd.choice(chars) for _ in range(rnd.randrange(0, 8)))
            conf = rnd.choice([0.0, 0.2, 0.39, 0.4, 0.5, 0.99])
            res = [[txt, conf]]
        else:
            res = rnd.choice([None, []])
        ea, eb = EngineScript([(res, None)]), EngineScript([(res, None)])
        na, nb = FuncScript(777), FuncScript(777)
        x1, y1 = rnd.randrange(0, 300), rnd.randrange(0, 300)
        x2, y2 = x1 + rnd.randrange(0, 400), y1 + rnd.randrange(0, 400)
        with Patch(ocr_engine=(ea, eb), num=(na, nb)):
            a, b = call_both('numrec', img, (x1, y1, x2, y2))
        same('numrec random res=%r' % (res,), a, b)
        same('numrec random img', np.array_equal(ea.calls[0][0], eb.calls[0][0]), True)
        same('numrec random fallback', len(na.calls), len(nb.calls))
        n += 1
    return n


# ---------------------------------------------------------------------------
# 4) yellow_ratio / has_color_badge / has_badge（真实 cv2 + numpy）
# ---------------------------------------------------------------------------
def hsv_solid(hsv, h=1080, w=1920):
    bgr = cv2.cvtColor(np.uint8([[[hsv[0], hsv[1], hsv[2]]]]), cv2.COLOR_HSV2BGR)[0, 0]
    return np.full((h, w, 3), bgr, np.uint8)


def test_badges():
    rnd = random.Random(31337)
    img = np.zeros((1080, 1920, 3), np.uint8)
    n = 0
    # HSV 阈值边界（yellow_ratio 的 H/S/V 上下界逐一边界值）
    for hsv in [(20, 255, 149), (20, 255, 150), (8, 120, 150), (8, 120, 149),
                (7, 255, 255), (35, 255, 255), (36, 255, 255), (20, 119, 255),
                (20, 120, 255), (20, 255, 254), (70, 40, 150), (69, 255, 255),
                (140, 255, 255), (141, 255, 255), (100, 40, 149)]:
        im = hsv_solid(hsv)
        a, b = call_both('yellow_ratio', im, (0, 0, 100, 100))
        same('yellow_ratio hsv boundary %r' % (hsv,), a, b)
        for name in ('has_color_badge', 'has_badge'):
            a, b = call_both(name, im, 680, 370)
            same('%s hsv boundary %r' % (name, hsv), a, b)
        n += 3

    # has_badge 两个框的占比阈值 0.12 / 0.1（逐行填充，行数即占比分子）
    yellow = hsv_solid((20, 255, 255))
    for rows in (5, 6, 7, 8):
        im = np.zeros((1080, 1920, 3), np.uint8)
        im[270:270 + rows, 720:770] = yellow[0, 0]      # 第一个框 50x50
        a, b = call_both('has_badge', im, 680, 370)
        same('has_badge first-box rows=%d' % rows, a, b)
        n += 1
    for rows in (5, 6, 7, 8):
        im = np.zeros((1080, 1920, 3), np.uint8)
        im[240:240 + rows, 710:780] = yellow[0, 0]      # 第二个框 70x100
        a, b = call_both('has_badge', im, 680, 370)
        same('has_badge second-box rows=%d' % rows, a, b)
        n += 1

    for _ in range(200):
        img[:] = 0
        for _ in range(rnd.randrange(0, 6)):
            x = rnd.randrange(0, 1880)
            y = rnd.randrange(0, 1040)
            h = rnd.randrange(1, 120)
            w = rnd.randrange(1, 120)
            color = rnd.choice([(0, 255, 255), (255, 255, 0), (255, 0, 0), (0, 0, 255),
                                (40, 200, 210), (128, 128, 128), (200, 180, 40)])
            img[y:y + h, x:x + w] = color
        gx = rnd.choice([680, 890, 1100, 1310, 0, 1860, 100])
        gy = rnd.choice([370, 580, 790, 1000, 0, 30, 120, 130, 1079])
        for box in ((gx, gy, gx + 95, gy + 45),
                    (gx + 1, max(0, gy - 110), gx + 95, gy - 45)):
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            a, b = call_both('yellow_ratio', img, box)
            same('yellow_ratio random gy=%d' % gy, a, b)
            n += 1
        for name in ('has_color_badge', 'has_badge'):
            a, b = call_both(name, img, gx, gy)
            same('%s random gx=%d gy=%d' % (name, gx, gy), a, b)
            n += 1

    cases = [
        ('yellow_ratio', (np.zeros((1080, 1920, 3), np.uint8), (100, 100, 200, 200))),
        ('yellow_ratio', (np.full((1080, 1920, 3), 255, np.uint8), (0, 0, 1920, 1080))),
        ('yellow_ratio', (np.full((1080, 1920, 3), (0, 255, 255), np.uint8), (0, 0, 50, 50))),
        ('yellow_ratio', (np.full((1080, 1920, 3), (0, 255, 255), np.uint8), (0, 0, 1, 1))),
        ('has_color_badge', (np.full((1080, 1920, 3), (255, 255, 0), np.uint8), 680, 370)),
        ('has_badge', (np.full((1080, 1920, 3), (0, 255, 255), np.uint8), 680, 370)),
        ('has_badge', (np.full((1080, 1920, 3), (0, 255, 255), np.uint8), 0, 0)),
        ('has_badge', (np.full((1080, 1920, 3), (0, 255, 255), np.uint8), 10, 40)),
        ('has_color_badge', (np.full((1080, 1920, 3), (0, 255, 255), np.uint8), 10, 40)),
    ]
    for name, args in cases:
        a, b = call_both(name, *args)
        same('%s const' % name, a, b)
        n += 1
    # gy 很小时 has_badge 的第二个框会落到负索引（Python 回绕）
    for gy in (0, 1, 29, 30, 89, 100, 129, 130, 131):
        for gx in (0, 5, 680, 1900):
            a, b = call_both('has_badge', img, gx, gy)
            same('has_badge edge %d,%d' % (gx, gy), a, b)
            n += 1
    return n


# ---------------------------------------------------------------------------
# 5) grid_shift(before, after)
# ---------------------------------------------------------------------------
def make_grid_img(rnd, h=1080, w=1920):
    img = np.full((h, w, 3), 20, np.uint8)
    y = 0
    while y < h:
        thick = rnd.randrange(1, 5)
        color = (rnd.randrange(0, 255), rnd.randrange(0, 255), rnd.randrange(0, 255))
        img[y:y + thick, 600:1400] = color
        y += rnd.randrange(40, 80)
    return img


def test_grid_shift():
    rnd = random.Random(99)
    n = 0
    base = make_grid_img(rnd)
    a, b = call_both('grid_shift', base, base.copy())
    same('grid_shift identical', a, b)
    same('grid_shift identical value', a, 0)
    n += 1

    for _ in range(120):
        src = make_grid_img(rnd)
        shift = rnd.randrange(-200, 201)
        after = np.full_like(src, 20)
        if shift >= 0:
            after[shift:] = src[:1080 - shift]
        else:
            after[:1080 + shift] = src[-shift:]
        a, b = call_both('grid_shift', src, after)
        same('grid_shift random shift=%d' % shift, a, b)
        n += 1

    for _ in range(30):
        src = np.random.RandomState(rnd.randrange(1 << 30)).randint(0, 256, (1080, 1920, 3), np.uint8)
        dst = np.random.RandomState(rnd.randrange(1 << 30)).randint(0, 256, (1080, 1920, 3), np.uint8)
        a, b = call_both('grid_shift', src, dst)
        same('grid_shift noise', a, b)
        n += 1
    return n


# ---------------------------------------------------------------------------
# 6) ocr(img, box=None)：假 ocr_engine，比较喂给引擎的图与返回值结构
# ---------------------------------------------------------------------------
class FakeEngine:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, img):
        self.calls.append(img.copy())
        return self.result, []


DETS = [
    ([[[100, 50], [140, 50], [140, 90], [100, 90]], '确认准备', 0.97],
     [[[300, 60], [380, 60], [380, 100], [300, 100]], '极速模拟', 0.88]),
    ([[[0, 0], [4, 0], [4, 4], [0, 4]], 'A', 0.5]),
    [],
    None,
]


def test_ocr():
    rnd = random.Random(5)
    img = np.zeros((1080, 1920, 3), np.uint8)
    n = 0
    boxes = [None, (0, 0, 1920, 1080), (600, 350, 1300, 750), (100, 100, 500, 400),
             (1900, 1060, 1920, 1080), (100, 100, 101, 101)]
    for dets in DETS:
        for box in boxes:
            ea, eb = FakeEngine(dets), FakeEngine(dets)
            with Patch(ocr_engine=(ea, eb)):
                a, b = call_both('ocr', img, box)
            same('ocr %r box=%r' % (dets, box), a, b)
            same('ocr fed shape', ea.calls[0].shape, eb.calls[0].shape)
            same('ocr fed equal', np.array_equal(ea.calls[0], eb.calls[0]), True)
            if box is None:
                same('ocr no box shape', ea.calls[0].shape, img.shape)
            else:
                x1, y1, x2, y2 = box
                P = 40
                same('ocr padded shape', ea.calls[0].shape,
                     (y2 - y1 + 2 * P, x2 - x1 + 2 * P, 3))
                same('ocr border replicate top',
                     np.array_equal(ea.calls[0][:P, :], ea.calls[0][P:P + 1, :].repeat(P, 0)), True)
                same('ocr border replicate left',
                     np.array_equal(ea.calls[0][:, :P], ea.calls[0][:, P:P + 1].repeat(P, 1)), True)
            same('ocr engine call count', len(ea.calls), 1)
            n += 1

    # box 为非空但为空切片 -> 两边应抛同类异常
    with Patch(ocr_engine=(FakeEngine(None), FakeEngine(None))):
        both_raise('ocr empty box', ORIG['ocr'], NEW['ocr'], (img, (0, 0, 0, 0)))
        n += 1

    chars = '确认准备极速模拟STRONGHOLDabc通过次0123·'
    for _ in range(120):
        dets = []
        for _ in range(rnd.randrange(0, 4)):
            x0, y0 = rnd.randrange(0, 900), rnd.randrange(0, 500)
            w, h = rnd.randrange(1, 300), rnd.randrange(1, 100)
            dets.append([[[x0, y0], [x0 + w, y0], [x0 + w, y0 + h], [x0, y0 + h]],
                         ''.join(rnd.choice(chars) for _ in range(rnd.randrange(0, 8))),
                         rnd.random()])
        box = None
        if rnd.random() < 0.7:
            x1, y1 = rnd.randrange(0, 1500), rnd.randrange(0, 900)
            box = (x1, y1, rnd.randrange(x1 + 1, 1921), rnd.randrange(y1 + 1, 1081))
        ea, eb = FakeEngine(dets), FakeEngine(dets)
        with Patch(ocr_engine=(ea, eb)):
            a, b = call_both('ocr', img, box)
        same('ocr random', a, b)
        same('ocr random fed', np.array_equal(ea.calls[0], eb.calls[0]), True)
        n += 1

    # 引擎异常应原样抛出（ocr 不捕获）
    def boom(image):
        raise ValueError('boom')

    with Patch(ocr_engine=(boom, boom)):
        both_raise('ocr engine raises', ORIG['ocr'], NEW['ocr'], (img, None))
        n += 1
    return n


# ---------------------------------------------------------------------------
# 7) passed_count：权威实现是 v1.2（字节码旧版被运行期 exec 覆盖），
#    因此用人工期望值验证 v1.2 语义，并单独展示与旧版字节码的差异。
# ---------------------------------------------------------------------------
def test_passed_count():
    cases = [
        ([], 0),
        ([(0, 300, '已通过模拟3次')], 3),
        ([(0, 400, '已通过模拟3次')], 0),
        ([(0, 349.9, '已通过模拟0次')], 0),
        ([(0, 300, '已通过'), (0, 320, '3次')], 3),
        ([(0, 300, '已通过'), (0, 320, ' 12 次 ')], 12),
        ([(0, 300, '通过 １２ 次')], 12),
        ([(0, 300, '通过 ١٢ 次')], 12),
        ([(0, 300, '已通过'), (0, 320, '模拟3次')], None),
        ([(0, 300, '已通过'), (0, 320, 'abc')], None),
        ([(0, 300, '已通过'), (0, 320, '7')], None),
        ([(0, 300, '通过'), (0, 320, '２')], None),
        ([(0, 300, '通过呢')], None),
        ([(0, 300, '通过 3 次'), (0, 320, '9次')], 3),
        ([(0, 320, '通过'), (0, 300, '9次')], 9),
        ([(0, 300, None), (0, 320, '通过5次')], 5),
        ([(0, 300, 12345)], 0),
        ([(0, 300, '已通过模拟12次')], 12),
        ([(0, 300, '通过12次 通过5次')], 12),
        ([(0, 300, '通过模拟'), (0, 320, '3次')], 3),
    ]
    for panel, want in cases:
        got = NEW['passed_count'](panel)
        check('passed_count v1.2 %r' % (panel,), got == want, 'want=%r got=%r' % (want, got))
    old = ORIG['passed_count']
    new = NEW['passed_count']
    panel = [(0, 300, '已通过'), (0, 320, '3次')]
    check('passed_count old != v1.2 (expected)', old(panel) != new(panel),
          'old=%r v1.2=%r' % (old(panel), new(panel)))
    panel2 = [(0, 300, '已通过模拟3次')]
    check('passed_count simple case agrees', old(panel2) == new(panel2) == 3,
          'old=%r v1.2=%r' % (old(panel2), new(panel2)))
    return len(cases)


def main():
    counts = {
        'find': test_find(),
        'num': test_num(),
        'numrec': test_numrec(),
        'badges': test_badges(),
        'grid_shift': test_grid_shift(),
        'ocr': test_ocr(),
        'passed_count': test_passed_count(),
    }
    failed = [r for r in RESULTS if not r[1]]
    print('\n==== SUMMARY ====')
    for k, v in counts.items():
        print('%-14s %d cases' % (k, v))
    print('total checks: %d, failed: %d' % (len(RESULTS), len(failed)))
    if failed:
        for label, _, detail in failed[:20]:
            print('  FAILED:', label, detail)
        sys.exit(1)
    print('ALL PASS')


if __name__ == '__main__':
    main()
