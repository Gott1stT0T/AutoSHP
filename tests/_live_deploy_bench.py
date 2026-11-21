"""实机验证：deploy_bench（识别备战席 → 逐个拖到格子）是否能真的把人放上场。"""
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

OUT = ROOT / 'farm_logs' / 'deploybench'
LOG = OUT / 'log.txt'


def log(*args):
    line = ' '.join(str(a) for a in args)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    print(line, flush=True)


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode('.png', img)
    if ok:
        (OUT / f'{name}.png').write_bytes(buf.tobytes())


def main() -> int:
    if LOG.exists():
        LOG.unlink()
    hwnd = find_window(['明日方舟', 'Arknights'], ('Arknights.exe',))
    dev = Win32Device(hwnd, Win32Options(input='cursor', parallax_wait=0.25))
    info = maa_mod.load_maa()
    models = maa_mod.find_ocr_models(str(info.ocr_dir))
    engine = ocr_mod.create_engine(models.det.parent.parent)
    rt = Runtime(dev, ROOT / 'farm_logs', ROOT / 'farm_logs' / 'db_done.json', app_dir=ROOT)
    G.bind(rt)
    G.ocr_engine = engine
    G.DEBUG = True
    G.apply_layout({'GOLD_BOX': [1170, 20, 1265, 80]})
    G.set_profile('low')
    G.load_layout()
    log('LAYOUT loaded:', bool(G.LAYOUT))

    before = dev.shot()
    save(before, '00_before')
    pos = G.bench_positions(before)
    log('bench_positions:', pos)

    board = G.Board()
    G.deploy_bench(board)
    time.sleep(1.0)
    after = dev.shot()
    save(after, '01_after')
    log('board.ops:', board.ops)
    log('LAST_TILE:', G.LAST_TILE[0])
    diff = cv2.absdiff(before, after)
    log('diff mean=%.2f changed_px=%d' % (diff.mean(), int((diff.max(axis=2) > 12).sum())))
    log('run.log tail 见 farm_logs/run.log')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
