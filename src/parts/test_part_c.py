# -*- coding: utf-8 -*-
"""part_c.py 与原始模块的差分测试（用 py311 运行）。

覆盖：
  * is_healer / is_dps          —— 纯函数，随机 + 边界输入逐一对比返回值
  * Board.__init__              —— 对比实例属性名、值与类型
  * read_shop                   —— 录制器 + 脚本化 ocr/numrec，对比调用序列、返回值、
                                   以及被改写的全局 UPX / CARDS
  * shop_cards                  —— 录制器 + 脚本化 ocr/numrec/yellow_ratio，对比返回结构
  * pick_squad                  —— 录制器 + 脚本化 ocr，对比 tap/log 序列
  * buy                         —— 录制器 + 脚本化 ocr/numrec，对比 tap 序列与返回值
  * 另外做一次字节码结构比对（指令序列逐条对比），作为行为等价的强证据。

用法： D:\\DSH\\SHP_Auto\\_tools\\py311\\python.exe test_part_c.py
"""
import dis
import random
import sys
import traceback
import types

import cv2
import numpy as np

REF = r'D:\DSH\SHP_Auto\_ref'
PART = r'D:\DSH\SHP_Auto\GarrisonFarmPC\src\parts\part_c.py'

sys.path.insert(0, REF)
import orig_garrison

orig = orig_garrison.load()
new = orig_garrison.load()
exec(compile(open(PART, encoding='utf-8').read(), PART, 'exec'), new)

ORIG = {}
MINE = {}
FUNCS = ['pick_squad', 'read_shop', 'is_healer', 'is_dps', 'shop_cards', 'buy']
for name in FUNCS:
    ORIG[name] = orig[name]
    MINE[name] = new[name]
ORIG['Board'] = orig['Board']
MINE['Board'] = new['Board']

# 让两边引用同一份常量对象，排除 set 迭代顺序带来的噪声
for k in ('DPS', 'HEALERS', 'ROMAN', 'PRIORITY', 'PRIORITY_FULL', 'PRIORITY_LOW',
          'CARD_X', 'CARD_Y', 'GOLD_BOX', 'SAFE_KEYS'):
    new[k] = orig[k]

FAILS = []
CHECKS = [0]


def check(cond, label, detail=''):
    CHECKS[0] += 1
    if not cond:
        FAILS.append('%s %s' % (label, detail))


def check_eq(a, b, label, detail=''):
    CHECKS[0] += 1
    if a != b:
        FAILS.append('%s: orig=%r mine=%r %s' % (label, a, b, detail))


# ---------------------------------------------------------------------------
# 1. 纯函数：is_healer / is_dps
# ---------------------------------------------------------------------------
def names_pool():
    pool = []
    for p in (orig['PRIORITY'], orig['PRIORITY_FULL'], orig['PRIORITY_LOW']):
        for a, b in p:
            pool.append(a)
            pool.append(b)
    pool.extend(sorted(orig['DPS']))
    pool.extend(list(orig['HEALERS']))
    pool.extend(['I', 'II', 'III', 'IV', 'V', 'VI', '1', 'L', 'LL', '0', 'XII'])
    pool.extend(['', ' ', '  ', '\n', '塔', '果', '望', '锏', '夕', '未知干员', '测试名字',
                 '预备干员-术师', '预备干员-近卫', 'Stormeye', 'stormeye', 'STORM EYE',
                 'Touch', 'touch', 'Mon3tr', 'MON3TR', 'mon3tr', 'Sharp', 'sharp',
                 'Sharp·', '·Sharp', '塔露拉酱', '塔露', '露拉', '多萝西', '炎熔',
                 '玛恩纳', '假日威龙陈', '𝔘𝔫𝔦𝔠𝔬𝔡𝔢', 'Ω', 'x' * 200])
    pool.extend([None, 0, 1, 0.0, True, False, [], (), {}, b'abc'])
    return pool


def mutate(rng, s):
    if not isinstance(s, str) or not s:
        return s
    kind = rng.randrange(8)
    if kind == 0:
        return s[1:]
    if kind == 1:
        return s[:-1]
    if kind == 2:
        return s + '·'
    if kind == 3:
        return '·' + s
    if kind == 4:
        i = rng.randrange(len(s))
        return s[:i] + s[i + 1:]
    if kind == 5:
        return s + s
    if kind == 6:
        i = rng.randrange(len(s))
        return s[:i] + 'X' + s[i:]
    return s.upper() if s.upper() != s else s.lower()


