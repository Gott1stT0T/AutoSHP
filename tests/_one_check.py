"""辅助脚本：跑一次 --check（供并发测试/单实例验证使用）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc.app import main  # noqa: E402

raise SystemExit(main(['--check', '--yes']))
