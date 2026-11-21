"""设备层端到端自测：在一个真实的 Win32 窗口上验证截图与消息注入。

运行：
    D:\\DSH\\SHP_Auto\\_tools\\py311\\python.exe tests\\test_win32_device.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.device.win32 import Win32Device, Win32Options, find_window, list_windows  # noqa: E402


def wait_window(title: str, timeout: float = 15.0) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        hwnd = find_window([title], ())
        if hwnd:
            return hwnd
        time.sleep(0.2)
    raise RuntimeError('测试窗口没有出现：' + title)


def main() -> int:
    events_path = Path(tempfile.gettempdir()) / 'gfpc_device_events.json'
    if events_path.exists():
        events_path.unlink()
    proc = subprocess.Popen([sys.executable, str(ROOT / 'tests' / 'win32_test_window.py'),
                             '--events', str(events_path), '--seconds', '90'],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        line = proc.stdout.readline().strip()
        print('window:', line)
        hwnd = wait_window('GFPCTestWindow')
        print('hwnd:', hex(hwnd), 'windows:', [w['title'] for w in list_windows()][:8])

        device = Win32Device(hwnd, Win32Options(input='cursor', anchor_virtual=(480, 270),
                                                parallax_wait=0.05))
        print(device.describe())

        frame = device.shot()
        print('shot:', frame.shape, frame.dtype, 'mean=%.1f' % frame.mean())
        assert frame.shape == (1080, 1920, 3), frame.shape

        device.tap(480, 270, wait=0.1)
        time.sleep(0.4)
        data = json.loads(events_path.read_text(encoding='utf-8'))
        print('events after tap:', data['events'])
        assert data['events'], '窗口没有收到鼠标事件'
        first = data['events'][0]
        assert first['msg'] == hex(0x0200), first          # WM_MOUSEMOVE
        down = [e for e in data['events'] if e['msg'] == hex(0x0201)]
        assert down, '没有收到 WM_LBUTTONDOWN'
        ex, ey = device.virtual_to_client(480, 270)
        assert abs(down[0]['x'] - ex) <= 2 and abs(down[0]['y'] - ey) <= 2, (down[0], ex, ey)
        up = [e for e in data['events'] if e['msg'] == hex(0x0202)]
        assert up, '没有收到 WM_LBUTTONUP'

        after = device.shot()
        cx, cy = 480, 270
        dot = after[cy - 12:cy + 12, cx - 12:cx + 12]
        assert dot[:, :, 2].mean() > 120, '点击后截图里没有出现红点，mean=%.1f' % dot[:, :, 2].mean()

        device.swipe(200, 200, 800, 400, ms=400, wait=0.1)
        time.sleep(0.3)
        data = json.loads(events_path.read_text(encoding='utf-8'))
        moves = [e for e in data['events'] if e['msg'] == hex(0x0200)]
        print('total events:', len(data['events']), 'moves:', len(moves))
        assert len(moves) > 5, '滑动没有产生足够的 WM_MOUSEMOVE'
        device.close()
        print('OK: 截图 / 点击 / 滑动 全部通过')
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == '__main__':
    raise SystemExit(main())
