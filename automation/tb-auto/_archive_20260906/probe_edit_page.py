"""探针: 从 1688 铺货失败列表点开一个编辑页,dump sell-field 字段 + SKU 滚动结构 + 标题/导购标题。"""
import asyncio
from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9222"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        isv_page = None
        for pg in ctx.pages:
            if 'ufuwu.1688.com' in pg.url:
                isv_page = pg; break
        if not isv_page:
            print("没找到 1688 ISV 页"); await b.close(); return
        frame = None
        for f in isv_page.frames:
            if 'isv-container' in (f.url or ''):
                frame = f; break
        if not frame:
            print("没找到 ISV frame"); await b.close(); return

        # 点第一个"编辑店铺草稿"
        await frame.locator('button:has-text("编辑店铺草稿")').first.click()
        print("已点 编辑店铺草稿")
        await asyncio.sleep(2)
        try:
            await frame.wait_for_selector('.ant-modal button:has-text("继续上架")', timeout=10000)
            await frame.locator('.ant-modal button:has-text("继续上架")').first.click()
            print("已点 继续上架")
        except Exception as e:
            print("继续上架 弹框未出现:", e)

        # 等编辑页打开
        edit_page = None
        for _ in range(30):
            await asyncio.sleep(1)
            for pg in ctx.pages:
                if 'item.upload.taobao.com' in pg.url:
                    edit_page = pg; break
            if edit_page:
                break
        if not edit_page:
            print("编辑页没打开"); await b.close(); return
        print("编辑页:", edit_page.url[:80])
        try:
            await edit_page.wait_for_load_state('networkidle', timeout=30000)
        except Exception:
            pass
        try:
            await edit_page.locator('#sell-field-title input').wait_for(state='visible', timeout=15000)
        except Exception:
            print("标题字段未出现,可能进了 category.htm")
        await asyncio.sleep(2)

        # 1) sell-field-* 字段
        fields = await edit_page.evaluate("""()=>{
            const out=[];
            document.querySelectorAll('[id^="sell-field-"]').forEach(el=>{
                const lbl = el.querySelector('label,.label,[class*="label"]')?.textContent?.trim()?.substring(0,30)||'';
                const inp = el.querySelector('input,textarea');
                out.push({id:el.id, label:lbl, hasInput:!!inp, val: inp?(inp.value||'').substring(0,40):''});
            });
            return out;
        }""")
        print(f"\n=== sell-field-* 字段({len(fields)}) ===")
        for f in fields:
            mark = '⭐' if ('导购' in f['label'] or 'guide' in f['id'].lower() or 'title' in f['id'].lower() or '标题' in f['label']) else '  '
            print(f"{mark} {f['id']} | '{f['label']}' | val='{f['val']}'")

        # 2) 标题
        title_val = await edit_page.evaluate("""()=>{const i=document.querySelector('#sell-field-title input');return i?i.value:'';}""")
        print(f"\n=== 标题 ===\n{title_val}")

        # 3) SKU 滚动
        sku = await edit_page.evaluate("""()=>{
            const sku=document.querySelector('#sell-field-sku'); if(!sku) return {found:false};
            const inputs=sku.querySelectorAll('input');
            let sc=sku,d=0;
            while(sc&&d<8){const st=getComputedStyle(sc); if(/(auto|scroll)/.test(st.overflowY)&&sc.scrollHeight>sc.clientHeight+10) break; sc=sc.parentElement; d++;}
            return {found:true, inputCount:inputs.length, skuSH:sku.scrollHeight, skuCH:sku.clientHeight,
                    scroller: sc?(sc.tagName+'.'+(sc.className||'').substring(0,60)):null,
                    scSH: sc?sc.scrollHeight:0, scCH: sc?sc.clientHeight:0, scId: sc?(sc.id||''):'', scDepth:d};
        }""")
        print(f"\n=== SKU ===")
        for k,v in sku.items(): print(f"  {k}: {v}")

        # 4) 滚动到底再数
        if sku.get('scroller'):
            await edit_page.evaluate("""()=>{
                const sku=document.querySelector('#sell-field-sku'); let sc=sku,d=0;
                while(sc&&d<8){const st=getComputedStyle(sc); if(/(auto|scroll)/.test(st.overflowY)&&sc.scrollHeight>sc.clientHeight+10) break; sc=sc.parentElement; d++;}
                if(sc) sc.scrollTop=sc.scrollHeight;
            }""")
            await asyncio.sleep(1.5)
            n2 = await edit_page.evaluate("""()=>document.querySelector('#sell-field-sku').querySelectorAll('input').length""")
            print(f"  滚动到底后 input 数: {n2} (之前 {sku['inputCount']})")

        await b.close()

asyncio.run(main())
