"""抓 GDI 与 ScreenDC 两张当前画面，便于判断 GDI 是否陈旧。"""
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.device.win32 import Win32Device, Win32Options, find_window


def main() -> int:
    hwnd = find_window(['明日方舟', 'Arknights'], ('Arknights.exe',))
    if not hwnd:
        print('no window')
        return 1
    dev = Win32Device(hwnd, Win32Options())
    for name in ('gdi', 'screendc'):
        fn = getattr(dev, f'_capture_{name}')
        img = fn(hwnd)
        if img is None:
            print(name, 'None', flush=True)
            continue
        print(name, img.shape, 'mean=%.1f std=%.1f' % (img.mean(), img.std()), flush=True)
        ok, buf = cv2.imencode('.png', img)
        if ok:
            (ROOT / 'farm_logs' / f'live_{name}_now.png').write_bytes(buf.tobytes())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
