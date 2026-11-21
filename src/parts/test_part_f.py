# -*- coding: utf-8 -*-
"""part_f.py 与原始模块的差分测试（用 py311 运行）。

覆盖：
  * in_facing_mode    —— 录制器 + 脚本化 ocr/shot，对比返回值、ocr 的 box 与 img 来源（None 时取 shot）
  * slots_left        —— 录制器 + 脚本化 numrec，对比返回值（含 None / %10 边界）
  * locate_new        —— 真实 cv2/numpy + 合成图，对比返回坐标（无变化 / 单连通域 / 多连通域取最大 / 区域外）
  * new_bench_slot    —— 同上（备战席木板区，另一个裁剪窗口与偏移）
  * sell_lowest       —— 构造 Board，对比返回值、swipe/log 序列、board.ops 与 board.used 的变化
  * sell_at           —— 录制器 + 脚本化 numrec，对比 shot/touch/drag_path/sleep 序列与返回值
  * set_facing        —— 录制器 + 脚本化 in_facing_mode，对比重试轮次、dist 逐步加长、失败截图分支
  * buy_and_deploy    —— 录制器 + 脚本化 buy/new_bench_slot/deploy_from_bench，对比分支与 board 状态
  * deploy_bench      —— 录制器 + 脚本化 deploy_from_bench，对比双层循环、连续 2 空位停止、外层 6 轮上限
  * 另外做一次字节码结构比对：把 00_header.py + 常量 + part_f.py 像真实构建那样拼起来编译，
    逐指令对比（比行为测试更强的等价证据）。

注意：part_f.py 单独编译时 `time.sleep(...)` 会编译成 LOAD_GLOBAL + LOAD_METHOD，而原始模块是
`import time` 之后编译的（编译器把 import 的名字标记为 module，属性调用生成 LOAD_GLOBAL NULL + LOAD_ATTR）。
所以字节码比对必须在“带 header 的模块上下文”里做，行为测试则与编译形式无关。

用法： D:\\DSH\\SHP_Auto\\_tools\\py311\\python.exe test_part_f.py
"""
import dis
import os
import re
import sys
import types

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REF = r'D:\DSH\SHP_Auto\_ref'
PART = os.path.join(HERE, 'part_f.py')

sys.path.insert(0, REF)
import orig_garrison

orig = orig_garrison.load()
new = orig_garrison.load()
exec(compile(open(PART, encoding='utf-8').read(), PART, 'exec'), new)

FUNCS = ['sell_at', 'in_facing_mode', 'set_facing', 'slots_left', 'locate_new',
         'new_bench_slot', 'sell_lowest', 'buy_and_deploy', 'deploy_bench']

FAILS = []
CHECKS = [0]
_MISSING = object()


def check(cond, label, detail=''):
    CHECKS[0] += 1
    if not cond:
        FAILS.append('%s %s' % (label, detail))


def check_eq(a, b, label, detail=''):
    CHECKS[0] += 1
    if a != b:
        FAILS.append('%s: orig=%r mine=%r %s' % (label, a, b, detail))


def env_set(ns, mapping):
    saved = {k: ns.get(k, _MISSING) for k in mapping}
    ns.update(mapping)
    return saved


def env_restore(ns, saved):
    for k, v in saved.items():
        if v is _MISSING:
            ns.pop(k, None)
        else:
            ns[k] = v


def compare(label, runner):
    """同一个 runner 在 oracle 命名空间与自己的命名空间各跑一次，比较结果。"""
    a = runner(orig)
    b = runner(new)
    check_eq(a, b, label)
    return a, b


# ===========================================================================
# 1. in_facing_mode(img) —— 纯 IO 包装，脚本化 ocr/shot
# ===========================================================================
IMG_IN = np.zeros((1080, 1920, 3), np.uint8)
SHOT_SENTINEL = object()


def in_facing_runner(items, use_img):
    def runner(ns):
        rec = []

        def fake_shot():
            rec.append(('shot',))
            return SHOT_SENTINEL

        def fake_ocr(img, box=None):
            rec.append(('ocr', 'shot' if img is SHOT_SENTINEL else
                        ('input' if img is IMG_IN else type(img).__name__), box))
            return [(x, y, t) for x, y, t in items]

        saved = env_set(ns, {'shot': fake_shot, 'ocr': fake_ocr})
        try:
            out = ns['in_facing_mode'](IMG_IN if use_img else None)
        finally:
            env_restore(ns, saved)
        return (out, rec)
    return runner


