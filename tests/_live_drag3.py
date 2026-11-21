"""拖拽排查：确认窗口是否真的获得前台，再用 SendInput 做一次平滑拖拽。"""
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.device.win32 import (Win32Device, Win32Options, find_window,  # noqa: E402
                                      user32, window_text)
from garrison_pc.logic import garrison as G  # noqa: E402

OUT = ROOT / 'farm_logs' / 'drag3'
LOG = OUT / 'log.txt'
user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]


class _U(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('union', _U)]


def log(*args):
    line = ' '.join(str(a) for a in args)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    sys.stdout.write(line + '\n')
    sys.stdout.flush()


def send_mouse(flags, dx=0, dy=0):
    inp = INPUT(type=0)
    inp.union.mi = MOUSEINPUT(dx, dy, 0, flags, 0, None)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def absxy(x, y):
    return int(x * 65535 / (user32.GetSystemMetrics(0) - 1)), \
           int(y * 65535 / (user32.GetSystemMetrics(1) - 1))


def force_foreground(hwnd):
    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        return True
    cur_tid = kernel32.GetCurrentThreadId()
    fg_tid = user32.GetWindowThreadProcessId(fg, None)
    attached = user32.AttachThreadInput(cur_tid, fg_tid, True)
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur_tid, fg_tid, False)
    time.sleep(0.6)
    return user32.GetForegroundWindow() == hwnd


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode('.png', img)
    if ok:
        (OUT / f'{name}.png').write_bytes(buf.tobytes())


def greens(dev_img):
    G.LAYOUT = {'safe': [[1195, 445], [1210, 548]],
                'path': [[1305, 345], [1192, 345], [1305, 445]],
                'rest': [[1305, 548], [1318, 650], [1440, 650]],
                'lift': [760, 650]}
    pts = G.LAYOUT['safe'] + G.LAYOUT['path'] + G.LAYOUT.get('rest', [])
    return [G.is_green(dev_img, p) for p in pts]


def main() -> int:
    if LOG.exists():
        LOG.unlink()
    try:
        return _main()
    except Exception:
        import traceback
        log(traceback.format_exc())
        return 2


def _main() -> int:
    hwnd = find_window(['明日方舟', 'Arknights'], ('Arknights.exe',))
    log('hwnd', hex(hwnd) if hwnd else None, window_text(hwnd) if hwnd else '')
    if not hwnd:
        return 1
    dev = Win32Device(hwnd, Win32Options(input='cursor', parallax_wait=0.25))
    log('fg before:', hex(user32.GetForegroundWindow()))
    ok = force_foreground(hwnd)
    log('force_foreground ->', ok, 'fg now:', hex(user32.GetForegroundWindow()))

    before = dev.shot()
    save(before, '00_before')
    log('greens before:', greens(before))

    start = dev.client_to_screen(int(sys.argv[1]) if len(sys.argv) > 2 else 1010,
                                 int(sys.argv[2]) if len(sys.argv) > 2 else 640)
    target = dev.client_to_screen(int(sys.argv[3]) if len(sys.argv) > 4 else 1195,
                                  int(sys.argv[4]) if len(sys.argv) > 4 else 445)
    log('screen start/target', start, target)

    user32.SetCursorPos(*start)
    time.sleep(0.2)
    send_mouse(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.7)                      # 长按，等游戏进入拖拽态
    lift = dev.shot()
    save(lift, '01_down')
    log('greens after down:', greens(lift))

    for i in range(1, 9):
        px, py = start[0], start[1] - i * 10
        user32.SetCursorPos(px, py)
        send_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, *absxy(px, py))
        time.sleep(0.05)
    time.sleep(0.4)
    lifted = dev.shot()
    save(lifted, '02_lifted')
    log('greens after lift:', greens(lifted))

    steps = 25
    for i in range(1, steps + 1):
        px = int(start[0] + (target[0] - start[0]) * i / steps)
        py = int((start[1] - 80) + (target[1] - (start[1] - 80)) * i / steps)
        user32.SetCursorPos(px, py)
        send_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, *absxy(px, py))
        time.sleep(0.03)
    time.sleep(0.4)
    at = dev.shot()
    save(at, '03_at_target')
    log('greens at target:', greens(at))

    send_mouse(MOUSEEVENTF_LEFTUP)
    time.sleep(1.2)
    after = dev.shot()
    save(after, '04_after')
    log('greens after up:', greens(after))
    log('diff before/after mean=%.2f' % float(cv2.absdiff(before, after).mean()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
