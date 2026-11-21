# 逆向还原作业说明（给协作者）

目标：把 CPython 3.11 字节码还原成**行为完全一致**的 Python 源码，用于新的 PC 端适配项目。
这是"移植"，不是"重写"：不允许改逻辑、改坐标、改字符串、改判定顺序，也不允许"顺手优化"。

## 1. 输入资料

- 每个函数一份规格文件：`D:\DSH\SHP_Auto\_ref\funcs\<序号>_<函数名>.txt`
  内含：参数、局部变量、`co_names`、**完整常量表**（含中文文案与坐标）、**完整字节码**、
  以及该函数内嵌套代码对象（推导式、内部函数）的字节码。
- 模块级常量表：`D:\DSH\SHP_Auto\_ref\funcs\MODULE_CONSTANTS.txt`
- 函数清单：`D:\DSH\SHP_Auto\_ref\funcs\MANIFEST.txt`
- 原始模块（可作为**行为参照/差分测试 oracle**）：`D:\DSH\SHP_Auto\_ref\orig_garrison.py`
  用 Python 3.11 加载：`D:\DSH\SHP_Auto\_tools\py311\python.exe`（3.12/3.13 不能读 3.11 字节码）

## 2. 输出

- 写入分配给你的文件：`D:\DSH\SHP_Auto\GarrisonFarmPC\src\parts\part_X.py`
- 文件里**只放函数定义**（按分配顺序），不要 `import`、不要常量、不要 `if __name__`、
  不要解释性文字/测试代码（测试写到单独文件）。
- 缩进 4 空格；保留原始字符串（中文全角/半角、空格、括号、`·`、`％` 等一律照抄）。
- 允许使用模块级已提供的名字：`json, os, re, time, unicodedata, np, cv2`，以及全局常量
  （`GRID_X, GRID_Y, GRID_TOP, GRID_BOTTOM, ROW_H, PRIORITY_FULL, SAFE_KEYS_FULL,
  PRIORITY_LOW, SAFE_KEYS_LOW, PRIORITY, SAFE_KEYS, PROFILE, TARGET, CARD_X, CARD_Y,
  GOLD_BOX, UPX, CARDS, SELL, REFRESH, READY, DPS, HEALERS, ROMAN, LAST_TIER, LAST_TILE,
  LAST_NAME, BENCH_ROWS, GOLD_FAIL, GENERIC, GARRISON, LEAVE_TIMEOUT, STALL_TIMEOUT, LAYOUT`），
  以及已实现的辅助函数 `shot, tap, swipe, touch, drag_path, ocr, find, numrec, num, log,
  save, load_done, save_done, set_profile, match_key, prio_index, is_safe_op, rank, Board,
  read_shop, is_healer, is_dps, shop_cards, buy, green_tiles, right3, bench_ops, load_layout,
  is_green, drag_name, near, deploy_from_bench, deploy_from_bench_old, tile_order, tile_xy,
  deploy_layout, sell_at, in_facing_mode, set_facing, slots_left, locate_new, new_bench_slot,
  sell_lowest, buy_and_deploy, deploy_bench, handle_popups, read_gold, gold_now,
  shop_signature, yellow_ratio, has_color_badge, has_badge, passed_count, grid_shift,
  detect_rows, scroll_grid, strategy_name, pick_strategy, pick_squad, prep_phase`。

## 3. 字节码阅读要点（3.11）

- `LOAD_CONST i` 取常量表第 i 项；`LOAD_GLOBAL NULL + f` 是全局函数/常量 f（`NULL` 是调用约定，忽略）。
- `PRECALL n` + `CALL n`：n 个位置参数；若前面有 `KW_NAMES ('a','b')`，则最后 len 个是关键字参数，
  其名字来自常量表那一项。
- `BINARY_OP +` / `-` / `*` / `/` / `//` / `%`；`COMPARE_OP <=` 等；`CONTAINS_OP` 是 `in` / `not in`。
- `POP_JUMP_FORWARD_IF_FALSE` = if 假则跳；`..._IF_NONE` / `..._IF_NOT_NONE` 同理。
- `FOR_ITER` 循环；`JUMP_BACKWARD` 回跳；`BUILD_LIST`/`BUILD_TUPLE`/`BUILD_CONST_KEY_MAP` 构造容器。
- `LOAD_METHOD` + `PRECALL/CALL` = 方法调用；`LOAD_ATTR` = 属性访问。
- 推导式/生成器出现在常量表的 `<code ...>` 项里，规格文件末尾单独给出了它们的字节码。
- `SWAP 2` / `COPY 1` 多是 `a, b = b, a` 或链式调用，按语义还原即可。
- `CALL_FUNCTION_EX` 表示 `*args` 展开调用。
- 装饰器/默认参数已体现在 `MAKE_FUNCTION` 前的常量与 `co_varnames` 上；默认值见常量表。
- 布尔短路（`and`/`or`）编译成条件跳转，按语义还原成 `and`/`or`，不要写成嵌套 if。
- 三目表达式 `A if C else B` 编译成两段跳转 + `BUILD_STRING`/`FORMAT_VALUE` 常见于 f-string，
  注意 `FORMAT_VALUE` 的格式说明来自常量表（如 `.1f`）。

## 4. 必须做的验证（差分测试）

对**纯函数**（不调用 tap/shot/ocr/log 等）必须与 oracle 对比：

```python
# 保存在 src/parts/test_part_x.py，用 3.11 运行
import sys, random
sys.path.insert(0, r'D:\DSH\SHP_Auto\_ref')
import orig_garrison

orig = orig_garrison.load()
new = orig_garrison.load()
exec(open(r'D:\DSH\SHP_Auto\GarrisonFarmPC\src\parts\part_X.py', encoding='utf-8').read(), new)

cases = [ ... ]          # 覆盖边界：空列表/单元素/中文名/未知名/超大数
for args in cases:
    a = orig['rank'](*args)
    b = new['rank'](*args)
    assert a == b, (args, a, b)
print('rank ok', len(cases))
```

- 有随机性的地方用固定种子，尽量跑 ≥200 组随机输入（名字取自常量 `PRIORITY`/`DPS`/`HEALERS` 等）。
- 对**有副作用**的函数（调用 shot/tap/ocr），用"录制器"对比调用序列：

```python
def make_ns(mod, records):
    ns = mod
    ns['shot'] = lambda: records.append(('shot',)) or FAKE_IMG
    ns['tap'] = lambda x, y, wait=0.6: records.append(('tap', x, y, wait))
    ns['ocr'] = lambda img, box=None: OCR_SCRIPT.pop(0)
    return ns
```

   让 oracle 与你的实现跑同一份脚本化输入（同样的假截图/假 OCR 结果），比较
   `records` 序列与返回值是否一致。若某函数依赖真实图像处理无法构造，请在报告里注明。

- 差分测试文件保留在 `src/parts/` 下，命名 `test_part_X.py`。

## 5. 报告

最后一条消息请给出：
1. 已还原的函数清单与它们与 oracle 的对比结果（通过/失败/未测）；
2. 任何"字节码有歧义、凭语义推断"的位置（列出函数名 + 判断理由）；
3. 未能测试的函数及原因。
