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
