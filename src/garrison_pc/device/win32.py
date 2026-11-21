"""官方 PC 端（Win32 窗口）设备层。

设计要点（与 MaaFramework 的 MaaWin32ControlUnit 对齐）：

* 截图：``PrintWindow(hwnd, hdc, PW_CLIENTONLY | PW_RENDERFULLCONTENT)``，
  只取客户区，后台/被遮挡也能拿到画面；如果返回黑图则回退到 GDI BitBlt，
  再回退到桌面 DC（需要窗口可见）。
* 输入：官方 PC 端「只认真实鼠标位置」，因此默认使用
  ``PostMessageWithCursorPos`` 等价策略：先把真实光标移动到目标点，
  再向窗口投递 ``WM_ACTIVATE`` / ``WM_MOUSEMOVE`` / ``WM_LBUTTONDOWN`` /
  ``WM_LBUTTONUP``（坐标为**客户区像素**）。
* 视差：游戏的 UI 会随鼠标位置轻微偏移。因此在每次截图前把光标停在固定锚点
  （默认客户区中心），并在移动后等待 ``parallax_wait`` 秒再截图。
* 坐标：对外暴露 1920x1080 虚拟坐标系，内部按客户区实际像素线性映射。
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Win32 常量
# ---------------------------------------------------------------------------
PW_CLIENTONLY = 0x00000001
PW_RENDERFULLCONTENT = 0x00000002

WM_ACTIVATE = 0x0006
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205

MK_LBUTTON = 0x0001
WA_ACTIVE = 1

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
DIB_RGB_COLORS = 0
GA_ROOTOWNER = 3

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

CREATE_NO_WINDOW = 0x08000000

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)


class RECT(ctypes.Structure):
    _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG),
                ('right', wintypes.LONG), ('bottom', wintypes.LONG)]


class POINT(ctypes.Structure):
    _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', wintypes.DWORD * 3)]


user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND,
                                                  wintypes.LPARAM), wintypes.LPARAM]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.GetLastActivePopup.argtypes = [wintypes.HWND]
user32.GetLastActivePopup.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.BlockInput.argtypes = [wintypes.BOOL]
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                            ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT]
gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]


def enable_dpi_awareness() -> None:
    """让 GetClientRect/PrintWindow 使用物理像素（避免高 DPI 下只截到一部分）。"""
    try:
        user32.SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def _makelparam(x: int, y: int) -> int:
    return (int(y) << 16) | (int(x) & 0xFFFF)


def get_process_exe(hwnd: int) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ''
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ''
    try:
        size = wintypes.DWORD(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return ''
    finally:
        kernel32.CloseHandle(handle)


def window_text(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def window_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetClassNameW(hwnd, buf, 512)
    return buf.value


def list_windows() -> list[dict]:
    """枚举可见顶层窗口（用于诊断/自动发现）。"""
    result: list[dict] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = window_text(hwnd)
        if not title:
            return True
        rect = RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        result.append({
            'hwnd': int(hwnd),
            'title': title,
            'class': window_class(hwnd),
            'exe': get_process_exe(hwnd),
            'client': (rect.right - rect.left, rect.bottom - rect.top),
        })
        return True

    user32.EnumWindows(_cb, 0)
    return result


def find_window(title_keywords: Iterable[str] = ('明日方舟', 'Arknights'),
                exe_names: Iterable[str] = ('Arknights.exe',)) -> int | None:
    """按标题关键字/进程名查找游戏窗口，返回 HWND。"""
    enable_dpi_awareness()
    keywords = [k.lower() for k in title_keywords if k]
    exes = [e.lower() for e in exe_names if e]
    exact: list[tuple[int, int]] = []
    loose: list[tuple[int, int]] = []
    for info in list_windows():
        w, h = info['client']
        if w < 320 or h < 180:
            continue
        title = info['title'].lower()
        exe = info['exe'].lower()
        score = 0
        if any(title == k for k in keywords):
            score += 4
        elif any(k in title for k in keywords):
            score += 2
        if exe and any(exe.endswith(e) for e in exes):
            score += 3
        if score >= 4:
            exact.append((score, info['hwnd']))
        elif score > 0:
            loose.append((score, info['hwnd']))
    if exact:
        return max(exact)[1]
    if loose:
        return max(loose)[1]
    return None


@dataclass
class Win32Options:
    """截图/输入策略（默认值与 MAA 推荐的 PC 端组合一致）。"""

    screencap: str = 'printwindow'          # printwindow | gdi | screendc
    input: str = 'cursor'                   # cursor | post | send
    anchor_virtual: tuple[int, int] | None = (960, 540)
    parallax_wait: float = 0.20
    block_input: bool = False
    click_hold: float = 0.045
    move_step_delay: float = 0.012
    popup_composite: bool = True


class Win32Device:
    """把官方 PC 端窗口包装成 1920x1080 虚拟设备。"""

    name = 'win32'

    def __init__(self, hwnd: int, options: Win32Options | None = None,
                 virtual_size: tuple[int, int] = (1920, 1080)):
        enable_dpi_awareness()
        if not hwnd:
            raise ValueError('无效的窗口句柄')
        self.hwnd = int(hwnd)
        self.options = options or Win32Options()
        self.virtual_w, self.virtual_h = virtual_size
        self._held = False
        self._cursor_moved_at = 0.0
        self._anchor_client: tuple[int, int] | None = None
        self._capture_method = self.options.screencap
        self._warned_minimized = False
        self._last_hash: int | None = None
        self.last_frame_info: dict = {}

    # -- 基础信息 ---------------------------------------------------------
    def title(self) -> str:
        return window_text(self.hwnd)

    def client_size(self) -> tuple[int, int]:
        rect = RECT()
        if not user32.GetClientRect(self.hwnd, ctypes.byref(rect)):
            raise RuntimeError('GetClientRect 失败')
        return rect.right - rect.left, rect.bottom - rect.top

    def describe(self) -> str:
        w, h = self.client_size()
        return (f'窗口「{self.title()}」 hwnd=0x{self.hwnd:X} 客户区={w}x{h} '
                f'截图={self._capture_method} 输入={self.options.input}')

    def is_minimized(self) -> bool:
        return bool(user32.IsIconic(self.hwnd))

    def ensure_ready(self) -> None:
        if not self.hwnd or not user32.IsWindow(self.hwnd):
            raise RuntimeError('游戏窗口已关闭')
        if self.is_minimized():
            raise RuntimeError('游戏窗口处于最小化状态：PrintWindow 无法可靠截图，请恢复窗口（可以放在后台或被遮挡，但不要最小化）')

    # -- 坐标映射 ---------------------------------------------------------
    def _scale(self) -> tuple[float, float, int, int]:
        return self._geometry()

    def _geometry(self) -> tuple[float, float, int, int]:
        """返回 (sx, sy, off_x, off_y)：虚拟坐标 → 客户区像素的映射参数。"""
        w, h = self.client_size()
        content_w, content_h = w, h
        off_x = off_y = 0
        # 非 16:9 时按比例居中，避免拉伸导致所有坐标漂移
        target = self.virtual_w / self.virtual_h
        actual = w / h if h else target
        if abs(actual - target) > 0.01:
            if actual > target:
                content_w = int(round(h * target))
                off_x = (w - content_w) // 2
            else:
                content_h = int(round(w / target))
                off_y = (h - content_h) // 2
        return content_w / self.virtual_w, content_h / self.virtual_h, off_x, off_y

    def virtual_to_client(self, x: float, y: float) -> tuple[int, int]:
        sx, sy, off_x, off_y = self._geometry()
        return int(round(off_x + x * sx)), int(round(off_y + y * sy))

    def client_to_screen(self, x: int, y: int) -> tuple[int, int]:
        pt = POINT(int(x), int(y))
        if not user32.ClientToScreen(self.hwnd, ctypes.byref(pt)):
            raise RuntimeError('ClientToScreen 失败')
        return pt.x, pt.y

    # -- 截图 -------------------------------------------------------------
    def _capture_printwindow(self, hwnd: int) -> np.ndarray | None:
        rect = RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        w, h = rect.right - rect.left, rect.bottom - rect.top
        if w <= 0 or h <= 0:
            return None
        hdc = user32.GetDC(hwnd)
        if not hdc:
            return None
        mem_dc = gdi32.CreateCompatibleDC(hdc)
        bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
        old = gdi32.SelectObject(mem_dc, bmp)
        try:
            ok = user32.PrintWindow(hwnd, mem_dc, PW_CLIENTONLY | PW_RENDERFULLCONTENT)
            if not ok:
                return None
            return self._read_bitmap(mem_dc, bmp, w, h)
        finally:
            if old:
                gdi32.SelectObject(mem_dc, old)
            if bmp:
                gdi32.DeleteObject(bmp)
            if mem_dc:
                gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hwnd, hdc)

    def _capture_gdi(self, hwnd: int) -> np.ndarray | None:
        rect = RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        w, h = rect.right - rect.left, rect.bottom - rect.top
        if w <= 0 or h <= 0:
            return None
        hdc = user32.GetDC(hwnd)
        if not hdc:
            return None
        mem_dc = gdi32.CreateCompatibleDC(hdc)
        bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
        old = gdi32.SelectObject(mem_dc, bmp)
        try:
            if not gdi32.BitBlt(mem_dc, 0, 0, w, h, hdc, 0, 0, SRCCOPY | CAPTUREBLT):
                return None
            return self._read_bitmap(mem_dc, bmp, w, h)
        finally:
            if old:
                gdi32.SelectObject(mem_dc, old)
            if bmp:
                gdi32.DeleteObject(bmp)
            if mem_dc:
                gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(hwnd, hdc)

    def _capture_screendc(self, hwnd: int) -> np.ndarray | None:
        rect = RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        w, h = rect.right - rect.left, rect.bottom - rect.top
        origin = POINT(0, 0)
        if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
            return None
        screen_dc = user32.GetDC(0)
        mem_dc = gdi32.CreateCompatibleDC(screen_dc)
        bmp = gdi32.CreateCompatibleBitmap(screen_dc, w, h)
        old = gdi32.SelectObject(mem_dc, bmp)
        try:
            if not gdi32.BitBlt(mem_dc, 0, 0, w, h, screen_dc, origin.x, origin.y,
                                SRCCOPY | CAPTUREBLT):
                return None
            return self._read_bitmap(mem_dc, bmp, w, h)
        finally:
            if old:
                gdi32.SelectObject(mem_dc, old)
            if bmp:
                gdi32.DeleteObject(bmp)
            if mem_dc:
                gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(0, screen_dc)

    @staticmethod
    def _read_bitmap(mem_dc: int, bmp: int, w: int, h: int) -> np.ndarray | None:
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buf = (ctypes.c_ubyte * (w * h * 4))()
        if not gdi32.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS):
            return None
        arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)
        return np.ascontiguousarray(arr[:, :, :3])

    @staticmethod
    def _is_blank(img: np.ndarray | None) -> bool:
        if img is None or img.size == 0:
            return True
        return float(img.mean()) < 2.0 and float(img.std()) < 2.0

    def _compose_popup(self, image: np.ndarray) -> np.ndarray:
        """把当前活动弹窗叠加到主窗口画面上（公告/确认框是独立顶层窗口）。"""
        root = user32.GetAncestor(self.hwnd, GA_ROOTOWNER) or self.hwnd
        popup = user32.GetLastActivePopup(root)
        if not popup or popup == self.hwnd or popup == root:
            return image
        if not user32.IsWindowVisible(popup):
            return image
        popup_img = self._capture_printwindow(popup)
        if popup_img is None or popup_img.size == 0:
            return image
        main_origin = POINT(0, 0)
        popup_origin = POINT(0, 0)
        if not user32.ClientToScreen(self.hwnd, ctypes.byref(main_origin)):
            return image
        if not user32.ClientToScreen(popup, ctypes.byref(popup_origin)):
            return image
        ox = popup_origin.x - main_origin.x
        oy = popup_origin.y - main_origin.y
        ph, pw = popup_img.shape[:2]
        h, w = image.shape[:2]
        x1, y1 = max(0, ox), max(0, oy)
        x2, y2 = min(w, ox + pw), min(h, oy + ph)
        if x1 >= x2 or y1 >= y2:
            return image
        out = image.copy()
        out[y1:y2, x1:x2] = popup_img[y1 - oy:y2 - oy, x1 - ox:x2 - ox]
        return out

    def _grab(self, method: str) -> np.ndarray | None:
        if method == 'printwindow':
            return self._capture_printwindow(self.hwnd)
        if method == 'gdi':
            return self._capture_gdi(self.hwnd)
        if method == 'screendc':
            return self._capture_screendc(self.hwnd)
        return None

    @staticmethod
    def _frame_hash(img: np.ndarray) -> int:
        """快速指纹：缩小到 32x18 灰度后哈希，用于发现"画面卡住不动"。"""
        small = cv2.resize(img, (32, 18), interpolation=cv2.INTER_AREA)
        return hash(small.tobytes())

    def capture(self) -> np.ndarray:
        """抓取客户区画面（原始像素，BGR）。

        某些 Unity/D3D 窗口在切换场景后会长期返回**陈旧的缓存帧**（例如一直停在加载 logo），
        因此这里做了两件事：
          1. 首选截图方式不固定：一旦发现连续多帧完全相同，就用其它方式再抓一次，
             谁给出不同的画面就切到谁；
          2. 记录 `last_frame_info`（方式/尺寸/是否疑似陈旧），便于日志排查。
        """
        self.ensure_ready()
        self._ensure_parked()
        preferred = self.options.screencap
        order = [self._capture_method] + [m for m in (preferred, 'printwindow', 'gdi', 'screendc')
                                          if m != self._capture_method]
        last_error = None
        first = None
        for method in order:
            try:
                img = self._grab(method)
            except OSError as exc:      # ctypes 调用异常
                last_error = exc
                img = None
            if self._is_blank(img):
                continue
            if first is None:
                first = (method, img)
            # 与上一帧完全相同：先记下来，继续用其它方式尝试，看是否有更新的画面
            if self._last_hash is not None and self._frame_hash(img) == self._last_hash:
                continue
            return self._finish(method, img)
        if first is not None:
            return self._finish(first[0], first[1], stale=True)
        raise RuntimeError(f'截图失败（尝试过 {order}）: {last_error or "返回黑图"}')

    def _finish(self, method: str, img: np.ndarray, stale: bool = False) -> np.ndarray:
        if method != self._capture_method:
            self._capture_method = method
        frame = img
        if self.options.popup_composite:
            try:
                frame = self._compose_popup(frame)
            except Exception:
                frame = img
        self._last_hash = self._frame_hash(frame)
        self.last_frame_info = {'method': method, 'size': frame.shape[:2], 'stale': stale}
        return frame

    def shot(self) -> np.ndarray:
        """返回 1920x1080 虚拟画面的 BGR 图（非 16:9 时裁掉留边，保证与点击坐标一致）。"""
        frame = self.capture()
        h, w = frame.shape[:2]
        target = self.virtual_w / self.virtual_h
        if abs(w / h - target) > 0.01:
            if w / h > target:
                content_w = int(round(h * target))
                off_x = (w - content_w) // 2
                frame = frame[:, off_x:off_x + content_w]
            else:
                content_h = int(round(w / target))
                off_y = (h - content_h) // 2
                frame = frame[off_y:off_y + content_h, :]
            h, w = frame.shape[:2]
        if (w, h) != (self.virtual_w, self.virtual_h):
            frame = cv2.resize(frame, (self.virtual_w, self.virtual_h),
                               interpolation=cv2.INTER_AREA if w > self.virtual_w else cv2.INTER_LINEAR)
        return frame

    # -- 鼠标 -------------------------------------------------------------
    def _send(self, message: int, wparam: int, lparam: int) -> None:
        if self.options.input in ('post', 'cursor'):
            user32.PostMessageW(self.hwnd, message, wparam, lparam)
        else:
            user32.SendMessageW(self.hwnd, message, wparam, lparam)

    def _activate(self) -> None:
        self._send(WM_ACTIVATE, WA_ACTIVE, 0)
        time.sleep(0.01)

    def _anchor_pos(self) -> tuple[int, int]:
        if self._anchor_client is None:
            anchor = self.options.anchor_virtual
            if anchor is None:
                w, h = self.client_size()
                self._anchor_client = (w // 2, h // 2)
            else:
                self._anchor_client = self.virtual_to_client(*anchor)
        return self._anchor_client

    def _park(self) -> None:
        if self.options.input != 'cursor':
            return
        try:
            x, y = self._anchor_pos()
            sx, sy = self.client_to_screen(x, y)
            if user32.SetCursorPos(sx, sy):
                self._cursor_moved_at = time.monotonic()
        except OSError:
            pass

    def _ensure_parked(self) -> None:
        if self.options.input != 'cursor':
            return
        x, y = self._anchor_pos()
        sx, sy = self.client_to_screen(x, y)
        pt = POINT()
        if not user32.GetCursorPos(ctypes.byref(pt)) or (pt.x, pt.y) != (sx, sy):
            self._park()
        elapsed = time.monotonic() - self._cursor_moved_at
        if elapsed < self.options.parallax_wait:
            time.sleep(self.options.parallax_wait - elapsed)

    def _move_cursor(self, cx: int, cy: int) -> None:
        if self.options.input != 'cursor':
            return
        sx, sy = self.client_to_screen(cx, cy)
        user32.SetCursorPos(sx, sy)
        self._cursor_moved_at = time.monotonic()
        time.sleep(0.004)

    def _block(self) -> None:
        if self.options.block_input:
            try:
                user32.BlockInput(True)
            except OSError:
                pass

    def _unblock(self) -> None:
        if self.options.block_input:
            try:
                user32.BlockInput(False)
            except OSError:
                pass

    def tap(self, x: float, y: float, wait: float = 0.6) -> None:
        cx, cy = self.virtual_to_client(x, y)
        lp = _makelparam(cx, cy)
        self._activate()
        self._block()
        try:
            self._move_cursor(cx, cy)
            self._send(WM_MOUSEMOVE, MK_LBUTTON, lp)
            time.sleep(0.01)
            self._send(WM_LBUTTONDOWN, MK_LBUTTON, lp)
            time.sleep(self.options.click_hold)
            self._send(WM_LBUTTONUP, 0, lp)
        finally:
            self._unblock()
        self._held = False
        self._park()
        if wait:
            time.sleep(wait)

    def touch(self, kind: str, x: float, y: float) -> None:
        kind = str(kind).upper()
        cx, cy = self.virtual_to_client(x, y)
        lp = _makelparam(cx, cy)
        if kind == 'DOWN':
            if self._held:
                self.touch('UP', x, y)
            self._activate()
            self._block()
            self._move_cursor(cx, cy)
            self._send(WM_MOUSEMOVE, MK_LBUTTON, lp)
            time.sleep(0.01)
            self._send(WM_LBUTTONDOWN, MK_LBUTTON, lp)
            self._held = True
        elif kind == 'MOVE':
            if not self._held:
                raise RuntimeError('MOVE 之前没有 DOWN')
            self._move_cursor(cx, cy)
            self._send(WM_MOUSEMOVE, MK_LBUTTON, lp)
            # 拖拽路径是逐步 MOVE 的，需要给游戏渲染线程留出处理时间
            time.sleep(max(0.006, self.options.move_step_delay))
        elif kind == 'UP':
            if self._held:
                self._send(WM_LBUTTONUP, 0, lp)
                self._held = False
                self._unblock()
                self._park()
        else:
            raise ValueError(f'未知触控事件: {kind}')

    def swipe(self, x1: float, y1: float, x2: float, y2: float,
              ms: int = 500, wait: float = 0.8) -> None:
        ms = max(60, int(ms))
        steps = max(4, min(40, int(ms / 40)))
        self.touch('DOWN', x1, y1)
        try:
            for i in range(1, steps + 1):
                px = x1 + (x2 - x1) * i / steps
                py = y1 + (y2 - y1) * i / steps
                self.touch('MOVE', px, py)
                time.sleep(max(0.008, ms / 1000.0 / steps))
        finally:
            self.touch('UP', x2, y2)
        if wait:
            time.sleep(wait)

    def close(self) -> None:
        if self._held:
            try:
                self.touch('UP', 0, 0)
            except Exception:
                self._held = False
        self._unblock()