def call_both(fname, arg):
    try:
        a = ORIG[fname](arg)
        ea = None
    except Exception as exc:  # noqa: BLE001
        a, ea = None, type(exc).__name__
    try:
        b = MINE[fname](arg)
        eb = None
    except Exception as exc:  # noqa: BLE001
        b, eb = None, type(exc).__name__
    return a, ea, b, eb


def test_pure():
    rng = random.Random(20241120)
    pool = names_pool()
    cases = list(pool)
    for _ in range(400):
        base = pool[rng.randrange(len(pool))]
        cases.append(mutate(rng, base))
    for _ in range(100):
        n = rng.randrange(0, 12)
        cases.append(''.join(chr(rng.randrange(0x4E00, 0x9FFF + 1)) for _ in range(n)))

    n = 0
    for case in cases:
        a, ea, b, eb = call_both('is_healer', case)
        check_eq(ea, eb, 'is_healer 异常类型', repr(case))
        check_eq(a, b, 'is_healer 返回值', repr(case))
        check_eq(bool(a), bool(b), 'is_healer 真值', repr(case))
        a, ea, b, eb = call_both('is_dps', case)
        check_eq(ea, eb, 'is_dps 异常类型', repr(case))
        check_eq(a, b, 'is_dps 返回值', repr(case))
        check_eq(bool(a), bool(b), 'is_dps 真值', repr(case))
        n += 1
    print('[1] is_healer / is_dps  : %d 组输入' % n)


# ---------------------------------------------------------------------------
# 2. Board.__init__
# ---------------------------------------------------------------------------
def test_board():
    a = ORIG['Board']()
    b = MINE['Board']()
    check_eq(list(vars(a)), list(vars(b)), 'Board 属性顺序/名称')
    check_eq(vars(a), vars(b), 'Board 属性值')
    for k in vars(a):
        check_eq(type(vars(a)[k]).__name__, type(vars(b)[k]).__name__, 'Board 属性类型 %s' % k)
    check_eq(sorted(dir(a)), sorted(dir(b)), 'Board dir')
    check_eq(ORIG['Board'].__name__, MINE['Board'].__name__, 'Board.__name__')
    for name in ('ops', 'used', 'hi_tiles', 'owned', 'occ'):
        check(vars(a)[name] is not vars(b)[name], 'Board 容器实例独立 %s' % name)
    print('[2] Board.__init__      : %d 个属性' % len(vars(a)))


# ---------------------------------------------------------------------------
# 3. 副作用函数：录制器 + 脚本化输入
# ---------------------------------------------------------------------------
class Q(dict):
    def __init__(self, ocr=(), numrec=(), yellow=(), img='IMG'):
        dict.__init__(self)
        self['ocr'] = list(ocr)
        self['numrec'] = list(numrec)
        self['yellow'] = list(yellow)
        self['img'] = img


def qclone(q):
    """复制一份脚本化输入队列（两个实现必须各自消费一份）。"""
    return Q(ocr=[list(p) for p in q['ocr']], numrec=list(q['numrec']),
             yellow=list(q['yellow']), img=q['img'])


def make_stubs(calls, q):
    def _shot():
        calls.append(('shot',))
        return q['img']

    def _tap(x, y, wait=0.6):
        calls.append(('tap', x, y, wait))

    def _ocr(img, box=None):
        calls.append(('ocr', img, box))
        return q['ocr'].pop(0)

    def _numrec(img, box):
        calls.append(('numrec', img, box))
        return q['numrec'].pop(0)

    def _yellow(img, box):
        calls.append(('yellow_ratio', img, box))
        return q['yellow'].pop(0)

    def _log(*a):
        calls.append(('log',) + a)

    return {'shot': _shot, 'tap': _tap, 'ocr': _ocr, 'numrec': _numrec,
            'yellow_ratio': _yellow, 'log': _log}


def reset_globals():
    for ns in (orig, new):
        ns['UPX'] = 100
        ns['CARDS'] = list(orig['CARD_X'])
        ns['CARD_Y'] = orig['CARD_Y']


