# GarrisonFarm PC

**《明日方舟》「卫戍协议·极速模拟」自动刷策略角标 —— 官方 PC 启动器 / MAA 生态适配版**

本项目把 [GarrisonFarm 个人优化版 v1.2](https://github.com/FJH3576/GarrisonFarm-Personal)
（基于 MuMu 模拟器 + MAA 的刷角标工具）改造为**官方 PC 端**版本：

- 设备层从 `adb + MuMu SDK` 换成 **Windows 窗口截图（PrintWindow）+ Win32 消息注入**，
  与 MAA v6 的 PC 端支持（`MaaWin32ControlUnit`）使用同一套协议；
- 业务逻辑（选策略、自选编队、买干员、升级商店、布阵、角标进度、超时保护）**逐函数移植**，
  行为与原版一致（并保留个人优化版 v1.2 的三处修正）；
- 仍然**只读** MAA 的配置与 PaddleOCR 模型，不修改 MAA 任何文件；
- 同时保留 ADB 设备层，模拟器用户也能用。

> 技术分析、调研与方案见：
> [原项目分析](docs/00-原项目分析.md) · [官方 PC 端调研](docs/01-官方PC端调研.md) · [技术方案](docs/02-技术方案.md)

## 功能

- 自动反复打「极速模拟」刷策略角标：自动选策略、买干员、升级商店、摆放干员、结算，再开下一局。
- 两种模式 × 两种目标：标准（需自选编队）/ 低配（只用预设干员），金色（同一策略 3 次）/ 彩色镀层（6 次）。
- 已有角标的策略自动跳过（按「已通过 N 次」判定，不依赖名称识别）。
- 启动自检（8 项）、离场保护（30 s）、卡死保护（10 min）、关键节点自动截图、`farm_logs/run.log`。

## 环境要求

| 项目 | 要求 |
|---|---|
| 系统 | Windows 10/11 64 位 |
| 游戏 | 官方 PC 端，**由鹰角启动器启动**，已进入「卫戍协议」主界面 |
| 画面 | 窗口 16:9（推荐 1920×1080 或 1280×720）；游戏内 **UI 缩放 100%**；鼠标指针比例调小 |
| MAA | 已安装 MaaAssistantArknights（**用于提供 PaddleOCR 模型**；推荐 v6.x） |
| 权限 | **必须以管理员身份运行**：官方 PC 端的游戏进程由 ACE 提升到高完整性级别，低权限进程的 PrintWindow/PostMessage 会被 Windows UIPI 拦掉（表现为截图全黑、点击无效）。程序检测到非管理员时会自动请求提权 |
| Python | 用源码运行时需要 Python 3.10+（推荐 3.11/3.12） |

## 安装与运行

### 方式 A：直接运行发布包

1. 解压到**普通目录**（不要放在 `Program Files`、压缩包内或只读位置）。
2. 双击 `GarrisonFarmPC.exe`（或 `开始刷角标.bat`），按菜单选择 1~4。
3. 首次运行建议先执行一次自检：`GarrisonFarmPC.exe --check`。

### 方式 B：从源码运行

```bat
setup.bat                 :: 创建 .venv 并安装依赖（只需一次）
.venv\Scripts\python launcher.py --check        :: 自检
开始刷角标.bat             :: 菜单启动
```

或者：

```bat
python -m pip install -r requirements.txt
python launcher.py --menu
```

## 第一次使用前（只需一次）

1. 安装 MAA 并至少连接过一次（这样 MAA 的 `resource/PaddleOCR` 模型才可用）。
2. 打开鹰角启动器 → 进入游戏 → 进入「卫戍协议」主界面（能看到「极速模拟」按钮）。
3. 游戏画质：**16:9 窗口**、UI 缩放 100%；不要开 HDR/独占全屏。
4. 标准模式需要在「卫戍协议 → 自选编队」里配置推荐干员（见程序弹窗提示）；
   低配模式把自选编队留空即可。
5. 运行 `GarrisonFarmPC.exe --check`，确认 8 项自检全绿（会保存一张 `farm_logs/startup_check.png`）。

## 使用

1. 进入「卫戍协议」主界面（有未打完的对局也可以，会提示断线重连）。
2. 运行程序，输入 1~4 选择模式，确认「使用前提醒」。
3. **运行期间不要用鼠标操作游戏窗口**：程序需要移动真实光标来点击/拖拽。
   窗口可以放在后台或被其他窗口遮挡，但**不要最小化**。
4. 停止：关闭命令行窗口或按 `Ctrl+C`。

### 命令行参数

| 参数 | 说明 |
|---|---|
| `--runs N` | 目标通关局数（默认 20） |
| `--attempts N` | 总局数上限（胜负都算），0=不限 |
| `--profile full\|low` | 标准 / 低配模式 |
| `--target 3\|6` | 金色 / 彩色角标 |
| `--menu` | 显示模式选择菜单 |
| `--check` | 只做自检（含截图）后退出 |
| `--probe-tap` | 自检时在画面中央点一下，验证输入通道 |
| `--debug` | 输出购买/部署判定的详细日志（排查用） |
| `--no-elevate` | 不自动请求管理员权限（测试用） |
| `--list-windows` | 列出可见窗口（排查"找不到游戏窗口"） |
| `--maa <目录>` | 指定 MAA 安装目录 |
| `--device win32\|adb` | 强制设备类型 |
| `--adb <路径> --address host:port` | 模拟器模式下手动指定 |
| `--yes` | 跳过使用前提醒 |
| `--version` | 显示版本号 |

退出码：`0` 正常 / `1` 运行异常 / `2` 无 OCR 模型 / `3` 无设备 / `4` 自检致命项 /
`5` 不在卫戍协议界面 / `7` 已有实例在运行。

## 配置 `settings.json`

程序目录下的 `settings.json`（不存在则用默认值；参考 `settings.example.json`）：

| 键 | 默认 | 说明 |
|---|---|---|
| `device` | `auto` | `auto` = 优先官方 PC 窗口，其次 ADB；`win32` / `adb` 强制 |
| `maa_dir` | `""` | 留空自动查找 |
| `launcher_path` | `""` | 留空自动查找鹰角启动器 |
| `pc_client_path` | `""` | 留空用 MAA 的 `PcClientPath` / 自动查找 |
| `auto_launch` | `true` | 没有游戏窗口时自动拉起启动器 |
| `window_title` | `["明日方舟","Arknights"]` | 窗口标题关键字 |
| `win32.screencap` | `printwindow` | `printwindow` / `gdi` / `screendc` |
| `win32.input` | `cursor` | `cursor`（真实光标+消息）/ `post` / `send` |
| `win32.anchor` | `[960,540]` | 鼠标停靠点（虚拟坐标），`null`=窗口中心 |
| `win32.parallax_wait` | `0.20` | 光标移动后等待视差稳定的秒数 |
| `win32.block_input` | `false` | 手势期间是否锁定物理鼠标 |
| `ocr_dir` | `""` | 留空用 MAA 的 `resource/PaddleOCR` |
| `layout` | `{}` | 坐标覆盖（适配 PC 端 UI 差异），见下方"官方 PC 端校准" |
| `leave_timeout` | `90` | 检测不到卫戍协议界面多久后停止（PC 端加载较慢） |
| `auto_elevate` | `true` | 非管理员时自动请求提权 |
| `log_dir` / `done_file` | `farm_logs` / `strategies_done.json` | 日志/截图与进度 |

### 官方 PC 端校准（重要）

PC 端的部分 HUD 与安卓版位置不同，实测**资金显示在顶部状态栏**，不在安卓版的右下角。
发布包里的 `settings.json` 已带 `layout` 覆盖：

```json
{
  "layout": { "GOLD_BOX": [1170, 20, 1265, 80] },
  "leave_timeout": 90
}
```

可覆盖的键就是业务逻辑里的常量名（如 `CARD_X`、`SELL`、`REFRESH`、`READY`、`BENCH_ROWS`、
`GRID_X`、`GRID_Y` 等），启动日志会打印 `[布局] 已应用坐标覆盖：...`。
`settings.pc-official.json` 是同内容的示例文件。

## 常见问题

**找不到游戏窗口 / 连到的是别的窗口**
运行 `GarrisonFarmPC.exe --list-windows` 查看窗口列表；确认游戏标题是「明日方舟」。
多开或特殊环境可在 `settings.json` 里改 `window_title`。

**截图全黑 / 点击没反应**
1) **先确认是管理员身份运行**（任务管理器里本程序需与游戏同为“高”完整性；程序会自动请求提权）；
2) 依次尝试 `win32.screencap` = `gdi` → `screendc`；`screendc` 需要窗口可见且不被遮挡。
3) HDR/独占全屏建议改成**窗口化 1920x1080**（实测窗口化下截图与坐标 1:1，最稳）。

