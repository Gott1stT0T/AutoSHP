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
