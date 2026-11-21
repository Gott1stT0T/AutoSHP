"""源码运行入口：python launcher.py [参数]"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'src'))

from garrison_pc.app import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
