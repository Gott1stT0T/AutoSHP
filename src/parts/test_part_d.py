# -*- coding: utf-8 -*-
"""Differential tests: part_d.py vs the original frozen module (oracle).

Run with:  D:\\DSH\\SHP_Auto\\_tools\\py311\\python.exe test_part_d.py

Covers, in the order required by README section 4:
  1. green_tiles       synthetic numpy BGR images
  2. right3            synthetic numpy BGR images + synthetic tiles lists
  3. drag_path         recorder for `adb` (the function issues one shell command)
  4. bench_ops         synthetic numpy images
  5. load_layout       temporary tiles.json files
  6. is_green          synthetic numpy images, boundary radii
  7. drag_name         scripted fake `ocr`
  8. near              pure function, >=200 random cases
  9. deploy_from_bench recorder for deploy_layout / deploy_from_bench_old
"""
import json
import os
import random
import shutil
import sys
import tempfile
import traceback

sys.path.insert(0, r'D:\DSH\SHP_Auto\_ref')
import orig_garrison

import cv2
import numpy as np

PART_D = r'D:\DSH\SHP_Auto\GarrisonFarmPC\src\parts\part_d.py'

CHECKS = []


def load_both():
    orig = orig_garrison.load()
    new = orig_garrison.load()
    exec(compile(open(PART_D, encoding='utf-8').read(), PART_D, 'exec'), new)
    for ns in (orig, new):
        ns['cv2'] = cv2
        ns['np'] = np
    return orig, new


def check(name, cond, detail=''):
    CHECKS.append((name, bool(cond), detail))
    if not cond:
        print('  FAIL %s %s' % (name, detail))


def eq_case(name, fa, fb, args, kwargs=None):
    """Run both implementations; compare return value and raised exception."""
    kwargs = kwargs or {}
    try:
        ra = ('ok', fa(*args, **kwargs))
    except Exception as e:  # noqa: BLE001
        ra = ('exc', type(e).__name__, str(e))
    try:
        rb = ('ok', fb(*args, **kwargs))
    except Exception as e:  # noqa: BLE001
        rb = ('exc', type(e).__name__, str(e))
    ok = repr(ra) == repr(rb)
    if not ok:
        check(name, False, '\n    args=%r\n    oracle=%r\n    new   =%r' % (args, ra, rb))
    else:
        check(name, True)
    return ok


# ---------------------------------------------------------------------------
# images
# ---------------------------------------------------------------------------
def make_img(rects, size=(1080, 1920)):
    """rects: list of (x, y, w, h, bgr) uint8 rectangles on a black canvas."""
    img = np.zeros((size[0], size[1], 3), np.uint8)
    for rect in rects:
        x, y, w, h = rect[:4]
        color = rect[4] if len(rect) > 4 else (0, 200, 0)
        img[y:y + h, x:x + w] = color
    return img


def make_slanted(colfn, y0=140, y1=760, x0=800):
    """Green area whose right boundary is colfn(y) (perspective / curved edge)."""
    img = np.zeros((1080, 1920, 3), np.uint8)
    for y in range(y0, y1):
        xe = min(1919, max(0, int(colfn(y))))
        if xe > x0:
            img[y, x0:xe] = GREEN
    return img


GREEN = (0, 200, 0)
DARKGREEN = (0, 60, 0)
BLUE = (200, 0, 0)


