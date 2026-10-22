# AI Brain 调参试打台 SPA 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `spzx-ai-brain` 后端补上 spec §6.5 的「调参试打台」前端——一个内嵌静态 SPA（Vue 3 + Vite + Element Plus），单人试打、实时调参、看完整推理诊断、存/提升预设。

**Architecture:** 独立 Vite 工程 `spzx-ai-brain/console-ui`，构建产物打进后端 `src/main/resources/static/`，由 Spring Boot 同源伺服；开发期用 Vite dev server 代理 `/console` 到 8600。前端只调已落地的 `/console/*` REST API（带 `X-Console-Token` 头）。纯逻辑抽成 `src/lib/*.js`，用 Node 内置 `node:test` 无依赖测试；Vue 组件以 `npm run build` 编译通过 + 运行时手动冒烟为验证。

**Tech Stack:** Node 20 / npm 10（registry `https://registry.npmmirror.com`）、Vue 3.5、Vite 5、Element Plus 2.9、axios 1.7、sass（版本对齐 `webstormProject/spzx-admin`）。

## Global Constraints

- **不执行任何 git 提交**（用户明确）。所有改动只写盘。
- 前端工程目录：`/Users/qyk9527/ideaProject/spzx-ai-brain/console-ui`；构建输出目录：`/Users/qyk9527/ideaProject/spzx-ai-brain/src/main/resources/static`。
- 依赖版本对齐 `webstormProject/spzx-admin/package.json`（Vue `^3.5.13`、Vite `^5.4.11`、`@vitejs/plugin-vue ^5.2.1`、`element-plus ^2.9.4`、`@element-plus/icons-vue ^2.3.1`、`axios ^1.7.7`、`sass ^1.83.0`）。
- 纯逻辑测试用 **Node 内置 `node:test` + `node:assert`**，**不引入 vitest/jest**（约定见根 `AGENTS.md`：测试不引入重框架）。组件不写 DOM 测试，以 `npm run build` + 冒烟为准。
- 后端 API 契约（已实现，前端不得改）见文末「后端契约」；鉴权头 `X-Console-Token` 存 `localStorage`（键 `aibrain_token`），不硬编码默认 token。
- 后端端口 8600；dev server 5175；preview 4175。
- 生成物 `console-ui/node_modules`、`src/main/resources/static` 不入库（`.gitignore`）。
- 绝对不在仓库/日志/文档里出现真实 apiKey 或控制台 token 值。

## File Structure

```
spzx-ai-brain/console-ui/
├── package.json
├── vite.config.js
├── index.html
├── .gitignore
├── src/
│   ├── main.js                 # 挂载 Vue + Element Plus
│   ├── App.vue                 # 布局 + 顶栏（租户/token/provider/model/连接状态）
│   ├── lib/
│   │   ├── payload.js          # 纯函数：buildOverrides/buildPreviewPayload/format*
│   │   ├── payload.test.js     # node:test
│   │   ├── api.js              # axios 实例 + token + 各端点封装
│   │   └── store.js            # 全局 reactive 状态
│   └── components/
│       ├── ParamsPanel.vue     # 6 组参数（生成/provider/prompt/RAG/模拟上下文）
│       ├── PresetPanel.vue     # 预设列表 + 保存 + 一键提升
│       ├── ChatPanel.vue       # 多轮试打
│       └── DiagnosticsPanel.vue# reply/intent/confidence/sources/toolTrace/决策/耗时/token/prompt
```

后续计划：工具接真实 spzx Connector + pgvector RAG、canonical 中台 + Chatwoot Adapter、Channel Sidecar。

---

### Task 1: Vite 工程脚手架 + 内嵌静态资源伺服验证

**Files:**
- Create: `console-ui/package.json`
- Create: `console-ui/vite.config.js`
- Create: `console-ui/index.html`
- Create: `console-ui/.gitignore`
- Create: `console-ui/src/main.js`
- Create: `console-ui/src/App.vue`

**Interfaces:**
- Produces: 可 `npm install && npm run build` 的工程；构建产物落到后端 `static/`；Vite dev/preview 代理 `/console → 8600`。

- [ ] **Step 1: 写 `package.json`**

```json
{
  "name": "spzx-ai-brain-console",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "node --test src/lib"
  },
  "dependencies": {
    "axios": "^1.7.7",
    "vue": "^3.5.13"
  },
  "devDependencies": {
    "@element-plus/icons-vue": "^2.3.1",
    "@vitejs/plugin-vue": "^5.2.1",
    "element-plus": "^2.9.4",
    "sass": "^1.83.0",
    "vite": "^5.4.11"
  }
}
```

- [ ] **Step 2: 写 `vite.config.js`**

```js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const proxy = {
  '/console': { target: 'http://localhost:8600', changeOrigin: true }
}

export default defineConfig({
  plugins: [vue()],
  base: './',
  build: {
    outDir: '../src/main/resources/static',
    emptyOutDir: true
  },
  server: { port: 5175, proxy },
  preview: { port: 4175, proxy }
})
```

- [ ] **Step 3: 写 `index.html`**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AI Brain 调参试打台</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

