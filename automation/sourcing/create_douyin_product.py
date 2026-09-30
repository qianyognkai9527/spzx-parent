"""create_douyin_product.py — 抖店后台新建商品(发布/下架)

流程: 自启有窗口 Chrome for Testing (登录态 /tmp/chrome-douyin-create, 重启即清要扫码,
      不连 9223 CDP) -> 新建页 -> 选类目(居家服/睡衣, 在"下一步"之前) -> 完整表单
      (标题/价格/尺码表/运费模板/商品状态=下架) -> 发布商品。
进度持久化 douyin_create_progress.json (原子写), 可断点续跑, batch 只跳过 status=saved。
用法:
  python create_douyin_product.py --dyId <offerId> [--test]   # 单个 (test只走到完整表单不发布)
  python create_douyin_product.py --batch N [--test]          # 批量前N个未处理的
  --data / --progress 可覆盖默认路径。
"""
import asyncio
import json
import os
import random
import re
import sys
import time
import pymysql
from playwright.async_api import async_playwright
from shop_ref import default_shop_id, PLATFORM_DOUYIN

CDP = "http://127.0.0.1:9223"
DATA = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/douyin_product_data.jsonl"
PROGRESS = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/douyin_create_progress.json"
STOCK_SRC = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/guiruo_dropship_data.jsonl"
MIN_STOCK = 20
CREATE_URL = "https://fxg.jinritemai.com/ffa/g/create"
LIST_URL = "https://fxg.jinritemai.com/ffa/g/list"
DB = dict(host="127.0.0.1", user="root", password="root123456", database="db_spzx", port=3306)
DELAY_MIN, DELAY_MAX = 8, 15


def resolve_paths():
    """支持 --data / --progress 覆盖默认路径(独立批次用不同文件)"""
    global DATA, PROGRESS
    args = sys.argv[1:]
    if '--data' in args:
        DATA = args[args.index('--data') + 1]
    if '--progress' in args:
        PROGRESS = args[args.index('--progress') + 1]
    os.makedirs(os.path.dirname(PROGRESS) or '.', exist_ok=True)

sys.path.insert(0, "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing")
from gen_optimization_package import clean_title, pricing  # noqa: E402


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_done():
    if os.path.exists(PROGRESS):
        try:
            return set(json.load(open(PROGRESS)).get('created', {}).keys())
        except Exception:
            pass
    return set()


def load_status_map():
    """返回 {offerId: status} 映射, 用于识别失败可重试"""
    if os.path.exists(PROGRESS):
        try:
            return {k: v.get('status') for k, v in json.load(open(PROGRESS)).get('created', {}).items()}
        except Exception:
            pass
    return {}


def has_main_imgs(rec):
    """校验主图本地文件存在"""
    imgs = rec.get('main_imgs') or []
    if not imgs:
        return False
    return os.path.exists(imgs[0])


def load_stock_map():
    """读取 1688 库存数据 {offerId: stock}, 无记录或空返回 {}"""
    if not os.path.exists(STOCK_SRC):
        return {}
    try:
        out = {}
        for line in open(STOCK_SRC, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get('offerId') and r.get('stock') is not None:
                out[str(r['offerId'])] = int(r['stock'])
        return out
    except Exception:
        return {}


def stock_below_min(rec, stock_map, threshold=MIN_STOCK):
    """有库存数据且 < 阈值 → True; 无库存数据 → False(不误杀)"""
    st = stock_map.get(str(rec.get('offerId')))
    if st is None:
        return False
    return st < threshold


def mark_done(offer_id, status):
    data = {}
    if os.path.exists(PROGRESS):
        try:
            data = json.load(open(PROGRESS))
        except Exception:
            data = {}
    data.setdefault('created', {})[offer_id] = {
        "status": status, "time": time.strftime('%Y-%m-%d %H:%M:%S')}
    tmp = PROGRESS + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PROGRESS)


