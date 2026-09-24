# 淘宝归类 v2 扩大覆盖（出售中商品支持）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让淘宝店铺分类批量归类覆盖出售中商品（编辑提交后保持出售中），并重采重建 plan、832 个 failed 全部从头重跑。

**Architecture:** 扩展现有 `assign_shop_category_v2.py` 体系：collect 脚本支持采出售中列表 → plan builder 合并重建（旧判定保留+新商品 classify）→ v2 主流程把「必须放入仓库」硬校验改为「读当前状态原样维持」。执行顺序由 todo 排序保证：出售中 → 仓库 → failed 尾部。

**Tech Stack:** Python 3.9（`automation/venv/bin/python`）+ Playwright async + CDP 9222 窗口模式 Chrome。无 pytest——纯逻辑用 assert 自检脚本直跑。

**Spec:** `docs/superpowers/specs/2026-09-24-shop-cat-v2-onsale-design.md`（commit b4006e5）

## Global Constraints

- venv 统一 `automation/venv/bin/python`（3.9.6，代码必须 3.9 兼容）
- 调价只限「家居服/睡衣」「美甲」两类（`PRICE_CATS`，用户指令勿扩）；调价规则=货源价+130
- 八类目规则与 `classify()` 优先级**不改**：美甲→牛仔短裤→秋冬款→半身裙→连衣裙→长裤（排除套装词）→家居服/睡衣→other
- 旧 plan 1942 条的 `category` 判定**原样保留**（done 866 复核依赖），只有新商品走 classify
- failed 832 **全部**从头重跑（`--retry-failed`），不做按错误类型的选择性队列
- 进度文件沿用 `shop_cat_v2_progress.json`（done/skipped 按 itemId 跳过）
- 所有 Chrome 操作走 CDP 9222 **窗口模式**（提交类禁 headless）；统一 `cdp_utils.connect_cdp`；每商品 `ctx.new_page()` 用完即关
- 翻页必须点「下一页」按钮（goto 改 current 无效）
- 工作目录：`automation/sourcing/`；git 仓库根：`ideaProject/spzx-parent/`（automation 已入库）
- 数据/缓存/登录态（*.jsonl、chrome-profile 等）已 gitignore，勿提交

---

### Task 1: collect_in_stock_current.py 支持 `--list sold_out`

**Files:**
- Modify: `automation/sourcing/collect_in_stock_current.py`
- Create: `automation/sourcing/test_collect_list.py`（纯逻辑自检）
- Create（运行产物，gitignore）: `automation/sourcing/taobao_onsale_current.jsonl`

**Interfaces:**
- Produces: 常量 `URLS = {'in_stock': ..., 'sold_out': ...}`、`OUT_FILES = {'in_stock': 'taobao_in_stock_current.jsonl', 'sold_out': 'taobao_onsale_current.jsonl'}`（模块级，Task 2 与运维依赖）；CLI `--list in_stock|sold_out|both`（默认 in_stock，向后兼容）
- Produces: `taobao_onsale_current.jsonl` 每行 `{"itemId": "...", "title": "..."}`（与现有 in_stock 文件同构）

- [ ] **Step 1: 写自检脚本（先失败）**

`automation/sourcing/test_collect_list.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_in_stock_current 纯逻辑自检: URL/OUT 映射与参数解析. 直跑: venv/bin/python test_collect_list.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_mappings():
    import collect_in_stock_current as c
    assert 'sold_out' in c.URLS and 'SellManage/sold_out' in c.URLS['sold_out']
    assert 'in_stock' in c.URLS and 'SellManage/in_stock' in c.URLS['in_stock']
    assert c.OUT_FILES['sold_out'].endswith('taobao_onsale_current.jsonl')
    assert c.OUT_FILES['in_stock'].endswith('taobao_in_stock_current.jsonl')


def test_parse_args_default():
    import collect_in_stock_current as c
    lists, rest = c.parse_lists(['--limit', '5'])
    assert lists == ['in_stock']          # 默认行为不变
    lists2, rest2 = c.parse_lists(['--list', 'both', '--limit', '5'])
    assert lists2 == ['in_stock', 'sold_out']
    assert rest2 == ['--limit', '5']
    lists3, _ = c.parse_lists(['--list', 'sold_out'])
    assert lists3 == ['sold_out']


if __name__ == '__main__':
    test_mappings()
    test_parse_args_default()
    print('PASS: collect list mappings/args')
```