- [ ] **Step 4: 写 `.gitignore`**

```
node_modules/
dist/
```

- [ ] **Step 5: 写 `src/main.js`**

```js
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'

createApp(App).use(ElementPlus).mount('#app')
```

- [ ] **Step 6: 写最小 `src/App.vue`（Task 7 再扩充）**

```vue
<template>
  <el-container style="height: 100vh">
    <el-header>AI Brain 调参试打台</el-header>
    <el-main>scaffold ok</el-main>
  </el-container>
</template>
```

- [ ] **Step 7: 安装并构建**

Run:
```bash
cd /Users/qyk9527/ideaProject/spzx-ai-brain/console-ui
npm install
npm run build
ls -1 ../src/main/resources/static
```
Expected: `npm run build` 成功；`static/` 出现 `index.html` 与 `assets/`。

- [ ] **Step 8: 验证后端同源伺服**

前提：MySQL 在线、`db_ai_brain` 存在。启动 8600 后：
```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
cd /Users/qyk9527/ideaProject/spzx-ai-brain && (mvn -q spring-boot:run > /tmp/aibrain_task1.log 2>&1 &)
sleep 25
curl -s -o /dev/null -w 'index=%{http_code}\n' http://localhost:8600/
curl -s http://localhost:8600/ | grep -o '<div id="app"></div>' || true
pkill -f 'spzx-ai-brain.*spring-boot' 2>/dev/null; pkill -f 'com.joker.aibrain.AiBrainApplication' 2>/dev/null
```
Expected: `index=200`；页面含 `<div id="app"></div>`。若 200 但为空，检查 `static/index.html` 是否生成。

---

### Task 2: 纯逻辑 helper + `node:test`

**Files:**
- Create: `console-ui/src/lib/payload.js`
- Test: `console-ui/src/lib/payload.test.js`

**Interfaces:**
- Produces:
  - `buildOverrides({ providerId, model, generation, rag, systemPrompt, toolsLocked })` → 后端 `Overrides` 形状
  - `buildPreviewPayload({ tenantId, sessionId, channel, text, sim, toolsLocked, overrides })` → 后端 `PreviewRequest` 形状
  - `formatUsage(usage)` / `decisionTagType(decision)` / `formatSources(sources)` / `formatToolTrace(trace)`

- [ ] **Step 1: 写失败测试 `src/lib/payload.test.js`**

```js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildOverrides, buildPreviewPayload, formatUsage, decisionTagType, formatSources, formatToolTrace
} from './payload.js'

test('空 provider/model/prompt 一律变 null，不覆盖线上配置', () => {
  const ov = buildOverrides({ providerId: null, model: '  ', systemPrompt: '', toolsLocked: false })
  assert.equal(ov.providerId, null)
  assert.equal(ov.model, null)
  assert.equal(ov.systemPrompt, null)
  assert.equal(ov.toolsLocked, false)
})

test('有值则保留并按需去空格', () => {
  const ov = buildOverrides({ providerId: 3, model: ' gpt-x ', systemPrompt: ' 你是客服 ', toolsLocked: true })
  assert.equal(ov.providerId, 3)
  assert.equal(ov.model, 'gpt-x')
  assert.equal(ov.systemPrompt, ' 你是客服 ')
  assert.equal(ov.toolsLocked, true)
})

test('generation/rag 保留传入字段，便于后端 merge', () => {
  const ov = buildOverrides({
    generation: { temperature: 0.2, topP: 0.8, presencePenalty: null, frequencyPenalty: null, seed: null, maxTokens: 800 },
    rag: { topK: 6, threshold: 0.01, sources: ['faq'], enabled: true }
  })
  assert.equal(ov.generation.temperature, 0.2)
  assert.equal(ov.generation.maxTokens, 800)
  assert.equal(ov.rag.topK, 6)
  assert.deepEqual(ov.rag.sources, ['faq'])
})

test('preview payload 组装且 sessionId 为空时传 null', () => {
  const p = buildPreviewPayload({
    tenantId: 'default', sessionId: '', channel: 'NATIVE', text: '你好',
    sim: { orderNo: 'A1', buyerId: 'b1', shopId: 's1' }, toolsLocked: true,
    overrides: buildOverrides({})
  })
  assert.equal(p.tenantId, 'default')
  assert.equal(p.sessionId, null)
  assert.equal(p.channel, 'NATIVE')
  assert.equal(p.text, '你好')
  assert.deepEqual(p.sim, { orderNo: 'A1', buyerId: 'b1', shopId: 's1' })
  assert.equal(p.overrides.toolsLocked, true)
})

test('决策标签颜色映射', () => {
  assert.equal(decisionTagType('AUTO'), 'success')
  assert.equal(decisionTagType('DRAFT'), 'warning')
  assert.equal(decisionTagType('HANDOFF'), 'danger')
  assert.equal(decisionTagType('???'), 'info')
})

test('usage / sources / toolTrace 文本化', () => {
  assert.match(formatUsage({ promptTokens: 1, completionTokens: 2, totalTokens: 3 }), /1.*2.*3/)
  assert.equal(formatSources([{ title: '发货', score: 0.0313 }])[0], '发货（0.0313）')
  assert.equal(formatToolTrace([{ name: 'query_order', elapsedMs: 3 }])[0], 'query_order（3ms）')
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain/console-ui && npm test`
Expected: FAIL — `Cannot find module './payload.js'`。