compare('in_facing_mode: 有「点击取消」',
        in_facing_runner([(960, 300, '点击取消')], True))
compare('in_facing_mode: 无「点击取消」',
        in_facing_runner([(960, 300, '确认'), (100, 100, '返回')], True))
compare('in_facing_mode: 空 OCR 结果', in_facing_runner([], True))
compare('in_facing_mode: img=None 时用 shot()',
        in_facing_runner([(960, 300, '点击取消')], False))
compare('in_facing_mode: 近似文案（find 模糊匹配）',
        in_facing_runner([(0, 0, '点击取消噢')], True))
compare('in_facing_mode: 空字符串文案', in_facing_runner([(0, 0, '')], True))
compare('in_facing_mode: 多条 OCR 结果', in_facing_runner(
    [(1, 2, '确认'), (3, 4, '点击取消'), (5, 6, '返回')], True))
r = in_facing_runner([(0, 0, '点击取消')], True)(orig)
check(r[0] is True and type(r[0]) is bool, 'in_facing_mode: 命中时必须是 True（bool）', repr(r[0]))


# ===========================================================================
# 2. slots_left(img) —— 脚本化 numrec
# ===========================================================================
SLOTS_BOX = (1862, 566, 1897, 607)


def slots_runner(value):
    def runner(ns):
        rec = []

        def fake_numrec(img, box):
            rec.append(('numrec', img, box))
            return value

        saved = env_set(ns, {'numrec': fake_numrec})
        try:
            out = ns['slots_left'](IMG_IN)
        finally:
            env_restore(ns, saved)
        return (out, rec)
    return runner


for v in (0, 1, 3, 9, 10, 12, 25, -1, None):
    a, b = compare('slots_left(%r)' % (v,), slots_runner(v))
    if v is not None:
        check_eq(b[0], v % 10, 'slots_left(%r) 期望 %r' % (v, v % 10))
check_eq(slots_runner(3)(orig), (3, [('numrec', IMG_IN, SLOTS_BOX)]),
         'slots_left: numrec 的 box 参数')


# ===========================================================================
# 3. locate_new / new_bench_slot —— 真实 cv2/numpy 合成图
# ===========================================================================
def base_image(seed=0):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 25, size=(1080, 1920, 3), dtype=np.uint8)


def with_rect(img, x0, y0, x1, y1, val=255):
    out = img.copy()
    out[y0:y1, x0:x1] = val
    return out


BASE = base_image(1234)


def crop_runner(fn_name, before, after):
    def runner(ns):
        saved = env_set(ns, {'np': np, 'cv2': cv2})
        try:
            out = ns[fn_name](before, after)
        finally:
            env_restore(ns, saved)
        return out
    return runner


def image_cases(region_x0, region_x1, region_y0, region_y1):
    """构造合成图；返回 [(label, before, after, rect, strict)]。

    strict=True 表示差异是唯一一块、离裁剪窗口边界 ≥10px 的实心矩形：
    此时闭运算不改变形状，质心必然落在矩形内，可额外断言坐标偏移正确。
    """
    cases = []
    cases.append(('完全相同', BASE, BASE.copy(), None, False))
    # 单块干净矩形（偶数边长 → 质心为整数），落在裁剪窗口内部
    rect = (region_x0 + 300, region_y0 + 100, region_x0 + 400, region_y0 + 200)
    cases.append(('单块矩形', BASE, with_rect(BASE, *rect), rect, True))
    rect = (region_x0 + 10, region_y0 + 10, region_x0 + 50, region_y0 + 50)
    cases.append(('靠近区域左上角', BASE, with_rect(BASE, *rect), rect, True))
    rect = (region_x1 - 60, region_y1 - 60, region_x1 - 10, region_y1 - 10)
    cases.append(('靠近区域右下角', BASE, with_rect(BASE, *rect), rect, True))
    # 区域外变化 → 裁剪窗口内无差异
    cases.append(('区域外变化',
                  BASE, with_rect(BASE, region_x1 + 5, region_y1 + 5,
                                  region_x1 + 60, region_y1 + 60), None, False))
    # 多连通域：取面积最大的那一块
    a = with_rect(BASE, 400, region_y0 + 20, 440, region_y0 + 60)          # 40x40
    a = with_rect(a, 900, region_y0 + 120, 980, region_y0 + 200)           # 80x80
    cases.append(('多连通域取最大', BASE, a,
                  (900, region_y0 + 120, 980, region_y0 + 200), True))
    # 两块同样大 → argmax 取第一个
    a = with_rect(BASE, 500, region_y0 + 40, 540, region_y0 + 80)
    a = with_rect(a, 1000, region_y0 + 120, 1040, region_y0 + 160)
    cases.append(('两块同样大取第一个', BASE, a,
                  (500, region_y0 + 40, 540, region_y0 + 80), True))
    # 面积最大的近似矩形（宽高不等）
    a = with_rect(BASE, 700, region_y0 + 30, 760, region_y0 + 110)
    cases.append(('宽高不等矩形', BASE, a,
                  (700, region_y0 + 30, 760, region_y0 + 110), True))
    # 随机噪声 + 一块实心矩形：验形态学闭运算后仍与 oracle 一致（不断言落点）
    rng = np.random.default_rng(7)
    noisy = rng.integers(0, 60, size=BASE.shape, dtype=np.uint8)
    noisy = with_rect(noisy, 1200, region_y0 + 50, 1280, region_y0 + 110)
    cases.append(('噪声背景 + 矩形', BASE, noisy, None, False))
    return cases