def images():
    grid = []
    n = 0
    for i in range(8):
        for j in range(6):
            grid.append((200 + i * 170, 140 + j * 100, 80, 80, GREEN))
            n += 1
    assert n == 48
    wide = [(900 + i * 100, 140 + j * 100, 90, 90, GREEN) for i in range(7) for j in range(6)]
    return [
        ('empty', make_img([])),
        ('one-blob', make_img([(300, 200, 80, 80)])),
        ('three-blobs', make_img([(300, 200, 80, 80), (900, 400, 90, 90), (1400, 600, 70, 70)])),
        ('two-close', make_img([(600, 300, 80, 80), (680, 340, 80, 80)])),
        ('two-far-x', make_img([(400, 300, 60, 60), (560, 300, 60, 60)])),
        ('two-far-y', make_img([(400, 300, 60, 60), (400, 430, 60, 60)])),
        ('grid-48', make_img(grid)),
        ('wide-right', make_img([(1200, 140, 320, 620, GREEN), (600, 300, 80, 80, BLUE)])),
        ('hue-mix', make_img([(300, 200, 80, 80, BLUE), (900, 300, 80, 80, GREEN),
                              (1200, 500, 80, 80, DARKGREEN)])),
        ('slanted-linear', make_slanted(lambda y: 1100 + (y - 140) * 0.75)),
        ('slanted-curved', make_slanted(lambda y: 1200 + (y - 140) * 0.4 + 120 * ((y - 140) / 620.0) ** 2)),
        ('slanted-steep', make_slanted(lambda y: 1650 - (y - 140) * 0.7)),
        ('above-board', make_img([(300, 20, 80, 100)])),
        ('left-of-board', make_img([(20, 200, 120, 120)])),
        ('tiny', make_img([(20, 20, 30, 30)], size=(200, 200))),
    ]


# ---------------------------------------------------------------------------
# 1. green_tiles
# ---------------------------------------------------------------------------
def test_green_tiles(orig, new):
    print('green_tiles:')
    lens = []
    for name, img in images():
        eq_case('green_tiles[%s]' % name, orig['green_tiles'], new['green_tiles'], (img.copy(),))
        lens.append(len(orig['green_tiles'](img.copy())))
    # coverage: empty result, dedup, and the 40-point cap must all be exercised
    check('green_tiles-coverage', (0 in lens and max(lens) == 40 and 1 in lens
                                   and any(1 < n < 40 for n in lens)), 'lens=%r' % (lens,))
    print('  %d cases (result sizes %r)' % (len(images()), lens))


# ---------------------------------------------------------------------------
# 2. right3
# ---------------------------------------------------------------------------
def test_right3(orig, new):
    print('right3:')
    tiles_sets = [
        [],
        [(100, 200)],
        [(1600, 200), (1500, 400), (100, 700)],
        [(1650, 140), (1650, 760), (0, 0)],
        [(1000, 200), (1450, 200), (1450, 690), (900, 450), (1600, 450)],
    ]
    imgs = images()
    n = 0
    sizes = []
    for name, img in imgs:
        for tiles in tiles_sets:
            eq_case('right3[%s]' % name, orig['right3'], new['right3'], (list(tiles), img.copy()))
            sizes.append(len(orig['right3'](list(tiles), img.copy())))
            n += 1
    # tiles derived from the real detector, so the polyfit branch gets realistic input
    for name, img in imgs:
        tiles = orig['green_tiles'](img.copy())
        eq_case('right3-detected[%s]' % name, orig['right3'], new['right3'], (tiles, img.copy()))
        sizes.append(len(orig['right3'](tiles, img.copy())))
        n += 1
    # coverage: both "no green at all" / "no usable edge row" and the keep path
    check('right3-coverage', (0 in sizes and any(s > 0 for s in sizes) and
                              any(s == 2 for s in sizes)), 'sizes=%r' % (sizes,))
    print('  %d cases (kept counts %r)' % (n, sorted(set(sizes))))


# ---------------------------------------------------------------------------
# 3. drag_path
# ---------------------------------------------------------------------------
def test_drag_path(orig, new):
    print('drag_path:')
    cases = [
        (100, 200, 300, 400),
        (100, 200, 300, 400, 1),
        (100, 200, 300, 400, 2),
        (0, 0, 1920, 1080, 7),
        (1920, 1080, 0, 0, 12),
        (960, 540, 960, 540),
        (100.7, 200.2, 300.9, 400.1, 12),
        (-50, -80, 3000, 2000, 30),
    ]
    for args in cases:
        rec_a, rec_b = [], []
        orig['adb'] = lambda *a, _r=rec_a: _r.append(a)
        new['adb'] = lambda *a, _r=rec_b: _r.append(a)
        ra = orig['drag_path'](*args)
        rb = new['drag_path'](*args)
        ok = (ra == rb) and (rec_a == rec_b) and ra is None
        check('drag_path%r' % (args,), ok,
              '' if ok else '\n    oracle rec=%r\n    new rec   =%r' % (rec_a, rec_b))
    print('  %d cases' % len(cases))