**点击位置偏移 / 买卖不生效**
1) 确认游戏是 16:9 且 UI 缩放 100%（实测窗口化 1920x1080 时与 1920x1080 基准 1:1）；
2) 用 `--check --probe-tap` 看中央点击是否生效；
3) 加 `--debug` 看 `[debug] buy: ...` 行：若出现 `near=['无法购买']`，通常是**备战席已满**
   （买了但还没上场的干员占了位置），等程序完成部署或手动点一次「准备就绪」推进即可；
4) 若鼠标视差明显，调大 `parallax_wait`（如 0.3），或把 `anchor` 改成画面中不遮挡 UI 的位置。

**进对局后 Program 好像"卡住"了**
PC 端进入对局要加载 60~90 秒（会一直显示鹰角 logo）。程序已把加载画面排除在"离场保护"之外，
`--debug` 心跳里能看到 `阶段=截图+识别`。若长时间不动，看 `farm_logs` 里最新的 `unknown_*.png`。

**提示"没有找到 PaddleOCR 模型"**
安装 MAA 并至少启动一次，或在 `settings.json` 里用 `ocr_dir` 指向
包含 `det/inference.onnx`、`rec/inference.onnx`、`rec/keys.txt` 的目录。

**自检通过，但一开始就停**
程序要求先进入「卫戍协议」主界面（能看到「极速模拟」）。日更/公告/断线后要回到该界面重跑。

