"""对比三种截图方式在真实游戏窗口上的表现，并检查 16:10 窗口里的 16:9 内容区。

用法：python tests/_live_capture_compare.py
"""
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.device.win32 import Win32Device, Win32Options, find_window  # noqa: E402


def save(img, name):
    out = ROOT / 'farm_logs' / name
    out.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode('.png', img)
    if ok:
        out.write_bytes(buf.tobytes())
    print('saved', out, img.shape, 'mean=%.1f std=%.1f' % (float(img.mean()), float(img.std())), flush=True)


def main() -> int:
    hwnd = find_window(['明日方舟', 'Arknights'], ('Arknights.exe',))
    if not hwnd:
        print('没有找到游戏窗口')
        return 1
    dev = Win32Device(hwnd, Win32Options(input='cursor', parallax_wait=0.3))
    print(dev.describe(), flush=True)
    time.sleep(0.5)

    for method in ('printwindow', 'gdi', 'screendc'):
        try:
            if method == 'printwindow':
                img = dev._capture_printwindow(hwnd)
            elif method == 'gdi':
                img = dev._capture_gdi(hwnd)
            else:
                img = dev._capture_screendc(hwnd)
        except Exception as exc:
            print(method, 'EXC', exc, flush=True)
            continue
        if img is None:
            print(method, 'None', flush=True)
            continue
        save(img, f'live_{method}_full.png')
        # 上/下黑边检测：整行均值
        rows = img.mean(axis=(1, 2))
        dark = rows < 3
        top = 0
        while top < len(dark) and dark[top]:
            top += 1
        bottom = 0
        while bottom < len(dark) and dark[len(dark) - 1 - bottom]:
            bottom += 1
        print(f'  {method}: 顶黑边 {top}px, 底黑边 {bottom}px, 行均值前5 {rows[:5].round(1)}', flush=True)
        save(dev.shot(), f'live_{method}_1920.png')
    print('done', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
