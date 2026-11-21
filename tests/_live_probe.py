"""实机探测：启动鹰角启动器 → 等待游戏窗口 → 抓一张真实画面（不发送任何点击）。

用法：
    python tests/_live_probe.py [等待秒数]
"""
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc import maa  # noqa: E402
from garrison_pc.device.win32 import Win32Device, Win32Options, find_window, list_windows  # noqa: E402


def main() -> int:
    wait = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    launcher = maa.find_launcher()
    print('launcher:', launcher, flush=True)
    if launcher is None:
        print('没有找到鹰角启动器', flush=True)
        return 1
    if not maa.game_running():
        print('启动启动器...', flush=True)
        maa.launch(launcher, launcher.parent)
    else:
        print('游戏进程已在运行', flush=True)

    hwnd = None
    deadline = time.time() + wait
    last_note = 0
    while time.time() < deadline:
        hwnd = find_window(['明日方舟', 'Arknights'], ('Arknights.exe',))
        if hwnd:
            break
        if time.time() - last_note > 10:
            last_note = time.time()
            print('等待游戏窗口……（请在启动器里点“开始游戏”/完成登录）', flush=True)
        time.sleep(2)

    if not hwnd:
        print('超时：没有等到游戏窗口', flush=True)
        for info in list_windows():
            print('  ', hex(info['hwnd']), info['client'], info['class'], info['title'], info['exe'], flush=True)
        return 2

    print('game window:', hex(hwnd), flush=True)
    device = Win32Device(hwnd, Win32Options(input='cursor', parallax_wait=0.3))
    print(device.describe(), flush=True)
    time.sleep(1.0)
    try:
        frame = device.shot()
    except Exception as exc:
        print('截图失败:', exc, flush=True)
        return 3
    out = ROOT / 'farm_logs' / 'live_probe.png'
    out.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode('.png', frame)
    if ok:
        out.write_bytes(buf.tobytes())
    print('frame:', frame.shape, 'mean=%.1f std=%.1f' % (float(frame.mean()), float(frame.std())), flush=True)
    print('saved:', out, flush=True)
    print('capture method:', device.last_frame_info, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