- [ ] **Step 2: 跑自检确认失败**

Run: `cd automation/sourcing && ../venv/bin/python test_collect_list.py`
Expected: `AttributeError: module 'collect_in_stock_current' has no attribute 'URLS'`

- [ ] **Step 3: 实现**

`collect_in_stock_current.py` 改动（保留全部现有函数与翻页/去重/断点逻辑）：

1. 文件头常量区（原 `CDP_PORT`/`FIRST_URL`/`OUT` 附近）替换为：

```python
CDP_PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
URLS = {
    'in_stock': "https://myseller.taobao.com/home.htm/SellManage/in_stock?current=1&pageSize=20",
    'sold_out': "https://myseller.taobao.com/home.htm/SellManage/sold_out?current=1&pageSize=20",
}
OUT_FILES = {
    'in_stock': os.path.join(BASE, "taobao_in_stock_current.jsonl"),
    'sold_out': os.path.join(BASE, "taobao_onsale_current.jsonl"),
}
FIRST_URL = URLS['in_stock']   # 兼容旧引用
OUT = OUT_FILES['in_stock']    # 兼容旧引用
```

2. 新增参数解析（放在 `append_items` 之后）：

```python
def parse_lists(argv):
    """argv(不含脚本名) -> (要采集的列表名列表, 剩余参数). --list both = 两个都采"""
    lists = ['in_stock']
    rest = []
    i = 0
    while i < len(argv):
        if argv[i] == '--list':
            val = argv[i + 1]
            assert val in ('in_stock', 'sold_out', 'both'), f'未知 --list {val}'
            lists = ['in_stock', 'sold_out'] if val == 'both' else [val]
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    return lists, rest
```

3. `main()` 改造：现有 `limit`/`restart` 解析与采集循环整体包进 `async def run_collect(name, limit, restart, b, ctx)`（原 main 的第 92-154 行主体原样搬入，把 `OUT` 换成 `OUT_FILES[name]`、`FIRST_URL` 换成 `URLS[name]`、日志加 `[name]` 前缀）；新 main：

```python
async def main():
    lists, rest = parse_lists(sys.argv[1:])
    limit = 0
    if '--limit' in rest:
        limit = int(rest[rest.index('--limit') + 1])
    restart = '--restart' in rest

    b, ctx = await connect_cdp(CDP_PORT, keep_urls=["myseller.taobao.com"], log=log)
    try:
        for name in lists:
            log(f"=== 采集列表 {name} ===")
            await run_collect(name, limit, restart, b, ctx)
    finally:
        await b.close()
```

注意：`run_collect` 内原有的 `page` 查找/goto/翻页/写文件逻辑**逐行平移**，不要改行为；`load_existing()`/`append_items()` 已按 `OUT` 形参化（把这两个函数改为接收 `out_path` 参数，调用点同步）。

- [ ] **Step 4: 跑自检确认通过**

Run: `../venv/bin/python test_collect_list.py`
Expected: `PASS: collect list mappings/args`

- [ ] **Step 5: 实采验证（小批量，9222 在线前提下）**

Run: `../venv/bin/python collect_in_stock_current.py --list sold_out --limit 30`
Expected: 日志 `[sold_out] 页1: 本页20个 …`，`taobao_onsale_current.jsonl` 生成且 ≤30 行、行结构 `{"itemId":...,"title":...}`；再跑一次同命令确认断点续跑（新增 10 个后到 30 上限或直接完成）。核对 9222 Chrome：`curl -s http://127.0.0.1:9222/json/version`（不在线则先按 AGENTS.md 窗口模式命令启动，末尾带初始 URL）。

- [ ] **Step 6: 全量采集出售中（~2300 个，约 15-20 分钟）**

Run: `nohup ../venv/bin/python collect_in_stock_current.py --list sold_out > collect_onsale.log 2>&1 &`
完成后核对：`wc -l taobao_onsale_current.jsonl` 应 ≥2200 行（与诊断实测 2253 同量级）。

- [ ] **Step 7: Commit**

```bash
git add automation/sourcing/collect_in_stock_current.py automation/sourcing/test_collect_list.py
git commit -m "feat(sourcing): collect_in_stock_current 支持采集出售中列表(--list sold_out)"
```

---

### Task 2: build_shop_cat_plan.py 合并重建（--merge）

