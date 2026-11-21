# 个人优化版 v1.2 的权威补丁（覆盖原版同名函数）

原仓库 `mumu_touch.py` 在运行期用 `exec(compile(...))` 替换了原版的两个函数。
新项目直接采用下面这份实现（逐字照抄，缩进按 4 空格），**不要**使用字节码里的旧版本。

```python
def passed_count(panel):
    import re
    import unicodedata
    texts=[str(t) for _,y,t in panel if y<350]
    for i,text in enumerate(texts):
        if '通过' not in text:
            continue
        def normalize(value):
            return ''.join(str(unicodedata.digit(c)) if c.isdigit() else c for c in value)
        combined=normalize(text)
        if i+1<len(texts):
            following=normalize(texts[i+1]).strip()
            if re.fullmatch(r'\d+\s*次?',following):
                combined+=following
        match=re.search(r'通过\s*(?:模拟)?\s*(\d+)\s*次',combined)
        if match:
            return int(match.group(1))
        return None
    return 0


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
```

另外，原仓库还把 `save_done` 包了一层，过滤掉 `无法识别名称[...]` 这类占位名：

```python
def save_done(s):
    return original_save_done({name for name in s if not str(name).startswith('无法识别名称[')})
```

新项目里 `save_done` 由运行时提供，过滤逻辑放在运行时（`Runtime.save_done`），
业务层不需要再包一层。