def load_data():
    out = []
    if not os.path.exists(DATA):
        return out
    with open(DATA, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def compute_title(rec):
    """铺货后的商品主标题(与 new_product_flow 填的一模一样)"""
    title = rec.get('title') or ''
    had_guiruo = '瑰若' in title
    title = clean_title(title)
    if had_guiruo and not title.startswith('瑰若'):
        title = '瑰若' + title
    if len(title) > 30:
        title = title[:30]
    return title


def compute_category(rec):
    """铺货类目标签(与 new_product_flow 选类目逻辑一致), 对应 fee_benchmark.category_name"""
    title = rec.get('title') or ''
    cat = rec.get('category') or ''
    if cat == '美甲' or any(k in title for k in ('穿戴甲', '甲片', '美甲', '甲油胶', '美甲贴')):
        return '美甲'
    if cat == '帽子' or any(k in title for k in ('帽', '贝雷', '棒球')):
        return '帽子'
    return '家居服'


def bind_source(rec, title, price, category, product_id):
    """铺货成功后绑定: 补建 source_product + upsert platform_product + 写 product_bind_relation。
    返回 (source_product_id, platform_product_id, 是否新建绑定)。任何 DB 错误只打日志不抛, 不阻塞铺货。"""
    offer = rec.get('offerId') or ''
    try:
        conn = pymysql.connect(**DB)
        cur = conn.cursor()
        # 1. source_product: 按 offerId + platform_type=2 查, 不存在补建
        cur.execute("SELECT id FROM source_product WHERE source_product_code=%s AND platform_type=2 AND is_deleted=0", (offer,))
        sp = cur.fetchone()
        if sp:
            sp_id = sp[0]
            cur.execute("UPDATE source_product SET source_price=%s, category_name=%s, update_time=NOW() WHERE id=%s",
                        (rec.get('source_price') or 0, category, sp_id))
        else:
            cur.execute("""INSERT INTO source_product
                (source_product_name, source_product_code, source_price, category_name,
                 platform_type, data_source, steady_status, is_deleted, create_by)
                VALUES (%s,%s,%s,%s,2,2,1,0,0)""",
                ((rec.get('title') or '')[:200], offer, rec.get('source_price') or 0, category))
            sp_id = cur.lastrowid
        # 2. platform_product: code=抖音 product_id 唯一
        shop_id = default_shop_id(cur, PLATFORM_DOUYIN)
        cur.execute("SELECT id FROM platform_product WHERE code=%s", (product_id,))
        pp = cur.fetchone()
        if pp:
            pp_id = pp[0]
            cur.execute("UPDATE platform_product SET title=%s, pricing=%s, platform_type=2, shop_id=%s, update_time=NOW() WHERE id=%s",
                        (title[:100], price, shop_id, pp_id))
        else:
            cur.execute("INSERT INTO platform_product (code, title, pricing, platform_type, shop_id, create_time) VALUES (%s,%s,%s,2,%s,NOW())",
                        (product_id, title[:100], price, shop_id))
            pp_id = cur.lastrowid
        # 3. product_bind_relation: 平台商品<->货源商品
        cur.execute("SELECT id FROM product_bind_relation WHERE product_id=%s AND source_productId=%s AND is_deleted=0", (pp_id, sp_id))
        new_bind = not cur.fetchone()
        if new_bind:
            cur.execute("INSERT INTO product_bind_relation (product_id, source_productId, create_by, is_deleted) VALUES (%s,%s,0,0)", (pp_id, sp_id))
        conn.commit()
        cur.close()
        conn.close()
        return sp_id, pp_id, new_bind
    except Exception as e:
        log(f"  ⚠ 绑定失败: {str(e)[:100]}")
        return None, None, False
    with open(DATA, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


async def js_click(page, text):
    """按精确文本点可见叶节点"""
    return await page.evaluate("""(t) => {
        const els = [...document.querySelectorAll('*')];
        const e = els.find(x => x.offsetParent !== null && x.children.length === 0
            && (x.textContent || '').trim() === t);
        if (e) { e.click(); return true; }
        return false;
    }""", text)


async def robust_upload(page, selector, file_path, timeout=30000):
    """健壮的文件上传: 等 attached → JS 强制可见 → 3种方式重试"""
    IMG_SEL = selector
    for attempt in range(3):
        try:
            fi = page.locator(IMG_SEL).first
            # 等 element attached
            await fi.wait_for(state="attached", timeout=timeout)
            # JS 强制可见 (headless 下 React 可能 display:none)
            await page.evaluate("""(sel) => {
                const el = document.querySelector(sel);
                if (el) {
                    el.scrollIntoView({behavior: 'instant', block: 'center'});
                    el.hidden = false;
                    el.style.display = '';
                    el.style.visibility = 'visible';
                    el.style.opacity = '1';
                    el.style.position = 'relative';
                    el.style.width = '1px';
                    el.style.height = '1px';
                }
            }""", IMG_SEL)
            await page.wait_for_timeout(300)
            # 方式1: locator.set_input_files (标准)
            await fi.set_input_files([file_path], timeout=timeout)
            return True
        except Exception as e1:
            log(f"    upload attempt {attempt+1} locator失败: {str(e1)[:50]}")
            try:
                # 方式2: page.set_input_files (页面级)
                await page.set_input_files(IMG_SEL, [file_path], timeout=timeout)
                return True
            except Exception as e2:
                try:
                    # 方式3: element_handle
                    handle = await page.query_selector(IMG_SEL)
                    if handle:
                        await handle.set_input_files([file_path])
                        return True
                except Exception:
                    pass
            # 重试前 reload
            if attempt < 2:
                try:
                    await page.reload(wait_until="domcontentloaded")
                    await asyncio.sleep(5)
                except Exception:
                    pass
    return False


async def new_product_flow(page, rec):
    """第一步: 主图+标题+类目 三步流. 成功进入完整表单返回 True"""
    main_imgs = rec.get('main_imgs', [])
    if not main_imgs:
        log("  ✗ 无主图")
        return False
    IMG_SEL = 'input[type=file][accept="image/*"]'
    # 1. 上传主图: 主图位传第1张, 辅助图位各传1张 (单选 input 不能一次传多张)
    ok = await robust_upload(page, IMG_SEL, main_imgs[0])
    if not ok:
        log("  ✗ 主图上传失败(3次重试均失败)")
        return False
    await asyncio.sleep(5)
    for i in range(1, min(len(main_imgs), 5)):  # 上传前5张主图
        try:
            await page.wait_for_timeout(500)
            aux = page.locator(IMG_SEL).nth(i)
            await aux.set_input_files([main_imgs[i]], timeout=15000)
            await asyncio.sleep(4)
        except Exception:
            break
    await asyncio.sleep(2)

    # 2. 填标题 (清洗, 去1688货号/痕迹; 原标题含瑰若则保留品牌前缀, 其它货源保留原名)
    title = compute_title(rec)
    title_ok = False
    for attempt in range(2):
        try:
            inp = page.locator('input[placeholder*="2-60个字符"]')
            await inp.wait_for(state='visible', timeout=60000)
            await inp.click()
            await asyncio.sleep(0.3)
            await inp.fill(title)
            await asyncio.sleep(0.3)
            await inp.press('Tab')
            await asyncio.sleep(0.5)
            # 验证填入
            val = await inp.input_value()
            if title[:10] not in val:
                log(f"  ⚠ 标题未生效, 重试...")
                continue
            log(f"  标题: {title[:50]}")
            title_ok = True
            break
        except Exception as e:
            log(f"  ⚠ 标题框异常(第{attempt+1}次): {str(e)[:40]}")
            if attempt == 0:
                try:
                    await page.goto(CREATE_URL, wait_until='domcontentloaded')
                    await asyncio.sleep(6)
                    await page.locator('input[type=file][accept="image/*"]').first.set_input_files([main_imgs[0]])
                    await asyncio.sleep(6)
                except Exception:
                    pass
    if not title_ok:
        log("  ✗ 标题框始终未出现")
        return False

    # 3. 类目: 在"下一步"之前选(抖音新版流程：先选类目才能点下一步)
    await js_click(page, '手动选择类目')
    await asyncio.sleep(4)
    
    # 检查智能推荐的第一个类目是否是"情趣内衣"，是则跳过
    first_rec = await page.evaluate(r'''() => {
        // 找智能推荐标签
        const tags = document.querySelectorAll('[class*="recomTag__"], [class*="recom"]');
        for (const t of tags) {
            const txt = (t.textContent || '').trim();
            if (txt && txt.length > 2) return txt;
        }
        // 备选：找推荐区域的文本
        const modal = document.querySelector('.ecom-g-modal-wrap, .ant-modal-wrap, #__ffa-goods-popup-container__');
        if (!modal) return '';
        const links = modal.querySelectorAll('a, span, div');
        for (const el of links) {
            const txt = (el.textContent || '').trim();
            if (txt.includes(' > ') && txt.length < 50) return txt;  // "服装 > 内衣裤袜 > 情趣内衣"
        }
        return '';
    }''')
    if '情趣内衣' in first_rec:
        log(f"  ⚠ 智能推荐类目: {first_rec}，永久过滤(情趣内衣)")
        mark_done(rec['offerId'], 'filtered')
        await page.evaluate(r'''() => {
            const close = document.querySelector('.ant-modal-close, [class*="close"]');
            if (close) close.click();
        }''')
        await asyncio.sleep(1)
        return False
    
    cat = rec.get('category') or ''
    is_meijia = cat == '美甲' or any(k in (rec.get('title') or '') for k in ('穿戴甲', '甲片', '美甲', '甲油胶', '美甲贴'))
    is_hat = cat == '帽子' or any(k in (rec.get('title') or '') for k in ('帽', '贝雷', '棒球'))
    picked = False
    if is_meijia:
        # 美甲类: 级联树逐级点 彩妆香水 -> 美甲产品 -> 美甲饰品 (稳定可靠)
        for target in ['彩妆香水', '美甲产品', '美甲饰品']:
            ok = await page.evaluate("""(t) => {
                const els = [...document.querySelectorAll('*')];
                const el = els.find(e => e.offsetParent !== null && e.children.length === 0
                    && (e.textContent || '').trim() === t);
                if (el) { el.click(); return true; }
                return false;
            }""", target)
            if not ok:
                log(f"  ✗ 级联类目找不到: {target}")
                return False
            await asyncio.sleep(2)
        picked = True
        log("  类目: 彩妆香水 > 美甲产品 > 美甲饰品")
    elif is_hat:
        # 帽子类: 智能推荐选 服装 > ... > 帽子
        try:
            tag = page.locator('[class*="recomTag__"]').filter(has_text='服装 > ... > 帽子').first
            await tag.click(timeout=5000)
            picked = True
            log("  类目: 服装 > 帽子")
        except Exception:
            log("  ✗ 找不到帽子类目标签")
            return False
        await asyncio.sleep(2)
    else:
        # 服装类: 逐级选 服饰内衣 > 服装 > 内衣裤袜 > 居家服/睡衣
        for step in ['服饰内衣', '服装', '内衣裤袜', '居家服/睡衣']:
            await page.evaluate(r'''(target) => {
                const modal = document.querySelector('.ecom-g-modal-wrap');
                if (!modal) return;
                const els = [...modal.querySelectorAll('*')];
                for (const el of els) {
                    if (el.offsetParent !== null && el.children.length === 0 && (el.textContent||'').trim() === target) {
                        el.click(); break;
                    }
                }
            }''', step)
            await asyncio.sleep(2)
        picked = True
        log("  类目: 服饰内衣 > 服装 > 内衣裤袜 > 居家服/睡衣")
    # 点弹窗内 确认（多等几秒让 modal 渲染）
    await asyncio.sleep(3)
    if not await js_click(page, '确认'):
        # fallback: 用 Playwright locator 找确认按钮
        confirm = page.locator('button:has-text("确认"), button:has-text("确定")').first
        if await confirm.count() > 0:
            await confirm.click(timeout=5000)
            log("  类目确认: ✓ (locator)")
        else:
            log("  ✗ 找不到类目确认")
            return False
    else:
        log("  类目确认: ✓ (js)")
    await asyncio.sleep(5)
    # 点页面主 下一步
    if not await js_click(page, '下一步'):
        log("  ✗ 找不到下一步(类目)")
        return False
    await asyncio.sleep(15)

    # 5. 验证进入完整表单 (有 商品标题 / 保存草稿)
    txt = await page.evaluate('() => document.body.innerText')
    if '保存草稿' not in txt or '商品标题' not in txt:
        log("  ✗ 未进入完整表单")
        return False
    log("  ✓ 已进入完整表单")
    return True


def build_sku_excel(rec, price, path):
    """生成智能填写助手 Excel: 颜色分类/尺码大小/价格/库存
    如果 rec 有 sku_prices (每SKU独立价), 用 源SKU价×5; 否则用统一价 price。"""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = 'Sheet1'
    ws.append(['颜色分类', '尺码大小', '价格', '库存'])
    colors = rec['sku'].get('colors', []) or ['默认']
    sizes = rec['sku'].get('sizes', []) or ['均码']
    # 解析 per-SKU 价格: sku_prices key 格式 "颜色:白色&尺码:M" -> 提取 color/size
    sku_p = {}
    for key, sv in (rec.get('sku_prices') or {}).items():
        try:
            parts = {}
            for seg in key.split('&'):
                if ':' in seg:
                    k, v = seg.split(':', 1)
                    parts[k.strip()] = v.strip()
            color = parts.get('颜色', '')
            sz = parts.get('尺码', '')
            if color and sz:
                sku_p[(color, sz)] = sv.get('price', 0) * 3
        except Exception:
            pass
    for c in colors:
        for s in sizes:
            p = sku_p.get((c, s)) or price
            ws.append([c, s, round(p, 2), 100])
    wb.save(path)
    return path


async def ai_guide_title(page):
    """AI生成导购标题: 点AI智能创作 -> 等生成 -> 点立即使用"""
    # 点 AI智能创作 按钮
    clicked = await page.evaluate("""() => {
        const els=[...document.querySelectorAll('button,span,div')];
        const e=els.find(x=>x.offsetParent!==null && (x.textContent||'').trim()==='AI智能创作');
        if(e){ e.click(); return true; }
        return false;
    }""")
    if not clicked:
        return False
    log("  AI导购标题: 已点AI智能创作")
    await asyncio.sleep(5)
    # 等"立即使用"出现(最多20s), 然后点它; 超时不阻塞流程(AI生成经常失败)
    for _ in range(10):
        ok = await page.evaluate("""() => {
            const els=[...document.querySelectorAll('button,span,div')];
            const e=els.find(x=>x.offsetParent!==null && x.children.length===0 && (x.textContent||'').trim()==='立即使用');
            if(e){ e.click(); return true; }
            return false;
        }""")
        if ok:
            log("  AI导购标题: 已使用")
            await asyncio.sleep(2)
            return True
        await asyncio.sleep(2)
    log("  ⚠ AI导购标题: 立即使用未出现(超时)")
    return False


async def close_drawer(page):
    """关闭右侧 ecom-g-drawer(规格图设置/智能填写等). 该抽屉会拦截属性区
    (适用性别/面料材质) 的点击, Playwright click 因此超时。"""
    try:
        closed = await page.evaluate(r'''() => {
            const d = document.querySelector('.ecom-g-drawer-open');
            if (!d) return false;
            const c = d.querySelector('.ecom-g-drawer-close');
            if (c) { c.click(); return true; }
            return false;
        }''')
        if closed:
            await asyncio.sleep(1.5)
        return closed
    except Exception:
        return False


async def fill_form(page, rec, test):
    """第二步: 完整表单填 SKU(Excel智能助手)/价格/运费/下架, 发布商品(下架状态)"""
    price = round(float(rec.get('source_price') or 0) * 5, 2)

    # 生成 SKU Excel 并上传到智能填写助手 (input accept=.xls,.xlsx...)
    xlsx_path = f"/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/tmp_douyin/{rec['offerId']}/sku.xlsx"
    try:
        build_sku_excel(rec, price, xlsx_path)
    except Exception as e:
        log(f"  ✗ Excel生成失败: {str(e)[:60]}")
        return False

    # 上传到智能填写助手
    uploaded = False
    for idx in range(5, 25):
        try:
            fi = page.locator('input[type=file]').nth(idx)
            acc = await fi.get_attribute('accept')
            if acc and '.xls' in acc:
                await fi.set_input_files(xlsx_path)
                uploaded = True
                log(f"  ✓ SKU Excel 已上传(第{idx}个file input)")
                break
        except Exception:
            continue
    if not uploaded:
        log("  ✗ 找不到智能填写助手的 Excel 上传框")
        return False
    await asyncio.sleep(6)

    # 点 智能识别
    await page.evaluate("""() => {
        const els = [...document.querySelectorAll('*')];
        const t = els.find(e => e.offsetParent !== null && e.children.length === 0
            && (e.textContent || '').trim() === '智能识别');
        if (t) t.click();
    }""")
    await asyncio.sleep(25)

    # 验证 SKU 表格生成 (宽松: 出现 SKU 表头或 颜色分类/尺码大小 或 价格填写进度)
    txt = await page.evaluate('() => document.body.innerText')
    sku_ok = ('价格填写进度' in txt or '颜色分类' in txt) and '请先选择商品规格' not in txt
    if not sku_ok:
        log("  ⚠ SKU 表格未生成, 尝试重试智能识别...")
        await page.evaluate("""() => {
            const els = [...document.querySelectorAll('*')];
            const t = els.find(e => e.offsetParent !== null && e.children.length === 0
                && (e.textContent || '').trim() === '智能识别');
            if (t) t.click();
        }""")
        await asyncio.sleep(20)
        txt = await page.evaluate('() => document.body.innerText')
        sku_ok = ('价格填写进度' in txt or '颜色分类' in txt) and '请先选择商品规格' not in txt
    if not sku_ok:
        log("  ✗ SKU 表格未生成(重试后仍失败)")
        return False
    log(f"  ✓ SKU 表格生成 (价格×5=￥{price})")

    # 上传详情图 (商品详情 section)
    try:
        det = rec.get('detail_imgs') or []
        if det:
            up = await upload_detail_imgs(page, det)
            log(f"  详情图: 上传{'✓' if up else '✗'} ({len(det)}张)")
        else:
            log("  详情图: 数据无 detail_imgs, 跳过")
    except Exception as e:
        log(f"  ⚠ 详情图上传异常: {str(e)[:60]}")

    # 运费模板: 选 运费3.7 (存在则选, 否则保持默认包邮)
    # 运费模板: 保持默认(包邮), 跳过 select_freight (曾致连接崩溃)
    log("  运费模板: 保持默认(跳过选择)")

    # 适用性别: 必填多选(2026-09-09 抖店表单新加必填项, 选项: 女/男/男女通用)
    try:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)
        gsel = page.locator('div[attr-field-id="适用性别"] .ecom-g-select').first
        if await gsel.count() > 0:
            closed = await close_drawer(page)
            log(f"  适用性别: 关闭规格图drawer={closed}")
            opened = False
            for att in range(3):
                try:
                    await gsel.scroll_into_view_if_needed(timeout=5000)
                    await gsel.click(timeout=6000, force=(att > 0))
                except Exception as e:
                    log(f"  适用性别: click尝试{att+1}异常 {str(e)[:40]}")
                    if att < 2:
                        await close_drawer(page)
                    continue
                await asyncio.sleep(1.5)
                opened = await page.evaluate(r'''() => {
                    for (const d of document.querySelectorAll('.ecom-g-select-dropdown')) {
                        const t = d.textContent || '';
                        if (t.includes('男女通用') && t.indexOf('男') < 30) return true;
                    }
                    return false;
                }''')
                if opened:
                    break
            log(f"  适用性别: 打开={opened}")
            gnode = page.locator('.ecom-g-select-dropdown:visible .ecom-g-select-tree-node-content-wrapper[title="女"]').first
            try:
                await gnode.wait_for(state="visible", timeout=10000)
            except Exception:
                log("  ⚠ 适用性别: 选项等待超时")
            if await gnode.count() > 0:
                await gnode.click(timeout=6000)
                log("  适用性别: 已选'女'")
            else:
                log("  ⚠ 适用性别: 未找到'女'选项")
            await page.keyboard.press('Escape')
            await asyncio.sleep(1)
            gval = await page.evaluate(r'''() => {
                const s = document.querySelector('div[attr-field-id="适用性别"] .ecom-g-select');
                return s ? (s.textContent || '').replace(/\s+/g, ' ').slice(0, 20) : '';
            }''')
            log(f"  适用性别: 校验值={gval}")
        else:
            log("  ⚠ 适用性别: 字段未找到")
    except Exception as e:
        log(f"  ⚠ 适用性别异常: {str(e)[:60]}")

    # 面料材质: 必填项 (2026-09-01 重写按已验证配方: 点开→点搜索框聚焦→输入→勾checkbox→填百分比→点空白收起)
    try:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)

        loc = page.locator('[data-kora="click_multi_value_measure_composition_select"] .aurora-select').first
        if await loc.count() == 0:
            loc = page.locator('[class*="composition-select-select"]').first
        opened = False
        if await loc.count() > 0:
            for att in range(2):
                try:
                    await loc.scroll_into_view_if_needed()
                    await loc.click(timeout=6000)
                    opened = True
                    break
                except Exception as e:
                    log(f"  面料材质: click尝试{att+1}异常 {str(e)[:40]}")
            if not opened:
                # 回退: JS 事件序列 (旧路径, 实测能打开面板)
                opened = await page.evaluate(r'''() => {
                    const sel = document.querySelector('[data-kora="click_multi_value_measure_composition_select"] .aurora-select')
                             || document.querySelector('[class*="composition-select-select"]');
                    if (!sel) return false;
                    const r = sel.getBoundingClientRect();
                    if (r.width <= 0) return false;
                    for (const evt of ['mousedown', 'mouseup', 'click']) {
                        sel.dispatchEvent(new MouseEvent(evt, {bubbles: true, cancelable: true, view: window}));
                    }
                    sel.focus();
                    return true;
                }''')
        log(f"  面料材质: 打开={opened}")
        await asyncio.sleep(2)

        # 关键1: 点搜索框聚焦 (不聚焦则键盘输入无效, 曾致"未找到选项")
        sbox = page.locator('.aurora-select-dropdown input:visible').first
        if await sbox.count() > 0:
            await sbox.click(timeout=3000)
            await asyncio.sleep(0.5)
            await page.keyboard.type('聚酯纤维', delay=80)
            await asyncio.sleep(2)
        else:
            log("  ⚠ 面料材质: 下拉搜索框未找到")

        # 关键2: 勾 checkbox (勿点文字)
        cb = page.locator('.aurora-select-item-option').filter(has_text='聚酯纤维').locator('.aurora-select-item-option-checkbox').first
        if await cb.count() == 0:
            cb = page.locator('.aurora-select-item-option').filter(has_text='聚酯纤维').first
        if await cb.count() > 0:
            await cb.click(timeout=3000)
            log("  面料材质: 已勾'聚酯纤维'")
        else:
            log("  ⚠ 面料材质: 未找到'聚酯纤维'选项")
        await asyncio.sleep(1)

        # 关键3: 百分比 input 填 100 (勾选后下拉内出现的非搜索框可见输入框)
        filled = False
        pct_inputs = page.locator('.aurora-select-dropdown input:visible')
        n_pct = await pct_inputs.count()
        for k in range(1, n_pct):  # index 0 是搜索框
            inp = pct_inputs.nth(k)
            try:
                ph = await inp.get_attribute('placeholder') or ''
            except Exception:
                ph = ''
            if '搜索' in ph:
                continue
            try:
                await inp.click(timeout=2000)
                await inp.fill('100')
                await inp.press('Tab')
                filled = True
                log("  面料含量: 100% ✓")
                break
            except Exception as e:
                log(f"  ⚠ 面料含量: 第{k}个input填值异常 {str(e)[:40]}")
        if not filled:
            # 回退: "面料材质成分含量"标签右侧偏移点击后找输入框
            pi = await page.evaluate(r'''() => {
                const all = document.querySelectorAll('*');
                for (const el of all) {
                    const txt = (el.textContent || '').trim();
                    if (txt === '面料材质成分含量' && el.children.length === 0 && el.offsetParent !== null) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.y > 0) return {x: r.x+r.width+80, y: r.y+r.height/2};
                    }
                }
                return null;
            }''')
            if pi:
                await page.mouse.click(pi['x'], pi['y'])
                await asyncio.sleep(2)
                dd = await page.evaluate(r'''() => {
                    const inputs = document.querySelectorAll('.aurora-select-dropdown input, .aurora-select-search input');
                    const out = [];
                    for (const i of inputs) { const r = i.getBoundingClientRect(); if (r.width > 0) out.push({x: r.x+r.width/2, y: r.y+r.height/2}); }
                    return out;
                }''')
                if dd:
                    await page.mouse.click(dd[-1]['x'], dd[-1]['y'])
                    await asyncio.sleep(0.3)
                    await page.keyboard.type('100', delay=30)
                    await asyncio.sleep(1)
                    await page.keyboard.press('Enter')
                    log("  面料含量: 100% (回退路径)")
                else:
                    log("  ⚠ 面料含量: dropdown未找到")
            else:
                log("  ⚠ 面料含量: 字段不存在，跳过")
        # 点空白收起下拉
        await page.mouse.click(10, 10)
        await asyncio.sleep(1)
        # 校验最终值
        val = await page.evaluate(r'''() => {
            const s = document.querySelector('[class*="composition-select-select"]');
            if (!s) return 'N/A';
            const tags = s.querySelectorAll('[class*="tag"]');
            return tags.length > 0 ? Array.from(tags).map(t=>t.textContent).join(',') : s.textContent?.trim().substring(0,20);
        }''')
        log(f"  面料材质: 最终值={val[:30]}")
        await asyncio.sleep(0.5)
    except Exception as e:
        log(f"  ⚠ 面料材质异常: {str(e)[:80]}")

    # 尺码表(尺码助手): 居家服/睡衣类目提交必填 身高+体重 (2026-09-10 实测拦截)
    # ⚠ 输入框被 overflow:hidden 容器(styles_layoutContainer)裁剪, Playwright click/fill 均超时;
    #   唯一可用路径 = JS scrollIntoView + focus + keyboard.type (值仅接受纯数字, 区间符被吞)
    try:
        std = {'XS': ('152', '44'), 'S': ('157', '51'), 'M': ('162', '59'),
               'L': ('167', '66'), 'XL': ('172', '74'), 'XXL': ('177', '81'),
               '2XL': ('177', '81'), 'XXXL': ('182', '88'), '3XL': ('182', '88'),
               'F': ('162', '59'), '均码': ('162', '59')}

        async def fill_size_cell(size_name, col, val):
            okc = await page.evaluate(r'''(arg) => {
                const label = document.querySelector('[class*="sizeChartFormItemLabel"]');
                if (!label) return null;
                let n = label, cardEl = null;
                for (let i = 0; i < 8 && n; i++) { n = n.parentElement; if (!n) break;
                    const t = n.textContent || '';
                    if (t.includes('尺码助手') && t.includes('尺码信息')) cardEl = n; }
                if (!cardEl) return null;
                const ins = [...cardEl.querySelectorAll('input')]
                    .filter(i => i.getBoundingClientRect().width > 0)
                    .map(i => ({el: i, ph: i.placeholder || '', val: (i.value || '').trim(), y: i.getBoundingClientRect().y}))
                    .sort((a, b) => a.y - b.y);
                const groups = [];
                for (const o of ins) {
                    const g = groups.find(g => Math.abs(g.y - o.y) < 22);
                    if (g) g.items.push(o); else groups.push({y: o.y, items: [o]});
                }
                for (const g of groups) {
                    const nameI = g.items.find(o => o.ph === '请输入' && o.val.toUpperCase() === arg.size);
                    const recs = g.items.filter(o => o.ph === '推荐填写');
                    if (nameI && recs.length >= 2) {
                        const t = recs[arg.col];
                        t.el.scrollIntoView({block: 'center', behavior: 'instant'});
                        t.el.focus();
                        return true;
                    }
                }
                return false;
            }''', {'size': size_name, 'col': col})
            if not okc:
                return False
            await asyncio.sleep(0.3)
            await page.keyboard.type(val, delay=50)
            await page.keyboard.press('Tab')
            await asyncio.sleep(0.4)
            return True

        sizes_present = await page.evaluate(r'''() => {
            const label = document.querySelector('[class*="sizeChartFormItemLabel"]');
            if (!label) return [];
            let n = label, cardEl = null;
            for (let i = 0; i < 8 && n; i++) {
                n = n.parentElement;
                if (!n) break;
                const t = n.textContent || '';
                if (t.includes('尺码助手') && t.includes('尺码信息')) cardEl = n;
            }
            if (!cardEl) return [];
            const out = [];
            for (const i of cardEl.querySelectorAll('input')) {
                if (i.placeholder === '请输入' && i.value.trim() && i.getBoundingClientRect().width > 0) out.push(i.value.trim().toUpperCase());
            }
            return out;
        }''')
        filled_n = 0
        for sz in sizes_present:
            stdv = std.get(sz)
            if not stdv:
                log(f"  ⚠ 尺码表: 未知尺码 '{sz}' 跳过")
                continue
            ok_row = True
            for col, val in enumerate(stdv):
                try:
                    if not await fill_size_cell(sz, col, val):
                        log(f"  尺码表: {sz} 第{col+1}列定位失败")
                        ok_row = False
                        break
                except Exception as e:
                    log(f"  尺码表: {sz} 第{col+1}列填写异常 {str(e)[:40]}")
                    ok_row = False
                    break
            if ok_row:
                filled_n += 1
        log(f"  尺码表: 已填 {filled_n}/{len(sizes_present)} 行 (尺码: {','.join(sizes_present[:8])})")
        rb = await page.evaluate(r'''() => {
            const label = document.querySelector('[class*="sizeChartFormItemLabel"]');
            if (!label) return 'NO_LABEL';
            let n = label, cardEl = null;
            for (let i = 0; i < 8 && n; i++) {
                n = n.parentElement;
                if (!n) break;
                const t = n.textContent || '';
                if (t.includes('尺码助手') && t.includes('尺码信息')) cardEl = n;
            }
            if (!cardEl) return 'NO_CARD';
            return [...cardEl.querySelectorAll('input')]
                .filter(i => i.getBoundingClientRect().width > 0 && i.placeholder === '推荐填写')
                .map(i => i.value || '-').join(' ');
        }''')
        log(f"  尺码表读回: {rb}")
    except Exception as e:
        log(f"  ⚠ 尺码表异常: {str(e)[:60]}")

    # 水洗标/吊牌图: 跳过(非必填，OCR拒绝PIL生成图)
    log("  水洗标/吊牌图: 跳过(非必填)")

    # 商品状态: 选"下架"(radio value=1), 再点"发布商品"
    if not test:
        # 选择"下架" radio
        picked = await page.evaluate("""() => {
            const radios=[...document.querySelectorAll('input.ecom-g-radio-input')];
            const r=radios.find(i=>i.closest('.ecom-g-radio-wrapper') && /下架/.test(i.closest('.ecom-g-radio-wrapper').textContent));
            if(r && !r.checked){ r.click(); return true; }
            return r ? true : false;
        }""")
        await asyncio.sleep(2)
        if not picked:
            log("  ⚠ 未找到'下架'状态选项")
        else:
            log("  商品状态: 下架")

    if test:
        log("  --test: 不发布")
        return True, None
    saved, dialogs, pid, reason = await save_draft(page)
    log(f"  发布商品: {'✓' if saved else '✗'}" + (f" | 弹窗: {dialogs}" if dialogs else ""))
    if pid:
        log(f"  product_id: {pid}")
    if not saved and '情趣内衣' in (reason or ''):
        log("  ⚠ 发布被驳: 类目应为情趣内衣(类目未开通), 永久过滤")
        mark_done(rec['offerId'], 'filtered')
    # dialogs 仅记录不否决: saved=True 必有正向证据(pid 拦截或页面成功标志), 商品已存在,
    # 因弹窗判失败会触发下轮重发(重复铺货); 无正向证据时 saved 本身就为 False
    return saved, pid


