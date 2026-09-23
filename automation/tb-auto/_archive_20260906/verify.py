"""验证页面当前状态 (正确版)"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        for page in browser.contexts[0].pages:
            if 'item.upload.taobao.com' in page.url:
                state = await page.evaluate("""
                    () => {
                        const result = {};

                        // 货号
                        const huohao = document.querySelector('input[itemlabel="货号"]');
                        result['货号'] = huohao ? huohao.value : '未找到';

                        // 一口价
                        const price = document.querySelector('#sell-field-price input');
                        result['一口价'] = price ? price.value : '未找到';

                        // 店铺中分类 - 检查select显示文本
                        const shopcatSelect = document.querySelector('#sell-field-shopcat .next-select');
                        result['店铺中分类_显示'] = shopcatSelect ? shopcatSelect.textContent.trim().substring(0, 30) : '未找到';
                        // 也检查是否有已选中的tag
                        const shopcatTags = document.querySelectorAll('#sell-field-shopcat .next-tag, #sell-field-shopcat .next-select-tag-content');
                        result['店铺中分类_tags'] = Array.from(shopcatTags).map(t => t.textContent.trim()).join(', ');

                        // 上架时间 - 用aria-checked正确检测
                        const startTime = document.querySelector('#sell-field-startTime');
                        const wrappers = startTime ? startTime.querySelectorAll('.next-radio-wrapper') : [];
                        let selectedTime = '未选中';
                        for (const w of wrappers) {
                            if (w.getAttribute('aria-checked') === 'true' || w.classList.contains('checked')) {
                                const radioItem = w.closest('.radio-item');
                                selectedTime = radioItem ? radioItem.textContent.trim().substring(0, 20) : w.textContent.trim().substring(0, 20);
                                break;
                            }
                        }
                        result['上架时间'] = selectedTime;

                        // 商品预检
                        const precheck = document.querySelector('#sell-field-ysbCheckTask .next-checkbox-wrapper');
                        result['商品预检_checked'] = precheck ? (precheck.classList.contains('checked') || precheck.getAttribute('aria-checked') === 'true') : false;
                        result['商品预检_disabled'] = precheck ? precheck.classList.contains('disabled') : false;

                        return result;
                    }
                """)
                import json
                print(json.dumps(state, ensure_ascii=False, indent=2))
                break

asyncio.run(main())