**Files:**
- Modify: `automation/sourcing/build_shop_cat_plan.py`
- Create: `automation/sourcing/test_plan_merge.py`
- Modify（产物，gitignore）: `automation/sourcing/shop_cat_plan.json`

**Interfaces:**
- Consumes: Task 1 的 `taobao_onsale_current.jsonl`；现有 `taobao_in_stock_current.jsonl`（09-13 旧文件，仍有仓库池基线价值）；现有 `shop_cat_plan.json`（1942 条旧判定）
- Produces: `build_merge_plan(old_plan, in_stock_rows, onsale_rows) -> (list, int)`（纯函数，Task 3 不依赖但运维核对用）；plan 条目结构 `{"itemId": str, "title": str, "category": str, "pool": "onsale"|"warehouse"|"gone"}`；CLI `--merge --in-stock <file> --onsale <file>`
- 约束: 旧 plan 已有 itemId 的 `category` **原样保留**；pool 判定 onsale 优先（同一 ID 同时出现在两个文件时归 onsale）

- [ ] **Step 1: 写自检脚本（先失败）**

`automation/sourcing/test_plan_merge.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_shop_cat_plan 合并逻辑自检. 直跑: venv/bin/python test_plan_merge.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_shop_cat_plan import build_merge_plan, classify


def test_old_category_preserved():
    old = [{'itemId': '1', 'title': '纯棉睡衣女', 'category': '秋冬款'}]  # 旧判定故意与新规则不同
    instock = [('1', '纯棉睡衣女')]
    onsale = []
    plan, new_n = build_merge_plan(old, instock, onsale)
    assert new_n == 0
    rec = [p for p in plan if p['itemId'] == '1'][0]
    assert rec['category'] == '秋冬款'          # 原样保留, 不重判
    assert rec['pool'] == 'warehouse'


def test_new_items_classified_and_pool():
    old = []
    instock = [('2', '珊瑚绒睡裙女冬季加厚')]
    onsale = [('3', '穿戴甲成品手工甲片'), ('4', '牛仔短裤女夏季')]
    plan, new_n = build_merge_plan(old, instock, onsale)
    assert new_n == 3
    m = {p['itemId']: p for p in plan}
    assert m['2']['category'] == classify('珊瑚绒睡裙女冬季加厚') and m['2']['pool'] == 'warehouse'
    assert m['3']['category'] == '美甲' and m['3']['pool'] == 'onsale'
    assert m['4']['category'] == '牛仔短裤' and m['4']['pool'] == 'onsale'


def test_gone_and_onsale_priority():
    old = [{'itemId': '5', 'title': 'x', 'category': 'other'}]
    plan, _ = build_merge_plan(old, [], [])           # 两个池都没有 -> gone
    assert plan[0]['pool'] == 'gone'
    old2 = [{'itemId': '6', 'title': 'x', 'category': 'other'}]
    plan2, _ = build_merge_plan(old2, [('6', 'x')], [('6', 'x')])  # 双池同时出现 -> onsale 优先
    assert plan2[0]['pool'] == 'onsale'


if __name__ == '__main__':
    test_old_category_preserved()
    test_new_items_classified_and_pool()
    test_gone_and_onsale_priority()
    print('PASS: plan merge')
```

- [ ] **Step 2: 跑自检确认失败**

Run: `../venv/bin/python test_plan_merge.py`
Expected: `ImportError: cannot import name 'build_merge_plan'`

- [ ] **Step 3: 实现**

`build_shop_cat_plan.py` 新增（`classify` 之后、`main` 之前）：

```python
def load_jsonl_rows(path):
    rows = []
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if line:
                r = json.loads(line)
                rows.append((str(r['itemId']), r.get('title', '')))
    return rows


def build_merge_plan(old_plan, in_stock_rows, onsale_rows):
    """旧判定原样保留 + 新商品 classify; pool: onsale > warehouse > gone. 返回 (plan列表, 新增数)"""
    onsale_ids = {iid for iid, _ in onsale_rows}
    instock_ids = {iid for iid, _ in in_stock_rows}
    titles = {}
    for iid, t in in_stock_rows + onsale_rows:
        titles[iid] = t
    merged = {}
    for p in old_plan:
        iid = str(p['itemId'])
        pool = 'onsale' if iid in onsale_ids else ('warehouse' if iid in instock_ids else 'gone')
        merged[iid] = {'itemId': iid,
                       'title': p.get('title') or titles.get(iid, ''),
                       'category': p['category'],
                       'pool': pool}
    new_n = 0
    for iid, t in onsale_rows + in_stock_rows:
        if iid not in merged:
            merged[iid] = {'itemId': iid, 'title': t, 'category': classify(t),
                           'pool': 'onsale' if iid in onsale_ids else 'warehouse'}
            new_n += 1
    return list(merged.values()), new_n
```

