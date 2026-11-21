"""实验：点开一张干员卡（初雪），抓详情面板与购买按钮位置。"""
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc import maa as maa_mod, ocr as ocr_mod  # noqa: E402
from garrison_pc.device.win32 import Win32Device, Win32Options, find_window  # noqa: E402

OUT = ROOT / 'farm_logs' / 'opprobe'
LOG = OUT / 'probe.txt'


def log(*args, **kwargs):
    line = ' '.join(str(a) for a in args)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    sys.stdout.write(line + '\n')
    sys.stdout.flush()


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode('.png', img)
    if ok:
        (OUT / f'{name}.png').write_bytes(buf.tobytes())


def texts(engine, img, box=None):
    crop = img if box is None else img[box[1]:box[3], box[0]:box[2]]
    res, _ = engine(crop)
    ox = box[0] if box else 0
    oy = box[1] if box else 0
    return [(int(sum(p[0] for p in b) / 4) + ox, int(sum(p[1] for p in b) / 4) + oy, t)
            for b, t, s in (res or [])]


def main() -> int:
    hwnd = find_window(['明日方舟', 'Arknights'], ('Arknights.exe',))
    if not hwnd:
        log('no window')
        return 1
    dev = Win32Device(hwnd, Win32Options(input='cursor', parallax_wait=0.2))
    info = maa_mod.load_maa()
    models = maa_mod.find_ocr_models(str(info.ocr_dir))
    engine = ocr_mod.create_engine(models.det.parent.parent)

    frame = dev.shot()
    all_t = texts(engine, frame)
    joined = ''.join(t for _, _, t in all_t)
    log('current texts:', joined[:80])
    # 若停在确认弹窗，先点“确定/取消”
    for x, y, t in all_t:
        if t.strip() in ('确定', '确认', '取消'):
            log('dismiss dialog via', t, (x, y))
            dev.tap(x, y, wait=1.0)
            break

    frame = dev.shot()
    save(frame, 'shop_before')
    log('tap operator card (744,920)')
    dev.tap(744, 920, wait=1.2)
    after = dev.shot()
    save(after, 'after_select')
    log('--- full OCR after select ---')
    for x, y, t in sorted(texts(engine, after), key=lambda v: (v[1], v[0])):
        log(f'({x:4d},{y:4d}) {t}')
    log('--- left panel 0..760, 120..780 ---')
    for x, y, t in sorted(texts(engine, after, (0, 120, 760, 780)), key=lambda v: (v[1], v[0])):
        log(f'({x:4d},{y:4d}) {t}')
    log('--- card area 560..900, 840..1080 ---')
    for x, y, t in sorted(texts(engine, after, (560, 840, 900, 1080)), key=lambda v: (v[1], v[0])):
        log(f'({x:4d},{y:4d}) {t}')

    # 尝试点“卡片下方 106px”处，看是否购买成功（资金变化）
    log('tap purchase spot (744,1026)')
    dev.tap(744, 1026, wait=1.5)
    after2 = dev.shot()
    save(after2, 'after_purchase')
    log('--- OCR after purchase tap ---')
    for x, y, t in sorted(texts(engine, after2), key=lambda v: (v[1], v[0])):
        log(f'({x:4d},{y:4d}) {t}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