async def select_freight(page):
    """运费模板 = 运费3.7; 若不存在保持默认包邮 (沿用 edit_douyin_product.py 逻辑)"""
    await page.evaluate("""() => {
        const els = [...document.querySelectorAll('*')];
        const t = els.find(e => e.offsetParent !== null && e.children.length === 0
            && (e.textContent || '').trim() === '服务与履约');
        if (t) t.click();
    }""")
    await asyncio.sleep(2)
    # 按 label 找到运费模板 select 并点开
    await page.evaluate("""() => {
        let opened = false;
        document.querySelectorAll('input[id^="rc_select"]').forEach(el => {
            let n = el, label = '';
            for (let i = 0; i < 6; i++) { n = n.parentElement; if (!n) break;
                const t = (n.querySelector('label,th,span') || n).innerText?.trim().split(String.fromCharCode(10))[0];
                if (t && t.length < 22) { label = t; break; }
            }
            if (label.includes('运费模板') && !opened) {
                (el.closest('[class*="select"]') || el.parentElement).click(); opened = true;
            }
        });
    }""")
    await asyncio.sleep(1.5)
    picked = await page.evaluate("""() => {
        const opt = [...document.querySelectorAll('*')].find(o => o.offsetParent !== null
            && o.children.length < 2 && (o.textContent || '').trim() === '运费3.7');
        if (opt) { opt.click(); return true; }
        return false;
    }""")
    log(f"  运费模板: {'运费3.7 ✓' if picked else '保持默认'}")
    return picked


