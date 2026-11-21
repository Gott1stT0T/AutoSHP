"""实验：点一下商店卡牌，看看 PC 端会弹出什么（用于校正 buy() 的判定）。"""
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc import maa as maa_mod, ocr as ocr_mod  # noqa: E402
from garrison_pc.device.win32 import Win32Device, Win32Options, find_window  # noqa: E402

OUT = ROOT / 'farm_logs' / 'click'


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode('.png', img)
    if ok:
        (OUT / f'{name}.png').write_bytes(buf.tobytes())


def main() -> int:
    hwnd = find_window(['明日方舟', 'Arknights'], ('Arknights.exe',))
    if not hwnd:
        print('no window')
        return 1
    dev = Win32Device(hwnd, Win32Options(input='cursor', parallax_wait=0.2))
    info = maa_mod.load_maa()
    models = maa_mod.find_ocr_models(str(info.ocr_dir))
    engine = ocr_mod.create_engine(models.det.parent.parent)

    before = dev.shot()
    save(before, 'before')
    x, y = 986, 920
    print('tap', x, y, flush=True)
    dev.tap(x, y, wait=1.2)
    after = dev.shot()
    save(after, 'after')

    res, _ = engine(after)
    texts = [(int(sum(p[0] for p in box) / 4), int(sum(p[1] for p in box) / 4), t)
             for box, t, score in (res or [])]
    print('--- OCR after click ---', flush=True)
    for tx, ty, t in sorted(texts, key=lambda v: (v[1], v[0])):
        print(f'({tx:4d},{ty:4d}) {t}', flush=True)
    print('--- left panel (0,200)-(760,700) ---', flush=True)
    left = after[200:700, 0:760]
    res2, _ = engine(left)
    print([str(item[1]) for item in (res2 or [])], flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
