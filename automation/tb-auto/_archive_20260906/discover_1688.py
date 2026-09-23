"""探查1688铺货日志页面结构"""
import asyncio
import json
from playwright.async_api import async_playwright

CDP_URL = "http://127.0.0.1:9222"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0]

        # 找到1688页面
        isv_page = None
        for page in context.pages:
            if 'ufuwu.1688.com' in page.url or 'fuwu_work_isv' in page.url:
                isv_page = page
                break

        if not isv_page:
            print("未找到1688页面")
            return

        print(f"页面URL: {isv_page.url}")
        print(f"页面标题: {await isv_page.title()}")
        print(f"Frames数量: {len(isv_page.frames)}")

        for i, f in enumerate(isv_page.frames):
            print(f"  Frame {i}: url={f.url[:100] if f.url else 'empty'}")

        # 扫描所有frame，找到有内容的
        for i, frame in enumerate(isv_page.frames):
            if not frame.url or frame.url == 'about:blank':
                continue

            print(f"\n{'='*60}")
            print(f"扫描 Frame {i}: {frame.url[:100]}")
            print(f"{'='*60}")

            # 获取所有文本内容（前2000字符）
            try:
                text = await frame.evaluate("document.body?.innerText?.substring(0, 2000) || ''")
                if text and len(text) > 50:
                    print(f"\n--- 页面文本 (前500字) ---")
                    print(text[:500])
            except:
                pass

            # 找按钮
            try:
                buttons = await frame.evaluate("""
                    () => {
                        const btns = document.querySelectorAll('button, [role="button"], .btn, .next-btn, a[class*="btn"], [class*="button"]');
                        return Array.from(btns).map(b => ({
                            text: b.textContent.trim().substring(0, 30),
                            tag: b.tagName,
                            class: b.className?.toString()?.substring(0, 50) || '',
                            href: b.href || ''
                        })).filter(b => b.text.length > 0).slice(0, 30);
                    }
                """)
                if buttons:
                    print(f"\n--- 按钮 ({len(buttons)}个) ---")
                    for b in buttons:
                        print(f"  '{b['text']}' | tag={b['tag']} | class={b['class'][:40]}")
            except:
                pass

            # 找链接
            try:
                links = await frame.evaluate("""
                    () => {
                        const as = document.querySelectorAll('a');
                        return Array.from(as).map(a => ({
                            text: a.textContent.trim().substring(0, 30),
                            href: a.href?.substring(0, 80) || ''
                        })).filter(a => a.text.length > 0).slice(0, 20);
                    }
                """)
                if links:
                    print(f"\n--- 链接 ({len(links)}个) ---")
                    for l in links:
                        print(f"  '{l['text']}' -> {l['href'][:60]}")
            except:
                pass

            # 找表格
            try:
                tables = await frame.evaluate("""
                    () => {
                        const tables = document.querySelectorAll('table, [class*="table"], [class*="grid"], [class*="list"]');
                        return Array.from(tables).map(t => ({
                            tag: t.tagName,
                            class: t.className?.toString()?.substring(0, 50) || '',
                            rows: t.querySelectorAll('tr, [class*="row"]').length,
                            text: t.textContent.trim().substring(0, 100)
                        })).slice(0, 10);
                    }
                """)
                if tables:
                    print(f"\n--- 表格 ({len(tables)}个) ---")
                    for t in tables:
                        print(f"  tag={t['tag']} rows={t['rows']} class={t['class'][:40]} text={t['text'][:50]}")
            except:
                pass

            # 找包含"编辑"或"草稿"或"铺货"的元素
            try:
                edit_elements = await frame.evaluate("""
                    () => {
                        const all = document.querySelectorAll('*');
                        const results = [];
                        for (const el of all) {
                            if (el.children.length === 0) {
                                const text = el.textContent.trim();
                                if (text.includes('编辑') || text.includes('草稿') || text.includes('铺货') || text.includes('继续上架') || text.includes('操作')) {
                                    results.push({
                                        tag: el.tagName,
                                        text: text.substring(0, 30),
                                        class: el.className?.toString()?.substring(0, 50) || '',
                                        parent_class: el.parentElement?.className?.toString()?.substring(0, 50) || ''
                                    });
                                }
                            }
                        }
                        return results.slice(0, 30);
                    }
                """)
                if edit_elements:
                    print(f"\n--- 包含编辑/草稿/铺货/操作的元素 ({len(edit_elements)}个) ---")
                    for e in edit_elements:
                        print(f"  '{e['text']}' | tag={e['tag']} | class={e['class'][:30]} | parent={e['parent_class'][:30]}")
            except:
                pass

            # 找下拉/筛选
            try:
                filters = await frame.evaluate("""
                    () => {
                        const sels = document.querySelectorAll('select, .next-select, [class*="filter"], [class*="search"], input[type="date"], [class*="dropdown"]');
                        return Array.from(sels).map(s => ({
                            tag: s.tagName,
                            class: s.className?.toString()?.substring(0, 50) || '',
                            text: s.textContent.trim().substring(0, 50)
                        })).slice(0, 15);
                    }
                """)
                if filters:
                    print(f"\n--- 筛选/下拉 ({len(filters)}个) ---")
                    for f in filters:
                        print(f"  tag={f['tag']} class={f['class'][:40]} text={f['text'][:40]}")
            except:
                pass

asyncio.run(main())
