"""测试最小操作方案: 不做属性填充，只做必要修改后提交"""
import asyncio
import json
import random
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')

        # 关闭所有编辑/成功页
        for page in list(browser.contexts[0].pages):
            if 'item.upload.taobao.com' in page.url:
                await page.close()

        isv_page = None
        for page in browser.contexts[0].pages:
            if 'ufuwu.1688.com' in page.url:
                isv_page = page
                break
        frame = isv_page.frames[2]

        # 打开945571190编辑页
        await frame.evaluate("""
            (key) => {
                const row = document.querySelector(`tr[data-row-key="${key}"]`);
                const btn = Array.from(row.querySelectorAll('button')).find(b => b.textContent.includes('编辑店铺草稿'));
                btn.click();
            }
        """, "945571190")
        await asyncio.sleep(2)
        await frame.locator('.ant-modal button:has-text("继续上架")').first.click()
        await asyncio.sleep(6)

        edit_page = None
        for page in browser.contexts[0].pages:
            if 'item.upload.taobao.com' in page.url:
                edit_page = page
                break
        if not edit_page:
            print("未找到编辑页面")
            return
        await edit_page.wait_for_load_state('networkidle', timeout=30000)
        await asyncio.sleep(2)

        print("=== 执行最小操作 ===")

        # 1. 款号
        style_num = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=2))
        while True:
            d1 = random.randint(0,9)
            if d1 != 4:
                d2 = random.randint(0,9); d3 = random.randint(0,9)
                digits = f"{d1}{d2}{d3}"
                if '38' not in digits:
                    style_num = style_num + digits
                    break
        huohao = edit_page.locator('input[itemlabel="货号"], input[itemlabel="款号"]')
        if await huohao.count() > 0:
            await huohao.first.click()
            await asyncio.sleep(0.5)
            await huohao.first.fill(style_num)
            print(f"  款号: {style_num}")
        else:
            print("  未找到款号输入框(可能不需要)")
        await asyncio.sleep(1)

        # 2. 价格×3
        price_loc = edit_page.locator('#sell-field-price input')
        if await price_loc.count() > 0:
            old = float(await price_loc.first.input_value())
            new = round(old * 3, 2)
            await price_loc.first.click()
            await asyncio.sleep(0.3)
            await price_loc.first.fill(str(new))
            print(f"  一口价: {old} -> {new}")
        await asyncio.sleep(1)

        # 3. 店铺中分类 → 家居服/睡衣
        await edit_page.locator('#sell-field-shopcat .next-select-trigger').click()
        await asyncio.sleep(2)
        await edit_page.wait_for_selector('.next-overlay-inner .next-tree-node', timeout=5000)
        await edit_page.locator('.next-overlay-inner .next-tree-node .next-checkbox-wrapper').first.click()
        await asyncio.sleep(1)
        await edit_page.mouse.click(10, 10)
        await asyncio.sleep(1)
        print("  店铺中分类: 家居服/睡衣")

        # 4. 上架时间 → 放入仓库
        await edit_page.locator('#sell-field-startTime .radio-item:has-text("放入仓库")').first.click()
        await asyncio.sleep(2)
        print("  上架时间: 放入仓库")

        # 5. 商品预检 → 启用
        await asyncio.sleep(1)
        precheck = edit_page.locator('#sell-field-ysbCheckTask .next-checkbox-wrapper')
        if await precheck.count() > 0:
            is_checked = await precheck.first.evaluate("el => el.classList.contains('checked')")
            if not is_checked:
                await precheck.first.click()
                await asyncio.sleep(1)
            print("  商品预检: 已启用")

        # 提交
        print("\n=== 提交 ===")
        await edit_page.locator('button', has_text='提交宝贝信息').first.click()

        # 等待并检测成功
        for i in range(1, 20):
            await asyncio.sleep(1)
            url = edit_page.url
            if 'success.htm' in url:
                print(f"[{i}s] 提交成功! URL: {url[:60]}")
                break
            # 检查滑块
            slider = await edit_page.query_selector('#nc_1_wrapper')
            if slider:
                vis = await slider.is_visible()
                if vis:
                    print(f"[{i}s] 检测到滑块!")
                    break
            if i == 19:
                print(f"[{i}s] 超时，当前URL: {url[:60]}")

        # 保持tab打开
        await edit_page.screenshot(path='/Users/qyk9527/tb-auto/minimal_test.png', full_page=False)
        print("截图已保存，tab保持打开")

asyncio.run(main())