- [ ] **Step 3: 写 `src/lib/payload.js`**

```js
function trimOrNull(v) {
  if (v === null || v === undefined) return null
  const s = String(v).trim()
  return s === '' ? null : String(v)
}

export function buildOverrides({
  providerId = null, model = '', generation = null, rag = null,
  systemPrompt = '', toolsLocked = false
} = {}) {
  return {
    providerId: providerId ?? null,
    model: trimOrNull(model),
    generation: generation ?? null,
    rag: rag ?? null,
    systemPrompt: trimOrNull(systemPrompt),
    toolsLocked: !!toolsLocked
  }
}

export function buildPreviewPayload({
  tenantId = 'default', sessionId = null, channel = 'NATIVE', text,
  sim = { orderNo: '', buyerId: '', shopId: '' }, toolsLocked = false, overrides = null
} = {}) {
  const sid = sessionId === null || sessionId === undefined || String(sessionId).trim() === ''
    ? null : String(sessionId)
  return {
    tenantId: tenantId || 'default',
    sessionId: sid,
    channel,
    text,
    sim: {
      orderNo: sim.orderNo || null,
      buyerId: sim.buyerId || null,
      shopId: sim.shopId || null
    },
    overrides: overrides ?? buildOverrides({ toolsLocked })
  }
}

export function formatUsage(usage) {
  if (!usage) return '—'
  const p = usage.promptTokens ?? '—'
  const c = usage.completionTokens ?? '—'
  const t = usage.totalTokens ?? '—'
  return `prompt ${p} / completion ${c} / total ${t}`
}

export function decisionTagType(decision) {
  if (decision === 'AUTO') return 'success'
  if (decision === 'DRAFT') return 'warning'
  if (decision === 'HANDOFF') return 'danger'
  return 'info'
}

export function formatSources(sources) {
  if (!Array.isArray(sources)) return []
  return sources.map((s) => `${s.title}（${s.score}）`)
}

export function formatToolTrace(trace) {
  if (!Array.isArray(trace)) return []
  return trace.map((t) => `${t.name}（${t.elapsedMs}ms）`)
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain/console-ui && npm test`
Expected: `pass 6`（0 fail）。

---

### Task 3: API 客户端 `src/lib/api.js`

**Files:**
- Create: `console-ui/src/lib/api.js`

**Interfaces:**
- Consumes: 后端契约（文末）
- Produces:
  - `getToken()/setToken(t)`
  - `getMeta()`, `preview(payload)`, `listSessions(tenantId)`, `getSession(id)`, `deleteSession(id)`
  - `listPresets(tenantId)`, `savePreset({tenantId,name,paramsJson,remark})`, `deletePreset(id)`, `promotePreset(id)`
  - 统一错误：导出 `ApiError`（含 `status` 与 `message`）

- [ ] **Step 1: 写 `src/lib/api.js`**

```js
import axios from 'axios'

const TOKEN_KEY = 'aibrain_token'
const http = axios.create({ baseURL: '' })

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

http.interceptors.request.use((cfg) => {
  cfg.headers['X-Console-Token'] = getToken()
  return cfg
})

http.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err.response?.status ?? 0
    if (status === 401) {
      return Promise.reject(new ApiError(401, '控制台 token 无效或缺失（顶栏填写 X-Console-Token）'))
    }
    const detail = err.response?.data
    const msg = typeof detail === 'string' && detail ? detail : (detail?.message || err.message)
    return Promise.reject(new ApiError(status, msg))
  }
)

export const getMeta = () => http.get('/console/meta').then((r) => r.data)
export const preview = (payload) => http.post('/console/preview', payload).then((r) => r.data)
export const listSessions = (tenantId = 'default') =>
  http.get('/console/session', { params: { tenantId } }).then((r) => r.data)
export const getSession = (id) => http.get(`/console/session/${id}`).then((r) => r.data)
export const deleteSession = (id) => http.delete(`/console/session/${id}`).then((r) => r.data)
export const listPresets = (tenantId = 'default') =>
  http.get('/console/preset', { params: { tenantId } }).then((r) => r.data)
export const savePreset = (body) => http.post('/console/preset', body).then((r) => r.data)
export const deletePreset = (id) => http.delete(`/console/preset/${id}`).then((r) => r.data)
export const promotePreset = (id) => http.post(`/console/preset/${id}/promote`).then((r) => r.data)
```

- [ ] **Step 2: 编译验证（import 解析）**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain/console-ui && npm run build`
Expected: BUILD 成功（`api.js` 被 tree-shake 前语法正确）。

---

### Task 4: 全局状态 `store.js` + 参数面板 `ParamsPanel.vue`

**Files:**
- Create: `console-ui/src/lib/store.js`
- Create: `console-ui/src/components/ParamsPanel.vue`

**Interfaces:**
- Produces: `store`（reactive，字段见下）；`ParamsPanel` 无 props、直接读写 store。

- [ ] **Step 1: 写 `src/lib/store.js`**

```js
import { reactive } from 'vue'
import { getToken } from './api.js'