# ---------------------------------------------------------------------------
# 4. bench_ops
# ---------------------------------------------------------------------------
def test_bench_ops(orig, new):
    print('bench_ops:')
    for name, img in images():
        eq_case('bench_ops[%s]' % name, orig['bench_ops'], new['bench_ops'], (img.copy(),))
    print('  %d cases' % len(images()))


# ---------------------------------------------------------------------------
# 5. load_layout
# ---------------------------------------------------------------------------
def test_load_layout(orig, new):
    print('load_layout:')
    root = tempfile.mkdtemp(prefix='partd_layout_')
    try:
        d1 = os.path.join(root, 'here')
        d2 = os.path.join(root, 'file')
        os.makedirs(d1)
        os.makedirs(d2)
        f_in_d2 = os.path.join(d2, 'garrison_farm.py')
        p1 = os.path.join(d1, 'tiles.json')
        p2 = os.path.join(d2, 'tiles.json')

        def setup_here():
            with open(p1, 'w', encoding='utf-8') as f:
                json.dump({'tiles': [[1, 2], [3, 4]], '名': '值'}, f, ensure_ascii=False)
            if os.path.exists(p2):
                os.remove(p2)

        def setup_exc_then_fallback():
            with open(p1, 'w', encoding='utf-8') as f:
                f.write('{ not json')
            with open(p2, 'w', encoding='utf-8') as f:
                json.dump({'from': 'file-dir'}, f)

        def setup_missing():
            if os.path.exists(p1):
                os.remove(p1)
            if os.path.exists(p2):
                os.remove(p2)

        cases = [
            ('here', setup_here, {'tiles': [[1, 2], [3, 4]], '名': '值'}),
            ('fallback-after-exc', setup_exc_then_fallback, {'from': 'file-dir'}),
            ('missing', setup_missing, None),
        ]

        for name, setup, expected in cases:
            setup()
            for ns in (orig, new):
                ns['HERE'] = d1
                ns['_here'] = lambda d=d1: d
                ns['__file__'] = f_in_d2
                ns['LAYOUT'] = None
            ra = orig['load_layout']()
            rb = new['load_layout']()
            la, lb = orig['LAYOUT'], new['LAYOUT']
            ok = (repr(ra) == repr(rb)) and (repr(la) == repr(lb)) and (repr(lb) == repr(expected))
            check('load_layout[%s]' % name, ok,
                  '' if ok else '\n    oracle ret=%r LAYOUT=%r\n    new ret=%r LAYOUT=%r\n    expected=%r'
                  % (ra, la, rb, lb, expected))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print('  3 cases')


# ---------------------------------------------------------------------------
# 6. is_green
# ---------------------------------------------------------------------------
def test_is_green(orig, new):
    print('is_green:')
    img = make_img([(400, 300, 120, 120), (1000, 200, 40, 40, BLUE)])
    pts = [(400, 300), (460, 360), (1000, 200), (1500, 900), (0, 0), (1919, 1079),
           (405.7, 305.2), (-10, -10)]
    radii = [1, 5, 22, 40, 60]
    n = 0
    for pt in pts:
        for r in radii:
            eq_case('is_green%r r=%r' % (pt, r), orig['is_green'], new['is_green'], (img.copy(), pt, r))
            n += 1
    # boundary radii
    for r in (0, -1, -22):
        eq_case('is_green-boundary r=%r' % r, orig['is_green'], new['is_green'], (img.copy(), (400, 300), r))
        n += 1
    # default radius omitted
    eq_case('is_green-default', orig['is_green'], new['is_green'], (img.copy(), (400, 300)))
    n += 1
    print('  %d cases' % n)


