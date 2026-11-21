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