def call_rec(fname, args, q, post=None):
    calls = []
    stubs = make_stubs(calls, q)
    orig.update(stubs)
    try:
        res = ORIG[fname](*args)
        exc = None
    except Exception as e:  # noqa: BLE001
        res, exc = None, type(e).__name__
    state = post() if post else None
    return (res, exc, calls, state)


def call_rec_new(fname, args, q, post=None):
    calls = []
    stubs = make_stubs(calls, q)
    new.update(stubs)
    try:
        res = MINE[fname](*args)
        exc = None
    except Exception as e:  # noqa: BLE001
        res, exc = None, type(e).__name__
    state = post() if post else None
    return (res, exc, calls, state)


def compare_scenario(fname, args, q_o, q_m, post=None, label=''):
    reset_globals()
    a = call_rec(fname, args, q_o, post)
    reset_globals()
    b = call_rec_new(fname, args, q_m, post)
    tag = '%s[%s]' % (fname, label)
    check_eq(a[1], b[1], tag + ' 异常')
    check_eq(a[0], b[0], tag + ' 返回值')
    check_eq(a[2], b[2], tag + ' 调用序列')
    if post:
        check_eq(a[3], b[3], tag + ' 全局状态')


def post_shop():
    return (orig['UPX'], list(orig['CARDS']))


def post_shop_new():
    return (new['UPX'], list(new['CARDS']))


def test_read_shop():
    scenarios = [
        ('升级-普通', Q(ocr=[[(150, 950, '升级')]], numrec=[777, 55, 8])),
        ('满级', Q(ocr=[[(50, 900, '满级')]], numrec=[500, 3])),
        ('都没有', Q(ocr=[[]], numrec=[None, 42, None])),
        ('两条命中取第一条', Q(ocr=[[(10, 900, '升级'), (20, 900, '满级')]], numrec=[1, 2])),
        ('浮点x坐标', Q(ocr=[[(152.9, 950, '升级')]], numrec=[0, 0, 0])),
        ('空panel', Q(ocr=[[]], numrec=[1, 2, 3])),
        ('多行含无关文本', Q(ocr=[[(10, 850, '等级'), (40, 900, '升级 3'), (700, 1000, '满级')]],
                             numrec=[1234, 99, 7])),
    ]
    for label, q in scenarios:
        q_o = Q(ocr=[list(p) for p in q['ocr']], numrec=list(q['numrec']),
                yellow=list(q['yellow']))
        q_m = Q(ocr=[list(p) for p in q['ocr']], numrec=list(q['numrec']),
                yellow=list(q['yellow']))
        a = call_rec('read_shop', ('IMG',), q_o, post_shop)
        reset_globals()
        b = call_rec_new('read_shop', ('IMG',), q_m, post_shop_new)
        tag = 'read_shop[%s]' % label
        check_eq(a[1], b[1], tag + ' 异常')
        check_eq(a[0], b[0], tag + ' 返回值')
        check_eq(a[2], b[2], tag + ' 调用序列')
        check_eq(a[3], b[3], tag + ' UPX/CARDS')
    print('[3] read_shop           : %d 场景' % len(scenarios))


def test_pick_squad():
    # ocr items: (x, y, text)
    s1 = [
        (400, 430, '塔露拉'), (700, 430, '维什戴尔'), (400, 470, '预备干员-术师'),
        (700, 470, 'ABC'), (1000, 470, '12345'),
        (400, 800, '褐果'), (700, 800, '史尔特尔'),
        (400, 830, '禁用'), (900, 850, '望'), (900, 860, ''), (900, 900, 'XYZ'),
        (1100, 480, '确定自选编队'), (1100, 520, '盟约阵容'),
        (1120, 500, '盟约'), (1140, 500, '编队'),
        (400, 380, '边界下'), (400, 520, '边界上'), (400, 521, '出界'),
    ]
    s2 = [
        (300, 400, 'A1'), (300, 450, '塔露拉'), (300, 500, '维什戴尔'),
        (300, 760, '能天使'), (300, 800, '凯尔希'), (300, 840, '望'),
        (300, 880, '逻各斯'),
    ]
    s3 = []
    s4 = [(500, 400, '测试')]
    scenarios = [('混合', s1), ('同名同排去重', s2), ('空', s3), ('单条', s4)]
    for label, items in scenarios:
        q_o = Q(ocr=[list(items)])
        q_m = Q(ocr=[list(items)])
        compare_scenario('pick_squad', (), q_o, q_m, label=label)
    print('[4] pick_squad          : %d 场景' % len(scenarios))


