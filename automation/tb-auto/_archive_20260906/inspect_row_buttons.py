"""只读检查:打印铺货失败列表每行的所有按钮文本 + 当前残留 modal,不点击不提交"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        ctx = browser.contexts[0]
        isv_page = None
        for page in ctx.pages:
            if 'ufuwu.1688.com' in page.url or 'fuwu_work_isv' in page.url:
                isv_page = page
                break
        if not isv_page:
            print("未找到1688页")
            return
        frame = None
        for f in isv_page.frames:
            if 'isv-container' in (f.url or ''):
                frame = f
                break
        if not frame:
            print("未找到 ISV frame")
            return

        rows = await frame.evaluate("""
            () => {
                const tbody = document.querySelector('.ant-table-tbody');
                if (!tbody) return [];
                const trs = tbody.querySelectorAll('tr.ant-table-row');
                return Array.from(trs).slice(0, 6).map(tr => {
                    const btns = Array.from(tr.querySelectorAll('button')).map(b => ({
                        text: b.textContent.trim(),
                        cls: b.className
                    }));
                    const rowKey = tr.getAttribute('data-row-key') || '';
                    const txt = tr.textContent.replace(/\\s+/g, ' ').trim().substring(0, 70);
                    return {rowKey, txt, btns};
                });
            }
        """)
        print(f"共读到 {len(rows)} 行(前6行):\n")
        for r in rows:
            print(f"行 {r['rowKey']}: {r['txt']}")
            for b in r['btns']:
                print(f"    按钮: [{b['text']}]  cls={b['cls'][:60]}")
            print()

        modal = await frame.evaluate("""
            () => {
                const m = document.querySelector('.ant-modal:not([style*=\"display: none\"])');
                if (!m) return null;
                return {
                    title: m.querySelector('.ant-modal-title, .ant-modal-header')?.textContent?.trim() || '(无标题)',
                    body: m.querySelector('.ant-modal-body')?.textContent?.replace(/\\s+/g,' ')?.trim()?.substring(0, 300) || '',
                    buttons: Array.from(m.querySelectorAll('button')).map(b => b.textContent.trim())
                };
            }
        """)
        if modal:
            print("=== 当前残留 modal ===")
            print(f"标题: {modal['title']}")
            print(f"正文: {modal['body']}")
            print(f"按钮: {modal['buttons']}")
        else:
            print("(当前无残留 modal)")
        browser.close()

asyncio.run(main())
