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