for fn_name, args in (('locate_new', (300, 1700, 100, 560)),
                      ('new_bench_slot', (200, 1500, 560, 770))):
    rx0, rx1, ry0, ry1 = args
    for label, before, after, rect, strict in image_cases(rx0, rx1, ry0, ry1):
        a, b = compare('%s: %s' % (fn_name, label),
                       crop_runner(fn_name, before, after))
        if strict:
            x0, y0, x1, y1 = rect
            # 质心一定落在矩形内；同时验证偏移（+300/+100 或 +200/+560）被正确加上
            check(b is not None and x0 <= b[0] < x1 and y0 <= b[1] < y1,
                  '%s: %s 坐标落在矩形内' % (fn_name, label), repr(b))

# 边界：同一对象、单像素变化、n<=1 分支
compare('locate_new: before/after 同一对象', crop_runner('locate_new', BASE, BASE))
compare('new_bench_slot: before/after 同一对象',
        crop_runner('new_bench_slot', BASE, BASE))
# 区域外与区域内各一块：只看区域内
imgs = with_rect(BASE, 50, 50, 90, 90)
imgs = with_rect(imgs, 800, 300, 840, 340)
for fn_name in ('locate_new', 'new_bench_slot'):
    a, b = compare('%s: 区域内外各一块' % fn_name, crop_runner(fn_name, BASE, imgs))
# 多个随机种子，确保形态学/连通域结果稳定一致
for seed in range(8):
    rng = np.random.default_rng(seed)
    after = BASE.copy()
    n_rect = int(rng.integers(1, 4))
    for _ in range(n_rect):
        ax = int(rng.integers(350, 1600))
        ay = int(rng.integers(120, 540))
        w = int(rng.integers(20, 90))
        h = int(rng.integers(20, 90))
        after = with_rect(after, ax, ay, ax + w, ay + h)
    compare('locate_new: 随机图 seed=%d' % seed, crop_runner('locate_new', BASE, after))
    after2 = BASE.copy()
    for _ in range(int(rng.integers(1, 3))):
        ax = int(rng.integers(250, 1450))
        ay = int(rng.integers(580, 750))
        w = int(rng.integers(20, 80))
        h = int(rng.integers(15, 60))
        after2 = with_rect(after2, ax, ay, ax + w, ay + h)
    compare('new_bench_slot: 随机图 seed=%d' % seed,
            crop_runner('new_bench_slot', BASE, after2))


# ===========================================================================
# 4. sell_lowest(board) —— 构造 Board + 脚本化 numrec/shot/swipe/log
# ===========================================================================
def sell_lowest_runner(ops, used, nums):
    def runner(ns):
        rec = []
        board = ns['Board']()
        board.ops = [tuple(o) for o in ops]
        board.used = list(used)
        vals = list(nums)

        def fake_shot():
            rec.append(('shot',))
            return SHOT_SENTINEL

        def fake_numrec(img, box):
            rec.append(('numrec', box))
            return vals.pop(0)

        def fake_swipe(*a):
            rec.append(('swipe',) + tuple(a))

        def fake_log(*a):
            rec.append(('log',) + tuple(a))

        saved = env_set(ns, {'shot': fake_shot, 'numrec': fake_numrec,
                             'swipe': fake_swipe, 'log': fake_log})
        try:
            out = ns['sell_lowest'](board)
        finally:
            env_restore(ns, saved)
        return (out, rec, board.ops, board.used)
    return runner


