"""OCR 引擎：复用 MAA 自带的 PaddleOCR 模型（det + rec + keys）。

与原项目一致，使用 ``rapidocr_onnxruntime`` 作为 PaddleOCR 的推理封装；
模型来自本机 MAA 的 ``resource/PaddleOCR``，不随本项目分发。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class OcrUnavailable(RuntimeError):
    pass


def _rapidocr_class():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:      # pragma: no cover - 依赖缺失时的友好提示
        raise OcrUnavailable(
            '缺少 OCR 依赖 rapidocr_onnxruntime（以及 onnxruntime / opencv）。\n'
            '请先运行 setup.bat，或手动执行：\n'
            '  pip install rapidocr_onnxruntime onnxruntime opencv-python-headless numpy'
        ) from exc
    return RapidOCR


def _ascii_paths(det: Path, rec: Path, keys: Path) -> tuple[Path, Path, Path]:
    """onnxruntime 在中文路径下可能加载失败，必要时把模型复制到纯 ASCII 临时目录。"""
    import shutil
    import tempfile

    if all(str(p).isascii() for p in (det, rec, keys)):
        return det, rec, keys
    tmp = Path(tempfile.gettempdir()) / 'garrisonfarm_pc_models'
    tmp.mkdir(parents=True, exist_ok=True)
    out = []
    for src in (det, rec, keys):
        dst = tmp / f'{src.parent.name}_{src.name}'
        try:
            if (not dst.is_file()) or dst.stat().st_size != src.stat().st_size:
                shutil.copy2(src, dst)
        except OSError:
            return det, rec, keys
        out.append(dst)
    return out[0], out[1], out[2]


def create_engine(ocr_dir: str | os.PathLike, threads: int | None = None,
                  text_score: float = 0.5) -> Any:
    """按 MAA 的目录结构创建 OCR 引擎。"""
    base = Path(ocr_dir)
    det = base / 'det' / 'inference.onnx'
    rec = base / 'rec' / 'inference.onnx'
    keys = base / 'rec' / 'keys.txt'
    missing = [str(p) for p in (det, rec, keys) if not p.is_file()]
    if missing:
        raise OcrUnavailable('OCR 模型不完整，缺少：' + '、'.join(missing))

    det, rec, keys = _ascii_paths(det, rec, keys)
    RapidOCR = _rapidocr_class()
    kwargs: dict[str, Any] = {
        'det_model_path': str(det),
        'rec_model_path': str(rec),
        'rec_keys_path': str(keys),
        'use_cls': False,
        'text_score': text_score,
    }
    if threads is None:
        threads = max(1, min(8, (os.cpu_count() or 4)))
    kwargs['intra_op_num_threads'] = int(threads)
    try:
        return RapidOCR(**kwargs)
    except TypeError:
        # 老版本 rapidocr 不接受线程参数
        kwargs.pop('intra_op_num_threads', None)
        return RapidOCR(**kwargs)


def warmup(engine: Any) -> float:
    """跑一张空白小图，返回耗时（秒），用于自检时判断 OCR 是否可用。"""
    import time

    img = np.full((64, 320, 3), 255, dtype=np.uint8)
    cv2.putText(img, 'OK 123', (8, 44), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    t0 = time.time()
    result = engine(img)
    elapsed = time.time() - t0
    if result is None:
        raise OcrUnavailable('OCR 引擎没有返回结果')
    return elapsed


def quick_ocr(engine: Any, img: np.ndarray) -> list[str]:
    """返回识别到的文本行（调试/自检用）。"""
    res, _ = engine(img) if isinstance(engine(img), tuple) else (engine(img), None)
    return [str(item[1]) for item in (res or [])]
