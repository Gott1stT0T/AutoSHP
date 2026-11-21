"""以管理员身份运行：验证 PrintWindow / GDI / 消息注入在真实游戏窗口上的表现。

输出写入 farm_logs/elevated_probe.txt（因为提权进程的控制台不可见）。
"""
from __future__ import annotations

import ctypes
import sys
import time
import traceback
from ctypes import wintypes
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.device import win32  # noqa: E402
from garrison_pc.device.win32 import (RECT, Win32Device, Win32Options,  # noqa: E402
                                      find_window, get_process_exe, user32)

LOG = ROOT / 'farm_logs' / 'elevated_probe.txt'


def log(*args) -> None:
    line = ' '.join(str(a) for a in args)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    print(line, flush=True)


def capture_with_flags(dev, flags):
    hwnd = dev.hwnd
    rect = RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetDC(hwnd)
    mem = win32.gdi32.CreateCompatibleDC(hdc)
    bmp = win32.gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = win32.gdi32.SelectObject(mem, bmp)
    try:
        ok = user32.PrintWindow(hwnd, mem, flags)
        if not ok:
            return None, f'PrintWindow returned 0 (err={ctypes.get_last_error()})'
        return dev._read_bitmap(mem, bmp, w, h), 'ok'
    finally:
        win32.gdi32.SelectObject(mem, old)
        win32.gdi32.DeleteObject(bmp)
        win32.gdi32.DeleteDC(mem)
        user32.ReleaseDC(hwnd, hdc)


def main() -> int:
    if LOG.exists():
        LOG.unlink()
    try:
        log('=== elevated probe ===')
        log('admin:', bool(ctypes.windll.shell32.IsUserAnAdmin()))
        hwnd = find_window(['明日方舟', 'Arknights'], ('Arknights.exe',))
        log('hwnd:', hex(hwnd) if hwnd else None)
        if not hwnd:
            return 1
        log('exe:', get_process_exe(hwnd))
        dev = Win32Device(hwnd, Win32Options(input='cursor', parallax_wait=0.2))
        log(dev.describe())
        time.sleep(0.3)
        for flags in (0, win32.PW_RENDERFULLCONTENT,
                      win32.PW_CLIENTONLY | win32.PW_RENDERFULLCONTENT):
            img, note = capture_with_flags(dev, flags)
            if img is None:
                log(f'printwindow flags={flags:#x}: {note}')
            else:
                log(f'printwindow flags={flags:#x}: {img.shape} mean={img.mean():.1f} std={img.std():.1f}')
                ok, buf = cv2.imencode('.png', img)
                if ok:
                    (ROOT / 'farm_logs' / f'elev_pw_{flags:#x}.png').write_bytes(buf.tobytes())
        img = dev._capture_gdi(hwnd)
        if img is not None:
            log(f'gdi: {img.shape} mean={img.mean():.1f} std={img.std():.1f}')
            ok, buf = cv2.imencode('.png', img)
            if ok:
                (ROOT / 'farm_logs' / 'elev_gdi.png').write_bytes(buf.tobytes())
        frame = dev.shot()
        log('shot():', frame.shape, 'mean=%.1f' % frame.mean())
        ok, buf = cv2.imencode('.png', frame)
        if ok:
            (ROOT / 'farm_logs' / 'elev_shot.png').write_bytes(buf.tobytes())
        log('capture method:', dev.last_frame_info)
        # 输入连通性：点击窗口中央（安全位置），看游戏是否响应；不做断言，只记录
        log('tap center (960,540) ...')
        dev.tap(960, 540, wait=0.6)
        time.sleep(1.0)
        frame2 = dev.shot()
        diff = float(cv2.absdiff(frame, frame2).mean())
        log('after tap diff=%.2f' % diff)
        ok, buf = cv2.imencode('.png', frame2)
        if ok:
            (ROOT / 'farm_logs' / 'elev_after_tap.png').write_bytes(buf.tobytes())
        log('done')
        return 0
    except Exception:
        log(traceback.format_exc())
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
