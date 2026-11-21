"""ADB 设备层（保留原项目对 MuMu / 雷电等模拟器的支持）。

协议与原 GarrisonFarm 一致：
  * 截图：``adb -s DEV exec-out screencap -p``
  * 点击：``adb -s DEV shell input tap X Y``
  * 滑动：``adb -s DEV shell input swipe X1 Y1 X2 Y2 MS``
  * 按住/移动/抬起：``adb -s DEV shell input motionevent DOWN|MOVE|UP X Y``

设备层对外仍然暴露 1920x1080 虚拟坐标；如果模拟器是别的分辨率，
会按实际截图尺寸做线性映射（原程序硬性要求 1920x1080，这里放宽了）。
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

CREATE_NO_WINDOW = 0x08000000


class AdbError(RuntimeError):
    pass


class AdbDevice:
    name = 'adb'

    def __init__(self, adb_path: str, address: str,
                 virtual_size: tuple[int, int] = (1920, 1080), timeout: float = 30.0):
        if not adb_path:
            raise AdbError('未指定 adb 路径')
        if not address:
            raise AdbError('未指定设备地址')
        self.adb_path = adb_path
        self.address = address
        self.virtual_w, self.virtual_h = virtual_size
        self.timeout = timeout
        self._held = False
        self._size: tuple[int, int] | None = None

    # -- 基础 -------------------------------------------------------------
    def _run(self, *args: str, capture: bool = False, timeout: float | None = None) -> bytes | None:
        cmd = [self.adb_path, '-s', self.address] + list(args)
        kwargs = {'capture_output': capture, 'creationflags': CREATE_NO_WINDOW}
        try:
            result = subprocess.run(cmd, timeout=timeout or self.timeout, **kwargs)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AdbError(f'adb 调用失败: {exc}') from exc
        if capture:
            return result.stdout
        return None

    def describe(self) -> str:
        w, h = self._screen_size()
        return f'adb={self.adb_path} device={self.address} 分辨率={w}x{h}'

    def ensure_ready(self) -> None:
        out = self._run('shell', 'echo', 'ok', capture=True, timeout=10) or b''
        if b'ok' not in out:
            raise AdbError(f'adb 设备 {self.address} 无响应')

    def _screen_size(self) -> tuple[int, int]:
        if self._size is None:
            raw = self._run('shell', 'wm', 'size', capture=True, timeout=10) or b''
            text = raw.decode('utf-8', 'replace')
            size = (1920, 1080)
            for line in text.splitlines():
                if ':' in line and 'x' in line:
                    try:
                        part = line.split(':')[-1].strip()
                        w, h = part.split('x')
                        size = (int(w), int(h))
                    except ValueError:
                        continue
            self._size = size
        return self._size

    def _scale(self) -> tuple[float, float]:
        w, h = self._screen_size()
        return w / self.virtual_w, h / self.virtual_h

    # -- 截图 -------------------------------------------------------------
    def capture(self) -> np.ndarray:
        for _ in range(5):
            raw = self._run('exec-out', 'screencap', '-p', capture=True) or b''
            if raw:
                img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    self._size = (img.shape[1], img.shape[0])
                    return img
            time.sleep(0.5)
        raise AdbError('截图失败（adb screencap 无输出）')

    def shot(self) -> np.ndarray:
        frame = self.capture()
        if frame.shape[1] != self.virtual_w or frame.shape[0] != self.virtual_h:
            frame = cv2.resize(frame, (self.virtual_w, self.virtual_h),
                               interpolation=cv2.INTER_AREA if frame.shape[1] > self.virtual_w
                               else cv2.INTER_LINEAR)
        return frame

    # -- 输入 -------------------------------------------------------------
    def _px(self, x: float, y: float) -> tuple[int, int]:
        sx, sy = self._scale()
        return int(round(x * sx)), int(round(y * sy))

    def tap(self, x: float, y: float, wait: float = 0.6) -> None:
        px, py = self._px(x, y)
        self._run('shell', 'input', 'tap', str(px), str(py))
        time.sleep(wait)

    def swipe(self, x1: float, y1: float, x2: float, y2: float,
              ms: int = 500, wait: float = 0.8) -> None:
        a = self._px(x1, y1)
        b = self._px(x2, y2)
        self._run('shell', 'input', 'swipe', str(a[0]), str(a[1]), str(b[0]), str(b[1]), str(int(ms)))
        time.sleep(wait)

    def touch(self, kind: str, x: float, y: float) -> None:
        kind = str(kind).upper()
        px, py = self._px(x, y)
        if kind not in ('DOWN', 'MOVE', 'UP'):
            raise ValueError(f'未知触控事件: {kind}')
        self._run('shell', 'input', 'motionevent', kind, str(px), str(py))
        self._held = kind != 'UP'

    def close(self) -> None:
        self._held = False


def find_adb(candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))
    found = shutil.which('adb')
    return found