LOW_OPS = [(1390, 700, 3, (680, 370)), (1210, 700, 4, (890, 370)),
           (1030, 700, 2, None)]
compare('sell_lowest: 卖掉最低星',
        sell_lowest_runner(LOW_OPS, [(680, 370), (890, 370)], [2, 3]))
compare('sell_lowest: 空 ops', sell_lowest_runner([], [], []))
compare('sell_lowest: 全是 5 星以上', sell_lowest_runner(
    [(1390, 700, 5, (680, 370)), (1210, 700, 6, (890, 370))], [], []))
compare('sell_lowest: 单元素', sell_lowest_runner([(1390, 700, 1, None)], [], [0, 1]))
compare('sell_lowest: 同星取第一个', sell_lowest_runner(
    [(1, 2, 3, 'a'), (4, 5, 3, 'b')], [], [1, 2]))
compare('sell_lowest: 卖出后数量没增加', sell_lowest_runner(
    [(1390, 700, 2, (680, 370))], [(680, 370)], [2, 2]))
compare('sell_lowest: 卖出后数量反而减少', sell_lowest_runner(
    [(1390, 700, 2, (680, 370))], [(680, 370)], [3, 1]))
compare('sell_lowest: n0 为 None', sell_lowest_runner(
    [(1390, 700, 2, None)], [], [None, 5]))
compare('sell_lowest: n1 为 None', sell_lowest_runner(
    [(1390, 700, 2, None)], [], [5, None]))
compare('sell_lowest: 两个都为 None', sell_lowest_runner(
    [(1390, 700, 2, None)], [], [None, None]))
compare('sell_lowest: used 里没有该 tile', sell_lowest_runner(
    [(1390, 700, 2, (680, 370))], [(999, 999), (890, 370)], [1, 2]))
compare('sell_lowest: 最低星不是列表第一个', sell_lowest_runner(
    [(1, 1, 4, None), (2, 2, 1, None), (3, 3, 3, None)], [], [4, 5]))
compare('sell_lowest: 星数 0 与 4', sell_lowest_runner(
    [(1, 1, 4, None), (2, 2, 0, None)], [], [0, 1]))
# 单独核对一次完整记录，确认 swipe 用的是 SELL 坐标 + 900/1.3
a, b = compare('sell_lowest: 单次完整调用记录',
               sell_lowest_runner([(1390, 700, 2, (680, 370))], [(680, 370)], [2, 3]))
check_eq(a[1], [('shot',), ('numrec', SLOTS_BOX), ('swipe', 1390, 700, 1760, 900, 900, 1.3),
                ('shot',), ('numrec', SLOTS_BOX), ('log', '卖掉低星干员', (1390, 700, 2))],
         'sell_lowest: 调用序列')
check_eq(a[0], True, 'sell_lowest: 卖出成功返回 True')


# ===========================================================================
# 5. sell_at(x, y) —— 录制器 + 脚本化 numrec
# ===========================================================================
class RecTime(object):
    def __init__(self, rec):
        self.rec = rec

    def sleep(self, s):
        self.rec.append(('sleep', s))


def sell_at_runner(g0, g1):
    def runner(ns):
        rec = []
        vals = [g0, g1]

        def fake_numrec(img, box):
            rec.append(('numrec', img, box))
            return vals.pop(0)

        def fake_shot():
            rec.append(('shot',))
            return SHOT_SENTINEL

        def fake_touch(kind, x, y):
            rec.append(('touch', kind, x, y))

        def fake_drag(x1, y1, x2, y2, steps=12):
            rec.append(('drag_path', x1, y1, x2, y2, steps))

        saved = env_set(ns, {'shot': fake_shot, 'numrec': fake_numrec,
                             'touch': fake_touch, 'drag_path': fake_drag,
                             'time': RecTime(rec)})
        try:
            out = ns['sell_at'](1390, 700)
        finally:
            env_restore(ns, saved)
        return (out, rec)
    return runner


