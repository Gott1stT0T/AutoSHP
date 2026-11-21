"""运行时对象：把设备、OCR、日志、进度文件注入业务逻辑层。"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np


class Runtime:
    """业务逻辑层看到的“世界”。

    ``logic.garrison`` 通过模块级 shim（``shot/tap/swipe/touch/log/save/load_done/
    save_done``）调用这里，因此业务代码与平台实现完全解耦。
    """

    def __init__(self, device: Any, log_dir: str | os.PathLike,
                 done_file: str | os.PathLike, ocr_engine: Any = None,
                 verbose: bool = True, app_dir: str | os.PathLike | None = None,
                 keep_screenshots: int = 200):
        self.device = device
        self.app_dir = Path(app_dir) if app_dir else Path(log_dir).resolve().parent
        self.log_dir = Path(log_dir)
        self.done_file = Path(done_file)
        self.ocr_engine = ocr_engine
        self.verbose = verbose
        self.keep_screenshots = keep_screenshots
        self._saved = 0
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.run_log = self.log_dir / 'run.log'
        self._done: set[str] = set()

    # -- 日志 -------------------------------------------------------------
    def log(self, *args: Any) -> None:
        line = ' '.join([time.strftime('%H:%M:%S')] + [str(x) for x in args])
        if self.verbose:
            print(line, flush=True)
        try:
            with open(self.run_log, 'a', encoding='utf-8') as f:
                print(time.strftime('%Y-%m-%d'), line, file=f)
        except OSError:
            pass

    # -- 截图存档 ---------------------------------------------------------
    def save(self, img: np.ndarray, tag: str = '') -> str:
        p = os.path.join(str(self.log_dir), f'{time.strftime("%H%M%S")}_{tag}.png')
        try:
            # cv2.imwrite 在中文路径下会失败，改用 imencode + 二进制写入
            ok, buf = cv2.imencode('.png', img)
            if ok:
                with open(p, 'wb') as f:
                    f.write(buf.tobytes())
        except Exception:
            pass
        self._saved += 1
        if self.keep_screenshots and self._saved % 20 == 0:
            self._prune()
        return p

    def _prune(self) -> None:
        try:
            shots = sorted(self.log_dir.glob('*.png'),
                           key=lambda f: f.stat().st_mtime, reverse=True)
            for old in shots[self.keep_screenshots:]:
                old.unlink(missing_ok=True)
        except OSError:
            pass

    # -- 策略进度 ---------------------------------------------------------
    def load_done(self) -> set[str]:
        try:
            with open(self.done_file, encoding='utf-8') as f:
                self._done = set(json.load(f))
        except Exception:
            self._done = set()
        return self._done

    def save_done(self, done: Iterable[str]) -> None:
        # 个人优化版 v1.2：占位名（无法识别名称[gx,gy]）不写入进度，避免下次误跳过
        cleaned = {name for name in done if not str(name).startswith('无法识别名称[')}
        self._done = set(cleaned)
        tmp = self.done_file.with_suffix(self.done_file.suffix + '.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(sorted(self._done), f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.done_file)

    # -- 业务逻辑桥接 -----------------------------------------------------
    def bind(self, logic_module: Any) -> Any:
        logic_module.bind(self)
        logic_module.ocr_engine = self.ocr_engine
        return logic_module
