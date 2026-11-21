"""卫戍协议「极速模拟」自动刷策略角标 —— 业务逻辑层。

本文件由原 GarrisonFarm 1.2（PyInstaller 冻结版）的 CPython 3.11 字节码逐函数还原，
并由个人优化版 v1.2 的补丁（passed_count / pick_strategy / save_done 过滤）合并而来。
所有函数名、常量名、常量取值、坐标、文案均与原程序一致，便于对照与回归测试。

坐标系固定为 1920x1080（16:9）虚拟画面：
  - ``shot()`` 返回 (1080, 1920, 3) 的 BGR 图；
  - 点击/滑动坐标都以该虚拟画面为准，由设备层缩放到真实窗口客户区像素。

本模块不包含任何平台相关代码（ADB / Win32 / MAA 发现逻辑都在设备层与运行时层）。
"""
import json
import os
import re
import time
import unicodedata

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# 运行时注入（设备、日志、进度文件）
# ---------------------------------------------------------------------------
RUNTIME = None

# 程序目录（由 bind() 注入；frozen 时是 exe 所在目录，源码运行时是项目根目录）
HERE = ''


def _here() -> str:
    return HERE


def bind(runtime):
    """由启动器在运行前注入运行时对象。"""
    global RUNTIME, HERE
    RUNTIME = runtime
    HERE = str(getattr(runtime, 'app_dir', '') or '')


def shot():
    return RUNTIME.device.shot()


def tap(x, y, wait=0.6):
    RUNTIME.device.tap(x, y, wait)


def swipe(x1, y1, x2, y2, ms=500, wait=0.8):
    RUNTIME.device.swipe(x1, y1, x2, y2, ms, wait)


def touch(kind, x, y):
    RUNTIME.device.touch(kind, x, y)


def log(*args):
    RUNTIME.log(*args)


def save(img, tag=''):
    RUNTIME.save(img, tag)


def load_done():
    return RUNTIME.load_done()


def save_done(s):
    RUNTIME.save_done(s)


def apply_layout(overrides):
    """用 settings.json 的 ``layout`` 覆盖坐标常量（用于适配官方 PC 端的 UI 差异）。

    ``overrides`` 形如 ``{"GOLD_BOX": [1170, 20, 1265, 80], "LEAVE_TIMEOUT": 90}``；
    只覆盖已存在的常量名，类型按原常量的类型转换。返回实际生效的键名列表。
    """
    if not overrides:
        return []
    scope = globals()
    applied = []
    for key, value in dict(overrides).items():
        if key not in scope or callable(scope[key]):
            continue
        cur = scope[key]
        try:
            if isinstance(cur, tuple) and isinstance(value, (list, tuple)):
                scope[key] = tuple(tuple(v) if isinstance(v, (list, tuple)) else v for v in value)
            elif isinstance(cur, list) and isinstance(value, (list, tuple)):
                scope[key] = [tuple(v) if isinstance(v, (list, tuple)) else v for v in value]
            elif isinstance(cur, (int, float)) and isinstance(value, (int, float)):
                scope[key] = type(cur)(value)
            else:
                scope[key] = value
            applied.append(key)
        except (TypeError, ValueError):
            continue
    return applied


# OCR 引擎由运行时注入（与 MAA 的 PaddleOCR 模型同源）
ocr_engine = None

# 调试开关：设置环境变量 GFPC_DEBUG=1 时输出更详细的购买/部署判定信息
DEBUG = bool(os.environ.get('GFPC_DEBUG'))

# ---------------------------------------------------------------------------
# 常量（与原程序逐字一致）
# ---------------------------------------------------------------------------
%s

GENERIC = ['点击任意', '继续', '返回', '确认', '确定', '领取', '下一步', '完成']
GARRISON = ['极速模拟', '卫戍', 'STRONGHOLD', '确认准备', '资金将在', '选择策略',
            '确认本局信息', '确定自选编队', '返回主页', '模拟完成', '模拟中断',
            'COUNTDOWN', '断线重连', '放弃模拟']
LAYOUT = None