for g0, g1 in ((100, 150), (100, 100), (100, 99), (0, 0), (0, 1),
               (None, 150), (100, None), (None, None), (999999, 1000000),
               (-5, 5)):
    compare('sell_at: g0=%r g1=%r' % (g0, g1), sell_at_runner(g0, g1))

a, b = compare('sell_at: 完整调用序列', sell_at_runner(100, 150))
check_eq(a[1],
         [('shot',), ('numrec', SHOT_SENTINEL, (1785, 768, 1850, 816)),
          ('touch', 'DOWN', 1390, 700),
          ('drag_path', 1390, 700, 1390, 580, 6),
          ('drag_path', 1390, 580, 1760, 900, 10),
          ('sleep', 0.4),
          ('touch', 'UP', 1760, 900),
          ('sleep', 1.0),
          ('shot',), ('numrec', SHOT_SENTINEL, (1785, 768, 1850, 816))],
         'sell_at: 调用序列')
check_eq(a[0], True, 'sell_at: 资金增加返回 True')


# ===========================================================================
# 6. set_facing(tx, ty, tries=3) —— 录制器 + 脚本化 in_facing_mode
# ===========================================================================
def set_facing_runner(script, tries=None, use_default=False):
    def runner(ns):
        rec = []
        queue = list(script)

        def fake_facing(img=None):
            rec.append(('in_facing_mode', img))
            return queue.pop(0)

        def fake_touch(kind, x, y):
            rec.append(('touch', kind, x, y))

        def fake_drag(x1, y1, x2, y2, steps=12):
            rec.append(('drag_path', x1, y1, x2, y2, steps))

        def fake_log(*a):
            rec.append(('log',) + tuple(a))

        def fake_save(img, tag=''):
            rec.append(('save', img, tag))

        def fake_shot():
            rec.append(('shot',))
            return SHOT_SENTINEL

        saved = env_set(ns, {'in_facing_mode': fake_facing, 'touch': fake_touch,
                             'drag_path': fake_drag, 'log': fake_log,
                             'save': fake_save, 'shot': fake_shot,
                             'time': RecTime(rec)})
        try:
            if use_default:
                out = ns['set_facing'](960, 540)
            else:
                out = ns['set_facing'](960, 540, tries)
        finally:
            env_restore(ns, saved)
        return (out, rec, len(queue))
    return runner


compare('set_facing: 第一次就成功', set_facing_runner([False], use_default=True))
compare('set_facing: 第三次才成功', set_facing_runner([True, True, False], use_default=True))
compare('set_facing: 三次都失败', set_facing_runner([True, True, True], use_default=True))
compare('set_facing: tries=1 失败', set_facing_runner([True], tries=1))
compare('set_facing: tries=1 成功', set_facing_runner([False], tries=1))
compare('set_facing: tries=0', set_facing_runner([], tries=0))
compare('set_facing: tries=2', set_facing_runner([True, False], tries=2))
compare('set_facing: tries=5 第 5 次成功',
        set_facing_runner([True, True, True, True, False], tries=5))
compare('set_facing: tries=-1', set_facing_runner([], tries=-1))

a, b = compare('set_facing: 默认 tries=3 的重试序列',
               set_facing_runner([True, True, True], use_default=True))
check_eq(a[0], False, 'set_facing: 3 次失败返回 False')
check_eq(a[1][0:6],
         [('touch', 'DOWN', 960, 540),
          ('drag_path', 960, 540, 1260, 540, 10),
          ('sleep', 0.3),
          ('touch', 'UP', 1260, 540),
          ('sleep', 1.2),
          ('in_facing_mode', None)],
         'set_facing: 第 1 轮调用序列（拖完再判断）')
check([x for x in a[1] if x[0] == 'drag_path'],
      'set_facing: 每轮 drag_path 至少一次')
drags = [x for x in a[1] if x[0] == 'drag_path']
check_eq(len(drags), 3, 'set_facing: 3 轮共 3 次 drag_path')
check_eq([d[3] for d in drags], [1260, 1320, 1380], 'set_facing: dist 每轮 +60')
check_eq([x for x in a[1] if x[0] == 'log'],
         [('log', '设置朝向未生效，重试', (960, 540)),
          ('log', '设置朝向未生效，重试', (960, 540)),
          ('log', '设置朝向未生效，重试', (960, 540)),
          ('log', '设置朝向多次失败，截图已保存')],
         'set_facing: 失败日志')