export const store = reactive({
  tenantId: 'default',
  token: getToken(),
  connected: false,
  meta: null,
  providerId: null,
  model: '',
  generation: { temperature: 0.3, topP: 0.9, presencePenalty: 0, frequencyPenalty: 0, seed: null, maxTokens: 1024 },
  rag: { topK: 4, threshold: 0.1, sources: ['faq', 'product', 'policy'], enabled: true },
  systemPrompt: '',
  sim: { orderNo: '', buyerId: '', shopId: '' },
  toolsLocked: false,
  channel: 'NATIVE',
  sessionId: null,
  messages: [],
  diagnostics: null,
  presets: [],
  sessions: []
})
```

- [ ] **Step 2: 写 `src/components/ParamsPanel.vue`**

要求（编译通过即可，交互在 Task 7 冒烟）：
- `el-collapse` 五段：生成参数 / 模型与 Provider / 提示词 / RAG / 模拟上下文。
- 生成参数：`temperature`、`topP`、`presencePenalty`、`frequencyPenalty` 用 `el-slider`+`el-input-number`；`seed` 用 `el-input-number`（可空）；`maxTokens` 用 `el-input-number`；三个预设按钮「保守/均衡/创意」分别写 store（保守 0.1/0.8/800，均衡 0.3/0.9/1024，创意 0.9/0.95/1500）。
- 模型与 Provider：`el-select`（options 来自 `store.meta?.providers`，选后同时写 `store.providerId` 与 `store.model` = 该 provider 的 `textModel`）；`store.model` 另给 `el-input` 可改。
- 提示词：`el-input type=textarea` 绑 `store.systemPrompt`。
- RAG：`el-switch` enabled、`el-input-number` topK、`el-input-number` threshold（step 0.01）、`el-select multiple` sources（faq/product/policy）。
- 模拟上下文：orderNo/buyerId/shopId 三个 `el-input`；`el-switch` toolsLocked（文案「锁定为模拟订单号，勿查真实买家」）；`el-select` channel（NATIVE/WECHAT/MINIPROGRAM/DOUYIN/TAOBAO/PDD）。

```vue
<script setup>
import { store } from '../lib/store.js'

const presets = {
  保守: { temperature: 0.1, topP: 0.8, maxTokens: 800 },
  均衡: { temperature: 0.3, topP: 0.9, maxTokens: 1024 },
  创意: { temperature: 0.9, topP: 0.95, maxTokens: 1500 }
}
function applyPreset(name) {
  Object.assign(store.generation, presets[name])
}
function onProviderChange(id) {
  const p = store.meta?.providers?.find((x) => x.id === id)
  store.model = p ? p.textModel : ''
}
const channels = ['NATIVE', 'WECHAT', 'MINIPROGRAM', 'DOUYIN', 'TAOBAO', 'PDD']
</script>

<template>
  <el-collapse>
    <el-collapse-item title="① 生成参数" name="gen">
      <div v-for="k in ['temperature', 'topP', 'presencePenalty', 'frequencyPenalty']" :key="k" class="row">
        <span class="lbl">{{ k }}</span>
        <el-input-number v-model="store.generation[k]" :step="k === 'temperature' || k === 'topP' ? 0.05 : 0.1" :min="0" />
      </div>
      <div class="row"><span class="lbl">maxTokens</span><el-input-number v-model="store.generation.maxTokens" :min="1" /></div>
      <div class="row"><span class="lbl">seed</span><el-input-number v-model="store.generation.seed" :min="0" /></div>
      <el-button-group>
        <el-button v-for="n in ['保守', '均衡', '创意']" :key="n" @click="applyPreset(n)">{{ n }}</el-button>
      </el-button-group>
    </el-collapse-item>

    <el-collapse-item title="② 模型与 Provider" name="model">
      <el-select v-model="store.providerId" placeholder="选择引擎" @change="onProviderChange" style="width: 100%">
        <el-option v-for="p in store.meta?.providers || []" :key="p.id" :label="`${p.name}（${p.textModel}）`" :value="p.id" />
      </el-select>
      <el-input v-model="store.model" placeholder="模型名（留空用 provider 默认）" />
    </el-collapse-item>

    <el-collapse-item title="③ 提示词（覆盖 system prompt）" name="prompt">
      <el-input v-model="store.systemPrompt" type="textarea" :rows="4" placeholder="留空用默认客服人设" />
    </el-collapse-item>

    <el-collapse-item title="④ RAG" name="rag">
      <div class="row"><span class="lbl">启用</span><el-switch v-model="store.rag.enabled" /></div>
      <div class="row"><span class="lbl">topK</span><el-input-number v-model="store.rag.topK" :min="1" /></div>
      <div class="row"><span class="lbl">阈值</span><el-input-number v-model="store.rag.threshold" :step="0.01" :min="0" /></div>
      <el-select v-model="store.rag.sources" multiple style="width: 100%">
        <el-option label="faq" value="faq" /><el-option label="product" value="product" /><el-option label="policy" value="policy" />
      </el-select>
    </el-collapse-item>

    <el-collapse-item title="⑤ 模拟上下文" name="sim">
      <el-input v-model="store.sim.orderNo" placeholder="订单号" />
      <el-input v-model="store.sim.buyerId" placeholder="买家ID" />
      <el-input v-model="store.sim.shopId" placeholder="店铺ID" />
      <div class="row"><span class="lbl">锁定订单号</span><el-switch v-model="store.toolsLocked" /></div>
      <el-select v-model="store.channel" style="width: 100%">
        <el-option v-for="c in channels" :key="c" :label="c" :value="c" />
      </el-select>
    </el-collapse-item>
  </el-collapse>