`main()` 加参数与分支：

```python
    ap.add_argument('--merge', action='store_true', help='合并重建: 旧判定保留, 新商品classify')
    ap.add_argument('--in-stock', default=os.path.join(BASE, 'taobao_in_stock_current.jsonl'))
    ap.add_argument('--onsale', default=os.path.join(BASE, 'taobao_onsale_current.jsonl'))
```

`main()` 体内、读 `args.input` 之前：

```python
    if args.merge:
        old_plan = json.load(open(args.output, encoding='utf-8')) if os.path.exists(args.output) else []
        instock_rows = load_jsonl_rows(args.in_stock)
        onsale_rows = load_jsonl_rows(args.onsale)
        plan, new_n = build_merge_plan(old_plan, instock_rows, onsale_rows)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(plan, f, ensure_ascii=False, indent=1)
        from collections import Counter
        buckets = Counter(p['category'] for p in plan)
        pools = Counter(p['pool'] for p in plan)
        print(f'合并完成: 共 {len(plan)} 个 (新增 {new_n})')
        print('pool 分布:', dict(pools))
        for c in CATS:
            print(f'  {c:<8} {buckets[c]:>5}')
        print(f'-> {args.output}')
        return
```

（原有非 merge 路径不动。）

- [ ] **Step 4: 跑自检确认通过**

Run: `../venv/bin/python test_plan_merge.py`
Expected: `PASS: plan merge`

- [ ] **Step 5: 真实数据合并 + 人工核对**

Run:
```bash
cp shop_cat_plan.json shop_cat_plan.backup_20260924.json
../venv/bin/python build_shop_cat_plan.py --merge
```
核对三件事：① 总数 ≈ 1942 + 出售中新增（≈2000+）且 pool 分布 onsale≈2250 / warehouse≈1900 / gone 少量；② 抽 3 个 done 的旧商品（如 `1005736775359`）确认 `category` 与 `shop_cat_v2_progress.json` 提交时一致（家居服/睡衣 等旧判定）；③ 抽 5 个新出售中穿戴甲商品确认 `category=美甲`。任一不符 → 停止，回查 build_merge_plan。

- [ ] **Step 6: Commit**

```bash
git add automation/sourcing/build_shop_cat_plan.py automation/sourcing/test_plan_merge.py
git commit -m "feat(sourcing): build_shop_cat_plan 支持合并重建(--merge), plan 条目带 pool"
```

---

### Task 3: v2 主流程 todo 过滤/排序抽出为纯函数（出售中优先 + failed 尾部）

**Files:**
- Modify: `automation/sourcing/assign_shop_category_v2.py:373-395`（main 内 plan/进度/todo 段）
- Create: `automation/sourcing/test_v2_todo.py`

**Interfaces:**
- Produces: `build_todo(plan, prog, retry_failed=False, start=0, limit=0, test=False) -> list`（纯函数）；排序键 = failed→2，pool onsale→0，warehouse→1，其他(gone)→2；**先过滤→再排序→最后切 limit/test**（探路 `--limit 3` 必须命中出售中头部）
- 消费: plan 条目的 `pool` 字段（Task 2 产出；旧字段缺失时按 warehouse 处理）

- [ ] **Step 1: 写自检脚本（先失败）**

