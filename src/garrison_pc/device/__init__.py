"""设备层工厂：按配置在 Win32（官方 PC 端）与 ADB（模拟器）之间选择。"""
from __future__ import annotations

import subprocess
from typing import Any

from .adb import AdbDevice, find_adb
from .win32 import Win32Device, Win32Options, find_window, list_windows

CREATE_NO_WINDOW = 0x08000000


class DeviceError(RuntimeError):
    pass


def _adb_devices(adb_path: str) -> list[str]:
    try:
        out = subprocess.run([adb_path, 'devices'], capture_output=True,
                             creationflags=CREATE_NO_WINDOW, timeout=15).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    devices = []
    for line in out.decode('utf-8', 'replace').splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == 'device':
            devices.append(parts[0])
    return devices


def _create_adb(settings: Any, maa: Any, log) -> AdbDevice:
    candidates = [settings.get('adb', '')]
    if maa is not None:
        candidates.append(maa.connection.adb_path)
        candidates.append(str(maa.root / 'adb.exe'))
        candidates.append(str(maa.root / 'externals' / 'adb' / 'adb.exe'))
    adb_path = find_adb(candidates) or ''
    if not adb_path:
        raise DeviceError('找不到 adb.exe：请在 MAA 的连接设置里配置，或在 settings.json 里填写 "adb"')

    address = settings.get('address', '') or (maa.connection.address if maa else '')
    devices = _adb_devices(adb_path)
    if address and address not in devices:
        try:
            subprocess.run([adb_path, 'connect', address], capture_output=True,
                           creationflags=CREATE_NO_WINDOW, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            pass
        devices = _adb_devices(adb_path)
    if not address:
        if len(devices) == 1:
            address = devices[0]
        elif devices:
            raise DeviceError('检测到多台设备，请在 settings.json 里指定 "address"：' + ', '.join(devices))
        else:
            raise DeviceError('没有在线的 adb 设备：请先启动模拟器，或在 MAA 中连接一次')
    if devices and address not in devices:
        raise DeviceError(f'adb 设备 {address} 不在线（当前：{", ".join(devices) or "无"}）')
    log(f'[设备] 使用 ADB：{adb_path} {address}')
    return AdbDevice(adb_path, address)


def create_device(settings: Any, maa: Any, log=print) -> Any:
    """按配置创建设备；auto 时优先官方 PC 端窗口，其次 ADB。"""
    mode = str(settings.get('device', 'auto') or 'auto').lower()
    titles = settings.get('window_title') or ['明日方舟', 'Arknights']
    exe = settings.get('game_exe') or 'Arknights.exe'

    if mode in ('win32', 'auto'):
        hwnd = find_window(titles, (exe,))
        if hwnd:
            opts = Win32Options(
                screencap=str(settings.win32.get('screencap', 'printwindow')),
                input=str(settings.win32.get('input', 'cursor')),
                anchor_virtual=tuple(settings.win32['anchor']) if settings.win32.get('anchor') else None,
                parallax_wait=float(settings.win32.get('parallax_wait', 0.20)),
                block_input=bool(settings.win32.get('block_input', False)),
                click_hold=float(settings.win32.get('click_hold', 0.045)),
                move_step_delay=float(settings.win32.get('move_step_delay', 0.012)),
                popup_composite=bool(settings.win32.get('popup_composite', True)),
            )
            device = Win32Device(hwnd, opts)
            log(f'[设备] 使用官方 PC 端窗口：{device.describe()}')
            return device
        if mode == 'win32':
            raise DeviceError('没有找到《明日方舟》PC 端窗口（标题需包含：'
                              + '/'.join(titles) + '）；请先通过鹰角启动器进入游戏')

    if mode in ('adb', 'auto'):
        # 只有 MAA 明确配置为 ADB 模式、或 auto 下找不到 PC 窗口时才走 ADB
        try:
            return _create_adb(settings, maa, log)
        except DeviceError as exc:
            if mode == 'adb':
                raise
            raise DeviceError(f'{exc}；也没有找到《明日方舟》PC 端窗口') from exc

    raise DeviceError(f'未知 device 配置：{mode}')


def diagnose_windows() -> list[dict]:
    return list_windows()
