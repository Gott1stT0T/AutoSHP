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
