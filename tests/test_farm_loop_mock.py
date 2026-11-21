"""集成冒烟测试：用脚本化的假设备/假 OCR 驱动 farm_loop，验证整条主循环不崩。

不接触真实游戏，只验证：主循环分支、pick_strategy/pick_squad/prep_phase 的调用链、
以及各模块之间的名字/接口是否自洽。
"""
from __future__ import annotations

import sys
import types
import unittest.mock as mock
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.runtime import Runtime  # noqa: E402
from garrison_pc import app  # noqa: E402
from garrison_pc.logic import garrison as G  # noqa: E402


class ScriptedScreen:
    def __init__(self):
        self.stage = 0
        self.shots = 0
        self.taps: list[tuple[float, float]] = []
        self.stages = [
            # (需要多少张截图后自动进入下一阶段; None=靠点击推进)
            dict(items=[(1700, 986, '开始模拟'), (200, 200, '极速模拟'), (300, 300, '回合')],
                 advance_on=(1700, 986), hold=None),
            dict(items=[(1686, 986, '确认本局信息')], advance_on=(1686, 986), hold=None),
            dict(items=[(1500, 300, '选择策略'), (1600, 200, '初始生命值'),
                        (1600, 300, '通过 0 次'), (1700, 600, '测试策略')],
                 advance_on=(1680, 990), hold=None),
            dict(items=[(600, 400, '维什戴尔'), (600, 800, '塔露拉'), (1686, 986, '确定自选编队')],
                 advance_on=(1686, 986), hold=None),
            dict(items=[(200, 200, '回合'), (200, 300, '准备就绪'), (300, 900, '升级'),
                        (320, 800, '满级'), (600, 940, '维什戴尔'), (900, 940, '塔露拉'),
                        (100, 60, '极速模拟')],
                 advance_on=None, hold=6),
            dict(items=[(1700, 900, '返回主页'), (1700, 800, '模拟完成')],
                 advance_on=None, hold=None),
        ]

    @property
    def items(self):
        return list(self.stages[self.stage]['items'])

    def on_shot(self):
        self.shots += 1
        stage = self.stages[self.stage]
        if stage['hold'] and self.shots >= stage['hold']:
            self.next_stage()

    def on_tap(self, x, y, wait=0.0):
        self.taps.append((x, y))
        stage = self.stages[self.stage]
        ax, ay = stage['advance_on'] or (-1, -1)
        if abs(x - ax) <= 3 and abs(y - ay) <= 3:
            self.next_stage()

    def next_stage(self):
        if self.stage < len(self.stages) - 1:
            self.stage += 1
            self.shots = 0


class FakeDevice:
    name = 'fake'

    def __init__(self, screen: ScriptedScreen):
        self.screen = screen

    def describe(self):
        return 'FakeDevice'

    def ensure_ready(self):
        pass

    def shot(self):
        self.screen.on_shot()
        return np.zeros((1080, 1920, 3), np.uint8)

    def tap(self, x, y, wait=0.6):
        self.screen.on_tap(x, y, wait)

    def swipe(self, x1, y1, x2, y2, ms=500, wait=0.8):
        self.screen.taps.append((x2, y2))

    def touch(self, kind, x, y):
        pass

    def close(self):
        pass


class FakeEngine:
    def __init__(self, screen: ScriptedScreen):
        self.screen = screen

    def __call__(self, img, **kwargs):
        items = []
        for x, y, t in self.screen.items:
            box = [[x - 5, y - 5], [x + 5, y - 5], [x + 5, y + 5], [x - 5, y + 5]]
            items.append([box, t, 0.99])
        return items, [0.0]


def main() -> int:
    screen = ScriptedScreen()
    device = FakeDevice(screen)
    log_dir = ROOT / 'farm_logs' / 'mock'
    log_dir.mkdir(parents=True, exist_ok=True)
    runtime = Runtime(device=device, log_dir=log_dir,
                      done_file=ROOT / 'strategies_done.mock.json', app_dir=ROOT)
    G.bind(runtime)
    G.ocr_engine = FakeEngine(screen)
    # 逻辑层的 ocr() 会按裁剪框换算坐标；冒烟测试直接用绝对坐标，避免框偏移干扰
    G.ocr = lambda img, box=None: [(x, y, t) for x, y, t in screen.items]
    G.numrec = lambda img, box: 10
    G.set_profile('full')
    G.TARGET = 3

    args = types.SimpleNamespace(runs=1, attempts=1)
    import time as real_time
    with mock.patch.object(real_time, 'sleep', lambda *_: None):
        app.farm_loop(runtime, args, runtime.log)
    print('taps:', len(screen.taps), 'final stage:', screen.stage)
    assert len(screen.taps) > 5, '没有产生足够的点击'
    assert screen.stage >= 5, f'主循环没有走到结算阶段（stage={screen.stage}）'
    print('OK: farm_loop 冒烟通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