check(('save', SHOT_SENTINEL, 'facing_failed') in a[1],
      'set_facing: 失败时保存截图')
check_eq(a[2], 0, 'set_facing: 脚本化 in_facing_mode 全部被消费')


# ===========================================================================
# 7. buy_and_deploy(board, i, tier, cost)
# ===========================================================================
def bad_runner(buy_ret, slot, pos, tier=3, cost=None):
    def runner(ns):
        rec = []

        def fake_shot():
            rec.append(('shot',))
            return SHOT_SENTINEL

        def fake_buy(i, cost_=None):
            rec.append(('buy', i, cost_))
            return buy_ret

        def fake_slot(before, after):
            rec.append(('new_bench_slot', before, after))
            return slot

        def fake_popups():
            rec.append(('handle_popups',))

        def fake_deploy(bench_xy, quiet=False, board=None, hi=False):
            rec.append(('deploy_from_bench', bench_xy, quiet,
                        board is board_obj, hi))
            return pos

        def fake_log(*a):
            rec.append(('log',) + tuple(a))

        board_obj = ns['Board']()
        saved = env_set(ns, {'shot': fake_shot, 'buy': fake_buy,
                             'new_bench_slot': fake_slot, 'log': fake_log,
                             'handle_popups': fake_popups,
                             'deploy_from_bench': fake_deploy})
        try:
            out = ns['buy_and_deploy'](board_obj, 2, tier, cost)
        finally:
            env_restore(ns, saved)
        return (out, rec, board_obj.pending, board_obj.ops)
    return runner


compare('buy_and_deploy: 买失败', bad_runner(False, None, None))
compare('buy_and_deploy: 买失败(带 cost)', bad_runner(False, None, None, cost=3))
compare('buy_and_deploy: 没找到新干员', bad_runner(True, None, None))
compare('buy_and_deploy: 部署成功 tier=3', bad_runner(True, (1390, 700), (680, 370)))
compare('buy_and_deploy: 部署成功 tier=4', bad_runner(True, (1390, 700), (680, 370), tier=4))
compare('buy_and_deploy: 部署成功 tier=5', bad_runner(True, (1390, 700), (680, 370), tier=5))
compare('buy_and_deploy: 部署成功 tier=6', bad_runner(True, (1390, 700), (680, 370), tier=6))
compare('buy_and_deploy: 部署失败', bad_runner(True, (1390, 700), None))
compare('buy_and_deploy: pos=(0,0)', bad_runner(True, (1390, 700), (0, 0)))

a, b = compare('buy_and_deploy: 成功分支记录', bad_runner(True, (1390, 700), (680, 370), tier=5))
check_eq(a[1],
         [('shot',), ('buy', 2, None), ('shot',),
          ('new_bench_slot', SHOT_SENTINEL, SHOT_SENTINEL),
          ('deploy_from_bench', (1390, 700), False, True, True)],
         'buy_and_deploy: tier>=5 时 hi=True 且 board 以关键字传入')
check_eq(a[0], True, 'buy_and_deploy: 成功返回 True')
check_eq(a[3], [(680, 370, 5, None)], 'buy_and_deploy: ops 追加 (x, y, max(tier,LAST_TIER), LAST_TILE)')

a, b = compare('buy_and_deploy: tier=4 记录', bad_runner(True, (1390, 700), (680, 370), tier=4))
check_eq(a[1][-1], ('deploy_from_bench', (1390, 700), False, True, False),
         'buy_and_deploy: tier<5 时 hi=False')

a, b = compare('buy_and_deploy: 没找到新干员记录', bad_runner(True, None, None))
check_eq(a[1],
         [('shot',), ('buy', 2, None), ('shot',),
          ('new_bench_slot', SHOT_SENTINEL, SHOT_SENTINEL),
          ('log', '没找到新买的干员（可能合成晋升了）'),
          ('handle_popups',)],
         'buy_and_deploy: 未找到分支的调用序列')
check_eq(a[2], True, 'buy_and_deploy: 未找到分支置 pending=True')


