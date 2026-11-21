"""集成自检：用一个真实 Win32 窗口冒充游戏窗口，跑 `--check` 全流程。

验证：MAA 配置读取 → PaddleOCR 模型加载 → 窗口查找 → PrintWindow 截图 →
      缩放到 1920x1080 → 自检输出 → 退出码。

运行：
    D:\\DSH\\SHP_Auto\\_tools\\py311\\python.exe tests\\test_app_check.py
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.app import main  # noqa: E402


def main_test() -> int:
    events = Path(tempfile.gettempdir()) / 'gfpc_app_check.json'
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / 'tests' / 'win32_test_window.py'),
         '--events', str(events), '--title', '明日方舟', '--seconds', '120'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding='utf-8', errors='replace')
    try:
        line = proc.stdout.readline().strip()
        print('window:', line)
        if not line.startswith('READY'):
            print('窗口启动失败')
            return 1
        time.sleep(1.0)
        code = main(['--check', '--yes', '--no-elevate'])
        print('app exit code:', code)
        shot = ROOT / 'farm_logs' / 'startup_check.png'
        print('startup screenshot:', shot, shot.exists(), shot.stat().st_size if shot.exists() else 0)
        if code != 0:
            return code
        if not shot.exists() or shot.stat().st_size < 1000:
            print('没有生成自检截图')
            return 1
        import cv2
        img = cv2.imread(str(shot))
        print('screenshot shape:', None if img is None else img.shape)
        assert img is not None and img.shape[:2] == (1080, 1920), img.shape if img is not None else None
        print('OK: --check 全流程通过')
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == '__main__':
    raise SystemExit(main_test())
