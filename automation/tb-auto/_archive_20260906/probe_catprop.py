"""探针: 打开一个编辑页,dump 类目属性(catProp)每个属性的:名称/是否必填/当前值。找未填的必填项。"""
import asyncio
from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9222"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        # 先关残留编辑页
        for pg in list(ctx.pages):
            if 'item.upload.taobao.com' in pg.url:
                try: await pg.close()
                except: pass
        isv_page = None
        for pg in ctx.pages:
            if 'ufuwu.1688.com' in pg.url:
                isv_page = pg; break
        frame = None
        for f in isv_page.frames:
            if 'isv-container' in (f.url or ''):
                frame = f; break

        await frame.locator('button:has-text("编辑店铺草稿")').first.click()
        await asyncio.sleep(2)
        try:
            await frame.wait_for_selector('.ant-modal button:has-text("继续上架")', timeout=10000)
            await frame.locator('.ant-modal button:has-text("继续上架")').first.click()
        except: pass

        edit_page = None
        for _ in range(30):
            await asyncio.sleep(1)
            for pg in ctx.pages:
                if 'item.upload.taobao.com' in pg.url:
                    edit_page = pg; break
            if edit_page: break
        if not edit_page:
            print("编辑页没开"); await b.close(); return
        try:
            await edit_page.wait_for_load_state('networkidle', timeout=30000)
        except: pass
        try:
            await edit_page.locator('#sell-field-title input').wait_for(state='visible', timeout=15000)
        except: pass
        await asyncio.sleep(2)

        # dump catProp 属性
        attrs = await edit_page.evaluate("""()=>{
            const out = [];
            // 类目属性可能在 #sell-field-catProp 或 [id*="catProp"]
            const root = document.querySelector('#sell-field-catProp') || document.querySelector('[id*="catProp"]');
            if(!root) return {err:'no catProp'};
            // 每个属性项通常是带 label 的行;找所有 input/select + 其 label
            const items = root.querySelectorAll('.sell-catProp-item, .catProp-item, [class*="catProp-item"], .next-form-item, li');
            const seen = new Set();
            const rows = [];
            // 也直接扫所有 input/select
            root.querySelectorAll('input, select, textarea').forEach(el=>{
                // 找最近的 label
                let label='';
                let p = el;
                for(let i=0;i<6 && p;i++){ p=p.parentElement; if(!p) break;
                    const lbl = p.querySelector('label, .label, [class*="label"], .sell-catProp-item-label');
                    if(lbl){ label = lbl.textContent.trim().substring(0,30); break; }
                }
                const val = el.value || (el.tagName==='SELECT'? (el.options[el.selectedIndex]?.text||'') : '');
                const required = label.includes('*') || (p && p.textContent.includes('*'));
                const key = label+'|'+val;
                if(!seen.has(key)){
                    seen.add(key);
                    rows.push({label: label.replace(/\\s+/g,' ').trim(), val: val.substring(0,20), required, tag: el.tagName, type: el.type||''});
                }
            });
            return {count: rows.length, rows};
        }""")
        print(f"catProp 属性数: {attrs.get('count', 0)}")
        if attrs.get('err'):
            print("err:", attrs['err'])
        for r in attrs.get('rows', []):
            mark = '⭐未填必填' if (r['required'] and not r['val']) else ('  ' )
            print(f"{mark} [{r['label']}] val='{r['val']}' req={r['required']} <{r['tag']}/{r['type']}>")

        # 额外: 全 catProp 区文本里搜"产品名称"
        has_pname = await edit_page.evaluate("""()=>{const t=document.querySelector('#sell-field-catProp')?.innerText||''; return {has: t.includes('产品名称'), snippet: t.substring(0,400)}""")
        print(f"\n含'产品名称': {has_pname['has']}")
        print(f"catProp 文本前400: {has_pname['snippet']}")

        await b.close()

asyncio.run(main())