async def upload_detail_imgs(page, detail_imgs):
    """上传详情图到 商品详情/商详图片 区. 找'商品详情'或'商详图片'容器内的 file input 批量传"""
    files = [f for f in detail_imgs if f and os.path.exists(f)]
    if not files:
        return False
    # 滚动到详情区确保可见
    try:
        await page.evaluate("""() => {
            const els = [...document.querySelectorAll('*')];
            const t = els.find(e => e.offsetParent !== null && e.children.length === 0
                && /商品详情|商详图片/.test(e.textContent || ''));
            if (t) t.scrollIntoView({behavior:'instant', block:'center'});
        }""")
        await asyncio.sleep(2)
    except Exception:
        pass
    # 找详情区的 file input (accept=image, 在含 商详图片/商品详情 的容器内)
    for try_idx in range(3):
        try:
            fi = page.locator("input[type=file][accept='image/*']").nth(try_idx + 13)
            acc = await fi.get_attribute('accept')
            if acc and 'image' in acc:
                # 用 robust 方式上传 (input 无 multiple 属性时逐张传)
                mult = await fi.get_attribute('multiple')
                for attempt in range(2):
                    try:
                        await fi.wait_for(state="attached", timeout=10000)
                        if mult is not None:
                            await fi.set_input_files(files, timeout=120000)
                            await asyncio.sleep(8)
                        else:
                            for fpath in files:
                                await fi.set_input_files([fpath], timeout=60000)
                                await asyncio.sleep(3)
                        return True
                    except Exception:
                        if attempt == 0:
                            try:
                                await page.reload(wait_until="domcontentloaded")
                                await asyncio.sleep(5)
                            except Exception:
                                pass
        except Exception:
            continue
    return False


