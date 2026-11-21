"""打印游戏窗口信息（客户区、窗口位置、状态）。"""
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.device import win32  # noqa: E402
from garrison_pc.device.win32 import (RECT, POINT, find_window, get_process_exe,  # noqa: E402
                                      user32, window_class, window_text)


def main() -> int:
    hwnd = find_window(['明日方舟', 'Arknights'], ('Arknights.exe',))
    if not hwnd:
        print('no window')
        return 1
    print('hwnd', hex(hwnd), 'title', window_text(hwnd), 'class', window_class(hwnd))
    print('exe', get_process_exe(hwnd))
    wr = RECT(); user32.GetWindowRect(hwnd, ctypes.byref(wr))
    cr = RECT(); user32.GetClientRect(hwnd, ctypes.byref(cr))
    origin = POINT(0, 0); user32.ClientToScreen(hwnd, ctypes.byref(origin))
    print('window', wr.left, wr.top, wr.right, wr.bottom)
    print('client', cr.right, cr.bottom, 'origin', origin.x, origin.y)
    print('visible', bool(user32.IsWindowVisible(hwnd)), 'iconic', bool(user32.IsIconic(hwnd)),
          'zoomed', bool(user32.IsZoomed(hwnd)))
    print('foreground', hex(user32.GetForegroundWindow()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