def test_shop_cards():
    # CARDS = [304, 550, 790, 1034, 1274, 1520]
    s1 = [
        (300, 800, ' 12 '),                                  # 304 的造价文本
        (302, 1010, '塔露拉'), (300, 940, '职业'),            # 304 名称 + op
        (548, 1010, '维什戴尔'), (550, 950, 'x'),             # 550 名称, op 需 CJK -> False
        (790, 780, 'INFO'), (790, 940, '职业'), (790, 1010, '褐果'),  # 790 空位但 op True
        (700, 800, 'III'), (1000, 800, '1'),                  # roman for 790 / 1034
        (1170, 800, 'V'),                                     # 1274 -> r=5 -> hi True, 无 yellow
        (1520, 1010, 'Stormeye'), (1450, 800, 'II'),          # 1520 名称非中文
    ]
    s2 = []
    s3 = [(300, 800, ' 7 '), (302, 1005, ' 塔露拉 ')]
    s4 = [(300, 1010, '塔露拉'), (300, 1030, ' 能天使 ')]     # names[-1] 取最后一个
    scenarios = [('混合排', s1, [304, 550, 790, 1034, 1274, 1520], [0.3, 0.05]),
                 ('空items', s2, [304], [0.2]),
                 ('单卡', s3, [304], []),
                 ('多名称取末个', s4, [304], [])]
    for label, items, cards, yellows in scenarios:
        for ns in (orig, new):
            ns['CARDS'] = list(cards)
        q_o = Q(ocr=[list(items)], numrec=[None, 77], yellow=list(yellows))
        q_m = Q(ocr=[list(items)], numrec=[None, 77], yellow=list(yellows))
        compare_scenario('shop_cards', ('IMG',), q_o, q_m, label=label)
    for ns in (orig, new):
        ns['CARDS'] = []
    compare_scenario('shop_cards', ('IMG',), Q(ocr=[[]]), Q(ocr=[[]]), label='空CARDS')
    print('[5] shop_cards          : %d 场景' % (len(scenarios) + 1))


def test_buy():
    cards = [304, 550, 790, 1034, 1274, 1520]
    # (label, i, cost, ocr 序列, numrec 序列)
    scenarios = [
        ('无法购买', 0, 12, [[(100, 1000, '无法购买')]], [100]),
        ('资金不足', 1, 12, [[(100, 1000, 'OK')], [(1500, 200, '资金不足')]], [100]),
        ('成功-g1<g0', 2, 12, [[], [], [(200, 300, '特质')]], [100, 90]),
        ('成功-g1==g0', 3, 12, [[], [], [(200, 300, '特质')]], [100, 100]),
        ('成功-g1>g0', 4, 25, [[], [], [(200, 300, '天赋')]], [100, 130]),
        ('cost为0', 5, 0, [[], [], [(200, 300, '特性')]], [100, 999]),
        ('g0为None', 0, 12, [[], [], [(200, 300, '特质')]], [None, 999]),
        ('g1为None', 1, 12, [[], [], [(200, 300, '特质')]], [100, None]),
        ('非干员', 2, 12, [[], [], [(200, 300, '不是干员')]], [100]),
        ('左侧空', 3, 12, [[], [], []], [100]),
    ]
    for label, i, cost, ocr_seq, numrec_seq in scenarios:
        for ns in (orig, new):
            ns['CARDS'] = list(cards)
        q_o = Q(ocr=[list(x) for x in ocr_seq], numrec=list(numrec_seq))
        q_m = Q(ocr=[list(x) for x in ocr_seq], numrec=list(numrec_seq))
        compare_scenario('buy', (i, cost), q_o, q_m, label=label)
    # 只传 i：验证 cost 默认值（原始 __defaults__ == (None,)）
    for ns in (orig, new):
        ns['CARDS'] = list(cards)
    compare_scenario('buy', (0,), Q(ocr=[[], [], [(200, 300, '特质')]], numrec=[100, 500]),
                     Q(ocr=[[], [], [(200, 300, '特质')]], numrec=[100, 500]),
                     label='只传i(默认cost)')
    print('[6] buy                 : %d 场景' % (len(scenarios) + 1))