async def save_draft(page):
    """真实点击'发布商品'按钮(放入仓库/下架状态提交), 拦截响应获取 product_id. 
    ⚠️ 之前用 evaluate .click() 可能没触发React真实提交, 导致实际保存成了草稿"""
    dialogs = []
    captured_pid = [None]

    async def on_dialog(d):
        dialogs.append(d.message[:120])
        try:
            await d.dismiss()
        except Exception:
            pass

    async def on_resp(r):
        if captured_pid[0]:
            return
        try:
            url = r.url
            if ('createWithSchema' in url or 'editWithSchema' in url or 'tproduct/save' in url
                    or '/product/' in url or '/tproduct/' in url or '/schema/' in url):
                ct = r.headers.get('content-type', '')
                if 'json' in ct or 'javascript' in ct:
                    try:
                        body = await r.json()
                    except Exception:
                        return
                    data = body.get('data') or body
                    # 检查错误响应
                    status_code = body.get('status_code') or body.get('code')
                    if status_code and status_code != 0:
                        err_msg = body.get('message') or body.get('msg') or ''
                        log(f"  [API错误] status={status_code} msg={err_msg[:80]}")
                    if isinstance(data, dict):
                        for key in ('product_id', 'id', 'productId', 'pid', 'productIds'):
                            val = data.get(key)
                            if val:
                                if isinstance(val, (str, int)) and len(str(val)) > 10:
                                    captured_pid[0] = str(val)
                                    log(f"  [拦截] {key}={val}")
                                    return
                                elif isinstance(val, list) and val:
                                    captured_pid[0] = str(val[0])
                                    log(f"  [拦截] {key}={val[0]}")
                                    return
                        if 'data' in data and isinstance(data['data'], dict):
                            inner = data['data']
                            for key in ('product_id', 'id', 'productId', 'pid'):
                                val = inner.get(key)
                                if val and len(str(val)) > 10:
                                    captured_pid[0] = str(val)
                                    log(f"  [拦截] data.{key}={val}")
                                    return
                    if r.status == 200 and 'json' in ct:
                        log(f"  [API] {url.split('/')[-1][:30]} status={r.status}")
        except Exception:
            pass

    page.on('dialog', on_dialog)
    page.on('response', on_resp)
    saved = False
    # 真实点击"发布商品"
    try:
        btn = page.locator("button:has-text('发布商品')").last
        await btn.scroll_into_view_if_needed(timeout=8000)
        await btn.click(timeout=8000)
        saved = True
    except Exception:
        saved = await page.evaluate("""() => {
            const btn = [...document.querySelectorAll('button')]
                .find(b => (b.innerText || '').trim() === '发布商品');
            if (btn) { btn.click(); return true; }
            return false;
        }""")
    await asyncio.sleep(5)

    # 轮询提交结果(参照 fix_douyin_images.publish 已验证模式):
    # 持续处理弹窗链(不修改，继续发布/推荐有误/知道了等) + 等保存响应/成功标志/校验错误
    final = None  # (ok, reason)
    for round_i in range(24):
        await asyncio.sleep(3.5)
        if captured_pid[0]:
            final = (True, f"pid={captured_pid[0]}")
            break
        st = await page.evaluate("""() => {
            const t = document.body.innerText || '';
            if (/线上商品数据已更新|商品发布成功|提交成功|发布成功|保存成功/.test(t)) return {k:'ok'};
            if (/被挤爆啦/.test(t)) return {k:'busy'};
            const errs = document.querySelectorAll('.ecom-g-form-item-has-error, [class*="form-item-has-error"], [class*="error-tip"]');
            const out = [];
            for (const e of errs) {
                if (e.offsetParent) out.push((e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,60));
            }
            if (out.length) return {k:'validation', detail: [...new Set(out)].slice(0,4).join(' | ')};
            return {k:''};
        }""")
        if st['k'] == 'ok':
            final = (True, '发布成功(页面标志)')
            break
        if st['k'] == 'busy':
            log("  ⚠ 被挤爆啦(风控限流), 等待...")
            continue
        if st['k'] == 'validation':
            final = (False, st.get('detail', ''))
            break
        # 弹窗链处理 (JS, 仅当有可见 modal)
        try:
            acted = await page.evaluate("""() => {
                const bs = [...document.querySelectorAll('button')].filter(b => b.offsetParent);
                const dlg = [...document.querySelectorAll('.ecom-g-modal, .ant-modal, [class*="modal"]')]
                    .find(m => m.offsetParent);
                if (!dlg) return null;
                for (const re of [/不修改，继续发布/, /继续发布/, /推荐有误/, /确认发布/, /确定/, /我知道了/, /知道了/]) {
                    const b = bs.find(x => re.test((x.innerText||'').trim()));
                    if (b) { b.click(); return (b.innerText||'').trim(); }
                }
                return null;
            }""")
            if acted:
                log(f"  · 弹窗: {acted}")
        except Exception:
            pass

    page.remove_listener('dialog', on_dialog)
    page.remove_listener('response', on_resp)

    if final:
        ok, reason = final
        log(f"  发布商品: {'✓' if ok else '✗'} ({reason})")
        return ok, dialogs, (captured_pid[0] if ok else None), reason

    log("  ✗ 提交结果未确认(超时无保存响应/成功标志)")
    return False, dialogs, None, ''


