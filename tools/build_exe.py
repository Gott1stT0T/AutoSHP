"""用 PyInstaller 打包为 onedir 可执行程序。

用法（在装有依赖的解释器上）：
    python tools/build_exe.py

产物：dist/GarrisonFarmPC/GarrisonFarmPC.exe
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_syntax() -> bool:
    """打包前先编译一遍，避免把语法错误打进 exe（PyInstaller 会静默丢掉有问题的模块）。"""
    import py_compile
    bad = []
    for path in list((ROOT / 'src' / 'garrison_pc').rglob('*.py')) + [ROOT / 'launcher.py']:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            bad.append(f'{path}: {exc.msg}')
    if bad:
        print('语法检查失败：')
        for item in bad:
            print('  ', item)
        return False
    print('语法检查通过')
    return True


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print('缺少 PyInstaller：python -m pip install pyinstaller')
        return 1
    if not check_syntax():
        return 2

    sep = ';' if os.name == 'nt' else ':'
    args = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm', '--clean', '--onedir', '--console',
        '--name', 'GarrisonFarmPC',
        '--paths', str(ROOT / 'src'),
        '--add-data', f'{ROOT / "tiles.json"}{sep}.',
        '--add-data', f'{ROOT / "settings.example.json"}{sep}.',
        '--collect-all', 'rapidocr_onnxruntime',
        '--hidden-import', 'onnxruntime',
        '--hidden-import', 'yaml',
        '--hidden-import', 'pyclipper',
        '--hidden-import', 'shapely',
        '--exclude-module', 'matplotlib',
        '--exclude-module', 'pandas',
        '--exclude-module', 'scipy',
        '--exclude-module', 'tkinter',
        str(ROOT / 'launcher.py'),
    ]
    print(' '.join(args))
    code = subprocess.call(args, cwd=str(ROOT))
    if code != 0:
        return code

    dist = ROOT / 'dist' / 'GarrisonFarmPC'
    for name in ('tiles.json', 'settings.example.json', '使用说明.txt', '开始刷角标.bat'):
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, dist / name)
    print('打包完成：', dist / 'GarrisonFarmPC.exe')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
