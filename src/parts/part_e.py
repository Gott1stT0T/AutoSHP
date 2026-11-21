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
