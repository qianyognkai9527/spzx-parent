# 淘宝31个错类目商品修复 — 已验证技术点 (2026-08-14 00:45)

## 现状
- 31个商品带"认证卖点"标记 = 错放类目 (清单: /tmp/rz_list.json, /tmp/rz_itemids.json)
- 常见错误类目: 运动内衣套装 / 睡衣/家居服套装 / 睡衣上装
- 目标类目: 女士内衣/男士内衣/家居服 >> 睡袍/浴袍
- 已验证流程脚本: /tmp/fix_cat_v3.py (切换+4下拉+填区间, 但保存被尺码信息卡住)

## 已验证可用的操作 (全部用 dispatchEvent MouseEvent click, 不是 .click())
1. **切换类目**: 点"切换类目" -> dispatchEvent 一级"女士内衣/男士内衣/家居服" -> 二级"睡袍/浴袍" -> "确定" -> 二次弹窗"是否切换类目...丢失?" 再"确定"
   - 关键: 级联用 `dispatchEvent(new MouseEvent('click',{bubbles:true}))` 才有效, evaluate .click() / Playwright locator.click() 都无效
2. **4个必填下拉** (填后验证: 读字段显示文本, 不是 input.value):
   - 品牌 -> "瑰若" (默认是"无品牌/无注册商标"也有效)
   - 上市年份季节 -> "2025年冬季"
   - 适用季节 -> "四季通用"
   - 适用性别 -> "女"
   - 选法: 打开下拉(input mousedown+mouseup+click) -> 点 `div.options-item` (dispatchEvent mousedown+mouseup+click)
   - 验证: 容器 innerText 会显示选中值 (e.g. "适用季节\n四季通用")

## 卡住的: 尺码信息 (商品尺寸表)
- 表格: 尺寸(M/L/XL/均码) x 身高(cm)区间值 x 体重(kg)区间值
- **用户提示: 点"区间值"开关(span.next-btn-helper, 每列一个) 变成 最小值/最大值 双输入框**
- 区间输入框是 `<input>` (无type属性, JS .type==='text'), 选择器要用 `input` 不是 `input[type=text]`
- ⚠️ **填值必须用 Playwright fill() (触发React onChange); 原生setter只改DOM value, React状态没变, 保存仍报空!**
- 还需要填: **卖点** ("请选择卖点" input, 选项未dump出来)

## 待办
- [ ] 填min/max改用Playwright fill()
- [ ] 卖点选项dump+填
- [ ] 保存后可能还有更多必填项 (每保存一次冒一个新必填)
- [ ] 验证1个完整保存"商品提交成功"后, 批量跑31个
