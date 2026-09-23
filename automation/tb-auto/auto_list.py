"""
1688铺货自动化脚本
自动处理铺货失败的商品：补齐信息、设置价格×3、选择分类、放入仓库、开启预检
"""
import asyncio
import json
import os
import random
import time
import logging
from playwright.async_api import async_playwright
from rules import generate_style_number, infer_attributes, rewrite_title
from config import *

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), LOG_FILE), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 情趣内衣/成人类目关键词: 店铺无准入资质, 命中则直接删除铺货日志跳过编辑
ADULT_KEYWORDS = ('情趣', '圣诞装', '制服', '角色扮演', '兔女郎', '丁字裤',
                  '开裆', '免脱', '三点', '女仆', '连体衣', '绳衣')


class ProductLister:
    def __init__(self, test_mode=False, limit=0):
        self.browser = None
        self.context = None
        self.processed = set()
        self.failed = []
        self.count = 0
        self.test_mode = test_mode
        self.limit = limit
        self.last_error = ""
        self.session_failed = set()
        self.load_progress()

    def load_progress(self):
        path = os.path.join(BASE_DIR, PROGRESS_FILE)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.processed = set(data.get('processed', []))
                self.failed = data.get('failed', [])
                self.count = data.get('count', 0)
                logger.info(f"加载进度: 已处理 {len(self.processed)} 个, 失败 {len(self.failed)} 个")

    def save_progress(self, product_id=None, status='processed', error=None, title=None):
        if product_id:
            if status == 'processed':
                self.processed.add(product_id)
            elif status == 'failed':
                rec = {'id': product_id, 'error': str(error)}
                if title:
                    rec['title'] = str(title)
                self.failed.append(rec)
        self.count = len(self.processed)
        path = os.path.join(BASE_DIR, PROGRESS_FILE)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'processed': list(self.processed),
                'failed': self.failed,
                'count': self.count
            }, f, ensure_ascii=False, indent=2)

    async def connect(self):
        async with async_playwright() as p:
            self.browser = await p.chromium.connect_over_cdp(CDP_URL)
            self.context = self.browser.contexts[0]
            logger.info("已连接到Chrome")
            await self.run()

    async def detect_slider(self, page):
        """检测滑块验证 - 只检测真实可见且有大小的验证码元素"""
        async def check_el(el):
            try:
                if not await el.is_visible():
                    return False
                box = await el.bounding_box()
                if not box:
                    return False
                if box['width'] > 150 and box['height'] > 30:
                    return True
            except:
                pass
            return False

        for selector in SLIDER_SELECTORS:
            try:
                for frame in page.frames:
                    el = await frame.query_selector(selector)
                    if el and await check_el(el):
                        box = await el.bounding_box()
                        logger.warning(f"[滑块检测] selector={selector} frame={frame.url[:40]} size={int(box['width'])}x{int(box['height'])}")
                        return True
            except:
                pass
        return False

    async def random_delay(self):
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        logger.info(f"等待 {delay:.1f} 秒...")
        await asyncio.sleep(delay)

    async def batch_break(self):
        if self.count > 0 and self.count % BATCH_200 == 0:
            delay = random.uniform(BATCH_200_BREAK_MIN, BATCH_200_BREAK_MAX)
            logger.info(f"已处理 {self.count} 个，休息 {delay/60:.1f} 分钟...")
            await asyncio.sleep(delay)
        elif self.count > 0 and self.count % BATCH_50 == 0:
            delay = random.uniform(BATCH_50_BREAK_MIN, BATCH_50_BREAK_MAX)
            logger.info(f"已处理 {self.count} 个，休息 {delay/60:.1f} 分钟...")
            await asyncio.sleep(delay)

    async def human_click(self, page, selector):
        """模拟人类点击"""
        el = await page.query_selector(selector)
        if not el:
            logger.warning(f"元素未找到: {selector}")
            return False
        box = await el.bounding_box()
        if box:
            x = box['x'] + box['width'] / 2 + random.uniform(-3, 3)
            y = box['y'] + box['height'] / 2 + random.uniform(-3, 3)
            await page.mouse.move(x, y, steps=random.randint(8, 20))
            await asyncio.sleep(random.uniform(0.1, 0.4))
            await page.mouse.click(x, y)
        else:
            await el.click()
        return True

    async def human_type(self, page, selector, text):
        """模拟人类输入"""
        el = await page.query_selector(selector)
        if not el:
            return False
        await el.click()
        await asyncio.sleep(random.uniform(0.1, 0.3))
        await el.fill('')
        for char in text:
            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.03, 0.1))
        return True

    async def process_edit_page(self, page):
        """处理商品编辑页面"""
        logger.info("=" * 50)
        logger.info("开始处理商品编辑页面")

        await page.wait_for_load_state('networkidle', timeout=30000)
        await asyncio.sleep(random.uniform(1, 2))

        # 无店铺草稿检测:跳到 category.htm(发布页)而非 render.htm(草稿编辑页)-> 该商品无草稿,跳过
        if 'category.htm' in page.url and 'render.htm' not in page.url:
            logger.warning(f"  无店铺草稿(跳到 category.htm 发布页),跳过该商品: {page.url[:60]}")
            self.last_error = "无店铺草稿(category.htm)"
            return False

        # 滑块检测
        if await self.detect_slider(page):
            logger.error("检测到滑块验证！暂停处理")
            self.last_error = "滑块验证"
            return False

        # 1. 读取商品标题
        title = await page.locator('#sell-field-title input').input_value()
        # 1a. 标题优化(去品牌/货号/1688痕迹,控长≤30)
        try:
            new_title = rewrite_title(title)
            if new_title and new_title != title:
                await page.locator('#sell-field-title input').fill(new_title)
                logger.info(f"  标题优化: {title[:30]} -> {new_title[:30]}")
                title = new_title
        except Exception as e:
            logger.warning(f"  标题优化失败: {e}")
        logger.info(f"商品标题: {title}")
        if not title:
            logger.error("无法读取商品标题")
            self.last_error = "无法读取商品标题"
            return False

        # 1b. 填"产品名称"(组合框,必填,值=类目名称最后一段;提前填,省二层提交重试)
        try:
            cat_last = await page.evaluate("""()=>{
                const el = Array.from(document.querySelectorAll('*')).find(e=>e.children.length===0 && (e.textContent||'').includes('当前类目'));
                if(!el) return '';
                const m = (el.textContent||'').match(/当前类目[：:]\\s*(.+)/);
                if(!m) return '';
                const parts = m[1].split(/>>|>|\/|\\\\/).map(s=>s.trim()).filter(Boolean);
                return parts.length ? parts[parts.length-1] : '';
            }""")
            if cat_last:
                pname_loc = page.locator('#struct-catProp input[itemlabel="产品名称"], #sell-field-catProp input[itemlabel="产品名称"]')
                if await pname_loc.count() > 0:
                    await pname_loc.first.click()
                    await asyncio.sleep(0.4)
                    await pname_loc.first.fill(cat_last)
                    await asyncio.sleep(0.3)
                    await pname_loc.first.press('Tab')
                    logger.info(f"  已填 产品名称 = {cat_last}(类目最后一段)")
        except Exception as e:
            logger.warning(f"  填产品名称异常: {e}")

        # 2. 填写货号/款号 - 用Playwright原生fill
        style_num = generate_style_number()
        logger.info(f"生成款号: {style_num}")
        huohao = page.locator('input[itemlabel="货号"], input[itemlabel="款号"]')
        if await huohao.count() > 0:
            try:
                await huohao.first.click(timeout=5000)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await huohao.first.fill(style_num, timeout=5000)
                logger.info(f"  货号已填写: {style_num}")
            except Exception as e:
                logger.warning(f"  货号填写失败: {str(e)[:50]}")
        else:
            logger.warning("未找到货号输入框")
        await asyncio.sleep(random.uniform(0.5, 1))

        # 3. 价格×3 - 一口价
        price_loc = page.locator('#sell-field-price input')
        base_price = 1.01
        if await price_loc.count() > 0:
            old_price = await price_loc.first.input_value()
            try:
                old_val = float(old_price)
                if old_val <= 0:
                    new_price = "1.01"
                else:
                    new_price = f"{old_val * 3:.2f}"
                base_price = float(new_price)
                await price_loc.first.click(timeout=5000)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await price_loc.first.fill(new_price, timeout=5000)
                logger.info(f"一口价: {old_price} -> {new_price}")
            except ValueError:
                logger.warning(f"一口价值异常: {old_price}")
        await asyncio.sleep(random.uniform(0.3, 0.5))

        # 3b. 价格×3 - SKU价格(逐个 scrollIntoView + fill + Tab,确保全部覆盖且框架注册)
        sku_inputs = page.locator('#sell-field-sku span.fusion-input input, #sell-field-sku span.next-input input')
        sku_count = await sku_inputs.count()
        sku_changed = 0
        for i in range(sku_count):
            try:
                inp = sku_inputs.nth(i)
                await inp.scroll_into_view_if_needed(timeout=5000)
                val = await inp.input_value(timeout=5000)
                ph = await inp.get_attribute('placeholder') or ''
            except:
                continue
            is_price = (val and '.' in val) or '价' in ph or '元' in ph
            if is_price and val:
                try:
                    old_p = float(val)
                    if old_p <= 0:
                        new_p = f"{base_price:.2f}" if base_price > 0 else "1.01"
                    else:
                        new_p = f"{old_p * 3:.2f}"
                    await inp.fill(new_p, timeout=8000)
                    await inp.press('Tab')
                    sku_changed += 1
                    if sku_changed <= 8:
                        logger.info(f"  SKU价格: {old_p} -> {new_p}")
                except ValueError:
                    pass
                except Exception as e:
                    logger.warning(f"  SKU改价异常[{i}]: {e}")
        logger.info(f"  SKU改价 {sku_changed} 个")
        # 3b-补:0库存/被禁用的 SKU 价格也 ×3(evaluate 解禁 + click + native setter,fill 跳过的这里补)
        try:
            fixed_dis = await page.evaluate(f"""
                () => {{
                    const base = {base_price};
                    const sku = document.querySelector('#sell-field-sku');
                    if(!sku) return 0;
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    let count = 0;
                    const inputs = sku.querySelectorAll('input');
                    for(const inp of inputs){{
                        const v = inp.value || '';
                        const ph = inp.placeholder || '';
                        const isPrice = v.includes('.') || ph.includes('价格') || ph.includes('价') || ph.includes('元');
                        if(!isPrice) continue;
                        const oldNum = parseFloat(v);
                        const newP = (isNaN(oldNum) || oldNum <= 0) ? (base > 0 ? base : 1.01) : Math.round(oldNum * 3 * 100) / 100;
                        const newStr = newP.toFixed(2);
                        if(v !== newStr){{
                            if(!inp.disabled){{ inp.click(); }}
                            setter.call(inp, newStr);
                            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                            inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                            inp.dispatchEvent(new Event('blur', {{bubbles: true}}));
                            count++;
                        }}
                    }}
                    return count;
                }}
            """)
            if fixed_dis:
                logger.info(f"  补改 {fixed_dis} 个(0库存/禁用)SKU价格")
        except Exception as e:
            logger.warning(f"  补改禁用SKU异常: {e}")
        await asyncio.sleep(random.uniform(0.5, 1))

        # 3c. 复查SKU区域: 找出任何遗漏的0价格并修复 (扫描所有input)
        try:
            fixed = await page.evaluate(f"""
                () => {{
                    const base = {base_price};
                    const skuArea = document.querySelector('#sell-field-sku');
                    if (!skuArea) return 0;
                    let count = 0;
                    const inputs = skuArea.querySelectorAll('input');
                    for (const inp of inputs) {{
                        const v = inp.value;
                        // 价格特征: 带小数点 或 placeholder含"价格"或"价"
                        const isPrice = v.includes('.') || (inp.placeholder && (inp.placeholder.includes('价格') || inp.placeholder.includes('价')));
                        if (isPrice) {{
                            const num = parseFloat(v);
                            if (isNaN(num) || num === 0) {{
                                inp.click();
                                inp.value = base.toFixed(2);
                                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                                inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                                inp.dispatchEvent(new Event('blur', {{bubbles: true}}));
                                count++;
                            }}
                        }}
                    }}
                    return count;
                }}
            """)
            if fixed:
                logger.info(f"  复查修复了 {fixed} 个0价格SKU")
        except:
            pass

        # 4. 店铺中分类 - 选择第一个选项"家居服/睡衣"
        logger.info("选择店铺中分类...")
        await page.locator('#sell-field-shopcat .next-select-trigger').click()
        try:
            await page.wait_for_selector('.next-overlay-inner .next-tree-node', timeout=5000)
            # 点击第一个树节点的checkbox (不是li，不是label文字，是checkbox wrapper)
            checkbox = page.locator('.next-overlay-inner .next-tree-node .next-checkbox-wrapper').first
            await checkbox.click()
            node_text = await page.locator('.next-overlay-inner .next-tree-node .next-tree-node-label').first.inner_text()
            logger.info(f"  选择: {node_text.strip()}")
            await asyncio.sleep(0.5)
            # 验证checkbox是否选中
            is_checked = await page.evaluate("""
                () => {
                    const cb = document.querySelector('.next-overlay-inner .next-tree-node .next-checkbox-wrapper');
                    return cb ? (cb.classList.contains('checked') || cb.getAttribute('aria-checked') === 'true') : false;
                }
            """)
            if not is_checked:
                logger.warning("  checkbox未选中，重试...")
                await checkbox.click()
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.warning(f"  店铺中分类选择失败: {e}")
        await asyncio.sleep(random.uniform(0.5, 1))
        await page.mouse.click(10, 10)
        await asyncio.sleep(random.uniform(0.3, 0.5))

        # 5. 上架时间 - 选择"放入仓库" (关键!)
        logger.info("设置上架时间: 放入仓库")
        radio_clicked = False
        # 尝试多种选择器
        for selector in [
            '#sell-field-startTime .radio-item:has-text("放入仓库")',
            '#sell-field-startTime label:has-text("放入仓库")',
            '#sell-field-startTime .sell-radio:has-text("放入仓库")',
        ]:
            loc = page.locator(selector)
            if await loc.count() > 0:
                await loc.first.click()
                radio_clicked = True
                logger.info(f"  放入仓库 已点击 (selector: {selector})")
                break
        if not radio_clicked:
            logger.error("  未找到'放入仓库'选项!")
        await asyncio.sleep(random.uniform(1, 2))

        # 验证上架时间 - 用aria-checked检测
        listing_check = await page.evaluate("""
            () => {
                const el = document.querySelector('#sell-field-startTime');
                if (!el) return {found: false};
                const wrappers = el.querySelectorAll('.next-radio-wrapper');
                let selected = '';
                for (const w of wrappers) {
                    if (w.getAttribute('aria-checked') === 'true' || w.classList.contains('checked')) {
                        selected = w.closest('.radio-item')?.textContent?.trim().substring(0, 20) || '';
                        break;
                    }
                }
                return {found: true, selected: selected};
            }
        """)
        logger.info(f"  验证上架时间: selected='{listing_check.get('selected')}'")
        if '放入仓库' not in (listing_check.get('selected') or ''):
            logger.warning("  上架时间未选中'放入仓库'，重试...")
            # 直接点击 input radio
            await page.locator('#sell-field-startTime .radio-item:has-text("放入仓库") input[type="radio"]').click()
            await asyncio.sleep(1)

        # 6. 商品预检 - 开启 (关键! 必须在放入仓库之后)
        # 预检 disabled 有两种原因:① 放入仓库未生效(重试点放入仓库可恢复) ② 每日预检次数耗尽(跳过预检直接提交)
        logger.info("开启商品预检...")
        precheck = page.locator('#sell-field-ysbCheckTask .next-checkbox-wrapper')
        precheck_enabled = False
        if await precheck.count() > 0:
            for attempt in range(2):
                state = await precheck.first.evaluate("""
                    el => ({
                        checked: el.classList.contains('checked') || el.getAttribute('aria-checked') === 'true',
                        disabled: el.classList.contains('disabled')
                    })
                """)
                if state['checked']:
                    precheck_enabled = True
                    logger.info(f"  商品预检 已开启(尝试 {attempt+1})")
                    break
                if not state['disabled']:
                    await precheck.first.click()
                    await asyncio.sleep(0.5)
                    v = await precheck.first.evaluate("el => el.classList.contains('checked') || el.getAttribute('aria-checked') === 'true'")
                    if v:
                        precheck_enabled = True
                        logger.info(f"  商品预检 已点击开启(尝试 {attempt+1})")
                        break
                else:
                    logger.warning(f"  预检disabled,重试点放入仓库(尝试 {attempt+1}/2)")
                    try:
                        await page.locator('#sell-field-startTime .radio-item:has-text("放入仓库") input[type="radio"]').click(timeout=3000)
                    except:
                        try:
                            await page.locator('#sell-field-startTime .radio-item:has-text("放入仓库")').first.click(timeout=3000)
                        except:
                            pass
                    await asyncio.sleep(2)
            if not precheck_enabled:
                logger.warning("  ⚠️ 预检2次重试仍disabled(可能每日次数耗尽),跳过预检直接提交")
        else:
            logger.warning("  未找到商品预检复选框,跳过预检")
        await asyncio.sleep(random.uniform(0.5, 1))

        # 验证商品预检
        precheck_check = await page.evaluate("""
            () => {
                const el = document.querySelector('#sell-field-ysbCheckTask .next-checkbox-wrapper');
                if (!el) return {found: false};
                return {
                    found: true,
                    is_checked: el.classList.contains('checked') || el.getAttribute('aria-checked') === 'true',
                    is_disabled: el.classList.contains('disabled'),
                    class: el.className.substring(0, 60)
                };
            }
        """)
        logger.info(f"  验证预检: checked={precheck_check.get('is_checked')}, disabled={precheck_check.get('is_disabled')}")

        # 滑块检测
        if await self.detect_slider(page):
            logger.error("检测到滑块验证！暂停处理")
            return False

        # 7. 提交前: 诊断必填字段 (仅供日志，不阻塞)
        await self.scan_required_fields(page)

        # 8. 提交
        if self.test_mode:
            logger.info("[测试模式] 跳过提交，保存截图...")
            screenshot_path = os.path.join(BASE_DIR, f"test_screenshot_{int(time.time())}.png")
            await page.screenshot(path=screenshot_path, full_page=False)
            logger.info(f"截图已保存: {screenshot_path}")
            return True

        logger.info("提交商品...")
        self.last_error = ""
        submit_result = await self.do_submit(page)
        if submit_result[0]:
            return True

        # 滑块触发 -> 不重试,直接返回失败(页面已跳转,重试必失败)
        if '滑块' in submit_result[1]:
            self.last_error = "滑块验证"
            return False

        # 其他提交失败: 可能是属性缺太多。补属性后重试
        logger.info("首次提交失败，填充类目属性后重试...")
        await self.fill_category_attributes(page, title)
        await asyncio.sleep(random.uniform(1, 2))

        # 滑块检测
        if await self.detect_slider(page):
            logger.error("补属性后检测到滑块验证！暂停处理")
            self.last_error = "滑块验证"
            return False

        result2 = await self.do_submit(page)
        if not result2[0]:
            self.last_error = result2[1]
        return result2[0]

    async def do_submit(self, page):
        """点击提交按钮并验证结果，返回 (是否成功, 错误原因)"""
        submit_btn = page.locator('button', has_text='提交宝贝信息').first
        if await submit_btn.count() > 0:
            text = (await submit_btn.inner_text()).strip()
            logger.info(f"  点击: {text}")
            await submit_btn.click()
            return await self.verify_submission(page)
        else:
            logger.error("未找到提交按钮")
            return (False, "未找到提交按钮")

    async def fill_category_attributes(self, page, title):
        """填充类目属性中空的必填项 - 根据属性名和商品标题推断"""
        # 属性值推断规则: 属性名 -> 优先尝试的值列表
        attr_rules = {
            '面料': ['聚酯纤维', '珊瑚绒', '网纱', '棉'],
            '款式': ['多件套式', '长裙式', '分体式', '背心式'],
            '产地': ['中国大陆', '中国'],
            '是否可外穿': ['是', '可外穿'],
            '柔软指数': ['柔软', '适中'],
            '版型': ['宽松', '常规'],
            '穿着方式': ['套头', '绑带', '系带'],
            '衣长': ['中长款', '长款', '常规'],
            '适用场景': ['居家', '家居', '日常'],
            '适用对象': ['青年', '女性', '通用'],
            '图案': ['纯色', '拼色', '印花'],
            '服装款式细节': ['蕾丝', '镂空', '印花'],
            '衣门襟': ['套头', '拉链', '系带'],
            '家居服风格': ['性感', '甜美', '简约'],
            '面料俗称': ['珊瑚绒', '聚酯纤维'],
            '厚薄': ['薄款', '适中', '加厚'],
            '袖长': ['长袖', '短袖'],
            '领型': ['圆领', 'V领', '一字领'],
            '主面料克重': ['200g', '300g'],
            '销售渠道类型': ['淘宝', '淘宝商城'],
        }

        # 根据商品标题调整部分规则
        if '植绒' in title or '珊瑚绒' in title or '摇粒绒' in title:
            attr_rules['面料'] = ['珊瑚绒', '摇粒绒', '聚酯纤维']
        elif '蕾丝' in title:
            attr_rules['面料'] = ['网纱', '聚酯纤维', '蕾丝']
            attr_rules['服装款式细节'] = ['蕾丝', '镂空']
        elif '丝绒' in title:
            attr_rules['面料'] = ['平绒', '珊瑚绒', '聚酯纤维']
        if '甜美' in title or '可爱' in title or '纯欲' in title:
            attr_rules['家居服风格'] = ['甜美', '性感']
        elif '性感' in title or '诱惑' in title:
            attr_rules['家居服风格'] = ['性感', '甜美']
        if '睡裙' in title or '吊带' in title:
            attr_rules['款式'] = ['长裙式', '吊带式', '背心式']
        if '套装' in title or '分体' in title:
            attr_rules['款式'] = ['多件套式', '分体式']
        if '长袖' in title:
            attr_rules['袖长'] = ['长袖']

        logger.info("填充类目属性...")
        # 先填"产品名称"(组合框,必填,值=类目名称最后一段;需点击聚焦让框架注册)
        try:
            cat_last = await page.evaluate("""()=>{
                const el = Array.from(document.querySelectorAll('*')).find(e=>e.children.length===0 && (e.textContent||'').includes('当前类目'));
                if(!el) return '';
                const m = (el.textContent||'').match(/当前类目[：:]\\s*(.+)/);
                if(!m) return '';
                const parts = m[1].split(/>>|>|\/|\\\\/).map(s=>s.trim()).filter(Boolean);
                return parts.length ? parts[parts.length-1] : '';
            }""")
            if cat_last:
                pname_loc = page.locator('#struct-catProp input[itemlabel="产品名称"], #sell-field-catProp input[itemlabel="产品名称"]')
                if await pname_loc.count() > 0:
                    await pname_loc.first.click()  # 聚焦(定位光标)
                    await asyncio.sleep(0.4)
                    await pname_loc.first.fill(cat_last)  # 类型化输入,框架注册
                    await asyncio.sleep(0.3)
                    await pname_loc.first.press('Tab')  # 失焦确认
                    logger.info(f"  已填 产品名称 = {cat_last}(类目最后一段)")
                else:
                    logger.warning("  未找到产品名称 input")
            else:
                logger.warning("  未取到类目名称,跳过产品名称")
        except Exception as e:
            logger.warning(f"  填产品名称异常: {e}")
        try:
            # 找到所有空的属性下拉
            items = await page.evaluate("""
                () => {
                    const section = document.querySelector('#struct-catProp') || document.querySelector('#sell-field-catProp');
                    if (!section) return [];
                    const result = [];
                    const attrItems = section.querySelectorAll('div.sell-catProp-item');
                    for (const item of attrItems) {
                        const label = item.querySelector('label.label');
                        const select = item.querySelector('.next-select');
                        if (label && select) {
                            const selectText = select.textContent.trim();
                            const labelText = label.textContent.trim();
                            // 跳过材质成分(单独处理)
                            if (labelText.includes('材质成分')) continue;
                            // 只处理显示"请选择"的空下拉
                            if (selectText.includes('请选择')) {
                                result.push({id: item.id, label: labelText});
                            }
                        }
                    }
                    return result;
                }
            """)

            filled_count = 0
            for item in items:
                attr_id = item['id']
                label = item['label']
                if not label:
                    continue

                # 打开下拉
                await page.evaluate("""
                    (id) => {
                        const el = document.getElementById(id);
                        const select = el.querySelector('.next-select');
                        if (select) { select.click(); return true; }
                        return false;
                    }
                """, attr_id)
                await asyncio.sleep(random.uniform(1, 2))

                # 读取选项 (自定义组件 sell-o-select-options)
                options = await page.evaluate("""
                    () => {
                        const seen = new Set();
                        const result = [];
                        // 自定义下拉组件选项
                        const items = document.querySelectorAll('.sell-o-select-options .options-item, .next-overlay-inner .options-item, [class*="options-item"]');
                        for (const m of items) {
                            if (m.offsetParent !== null) {
                                const t = m.textContent.trim();
                                if (t && t.length < 30 && !seen.has(t)) {
                                    seen.add(t);
                                    result.push(t);
                                }
                            }
                        }
                        // 兜底: 标准菜单
                        if (result.length === 0) {
                            const items2 = document.querySelectorAll('.next-overlay-inner [class*="menu-item"]');
                            for (const m of items2) {
                                if (m.offsetParent !== null) {
                                    const t = m.textContent.trim();
                                    if (t && t.length < 30 && !seen.has(t)) {
                                        seen.add(t);
                                        result.push(t);
                                    }
                                }
                            }
                        }
                        return result;
                    }
                """)

                # 根据规则选择值
                suggested = attr_rules.get(label, [])
                chosen = None
                for s in suggested:
                    for o in options:
                        if s in o or o in s:
                            chosen = o
                            break
                    if chosen:
                        break
                # 兜底: 选第一个非空选项
                if not chosen and options:
                    chosen = options[0]

                if chosen:
                    await page.evaluate("""
                        (text) => {
                            const items = document.querySelectorAll('.sell-o-select-options .options-item, .next-overlay-inner .options-item, [class*="options-item"]');
                            for (const m of items) {
                                if (m.offsetParent !== null && m.textContent.trim() === text) {
                                    m.click();
                                    return true;
                                }
                            }
                            // 兜底: 标准菜单
                            const items2 = document.querySelectorAll('.next-overlay-inner [class*="menu-item"]');
                            for (const m of items2) {
                                if (m.offsetParent !== null && m.textContent.trim() === text) {
                                    m.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """, chosen)
                    await asyncio.sleep(random.uniform(0.8, 1.5))
                    # 验证选择是否生效
                    verify = await page.evaluate("""
                        (id) => {
                            const el = document.getElementById(id);
                            if (!el) return false;
                            const select = el.querySelector('.next-select');
                            const text = select ? select.textContent.trim() : '';
                            return text && !text.includes('请选择');
                        }
                    """, attr_id)
                    if verify:
                        logger.info(f"  属性[{label}]: 选择 '{chosen}' ✓")
                        filled_count += 1
                    else:
                        logger.warning(f"  属性[{label}]: 选择 '{chosen}' 未生效，重试...")
                        # 重试点击选项
                        await page.evaluate("""
                            (id) => {
                                const el = document.getElementById(id);
                                if (!el) return false;
                                const select = el.querySelector('.next-select');
                                if (select) select.click();
                                return true;
                            }
                        """, attr_id)
                        await asyncio.sleep(1)
                        await page.evaluate("""
                            (text) => {
                                const items = document.querySelectorAll('.sell-o-select-options .options-item, [class*="options-item"]');
                                for (const m of items) {
                                    if (m.offsetParent !== null && m.textContent.trim() === text) {
                                        m.click(); return true;
                                    }
                                }
                                return false;
                            }
                        """, chosen)
                        await asyncio.sleep(1)
                else:
                    logger.warning(f"  属性[{label}]: 无可用选项，跳过")

                await asyncio.sleep(random.uniform(0.5, 1))
                # 关闭可能残留的下拉
                await page.mouse.click(10, 10)
                await asyncio.sleep(random.uniform(0.3, 0.6))

            logger.info(f"  共填充 {filled_count} 个属性下拉")

            # 诊断:扫描仍为空的必填类目属性(label.required),定位阻断项
            try:
                empty_req = await page.evaluate("""()=>{
                    const root = document.querySelector('#struct-catProp') || document.querySelector('#sell-field-catProp');
                    if(!root) return [];
                    const out = [];
                    root.querySelectorAll('label.required, label.label.required').forEach(lbl=>{
                        const name = lbl.textContent.trim().replace('*','').trim();
                        let p=lbl;
                        for(let i=0;i<6 && p;i++){ p=p.parentElement; if(!p) break; }
                        const container = p || lbl.parentElement;
                        const allText = container.innerText.replace(/\\s+/g,' ').trim();
                        // 判断是否未填:含"请选择"或"请输入"且无实际值
                        const sel = container.querySelector('.next-select');
                        const selText = sel ? sel.textContent.trim() : '';
                        const inp = container.querySelector('input');
                        const inpVal = inp ? inp.value : '';
                        const unfilled = (selText.includes('请选择') || (inp && !inpVal && !selText));
                        if(unfilled) out.push(name + '(' + (selText||inpVal||'空') + ')');
                    });
                    return out;
                }""")
                if empty_req:
                    logger.warning(f"  ⚠️ 仍为空的必填类目属性: {empty_req}")
            except Exception:
                pass

            # 处理数字输入框 (吊牌价等)
            num_inputs = await page.evaluate("""
                () => {
                    const section = document.querySelector('#struct-catProp') || document.querySelector('#sell-field-catProp');
                    if (!section) return [];
                    const result = [];
                    const items = section.querySelectorAll('div.sell-catProp-item');
                    for (const item of items) {
                        const label = item.querySelector('label.label');
                        const input = item.querySelector('input[type="text"], input:not([type])');
                        if (label && input && !input.value) {
                            const ph = input.placeholder || '';
                            if (ph.includes('数字') || ph.includes('整数') || ph.includes('元')) {
                                result.push({id: item.id, label: label.textContent.trim(), ph: ph});
                            }
                        }
                    }
                    return result;
                }
            """)
            for ni in num_inputs:
                try:
                    label = ni['label']
                    # 吊牌价填一个合理数字
                    price_val = '99'
                    if '吊牌价' in label:
                        price_val = str(random.randint(89, 199))
                    await page.locator(f'#{ni["id"]} input').first.click()
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                    await page.locator(f'#{ni["id"]} input').first.fill(price_val)
                    logger.info(f"  数字[{label}]: 填 '{price_val}'")
                    await asyncio.sleep(random.uniform(0.5, 1))
                except Exception as e:
                    logger.warning(f"  数字[{ni['label']}] 填写失败: {e}")
        except Exception as e:
            logger.warning(f"  填充类目属性异常: {e}")

    async def scan_required_fields(self, page):
        """诊断: 扫描所有 sell-field 区域，找出空的必填字段"""
        logger.info("扫描必填字段...")
        try:
            fields = await page.evaluate("""
                () => {
                    const results = [];
                    const els = document.querySelectorAll('[id^="sell-field-"], [id^="struct-"]');
                    for (const el of els) {
                        const id = el.id;
                        // 只处理带标签的字段
                        const label = el.querySelector('.sell-component-info-wrapper-label, [class*="label"]');
                        const labelText = label ? label.textContent.trim() : '';
                        if (!labelText && !id.includes('struct')) continue;
                        
                        const text = el.textContent;
                        const isRequired = text.includes('*') || labelText.includes('*');
                        
                        // 判断是否为空: 检查输入框值 / select文本 / checkbox状态
                        const inputs = el.querySelectorAll('input[type="text"], input:not([type]), textarea');
                        const selects = el.querySelectorAll('.next-select, select, [class*="select-trigger"]');
                        
                        let isEmpty = false;
                        let inputValue = '';
                        
                        if (inputs.length > 0) {
                            inputValue = inputs[0].value || '';
                            isEmpty = !inputValue.trim();
                        } else if (selects.length > 0) {
                            const selectText = selects[0].textContent.trim();
                            const placeholderWords = ['请选择', '选择分类', '请输入', '模板'];
                            isEmpty = !selectText || placeholderWords.some(w => selectText.includes(w));
                        } else {
                            // 没有输入框和select，跳过
                            continue;
                        }
                        
                        results.push({
                            id: id,
                            label: labelText,
                            is_required: isRequired,
                            isEmpty: isEmpty,
                            value: inputValue.substring(0, 30) || (selects.length > 0 ? selects[0].textContent.trim().substring(0, 30) : '')
                        });
                    }
                    return results;
                }
            """)
            
            empty_required = [f for f in fields if f.get('is_required') and f.get('isEmpty')]
            if empty_required:
                logger.warning(f"  发现 {len(empty_required)} 个空的必填字段:")
                for f in empty_required:
                    logger.warning(f"    - [{f['id']}] {f['label']}")
            else:
                logger.info("  所有必填字段已填写")
            
            # 检查是否有错误提示
            errors = await page.evaluate("""
                () => {
                    const errs = document.querySelectorAll('.next-input-error, .has-error, [class*="form-error"], .next-error, [class*="field-error"]');
                    const results = [];
                    for (const e of errs) {
                        if (e.offsetParent !== null) {
                            const text = e.textContent.trim();
                            if (text) results.push(text.substring(0, 60));
                        }
                    }
                    return results;
                }
            """)
            if errors:
                logger.warning(f"  页面错误提示: {errors[:5]}")
        except Exception as e:
            logger.warning(f"  扫描必填字段异常: {e}")

    async def verify_submission(self, page, timeout=15):
        """验证提交是否成功 - 优先通过URL判断(success.htm)。返回(是否成功, 错误原因)"""
        for i in range(timeout):
            await asyncio.sleep(1)

            # 1. URL变成 success.htm -> 提交成功
            try:
                if 'success.htm' in page.url:
                    logger.info(f"  提交成功! URL: {page.url[:60]}")
                    return (True, "")
            except:
                pass

            # 2. 滑块检测 -> 暂停等待手动验证,验证后重新提交
            if await self.detect_slider(page):
                logger.warning("⚠️ 检测到滑块验证！请在 Chrome 窗口手动完成滑块,脚本自动等待(最多10分钟)...")
                solved = False
                for _ in range(120):  # 120 * 5s = 10分钟
                    await asyncio.sleep(5)
                    if not await self.detect_slider(page):
                        solved = True
                        break
                if solved:
                    logger.info("✅ 滑块已手动验证,重新点击提交")
                    await asyncio.sleep(2)
                    try:
                        sb = page.locator('button', has_text='提交宝贝信息').first
                        if await sb.count() > 0:
                            await sb.click()
                            await asyncio.sleep(3)
                    except:
                        pass
                    continue  # 继续循环检查提交结果
                else:
                    logger.error("等待滑块验证超时(10分钟),跳过")
                    return (False, "滑块验证超时")

            # 3. 检查错误弹窗 (包裹try/except防止页面跳转时崩溃)
            try:
                result = await page.evaluate("""
                () => {
                    const errorKeywords = ['请填写', '请选择', '不能为空', '请输入', '提交失败', '发布失败',
                                            '保存失败', '校验失败', '有错误', '失败', '错误', '必填',
                                            '缺失', '不正确', '未填写', '请完善', '请先',
                                            '重复铺货', '重复发布', '重复商品'];
                    const dialogs = document.querySelectorAll('.next-dialog, .next-overlay-inner, [class*="dialog"], [class*="modal"]');
                    for (const d of dialogs) {
                        if (d.offsetParent === null) continue;
                        const text = d.textContent.trim();
                        if (!text) continue;
                        for (const kw of errorKeywords) {
                            if (text.includes(kw)) {
                                return {status: 'error', text: text.substring(0, 150)};
                            }
                        }
                    }
                    // 检查页面校验错误指示器 "错误(N)"
                    const indicators = document.querySelectorAll('[class*="assistant-navtab"], [class*="error-count"], [class*="navtab"]');
                    for (const ind of indicators) {
                        if (ind.offsetParent === null) continue;
                        const text = ind.textContent.trim();
                        const m = text.match(/错误\\((\\d+)\\)/);
                        if (m && parseInt(m[1]) > 0) {
                            return {status: 'error', text: '校验错误数: ' + m[1] + ' | ' + text.substring(0, 80)};
                        }
                    }
                    // 检查页面主体中的错误提示
                    const body = document.body ? document.body.innerText : '';
                    const errMatch = body.match(/错误\\((\\d+)\\)/);
                    if (errMatch && parseInt(errMatch[1]) > 0) {
                        // 找出具体报错的字段 (红色边框/错误提示)
                        const errorFields = [];
                        const errEls = document.querySelectorAll('.next-input.has-error, .next-input-error, .has-error, [class*="error"] input, [class*="error"] select');
                        for (const e of errEls) {
                            if (e.offsetParent === null) continue;
                            // 找到这个字段的标签
                            let label = '';
                            let p = e;
                            for (let i = 0; i < 5; i++) {
                                p = p.parentElement;
                                if (!p) break;
                                const lbl = p.querySelector('.sell-catProp-item label, label.label, .sell-component-info-wrapper-label');
                                if (lbl) { label = lbl.textContent.trim().substring(0, 20); break; }
                            }
                            if (label) errorFields.push(label);
                        }
                        // 也检查红色错误提示文本
                        const redTexts = [];
                        document.querySelectorAll('.next-input-error-message, [class*="error-message"], [class*="err-msg"]').forEach(e => {
                            if (e.offsetParent !== null && e.textContent.trim()) {
                                redTexts.push(e.textContent.trim().substring(0, 40));
                            }
                        });
                        return {status: 'error', text: '错误数:' + errMatch[1] + ' 字段:' + (errorFields.join(',') || '未知') + (redTexts.length ? ' 提示:' + redTexts.join(',') : '')};
                    }
                    return null;
                }
            """)
            except Exception:
                # 页面可能在跳转到success.htm，检查URL
                try:
                    if 'success.htm' in page.url:
                        logger.info(f"  提交成功(跳转中)! URL: {page.url[:60]}")
                        return (True, "")
                except:
                    pass
                await asyncio.sleep(1)
                continue
            if result:
                reason = result.get('text', '')
                logger.error(f"  提交失败原因: {reason}")
                return (False, reason)

        # 超时
        logger.warning(f"  提交结果不确定，当前URL: {page.url[:60]}")
        # 捕获可见弹窗文本
        try:
            dialog_text = await page.evaluate("""
                () => {
                    const dialogs = document.querySelectorAll('.next-dialog, .next-overlay-inner, [class*="dialog"], [class*="modal"], [class*="message"], [class*="toast"]');
                    const texts = [];
                    for (const d of dialogs) {
                        if (d.offsetParent !== null && d.textContent.trim()) {
                            texts.push(d.textContent.trim().substring(0, 200));
                        }
                    }
                    return texts;
                }
            """)
            if dialog_text:
                logger.warning(f"  可见弹窗: {dialog_text[:3]}")
        except:
            pass
        screenshot_path = os.path.join(BASE_DIR, f"submit_unknown_{int(time.time())}.png")
        try:
            await page.screenshot(path=screenshot_path, full_page=False)
        except:
            pass
        # 最终检查URL
        if 'success.htm' in page.url:
            return (True, "")
        return (False, "提交结果不确定")
        try:
            title = await page.title()
            logger.warning(f"  当前页面标题: {title}")
            if '发布' in title and '成功' in title:
                return True
        except:
            pass
        return False

    async def find_1688_page(self):
        for page in self.context.pages:
            if 'ufuwu.1688.com' in page.url or 'fuwu_work_isv' in page.url:
                return page
        return None

    async def find_edit_page(self):
        for page in self.context.pages:
            if 'item.upload.taobao.com' in page.url:
                return page
        return None

    async def close_orphan_edit_tabs(self, keep=None):
        """关闭所有残留的 item.upload 编辑tab (keep 指定保留的, 默认全关)"""
        if self.context is None:
            return
        for page in self.context.pages:
            try:
                if 'item.upload.taobao.com' in page.url and page is not keep:
                    await page.close()
            except Exception:
                pass

    async def get_isv_frame(self, isv_page):
        """获取ISV container frame (Frame 2)"""
        for frame in isv_page.frames:
            if 'isv-container' in (frame.url or ''):
                return frame
        # fallback: 最后一个非空frame
        for frame in isv_page.frames[::-1]:
            if frame.url and frame.url != 'about:blank':
                return frame
        return None

    async def get_product_rows(self, frame):
        """获取当前页所有商品行"""
        rows = await frame.evaluate("""
            () => {
                const tbody = document.querySelector('.ant-table-tbody');
                if (!tbody) return [];
                const trs = tbody.querySelectorAll('tr.ant-table-row');
                return Array.from(trs).map((tr, index) => {
                    const editBtn = Array.from(tr.querySelectorAll('button')).find(
                        b => b.textContent.includes('编辑店铺草稿')
                    );
                    const titleMatch = tr.textContent.match(/ID：(\\d+)/);
                    return {
                        index: index,
                        row_key: tr.getAttribute('data-row-key') || '',
                        product_id: titleMatch ? titleMatch[1] : '',
                        has_edit_btn: !!editBtn,
                        title: tr.textContent.trim().substring(0, 60)
                    };
                }).filter(r => r.has_edit_btn);
            }
        """)
        return rows

    async def click_edit_and_continue(self, frame, row_key=None):
        """点击指定行的'编辑店铺草稿'然后'继续上架'"""
        # 找到指定行的按钮并点击
        if row_key:
            clicked = await frame.evaluate("""
                (key) => {
                    const row = document.querySelector(`tr[data-row-key="${key}"]`);
                    if (!row) return false;
                    const btn = Array.from(row.querySelectorAll('button')).find(
                        b => b.textContent.includes('编辑店铺草稿')
                    );
                    if (btn) { btn.click(); return true; }
                    return false;
                }
            """, row_key)
            if not clicked:
                logger.warning(f"  未找到row_key={row_key}的编辑按钮，点击第一个...")
                await frame.locator('button:has-text("编辑店铺草稿")').first.click()
        else:
            await frame.locator('button:has-text("编辑店铺草稿")').first.click()

        logger.info("  已点击'编辑店铺草稿'")
        await asyncio.sleep(random.uniform(1.5, 3))

        # 等待弹框出现并点击"继续上架"
        try:
            await frame.wait_for_selector('.ant-modal button:has-text("继续上架")', timeout=10000)
            await frame.locator('.ant-modal button:has-text("继续上架")').first.click()
            logger.info("  已点击'继续上架'")
            return True
        except:
            logger.error("  未找到'继续上架'按钮")
            # 尝试关闭可能出现的弹框 (JS click 避免按钮内部 SVG 遮挡导致 Playwright 超时崩溃)
            try:
                await frame.evaluate(
                    "() => { const b = document.querySelector('.ant-modal-close'); if (b) b.click(); }"
                )
            except Exception:
                pass
            return False

    async def wait_for_edit_page(self, timeout=30):
        """等待淘宝编辑页面在新tab打开，并等待表单就绪"""
        for _ in range(timeout):
            await asyncio.sleep(1)
            edit_page = await self.find_edit_page()
            if edit_page:
                # 无草稿(category.htm 发布页)直接返回,不等加载,由 process_edit_page 跳过
                if 'category.htm' in edit_page.url and 'render.htm' not in edit_page.url:
                    return edit_page
                try:
                    await edit_page.wait_for_load_state('networkidle', timeout=30000)
                    # 等待标题输入框出现，确保表单已渲染
                    await edit_page.locator('#sell-field-title input').wait_for(state='visible', timeout=15000)
                except:
                    pass
                return edit_page
        return None

    async def close_edit_page(self, page):
        """关闭编辑页面tab"""
        try:
            await page.close()
        except:
            pass

    async def go_to_next_page(self, frame):
        """翻到下一页"""
        next_btn = frame.locator('.ant-pagination-next:not(.ant-pagination-disabled)')
        if await next_btn.count() > 0:
            await next_btn.first.click()
            await asyncio.sleep(random.uniform(2, 4))
            return True
        return False

    async def go_to_prev_page(self, frame):
        """翻到上一页"""
        prev_btn = frame.locator('.ant-pagination-prev:not(.ant-pagination-disabled)')
        if await prev_btn.count() > 0:
            await prev_btn.first.click()
            await asyncio.sleep(random.uniform(2, 4))
            return True
        return False

    async def get_total_pages(self, frame):
        """获取总页数(按每页100条估算)"""
        import re as _re
        text = await frame.evaluate("document.querySelector('.ant-pagination')?.textContent?.trim() || ''")
        m = _re.search(r'共(\d+)条', text)
        total = int(m.group(1)) if m else 0
        if total:
            return (total + 99) // 100
        # 兜底:页码 "X/Y" 格式
        m2 = _re.search(r'(\d+)\s*/\s*(\d+)', text)
        return int(m2.group(2)) if m2 else 0

    async def go_to_last_page(self, frame):
        """跳到最后一页"""
        total = await self.get_total_pages(frame)
        if not total:
            return False
        ok = await frame.evaluate("""(n)=>{
            const jumper = document.querySelector('.ant-pagination-options-quick-jumper input');
            if(!jumper) return false;
            jumper.focus();
            jumper.value = String(n);
            jumper.dispatchEvent(new Event('input',{bubbles:true}));
            jumper.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',bubbles:true}));
            return true;
        }""", total)
        if ok:
            await asyncio.sleep(4)
            return True
        return False

    async def close_any_modal(self, frame):
        """关闭可能残留的弹框 (JS click 避免按钮内部 SVG 遮挡导致 30s 卡顿)"""
        try:
            closed = await frame.evaluate(
                "() => { const b = document.querySelector('.ant-modal-close'); if (b) { b.click(); return true; } return false; }"
            )
            if closed:
                await asyncio.sleep(0.5)
                return True
        except:
            pass
        return False

    async def refresh_isv_list(self, frame):
        """每处理完一个商品后强制重新查询 ISV 铺货失败列表(重新点击铺货失败tab触发Ant重新查询), 并重新定位到最后一页"""
        try:
            clicked = await frame.evaluate("""() => {
                const tabs = Array.from(document.querySelectorAll('.ant-tabs-tab'));
                const fail = tabs.find(t => t.textContent.includes('铺货失败'));
                if (fail) { fail.click(); return true; }
                return false;
            }""")
            if not clicked:
                return None
            await asyncio.sleep(3)
            page_num = await self.get_total_pages(frame)
            if page_num and page_num > 1:
                await self.go_to_last_page(frame)
                return page_num
            return 1
        except Exception as e:
            logger.warning(f"  重新查询ISV失败: {e}")
            return None

    async def delete_log_entry(self, frame, row_key):
        """删除指定 row_key 的铺货日志:勾选行 -> 批量删除日志 -> 确定。"""
        try:
            checked = await frame.evaluate("""
                (key) => {
                    const tr = document.querySelector(`tr.ant-table-row[data-row-key="${key}"]`);
                    if (!tr) return false;
                    const cb = tr.querySelector('input[type="checkbox"]');
                    if (cb && !cb.checked) { cb.click(); }
                    return true;
                }
            """, row_key)
            if not checked:
                logger.warning(f"  删除日志: 未找到 row_key={row_key} 的行(可能已不在当前页)")
                return False
            await asyncio.sleep(1)

            del_btn = frame.locator('button:has-text("批量删除日志")')
            if await del_btn.count() == 0:
                logger.warning("  删除日志: 未找到'批量删除日志'按钮")
                return False
            await del_btn.first.click()
            await asyncio.sleep(2)

            confirmed = await frame.evaluate("""
                () => {
                    const btns = document.querySelectorAll('.ant-modal button');
                    for (const b of btns) {
                        const t = b.textContent.replace(/\\s/g, '');
                        if (t === '确定' || t === '确 定') { b.click(); return true; }
                    }
                    return false;
                }
            """)
            if confirmed:
                logger.info(f"  ✓ 已删除铺货日志 row_key={row_key}")
                await asyncio.sleep(4)
                return True
            else:
                logger.warning("  删除日志: 未找到确认按钮")
                return False
        except Exception as e:
            logger.warning(f"  删除日志异常: {e}")
            return False

    async def run(self):
        """主运行循环"""
        logger.info(f"模式: {'测试' if self.test_mode else '正式批量'}")

        # 测试模式：只处理当前已打开的编辑页面
        if self.test_mode:
            edit_page = await self.find_edit_page()
            if edit_page:
                logger.info(f"找到编辑页面: {edit_page.url[:80]}")
                success = await self.process_edit_page(edit_page)
                if success:
                    logger.info("测试处理成功!")
                else:
                    logger.error("测试处理失败")
            else:
                logger.error("未找到商品编辑页面")
                logger.info("请先在浏览器中打开一个商品编辑页面")
            return

        # 正式模式：批量处理铺货失败商品
        isv_page = await self.find_1688_page()
        if not isv_page:
            logger.error("未找到1688页面")
            return

        frame = await self.get_isv_frame(isv_page)
        if not frame:
            logger.error("未找到ISV内容frame")
            return

        logger.info(f"已连接到1688铺货日志页面")

        # 倒序处理:从最后一页最后一行开始往前
        page_num = await self.get_total_pages(frame)
        if page_num and page_num > 1:
            logger.info(f"倒序处理:跳到最后一页(共 {page_num} 页)")
            await self.go_to_last_page(frame)
        else:
            page_num = 1
        total_attempts = 0
        total_processed_this_session = 0
        resync_count = 0
        last_resync_processed = 0

        while True:
            logger.info(f"\n{'='*60}")
            logger.info(f"第 {page_num} 页")
            logger.info(f"{'='*60}")

            # 获取当前页未处理的商品 (排除本会话已失败的，避免死循环)
            rows = await self.get_product_rows(frame)
            # 0 行可能是翻页没加载出来,重试2次
            if not rows:
                for _ in range(2):
                    await asyncio.sleep(3)
                    rows = await self.get_product_rows(frame)
                    if rows:
                        break
            unprocessed = [r for r in rows if r['row_key'] not in self.processed and r['row_key'] not in self.session_failed]
            logger.info(f"本页共 {len(rows)} 个商品，未处理 {len(unprocessed)} 个")

            if not unprocessed:
                # 分页错位自愈: 当前页读完但实际列表还有条目时,
                # 重读总页数并跳回最后一页继续, 避免误判"已到第一页"提前退出
                actual_total = await self.get_total_pages(frame)
                if actual_total and actual_total > 1:
                    if resync_count == 0 or total_processed_this_session > last_resync_processed:
                        resync_count += 1
                        last_resync_processed = total_processed_this_session
                        if resync_count > 10:
                            logger.error(f"分页重同步超过 10 次仍无法清空, 停止防死循环")
                            break
                        logger.info(f"分页错位(实际 {actual_total} 页), 重新同步到最后页继续...")
                        page_num = actual_total
                        await self.go_to_last_page(frame)
                        continue
                logger.info(f"本页全部处理完成，翻到上一页...")
                if await self.go_to_prev_page(frame):
                    page_num -= 1
                    continue
                # prev 按钮失败,用页码跳转兜底
                if page_num > 1:
                    page_num -= 1
                    try:
                        jumped = await frame.evaluate("""(n)=>{const j=document.querySelector('.ant-pagination-options-quick-jumper input');if(!j)return false;j.focus();j.value=String(n);j.dispatchEvent(new Event('input',{bubbles:true}));j.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',bubbles:true}));return true;}""", page_num)
                        if jumped:
                            await asyncio.sleep(4)
                            continue
                    except:
                        pass
                logger.info("已到第一页,没有更多页面了")
                break

            row = unprocessed[-1]  # 倒序:取最后一个未处理
            row_key = row['row_key']
            product_id = row['product_id']
            title = row['title'][:40]

            # 检查limit (按尝试次数)
            if self.limit > 0 and total_attempts >= self.limit:
                logger.info(f"已达到限制数量 {self.limit}，停止处理")
                return

            total_attempts += 1
            logger.info(f"\n--- 处理商品 [{row_key}]: {title} ---")

            # 情趣内衣/成人类目: 店铺无准入资质, 直接删除铺货日志, 不浪费时间编辑提交
            full_title = row.get('title', '')
            if any(kw in full_title for kw in ADULT_KEYWORDS):
                logger.info(f"  ⚠ 情趣内衣类目(无成人准入资质), 直接删除铺货日志, 跳过编辑")
                await self.delete_log_entry(frame, row_key)
                self.save_progress(row_key, 'processed')
                await asyncio.sleep(1)
                continue

            # 滑块检测
            if await self.detect_slider(isv_page):
                logger.error("检测到滑块验证！暂停所有处理")
                logger.info("请手动解除滑块后重新运行脚本")
                self.save_progress()
                return

            # 点击"编辑店铺草稿" -> "继续上架" (按row_key定位)
            success = await self.click_edit_and_continue(frame, row_key=row_key)
            if not success:
                logger.error(f"  无法打开编辑页面，跳过")
                await self.close_orphan_edit_tabs()
                self.save_progress(row_key, 'failed', '无法打开编辑页面', title=title)
                await asyncio.sleep(2)
                continue

            # 等待编辑页面打开
            edit_page = await self.wait_for_edit_page(timeout=30)
            if not edit_page:
                logger.error(f"  编辑页面未打开，跳过")
                await self.close_orphan_edit_tabs()
                self.save_progress(row_key, 'failed', '编辑页面未打开', title=title)
                continue

            logger.info(f"  编辑页面已打开: {edit_page.url[:60]}")

            # 处理编辑页面
            self.last_error = ""
            try:
                success = await self.process_edit_page(edit_page)
            except Exception as e:
                logger.error(f"  处理异常: {e}")
                success = False
                self.last_error = f"异常: {str(e)[:80]}"

            need_delete_log = False
            if success:
                self.save_progress(row_key, 'processed')
                total_processed_this_session += 1
                logger.info(f"  ✓ 处理成功 (总计: {self.count})")
            else:
                err = self.last_error or '编辑页面处理失败'
                # 滑块触发 -> 跳过当前商品，继续下一个 (滑块已验证通过时不需要整批暂停)
                if '滑块' in err:
                    logger.error(f"  ✗ 遇到滑块验证，跳过该商品继续: {err[:40]}")
                    self.session_failed.add(row_key)
                    self.save_progress(row_key, 'failed', err, title=title)
                # 重复铺货 -> 删除该铺货日志
                elif '重复铺货' in err or '重复发布' in err or '重复商品' in err:
                    logger.error(f"  ✗ 重复铺货，删除该铺货日志: {err[:60]}")
                    need_delete_log = True
                # 成人类目未准入 -> 删除该铺货日志
                elif '成人' in err or '准入' in err or '专营' in err:
                    logger.error(f"  ✗ 成人类目未准入，删除该铺货日志: {err[:60]}")
                    need_delete_log = True
                # 商品已下架/不存在 -> 删除该铺货日志
                elif '已下架' in err or '商品不存在' in err:
                    logger.error(f"  ✗ 商品已下架/不存在，删除该铺货日志: {err[:60]}")
                    need_delete_log = True
                else:
                    logger.error(f"  ✗ 处理失败: {err[:60]}")
                    self.session_failed.add(row_key)
                    self.save_progress(row_key, 'failed', err, title=title)

            # 关闭编辑页面tab
            await self.close_edit_page(edit_page)

            # 删除铺货日志(重复铺货/成人类目未准入)
            if need_delete_log:
                await self.delete_log_entry(frame, row_key)
                self.save_progress(row_key, 'processed')

            # 关闭1688页面可能残留的弹框
            await self.close_any_modal(frame)

            # 批次休息
            await self.batch_break()

            # 随机延迟
            await self.random_delay()

            # 每处理完一个商品(成功/失败)后, 重新查询 ISV 铺货失败列表, 避免分页错位漏采
            new_page = await self.refresh_isv_list(frame)
            if new_page:
                page_num = new_page

        logger.info(f"\n{'='*60}")
        logger.info(f"处理完成！本次处理 {total_processed_this_session} 个商品")
        logger.info(f"总计已处理: {len(self.processed)} 个, 失败: {len(self.failed)} 个")
        logger.info(f"{'='*60}")


if __name__ == "__main__":
    import sys
    test_mode = '--test' in sys.argv
    limit = 0
    if '--limit' in sys.argv:
        idx = sys.argv.index('--limit')
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])
    lister = ProductLister(test_mode=test_mode, limit=limit)
    asyncio.run(lister.connect())
