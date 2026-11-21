"""诊断：窗口状态 + PrintWindow 各种 flag + GDI 复采。

用法：python tests/_live_diag.py
"""
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.device import win32  # noqa: E402
from garrison_pc.device.win32 import (Win32Device, Win32Options, find_window,  # noqa: E402
                                      window_text, user32, gdi32, RECT)


def capture_with_flags(dev, flags):
    hwnd = dev.hwnd
    rect = RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mem, bmp)
    try:
        ok = user32.PrintWindow(hwnd, mem, flags)
        if not ok:
            return None, 'PrintWindow returned 0'
        img = dev._read_bitmap(mem, bmp, w, h)
        return img, 'ok'
    finally:
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(hwnd, hdc)


def main() -> int:
    hwnd = find_window(['明日方舟', 'Arknights'], ('Arknights.exe',))
    print('hwnd', hex(hwnd) if hwnd else None, flush=True)
    if not hwnd:
        return 1
    fg = user32.GetForegroundWindow()
    print('title:', window_text(hwnd), '| foreground:', window_text(fg) or hex(fg), flush=True)
    print('IsWindowVisible:', bool(user32.IsWindowVisible(hwnd)),
          'IsIconic:', bool(user32.IsIconic(hwnd)), flush=True)
    rect = RECT(); user32.GetWindowRect(hwnd, ctypes.byref(rect))
    print('window rect:', rect.left, rect.top, rect.right, rect.bottom, flush=True)
    crect = RECT(); user32.GetClientRect(hwnd, ctypes.byref(crect))
    print('client:', crect.right, crect.bottom, flush=True)

    dev = Win32Device(hwnd, Win32Options(input='cursor', parallax_wait=0.2))
    for flags in (0, win32.PW_RENDERFULLCONTENT, win32.PW_CLIENTONLY,
                  win32.PW_CLIENTONLY | win32.PW_RENDERFULLCONTENT):
        img, note = capture_with_flags(dev, flags)
        if img is None:
            print(f'flags={flags:#x}: {note}', flush=True)
        else:
            print(f'flags={flags:#x}: {img.shape} mean={img.mean():.1f} std={img.std():.1f}', flush=True)
            ok, buf = cv2.imencode('.png', img)
            if ok:
                (ROOT / 'farm_logs' / f'live_pw_{flags:#x}.png').write_bytes(buf.tobytes())
    gdi = dev._capture_gdi(hwnd)
    if gdi is not None:
        print('gdi again: mean=%.1f std=%.1f' % (gdi.mean(), gdi.std()), flush=True)
        ok, buf = cv2.imencode('.png', gdi)
        if ok:
            (ROOT / 'farm_logs' / 'live_gdi_again.png').write_bytes(buf.tobytes())
    print('done', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
