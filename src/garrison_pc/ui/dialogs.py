"""Windows 对话框与终端辅助。"""
from __future__ import annotations

import os

MB_OK = 0x00000000
MB_ICONERROR = 0x00000010
MB_ICONWARNING = 0x00000030
MB_ICONINFORMATION = 0x00000040
MB_SETFOREGROUND = 0x00010000


def message_box(text: str, title: str = 'GarrisonFarm PC', flags: int = MB_OK | MB_ICONINFORMATION) -> None:
    # 便于自动化/测试：GFPC_NO_DIALOG=1 时只打印，不弹窗阻塞
    if os.environ.get('GFPC_NO_DIALOG'):
        print(f'[{title}] {text}', flush=True)
        return
    if os.name != 'nt':
        print(f'[{title}] {text}')
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title, flags | MB_SETFOREGROUND)
    except Exception:
        print(f'[{title}] {text}')


def info(text: str, title: str = 'GarrisonFarm PC') -> None:
    message_box(text, title, MB_OK | MB_ICONINFORMATION)


def warn(text: str, title: str = 'GarrisonFarm PC') -> None:
    message_box(text, title, MB_OK | MB_ICONWARNING)


def error(text: str, title: str = 'GarrisonFarm PC') -> None:
    message_box(text, title, MB_OK | MB_ICONERROR)


def clear_screen() -> None:
    if os.name == 'nt':
        os.system('')