# ---------------------------------------------------------------------------
# 7. drag_name
# ---------------------------------------------------------------------------
OCR_SCRIPTS = [
    [],
    [(1, 2, '')],
    # contains 'LV' -> skipped (that is the level label line)
    [(0, 0, '鏅旈湶  LV')],
    [(0, 0, 'LV 5 鏅旈湶')],
    [(0, 0, 'ABC LV')],
    [(0, 0, 'LV')],
    [(0, 0, 'lv')],
    [(0, 0, '中文 LV 33')],
    [(0, 0, '123 LV')],
    [(0, 0, 'LV1')],
    # no 'LV' -> the name line, returned stripped
    [(0, 0, '鏅旈湶')],
    [(0, 0, '  名字  ')],
    [(0, 0, 'ABC')],
    [(0, 0, 'L V')],
    [(0, 0, 'かな')],
    [(0, 0, 'éclair')],
    [(0, 0, '鿿')],
    [(0, 0, '一')],
    # punctuation / digits only -> not a name line
    [(0, 0, '。')],
    [(0, 0, '123')],
    [(0, 0, '\u3007')],
    [(0, 0, '  ')],
    # several OCR lines: first matching line wins
    [(0, 0, '123'), (0, 0, '名字'), (0, 0, 'other')],
    [(0, 0, 'name LV 5'), (0, 0, 'second name')],
    [(0, 0, 'second LV'), (0, 0, 'first name')],
    [(0, 0, 'LV 1'), (0, 0, 'LV 2')],
]


def test_drag_name(orig, new):
    print('drag_name:')
    n = 0
    for i, script in enumerate(OCR_SCRIPTS):
        rec_a, rec_b = [], []
        orig['ocr'] = lambda img, box=None, _s=script, _r=rec_a: (_r.append((img, box)), _s)[1]
        new['ocr'] = lambda img, box=None, _s=script, _r=rec_b: (_r.append((img, box)), _s)[1]
        img = np.zeros((1080, 1920, 3), np.uint8)
        ra = rb = None
        ea = eb = None
        try:
            ra = orig['drag_name'](img)
        except Exception as e:  # noqa: BLE001
            ea = (type(e).__name__, str(e))
        try:
            rb = new['drag_name'](img)
        except Exception as e:  # noqa: BLE001
            eb = (type(e).__name__, str(e))
        ok = (repr(ra) == repr(rb)) and (repr(ea) == repr(eb)) and (rec_a == rec_b)
        check('drag_name[%d] %r' % (i, script[-1] if script else []), ok,
              '' if ok else '\n    oracle=%r exc=%r rec=%r\n    new   =%r exc=%r rec=%r'
              % (ra, ea, rec_a, rb, eb, rec_b))
        n += 1
    # coverage: both the "return the name line" and the "no name" paths must be hit
    got = set()
    for script in OCR_SCRIPTS:
        orig['ocr'] = lambda img, box=None, _s=script: _s
        try:
            got.add(orig['drag_name'](None))
        except Exception as e:  # noqa: BLE001
            got.add(type(e).__name__)
    names = {v for v in got if isinstance(v, str) and v and v not in ('IndexError', 'TypeError', 'ValueError')}
    check('drag_name-coverage', ('' in got and len(names) >= 5), 'got=%r' % (got,))
    print('  %d cases (outcomes %r)' % (n, sorted(map(repr, got))))


# ---------------------------------------------------------------------------
# 8. near
# ---------------------------------------------------------------------------
def test_near(orig, new):
    print('near:')
    rnd = random.Random(20240501)
    cases = []
    # exhaustive-ish small grid
    pts = [(0, 0), (0, 1), (1, 0), (10, 10), (11, 10), (-5, -5), (100, 200), (1000, 1000)]
    for t in pts:
        for n_pts in range(0, 5):
            lst = [rnd.choice(pts) for _ in range(n_pts)]
            for d in (0, 1, 5, 10, 95, 200, -1):
                cases.append((t, lst, d))
    # random
    for _ in range(220):
        t = (rnd.randint(-50, 60), rnd.randint(-50, 60))
        lst = [(rnd.randint(-50, 60), rnd.randint(-50, 60)) for _ in range(rnd.randint(0, 10))]
        d = rnd.choice([0, 1, 2, 3, 5, 10, 95, 500])
        cases.append((t, lst, d))
    for args in cases:
        eq_case('near%r' % (args,), orig['near'], new['near'], args)
    # default d
    eq_case('near-default', orig['near'], new['near'], ((0, 0), [(96, 0)]))
    eq_case('near-default2', orig['near'], new['near'], ((0, 0), [(95, 95)]))
    print('  %d cases' % (len(cases) + 2))