# ---------------------------------------------------------------------------
# 3b. 合成图用例：真实 cv2 / numpy / numrec / yellow_ratio
#     （ocr 不可用，仍用脚本化结果；像素相关部分用随机合成图 + 只按像素裁剪切图的假 OCR 引擎，
#       只要传入的矩形有任何差异，裁到的像素和就会不同，从而被发现）
# ---------------------------------------------------------------------------
REAL = {k: orig[k] for k in ('numrec', 'yellow_ratio', 'num', 'find')}


def make_engine(log):
    def engine(crop, use_det=False, use_cls=False, use_rec=True):
        total = int(crop.sum())
        log.append(('engine', crop.shape, total))
        return ([[str(total % 99991 + 1), 0.99]], [])

    return engine


def synth_call(which, fname, args, q, post=None):
    ns = orig if which == 'orig' else new
    calls = []
    engine_log = []

    def _ocr(image, box=None):
        calls.append(('ocr', box))
        return q['ocr'].pop(0)

    def _shot():
        calls.append(('shot',))
        return q['img']

    def _tap(x, y, wait=0.6):
        calls.append(('tap', x, y, wait))

    def _log(*a):
        calls.append(('log',) + a)

    ns.update(REAL)
    ns['cv2'] = cv2
    ns['np'] = np
    ns['ocr'] = _ocr
    ns['shot'] = _shot
    ns['tap'] = _tap
    ns['log'] = _log
    # numrec / yellow_ratio 取自模块（它们的 __globals__ 指向 orig），
    # 所以引擎与 cv2 两边都要挂上同一份，调用才会真正走到这次录制的引擎。
    eng = make_engine(engine_log)
    orig['ocr_engine'] = eng
    new['ocr_engine'] = eng
    orig['cv2'] = cv2
    new['cv2'] = cv2
    fn = (ORIG if which == 'orig' else MINE)[fname]
    try:
        res = fn(*args)
        exc = None
    except Exception as e:  # noqa: BLE001
        res, exc = None, type(e).__name__
    state = post(which) if post else None
    return (res, exc, calls, engine_log, state)


def test_synthetic():
    rng = np.random.default_rng(7)
    img = rng.integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
    # 纯黄 BGR(0,255,255) -> HSV(30,255,255)，落在 yellow_ratio 的 inRange 内。
    # 只给 r==0（没有罗马数字标号）的卡位涂黄：304 / 1274。
    for x in (304, 1274):
        x1, y1, x2, y2 = x - 104, 800, x - 78, 826
        img[y1:y2, x1:x2] = (0, 255, 255)
    # 造价数字框涂上非均匀色块，确保 numrec 的裁切区域有内容
    for x in (304, 550, 790):
        img[780:822, x - 22:x + 22] = rng.integers(0, 256, (42, 44, 3), dtype=np.uint8)

    def post_shopupx(which):
        ns = orig if which == 'orig' else new
        return (ns['UPX'], list(ns['CARDS']))

    # --- read_shop：真实 numrec（假引擎按像素裁切求和）
    for label, bottom in [('升级', [(1000, 900, '升级'), (900, 950, '等级')]),
                          ('满级', [(1000, 900, '满级')])]:
        q = Q(ocr=[list(bottom)], img=img)
        reset_globals()
        a = synth_call('orig', 'read_shop', (img,), qclone(q), post_shopupx)
        reset_globals()
        b = synth_call('mine', 'read_shop', (img,), qclone(q), post_shopupx)
        tag = 'read_shop[合成图-%s]' % label
        check_eq(a[1], b[1], tag + ' 异常')
        check_eq(a[0], b[0], tag + ' 返回值')
        check_eq(a[2], b[2], tag + ' 调用序列')
        check_eq(a[3], b[3], tag + ' numrec 裁切形状/像素和')
        check_eq(a[4], b[4], tag + ' UPX/CARDS')

    # --- shop_cards：真实 numrec + 真实 yellow_ratio
    #     0:304 r=0 -> 纯黄 -> hi=True      1:550 r=0 -> 噪声 -> hi=False
    #     2:790 r=3 -> hi=False(不走取色)   3:1034 r=5 -> hi=True(不走取色)
    #     4:1274 r=0 -> 纯黄 -> hi=True     5:1520 r=I(1) -> hi=False(不走取色)
    for ns in (orig, new):
        ns['CARDS'] = [304, 550, 790, 1034, 1274, 1520]
    items = [
        (300, 800, ' 12 '), (302, 1010, '塔露拉'), (300, 940, '职业'),   # 304
        (548, 1010, '维什戴尔'), (550, 950, 'x'),                        # 550
        (790, 780, 'INFO'), (790, 940, '职业'), (790, 1010, '褐果'),      # 790: empty
        (700, 800, 'III'),                                              # 790  -> r=3
        (960, 800, 'V'),                                                # 1034 -> r=5
        (1520, 1010, 'Stormeye'), (1450, 800, 'I'),                     # 1520 -> r=1
    ]
    q = Q(ocr=[list(items)], img=img)
    a = synth_call('orig', 'shop_cards', (img,), qclone(q))
    b = synth_call('mine', 'shop_cards', (img,), qclone(q))
    check_eq(a[1], b[1], 'shop_cards[合成图] 异常')
    check_eq(a[0], b[0], 'shop_cards[合成图] 返回值')
    check_eq(a[2], b[2], 'shop_cards[合成图] 调用序列')
    check_eq(a[3], b[3], 'shop_cards[合成图] numrec 裁切形状/像素和')
    got = b[0] or []
    check(bool(got[0]['hi']) is True, 'shop_cards 合成图 纯黄块 r=0 -> yellow_ratio>0.1',
          repr(got[:1]))
    check(bool(got[1]['hi']) is False, 'shop_cards 合成图 噪声块 -> yellow_ratio<=0.1',
          repr(got[1:2]))
    check(got[2]['hi'] is False, 'shop_cards 合成图 III -> r=3 -> hi=False', repr(got[2:3]))
    check(got[3]['hi'] is True, 'shop_cards 合成图 V -> r=5 -> hi=True', repr(got[3:4]))
    check(bool(got[4]['hi']) is True, 'shop_cards 合成图 纯黄块 r=0 -> hi=True', repr(got[4:5]))
    check(got[5]['hi'] is False, 'shop_cards 合成图 I -> r=1 -> hi=False', repr(got[5:6]))
    check(got[2]['empty'] is True and got[2]['cost'] is None, 'shop_cards 合成图 INFO -> empty 且不读造价',
          repr(got[2:3]))
    print('[6b] 合成图(真实cv2)     : 3 组（read_shop x2 / shop_cards x1）')


