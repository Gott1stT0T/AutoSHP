"""一个极简 Win32 测试窗口，用于验证设备层（截图 + 消息注入）。

窗口行为：
  * 客户区 960x540，画出网格；
  * 收到 WM_LBUTTONDOWN / WM_MOUSEMOVE(左键按下) / WM_LBUTTONUP 时记录事件，
    并立即把事件列表写入 ``--events`` 指定的 JSON 文件；
  * 点击位置画一个红点，便于截图验证。

用法：
    python win32_test_window.py --events C:\\temp\\events.json [--seconds 60]
"""
import argparse
import ctypes
import json
import time
import traceback
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)

# 64 位下必须显式声明原型，否则句柄会被截断
user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
user32.RegisterClassExW.restype = wintypes.WORD
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                   wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                   wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.BeginPaint.restype = wintypes.HDC
user32.EndPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.HBRUSH]
user32.FillRect.restype = ctypes.c_int
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT), wintypes.BOOL]
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadCursorW.restype = wintypes.HANDLE
user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
gdi32.CreateSolidBrush.argtypes = [wintypes.DWORD]
gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.DWORD]
gdi32.CreatePen.restype = wintypes.HPEN
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.MoveToEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.LPVOID]
gdi32.LineTo.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
WM_PAINT = 0x000F
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_MOUSEMOVE = 0x0200
MK_LBUTTON = 0x0001
CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_VISIBLE = 0x10000000
COLOR_WINDOW = 5
IDC_ARROW = 32512

events: list[dict] = []
events_path = ''
dots: list[tuple[int, int]] = []


class WNDCLASSEX(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.UINT), ('style', wintypes.UINT),
        ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int), ('hInstance', wintypes.HINSTANCE),
        ('hIcon', wintypes.HICON), ('hCursor', wintypes.HANDLE),
        ('hbrBackground', wintypes.HBRUSH), ('lpszMenuName', wintypes.LPCWSTR),
        ('lpszClassName', wintypes.LPCWSTR), ('hIconSm', wintypes.HICON),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [('hdc', wintypes.HDC), ('fErase', wintypes.BOOL),
                ('rcPaint', wintypes.RECT), ('fRestore', wintypes.BOOL),
                ('fIncUpdate', wintypes.BOOL), ('rgbReserved', ctypes.c_byte * 32)]


def flush() -> None:
    if not events_path:
        return
    try:
        with open(events_path, 'w', encoding='utf-8') as f:
            json.dump({'events': events, 'dots': dots}, f)
    except OSError:
        pass


def _draw(hwnd: int, hdc: int) -> None:
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    w, h = rect.right, rect.bottom
    brush = gdi32.CreateSolidBrush(0x00202020)
    user32.FillRect(hdc, ctypes.byref(rect), brush)
    gdi32.DeleteObject(brush)
    pen = gdi32.CreatePen(0, 1, 0x00606060)
    old = gdi32.SelectObject(hdc, pen)
    for x in range(0, w, 120):
        gdi32.MoveToEx(hdc, x, 0, None)
        gdi32.LineTo(hdc, x, h)
    for y in range(0, h, 90):
        gdi32.MoveToEx(hdc, 0, y, None)
        gdi32.LineTo(hdc, w, y)
    gdi32.SelectObject(hdc, old)
    gdi32.DeleteObject(pen)
    brush = gdi32.CreateSolidBrush(0x000000FF)
    for (x, y) in dots:
        dot = wintypes.RECT(x - 6, y - 6, x + 6, y + 6)
        user32.FillRect(hdc, ctypes.byref(dot), brush)
    gdi32.DeleteObject(brush)


def wndproc(hwnd, msg, wparam, lparam):
    try:
        return _wndproc(hwnd, msg, wparam, lparam)
    except Exception as exc:      # ctypes 回调里抛异常会静默丢消息，必须自己打印
        traceback.print_exc()
        print('WM ERROR', hex(msg), exc, flush=True)
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def _wndproc(hwnd, msg, wparam, lparam):
    if msg == WM_PAINT:
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        _draw(hwnd, hdc)
        user32.EndPaint(hwnd, ctypes.byref(ps))
        return 0
    if msg in (WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEMOVE):
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        if msg == WM_MOUSEMOVE and not (wparam & MK_LBUTTON):
            return 0
        events.append({'msg': hex(msg), 'x': x, 'y': y, 'wparam': int(wparam)})
        if msg == WM_LBUTTONDOWN:
            dots.append((x, y))
            flush()
        elif msg == WM_LBUTTONUP:
            flush()
        user32.InvalidateRect(hwnd, None, False)
        return 0
    if msg == WM_CLOSE:
        user32.DestroyWindow(hwnd)
        return 0
    if msg == WM_DESTROY:
        flush()
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def main() -> None:
    global events_path
    parser = argparse.ArgumentParser()
    parser.add_argument('--events', default='events.json')
    parser.add_argument('--title', default='GFPCTestWindow')
    parser.add_argument('--seconds', type=float, default=120)
    args = parser.parse_args()
    events_path = args.events
    flush()

    # 与真实游戏一样声明 DPI 感知，否则客户区/消息坐标会出现 1.25/1.5 倍虚拟化
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    hinstance = kernel32.GetModuleHandleW(None)
    proc = WNDPROC(wndproc)
    cls = WNDCLASSEX()
    cls.cbSize = ctypes.sizeof(WNDCLASSEX)
    cls.style = CS_HREDRAW | CS_VREDRAW
    cls.lpfnWndProc = proc
    cls.hInstance = hinstance
    cls.hCursor = user32.LoadCursorW(None, IDC_ARROW)
    cls.hbrBackground = COLOR_WINDOW + 1
    cls.lpszClassName = 'GFPCTestWindowClass'
    if not user32.RegisterClassExW(ctypes.byref(cls)):
        raise ctypes.WinError(ctypes.get_last_error())

    hwnd = user32.CreateWindowExW(0, 'GFPCTestWindowClass', args.title,
                                  WS_OVERLAPPEDWINDOW | WS_VISIBLE,
                                  100, 100, 976, 579, None, None, hinstance, None)
    if not hwnd:
        raise ctypes.WinError(ctypes.get_last_error())
    print('READY', hwnd, flush=True)

    deadline = time.time() + args.seconds
    msg = wintypes.MSG()
    while time.time() < deadline:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            if msg.message in (0x0012,):      # WM_QUIT
                return
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.01)
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


if __name__ == '__main__':
    main()
