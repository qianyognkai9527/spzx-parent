"""诊断: 点击提交后页面的完整变化"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')

        # 打开一个编辑页面
        isv_page = None
        for page in browser.contexts[0].pages:
            if 'ufuwu.1688.com' in page.url:
                isv_page = page
                break
        frame = isv_page.frames[2]

        # 找第一个未处理商品
        rows = await frame.evaluate("""
            () => {
                const tbody = document.querySelector('.ant-table-tbody');
                const trs = tbody.querySelectorAll('tr.ant-table-row');
                return Array.from(trs).map(tr => ({
                    key: tr.getAttribute('data-row-key'),
                    has_edit: !!Array.from(tr.querySelectorAll('button')).find(b => b.textContent.includes('编辑店铺草稿'))
                })).filter(r => r.has_edit);
            }
        """)
        row_key = rows[0]['key']
        print(f"商品: {row_key}")

        await frame.evaluate("""
            (key) => {
                const row = document.querySelector(`tr[data-row-key="${key}"]`);
                const btn = Array.from(row.querySelectorAll('button')).find(b => b.textContent.includes('编辑店铺草稿'));
                btn.click();
            }
        """, row_key)
        await asyncio.sleep(2)
        await frame.locator('.ant-modal button:has-text("继续上架")').first.click()
        await asyncio.sleep(4)

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

        print(f"标题: {await edit_page.title()}")

        # 检查提交按钮状态
        btn_state = await edit_page.evaluate("""
            () => {
                const btns = Array.from(document.querySelectorAll('button'));
                const submit = btns.find(b => b.textContent.includes('提交宝贝信息'));
                if (!submit) return {found: false};
                return {
                    found: true,
                    disabled: submit.disabled,
                    class: submit.className.substring(0, 80),
                    rect: submit.getBoundingClientRect().toJSON(),
                    visible: submit.offsetParent !== null,
                    tabindex: submit.tabIndex
                };
            }
        """)
        print(f"\n提交按钮状态: {json.dumps(btn_state, ensure_ascii=False)}")

        # 点击提交
        print("\n点击提交...")
        await edit_page.evaluate("""
            () => {
                const btns = Array.from(document.querySelectorAll('button'));
                const submit = btns.find(b => b.textContent.includes('提交宝贝信息'));
                if (submit) submit.click();
            }
        """)

        # 逐秒抓取状态
        for i in range(1, 8):
            await asyncio.sleep(1)
            state = await edit_page.evaluate("""
                () => {
                    const result = {};
                    // 1. 页面标题
                    result.title = document.title;
                    
                    // 2. 提交按钮是否disabled
                    const submit = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('提交宝贝信息'));
                    result.submit_disabled = submit ? submit.disabled : null;
                    
                    // 3. 可见弹窗/overlay
                    const dialogs = document.querySelectorAll('.next-dialog, .next-overlay-inner, [class*="dialog"], [class*="modal"], [class*="toast"], [class*="message"]');
                    result.dialogs = [];
                    for (const d of dialogs) {
                        if (d.offsetParent !== null && d.textContent.trim()) {
                            result.dialogs.push(d.className.substring(0, 40) + ': ' + d.textContent.trim().substring(0, 120));
                        }
                    }
                    
                    // 4. 可见错误元素
                    const errs = document.querySelectorAll('[class*="error"], [class*="Error"], [class*="warn"], .next-input-error, .has-error, [class*="invalid"], [class*="red"]');
                    result.errors = [];
                    for (const e of errs) {
                        if (e.offsetParent !== null && e.textContent.trim()) {
                            result.errors.push(e.className.substring(0, 40) + ': ' + e.textContent.trim().substring(0, 60));
                        }
                    }
                    
                    // 5. 页面底部是否有新内容
                    const body = document.body.innerText;
                    result.body_has_loading = body.includes('提交中') || body.includes('发布中') || body.includes('保存中');
                    result.body_has_success = body.includes('成功') || body.includes('已发布');
                    result.body_has_fail = body.includes('失败') || body.includes('请填写') || body.includes('请选择');
                    
                    return result;
                }
            """)
            print(f"\n[{i}s] title={state['title'][:30]} | submit_disabled={state['submit_disabled']}")
            if state['dialogs']:
                print(f"  弹窗: {state['dialogs'][:3]}")
            if state['errors']:
                print(f"  错误: {state['errors'][:5]}")
            if state['body_has_loading']:
                print(f"  页面状态: 提交中...")
            if state['body_has_success']:
                print(f"  页面状态: 成功!")
            if state['body_has_fail']:
                print(f"  页面状态: 有失败提示")

        # 保存截图
        await edit_page.screenshot(path='/Users/qyk9527/tb-auto/diagnose_submit.png', full_page=False)
        print("\n截图已保存")

asyncio.run(main())
