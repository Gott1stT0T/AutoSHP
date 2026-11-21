"""应用配置：读写程序目录下的 ``settings.json``（默认值见 ``DEFAULTS``）。"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    # ---- 设备 ----
    'device': 'auto',                 # auto | win32 | adb
    'maa_dir': '',                    # 留空 = 自动查找
    'adb': '',                        # 留空 = 用 MAA 配置里的 adb
    'address': '',                    # 留空 = 用 MAA 配置里的地址
    'window_title': ['明日方舟', 'Arknights'],
    'game_exe': 'Arknights.exe',
    'launcher_path': '',              # 留空 = 自动查找鹰角启动器
    'pc_client_path': '',             # 留空 = 用 MAA 启动设置里的 PcClientPath / 自动查找
    'auto_launch': True,              # 找不到游戏窗口时自动拉起启动器
    'auto_elevate': True,             # 非管理员时自动请求以管理员身份重启（PC 端必需）
    'launch_timeout': 180,            # 等待游戏窗口出现的秒数    'launch_timeout': 180,            # 等待游戏窗口出现的秒数

    # ---- Win32 截图/输入 ----
    'win32': {
        'screencap': 'printwindow',   # printwindow | gdi | screendc
        'input': 'cursor',            # cursor | post | send
        'anchor': [960, 540],         # 鼠标停靠点（1920x1080 虚拟坐标），null=窗口中心
        'parallax_wait': 0.20,        # 光标移动后等待视差动画稳定的秒数
        'block_input': False,         # 手势期间是否锁定物理鼠标
        'click_hold': 0.045,
        'move_step_delay': 0.012,
        'popup_composite': True,
    },

    # ---- OCR ----
    'ocr_dir': '',                    # 留空 = 用 MAA 的 resource/PaddleOCR

    # ---- 运行 ----
    'log_dir': 'farm_logs',
    'done_file': 'strategies_done.json',
    'log_keep': 200,                  # farm_logs 里最多保留多少张截图
    'warn_if_maa_running': True,

    # ---- 坐标覆盖（适配官方 PC 端的 UI 差异；见 docs/01 与 docs/03 实测记录） ----
    # 例：{"GOLD_BOX": [1170, 20, 1265, 80], "CARD_X": [790, 1034, 1274, 1520]}
    'layout': {},
    'leave_timeout': 90,              # 秒：检测不到卫戍协议界面多久后停止（PC 端加载较慢）
}


def _merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


class Settings:
    def __init__(self, path: str | os.PathLike, data: dict[str, Any] | None = None):
        self.path = Path(path)
        self.data = _merge(DEFAULTS, data or {})
        self._original = deepcopy(data or {})

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def win32(self) -> dict[str, Any]:
        return self.data['win32']

    def save(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + '.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


def load_settings(path: str | os.PathLike) -> Settings:
    if os.path.isfile(path):
        try:
            with open(path, encoding='utf-8-sig') as f:
                return Settings(path, json.load(f))
        except (OSError, ValueError):
            pass
    return Settings(path, {})