# ---------------------------------------------------------------------------
# 4. 字节码结构比对（指令序列逐条对比）
# ---------------------------------------------------------------------------
SIMPLE = (int, float, str, bytes, bool, type(None))
UNCOND = ('JUMP_FORWARD', 'JUMP_BACKWARD', 'JUMP_ABSOLUTE', 'JUMP_BACKWARD_NO_INTERRUPT')


def norm(code):
    """返回 (规范化指令序列, 原始指令序列, 嵌套 code 对象列表)。

    规范化只做一件语义上完全等价的事：跳转方向前缀（FORWARD/BACKWARD）去掉，
    并把跳转目标穿过紧邻的无条件跳转（跳转线程化）。这样
    ``POP_JUMP_BACKWARD_IF_FALSE -> 循环头`` 与
    ``POP_JUMP_FORWARD_IF_FALSE -> 块尾的 JUMP_BACKWARD -> 循环头``
    会被视为同一个跳转（两者行为完全相同，只是不同 3.11 补丁版本的跳转编码不同）。
    """
    insts = list(dis.get_instructions(code))
    byoff = {i.offset: i for i in insts}

    def resolve(off):
        for _ in range(4):
            hop = byoff.get(off)
            if hop is not None and hop.opname in UNCOND and isinstance(hop.argval, int):
                off = hop.argval
                continue
            break
        return off

    ins = []
    raw = []
    subs = []
    for item in insts:
        a = item.argval
        if isinstance(a, types.CodeType):
            raw.append((item.opname, '<code:%s>' % a.co_name))
            ins.append((item.opname, '<code:%s>' % a.co_name))
            subs.append(a)
        elif isinstance(a, frozenset):
            raw.append((item.opname, tuple(sorted(a))))
            ins.append((item.opname, tuple(sorted(a))))
        elif isinstance(a, int) and ('JUMP' in item.opname):
            raw.append((item.opname, a))
            name = item.opname.replace('FORWARD', '').replace('BACKWARD', '')
            ins.append((name, resolve(a)))
        elif isinstance(a, SIMPLE) or isinstance(a, tuple):
            raw.append((item.opname, a))
            ins.append((item.opname, a))
        else:
            raw.append((item.opname, repr(a)))
            ins.append((item.opname, repr(a)))
    return ins, raw, subs


