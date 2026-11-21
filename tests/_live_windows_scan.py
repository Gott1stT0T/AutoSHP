"""列出 Arknights.exe 的所有顶层窗口（含不可见），并对比截图内容。"""
import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.device import win32  # noqa: E402
from garrison_pc.device.win32 import (RECT, Win32Device, Win32Options, get_process_exe,  # noqa: E402
                                      user32, window_class, window_text)

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def enum_all(exe_filter='Arknights.exe'):
    out = []

    @WNDENUMPROC
    def cb(hwnd, _):
        exe = get_process_exe(hwnd) or ''
        if not exe.lower().endswith(exe_filter.lower()):
            return True
        rect = RECT(); user32.GetClientRect(hwnd, ctypes.byref(rect))
        out.append(dict(hwnd=int(hwnd), title=window_text(hwnd), cls=window_class(hwnd),
                        visible=bool(user32.IsWindowVisible(hwnd)),
                        iconic=bool(user32.IsIconic(hwnd)),
                        client=(rect.right, rect.bottom)))
        return True

    user32.EnumWindows(cb, 0)
    return out


def main() -> int:
    wins = enum_all()
    for w in wins:
        print(w, flush=True)
    for w in wins:
        if w['client'][0] < 320:
            continue
        try:
            dev = Win32Device(w['hwnd'], Win32Options())
            frame = dev._capture_printwindow(w['hwnd'])
        except Exception as exc:
            print('capture fail', w['hwnd'], exc)
            continue
        if frame is None:
            print('hwnd', hex(w['hwnd']), 'printwindow None')
            continue
        print('hwnd', hex(w['hwnd']), 'frame', frame.shape,
              'mean=%.1f std=%.1f' % (frame.mean(), frame.std()))
        ok, buf = cv2.imencode('.png', frame)
        dev.close()
        if ok:
            (ROOT / 'farm_logs' / f'win_{w["hwnd"]:x}.png').write_bytes(buf.tobytes())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
