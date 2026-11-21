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