def codemap(code):
    """把 code 树压平成 {路径: 签名}，路径按 co_consts 中的出现顺序编号。

    常量只比较 LOAD_CONST 指令里真正被引用的值（它们已体现在指令序列中），
    未被引用的 co_consts 槽位（如 docstring）不影响行为。
    """
    out = {}
    used = []
    for item in dis.get_instructions(code):
        if item.opname == 'LOAD_CONST' and not isinstance(item.argval, types.CodeType):
            v = item.argval
            used.append(v if isinstance(v, SIMPLE) or isinstance(v, tuple) else repr(v))
    subs = [c for c in code.co_consts if isinstance(c, types.CodeType)]
    ins, raw, _ = norm(code)
    out[''] = (ins, raw, tuple(used), code.co_varnames, code.co_freevars,
               code.co_cellvars, tuple(sorted(code.co_names)), code.co_name)
    for idx, sub in enumerate(subs):
        for k, v in codemap(sub).items():
            out['%d.%s' % (idx, k.strip('.')) if k else str(idx)] = v
    return out


def test_bytecode():
    pairs = [(n, ORIG[n], MINE[n]) for n in FUNCS]
    pairs.append(('Board.__init__', vars(ORIG['Board'])['__init__'],
                  vars(MINE['Board'])['__init__']))
    pairs.append(('Board', None, None))
    total_codes = 0
    cosmetic = 0
    for label, of, mf in pairs:
        if of is None:
            check_eq(ORIG['Board'].__name__, MINE['Board'].__name__, 'Board.__name__')
            check_eq(ORIG['Board'].__doc__, MINE['Board'].__doc__, 'Board.__doc__')
            check_eq(ORIG['Board'].__qualname__, MINE['Board'].__qualname__, 'Board.__qualname__')
            continue
        check_eq(of.__doc__, mf.__doc__, '%s.__doc__' % label)
        check_eq(of.__defaults__, mf.__defaults__, '%s.__defaults__' % label)
        check_eq(of.__code__.co_argcount, mf.__code__.co_argcount, '%s co_argcount' % label)
        mo = codemap(of.__code__)
        mm = codemap(mf.__code__)
        check_eq(sorted(mo), sorted(mm), '%s 嵌套代码对象结构' % label)
        for key in sorted(set(mo) & set(mm)):
            total_codes += 1
            ins_a, raw_a, consts_a, va, fa, ca, na, cname_a = mo[key]
            ins_b, raw_b, consts_b, vb, fb, cb, nb, cname_b = mm[key]
            check_eq(ins_a, ins_b, '%s/%s 指令序列' % (label, key))
            check_eq(consts_a, consts_b, '%s/%s 被引用常量' % (label, key))
            check_eq(va, vb, '%s/%s co_varnames' % (label, key))
            check_eq(fa, fb, '%s/%s co_freevars' % (label, key))
            check_eq(ca, cb, '%s/%s co_cellvars' % (label, key))
            check_eq(na, nb, '%s/%s co_names' % (label, key))
            check_eq(cname_a, cname_b, '%s/%s co_name' % (label, key))
            if ins_a == ins_b and raw_a != raw_b and len(raw_a) == len(raw_b):
                cosmetic += sum(1 for p, q in zip(raw_a, raw_b) if p != q)
    print('[7] 字节码结构比对      : %d 个代码对象（含嵌套），'
          '%d 处仅为跳转编码差异（已归一化）' % (total_codes, cosmetic))


def main():
    for fn in (test_pure, test_board, test_read_shop, test_pick_squad,
               test_shop_cards, test_buy, test_synthetic, test_bytecode):
        try:
            fn()
        except Exception:  # noqa: BLE001
            FAILS.append('%s 崩溃\n%s' % (fn.__name__, traceback.format_exc()))
    print()
    if FAILS:
        print('FAILED: %d / %d 项检查' % (len(FAILS), CHECKS[0]))
        for f in FAILS[:60]:
            print('  -', f)
        if len(FAILS) > 60:
            print('  ... 共 %d 条' % len(FAILS))
        return 1
    print('ALL OK: %d 项检查全部通过' % CHECKS[0])
    return 0


if __name__ == '__main__':
    sys.exit(main())
