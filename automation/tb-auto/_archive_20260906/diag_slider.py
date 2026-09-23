"""诊断: 提交后保持tab打开，观察滑块和提交结果"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
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

        # 点击提交 (不做任何其他修改，只测试滑块行为)
        print("点击提交...")
        await edit_page.locator('button', has_text='提交宝贝信息').first.click()

        # 逐秒观察
        for i in range(1, 16):
            await asyncio.sleep(1)
            state = await edit_page.evaluate("""
                () => {
                    const result = {};
                    const slider = document.querySelector('#nc_1_wrapper, #nc_1__scale_text');
                    if (slider) {
                        const rect = slider.getBoundingClientRect();
                        result.slider = {
                            visible: slider.offsetParent !== null,
                            w: Math.round(rect.width),
                            h: Math.round(rect.height),
                            text: slider.textContent.trim().substring(0, 40)
                        };
                    } else {
                        result.slider = null;
                    }
                    // 成功弹窗
                    const dialogs = document.querySelectorAll('.next-dialog, [class*="dialog"], [class*="modal"], [class*="message"]');
                    result.dialogs = [];
                    for (const d of dialogs) {
                        if (d.offsetParent !== null && d.textContent.trim()) {
                            result.dialogs.push(d.textContent.trim().substring(0, 80));
                        }
                    }
                    result.body_has_success = document.body.innerText.includes('成功');
                    result.body_has_slider_text = document.body.innerText.includes('拖动') || document.body.innerText.includes('滑块');
                    result.title = document.title;
                    return result;
                }
            """)
            slider = state.get('slider')
            dialogs = state.get('dialogs', [])
            print(f"[{i}s] slider={json.dumps(slider, ensure_ascii=False) if slider else '无'} | success={state.get('body_has_success')} | dialogs={dialogs[:2]}")

            if state.get('body_has_success'):
                print(">>> 提交成功!")
                break

        # 保存截图并保持tab打开
        await edit_page.screenshot(path='/Users/qyk9527/tb-auto/diag_slider.png', full_page=False)
        print("\n截图已保存，tab保持打开，请查看浏览器")

asyncio.run(main())