async def fetch_product_id_by_title(page, title, max_pages=3):
    """发布成功后, 取离线列表第1个商品的 product_id (最新发布的)。
    同时尝试标题匹配作为备选。"""
    norm = title.replace(' ', '')

    # 方法1: 取列表第1个(最新)
    try:
        url = "https://fxg.jinritemai.com/product/tproduct/list?page=1&pageSize=5&tab=offline"
        res = await page.evaluate("""async (u) => {
            const r = await fetch(u, {credentials:'include'});
            return await r.json();
        }""", url)
        items = res.get('data', []) or []
        if items:
            first = items[0]
            first_name = re.sub(r'\s+', '', first.get('name') or '')
            # 检查是否匹配(前10字或全匹配)
            if first_name[:10] == norm[:10] or first_name == norm:
                pid = str(first.get('product_id', ''))
                if pid:
                    log(f"  绑定: 列表第1个匹配 '{first_name[:30]}'")
                    return pid
    except Exception:
        pass

    # 方法2: 遍历匹配
    for pg in range(1, max_pages + 1):
        try:
            url = f"https://fxg.jinritemai.com/product/tproduct/list?page={pg}&pageSize=20&tab=offline"
            res = await page.evaluate("""async (u) => {
                const r = await fetch(u, {credentials:'include'});
                return await r.json();
            }""", url)
        except Exception:
            await asyncio.sleep(1)
            continue
        for item in res.get('data', []) or []:
            name = re.sub(r'\s+', '', item.get('name') or '')
            if (name == norm or name[:10] == norm[:10]) and str(item.get('product_id', '')):
                return str(item.get('product_id', ''))
        await asyncio.sleep(0.8)

    log("  ⚠ 绑定: 列表未匹配到标题")
    return None


