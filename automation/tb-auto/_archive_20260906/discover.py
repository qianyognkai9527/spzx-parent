"""
DOM探查脚本 - 扫描1688铺货后台商品编辑页面的所有表单字段
使用方法：
1. Chrome已以调试模式运行 (--remote-debugging-port=9222)
2. 在浏览器中导航到商品编辑页面
3. 运行: python discover.py
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright

CDP_URL = "http://127.0.0.1:9222"


async def scan_frame(frame, frame_index):
    """扫描一个frame内的所有表单元素"""
    results = {
        "frame_index": frame_index,
        "url": frame.url,
        "inputs": [],
        "selects": [],
        "textareas": [],
        "buttons": [],
        "radio_groups": {},
        "checkboxes": [],
        "custom_dropdowns": [],
        "labels_text": []
    }

    # 1. 扫描所有 input 元素
    try:
        inputs = await frame.query_selector_all("input")
        for inp in inputs:
            inp_type = await inp.get_attribute("type") or "text"
            inp_id = await inp.get_attribute("id") or ""
            name = await inp.get_attribute("name") or ""
            placeholder = await inp.get_attribute("placeholder") or ""
            value = await inp.get_attribute("value") or ""
            cls = await inp.get_attribute("class") or ""
            disabled = await inp.get_attribute("disabled")
            readonly = await inp.get_attribute("readonly")

            label_text = ""
            if inp_id:
                try:
                    label_el = await frame.query_selector(f"label[for='{inp_id}']")
                    if label_el:
                        label_text = (await label_el.inner_text()).strip()
                except:
                    pass
            if not label_text:
                try:
                    parent = await inp.evaluate(
                        "el => el.closest('label, .form-item, .ant-form-item, .el-form-item, .field-item, dl, .next-form-item')?.innerText || ''")
                    if parent:
                        label_text = parent.strip()[:100]
                except:
                    pass

            if inp_type in ("radio",):
                if name not in results["radio_groups"]:
                    results["radio_groups"][name] = {
                        "name": name,
                        "label": label_text,
                        "options": []
                    }
                checked = await inp.is_checked()
                results["radio_groups"][name]["options"].append({
                    "value": value,
                    "label": label_text,
                    "checked": checked,
                    "id": inp_id
                })
            elif inp_type in ("checkbox",):
                checked = await inp.is_checked()
                results["checkboxes"].append({
                    "id": inp_id,
                    "name": name,
                    "label": label_text,
                    "checked": checked,
                    "value": value
                })
            elif inp_type in ("hidden", "submit", "button", "file", "image"):
                pass
            else:
                results["inputs"].append({
                    "type": inp_type,
                    "id": inp_id,
                    "name": name,
                    "label": label_text,
                    "placeholder": placeholder,
                    "value": value[:50],
                    "class": cls[:80],
                    "disabled": bool(disabled),
                    "readonly": bool(readonly)
                })
    except Exception as e:
        results["_input_error"] = str(e)

    # 2. 扫描所有 select 元素
    try:
        selects = await frame.query_selector_all("select")
        for sel in selects:
            sel_id = await sel.get_attribute("id") or ""
            name = await sel.get_attribute("name") or ""
            cls = await sel.get_attribute("class") or ""

            label_text = ""
            if sel_id:
                try:
                    label_el = await frame.query_selector(f"label[for='{sel_id}']")
                    if label_el:
                        label_text = (await label_el.inner_text()).strip()
                except:
                    pass

            options = []
            option_els = await sel.query_selector_all("option")
            for opt in option_els:
                opt_val = await opt.get_attribute("value") or ""
                opt_text = (await opt.inner_text()).strip()
                selected = await opt.get_attribute("selected")
                options.append({"value": opt_val, "text": opt_text, "selected": bool(selected)})

            results["selects"].append({
                "id": sel_id,
                "name": name,
                "label": label_text,
                "class": cls[:80],
                "options": options
            })
    except Exception as e:
        results["_select_error"] = str(e)

    # 3. 扫描所有 textarea
    try:
        textareas = await frame.query_selector_all("textarea")
        for ta in textareas:
            ta_id = await ta.get_attribute("id") or ""
            name = await ta.get_attribute("name") or ""
            placeholder = await ta.get_attribute("placeholder") or ""
            cls = await ta.get_attribute("class") or ""

            label_text = ""
            if ta_id:
                try:
                    label_el = await frame.query_selector(f"label[for='{ta_id}']")
                    if label_el:
                        label_text = (await label_el.inner_text()).strip()
                except:
                    pass

            results["textareas"].append({
                "id": ta_id,
                "name": name,
                "label": label_text,
                "placeholder": placeholder,
                "class": cls[:80]
            })
    except Exception as e:
        results["_textarea_error"] = str(e)

    # 4. 扫描所有按钮
    try:
        buttons = await frame.query_selector_all("button, [role='button'], .btn, .ant-btn, .el-button, .next-btn")
        for btn in buttons:
            text = (await btn.inner_text()).strip()
            btn_id = await btn.get_attribute("id") or ""
            cls = await btn.get_attribute("class") or ""
            disabled = await btn.get_attribute("disabled")
            if text:
                results["buttons"].append({
                    "text": text[:50],
                    "id": btn_id,
                    "class": cls[:80],
                    "disabled": bool(disabled)
                })
    except Exception as e:
        results["_button_error"] = str(e)

    # 5. 扫描自定义下拉组件
    try:
        custom_selects = await frame.query_selector_all(
            ".ant-select, .el-select, .next-select, [class*='select-wrapper'], "
            "[class*='dropdown-trigger'], [role='combobox'], [class*='select-selector'], "
            ".next-select-wrapper, .ant-select-selector"
        )
        for cs in custom_selects:
            text = (await cs.inner_text()).strip()
            cls = await cs.get_attribute("class") or ""
            cs_id = await cs.get_attribute("id") or ""

            label_text = ""
            try:
                parent_text = await cs.evaluate(
                    "el => el.closest('.ant-form-item, .el-form-item, .form-item, .field-item, dl, .next-form-item, .next-form-row')?.innerText || ''"
                )
                if parent_text:
                    label_text = parent_text.strip()[:100]
            except:
                pass

            results["custom_dropdowns"].append({
                "text": text[:80],
                "id": cs_id,
                "class": cls[:80],
                "label": label_text
            })
    except Exception as e:
        results["_custom_error"] = str(e)

    # 6. 扫描带文字的label/form-item
    try:
        form_items = await frame.query_selector_all(
            ".ant-form-item-label label, .el-form-item__label, .form-item label, "
            ".next-form-item-label, dt, .field-label, [class*='label'], "
            "label, .form-label, .next-form-item label"
        )
        for fi in form_items:
            text = (await fi.inner_text()).strip()
            if text and len(text) < 50:
                results["labels_text"].append(text)
    except:
        pass

    # 转换 radio_groups 为列表
    results["radio_groups"] = list(results["radio_groups"].values())

    return results


async def main():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(CDP_URL)
            print("[OK] 已连接到Chrome (CDP)")
        except Exception as e:
            print(f"[ERROR] 无法连接到Chrome CDP: {e}")
            print("[提示] 请确保Chrome已以 --remote-debugging-port=9222 启动")
            return

        context = browser.contexts[0]

        # 列出所有页面
        print(f"\n[*] 共有 {len(context.pages)} 个标签页:")
        for i, pg in enumerate(context.pages):
            print(f"  Tab {i}: {pg.url[:100]}")

        # 选择第一个页面
        page = context.pages[0] if context.pages else await context.new_page()

        print(f"\n[*] 当前页面URL: {page.url}")
        print(f"[*] 页面标题: {await page.title()}")
        print(f"[*] 页面frames数量: {len(page.frames)}")

        for i, f in enumerate(page.frames):
            print(f"  Frame {i}: url={f.url[:100] if f.url else 'empty'}")

        # 扫描所有 frames
        all_results = []
        for i, frame in enumerate(page.frames):
            if not frame.url or frame.url == "about:blank":
                continue
            print(f"\n[*] 正在扫描 Frame {i}: {frame.url[:100]}...")
            try:
                result = await scan_frame(frame, i)
                all_results.append(result)

                print(f"    inputs: {len(result['inputs'])}")
                print(f"    selects: {len(result['selects'])}")
                print(f"    textareas: {len(result['textareas'])}")
                print(f"    buttons: {len(result['buttons'])}")
                print(f"    radio_groups: {len(result['radio_groups'])}")
                print(f"    checkboxes: {len(result['checkboxes'])}")
                print(f"    custom_dropdowns: {len(result['custom_dropdowns'])}")
                print(f"    labels: {len(result['labels_text'])}")
            except Exception as e:
                print(f"    [ERROR] 扫描失败: {e}")
                all_results.append({"frame_index": i, "url": frame.url, "error": str(e)})

        # 截图
        screenshot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discover_screenshot.png")
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"\n[*] 截图已保存: {screenshot_path}")

        # 保存完整结果
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discover_output.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(f"[*] 完整结果已保存: {output_path}")

        # 打印可读摘要
        print("\n" + "=" * 60)
        print("扫描结果摘要")
        print("=" * 60)
        for r in all_results:
            if "error" in r:
                continue
            print(f"\n--- Frame {r['frame_index']}: {r['url'][:100]} ---")

            if r["inputs"]:
                print(f"\n  [文本输入框] ({len(r['inputs'])}个)")
                for inp in r["inputs"]:
                    label = inp.get("label", "") or inp.get("placeholder", "") or inp.get("name", "")
                    print(f"    - label={label} | type={inp['type']} | id={inp['id']} | value={inp.get('value', '')[:30]}")

            if r["selects"]:
                print(f"\n  [下拉选择] ({len(r['selects'])}个)")
                for sel in r["selects"]:
                    label = sel.get("label", "") or sel.get("name", "")
                    opts = [o["text"] for o in sel["options"][:10]]
                    print(f"    - label={label} | options={opts}")
                    if len(sel["options"]) > 10:
                        print(f"      ... 还有{len(sel['options']) - 10}个选项")

            if r["custom_dropdowns"]:
                print(f"\n  [自定义下拉组件] ({len(r['custom_dropdowns'])}个)")
                for cd in r["custom_dropdowns"]:
                    print(f"    - text={cd['text'][:50]} | label={cd.get('label', '')[:50]} | class={cd['class'][:50]}")

            if r["textareas"]:
                print(f"\n  [文本域] ({len(r['textareas'])}个)")
                for ta in r["textareas"]:
                    label = ta.get("label", "") or ta.get("placeholder", "")
                    print(f"    - label={label} | id={ta['id']}")

            if r["radio_groups"]:
                print(f"\n  [单选组] ({len(r['radio_groups'])}个)")
                for rg in r["radio_groups"]:
                    opts = [f"{o['label']}({o['value']})" for o in rg["options"]]
                    print(f"    - name={rg['name']} | label={rg.get('label', '')} | options={opts}")

            if r["checkboxes"]:
                print(f"\n  [复选框] ({len(r['checkboxes'])}个)")
                for cb in r["checkboxes"]:
                    print(f"    - label={cb['label']} | checked={cb['checked']} | id={cb['id']}")

            if r["buttons"]:
                print(f"\n  [按钮] ({len(r['buttons'])}个)")
                for btn in r["buttons"][:20]:
                    print(f"    - '{btn['text']}' | id={btn['id']} | disabled={btn['disabled']}")
                if len(r["buttons"]) > 20:
                    print(f"    ... 还有{len(r['buttons']) - 20}个按钮")

            if r["labels_text"]:
                unique_labels = list(set(r["labels_text"]))
                print(f"\n  [页面标签文字] ({len(unique_labels)}个)")
                for lbl in unique_labels:
                    print(f"    - {lbl}")

        print("\n" + "=" * 60)
        print("扫描完成！")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
