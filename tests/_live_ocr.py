"""对真实游戏截图跑 OCR，检查关键文案是否可识别。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from garrison_pc import maa as maa_mod  # noqa: E402
from garrison_pc import ocr as ocr_mod  # noqa: E402


def main() -> int:
    args = sys.argv[1:]
    image = Path(args[0]) if args else ROOT / 'farm_logs' / 'elev_shot.png'
    info = maa_mod.load_maa()
    models = maa_mod.find_ocr_models(str(info.ocr_dir) if info and info.ocr_dir else None)
    print('models:', models)
    engine = ocr_mod.create_engine(models.det.parent.parent)
    import cv2
    img = cv2.imread(str(image))
    print('image:', image, None if img is None else img.shape)
    res, elapse = engine(img)
    texts = [(int(sum(p[0] for p in box) / 4), int(sum(p[1] for p in box) / 4), t)
             for box, t, score in (res or [])]
    for x, y, t in sorted(texts, key=lambda v: (v[1], v[0])):
        print(f'({x:4d},{y:4d}) {t}')
    joined = ''.join(t for _, _, t in texts)
    print('\n关键文案检测：')
    for kw in ('极速模拟', '独立模拟', '个人模拟', '卫戍协议', '协议数据库', '模拟邀请',
               '功勋兑换处', '更改主题', '关键目标', '联合模拟', '切换主题'):
        print(f'  {"命中" if kw in joined else "未命中"}  {kw}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