async def main():
    resolve_paths()
    test = '--test' in sys.argv
    dy_id = None
    batch = 0
    for i, a in enumerate(sys.argv[1:]):
        if a == '--dyId':
            dy_id = sys.argv[i + 2]
        elif a == '--batch':
            batch = int(sys.argv[i + 2])
    if not dy_id and not batch and not test:
        print("用法: --dyId <offerId> | --batch N [--test] | --test")
        return

    done = load_done()
    status_map = load_status_map()
    stock_map = load_stock_map()
    all_recs = load_data()
    if dy_id:
        todo = [r for r in all_recs if r['offerId'] == dy_id]
    elif test:
        todo = [r for r in all_recs if r['offerId'] not in done][:1]
    else:
        # batch: 未处理的 + 已失败可重试的(有主图), 跳过无主图(无法铺)
        # 过滤: saved/filtered 跳过; 库存<20 直接永久过滤
        todo = []
        low_stock = 0
        for r in all_recs:
            st = status_map.get(r['offerId'])
            if st == 'saved' or st == 'filtered':
                continue
            if not has_main_imgs(r):
                continue
            if stock_below_min(r, stock_map):
                mark_done(r['offerId'], 'filtered')
                low_stock += 1
                continue
            todo.append(r)
        if low_stock:
            log(f"库存<{MIN_STOCK} 直接过滤 {low_stock} 条")
        todo = todo[:batch]
    if not todo:
        log("没有待处理商品")
        return
    skipped = sum(1 for r in all_recs if r['offerId'] not in done and not has_main_imgs(r))
    filtered_cnt = sum(1 for s in status_map.values() if s == 'filtered')
    log(f"共 {len(all_recs)}, 已成功 {sum(1 for s in status_map.values() if s == 'saved')}, "
        f"已过滤 {filtered_cnt}, 本次 {len(todo)}, 跳过无主图 {skipped}")

    pw = await async_playwright().start()
    ctx = await pw.chromium.launch_persistent_context(
        "/tmp/chrome-douyin-create",
        executable_path="/Users/qyk9527/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        headless=False,
        args=['--disable-gpu', '--disable-dev-shm-usage'],
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()

    async def _safe_dismiss(d):
        try:
            await d.dismiss()
        except Exception:
            pass
    page.on('dialog', lambda d: asyncio.create_task(_safe_dismiss(d)))

    await page.goto(CREATE_URL, wait_until='domcontentloaded')
    await asyncio.sleep(10)
    
    # 检查登录
    if 'login' in page.url.lower() or 'sso' in page.url.lower():
        log("需要登录抖店，请扫码...")
        for _ in range(120):
            await asyncio.sleep(5)
            url = page.url
            if 'login' not in url.lower() and 'sso' not in url.lower() and 'jinritemai' in url:
                log("登录成功!")
                break
        for attempt in range(3):
            try:
                await page.goto(CREATE_URL, wait_until='domcontentloaded', timeout=30000)
                break
            except:
                await asyncio.sleep(5)
        await asyncio.sleep(10)

    for i, rec in enumerate(todo):
        log(f"\n[{i+1}/{len(todo)}] {rec['offerId']}")
        # 清理残留的 create 页面 (防止崩溃后堆积, 拖垮 CDP)
        if i % 5 == 0:
            try:
                for pg in ctx.pages:
                    if 'ffa/g/create' in (pg.url or '') and pg != page:
                        try:
                            await pg.close()
                        except Exception:
                            pass
            except Exception:
                pass
        # 每条商品开启一个新 page，彻底规避 SPA 状态残留
        if i > 0:
            try:
                await page.close()
            except Exception:
                pass
        page = await ctx.new_page()
        
        try:
            await page.goto(CREATE_URL, wait_until='domcontentloaded')
        except Exception:
            pass
        await asyncio.sleep(6)
        try:
            ok = await new_product_flow(page, rec)
            if ok:
                filled, pub_pid = await fill_form(page, rec, test)
                if test:
                    mark_done(rec['offerId'], 'test_filled')
                    log("  --test: 完成, 不保存")
                elif filled:
                    mark_done(rec['offerId'], 'saved')
                    try:
                        btitle = compute_title(rec)
                        bprice = round(float(rec.get('source_price') or 0) * 3, 2)
                        bcat = compute_category(rec)
                        # 优先用发布响应拦截的 product_id, 失败再用列表匹配(含重试)
                        pid = pub_pid
                        if not pid:
                            for retry in range(3):
                                pid = await fetch_product_id_by_title(page, btitle)
                                if pid:
                                    break
                                if retry < 2:
                                    log(f"  ⚠ 绑定: 列表未匹配, {5*(retry+1)}s后重试...")
                                    await asyncio.sleep(5 * (retry + 1))
                        if pid:
                            sp_id, pp_id, new_bind = bind_source(rec, btitle, bprice, bcat, pid)
                            log(f"  绑定: sp={sp_id} pp={pp_id} 新建={new_bind} (抖音ID {pid})")
                        else:
                            log(f"  ⚠ 绑定跳过: 未拿到抖音 product_id (offerId={rec['offerId']})")
                    except Exception as e:
                        log(f"  ⚠ 绑定异常(不阻塞铺货): {str(e)[:80]}")
                else:
                    if load_status_map().get(rec['offerId']) != 'filtered':
                        mark_done(rec['offerId'], 'save_failed')
            else:
                if load_status_map().get(rec['offerId']) != 'filtered':
                    mark_done(rec['offerId'], 'create_failed')
        except Exception as e:
            log(f"  ✗ 异常: {str(e)[:80]}")
            if 'Connection closed' in str(e) or 'detached' in str(e) or 'ERR_ABORTED' in str(e):
                log("  ⚠ 连接异常, 标记留待重试")
                continue
            mark_done(rec['offerId'], 'error')
        await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        if (i + 1) % 50 == 0:
            wait = random.uniform(30, 60)
            log(f"  每50条暂停 {wait:.0f}s ...")
            await asyncio.sleep(wait)

    log(f"完成! 本次处理 {len(todo)} 条")
    try:
        await page.close()
    except Exception:
        pass
    await ctx.close()
    await pw.stop()


asyncio.run(main())
