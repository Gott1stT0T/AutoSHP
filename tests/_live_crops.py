"""裁剪真实截图的关键区域，便于目视核对坐标常量。"""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc import maa as maa_mod, ocr as ocr_mod
from garrison_pc.logic import garrison as G  # noqa: F401  (常量)

SRC = ROOT / 'farm_logs' / 'live_now_elev.png'
OUT = ROOT / 'farm_logs' / 'crops'


def main() -> int:
    img = cv2.imread(str(SRC))
    if img is None:
        print('no image', SRC)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    regions = {
        'gold_box': (1785, 768, 1850, 816),
        'right_bottom': (1500, 500, 1920, 900),
        'top_center': (600, 20, 1350, 90),
        'bottom_cards': (250, 760, 1800, 1060),
        'left_panel': (0, 820, 760, 1060),
        'ready': (1700, 120, 1900, 220),
    }
    for name, (x1, y1, x2, y2) in regions.items():
        crop = img[y1:y2, x1:x2]
        big = cv2.resize(crop, (crop.shape[1] * 3, crop.shape[0] * 3),
                         interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(str(OUT / f'{name}.png'), big)
        print(name, 'saved', crop.shape)

    info = maa_mod.load_maa()
    models = maa_mod.find_ocr_models(str(info.ocr_dir))
    engine = ocr_mod.create_engine(models.det.parent.parent)
    print('\nOCR regions:')
    for name, (x1, y1, x2, y2) in regions.items():
        crop = img[y1:y2, x1:x2]
        res, _ = engine(crop)
        texts = [str(item[1]) for item in (res or [])]
        print(f'  {name}: {texts}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
