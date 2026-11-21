"""检查自身与游戏进程的完整性级别（判断是否需要管理员权限）。"""
import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.device.win32 import find_window, get_process_exe, user32  # noqa: E402

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)

TOKEN_QUERY = 0x0008
TokenIntegrityLevel = 25


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [('Sid', ctypes.c_void_p), ('Attributes', wintypes.DWORD)]


class TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = [('Label', SID_AND_ATTRIBUTES)]


def integrity(pid: int) -> str:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return f'OpenProcess failed {ctypes.get_last_error()}'
    try:
        token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(h, TOKEN_QUERY, ctypes.byref(token)):
            return f'OpenProcessToken failed {ctypes.get_last_error()}'
        try:
            size = wintypes.DWORD(0)
            advapi32.GetTokenInformation(token, TokenIntegrityLevel, None, 0, ctypes.byref(size))
            buf = ctypes.create_string_buffer(size.value)
            if not advapi32.GetTokenInformation(token, TokenIntegrityLevel, buf, size,
                                                ctypes.byref(size)):
                return f'GetTokenInformation failed {ctypes.get_last_error()}'
            label = ctypes.cast(buf, ctypes.POINTER(TOKEN_MANDATORY_LABEL)).contents
            sub = ctypes.cast(label.Label.Sid, ctypes.POINTER(ctypes.c_ubyte * 12)).contents
            rid = int.from_bytes(bytes(sub[8:12]), 'little')
            return {0x1000: 'Low', 0x2000: 'Medium', 0x2100: 'Medium+', 0x3000: 'High',
                    0x4000: 'System'}.get(rid, f'RID {rid:#x}')
        finally:
            kernel32.CloseHandle(token)
    finally:
        kernel32.CloseHandle(h)


def main() -> int:
    print('self pid', ctypes.windll.kernel32.GetCurrentProcessId() if hasattr(ctypes.windll.kernel32, 'GetCurrentProcessId') else '?')
    me = Path(sys.executable)
    print('self integrity:', integrity(ctypes.windll.kernel32.GetCurrentProcessId()))
    hwnd = find_window(['明日方舟', 'Arknights'], ('Arknights.exe',))
    if not hwnd:
        print('no game window')
        return 1
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    print('game hwnd', hex(hwnd), 'pid', pid.value, 'exe', get_process_exe(hwnd))
    print('game integrity:', integrity(pid.value))
    crect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(crect))
    print('client:', crect.right, crect.bottom)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
