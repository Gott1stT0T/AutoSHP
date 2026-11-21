"""验证：用 SendInput（真实鼠标按键状态）拖拽干员，判断 PostMessage 拖动是否被游戏忽略。"""
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.device.win32 import (RECT, POINT, Win32Device, Win32Options,  # noqa: E402
                                      find_window, user32, window_text)

OUT = ROOT / 'farm_logs' / 'dragsi'

user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
INPUT_MOUSE = 0


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]


class _INPUTunion(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('union', _INPUTunion)]


def send_mouse(flags: int, dx: int = 0, dy: int = 0) -> None:
    inp = INPUT(type=INPUT_MOUSE)
    inp.union.mi = MOUSEINPUT(dx, dy, 0, flags, 0, None)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def abs_coords(x: int, y: int):
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    return int(x * 65535 / (sw - 1)), int(y * 65535 / (sh - 1))


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
    print('window:', window_text(hwnd), hex(hwnd), flush=True)
    dev = Win32Device(hwnd, Win32Options(input='cursor', parallax_wait=0.25))
    user32.ShowWindow(hwnd, 9)          # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.8)
    print('foreground now:', hex(user32.GetForegroundWindow()), flush=True)

    start_client = (1010, 655)
    target_client = (1195, 445)
    sx, sy = dev.client_to_screen(*start_client)
    tx, ty = dev.client_to_screen(*target_client)
    print('client->screen', (sx, sy), (tx, ty), flush=True)

    before = dev.shot()
    save(before, '00_before')

    user32.SetCursorPos(sx, sy)
    time.sleep(0.15)
    send_mouse(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.35)
    save(dev.shot(), '01_down')

    # 向上抬起 60px 触发“拿起”
    for i in range(1, 5):
        px, py = sx, sy - i * 15
        user32.SetCursorPos(px, py)
        ax, ay = abs_coords(px, py)
        send_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay)
        time.sleep(0.06)
    time.sleep(0.4)
    save(dev.shot(), '02_lifted')

    steps = 16
    for i in range(1, steps + 1):
        px = int(sx + (tx - sx) * i / steps)
        py = int((sy - 60) + (ty - (sy - 60)) * i / steps)
        user32.SetCursorPos(px, py)
        ax, ay = abs_coords(px, py)
        send_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay)
        time.sleep(0.02)
    time.sleep(0.4)
    save(dev.shot(), '03_at_target')

    send_mouse(MOUSEEVENTF_LEFTUP)
    time.sleep(1.2)
    save(dev.shot(), '04_after')
    print('done', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
