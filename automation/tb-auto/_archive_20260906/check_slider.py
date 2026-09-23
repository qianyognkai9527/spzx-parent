"""检查编辑页面的滑块元素 - 只加载不操作，避免触发"""
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

        print("=== 编辑页面滑块检测 (无操作加载) ===")
        for selector in ["#nc_1_wrapper", ".nc_iconfont", "#nc_1_n1z", "#aliyunCaptcha", ".baxia-dialog", "#baxia-dialog", ".nc-container", "#smcaptcha", ".J_MIDDLEWARE_FRAME_WIDGET"]:
            info = await edit_page.evaluate("""
                (sel) => {
                    const el = document.querySelector(sel);
                    if (!el) return {found: false};
                    const rect = el.getBoundingClientRect();
                    return {
                        found: true,
                        visible: el.offsetParent !== null,
                        display: getComputedStyle(el).display,
                        w: Math.round(rect.width),
                        h: Math.round(rect.height),
                        tag: el.tagName,
                        cls: el.className.substring(0, 60)
                    };
                }
            """, selector)
            if info.get('found'):
                print(f"  {selector}: {json.dumps(info, ensure_ascii=False)}")

        # 也检查iframe
        print("\n=== iframe中的滑块检查 ===")
        for i, f in enumerate(edit_page.frames):
            for selector in [".nc_iconfont", "#nc_1_wrapper", ".J_MIDDLEWARE_FRAME_WIDGET"]:
                try:
                    info = await f.evaluate("""
                        (sel) => {
                            const el = document.querySelector(sel);
                            if (!el) return {found: false};
                            return {found: true, visible: el.offsetParent !== null, w: Math.round(el.getBoundingClientRect().width), h: Math.round(el.getBoundingClientRect().height), tag: el.tagName};
                        }
                    """, selector)
                    if info.get('found'):
                        print(f"  Frame {i} {selector}: {json.dumps(info, ensure_ascii=False)}")
                except:
                    pass

        await edit_page.screenshot(path='/Users/qyk9527/tb-auto/check_slider.png', full_page=False)
        print("\n截图已保存")

asyncio.run(main())