**和 MAA 冲突**
运行本程序时不要同时跑 MAA 的任务（两者会抢鼠标/设备）。程序检测到 MAA 在运行会提示。

## 目录结构

```
GarrisonFarmPC/
├─ GarrisonFarmPC.exe        （发布包）打包入口
├─ launcher.py               源码入口
├─ 开始刷角标.bat / start.bat 菜单启动
├─ setup.bat                 创建 .venv 并安装依赖
├─ settings.example.json     配置示例
├─ tiles.json                部署格坐标（拖拽视角，1920×1080）
├─ strategies_done.json      角标进度（自动生成）
├─ farm_logs/                run.log 与截图
├─ src/garrison_pc/          源码
│   ├─ app.py                启动/主循环
│   ├─ selfcheck.py          启动自检
│   ├─ maa.py                MAA 配置与模型
│   ├─ ocr.py                PaddleOCR 封装
│   ├─ runtime.py            运行时注入
│   ├─ device/win32.py       PC 端设备层
│   ├─ device/adb.py         模拟器设备层
│   └─ logic/garrison.py     业务逻辑（移植）
├─ src/parts/                逐函数还原的分片与移植测试
├─ tests/                    差分/设备/集成测试
├─ tools/                    组装与打包脚本
└─ docs/                     分析、调研、方案
```

## 测试

```bat
python tests\run_all.py          :: 全部（逻辑差分需要 Python 3.11）
python tests\test_win32_device.py :: 真实窗口上的截图/点击/滑动
python tests\test_app_check.py    :: 用真实窗口冒充游戏窗口跑 --check
```

覆盖范围与实测结果见 [验证报告](docs/03-验证报告.md)：
逻辑差分包 4126 项全通过；设备层、CLI 自检、主循环冒烟均通过。

## 来源与许可

- 业务逻辑移植自 [GarrisonFarm 个人优化版 v1.2](https://github.com/FJH3576/GarrisonFarm-Personal)
  （原始出处：B 站《利用 MAA 自动刷取卫戍协议蚀刻章镀层》）。
  该仓库**未声明开源许可证**，因此本项目按"个人自用/学习研究"定位；
  如需公开分发，请先取得原作者授权。
- MAA 的配置格式与 PaddleOCR 模型归 [MaaAssistantArknights](https://github.com/MaaAssistantArknights/MaaAssistantArknights)
  所有；本项目仅在运行时**读取用户本机的 MAA 安装目录**，不复制、不分发 MAA 的资源。
- Win32 截图/输入协议参考 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 的
  `MaaWin32ControlUnit` 实现（独立重写，未复制其代码）。

## 免责声明

- 本项目仅通过 Windows 公开 API 做**外部截图与输入注入**，不注入游戏进程、不修改游戏文件/内存。
- 游戏带 ACE 反作弊；使用任何自动化工具都存在风险，请自行评估并承担后果。
- 游戏活动/版本更新可能导致界面与坐标变化，届时需要重新校准。