`automation/sourcing/test_v2_todo.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2 build_todo 纯逻辑自检. 直跑: venv/bin/python test_v2_todo.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assign_shop_category_v2 import build_todo


def prog():
    return {'done': ['d1'], 'skipped': ['s1'], 'failed': {'f1': {'category': 'x', 'error': 'e'}},
            'noprice': [], 'sizegap': {}}


PLAN = [
    {'itemId': 'w1', 'category': '长裤', 'pool': 'warehouse'},
    {'itemId': 'f1', 'category': '美甲', 'pool': 'onsale'},      # failed -> 尾部
    {'itemId': 'o1', 'category': '美甲', 'pool': 'onsale'},
    {'itemId': 'g1', 'category': 'other', 'pool': 'gone'},
    {'itemId': 'd1', 'category': '长裤', 'pool': 'warehouse'},   # done -> 剔除
    {'itemId': 'o2', 'category': 'other', 'pool': 'onsale'},     # 无 pool 旧数据按 warehouse
]


def test_order_and_filter():
    todo = build_todo(PLAN, prog(), retry_failed=True)
    ids = [r['itemId'] for r in todo]
    assert 'd1' not in ids and 's1' not in ids     # done/skipped 剔除
    assert ids == ['o1', 'o2', 'w1', 'g1', 'f1']   # onsale -> warehouse -> gone -> failed


def test_limit_hits_onsale_head():
    todo = build_todo(PLAN, prog(), retry_failed=True, limit=2)
    assert [r['itemId'] for r in todo] == ['o1', 'o2']   # 排序后切片, 探路命中出售中


def test_no_retry_failed_excludes():
    todo = build_todo(PLAN, prog(), retry_failed=False)
    assert 'f1' not in [r['itemId'] for r in todo]


def test_legacy_no_pool_field():
    plan = [{'itemId': 'x1', 'category': '长裤'}]        # 旧 plan 无 pool
    todo = build_todo(plan, prog())
    assert [r['itemId'] for r in todo] == ['x1']         # 按 warehouse 兜底, 不报错


if __name__ == '__main__':
    test_order_and_filter()
    test_limit_hits_onsale_head()
    test_no_retry_failed_excludes()
    test_legacy_no_pool_field()
    print('PASS: v2 build_todo')
```

- [ ] **Step 2: 跑自检确认失败**

Run: `../venv/bin/python test_v2_todo.py`
Expected: `ImportError: cannot import name 'build_todo'`

- [ ] **Step 3: 实现**

`assign_shop_category_v2.py`：在 `main()` 之前新增：

```python
def build_todo(plan, prog, retry_failed=False, start=0, limit=0, test=False):
    """过滤 done/skipped/failed(可选重试) 后按 出售中->仓库->gone/failed 排序; limit/test 在排序后切片"""
    done = set(prog['done'])
    skipped = set(prog['skipped'])
    failed_ids = set(prog['failed'].keys())
    todo = [r for r in plan[start:] if str(r['itemId']) not in done and str(r['itemId']) not in skipped
            and (retry_failed or str(r['itemId']) not in failed_ids)]

    def sort_key(r):
        iid = str(r['itemId'])
        if iid in failed_ids:
            return 2
        pool = r.get('pool', 'warehouse')
        return 0 if pool == 'onsale' else (1 if pool == 'warehouse' else 2)

    todo.sort(key=sort_key)
    if test:
        todo = todo[:1]
    elif limit:
        todo = todo[:limit]
    return todo
```

`main()` 内原 383-394 行替换为：

```python
    plan = load_plan()
    prog = load_progress()
    todo = build_todo(plan, prog, retry_failed=retry_failed, start=start, limit=limit, test=test)
    my_ids = {str(r['itemId']) for r in todo}
    failed_ids = set(prog['failed'].keys())
```

（后续 `log(f"计划 {len(plan)} 个, ...")` 与主循环不动；`failed_ids` 原在过滤时定义，日志用到则保留此行。）

- [ ] **Step 4: 跑自检确认通过**

Run: `../venv/bin/python test_v2_todo.py`
Expected: `PASS: v2 build_todo`

- [ ] **Step 5: Commit**

```bash
git add automation/sourcing/assign_shop_category_v2.py automation/sourcing/test_v2_todo.py
git commit -m "feat(sourcing): v2 todo 抽纯函数 build_todo, 排序 出售中->仓库->failed尾部"
```

---

### Task 4: 上架状态原样维持（核心行为改动）+ 在售探路

**Files:**
- Modify: `automation/sourcing/assign_shop_category_v2.py:308-310`（process_one 内 check_listing_mode 校验段）
- Create: `automation/sourcing/probe_item_state.py`（探路验证工具，保留）

**Interfaces:**
- Consumes: `check_listing_mode(page)`（assign_shop_category.py:139-152，**不改**，纯读取）
- Produces: 常量 `LISTING_OK_STATES = ('放入仓库', '立刻上架')`；probe CLI `python probe_item_state.py <itemId> [<itemId>...]` → 每行打印 `itemId | 上架状态=<txt> | 分类=<tags>`（只读编辑页，不点击不提交）

- [ ] **Step 1: 改 v2 校验逻辑**

