"""启动自检：程序目录、MAA、设备、截图、输入方式、OCR 模型。"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

OK = '✔'
WARN = '⚠'
FAIL = '✘'


@dataclass
class CheckResult:
    status: str
    item: str
    message: str = ''
    fatal: bool = False


def check_writable(app_dir: Path) -> CheckResult:
    try:
        probe = app_dir / '.write_test'
        probe.write_text('ok', encoding='utf-8')
        probe.unlink()
        return CheckResult(OK, '程序目录可写')
    except OSError as exc:
        return CheckResult(FAIL, '程序目录可写',
                           f'{app_dir} 无法写入（{exc}）。请把整个文件夹解压到普通目录后再运行。',
                           fatal=True)


def check_files(app_dir: Path) -> CheckResult:
    missing = [name for name in ('tiles.json',) if not (app_dir / name).is_file()]
    if missing:
        return CheckResult(WARN, '程序文件完整',
                           '缺少 ' + '、'.join(missing) + '，将使用最右 3 列自动识别部署格')
    return CheckResult(OK, '程序文件完整')


def check_maa(maa: Any) -> CheckResult:
    if maa is None:
        return CheckResult(WARN, '找到 MAA', '未找到 MAA 安装目录：将使用内置/指定的模型与 ADB 设置')
    return CheckResult(OK, '找到 MAA', str(maa.root))


def check_connect_settings(maa: Any) -> CheckResult:
    if maa is None or maa.config_file is None:
        return CheckResult(WARN, '读取 MAA 连接设置', '没有读到 MAA 配置，使用 settings.json')
    conn = maa.connection
    text = f'连接配置={conn.config or "未知"}'
    if conn.is_pc:
        text += '（官方 PC 端 / Win32 窗口）'
    else:
        text += f' adb={conn.adb_path or "自动"} 地址={conn.address or "自动"}'
    return CheckResult(OK, '读取 MAA 连接设置', text)


def check_device(device: Any) -> CheckResult:
    try:
        device.ensure_ready()
        return CheckResult(OK, '连接设备', device.describe())
    except Exception as exc:
        return CheckResult(FAIL, '连接设备', str(exc), fatal=True)


def check_capture(device: Any, save_dir: Path) -> CheckResult:
    try:
        img = device.shot()
    except Exception as exc:
        return CheckResult(FAIL, '截图', str(exc), fatal=True)
    h, w = img.shape[:2]
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
        import cv2
        ok, buf = cv2.imencode('.png', img)
        if ok:
            (save_dir / 'startup_check.png').write_bytes(buf.tobytes())
    except Exception:
        pass
    if img.mean() < 2:
        return CheckResult(FAIL, '截图', '截到的是纯黑画面：请确认游戏已进入画面（不要最小化）', fatal=True)
    # 真实窗口的宽高比用客户区判断（shot() 已裁成 16:9）
    aspect_note = ''
    try:
        cw, ch = device.client_size()
        if ch and abs(cw / ch - 16 / 9) > 0.02:
            aspect_note = f'；窗口客户区 {cw}x{ch} 不是 16:9，建议在游戏设置里改成 1920x1080/1280x720 窗口化'
    except Exception:
        pass
    if aspect_note:
        return CheckResult(WARN, '截图', f'{w}x{h}，已保存 startup_check.png{aspect_note}')
    return CheckResult(OK, '截图', f'{w}x{h}，已保存 startup_check.png')


def check_input(device: Any) -> CheckResult:
    method = getattr(device, 'options', None)
    if getattr(device, 'name', '') == 'win32':
        mode = getattr(method, 'input', 'cursor') if method else 'cursor'
        return CheckResult(OK, '输入方式', f'Win32 消息注入（{mode}）')
    return CheckResult(OK, '输入方式', 'ADB input / motionevent')


def check_ocr(engine: Any, ocr_dir: Path | None) -> CheckResult:
    if engine is None:
        return CheckResult(FAIL, '文字识别模型', 'OCR 引擎未初始化', fatal=True)
    try:
        import cv2
        img = np.full((64, 320, 3), 255, dtype=np.uint8)
        cv2.putText(img, 'OK 123', (8, 44), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        t0 = time.time()
        res = engine(img)
        elapsed = time.time() - t0
        texts = [str(item[1]) for item in (res[0] if isinstance(res, tuple) else res) or []]
        where = f'MAA 模型（{ocr_dir}）' if ocr_dir else '指定模型'
        if not texts:
            return CheckResult(WARN, '文字识别模型', f'{where} 测试识别没有结果，可能影响识别准确率')
        return CheckResult(OK, '文字识别模型', f'{where}，单次约 {elapsed:.1f}s')
    except Exception as exc:
        return CheckResult(FAIL, '文字识别模型', f'{exc}', fatal=True)


def run_all(settings: Any, maa: Any, device: Any, engine: Any, app_dir: Path,
            log_dir: Path, log=print) -> list[CheckResult]:
    ocr_dir = getattr(settings, '_ocr_dir', None)
    results = [
        check_writable(app_dir),
        check_files(app_dir),
        check_maa(maa),
        check_connect_settings(maa),
        check_device(device),
        check_capture(device, log_dir),
        check_input(device),
        check_ocr(engine, Path(ocr_dir) if ocr_dir else None),
    ]
    print('========== 启动自检 ==========', flush=True)
    for r in results:
        suffix = f'：{r.message}' if r.message else ''
        print(f'  [{r.status}] {r.item}{suffix}', flush=True)
    print('==============================', flush=True)
    return results
