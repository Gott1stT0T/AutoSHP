"""卫戍协议「极速模拟」自动刷策略角标 —— 业务逻辑层。

本文件由原 GarrisonFarm 1.2（PyInstaller 冻结版）的 CPython 3.11 字节码逐函数还原，
并由个人优化版 v1.2 的补丁（passed_count / pick_strategy / save_done 过滤）合并而来。
所有函数名、常量名、常量取值、坐标、文案均与原程序一致，便于对照与回归测试。

坐标系固定为 1920x1080（16:9）虚拟画面：
  - ``shot()`` 返回 (1080, 1920, 3) 的 BGR 图；
  - 点击/滑动坐标都以该虚拟画面为准，由设备层缩放到真实窗口客户区像素。

本模块不包含任何平台相关代码（ADB / Win32 / MAA 发现逻辑都在设备层与运行时层）。
"""
import json
import os
import re
import time
import unicodedata

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# 运行时注入（设备、日志、进度文件）
# ---------------------------------------------------------------------------
RUNTIME = None

# 程序目录（由 bind() 注入；frozen 时是 exe 所在目录，源码运行时是项目根目录）
HERE = ''


def _here() -> str:
    return HERE


def bind(runtime):
    """由启动器在运行前注入运行时对象。"""
    global RUNTIME, HERE
    RUNTIME = runtime
    HERE = str(getattr(runtime, 'app_dir', '') or '')


def shot():
    return RUNTIME.device.shot()


def tap(x, y, wait=0.6):
    RUNTIME.device.tap(x, y, wait)


def swipe(x1, y1, x2, y2, ms=500, wait=0.8):
    RUNTIME.device.swipe(x1, y1, x2, y2, ms, wait)


def touch(kind, x, y):
    RUNTIME.device.touch(kind, x, y)


def log(*args):
    RUNTIME.log(*args)


def save(img, tag=''):
    RUNTIME.save(img, tag)


def load_done():
    return RUNTIME.load_done()


def save_done(s):
    RUNTIME.save_done(s)


def apply_layout(overrides):
    """用 settings.json 的 ``layout`` 覆盖坐标常量（用于适配官方 PC 端的 UI 差异）。

    ``overrides`` 形如 ``{"GOLD_BOX": [1170, 20, 1265, 80], "LEAVE_TIMEOUT": 90}``；
    只覆盖已存在的常量名，类型按原常量的类型转换。返回实际生效的键名列表。
    """
    if not overrides:
        return []
    scope = globals()
    applied = []
    for key, value in dict(overrides).items():
        if key not in scope or callable(scope[key]):
            continue
        cur = scope[key]
        try:
            if isinstance(cur, tuple) and isinstance(value, (list, tuple)):
                scope[key] = tuple(tuple(v) if isinstance(v, (list, tuple)) else v for v in value)
            elif isinstance(cur, list) and isinstance(value, (list, tuple)):
                scope[key] = [tuple(v) if isinstance(v, (list, tuple)) else v for v in value]
            elif isinstance(cur, (int, float)) and isinstance(value, (int, float)):
                scope[key] = type(cur)(value)
            else:
                scope[key] = value
            applied.append(key)
        except (TypeError, ValueError):
            continue
    return applied


# OCR 引擎由运行时注入（与 MAA 的 PaddleOCR 模型同源）
ocr_engine = None

# 调试开关：设置环境变量 GFPC_DEBUG=1 时输出更详细的购买/部署判定信息
DEBUG = bool(os.environ.get('GFPC_DEBUG'))

# ---------------------------------------------------------------------------
# 常量（与原程序逐字一致）
# ---------------------------------------------------------------------------
GRID_X = [680, 890, 1100, 1310]
GRID_Y = [370, 580, 790, 1000]
GRID_TOP = 250
GRID_BOTTOM = 1050
ROW_H = 210
PRIORITY_FULL = [('塔露拉', '塔露拉'), ('维什戴尔', '维什戴尔'), ('星熊', '斩业星熊'), ('安洁莉娜', '予愿安洁莉娜'), ('能天使', '新约能天使'), ('凯尔希', '凯尔希·思衡托'), ('望', '望'), ('初雪', '圣聆初雪'), ('逻各斯', '逻各斯'), ('蕾缪安', '蕾缪安'), ('贝洛内', '贝洛内'), ('冻河', '冻河'), ('明霄陈', '赤刃明霄陈'), ('结城理', '结城理')]
SAFE_KEYS_FULL = ['维什戴尔', '望', '能天使', '初雪', '蕾缪安', '逻各斯', '冻河']
PRIORITY_LOW = [('塔露拉', '塔露拉'), ('史尔特尔', '史尔特尔'), ('耀骑士', '耀骑士临光'), ('逻各斯', '逻各斯'), ('克莱门莎', '克莱门莎'), ('锏', '锏'), ('帕拉斯', '帕拉斯'), ('真言', '真言'), ('蕾缪安', '蕾缪安'), ('烛煌', '烛煌'), ('艾丽妮', '艾丽妮'), ('薇薇安娜', '薇薇安娜'), ('维娜', '维娜·维多利亚'), ('乌尔比安', '乌尔比安'), ('棘刺', '棘刺'), ('凛冬', '怒潮凛冬'), ('初雪', '圣聆初雪'), ('迷迭香', '迷迭香'), ('鸿雪', '鸿雪'), ('贝洛内', '贝洛内'), ('佩佩', '佩佩'), ('隐德来希', '隐德来希'), ('冻河', '冻河'), ('酒神', '酒神')]
SAFE_KEYS_LOW = ['逻各斯', '真言', '蕾缪安', '烛煌', '初雪', '迷迭香', '鸿雪', '冻河', '酒神']
PRIORITY = [('塔露拉', '塔露拉'), ('维什戴尔', '维什戴尔'), ('星熊', '斩业星熊'), ('安洁莉娜', '予愿安洁莉娜'), ('能天使', '新约能天使'), ('凯尔希', '凯尔希·思衡托'), ('望', '望'), ('初雪', '圣聆初雪'), ('逻各斯', '逻各斯'), ('蕾缪安', '蕾缪安'), ('贝洛内', '贝洛内'), ('冻河', '冻河'), ('明霄陈', '赤刃明霄陈'), ('结城理', '结城理')]
SAFE_KEYS = ['维什戴尔', '望', '能天使', '初雪', '蕾缪安', '逻各斯', '冻河']
PROFILE = 'full'
TARGET = 3
CARD_X = [304, 550, 790, 1034, 1274, 1520]
CARD_Y = 920
GOLD_BOX = (1785, 768, 1850, 816)
UPX = 100
CARDS = [304, 550, 790, 1034, 1274, 1520]
SELL = (1760, 900)
REFRESH = (1786, 686)
READY = (1780, 170)
DPS = {'Pith', 'Sharp', 'Stormeye', '丰川祥子', '乌尔比安', '佩佩', '克莱门莎', '凛御银灰', '史尔特尔', '司霆惊蛰', '圣聆初雪', '塑心', '塔露拉', '夕', '帕拉斯', '引星棘刺', '怒潮凛冬', '斩业星熊', '望', '棘刺', '歌蕾蒂娅', '真言', '结城理', '维什戴尔', '维娜', '维娜·维多利亚', '耀骑士临光', '艾丽妮', '荒芜拉普兰德', '蕾缪安', '薇薇安娜', '贝洛内', '赤刃明霄陈', '迷迭香', '逻各斯', '锏', '阿米娅', '预备干员-术师', '预备干员-近卫', '领主·Sharp', '鸿雪'}
HEALERS = ['褐果', '莎草', '哈洛德', '瑰盐', '乌啾', '风絮', '流明', '夜莺', '华法琳', '纯烬艾雅法拉', 'Mon3tr', 'Touch']
ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6}
LAST_TIER = [1]
LAST_TILE = [None]
LAST_NAME = ['']
BENCH_ROWS = [[(1390, 700), (1300, 700), (1210, 700), (1120, 700), (1030, 700), (940, 700)], [(1260, 600), (1150, 600), (1040, 600), (930, 600), (820, 600)]]
GOLD_FAIL = [0]
LEAVE_TIMEOUT = 30
STALL_TIMEOUT = 600

