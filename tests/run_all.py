"""一键运行全部测试。

用法：
    python tests/run_all.py

说明：
  * `test_logic_diff.py` 需要 Python 3.11（原程序字节码是 3.11），其他版本会自动跳过；
  * 其它测试在 Python 3.10+ 都可运行。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = [
    ('逻辑差分（需要 3.11）', 'test_logic_diff.py'),
    ('字面量覆盖审计', 'test_literal_coverage.py'),
    ('Win32 设备端到端', 'test_win32_device.py'),
    ('CLI 自检集成', 'test_app_check.py'),
    ('主循环冒烟', 'test_farm_loop_mock.py'),
]


def main() -> int:
    failures = []
    for title, name in TESTS:
        if name == 'test_logic_diff.py' and sys.version_info[:2] != (3, 11):
            print(f'[跳过] {title}：需要 Python 3.11（当前 {sys.version.split()[0]}）')
            continue
        print(f'\n===== {title} ({name}) =====')
        code = subprocess.call([sys.executable, str(HERE / name)])
        if code != 0:
            failures.append(name)
        print(f'----- {title}: {"通过" if code == 0 else "失败"} -----')
    print('\n汇总：', '全部通过' if not failures else f'失败 {failures}')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
