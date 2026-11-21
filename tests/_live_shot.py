"""提权后抓一张当前游戏画面（不点击）。"""
import ctypes
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.device.win32 import Win32Device, Win32Options, find_window, window_text

OUT = ROOT / 'farm_logs' / 'live_now_elev.png'


def main() -> int:
    hwnd = find_window(['明日方舟', 'Arknights'], ('Arknights.exe',))
    if not hwnd:
        print('no window')
        return 1
    print('admin:', bool(ctypes.windll.shell32.IsUserAnAdmin()), 'title:', window_text(hwnd))
    dev = Win32Device(hwnd, Win32Options(input='cursor', parallax_wait=0.2))
    print(dev.describe())
    time.sleep(0.5)
    frame = dev.shot()
    print('shot', frame.shape, 'mean=%.1f std=%.1f' % (frame.mean(), frame.std()),
          'method', dev.last_frame_info)
    ok, buf = cv2.imencode('.png', frame)
    if ok:
        OUT.write_bytes(buf.tobytes())
    print('saved', OUT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
