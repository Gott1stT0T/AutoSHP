"""启动入口：参数解析、模式选择、自检、主循环。

主循环逐句还原自原 GarrisonFarm 的 ``main()``（见 docs/00-原项目分析.md），
只把「设备连接 / 自检 / 启动」部分换成官方 PC 端（Win32）实现。
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

from . import maa as maa_mod
from . import ocr as ocr_mod
from . import selfcheck
from .config import load_settings
from .device import DeviceError, create_device, diagnose_windows
from .runtime import Runtime
from .ui import dialogs
from .logic import garrison as G


def app_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


APP_DIR = app_dir()


def setup_console() -> None:
    """让中文在 Windows 控制台（代码页 936）与重定向管道里都能正常显示。"""
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


def is_admin() -> bool:
    if os.name != 'nt':
        return True
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return True


def relaunch_as_admin() -> bool:
    """以管理员身份重启自身（保留命令行参数）。返回是否成功发起。"""
    if os.name != 'nt':
        return False
    try:
        import ctypes
        if getattr(sys, 'frozen', False):
            exe, args = sys.executable, sys.argv[1:]
        else:
            exe, args = sys.executable, [str(Path(__file__).resolve().parents[2] / 'launcher.py')] + sys.argv[1:]
        import subprocess
        params = subprocess.list2cmdline(args)
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, 'runas', exe, params, str(APP_DIR), 1)
        return int(rc) > 32
    except Exception as exc:
        print(f'提权失败：{exc}')
        return False


_MUTEX = None


def acquire_single_instance() -> bool:
    """同一时间只允许一个实例操作游戏窗口（命名互斥体，进程退出自动释放）。"""
    global _MUTEX
    if os.name != 'nt':
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, 'Local\\GarrisonFarmPC.SingleInstance')
        if not handle:
            return True
        if kernel32.GetLastError() == 183:      # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(handle)
            return False
        _MUTEX = handle
        return True
    except Exception:
        return True


def release_single_instance() -> None:
    global _MUTEX
    if _MUTEX:
        try:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(_MUTEX)
        except Exception:
            pass
        _MUTEX = None


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog='GarrisonFarmPC',
        description='明日方舟「卫戍协议·极速模拟」自动刷策略角标（官方 PC 启动器 / MAA 生态适配版）',
        add_help=True,
    )
    ap.add_argument('--runs', type=int, default=20, help='目标通关局数（默认 20）')
    ap.add_argument('--attempts', type=int, default=0, help='总局数上限（成功失败都算），0=不限')
    ap.add_argument('--maa', default='', help='MAA 目录（默认自动查找）')
    ap.add_argument('--adb', default='', help='覆盖 MAA 配置中的 adb 路径（模拟器模式）')
    ap.add_argument('--address', default='', help='覆盖 MAA 配置中的连接地址（模拟器模式）')
    ap.add_argument('--device', default='', choices=['', 'win32', 'adb', 'auto'],
                    help='强制设备类型：win32=官方 PC 端，adb=模拟器')
    ap.add_argument('--profile', default='full', choices=['full', 'low'],
                    help='full=标准（自选编队），low=低配（只用预设干员）')
    ap.add_argument('--target', type=int, default=3, choices=[3, 6],
                    help='3=金色角标，6=彩色角标（镀层）')
    ap.add_argument('--menu', action='store_true', help='启动时显示模式选择菜单')
    ap.add_argument('--check', action='store_true', help='只做自检（含截图），然后退出')
    ap.add_argument('--yes', action='store_true', help='跳过启动时的使用前提醒')
    ap.add_argument('--show-doc', default='', help='显示指定文件中以 :: 开头的说明文字')
    ap.add_argument('--list-windows', action='store_true', help='列出可见窗口（排查窗口识别问题）')
    ap.add_argument('--probe-tap', action='store_true', help='自检时在画面中央点一下，验证输入通道')
    ap.add_argument('--debug', action='store_true', help='输出购买/部署判定的详细日志')
    ap.add_argument('--no-elevate', action='store_true', help='不自动请求管理员权限（测试用）')
    ap.add_argument('--version', action='store_true', help='显示版本号后退出')
    return ap


# ---------------------------------------------------------------------------
# 说明文字 / 模式菜单
# ---------------------------------------------------------------------------
def show_doc(path: str) -> None:
    if not path:
        return
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            lines = f.read().splitlines()
    except OSError as exc:
        print('（说明文字读取失败：%s）' % exc)
        return
    for line in lines:
        if line.startswith('::'):
            print(line[2:].lstrip())
    print()


MENU_TEXT = (
    '请选择运行模式（输入数字后按回车）：\n'
    '  1. 标准模式 · 刷金色角标（每个策略通关 3 次）   需要配置自选编队\n'
    '  2. 标准模式 · 刷彩色角标（每个策略通关 6 次）   需要配置自选编队\n'
    '  3. 低配模式 · 刷金色角标（每个策略通关 3 次）   不需要自选编队\n'
    '  4. 低配模式 · 刷彩色角标（每个策略通关 6 次）   不需要自选编队'
)


def choose_menu() -> tuple[str, int]:
    print(MENU_TEXT)
    while True:
        try:
            choice = input('请输入 1~4：').strip()
        except EOFError:
            choice = '1'
        if choice in ('1', '2', '3', '4'):
            profile = 'low' if choice in ('3', '4') else 'full'
            target = 6 if choice in ('2', '4') else 3
            print('运行模式：%s · %s' % ('低配模式' if profile == 'low' else '标准模式',
                                        '彩色角标（通关 6 次）' if target == 6 else '金色角标（通关 3 次）'))
            return profile, target
        print('输入无效，请输入 1~4。')


def reminder(profile: str, target: int, device_desc: str) -> None:
    if profile == 'low':
        body = ('低配模式不需要配置自选编队（为空即可），只使用游戏预设干员。\n'
                '建议在「选配助战」里为自己没有的推荐干员借用助战（最多 30 名），胜率更高；不借用也能运行。')
        names = '、'.join(name for _, name in G.PRIORITY_LOW)
    else:
        body = '请确认游戏「自选编队」中已配置推荐干员（每局开局会自动从中选 Ⅴ、Ⅵ 阶各 2 名）。'
        names = '、'.join(name for _, name in G.PRIORITY_FULL)
    text = (
        f'{body}\n\n'
        f'本程序会优先购买以下干员（按权重从高到低）：\n{names}\n'
        ' 优先放在两个安全位，其余干员优先放在敌人路径上。\n\n'
        f'当前设备：{device_desc}\n'
        f'当前模式：{"刷彩色角标（同一策略通关 6 次）" if target == 6 else "刷金色角标（同一策略通关 3 次）"}\n\n'
        '运行期间请不要用鼠标操作游戏窗口（程序需要移动真实光标来点击）。\n'
        '点击「确定」开始运行。'
    )
    dialogs.info(text, 'GarrisonFarm PC 使用前提醒')


# ---------------------------------------------------------------------------
# 设备准备
# ---------------------------------------------------------------------------
def wait_game_window(settings, log, timeout: float | None = None) -> int | None:
    titles = settings.get('window_title') or ['明日方舟', 'Arknights']
    exe = settings.get('game_exe') or 'Arknights.exe'
    from .device.win32 import find_window
    deadline = time.time() + (timeout or float(settings.get('launch_timeout', 180)))
    while time.time() < deadline:
        hwnd = find_window(titles, (exe,))
        if hwnd:
            return hwnd
        time.sleep(2)
    return None


def ensure_game(settings, maa_info, log) -> None:
    """窗口不存在时按配置拉起鹰角启动器（官方 PC 端要求由启动器拉起游戏）。"""
    from .device.win32 import find_window
    titles = settings.get('window_title') or ['明日方舟', 'Arknights']
    exe = settings.get('game_exe') or 'Arknights.exe'
    if find_window(titles, (exe,)):
        return
    if not settings.get('auto_launch', True):
        return
    game_hint = settings.get('pc_client_path', '') or (
        maa_info.connection.pc_client_path if maa_info is not None else '')
    game = maa_mod.find_game(game_hint)
    launcher = maa_mod.find_launcher(settings.get('launcher_path', ''), str(game) if game else '')
    if launcher is None:
        log('[启动] 没有找到鹰角启动器：请手动打开启动器并进入游戏')
        return
    log(f'[启动] 正在通过启动器启动游戏：{launcher}')
    try:
        maa_mod.launch(launcher, launcher.parent)
    except OSError as exc:
        log(f'[启动] 启动失败：{exc}；请手动打开启动器')
        return
    log(f'[启动] 等待游戏窗口（最多 {int(settings.get("launch_timeout", 180))} 秒）……')
    if wait_game_window(settings, log) is None:
        log('[启动] 仍未检测到游戏窗口：请在启动器里进入游戏后重新运行本程序')


# ---------------------------------------------------------------------------
# 主循环（逐句还原自原程序 main()）
# ---------------------------------------------------------------------------
OVERLAY_HINTS = ('蚀刻章', '公告', '情报', '档案', '活动说明', '规则说明')


def clear_overlays(device, log, tries: int = 4) -> bool:
    """启动前清理挡在卫戍协议主界面前的弹窗（蚀刻章/公告等）。

    返回是否已经能看到「极速模拟」/「断线重连」。
    """
    for _ in range(tries):
        items = G.ocr(device.shot())
        text = ''.join(t for _, _, t in items)
        if '极速模拟' in text or '断线重连' in text:
            return True
        hit = G.find(items, *G.GENERIC)
        if hit:
            log('关闭弹窗：', hit[2])
            device.tap(hit[0], hit[1], 1.0)
            continue
        if any(k in text for k in OVERLAY_HINTS):
            log('检测到弹窗，点击空白处关闭')
            device.tap(960, 120, 1.0)
            continue
        break
    items = G.ocr(device.shot())
    text = ''.join(t for _, _, t in items)
    return '极速模拟' in text or '断线重连' in text


def farm_loop(runtime: Runtime, args, log) -> None:
    device = runtime.device
    shot = device.shot
    tap = device.tap
    ocr = lambda img: G.ocr(img)          # noqa: E731  (走业务层的 OCR 封装)
    find = G.find
    save = runtime.save

    # 心跳：每 30 秒记录一次当前阶段，卡住时可以从 run.log 看出停在哪个分支
    import threading
    stop_beat = threading.Event()
    state = {'stage': '启动', 'txt': ''}
    t_start = time.time()

    def _beat() -> None:
        while not stop_beat.wait(30):
            try:
                info = getattr(device, 'last_frame_info', {}) or {}
                log(f'[心跳] 阶段={state["stage"]}  已运行{int(time.time() - t_start)}s  '
                    f'截图={info.get("method")}/{info.get("size")}  '
                    f'屏幕文本={state["txt"][:60]!r}')
            except Exception:
                pass

    threading.Thread(target=_beat, daemon=True).start()

    done = G.load_done()
    board = G.Board()
    last_seen = time.time()
    last_progress = time.time()
    last_round = None
    runs = 0
    attempts = 0
    results: list[tuple] = []
    current = None
    idle = 0
    run_t0 = time.time()

    while runs < args.runs:
        state['stage'] = '截图+识别'
        img = shot()
        items = ocr(img)
        txt = ''.join(t for _, _, t in items)
        state['txt'] = txt

        if time.time() - last_progress > G.STALL_TIMEOUT:
            save(img, 'stalled')
            log(f'已有 {G.STALL_TIMEOUT // 60} 分钟没有进展，判定为卡死，停止运行。')
            break

        if any(k in txt for k in G.GARRISON):
            last_seen = time.time()
        else:
            # 加载画面/黑屏/公告不算"离开卫戍协议"（PC 端读取对局的时间明显比模拟器长）
            low_detail = float(img.mean()) < 25 and float(img.std()) < 45
            if low_detail or '鹰角网络' in txt or 'STUDIO' in txt.upper() or '公告' in txt:
                last_seen = time.time()
            elif time.time() - last_seen > G.LEAVE_TIMEOUT:
                save(img, 'left_garrison')
                log(f'已有 {G.LEAVE_TIMEOUT} 秒检测不到卫戍协议界面，立即停止。')
                break

        if '点击取消' in txt and '准备就绪' in txt:
            t = G.LAST_TILE[0]
            log('检测到停在选择朝向界面，自动补设朝向', t)
            if t:
                G.set_facing(*t)
            else:
                hit = find(items, '点击取消')
                tap(hit[0], hit[1], 1.0)
            continue

        if '返回主页' in txt:
            state['stage'] = '结算'
            save(img, 'result')
            ok = '模拟完成' in txt
            if ok and current:
                done.add(current)
                G.save_done(done)
            if ok:
                runs += 1
            attempts += 1
            results.append((current, ok, int(time.time() - run_t0)))
            log(f'本局{"通关" if ok else "失败"}，策略 {current}，用时 {int(time.time() - run_t0)}s，'
                f'已通关 {runs}/{args.runs}，已打 {attempts} 局')
            current = None
            last_progress = time.time()
            hit = find(items, '返回主页')
            tap(hit[0], hit[1], 4)
            board = G.Board()
            if runs >= args.runs or (args.attempts and attempts >= args.attempts):
                break
            time.sleep(1)
            continue

        if ('请选择模拟难度' in txt
                or ('开始模拟' in txt and '极速模拟' in txt and '回合' in txt)):
            hit = find(items, '开始模拟')
            tap(*(hit[:2] if hit else (1700, 986)), 3)
            board = G.Board()
            time.sleep(1)
            continue

        if '确认准备' in txt or '资金将在' in txt:
            tap(860, 602, 0.5)
            tap(1410, 728, 2)
            time.sleep(1)
            continue

        if '断线重连' in txt:
            hit = find(items, '断线重连')
            log('检测到未完成的对局，断线重连')
            tap(*(hit[:2] if hit else (1660, 970)), 5)
            board = G.Board()
            time.sleep(1)
            continue

        if '独立模拟' in txt and '极速模拟' in txt:
            hit = find(items, '极速模拟')
            tap(*(hit[:2] if hit else (1280, 1000)), 3)
            time.sleep(1)
            continue

        if '确认本局信息' in txt:
            tap(1686, 986, 3)
            time.sleep(1)
            continue

        if '选择策略' in txt:
            state['stage'] = '选策略'
            run_t0 = time.time()
            last_progress = time.time()
            current = G.pick_strategy(done)
            G.save_done(done)
            if current is None:
                break
            tap(1680, 990, 3)
            time.sleep(1)
            continue

        if '确定自选编队' in txt:
            G.pick_squad()
            time.sleep(1)
            continue

        if '回合' in txt and '准备就绪' in txt and ('刷新' in txt or '升级' in txt or '满级' in txt):
            state['stage'] = '回合准备 prep_phase'
            G.prep_phase(board, img)
            if board.prep_done and time.time() - board.last_ready > 10:
                log('仍在休整期，重新点击准备就绪')
                tap(*G.READY, 1.5)
                G.handle_popups()
                board.last_ready = time.time()
            if board.round_done != last_round:
                last_round = board.round_done
                last_progress = time.time()
            idle = 0
            continue

        if '回合' in txt or ('查看' in txt and '极速模拟' in txt) or 'COUNTDOWN' in txt.upper():
            board.prep_done = False
            time.sleep(4)
            idle = 0
            continue

        if any(k in txt for k in G.GARRISON):
            hit = find(items, *G.GENERIC)
        else:
            hit = None

        if hit:
            log('通用点击:', hit[2])
            tap(hit[0], hit[1], 2)
            idle = 0
        else:
            state['stage'] = '未知界面'
            idle += 1
            if idle % 5 == 0:
                save(img, 'unknown')
            time.sleep(2)

    log('结束。本次结果:', results)
    log('已获得角标的策略:', sorted(done))
    stop_beat.set()


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    setup_console()
    args = build_parser().parse_args(argv)

    if args.version:
        from . import __version__
        print(f'GarrisonFarm PC {__version__}')
        return 0

    print('GarrisonFarm PC —— 明日方舟「卫戍协议·极速模拟」自动刷策略角标', flush=True)

    if args.list_windows:
        for info in diagnose_windows():
            print(f"  0x{info['hwnd']:08X}  {info['client'][0]}x{info['client'][1]}  "
                  f"{info['class']:<28} {info['title']}  <- {info['exe']}")
        return 0

    if not acquire_single_instance():
        print('已经有一个 GarrisonFarm PC 在运行：请先关闭它（一次只允许一个实例操作游戏窗口）。')
        dialogs.warn('已经有一个 GarrisonFarm PC 在运行。\n请先关闭它，再启动新的。', 'GarrisonFarm PC')
        return 7

    if args.show_doc:
        show_doc(args.show_doc)

    if args.menu:
        profile, target = choose_menu()
    else:
        profile, target = args.profile, args.target
    G.set_profile(profile)
    G.TARGET = target
    print(f'当前模式：{"低配模式" if profile == "low" else "标准模式"} · '
          f'{"刷彩色角标（同一策略通关 6 次）" if target == 6 else "刷金色角标（同一策略通关 3 次）"}')

    settings = load_settings(APP_DIR / 'settings.json')
    if args.device:
        settings.data['device'] = args.device
    if args.adb:
        settings.data['adb'] = args.adb
    if args.address:
        settings.data['address'] = args.address

    log_dir = APP_DIR / settings.get('log_dir', 'farm_logs')
    done_file = APP_DIR / settings.get('done_file', 'strategies_done.json')
    runtime = Runtime(device=None, log_dir=log_dir, done_file=done_file, app_dir=APP_DIR,
                      keep_screenshots=int(settings.get('log_keep', 200) or 0))
    log = runtime.log

    # 官方 PC 端通常以管理员权限运行（ACE 会提升游戏进程），
    # 低权限进程的 PrintWindow/PostMessage 会被 UIPI 拦掉：截图全黑、点击无效。
    if (os.name == 'nt' and not is_admin()
            and not getattr(args, 'no_elevate', False)
            and str(settings.get('device', 'auto')).lower() != 'adb'
            and settings.get('auto_elevate', True)):
        log('[权限] 当前不是管理员：官方 PC 端一般以管理员身份运行，'
            '截图与点击会被系统拦截（PrintWindow 返回 0 / 点击无效）')
        release_single_instance()          # 先让出互斥体，避免提权后的新实例被自己挡住
        if relaunch_as_admin():
            log('[权限] 已请求以管理员身份重新启动：请在弹出的 UAC 窗口点「是」')
            return 0
        acquire_single_instance()
        log('[权限] 提权被取消：若截图全黑或点击无效，请右键程序「以管理员身份运行」')

    if settings.get('warn_if_maa_running', True) and maa_mod.maa_running():
        log('[提示] 检测到 MAA 正在运行：请勿同时运行 MAA 任务，否则会互相抢操作')

    maa_info = maa_mod.load_maa(args.maa, settings.get('maa_dir', ''))
    if maa_info is None:
        log('[提示] 没有找到 MAA 安装目录：将使用 settings.json / 命令行指定的配置')
    else:
        log(f'[MAA] 目录：{maa_info.root}')
        if maa_info.connection.is_pc:
            log('[MAA] 连接配置为「PC 端」：本程序将使用 Win32 窗口截图 + 消息注入')
        elif maa_info.connection.adb_path or maa_info.connection.address:
            log(f'[MAA] adb={maa_info.connection.adb_path or "自动"} '
                f'地址={maa_info.connection.address or "自动"}')

    # OCR 模型：显式配置 > MAA 自带
    ocr_dir = settings.get('ocr_dir', '') or (str(maa_info.ocr_dir) if maa_info and maa_info.ocr_dir else '')
    models = maa_mod.find_ocr_models(ocr_dir if ocr_dir else None,
                                     [APP_DIR / 'fallback' / 'PaddleOCR', APP_DIR / 'models'])
    engine = None
    if models is not None:
        try:
            engine = ocr_mod.create_engine(models.det.parent.parent)
            settings._ocr_dir = str(models.det.parent.parent)
            log(f'[OCR] 模型目录：{models.det.parent.parent}')
        except Exception as exc:
            log(f'[OCR] 模型加载失败：{exc}')
    if engine is None:
        log('[OCR] 没有可用的 PaddleOCR 模型：请安装 MAA（提供 resource/PaddleOCR），'
            '或用 settings.json 的 ocr_dir 指定模型目录')
        dialogs.error('找不到可用的 PaddleOCR 模型。\n'
                      '请先安装 MAA（本程序只读取它的模型），或在 settings.json 里用 ocr_dir 指定模型目录。')
        return 2

    # 设备
    if not args.check:
        ensure_game(settings, maa_info, log)
    try:
        device = create_device(settings, maa_info, log)
    except DeviceError as exc:
        log(f'[设备] {exc}')
        dialogs.error(str(exc) + '\n\n可运行 “GarrisonFarmPC.exe --list-windows” 查看当前窗口列表。')
        return 3

    runtime.device = device
    G.bind(runtime)
    G.ocr_engine = engine
    applied = G.apply_layout(settings.get('layout') or {})
    if applied:
        log('[布局] 已应用坐标覆盖：' + ', '.join(applied))
    G.load_layout()
    if G.LAYOUT:
        log('[布局] 已加载 tiles.json（安全位/敌人路径/备用格），部署将使用固定布局')
    else:
        log('[布局] 未找到 tiles.json：部署将使用最右 3 列自动识别')
    if getattr(args, 'debug', False):
        G.DEBUG = True
        log('[调试] 已开启详细日志')
    G.LEAVE_TIMEOUT = int(settings.get('leave_timeout') or 90)
    if settings.get('leave_timeout'):
        G.LEAVE_TIMEOUT = int(settings.get('leave_timeout'))

    checks = selfcheck.run_all(settings, maa_info, device, engine, APP_DIR, log_dir, log)
    fatal = [c for c in checks if c.fatal]
    warnings = [c for c in checks if c.status == selfcheck.WARN]
    if fatal:
        dialogs.error('启动自检未通过：\n' + '\n'.join(f'  {c.item}：{c.message}' for c in fatal))
        device.close()
        return 4
    if warnings and not args.check:
        dialogs.warn('自检发现以下情况，已自动处理并继续运行：\n'
                     + '\n'.join(f'  - {c.item}：{c.message}' for c in warnings))

    if args.check:
        if args.probe_tap:
            log('[自检] 在画面中央点击一次以验证输入通道……')
            device.tap(960, 540, 0.5)
        log('[自检] 完成，未开始刷取。')
        device.close()
        return 0

    if not args.yes:
        reminder(profile, target, device.describe())

    # 启动前确认已经在卫戍协议界面（先清掉蚀刻章/公告这类弹窗）
    ok_start = clear_overlays(device, log)
    if not ok_start:
        for _ in range(2):
            time.sleep(2)
            text = ''.join(t for _, _, t in G.ocr(device.shot()))
            if '极速模拟' in text or '断线重连' in text:
                ok_start = True
                break
    if not ok_start:
        msg = ('【提示】当前不是卫戍协议的极速模拟界面，程序已停止。\n'
               '请先在游戏中进入「卫戍协议」主界面（能看到“极速模拟”按钮），'
               '或「请选择模拟难度」界面，或已在进行中的极速模拟对局，然后重新运行。')
        log(msg.replace('\n', ' '))
        dialogs.error(msg, 'GarrisonFarm PC')
        device.close()
        return 5

    try:
        farm_loop(runtime, args, log)
    except KeyboardInterrupt:
        log('用户中断（Ctrl+C），已停止')
    except Exception as exc:
        log(f'[错误] {exc}')
        traceback.print_exc()
        try:
            with open(log_dir / 'run.log', 'a', encoding='utf-8') as f:
                traceback.print_exc(file=f)
        except OSError:
            pass
        dialogs.error(f'运行出错：{exc}\n详情见 farm_logs\\run.log')
        return 1
    finally:
        try:
            device.close()
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
