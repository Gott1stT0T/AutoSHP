"""用真实截图校准坐标：对比原始常量与 PC 端候选常量读到的数值。"""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc import maa as maa_mod, ocr as ocr_mod  # noqa: E402
from garrison_pc.logic import garrison as G  # noqa: E402
from garrison_pc.runtime import Runtime  # noqa: E402

IMG = ROOT / 'farm_logs' / 'live_now_elev.png'


class FakeDevice:
    name = 'fake'

    def __init__(self, img):
        self.img = img

    def shot(self):
        return self.img

    def tap(self, *a, **k):
        pass

    def swipe(self, *a, **k):
        pass

    def touch(self, *a, **k):
        pass

    def describe(self):
        return 'crop'

    def close(self):
        pass


def main() -> int:
    img = cv2.imread(str(IMG))
    info = maa_mod.load_maa()
    models = maa_mod.find_ocr_models(str(info.ocr_dir))
    engine = ocr_mod.create_engine(models.det.parent.parent)
    rt = Runtime(FakeDevice(img), ROOT / 'farm_logs' / 'calib', ROOT / 'strategies_done.calib.json',
                 app_dir=ROOT)
    G.bind(rt)
    G.ocr_engine = engine
    G.set_profile('low')

    print('=== 原始常量 ===')
    print('GOLD_BOX', G.GOLD_BOX, 'numrec=', G.numrec(img, G.GOLD_BOX),
          'num=', G.num(img, G.GOLD_BOX))
    print('read_shop:', G.read_shop(img))
    print('read_gold:', G.read_gold(img))
    print('slots_left:', G.slots_left(img))
    cards = G.shop_cards(img)
    for c in cards:
        print('  card', c)

    print('\n=== 候选：资金挪到顶部 ===')
    tests = {
        'gold_1170_20_1265_80': [1170, 20, 1265, 80],
        'gold_1150_15_1280_85': [1150, 15, 1280, 85],
        'gold_1180_25_1250_70': [1180, 25, 1250, 70],
    }
    for name, box in tests.items():
        print(f'  {name}: numrec={G.numrec(img, tuple(box))} num={G.num(img, tuple(box))}')

    print('\n=== 候选：CARD_X 按实测 ===')
    G.apply_layout({'CARD_X': [766, 986, 1229, 1473]})
    print('CARD_X ->', G.CARD_X, 'CARDS ->', G.CARDS)
    for c in G.shop_cards(img):
        print('  card', c)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
