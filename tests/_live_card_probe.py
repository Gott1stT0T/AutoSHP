"""等待商店界面出现，点开一张「干员」卡，抓取详情面板与购买按钮位置。"""
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc import maa as maa_mod, ocr as ocr_mod  # noqa: E402
from garrison_pc.device.win32 import Win32Device, Win32Options, find_window  # noqa: E402

OUT = ROOT / 'farm_logs' / 'cardprobe'
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
    return [(int(sum(p[0] for p in b) / 4) + (box[0] if box else 0),
             int(sum(p[1] for p in b) / 4) + (box[1] if box else 0), t)
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

    deadline = time.time() + 300
    shop = None
    while time.time() < deadline:
        frame = dev.shot()
        joined = ''.join(t for _, _, t in texts(engine, frame))
        if '刷新' in joined and '升级' in joined and '回合' in joined:
            shop = frame
            log('shop detected', flush=True)
            break
        log('waiting shop...', joined[:60], flush=True)
        time.sleep(5)
    if shop is None:
        log('timeout waiting shop')
        return 2

    save(shop, 'shop')
    all_texts = sorted(texts(engine, shop), key=lambda v: (v[1], v[0]))
    log('--- shop texts ---', flush=True)
    for x, y, t in all_texts:
        log(f'({x:4d},{y:4d}) {t}', flush=True)

    # 找一张干员卡（名字在 y≈1020 附近、且不是装备）
    cards = [(x, t) for x, y, t in all_texts if 990 <= y <= 1060]
    log('candidates:', cards, flush=True)
    if not cards:
        return 3
    x, name = cards[0]
    log('click card', name, 'at', x, flush=True)
    dev.tap(x, 920, wait=1.2)
    after = dev.shot()
    save(after, 'after_card')
    log('--- left panel 0..760, 150..760 ---', flush=True)
    for tx, ty, t in sorted(texts(engine, after, (0, 150, 760, 760)), key=lambda v: (v[1], v[0])):
        log(f'({tx:4d},{ty:4d}) {t}', flush=True)
    log('--- around card (x-160..x+160, 750..1080) ---', flush=True)
    for tx, ty, t in sorted(texts(engine, after, (max(0, x - 160), 750, x + 160, 1080)),
                            key=lambda v: (v[1], v[0])):
        log(f'({tx:4d},{ty:4d}) {t}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