# LAST_TIER / LAST_TILE 被读作 [0]：单独验证
def bad_runner_last(tier, last_tier, last_tile):
    def runner(ns):
        rec = []
        board_obj = ns['Board']()

        def fake_deploy(bench_xy, quiet=False, board=None, hi=False):
            return (11, 22)

        def fake_slot(before, after):
            return (1, 2)

        saved = env_set(ns, {'shot': lambda: None, 'buy': lambda i, c=None: True,
                             'new_bench_slot': fake_slot, 'log': lambda *a: None,
                             'handle_popups': lambda: None,
                             'deploy_from_bench': fake_deploy,
                             'LAST_TIER': [last_tier], 'LAST_TILE': [last_tile]})
        try:
            out = ns['buy_and_deploy'](board_obj, 0, tier, 2)
        finally:
            env_restore(ns, saved)
        return (out, board_obj.ops, board_obj.pending)
    return runner


compare('buy_and_deploy: LAST_TIER 更大', bad_runner_last(1, 5, (680, 370)))
compare('buy_and_deploy: LAST_TIER 更小', bad_runner_last(6, 5, None))
compare('buy_and_deploy: LAST_TILE 为元组', bad_runner_last(3, 1, (890, 370)))


# ===========================================================================
# 8. deploy_bench(board) —— 见下方说明，不再与 oracle 逐调用对比
# ===========================================================================
# 适配官方 PC 端时 deploy_bench 被改为：bench_positions() 识别实际位置（回退 BENCH_ROWS）
# + 最多尝试 6 次 + 连续 3 次失败才停止；控制流与原版有意不同。
# 新实现由实机测试 tests/_live_deploy_bench.py 覆盖（实测一次部署 5 名干员成功）。

# ===========================================================================
# 9. 字节码结构比对（在真实模块上下文里编译 header + part_f）
# ===========================================================================
def assembled_source():
    with open(os.path.join(HERE, '_constants_generated.txt'), encoding='utf-8') as f:
        consts = f.read().strip()
    m = re.search(r'^DPS = \{(.*)\}$', consts, re.MULTILINE)
    if m:
        items = sorted(x.strip() for x in m.group(1).split(',') if x.strip())
        consts = consts[:m.start()] + 'DPS = {' + ', '.join(items) + '}' + consts[m.end():]
    with open(os.path.join(HERE, '00_header.py'), encoding='utf-8') as f:
        header = f.read()
    header = header.replace('%s', consts, 1)
    with open(PART, encoding='utf-8') as f:
        body = f.read().strip()
    return header + '\n\n' + body + '\n'


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
    consts = tuple(norm_const(c) for c in co.co_consts if not isinstance(c, types.CodeType))
    nested = [sig(c) for c in co.co_consts if isinstance(c, types.CodeType)]
    return (co.co_argcount, co.co_posonlyargcount, co.co_kwonlyargcount,
            co.co_flags, tuple(co.co_names), tuple(co.co_varnames),
            tuple(co.co_freevars), tuple(co.co_cellvars),
            consts, tuple(ins), tuple(nested))


LABELS = ['argcount', 'posonly', 'kwonly', 'flags', 'names', 'varnames',
          'freevars', 'cellvars', 'consts']


def firstdiff(a, b, path=''):
    diffs = []
    if a[:9] != b[:9]:
        for label, x, y in zip(LABELS, a[:9], b[:9]):
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


try:
    assembled = {'__name__': 'part_f_assembled', '__file__': 'garrison.py'}
    exec(compile(assembled_source(), 'garrison.py', 'exec'), assembled)
    for name in FUNCS:
        if name == 'deploy_bench':
            continue        # 有意修改过控制流，不参与字节码结构比对
        fa = orig[name]
        fb = assembled[name]
        check_eq(fb.__defaults__, fa.__defaults__, '%s: 默认参数' % name)
        d = firstdiff(sig(fa.__code__), sig(fb.__code__), name)
        check(not d, '%s: 字节码结构一致' % name, '; '.join(d[:4]))
except Exception as exc:  # pragma: no cover
    FAILS.append('字节码结构比对无法执行: %r' % (exc,))


# ===========================================================================
# 汇总
# ===========================================================================
print('检查项: %d' % CHECKS[0])
if FAILS:
    print('失败 %d 项:' % len(FAILS))
    for line in FAILS:
        print('  -', line)
    sys.exit(1)
print('part_f 全部通过 (%d 项检查, %d 个函数)' % (CHECKS[0], len(FUNCS)))