# ---------------------------------------------------------------------------
# 9. deploy_from_bench
# ---------------------------------------------------------------------------
def test_deploy_from_bench(orig, new):
    print('deploy_from_bench:')

    def run(ns, args, kwargs, layout):
        rec = []
        ns['LAYOUT'] = layout
        ns['deploy_layout'] = lambda *a, **k: (rec.append(('deploy_layout', a, k)), 'LAYOUT-RESULT')[1]
        ns['deploy_from_bench_old'] = lambda *a, **k: (rec.append(('old', a, k)), 'OLD-RESULT')[1]
        try:
            r = ('ok', ns['deploy_from_bench'](*args, **kwargs))
        except Exception as e:  # noqa: BLE001
            r = ('exc', type(e).__name__, str(e))
        return r, rec

    cases = [
        (((320, 500),), {}),
        (((320, 500),), {'quiet': True}),
        (((320, 500), True, 'BOARD'), {}),
        (((320, 500),), {'board': 'BOARD'}),
        (((320, 500),), {'board': 'BOARD', 'hi': True}),
        (((320, 500),), {'board': 'BOARD', 'hi': False}),
        (((320, 500), False, 'BOARD', True), {}),
        (((320, 500),), {'quiet': True, 'board': 'BOARD', 'hi': True}),
    ]
    layouts = [None, {}, {'tiles': 1}, 0, 'truthy']
    n = 0
    for layout in layouts:
        for args, kwargs in cases:
            ra, rec_a = run(orig, args, kwargs, layout)
            rb, rec_b = run(new, args, kwargs, layout)
            ok = (repr(ra) == repr(rb)) and (rec_a == rec_b)
            check('deploy_from_bench layout=%r %r %r' % (layout, args, kwargs), ok,
                  '' if ok else '\n    oracle=%r rec=%r\n    new   =%r rec=%r'
                  % (ra, rec_a, rb, rec_b))
            n += 1
    print('  %d cases' % n)


def test_metadata(orig, new):
    print('metadata:')
    for fn in ('green_tiles', 'right3', 'drag_path', 'bench_ops', 'load_layout',
               'is_green', 'drag_name', 'near', 'deploy_from_bench'):
        a, b = orig[fn].__defaults__, new[fn].__defaults__
        ca, cb = orig[fn].__code__, new[fn].__code__
        ok = (a == b and ca.co_argcount == cb.co_argcount
              and ca.co_varnames == cb.co_varnames
              and ca.co_cellvars == cb.co_cellvars
              and ca.co_consts[0] == cb.co_consts[0]
              and ca.co_flags == cb.co_flags)
        check('meta[%s]' % fn, ok,
              '' if ok else '\n    defaults %r/%r varnames %r/%r cell %r/%r const0 %r/%r'
              % (a, b, ca.co_varnames, cb.co_varnames, ca.co_cellvars,
                 cb.co_cellvars, ca.co_consts[0], cb.co_consts[0]))


def main():
    orig, new = load_both()
    test_metadata(orig, new)
    test_green_tiles(orig, new)
    test_right3(orig, new)
    test_drag_path(orig, new)
    test_bench_ops(orig, new)
    test_load_layout(orig, new)
    test_is_green(orig, new)
    test_drag_name(orig, new)
    test_near(orig, new)
    test_deploy_from_bench(orig, new)
    failed = [c for c in CHECKS if not c[1]]
    print('\n%d checks, %d failed' % (len(CHECKS), len(failed)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
