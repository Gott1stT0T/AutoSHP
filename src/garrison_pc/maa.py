"""MAA（MaaAssistantArknights）集成。

职责：
  * 定位本机 MAA 安装目录（显式参数 / 设置文件 / 正在运行的进程 / 常见安装位置）；
  * 读取 MAA 的连接配置（v6.x 的 ``config/gui.new.json``，兼容旧 ``gui.json``）；
  * 读取 PC 端的窗口截图/输入方式（``Extras.Win32Extra``）与 PC 客户端路径；
  * 定位 MAA 自带的 PaddleOCR 模型（``resource/PaddleOCR``）。

本模块对 MAA 目录**只读**，不写任何文件。
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

MAA_EXE_NAMES = ('MAA.exe', 'MaaAssistantArknights.exe', 'MaaWpfGui.exe')
#: 找不到显式路径时试探的常见安装目录（相对盘符）
MAA_DIR_HINTS = (
    'MAA',
    'MaaAssistantArknights',
    'Program Files/MAA',
    'Program Files/MaaAssistantArknights',
    'Program Files (x86)/MAA',
    'Tools/MAA',
    'Software/MAA',
    'Games/MAA',
)

CREATE_NO_WINDOW = 0x08000000


@dataclass
class MaaConnection:
    """MAA 连接设置的一个快照。"""

    config: str = ''
    adb_path: str = ''
    address: str = ''
    client_type: str = 'Official'
    win32: dict[str, Any] = field(default_factory=dict)
    pc_client_path: str = ''
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def is_pc(self) -> bool:
        return str(self.config).upper() == 'PC'


@dataclass
class MaaInfo:
    root: Path
    config_file: Path | None
    connection: MaaConnection
    ocr_dir: Path | None
    raw_config: dict[str, Any] = field(default_factory=dict)

    @property
    def version_hint(self) -> str:
        return str(self.raw_config.get('Update', {}).get('Name', '') or '')


# ---------------------------------------------------------------------------
# 目录/进程探测
# ---------------------------------------------------------------------------
def is_maa_dir(path: str | os.PathLike) -> bool:
    p = Path(path)
    if not p.is_dir():
        return False
    if (p / 'resource' / 'version.json').is_file():
        return True
    if (p / 'config' / 'gui.new.json').is_file():
        return True
    if any((p / name).is_file() for name in MAA_EXE_NAMES):
        return True
    return False


def _query_process_paths(names: Iterable[str]) -> list[str]:
    """通过 Win32 API 取指定进程名的可执行文件路径（不依赖 psutil/wmic）。"""
    if os.name != 'nt':
        return []
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_VM_READ = 0x0010

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    psapi.EnumProcesses.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD,
                                    ctypes.POINTER(wintypes.DWORD)]
    psapi.EnumProcesses.restype = wintypes.BOOL

    wanted = {n.lower() for n in names}
    count = 4096
    while True:
        buf = (wintypes.DWORD * count)()
        needed = wintypes.DWORD()
        if not psapi.EnumProcesses(buf, ctypes.sizeof(buf), ctypes.byref(needed)):
            return []
        got = needed.value // ctypes.sizeof(wintypes.DWORD)
        if got < count:
            break
        count *= 2

    found: list[str] = []
    for i in range(got):
        pid = buf[i]
        if not pid:
            continue
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            handle = kernel32.OpenProcess(PROCESS_VM_READ, False, pid)
        if not handle:
            continue
        try:
            size = wintypes.DWORD(32768)
            path_buf = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, path_buf, ctypes.byref(size)):
                path = path_buf.value
                if os.path.basename(path).lower() in wanted:
                    found.append(path)
        finally:
            kernel32.CloseHandle(handle)
    return found


def running_maa_paths() -> list[str]:
    exe_paths = _query_process_paths(MAA_EXE_NAMES)
    dirs: list[str] = []
    for exe in exe_paths:
        d = os.path.dirname(exe)
        if is_maa_dir(d) and d not in dirs:
            dirs.append(d)
    return dirs


def find_maa(explicit: str = '', settings_hint: str = '') -> Path | None:
    """按优先级定位 MAA 目录；找不到返回 None。"""
    for candidate in (explicit, settings_hint):
        if candidate and is_maa_dir(candidate):
            return Path(candidate).resolve()

    for candidate in running_maa_paths():
        return Path(candidate).resolve()

    # 盘符 + 常见目录的浅层扫描（最多 3 层）
    drives = [f'{chr(c)}:/' for c in range(ord('C'), ord('K') + 1) if os.path.exists(f'{chr(c)}:/')]
    for drive in drives:
        for hint in MAA_DIR_HINTS:
            p = Path(drive) / hint
            if is_maa_dir(p):
                return p.resolve()
    for drive in drives:
        try:
            entries = list(os.scandir(drive))
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name.lower().startswith(('maa', 'maaassistant')):
                if is_maa_dir(entry.path):
                    return Path(entry.path).resolve()
            try:
                for sub in os.scandir(entry.path):
                    if not sub.is_dir():
                        continue
                    if sub.name.lower().startswith(('maa', 'maaassistant')) and is_maa_dir(sub.path):
                        return Path(sub.path).resolve()
            except OSError:
                continue
    return None


# ---------------------------------------------------------------------------
# 配置解析
# ---------------------------------------------------------------------------
def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)


def _first_dict_with(d: dict[str, Any], key: str, depth: int = 4) -> dict[str, Any] | None:
    """在嵌套字典里找第一个含 key 的字典（MAA 配置结构跨版本有差异）。"""
    if not isinstance(d, dict) or depth < 0:
        return None
    if isinstance(d.get(key), dict):
        return d[key]
    for value in d.values():
        if isinstance(value, dict):
            found = _first_dict_with(value, key, depth - 1)
            if found is not None:
                return found
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    found = _first_dict_with(item, key, depth - 1)
                    if found is not None:
                        return found
    return None


def _json_object(root: dict[str, Any]) -> dict[str, Any]:
    """gui.new.json 里当前生效的配置（``Configurations`` + ``Current``）。"""
    configs = root.get('Configurations')
    if isinstance(configs, dict) and configs:
        current = str(root.get('Current') or '')
        if current and isinstance(configs.get(current), dict):
            return configs[current]
        for value in configs.values():
            if isinstance(value, dict):
                return value
    return root


def parse_connection(root: dict[str, Any]) -> MaaConnection:
    obj = _json_object(root)
    connect = _first_dict_with(obj, 'ConnectSettings') or _first_dict_with(root, 'ConnectSettings') or {}
    runtime = _first_dict_with(obj, 'RuntimeSettings') or _first_dict_with(root, 'RuntimeSettings') or {}
    startup = _first_dict_with(obj, 'StartUpSettings') or _first_dict_with(root, 'StartUpSettings') or {}
    extras = connect.get('Extras') if isinstance(connect.get('Extras'), dict) else {}
    win32 = extras.get('Win32Extra') if isinstance(extras.get('Win32Extra'), dict) else {}
    return MaaConnection(
        config=str(connect.get('Config') or ''),
        adb_path=str(connect.get('AdbPath') or ''),
        address=str(connect.get('Address') or ''),
        client_type=str(runtime.get('ClientType') or 'Official'),
        win32=dict(win32),
        pc_client_path=str(startup.get('PcClientPath') or ''),
        extras=dict(extras),
    )


def load_maa(explicit: str = '', settings_hint: str = '') -> MaaInfo | None:
    root = find_maa(explicit, settings_hint)
    if root is None:
        return None
    config_file = root / 'config' / 'gui.new.json'
    if not config_file.is_file():
        config_file = root / 'config' / 'gui.json'
    raw: dict[str, Any] = {}
    if config_file.is_file():
        try:
            raw = _load_json(config_file)
        except (OSError, ValueError):
            raw = {}
    ocr_dir = root / 'resource' / 'PaddleOCR'
    if not (ocr_dir / 'det' / 'inference.onnx').is_file():
        ocr_dir = None
    return MaaInfo(root=root, config_file=config_file if config_file.is_file() else None,
                   connection=parse_connection(raw) if raw else MaaConnection(),
                   ocr_dir=ocr_dir, raw_config=raw)


# ---------------------------------------------------------------------------
# PaddleOCR 模型
# ---------------------------------------------------------------------------
@dataclass
class OcrModelPaths:
    det: Path
    rec: Path
    keys: Path

    def exists(self) -> bool:
        return all(p.is_file() for p in (self.det, self.rec, self.keys))

    def describe(self) -> str:
        return f'det={self.det} rec={self.rec} keys={self.keys}'


def find_ocr_models(maa_dir: str | os.PathLike | None, extra_dirs: Iterable[str] = ()) -> OcrModelPaths | None:
    """在 MAA 目录、PaddleOCR 目录或额外目录里寻找 det/rec/keys 三件套。"""
    roots: list[Path] = []
    if maa_dir:
        p = Path(maa_dir)
        roots.extend([p, p / 'resource' / 'PaddleOCR', p / 'PaddleOCR'])
    for d in extra_dirs:
        if d:
            p = Path(d)
            roots.extend([p, p / 'resource' / 'PaddleOCR', p / 'PaddleOCR'])
    for base in roots:
        paths = OcrModelPaths(
            det=base / 'det' / 'inference.onnx',
            rec=base / 'rec' / 'inference.onnx',
            keys=base / 'rec' / 'keys.txt',
        )
        if paths.exists():
            return paths
    return None


# ---------------------------------------------------------------------------
# 鹰角启动器 / PC 客户端
# ---------------------------------------------------------------------------
LAUNCHER_EXE_NAMES = ('Games.exe', 'Launcher.exe')
GAME_EXE_NAMES = ('Arknights.exe',)


def _registry_launcher_dirs() -> list[str]:
    dirs: list[str] = []
    if os.name != 'nt':
        return dirs
    try:
        import winreg
    except ImportError:
        return dirs
    roots = (
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'),
        (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
    )
    for hive, sub in roots:
        try:
            with winreg.OpenKey(hive, sub) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        name = winreg.EnumKey(key, index)
                        with winreg.OpenKey(key, name) as entry:
                            try:
                                display = str(winreg.QueryValueEx(entry, 'DisplayName')[0])
                                location = str(winreg.QueryValueEx(entry, 'InstallLocation')[0])
                            except OSError:
                                continue
                    except OSError:
                        continue
                    if not location:
                        continue
                    if 'Hypergryph' in display or '鹰角' in display or 'Arknights' in display:
                        if location not in dirs:
                            dirs.append(location)
        except OSError:
            continue
    return dirs


def find_launcher(explicit: str = '', game_path: str = '') -> Path | None:
    """定位鹰角启动器可执行文件。

    官方 PC 端自 2026 年底起校验父进程必须是启动器，因此必须由启动器拉起游戏。
    """
    if explicit and Path(explicit).is_file():
        return Path(explicit).resolve()
    candidates: list[Path] = []
    if game_path:
        p = Path(game_path)
        for parent in [p] + list(p.parents)[:5]:
            for name in LAUNCHER_EXE_NAMES:
                candidates.append(parent / name)
    for d in _registry_launcher_dirs():
        base = Path(d)
        for rel in ('Launcher.exe', 'Games.exe', '1.6.0/Games.exe', '1.6.0/Launcher.exe',
                    'Hypergryph Launcher/Launcher.exe', 'Hypergryph Launcher/Games.exe'):
            candidates.append(base / rel)
    for c in candidates:
        if c.is_file():
            return c.resolve()
    return None


def find_game(game_path: str = '') -> Path | None:
    """定位 Arknights.exe（仅用于识别安装位置，不作为启动入口）。"""
    if game_path:
        p = Path(game_path)
        if p.is_file() and p.suffix.lower() == '.exe':
            return p.resolve()
        if p.is_dir():
            for name in GAME_EXE_NAMES:
                for sub in ('', 'Arknights Game', 'games/Arknights', 'games/Arknights Game'):
                    q = (p / sub / name) if sub else (p / name)
                    if q.is_file():
                        return q.resolve()
    launcher = find_launcher('', game_path)
    if launcher:
        base = launcher.parent if launcher.parent.name.lower() != 'games' else launcher.parent.parent
        for rel in ('games/Arknights/Arknights.exe', 'games/Arknights Game/Arknights.exe',
                    'games/Arknights/Arknights Game/Arknights.exe'):
            q = base / rel
            if q.is_file():
                return q.resolve()
    return None


# ---------------------------------------------------------------------------
# 进程状态（用于"不要和 MAA 任务并发"的提醒）
# ---------------------------------------------------------------------------
def maa_running() -> bool:
    return bool(_query_process_paths(MAA_EXE_NAMES))


def game_running() -> bool:
    return bool(_query_process_paths(GAME_EXE_NAMES))


def launch(path: str | os.PathLike, workdir: str | os.PathLike | None = None) -> None:
    """以普通权限启动一个 exe（不抢占前台）。"""
    args = [str(path)]
    kwargs: dict[str, Any] = {'close_fds': True}
    if workdir:
        kwargs['cwd'] = str(workdir)
    if os.name == 'nt':
        kwargs['creationflags'] = CREATE_NO_WINDOW
    subprocess.Popen(args, **kwargs)
