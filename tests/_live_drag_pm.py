"""用 PostMessage（当前实现）做一次拖拽，验证后台消息能否触发拖拽态。"""
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.device.win32 import (Win32Device, Win32Options, find_window,  # noqa: E402
                                      user32)
from garrison_pc.logic import garrison as G  # noqa: E402

OUT = ROOT / 'farm_logs' / 'dragpm'
LOG = OUT / 'log.txt'


def log(*args):
    line = ' '.join(str(a) for a in args)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    print(line, flush=True)


def greens(img):
    G.LAYOUT = {'safe': [[1195, 445], [1210, 548]],
                'path': [[1305, 345], [1192, 345], [1305, 445]],
                'rest': [[1305, 548], [1318, 650], [1440, 650]],
                'lift': [760, 650]}
    pts = G.LAYOUT['safe'] + G.LAYOUT['path'] + G.LAYOUT['rest']
    return [bool(G.is_green(img, p)) for p in pts]


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
    log('fg:', hex(user32.GetForegroundWindow()), 'hwnd:', hex(hwnd))
    start = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (1010, 680)
    target = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1305, 345)
    log('start/target', start, target)

    save(dev.shot(), '00_before')
    log('greens before', greens(dev.shot()))

    dev.touch('DOWN', *start)
    time.sleep(0.5)
    log('greens after down', greens(dev.shot()))

    for i in range(1, 9):
        dev.touch('MOVE', start[0], start[1] - i * 10)
        time.sleep(0.05)
    time.sleep(0.3)
    log('greens after lift', greens(dev.shot()))

    steps = 20
    for i in range(1, steps + 1):
        x = start[0] + (target[0] - start[0]) * i / steps
        y = (start[1] - 80) + (target[1] - (start[1] - 80)) * i / steps
        dev.touch('MOVE', x, y)
        time.sleep(0.03)
    time.sleep(0.3)
    log('greens at target', greens(dev.shot()))
    save(dev.shot(), '03_target')

    dev.touch('UP', *target)
    time.sleep(1.2)
    save(dev.shot(), '04_after')
    log('greens after up', greens(dev.shot()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
