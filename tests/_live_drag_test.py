"""实机验证：从备战席拖动一名干员到地图格子（走完整 deploy_from_bench 逻辑）。"""
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc import maa as maa_mod, ocr as ocr_mod  # noqa: E402
from garrison_pc.device.win32 import Win32Device, Win32Options, find_window  # noqa: E402
from garrison_pc.logic import garrison as G  # noqa: E402
from garrison_pc.runtime import Runtime  # noqa: E402

OUT = ROOT / 'farm_logs' / 'dragtest'


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
    dev = Win32Device(hwnd, Win32Options(input='cursor', parallax_wait=0.25))
    info = maa_mod.load_maa()
    models = maa_mod.find_ocr_models(str(info.ocr_dir))
    engine = ocr_mod.create_engine(models.det.parent.parent)
    rt = Runtime(dev, ROOT / 'farm_logs', ROOT / 'farm_logs' / 'drag_done.json', app_dir=ROOT)
    G.bind(rt)
    G.ocr_engine = engine
    G.apply_layout({'GOLD_BOX': [1170, 20, 1265, 80]})
    G.set_profile('low')
    G.load_layout()

    before = dev.shot()
    save(before, 'before')
    text = ''.join(t for _, _, t in G.ocr(before))
    print('screen:', text[:80], flush=True)

    board = G.Board()
    slot = (870, 650)
    print('deploy_from_bench', slot, flush=True)
    result = G.deploy_from_bench(slot, quiet=False, board=board, hi=False)
    print('result:', result, flush=True)

    time.sleep(0.5)
    after = dev.shot()
    save(after, 'after')
    t2 = ''.join(t for _, _, t in G.ocr(after))
    print('after screen:', t2[:80], flush=True)
    print('LAST_TILE:', G.LAST_TILE[0], 'LAST_TIER:', G.LAST_TIER[0], flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