</template>

<style scoped>
.row { display: flex; align-items: center; gap: 8px; margin: 6px 0; }
.lbl { width: 110px; color: #666; font-size: 13px; }
</style>
```

- [ ] **Step 3: 编译验证**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain/console-ui && npm run build`
Expected: BUILD 成功。

---

### Task 5: 预设面板 `PresetPanel.vue`

**Files:**
- Create: `console-ui/src/components/PresetPanel.vue`

**Interfaces:**
- Consumes: `store`、`api.js`（`listPresets/savePreset/deletePreset/promotePreset`）、`buildOverrides`
- Produces: 预设列表 + 保存当前参数为预设 + 一键提升（二次确认）

- [ ] **Step 1: 写 `src/components/PresetPanel.vue`**

```vue
<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { store } from '../lib/store.js'
import { buildOverrides } from '../lib/payload.js'
import { listPresets, savePreset, deletePreset, promotePreset } from '../lib/api.js'

const name = ref('')
const loading = ref(false)

async function refresh() {
  loading.value = true
  try {
    store.presets = await listPresets(store.tenantId)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!name.value.trim()) return ElMessage.warning('先填预设名称')
  const ov = buildOverrides(store)
  const paramsJson = JSON.stringify({
    providerId: ov.providerId, model: ov.model, generation: store.generation,
    rag: store.rag, systemPrompt: ov.systemPrompt
  })
  try {
    await savePreset({ tenantId: store.tenantId, name: name.value.trim(), paramsJson, remark: 'console-ui' })
    ElMessage.success('已保存')
    name.value = ''
    await refresh()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function promote(p) {
  try {
    await ElMessageBox.confirm(`将预设「${p.name}」提升为线上运行配置？影响所有线上请求。`, '二次确认', { type: 'warning' })
  } catch { return }
  try {
    await promotePreset(p.id)
    ElMessage.success('已提升为线上配置（含审计）')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function remove(p) {
  try { await deletePreset(p.id); ElMessage.success('已删除'); await refresh() } catch (e) { ElMessage.error(e.message) }
}

function apply(p) {
  try {
    const cfg = JSON.parse(p.paramsJson || '{}')
    if (cfg.generation) Object.assign(store.generation, cfg.generation)
    if (cfg.rag) Object.assign(store.rag, cfg.rag)
    if (cfg.providerId != null) store.providerId = cfg.providerId
    if (cfg.model) store.model = cfg.model
    if (cfg.systemPrompt != null) store.systemPrompt = cfg.systemPrompt
    ElMessage.success(`已套用「${p.name}」到表单`)
  } catch { ElMessage.error('预设 paramsJson 解析失败') }
}

defineExpose({ refresh })
</script>

<template>
  <div class="preset">
    <div class="head">
      <span>预设</span>
      <el-button size="small" @click="refresh" :loading="loading">刷新</el-button>
    </div>
    <el-input v-model="name" size="small" placeholder="预设名称" style="margin-bottom: 6px" />
    <el-button size="small" type="primary" style="width: 100%" @click="save">保存当前参数</el-button>
    <el-scrollbar height="calc(100vh - 260px)">
      <div v-for="p in store.presets" :key="p.id" class="item">
        <div class="pname">{{ p.name }}</div>
        <div class="ops">
          <el-button link size="small" @click="apply(p)">套用</el-button>
          <el-button link size="small" type="primary" @click="promote(p)">提升</el-button>
          <el-button link size="small" type="danger" @click="remove(p)">删</el-button>
        </div>
      </div>
    </el-scrollbar>
  </div>
</template>

<style scoped>
.preset { padding: 8px; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; font-weight: 600; }
.item { padding: 6px 0; border-bottom: 1px solid #eee; }
.pname { font-size: 13px; }
.ops { display: flex; gap: 4px; }
</style>
```

- [ ] **Step 2: 编译验证**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain/console-ui && npm run build`
Expected: BUILD 成功。

---

### Task 6: 试打对话 `ChatPanel.vue` + 诊断面板 `DiagnosticsPanel.vue`

**Files:**
- Create: `console-ui/src/components/ChatPanel.vue`
- Create: `console-ui/src/components/DiagnosticsPanel.vue`

**Interfaces:**
- Consumes: `store`、`buildPreviewPayload`、`buildOverrides`、`preview`、`listSessions`、`getSession`、`deleteSession`
- Produces: 多轮试打（每条 `preview` 带 `sessionId`）；`store.messages`、`store.diagnostics`、`store.sessionId` 更新。

- [ ] **Step 1: 写 `src/components/ChatPanel.vue`**

要求：输入框 + 发送；发送时 `buildPreviewPayload`（`sessionId=store.sessionId`），把买家消息与 AI 回复追加到 `store.messages`，更新 `store.sessionId`/`store.diagnostics`；转人工（`handoff=true`）时 AI 气泡显示「已转人工」；顶部按钮：新会话（清空 sessionId/messages/diagnostics）、刷新会话列表、加载会话（`getSession` 后重建 messages）。

```vue
<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { store } from '../lib/store.js'
import { buildPreviewPayload, buildOverrides, decisionTagType } from '../lib/payload.js'
import { preview, listSessions, getSession, deleteSession } from '../lib/api.js'

const text = ref('')
const sending = ref(false)

async function send() {
  const t = text.value.trim()
  if (!t) return
  store.messages.push({ role: 'buyer', content: t })
  sending.value = true
  try {
    const payload = buildPreviewPayload({
      tenantId: store.tenantId, sessionId: store.sessionId, channel: store.channel,
      text: t, sim: store.sim, toolsLocked: store.toolsLocked,
      overrides: buildOverrides(store)
    })
    const out = await preview(payload)
    store.sessionId = out.sessionId
    store.diagnostics = out.response
    store.messages.push({
      role: 'ai',
      content: out.response.handoff ? '（已转人工，无草稿）' : (out.response.reply || '（空回复）'),
      decision: out.response.decision
    })
    text.value = ''
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    sending.value = false
  }
}

function newSession() {
  store.sessionId = null
  store.messages = []
  store.diagnostics = null
}

async function refreshSessions() {
  try { store.sessions = await listSessions(store.tenantId) } catch (e) { ElMessage.error(e.message) }
}

async function load(id) {
  try {
    store.sessionId = id
    const msgs = await getSession(id)
    store.messages = msgs.map((m) => ({ role: m.role, content: m.content, decision: null }))
    store.diagnostics = null
  } catch (e) { ElMessage.error(e.message) }
}

async function remove(id) {
  try { await deleteSession(id); await refreshSessions() } catch (e) { ElMessage.error(e.message) }
}

defineExpose({ refreshSessions })
</script>

<template>
  <div class="chat">
    <el-button-group>
      <el-button size="small" @click="newSession">新会话</el-button>
      <el-button size="small" @click="refreshSessions">刷新会话</el-button>
    </el-button-group>
    <el-select v-model="store.sessionId" size="small" clearable placeholder="历史会话" style="width: 220px; margin-left: 8px" @change="load">
      <el-option v-for="s in store.sessions" :key="s.id" :label="`#${s.id} ${s.title || ''}`" :value="s.id" />
    </el-select>
    <el-button v-if="store.sessionId" size="small" type="danger" @click="remove(store.sessionId)">删会话</el-button>

    <el-scrollbar height="calc(100vh - 360px)" style="margin: 8px 0">
      <div v-for="(m, i) in store.messages" :key="i" :class="['msg', m.role]">
        <span class="who">{{ m.role === 'buyer' ? '买家' : 'AI' }}</span>
        <el-tag v-if="m.decision" :type="decisionTagType(m.decision)" size="small" style="margin-left: 6px">{{ m.decision }}</el-tag>
        <div class="content">{{ m.content }}</div>
      </div>
    </el-scrollbar>

    <el-input v-model="text" type="textarea" :rows="3" placeholder="输入买家消息，Enter 发送（Shift+Enter 换行）" @keydown.enter.exact.prevent="send" />
    <el-button type="primary" :loading="sending" style="margin-top: 6px" @click="send">试打</el-button>
  </div>
</template>

<style scoped>
.chat { padding: 8px; }
.msg { margin: 8px 0; }
.msg .who { font-size: 12px; color: #999; }
.msg.buyer .content { background: #ecf5ff; padding: 8px; border-radius: 6px; }
.msg.ai .content { background: #f5f5f5; padding: 8px; border-radius: 6px; }
</style>
```

- [ ] **Step 2: 写 `src/components/DiagnosticsPanel.vue`**

要求：读 `store.diagnostics`（即 `AiResponse`），无数据时显示空态。展示：决策 `el-tag`、intent、confidence、riskLevel、handoff、elapsedMs、`formatUsage`、`formatSources`、`formatToolTrace`，以及可折叠的 `assembledPrompt`。

```vue
<script setup>
import { computed } from 'vue'
import { store } from '../lib/store.js'
import { decisionTagType, formatUsage, formatSources, formatToolTrace } from '../lib/payload.js'

const d = computed(() => store.diagnostics)
const sources = computed(() => formatSources(d.value?.sources))
const trace = computed(() => formatToolTrace(d.value?.toolTrace))
</script>

<template>
  <div class="diag">
    <div class="head">诊断</div>
    <el-empty v-if="!d" description="还没有试打结果" :image-size="60" />
    <template v-else>
      <div class="kv">
        <el-tag :type="decisionTagType(d.decision)">{{ d.decision }}</el-tag>
        <el-tag v-if="d.handoff" type="danger" style="margin-left: 6px">已转人工</el-tag>
      </div>
      <div class="kv">intent：{{ d.intent }}</div>
      <div class="kv">confidence：{{ d.confidence }}</div>
      <div class="kv">riskLevel：{{ d.riskLevel }}</div>
      <div class="kv">耗时：{{ d.elapsedMs }} ms</div>
      <div class="kv">token：{{ formatUsage(d.usage) }}</div>
      <div class="kv">来源：{{ sources.length ? sources.join('；') : '（无命中）' }}</div>
      <div class="kv">工具轨迹：{{ trace.length ? trace.join('；') : '（无）' }}</div>
      <el-collapse>
        <el-collapse-item title="实际拼装 prompt" name="p">
          <pre class="prompt">{{ d.assembledPrompt || '（无）' }}</pre>
        </el-collapse-item>
      </el-collapse>
    </template>
  </div>
</template>

<style scoped>
.diag { padding: 8px; }
.head { font-weight: 600; margin-bottom: 6px; }
.kv { font-size: 13px; margin: 4px 0; word-break: break-all; }
.prompt { white-space: pre-wrap; font-size: 12px; background: #fafafa; padding: 6px; border-radius: 4px; }
</style>
```

- [ ] **Step 3: 编译验证**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain/console-ui && npm run build`
Expected: BUILD 成功。

---

### Task 7: `App.vue` 布局 + 连接引导

**Files:**
- Modify: `console-ui/src/App.vue`（替换 Task 1 的最小版）

**Interfaces:**
- Consumes: `store`、`api.js`（`getToken/setToken/getMeta`）、三个面板组件
- Produces: 完整单页布局；顶栏连接按钮（写 token → 拉 meta → `connected=true`）。

- [ ] **Step 1: 写完整 `src/App.vue`**

```vue
<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { store } from './lib/store.js'
import { getToken, setToken, getMeta } from './lib/api.js'
import ParamsPanel from './components/ParamsPanel.vue'
import PresetPanel from './components/PresetPanel.vue'
import ChatPanel from './components/ChatPanel.vue'
import DiagnosticsPanel from './components/DiagnosticsPanel.vue'

const tokenInput = ref(getToken())
const presetRef = ref(null)
const chatRef = ref(null)

async function connect() {
  setToken(tokenInput.value.trim())
  store.token = tokenInput.value.trim()
  try {
    store.meta = await getMeta()
    store.connected = true
    ElMessage.success(`已连接：${store.meta.providers.length} 个 provider、${(store.meta.presets || []).length} 个预设`)
    await presetRef.value?.refresh()
    await chatRef.value?.refreshSessions()
  } catch (e) {
    store.connected = false
    ElMessage.error(e.message)
  }
}

onMounted(() => { if (getToken()) connect() })
</script>

<template>
  <el-container class="app">
    <el-header class="header">
      <span class="title">AI Brain 调参试打台</span>
      <el-input v-model="store.tenantId" size="small" style="width: 120px" placeholder="tenant" />
      <el-input v-model="tokenInput" size="small" style="width: 260px" type="password" show-password placeholder="X-Console-Token" />
      <el-button size="small" type="primary" @click="connect">连接</el-button>
      <el-tag :type="store.connected ? 'success' : 'info'" size="small">{{ store.connected ? '已连接' : '未连接' }}</el-tag>
    </el-header>
    <el-container>
      <el-aside width="240px" class="aside"><PresetPanel ref="presetRef" /></el-aside>
      <el-main class="main">
        <el-row :gutter="12">
          <el-col :span="13">
            <el-card shadow="never"><ChatPanel ref="chatRef" /></el-card>
            <el-card shadow="never" style="margin-top: 12px"><ParamsPanel /></el-card>
          </el-col>
          <el-col :span="11"><el-card shadow="never"><DiagnosticsPanel /></el-card></el-col>
        </el-row>
      </el-main>
    </el-container>
  </el-container>
</template>

<style>
html, body, #app { height: 100%; margin: 0; }
.app { height: 100vh; }
.header { display: flex; align-items: center; gap: 8px; background: #fff; border-bottom: 1px solid #eee; }
.title { font-weight: 700; margin-right: 8px; }
.aside { border-right: 1px solid #eee; background: #fff; }
.main { background: #f7f8fa; }
</style>
```

- [ ] **Step 2: 编译验证**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain/console-ui && npm run build`
Expected: BUILD 成功；`src/main/resources/static/assets/*.js` 出现。

---

### Task 8: 收尾——全量构建/同源冒烟/文档/留痕

**Files:**
- Modify: `spzx-ai-brain/README.md`（追加「调参试打台 UI」一节）
- Modify: `spzx-parent/AGENTS.md`（spzx-ai-brain 节补 UI 构建/伺服说明）

**Interfaces:**
- Produces: 可构建、可由后端同源伺服、经 `/console` 代理连通真实 API 的完整试打台。

- [ ] **Step 1: 单元测试 + 构建**

```bash
cd /Users/qyk9527/ideaProject/spzx-ai-brain/console-ui
npm test
npm run build
```
Expected: `pass 6`；BUILD 成功。

- [ ] **Step 2: 同源冒烟（preview server 代理 + 真实 API）**

前提：MySQL 在线、8600 后端起（若未起，先起）。token 用 `application-local.yml` 里的真实值。
```bash
cd /Users/qyk9527/ideaProject/spzx-ai-brain/console-ui
(npm run preview > /tmp/aibrain_preview.log 2>&1 &)
sleep 4
# SPA 外壳
curl -s -o /dev/null -w 'spa=%{http_code}\n' http://localhost:4175/
# 经 preview 代理打后端 API（token 从 application-local.yml 读取，勿打印）
TOKEN=$(grep -A2 '^ai:' /Users/qyk9527/ideaProject/spzx-ai-brain/src/main/resources/application-local.yml | grep token | awk '{print $2}')
curl -s -o /dev/null -w 'proxy_meta=%{http_code}\n' -H "X-Console-Token: $TOKEN" http://localhost:4175/console/meta
curl -s -o /dev/null -w 'proxy_401=%{http_code}\n' http://localhost:4175/console/meta
pkill -f 'vite preview' 2>/dev/null
```
Expected: `spa=200`；`proxy_meta=200`；`proxy_401=401`。（若后端未起，`proxy_meta` 会 500/502 —— 先起后端重试。）

- [ ] **Step 3: 后端同源伺服再验（构建产物）**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
cd /Users/qyk9527/ideaProject/spzx-ai-brain && (mvn -q spring-boot:run > /tmp/aibrain_task8.log 2>&1 &)
sleep 25
curl -s -o /dev/null -w 'backend_index=%{http_code}\n' http://localhost:8600/
pkill -f 'com.joker.aibrain.AiBrainApplication' 2>/dev/null
```
Expected: `backend_index=200`。

- [ ] **Step 4: 文档**

`spzx-ai-brain/README.md` 追加：
```markdown
## 调参试打台 UI（console-ui）

- 开发：`cd console-ui && npm install && npm run dev`（5175，代理 `/console` → 8600）。
- 构建：`npm run build` → 产物写入 `src/main/resources/static`，由后端 8600 同源伺服（`http://localhost:8600/`）。
- 顶栏填 `X-Console-Token`（值在 gitignore 的 `application-local.yml`）后「连接」。
- 纯逻辑测试：`npm test`（Node 内置 `node:test`，无重框架）。
```

`spzx-parent/AGENTS.md` 的 spzx-ai-brain 节补一行：
```markdown
- 试打台 UI：`console-ui/`（Vue3+Vite+ElementPlus），`npm run build` 产物进 `src/main/resources/static` 由 8600 同源伺服；dev 5175 代理 `/console`。
```

- [ ] **Step 5: 留痕**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent && python3 scripts/log_work.py \
  --module "系统" --title "AI Brain 调参试打台 SPA（console-ui）" \
  --progress "8/8 任务；node:test 6/6；同源冒烟 200/401 通过" \
  --remark "Vue3+Vite+ElementPlus；构建产物内嵌 spzx-ai-brain/static；端口5175/8600"
```

- [ ] **Step 6: 不提交**

用户明确不提交 git。跳过。

---

## 后端契约（前端据此调用，已实现，勿改）

- 鉴权：请求头 `X-Console-Token: <token>`（除静态资源外所有 `/console/**`）。
- `GET /console/meta` → `{ providers:[{id,name,textModel,visionModel}], presets:[AiConsolePreset], defaults:{generation,rag} }`（**无 apiKey/baseUrl**）
- `POST /console/preview` body `{tenantId,sessionId,channel,text,sim:{orderNo,buyerId,shopId},overrides:{providerId,model,generation,rag,systemPrompt,toolsLocked}}` → `{sessionId, isTest:true, response:AiResponse}`
- `AiResponse` = `{reply,card,intent,confidence,sources:[{id,title,snippet,score}],handoff,riskLevel,decision,elapsedMs,usage:{promptTokens,completionTokens,totalTokens},toolTrace:[{name,input,output,elapsedMs}],assembledPrompt}`
- `decision` ∈ `AUTO|DRAFT|HANDOFF`；`channel` ∈ `NATIVE|WECHAT|MINIPROGRAM|DOUYIN|TAOBAO|PDD`
- `GET /console/session?tenantId=default` → `[SandboxSession{id,tenantId,title,isTest}]`
- `GET /console/session/{id}` → `[SandboxMessage{id,sessionId,role,content,metaJson}]`
- `DELETE /console/session/{id}`
- `GET /console/preset?tenantId=default` → `[AiConsolePreset{id,tenantId,name,paramsJson,remark,createBy}]`
- `POST /console/preset` body `{tenantId,name,paramsJson,remark}`
- `DELETE /console/preset/{id}`
- `POST /console/preset/{id}/promote`

## 执行顺序

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8。Task 1 是硬前置（依赖能装、能构建、后端能伺服）；Task 2 提供纯逻辑并被 4/5/6/7 复用；Task 7 需要 3/4/5/6 的组件存在才能构建。
