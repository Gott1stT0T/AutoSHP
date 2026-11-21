"""原始拖拽验证：按住备战席干员 → 分段移动 → 放到目标格 → 截图观察。
"""
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.device.win32 import Win32Device, Win32Options, find_window  # noqa: E402

OUT = ROOT / 'farm_logs' / 'dragraw'


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
    dev = Win32Device(hwnd, Win32Options(input='cursor', parallax_wait=0.25, move_step_delay=0.03))
    start = (1010, 655)
    target = (1195, 445)

    dev.tap(1500, 200, 0.3)          # 点空白处，确保没有选中卡牌
    frame = dev.shot()
    save(frame, '00_before')

    print('DOWN', start, flush=True)
    dev.touch('DOWN', *start)
    time.sleep(0.35)
    save(dev.shot(), '01_down')

    # 小步抬起（模拟人的拖拽起手）
    for i in range(1, 5):
        dev.touch('MOVE', start[0], start[1] - i * 15)
        time.sleep(0.05)
    time.sleep(0.25)
    save(dev.shot(), '02_lifted')

    # 移动到目标格
    steps = 12
    for i in range(1, steps + 1):
        x = start[0] + (target[0] - start[0]) * i / steps
        y = (start[1] - 60) + (target[1] - (start[1] - 60)) * i / steps
        dev.touch('MOVE', x, y)
        time.sleep(0.03)
    time.sleep(0.35)
    save(dev.shot(), '03_at_target')

    print('UP', flush=True)
    dev.touch('UP', *target)
    time.sleep(1.2)
    save(dev.shot(), '04_after')
    print('done', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