`assign_shop_category_v2.py` 顶部常量区（`PRICE_CATS` 旁）加：

```python
LISTING_OK_STATES = ('放入仓库', '立刻上架')   # 仓库商品维持待上架; 在售商品维持出售中(用户指令 2026-09-24)
```

`process_one` 内原（约 308-310 行）：

```python
        lm = await check_listing_mode(page)
        if not lm.get('ok') or '放入仓库' not in lm.get('txt', ''):
            return 'fail', f'上架时间非放入仓库: {lm.get("txt")}', None
```

替换为：

```python
        lm = await check_listing_mode(page)
        if not lm.get('ok'):
            return 'fail', f'上架状态读取失败: {lm.get("txt")}', None
        if not any(s in lm.get('txt', '') for s in LISTING_OK_STATES):
            return 'fail', f'上架状态异常: {lm.get("txt")}', None
```

（不点击任何 radio，表单原样提交——仓库商品保持放入仓库，在售商品保持立刻上架。）

- [ ] **Step 2: 写探路验证工具 probe_item_state.py**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读探测商品编辑页当前状态: 上架状态radio + 店铺分类tags. 绝不点击提交.
用法: venv/bin/python probe_item_state.py <itemId> [...]"""
import asyncio
import sys
import time
from cdp_utils import connect_cdp
from assign_shop_category import wait_edit_ready, scroll_edit_page

EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def probe(ctx, item_id):
    page = None
    try:
        page = await ctx.new_page()
        await page.goto(EDIT_URL.format(id=item_id), timeout=60000, wait_until='domcontentloaded')
        title = await wait_edit_ready(page, timeout=40)
        if not title:
            return f"{item_id} | 加载失败"
        await scroll_edit_page(page)
        await asyncio.sleep(1)
        state = await page.evaluate("""() => {
            const el = document.querySelector('#sell-field-startTime');
            if (!el) return 'NO_FIELD';
            for (const w of el.querySelectorAll('.next-radio-wrapper, .radio-item')) {
                const checked = w.getAttribute('aria-checked')==='true' || w.classList.contains('checked') || (w.querySelector('input')||{}).checked;
                if (checked) return (w.textContent||'').trim().slice(0, 20);
            }
            return 'NONE_SELECTED';
        }""")
        tags = await page.evaluate("""() => {
            const box = document.querySelector('#sell-field-shopcat');
            if (!box) return 'NO_FIELD';
            return Array.from(box.querySelectorAll('.next-tag')).map(t => t.textContent.trim());
        }""")
        return f"{item_id} | 上架状态={state} | 分类={tags} | {title[:20]}"
    except Exception as e:
        return f"{item_id} | ERR: {str(e)[:60]}"
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass


async def main():
    ids = [a for a in sys.argv[1:] if a.isdigit()]
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    try:
        for iid in ids:
            log(await probe(ctx, iid))
            await asyncio.sleep(2)
    finally:
        await b.close()


if __name__ == '__main__':
    asyncio.run(main())
```

- [ ] **Step 3: 探路（出售中池前 3 个）**

前置：9222 窗口模式在线且已登录（`curl -s http://127.0.0.1:9222/json/version`）。

Run: `../venv/bin/python assign_shop_category_v2.py --test`（单商品冒烟，plan 头部应为 onsale 池）
然后 Run: `../venv/bin/python assign_shop_category_v2.py --limit 3 2>&1 | tee trail_run.log`
Expected: 3 条日志均 `✓ … 类目=…`；无 `risk`。

- [ ] **Step 4: 验证探路结果（spec 验收标准 #1）**

从 trail_run.log 取 3 个 itemId，逐个：

Run: `../venv/bin/python probe_item_state.py <id1> <id2> <id3>`
Expected（三项全过才算过）：
1. `上架状态=立刻上架`（仍在售）
2. `分类=[目标类目]`（分类正确写入）
3. 日志中有货源价且类目∈(家居服/睡衣,美甲) 的，价格按 货源价+130 生效（无货源价或非目标类目则跳过此项）

任一项不符 → **停止放量**，回 Task 4 Step 1 检查（radio 是否被误动/提交语义），排查后再探路。

- [ ] **Step 5: Commit**

```bash
git add automation/sourcing/assign_shop_category_v2.py automation/sourcing/probe_item_state.py
git commit -m "feat(sourcing): v2 上架状态原样维持(支持在售商品), 附只读探测工具"
```

---

### Task 5: 全量执行启动 + 运维交接

**Files:**
- Delete: `automation/sourcing/diag_cat_list.py`, `diag_cat_nav.py`, `diag_cat_onsale.py`, `diag_cat_filter.py`, `diag_cat_link.py`, `diag_cat_mgmt.py`, `diag_cat_page.py`, `diag_cat_page2.py`, `diag_cat_sample.py`, `diag_onsale_full.py`, `diag_onsale_done.py`（诊断一次性脚本，结论已沉淀 spec）
- 运行产物: `automation/sourcing/cat_v2_run.log`（自愈循环日志，gitignore）

**Interfaces:**
- Consumes: Task 1-4 全部产物；`run_cat_v2.sh`（不改，自愈循环 + shlock 单实例锁）
- Produces: 后台常驻运行 `run_cat_v2.sh --retry-failed`（出售中 ~2000 → 仓库 440 → failed 832 尾部）

- [ ] **Step 1: 清理诊断脚本**

```bash
cd automation/sourcing && rm diag_cat_list.py diag_cat_nav.py diag_cat_onsale.py diag_cat_filter.py diag_cat_link.py diag_cat_mgmt.py diag_cat_page.py diag_cat_page2.py diag_cat_sample.py diag_onsale_full.py diag_onsale_done.py
git add -A . && git commit -m "chore(sourcing): 清理归类诊断一次性脚本(结论已入 spec)"
```

（`taobao_onsale_ids.json`、`diag_cat_result.json` 为 gitignore 数据，留本地备查。）

- [ ] **Step 2: 起跑前检查**

```bash
pgrep -fl "assign_shop_category_v2|run_cat_v2" || echo 无实例
curl -s http://127.0.0.1:9222/json/version | head -c 60
../venv/bin/python build_shop_cat_plan.py --merge   # 确认 plan 终态
```
Expected: 无运行实例；9222 在线；plan 总数/分布与 Task 2 Step 5 一致。

- [ ] **Step 3: 后台启动全量跑**

```bash
nohup ./run_cat_v2.sh --retry-failed > /dev/null 2>&1 &
sleep 20 && tail -5 cat_v2_run.log
```
Expected: 日志出现 `=== v2 第 1/20 轮启动 ===` 与 `[1/xxxx] <itemId> -> <类目> (货源价=...)`，头部为 onsale 池商品。

- [ ] **Step 4: 首小时观察点（全部满足才算交接完成）**

1. `grep -c "✓" cat_v2_run.log` 随时间增长，且无连续 `⚠ 风控`（RGV587 自愈属正常，连续多轮风控需人工滑块——AGENTS.md 红线）
2. `grep "上架状态异常\|上架状态读取失败" cat_v2_run.log` 为 0（新校验不误伤）
3. 进度文件在涨：`python3 -c "import json;d=json.load(open('shop_cat_v2_progress.json'));print(len(d['done']))"`
4. 30 分钟抽 2 个新 done 的 onsale 商品跑 `probe_item_state.py`，上架状态仍=立刻上架

- [ ] **Step 5: 交接说明（输出给用户，不 commit）**

汇报：预计总时长（~2900 个 × 60-80s + 风控冷却，约 2-3 天）、自愈机制（exit 42 自动降级+冷却续跑，无需人工）、人工介入条件（连续多轮风控滑块 / Chrome 9222 挂死重启法 / cron 守卫已自动让路）、监控命令（`tail -f cat_v2_run.log`）。

---

## Self-Review 结论

- **Spec 覆盖**: 数据管道（Task 1-2）、状态自适应（Task 4）、顺序与重试（Task 3 + 启动参数 `--retry-failed`）、探路与验收（Task 4）、运维（Task 5）——全覆盖；「不做的事」未引入。
- **占位符**: 无 TBD/TODO；所有代码块为完整可粘贴实现。
- **类型一致性**: `build_merge_plan(old_plan, in_stock_rows, onsale_rows)`、`build_todo(plan, prog, retry_failed, start, limit, test)`、`URLS/OUT_FILES/LISTING_OK_STATES` 各任务引用一致；plan 条目 `pool` 字段命名统一。
- **风险提示**: v2 `main()` 内 `failed_ids` 原定义于过滤段，Task 3 抽函数后在 main 里补一行定义（已写入步骤）；`--start` 与排序组合语义 = 先切 start 再过滤排序，与旧行为兼容。