GENERIC = ['点击任意', '继续', '返回', '确认', '确定', '领取', '下一步', '完成']
GARRISON = ['极速模拟', '卫戍', 'STRONGHOLD', '确认准备', '资金将在', '选择策略',
            '确认本局信息', '确定自选编队', '返回主页', '模拟完成', '模拟中断',
            'COUNTDOWN', '断线重连', '放弃模拟']
LAYOUT = None




# ======================================================================
# part_a.py
# ======================================================================

def ocr(img, box=None):
    """返回 [(cx, cy, text)]，坐标为全图坐标"""
    ox = oy = 0
    if box:
        x1, y1, x2, y2 = box
        P = 40
        img = cv2.copyMakeBorder(img[y1:y2, x1:x2], P, P, P, P, cv2.BORDER_REPLICATE)
        ox, oy = x1 - P, y1 - P
    res, _ = ocr_engine(img)
    out = []
    for b, t, c in res or []:
        xs = [p[0] for p in b]
        ys = [p[1] for p in b]
        out.append((ox + sum(xs) / 4, oy + sum(ys) / 4, t))
    return out


def find(items, *kw):
    for x, y, t in items:
        if any(k in t for k in kw):
            return x, y, t
    return None


def numrec(img, box):
    """只用识别模型读固定位置的数字（MAA 的检测模型常漏掉单个数字）"""
    x1, y1, x2, y2 = box
    try:
        res, _ = ocr_engine(img[y1:y2, x1:x2], use_det=False, use_cls=False, use_rec=True)
    except Exception:
        return None
    t, conf = (res[0][0], res[0][1]) if res else ('', 0)
    d = ''.join(str(__import__('unicodedata').digit(ch)) for ch in t if ch.isdigit())
    if d and conf >= 0.4:
        return int(d)
    return num(img, box)


def num(img, box):
    best = ''
    for _, _, t in ocr(img, box):
        d = ''.join(str(__import__('unicodedata').digit(ch)) for ch in t if ch.isdigit())
        if len(d) > len(best):
            best = d
    return int(best) if best else None


def yellow_ratio(img, box):
    x1, y1, x2, y2 = box
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (8, 120, 150), (35, 255, 255))
    return m.mean() / 255


def has_color_badge(img, gx, gy):
    """格子右上角的彩色（镀层）角标：青蓝色系、不是金色（游戏内实测：彩标 0.37，金标 0）"""
    x1, y1, x2, y2 = gx + 40, max(0, gy - 110), gx + 95, gy - 45
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    cyan = cv2.inRange(hsv, (70, 40, 150), (140, 255, 255)).mean() / 255
    return cyan > 0.15 and yellow_ratio(img, (x1, y1, x2, y2)) < 0.05


def has_badge(img, gx, gy):
    """格子右上角的金色角标"""
    return yellow_ratio(img, (gx + 40, gy - 100, gx + 90, gy - 50)) > 0.12 or yellow_ratio(img, (gx + 30, max(0, gy - 130), gx + 100, gy - 30)) > 0.1


def passed_count(panel):
    import re
    import unicodedata
    texts = [str(t) for _, y, t in panel if y < 350]
    for i, text in enumerate(texts):
        if '通过' not in text:
            continue
        def normalize(value):
            return ''.join(str(unicodedata.digit(c)) if c.isdigit() else c for c in value)
        combined = normalize(text)
        if i + 1 < len(texts):
            following = normalize(texts[i + 1]).strip()
            if re.fullmatch(r'\d+\s*次?', following):
                combined += following
        match = re.search(r'通过\s*(?:模拟)?\s*(\d+)\s*次', combined)
        if match:
            return int(match.group(1))
        return None
    return 0


def grid_shift(before, after):
    """滚动后网格移动了多少像素（向上为正），用模板匹配测量"""
    strip = before[560:700, 600:1400]
    area = after[GRID_TOP:GRID_BOTTOM, 600:1400]
    res = cv2.matchTemplate(area, strip, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(res)
    if mx < 0.6:
        return None
    return 560 - (GRID_TOP + loc[1])



# ======================================================================
# part_b.py
# ======================================================================

def detect_rows(img):
    """滚动后网格行位置不规则（有分组标题），按第一列的立绘纹理找出每行中心"""
    band = cv2.cvtColor(img[:, 620:740], cv2.COLOR_BGR2GRAY).astype(np.float32)
    on = band.std(axis=1) > 18
    rows, start = [], None
    for y in range(GRID_TOP - 60, GRID_BOTTOM + 20):
        if on[y] and start is None:
            start = y
        if (not on[y] or y == GRID_BOTTOM + 19) and start is not None:
            if y - start >= 60:
                c = (start + y) // 2
                if GRID_TOP <= c <= GRID_BOTTOM - 20:
                    rows.append(c)
            start = None
    return rows


def scroll_grid():
    """慢速向上拖动策略列表约两行，结束前停顿以消除惯性"""
    x = 1000
    touch('DOWN', x, 900)
    drag_path(x, 900, x, 480, 14)
    time.sleep(0.5)
    touch('UP', x, 480)
    time.sleep(0.8)


def strategy_name(panel):
    cand = [(y, t) for x, y, t in panel
            if 520 < y < 650
            and any('一' <= ch <= '鿿' for ch in t)
            and '生命' not in t and '通过' not in t and '【' not in t]
    return cand[0][1] if cand else ''


def pick_strategy(done):
    tap(1500,580,1.0)
    rows=list(GRID_Y)
    for page in range(8):
        img=shot()
        for gy in rows:
            if not GRID_TOP+60<=gy<=GRID_BOTTOM-40:
                continue
            for gx in GRID_X:
                tap(gx,gy,0.7)
                count=None
                name=''
                for attempt in range(3):
                    panel=ocr(shot(),(1440,150,1920,800))
                    # A real strategy panel must be open before absence of a
                    # completion banner can be interpreted as zero clears.
                    if any('初始生命值' in str(t).replace(' ','') for _,_,t in panel):
                        count=passed_count(panel)
                        name=strategy_name(panel)
                        if count is not None:
                            break
                    if attempt<2:
                        time.sleep(0.6)
                if count is None:
                    log('通关次数读取失败，跳过该格',(gx,gy))
                    continue
                if not name:
                    log('无法识别名称',(gx,gy),'已通过',count,'次')
                label=name or '无法识别名称[%s,%s]'%(gx,gy)
                if count>=TARGET:
                    log('跳过策略:',label,'已通过',count,'次，目标',TARGET,'次')
                    continue
                log('选择策略: %s（已通过 %s 次，目标 %s 次）'%(label,count,TARGET))
                return label
        scroll_grid()
        after=shot()
        shift=grid_shift(img,after)
        if shift is not None and abs(shift)<20:
            break
        rows=detect_rows(after)
        if not rows:
            break
        log('策略列表下滑，继续查找（本页 %s 行）'%len(rows))
    log('没有找到通关次数未达标的策略')
    return None


def set_profile(name):
    global PROFILE, PRIORITY, SAFE_KEYS
    PROFILE = name
    PRIORITY, SAFE_KEYS = (PRIORITY_LOW, SAFE_KEYS_LOW) if name == 'low' else (PRIORITY_FULL, SAFE_KEYS_FULL)


def match_key(name, key):
    if not name:
        return False
    if len(key) == 1:
        return name.strip() == key or len(name.strip()) <= 2 and key in name
    return key in name


def prio_index(name):
    for i, (k, _) in enumerate(PRIORITY):
        if match_key(name, k):
            return i


def is_safe_op(name):
    return any(match_key(name, k) for k in SAFE_KEYS)


def rank(name, tier):
    """干员价值：优先干员 > 其他 V/VI 输出 > 其他 V/VI > 低星"""
    i = prio_index(name)
    if i is not None:
        return 1000 - i
    if tier >= 5:
        return 500 + (50 if is_dps(name) else 0)
    return tier



# ======================================================================
# part_c.py
# ======================================================================

def pick_squad():
    """确定自选编队：每个等阶按权重选 2 名（优先干员 > 输出 > 其他）"""
    img = shot()
    items = ocr(img, (560, 80, 1720, 960))
    names = [(x, y, t) for x, y, t in items
             if any('一' <= ch <= '鿿' for ch in t)
             and '盟约' not in t and '阵容' not in t and '确定' not in t and '编队' not in t]
    banned = [(x, y) for x, y, t in items if '禁用' in t]
    picked = []
    for lo, hi in ((380, 520), (760, 900)):
        row = [(x, y, t) for x, y, t in names
               if lo <= y <= hi and '禁用' not in t
               and not any(abs(x - bx) < 90 and 0 < by - y < 80 for bx, by in banned)]
        row.sort(key=lambda c: -(rank(c[2], 6) + (5 if is_dps(c[2]) else 0)))
        for x, y, t in row[:2]:
            tap(x, y - 170, 0.4)
            picked.append(t)
    log('自选编队选择:', picked or '无（自选编队为空，直接开始）')
    tap(1686, 986, 1.5)


class Board:
    def __init__(self):
        self.ops = []
        self.round_done = -1
        self.used = []
        self.pending = False
        self.hi_tiles = []
        self.prep_done = False
        self.last_ready = 0.0
        self.owned = {}
        self.healers = 0
        self.occ = {}


def read_shop(img):
    global UPX, CARDS
    gold = numrec(img, GOLD_BOX)
    bottom = ocr(img, (0, 820, 760, 1010))
    hit = find(bottom, '满级', '升级')
    UPX = int(hit[0]) if hit else 100
    CARDS = [x for x in CARD_X if x > UPX + 150]
    maxed = bool(find(bottom, '满级'))
    up_cost = None if maxed else numrec(img, (UPX - 22, 780, UPX + 22, 822))
    rnd = numrec(img, (728, 32, 778, 68))
    return gold, up_cost, maxed, rnd


def is_healer(name):
    return bool(name) and any(h in name or len(name) >= 2 and name in h for h in HEALERS)


def is_dps(name):
    import difflib
    if not name:
        return False
    for d in DPS:
        if d in name or name in d or difflib.SequenceMatcher(None, d, name).ratio() >= 0.6:
            return True
    return False


def shop_cards(img):
    """一次 OCR 解析整排商店卡牌 -> [dict(i, x, empty, cost, hi, op)]"""
    items = ocr(img, (180, 770, 1700, 1060))
    out = []
    for i, x in enumerate(CARDS):
        mine = [(cx, cy, t) for cx, cy, t in items if abs(cx - x) < 115]
        empty = any('INFO' in t.upper() for _, _, t in mine)
        cost = None
        for cx, cy, t in mine:
            if cy < 830 and abs(cx - x) < 45 and t.strip().isdigit():
                cost = int(t.strip())
        if cost is None and not empty:
            cost = numrec(img, (x - 22, 780, x + 22, 822))
        op = any(930 < cy < 1000 and any('一' <= ch <= '鿿' for ch in t)
                 for cx, cy, t in mine)
        r = 0
        for cx, cy, t in mine:
            tt = t.strip().upper().replace('1', 'I').replace('L', 'I')
            if cy < 840 and cx < x - 50 and tt in ROMAN:
                r = ROMAN[tt]
        hi = r >= 5 if r else yellow_ratio(img, (x - 104, 800, x - 78, 826)) > 0.1
        names = [t for cx, cy, t in mine
                 if cy >= 1000 and any('一' <= ch <= '鿿' or ch.isalpha() for ch in t)]
        name = names[-1].strip() if names else ''
        out.append(dict(i=i, x=x, empty=empty, cost=cost, hi=hi, op=op and not empty,
                        name=name, dps=is_dps(name)))
    return out


def buy(i, cost=None):
    """点两次购买；确认是干员（左侧面板有'阻挡'）才买"""
    x = CARDS[i]
    g0 = numrec(shot(), GOLD_BOX)
    tap(x, CARD_Y, 0.8)
    img = shot()
    if DEBUG:
        log(f'[debug] buy[{i}] x={x} g0={g0} cost={cost}')
        save(img, f'buy_after_tap_{i}')
    if find(ocr(img, (x - 120, 980, x + 120, 1060)), '无法购买') or find(
            ocr(img, (1400, 120, 1920, 260)), '资金不足'):
        if DEBUG:
            near = [t for _, _, t in ocr(img, (x - 120, 980, x + 120, 1060))]
            top = [t for _, _, t in ocr(img, (1400, 120, 1920, 260))]
            log('[debug] buy: 无法购买/资金不足  near=', near, 'top=', top)
        tap(960, 600, 0.4)
        return False
    left = ocr(img, (0, 250, 700, 620))
    is_op = bool(find(left, '特质', '天赋', '特性'))
    if DEBUG:
        log('[debug] buy: 左面板=', [t for _, _, t in left][:8], 'is_op=', is_op)
    if not is_op:
        tap(x, CARD_Y, 0.4)
        tap(960, 600, 0.4)
        return False
    tap(x, CARD_Y + 106, 1.2)
    g1 = numrec(shot(), GOLD_BOX)
    if DEBUG:
        log(f'[debug] buy: 购买后 g1={g1}')
    if cost != 0 and g0 is not None and g1 is not None and g1 >= g0:
        tap(960, 600, 0.4)
        return False
    return True



# ======================================================================
# part_d.py
# ======================================================================

def green_tiles(img):
    """可部署格（拖拽时高亮为绿色）中心点，最右优先"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (35, 100, 100), (85, 255, 255)).astype(np.float32) / 255
    m[:120] = 0
    m[760:] = 0
    m[:, :180] = 0
    m[:, 1650:] = 0
    f = cv2.blur(m, (61, 61))
    ys, xs = np.where(f > 0.93)
    order = np.argsort(-xs)
    pts = []
    for k in order:
        x, y = int(xs[k]), int(ys[k])
        if all(abs(x - px) > 105 or abs(y - py) > 75 for px, py in pts):
            pts.append((x, y))
        if len(pts) >= 40:
            break
    return pts


def right3(tiles, img):
    """只保留全图最右侧3列：以整个可部署区域的右边界为准（随行高做透视修正）"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (35, 100, 100), (85, 255, 255))
    m[:120] = 0
    m[760:] = 0
    m[:, 1650:] = 0
    ys, xs = np.where(m > 0)
    if len(xs) == 0:
        return []
    edges = []
    for y0 in range(140, 760, 40):
        sel = xs[(ys >= y0) & (ys < y0 + 40)]
        if len(sel) > 200:
            edges.append((y0 + 20, np.percentile(sel, 99.5)))
    if not edges:
        return []
    ey = np.array([e[0] for e in edges])
    ex = np.array([e[1] for e in edges])
    if len(edges) >= 2:
        k, c = np.polyfit(ey, ex, 1)
        c += max(0, (ex - (k * ey + c)).max())
    else:
        k, c = 0.0, ex[0]
    keep = []
    for x, y in tiles:
        edge = k * y + c
        tile_w = 100 + (y - 140) * 0.06
        if x >= edge - 3 * tile_w:
            keep.append((x, y))
    return keep


def drag_path(x1, y1, x2, y2, steps=12):
    """拖拽路径（原实现把 motionevent MOVE 拼成一条 adb 命令；这里改为逐步 move，
    由设备层控制每步间隔，Win32 下等效于按住拖动）"""
    for k in range(1, steps + 1):
        touch('MOVE', x1 + (x2 - x1) * k / steps, y1 + (y2 - y1) * k / steps)


def bench_ops(img):
    """备战席上的干员：在木板区找'干员'差分不可靠，改用固定扫描点"""
    return None


def bench_positions(img):
    """识别备战席上干员的实际位置（用头顶的等阶罗马数字徽章定位）。

    PC 端备战席的位置与安卓版固定点有偏差，因此优先用 OCR 找徽章（I/II/…/VI），
    找不到时回退到 BENCH_ROWS。返回的是**可以按住的干员身体位置**。
    """
    try:
        items = ocr(img, (520, 545, 1560, 650))
    except Exception:
        items = []
    found = []
    for x, y, t in items:
        tt = str(t).strip().upper().replace('1', 'I').replace('L', 'I').replace('|', 'I')
        if tt in ROMAN and len(tt) <= 3:
            pos = (int(x), int(y) + 85)
            if all(abs(pos[0] - px) > 60 for px, _ in found):
                found.append(pos)
    found.sort(key=lambda p: p[0])
    if found:
        return found
    return [p for row in BENCH_ROWS for p in row]


def load_layout():
    global LAYOUT
    for d in (_here(), os.path.dirname(os.path.abspath(__file__))):
        p = os.path.join(d, 'tiles.json')
        if os.path.isfile(p):
            try:
                LAYOUT = json.load(open(p, encoding='utf-8'))
                return
            except Exception:
                continue


def is_green(img, pt, r=22):
    x, y = int(pt[0]), int(pt[1])
    hsv = cv2.cvtColor(img[y - r:y + r, x - r:x + r], cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (35, 100, 100), (85, 255, 255)).mean() / 255 > 0.8


def drag_name(img):
    """拖拽时左侧面板显示的干员名"""
    for _, _, t in ocr(img, (0, 262, 330, 322)):
        if any('一' <= ch <= '鿿' or ch.isalpha() for ch in t) and 'LV' not in t.upper():
            return t.strip()
    return ''


def near(t, lst, d=95):
    return any(abs(t[0] - u[0]) <= d and abs(t[1] - u[1]) <= d for u in lst)


def deploy_from_bench(bench_xy, quiet=False, board=None, hi=False):
    if LAYOUT and board is not None:
        return deploy_layout(bench_xy, board, tier_hint=5 if hi else 0)
    return deploy_from_bench_old(bench_xy, quiet, board, hi)


def deploy_tiles(img):
    """调试用：当前拖拽态下可用的绿色格子。"""
    return right3(green_tiles(img), img)



# ======================================================================
# part_e.py
# ======================================================================

def deploy_from_bench_old(bench_xy, quiet=False, board=None, hi=False):
    """按住备战席干员 -> 找最右3列的空格放下 -> 朝右。
    hi=True 且右3列已满时：直接拖到低星干员的格子上交换，换下来的干员卖掉"""
    bx, by = bench_xy
    before = shot()
    left0 = slots_left(before)
    used = board.used if board else []
    hi_tiles = board.hi_tiles if board else []
    for attempt in range(3):
        touch('DOWN', bx, by)
        drag_path(bx, by, bx, by - 180, 9)
        time.sleep(0.8)
        img = shot()
        LAST_TIER[0] = 5 if yellow_ratio(img, (20, 328, 58, 362)) > 0.08 else 1
        is_hi = hi or LAST_TIER[0] >= 5
        cand = right3(green_tiles(img), img)
        if DEBUG:
            log(f'[debug] deploy_old[{attempt}]: 起点{bench_xy} 绿色格={len(cand)} '
                f'used={len(used)} 等级={LAST_TIER[0]}')
        if not cand:
            # 没有绿色格 = 没抓起来（起点空/动画未结束）或确实没有可部署位；
            # 此时继续拖动只会乱点，直接松手放弃这一格
            touch('UP', bx, by - 180)
            time.sleep(0.5)
            if DEBUG:
                log('[debug] deploy_old: 绿色格为空，放弃该起点')
            return None
        free = [t for t in cand if not near(t, used)]
        swap = False
        if free:
            tx, ty = free[min(attempt, len(free) - 1)]
        else:
            targets = ([t for t in used if not near(t, hi_tiles)] + [t for t in cand if not near(t, hi_tiles)]) if is_hi else []
            targets.sort(key=lambda p: -p[0])
            if not targets:
                touch('UP', bx, by - 180)
                time.sleep(0.8)
                if not quiet:
                    log('最右3列没有可用格')
                    save(img, 'no_tiles')
                return None
            tx, ty = targets[0]
            swap = True
        drag_path(bx, by - 180, tx, ty, 10)
        touch('UP', tx, ty)
        time.sleep(1.0)
        im = shot()
        if find(ocr(im, (300, 0, 1700, 820)), '点击取消', '取消'):
            LAST_TILE[0] = (tx, ty)
            set_facing(tx, ty)
            after = shot()
            if not near((tx, ty), used):
                used.append((tx, ty))
            left1 = slots_left(after)
            swapped = left0 is not None and left1 is not None and left1 >= left0
            if swapped and not swap and not is_hi:
                log('该格已有干员（发生交换），标记为占用', (tx, ty))
                return None
            if swapped:
                out = new_bench_slot(before, after) or (bx, by)
                swipe(out[0], out[1], *SELL, 900, 1.3)
                log('V/VI 替换低星干员', (tx, ty), '，已卖出换下的干员')
            if is_hi:
                hi_tiles.append((tx, ty))
            log('部署到', (tx, ty), 'V/VI' if is_hi else '')
            LAST_TILE[0] = (tx, ty)
            return (tx, ty)
        log('放置失败，重试', (tx, ty))
    return None


def tile_order(name):
    """按干员类型给出格子优先顺序（格子名）"""
    safe = [f'safe{i}' for i in range(len(LAYOUT['safe']))]
    path = [f'path{i}' for i in range(len(LAYOUT['path']))]
    rest = [f'rest{i}' for i in range(len(LAYOUT.get('rest', [])))]
    return safe + path + rest if is_safe_op(name) else path + rest + safe


def tile_xy(tn):
    kind = tn.rstrip('0123456789')
    return tuple(LAYOUT[kind][int(tn[len(kind):])])


def deploy_layout(bench_xy, board=None, name_hint='', tier_hint=0, depth=0):
    """固定布局部署：安全位给维什戴尔/望/能天使/初雪，其余优先放敌人路径；
    位置不够时按权重把价值更低的干员换下来（低星卖掉，高星重新安排）"""
    bx, by = bench_xy
    lx, ly = LAYOUT.get('lift', [760, 650])
    before = shot()
    left0 = slots_left(before)
    touch('DOWN', bx, by)
    drag_path(bx, by, bx, by - 120, 6)
    drag_path(bx, by - 120, lx, ly, 8)
    time.sleep(0.8)
    img = shot()
    all_pts = LAYOUT['safe'] + LAYOUT['path'] + LAYOUT.get('rest', [])
    tabs = [t for _, y, t in ocr(img, (0, 520, 700, 600)) if t.strip() in ('特质', '技能', '特性', '天赋')]
    picked = len(tabs) >= 1 or bool(drag_name(img)) or bool(find(ocr(img, (0, 262, 330, 380)), 'LV')) or any(is_green(img, p) for p in all_pts)
    if DEBUG:
        log(f'[debug] deploy_layout: 起点{bench_xy} tabs={tabs} '
            f'drag_name={drag_name(img)!r} 绿色位={sum(bool(is_green(img, p)) for p in all_pts)} '
            f'picked={picked}')
    if not picked:
        touch('UP', lx, ly)
        time.sleep(0.8)
        return None
    if not any(t.strip() in ('特质', '天赋') for t in tabs):
        touch('UP', lx, ly)
        time.sleep(0.8)
        log('拿起的是装备，放回:', drag_name(img) or '?')
        return None
    name = drag_name(img) or name_hint
    tier = 5 if yellow_ratio(img, (20, 328, 58, 362)) > 0.08 else 1
    if prio_index(name) is not None:
        tier = max(tier, 5)
    if depth >= 1 and tier < 5:
        drag_path(lx, ly, *SELL, 10)
        touch('UP', *SELL)
        time.sleep(1.0)
        log('换下的是低星干员，卖掉:', name or '?')
        return None
    tier = max(tier, tier_hint if depth == 0 else 0)
    my = rank(name, tier)
    order = tile_order(name)
    ranged = False

    def occupant(tn):
        if tn in board.occ:
            return board.occ[tn][:2]
        return None if is_green(img, tile_xy(tn)) else ('?', 5)

    def value(tn, occ):
        r = rank(occ[0], occ[1])
        if tn.startswith('safe') and is_safe_op(name) and not is_safe_op(occ[0]):
            r -= 2000
        return r

    safe = [t for t in order if t.startswith('safe')]
    other = [t for t in order if not t.startswith('safe')]
    groups = [safe, other] if is_safe_op(name) else [other, safe]
    target, swap_out = None, None
    for grp in groups:
        occs = {tn: occupant(tn) for tn in grp}
        free = [tn for tn in grp if occs[tn] is None]
        if free:
            target = free[0]
            break
        cands = sorted((value(tn, occs[tn]), grp.index(tn), tn) for tn in grp
                       if occs[tn][1] < 5 and occs[tn][0] != '?' and value(tn, occs[tn]) < my)
        if cands:
            target = cands[0][2]
            swap_out = occs[target]
            break
    if target is None:
        touch('UP', lx, ly)
        time.sleep(0.8)
        log('没有可用位置，留在备战席:', name or '?')
        return None
    tx, ty = tile_xy(target)
    drag_path(lx, ly, tx, ty, 10)
    touch('UP', tx, ty)
    time.sleep(1.0)
    if not find(ocr(shot(), (300, 0, 1700, 820)), '点击取消', '取消'):
        log('放置失败', name, target)
        return None
    LAST_TILE[0] = (tx, ty)
    set_facing(tx, ty)
    after = shot()
    board.occ[target] = (name, tier, ranged)
    left1 = slots_left(after)
    if not swap_out and left0 is not None and left1 is not None and left1 >= left0:
        log('意外交换：', target, '上原本有干员，重新安排被换下的干员')
        swap_out = ('?', 5)
    log('部署', name or '?', f'T{tier}', '->', target, f'（换下 {swap_out[0]}）' if swap_out else '')
    if swap_out:
        board.pending = True
        out = new_bench_slot(before, after)
        if out:
            if swap_out[1] < 5:
                ok = sell_at(*out)
                log('卖掉换下的干员', swap_out[0], '成功' if ok else '（未确认）')
            elif depth == 0:
                deploy_layout(out, board, swap_out[0], swap_out[1], depth + 1)
    LAST_TIER[0], LAST_NAME[0], LAST_TILE[0] = tier, name, (tx, ty)
    return (tx, ty)



# ======================================================================
# part_f.py
# ======================================================================

def sell_at(x, y):
    """把 (x, y) 处的备战席干员拖到右下角出售区（慢速拖拽），返回是否卖出（资金增加）"""
    g0 = numrec(shot(), GOLD_BOX)
    touch('DOWN', x, y)
    drag_path(x, y, x, y - 120, 6)
    drag_path(x, y - 120, SELL[0], SELL[1], 10)
    time.sleep(0.4)
    touch('UP', SELL[0], SELL[1])
    time.sleep(1.0)
    g1 = numrec(shot(), GOLD_BOX)
    return g0 is not None and g1 is not None and g1 > g0


def in_facing_mode(img=None):
    """是否停在「选择朝向」界面（出现「点击取消」）"""
    return bool(find(ocr(img if img is not None else shot(), (300, 0, 1700, 820)), '点击取消'))


def set_facing(tx, ty, tries=3):
    """慢速拖拽设置朝向（朝右），确认「点击取消」消失；失败则加长距离重试"""
    for k in range(tries):
        dist = 300 + 60 * k
        touch('DOWN', tx, ty)
        drag_path(tx, ty, tx + dist, ty, 10)
        time.sleep(0.3)
        touch('UP', tx + dist, ty)
        time.sleep(1.2)
        if not in_facing_mode():
            return True
        log('设置朝向未生效，重试', (tx, ty))
    save(shot(), 'facing_failed')
    log('设置朝向多次失败，截图已保存')
    return False


def slots_left(img):
    """剩余可放置角色数"""
    n = numrec(img, (1862, 566, 1897, 607))
    return n % 10 if n is not None else None


def locate_new(before, after):
    d = cv2.absdiff(before[100:560, 300:1700], after[100:560, 300:1700])
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, m = cv2.threshold(g, 40, 255, cv2.THRESH_BINARY)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(m)
    if n <= 1:
        return None
    k = 1 + int(np.argmax(st[1:, 4]))
    return (int(cen[k][0]) + 300, int(cen[k][1]) + 100)


def new_bench_slot(before, after):
    """找出刚出现在备战席（木板区）的干员位置"""
    d = cv2.absdiff(before[560:770, 200:1500], after[560:770, 200:1500])
    g = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, m = cv2.threshold(g, 40, 255, cv2.THRESH_BINARY)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(m)
    if n <= 1:
        return None
    k = 1 + int(np.argmax(st[1:, 4]))
    return (int(cen[k][0]) + 200, int(cen[k][1]) + 560)


def sell_lowest(board):
    low = [o for o in board.ops if o[2] < 5]
    if not low:
        return False
    o = min(low, key=lambda o: o[2])
    n0 = slots_left(shot())
    swipe(o[0], o[1], *SELL, 900, 1.3)
    n1 = slots_left(shot())
    if n0 is not None and n1 is not None and n1 <= n0:
        log('卖出可能失败（可放置数未增加）', o[:3])
    board.ops.remove(o)
    if o[3] in board.used:
        board.used.remove(o[3])
    log('卖掉低星干员', o[:3])
    return True


def buy_and_deploy(board, i, tier, cost=None):
    before = shot()
    if DEBUG:
        log(f'[debug] buy_and_deploy: 卡{i} tier={tier} cost={cost}')
    ok = buy(i, cost)
    if DEBUG:
        log(f'[debug] buy_and_deploy: buy() -> {ok}')
    if not ok:
        return False
    after = shot()
    slot = new_bench_slot(before, after)
    if DEBUG:
        log(f'[debug] buy_and_deploy: 新干员位置 {slot}')
    if not slot:
        log('没找到新买的干员（可能合成晋升了）')
        handle_popups()
        board.pending = True
        return True
    pos = deploy_from_bench(slot, board=board, hi=tier >= 5)
    if DEBUG:
        log(f'[debug] buy_and_deploy: deploy_from_bench({slot}) -> {pos}')
    if not pos:
        # 刚买到的干员还在入场动画里时，第一次拖拽可能抓空；等半秒按识别到的位置重试
        time.sleep(0.5)
        for cand in bench_positions(shot()):
            if DEBUG:
                log(f'[debug] buy_and_deploy: 重试起点 {cand}')
            pos = deploy_from_bench(cand, board=board, hi=tier >= 5)
            if pos:
                break
            if DEBUG:
                log(f'[debug] buy_and_deploy: {cand} 仍失败')
    if pos:
        board.ops.append((pos[0], pos[1], max(tier, LAST_TIER[0]), LAST_TILE[0]))
    else:
        board.pending = True
    return True


def deploy_bench(board):
    """把备战席上剩下的干员部署（朝右、尽量靠右）。优先用识别到的实际位置，
    识别不到时回退固定扫描点；每轮最多尝试 6 次，连续失败就停"""
    positions = bench_positions(shot())
    tried = 0
    failed = 0
    for xy in positions:
        if tried >= 6:
            return
        tried += 1
        pos = deploy_from_bench(xy, quiet=True, board=board)
        if pos:
            board.ops.append((pos[0], pos[1], LAST_TIER[0], LAST_TILE[0]))
            failed = 0
            continue
        failed += 1
        if failed >= 3:
            return



# ======================================================================
# part_g.py
# ======================================================================

def handle_popups():
    img = shot()
    items = ocr(img)
    if find(items, '确认准备', '资金将在'):
        tap(860, 602, 0.5)
        tap(1410, 728, 1.5)
        return True
    return False


def read_gold(img=None, tries=3):
    """读取资金。失败时换新截图重试，并用更宽的识别框兜底；仍失败返回 None（表示"未知"，不是 0）"""
    for k in range(tries):
        im = img if k == 0 and img is not None else shot()
        g = numrec(im, GOLD_BOX)
        if g is None:
            g = num(im, (1760, 760, 1880, 825))
        if g is not None and 0 <= g <= 99:
            return g
        time.sleep(0.4)
    return None


def gold_now():
    g = read_gold()
    if g is None:
        GOLD_FAIL[0] += 1
        if GOLD_FAIL[0] <= 3:
            save(shot(), 'gold_unreadable')
        log('警告：资金数字读取失败，按「未知」处理继续尝试（截图已保存到 farm_logs）')
    return g


def shop_signature(cards):
    return tuple((c['name'], c['cost']) for c in cards)


def prep_phase(board, img):
    gold, up_cost, maxed, rnd = read_shop(img)
    if rnd is None:
        if board.prep_done:
            return None
        rnd = max(1, board.round_done + 1)
    if rnd == board.round_done:
        return None
    t0 = time.time()
    log(f'回合{rnd} 资金{gold} 升级费用{up_cost} 满级{maxed}')
    save(img, f'shop_r{rnd}')
    if board.round_done < 0 and rnd == 1:
        bought = 0
        for c in shop_cards(img):
            g = gold_now()
            if bought >= 2:
                break
            if c['op'] and c['cost'] is not None and (g is None or c['cost'] <= g):
                if is_healer(c['name']) and board.healers >= 1:
                    log('跳过第二个医疗干员:', c['name'])
                    continue
                if buy_and_deploy(board, c['i'], 5 if c['hi'] else 1, c['cost']):
                    bought += 1
                    board.healers += is_healer(c['name'])
    if not maxed:
        for _ in range(4):
            img = shot()
            gold, up_cost, maxed, _ = read_shop(img)
            if maxed or (gold is not None and up_cost is not None and gold < up_cost):
                break
            ux0 = UPX
            tap(UPX, 920, 0.6); tap(UPX, 920, 1.0)
            g2, c2, maxed, _ = read_shop(shot())
            ok = maxed or UPX != ux0 or (gold is not None and g2 is not None and g2 < gold) or (up_cost is not None and c2 is not None and c2 != up_cost)
            if not ok:
                break
            log('商店升级，资金', gold, '->', g2, '，升级费用', up_cost, '->', '满级' if maxed else c2)
        if DEBUG:
            log(f'[debug] 升级循环结束 maxed={maxed} gold={gold} up_cost={up_cost}')
        if not maxed:
            all_cards = shop_cards(shot())
            if DEBUG:
                log('[debug] 购买阶段：卡片=', [(c['i'], c['name'], c['cost'], bool(c['op']))
                                              for c in all_cards])
            for c in all_cards:
                im = shot()
                g = read_gold(im)
                sl = slots_left(im)
                if DEBUG:
                    log(f'[debug] 卡[{c["i"]}] {c["name"]} cost={c["cost"]} op={c["op"]} '
                        f'gold={g} slots={sl}')
                if g == 0 or sl == 0:
                    log('停止购买：', '资金为 0' if g == 0 else '部署位已满')
                    break
                if g is None:
                    log('警告：资金读取失败，仍尝试购买（买不起时游戏会提示）')
                if c['op'] and c['cost'] is not None and (g is None or c['cost'] <= g):
                    if is_healer(c['name']) and board.healers >= 1:
                        log('跳过第二个医疗干员:', c['name'])
                        continue
                    if buy_and_deploy(board, c['i'], 5 if c['hi'] else 1, c['cost']):
                        board.healers += is_healer(c['name'])
    if maxed:
        refreshes, same_count, last_sig = 0, 0, None
        for _ in range(40):
            img = shot()
            gold = read_gold(img)
            got = False
            allc = shop_cards(img)
            sig = shop_signature(allc)
            if last_sig is not None:
                if sig == last_sig:
                    same_count += 1
                    if same_count >= 2:
                        save(img, 'refresh_no_effect')
                        log('停止刷新：连续刷新后商店没有变化（可能资金不足或刷新按钮没点到），截图已保存')
                        break
                else:
                    same_count = 0
            last_sig = sig
            if gold is None:
                GOLD_FAIL[0] += 1
                if GOLD_FAIL[0] <= 3:
                    save(img, 'gold_unreadable')
                log('警告：资金数字读取失败，按「未知」处理（尝试购买和刷新，由游戏提示判断是否买得起）')
            gold_v = 99 if gold is None else gold
            free = [c for c in allc if c['op'] and c['cost'] == 0]
            cards = [c for c in allc
                     if c['hi'] and c['op'] and c['cost'] is not None and c['cost'] <= gold_v]

            def owned(c):
                return any(n and (n in c['name'] or c['name'] in n) for n in board.owned)
            prio = sorted([c for c in cards if prio_index(c['name']) is not None],
                          key=lambda c: prio_index(c['name']))
            if free:
                pick = sorted(free, key=lambda c: -rank(c['name'], 5 if c['hi'] else 1))[:1]
            else:
                pick = (prio or [c for c in cards if owned(c)] or [c for c in cards if c['dps']]
                        or (cards if gold is not None and gold - 1 < 4 else []))
            failed = False
            for c in pick:
                tag = '优先' if prio_index(c['name']) is not None else ('输出' if c['dps'] else '非输出')
                log('购买 V/VI:', c['name'], tag, f'费用{c["cost"]}')
                if buy_and_deploy(board, c['i'], 5 if c['hi'] else 1, c['cost']):
                    board.owned[c['name']] = board.owned.get(c['name'], 0) + 1
                    got = True
                else:
                    failed = True
                break
            if failed:
                log('购买失败，结束本回合购买')
                break
            if got:
                last_sig = None
                continue
            if gold is not None and gold < 4:
                log(f'停止刷新：资金 {gold} 不足 4（本回合刷新 {refreshes} 次）')
                break
            refreshes += 1
            hi_n = sum(1 for c in allc if c['hi'] and c['op'])
            log(f'刷新商店（第 {refreshes} 次）：资金 {gold if gold is not None else "未知"}，当前 5/6 级干员 {hi_n} 张，可买 {len(cards)} 张')
            tap(*REFRESH, 1.0)
    if board.pending:
        if DEBUG:
            log(f'[debug] 回合结束前 pending=True，部署备战席；已有 ops={len(board.ops)}')
        deploy_bench(board)
        board.pending = False
    if DEBUG:
        log(f'[debug] 回合{rnd} 结束：场上 ops={len(board.ops)} pending={board.pending}')
    board.round_done = rnd
    board.prep_done = True
    time.sleep(1.5)
    tap(*READY, 1.5)
    board.last_ready = time.time()
    handle_popups()
    log(f'回合{rnd} 准备耗时 {time.time() - t0:.0f}s')
