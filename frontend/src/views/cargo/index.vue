<template>
  <section class="page" data-module="cargo">
    <header class="page-head">
      <div>
        <h2>货邮装载管理</h2>
        <p class="page-desc">维护装载单，围绕装载单号、关联航班、货邮重量、装载位置做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记装载单</button>
        <button class="btn" type="button" @click="exportRows">导出货邮装载清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label v-for="field in filterFields" :key="field.param" class="filter-item">
        <span>{{ field.label }}</span>
        <input v-model="filters[field.param]" :placeholder="`按${field.label}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无货邮装载数据，可先登记装载单</td>
        </tr>
      </tbody>
    </table>

    <div class="pagination">
      <button class="btn" type="button" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
      <label class="page-item">
        <span>第</span>
        <input v-model="pageInput" class="page-input" type="text" inputmode="numeric" @keydown.enter.prevent="jumpPage" />
        <span>页</span>
      </label>
      <button class="btn" type="button" :disabled="page >= lastPage" @click="goPage(page + 1)">下一页</button>
      <span>共 {{ lastPage }} 页</span>
      <label class="page-item">
        <span>每页</span>
        <input v-model="sizeInput" class="page-input size-input" type="text" inputmode="numeric" @keydown.enter.prevent="jumpPage" />
        <span>条</span>
      </label>
      <button class="btn" type="button" @click="jumpPage">跳转</button>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条货邮装载记录，当前第 {{ page }} 页 {{ rows.length }} 条</span>
      <span v-if="infoMessage" class="info-text">{{ infoMessage }}</span>
      <span v-else-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="showCreate" class="modal-mask" @click.self="closeCreate">
      <div class="modal">
        <h3>登记装载单</h3>
        <form @submit.prevent="submitCreate">
          <label v-for="field in createFields" :key="field" class="modal-item">
            <span>{{ field }}<em>*</em></span>
            <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
          </label>
          <p v-if="createError" class="error-text">{{ createError }}</p>
          <div class="modal-actions">
            <button class="btn ghost" type="button" @click="closeCreate">取消</button>
            <button class="btn primary" type="submit">提交登记</button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type FilterMap = Record<string, string>

const ENDPOINT = '/api/cargo'
const STORAGE_KEY = 'cargo-list-state'
const MAX_SIZE = 200
const columns = ["装载单号", "关联航班", "货邮重量", "装载位置", "装载车辆", "作业人员", "完成时刻", "装载状态"]
const actions = ["安排装载", "确认完成", "取消装载"]
const stats = [{"label": "待装载货邮", "value": 0}, {"label": "本月装载重量", "value": 0}, {"label": "超重退运", "value": 0}]

// 过滤项标签与后端参数一一对应，翻页时也会原样带回，不会再丢条件。
const filterFields = [
  { label: '装载单号', param: 'keyword' },
  { label: '关联航班', param: 'flight' },
  { label: '货邮重量', param: 'weight' },
  { label: '装载位置', param: 'position' },
]
const createFields = ["装载单号", "关联航班", "货邮重量"]

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const pageInput = ref('1')
const sizeInput = ref('20')
const errorMessage = ref('')
const infoMessage = ref('')
const filters = ref<FilterMap>({})

const showCreate = ref(false)
const createForm = ref<Record<string, string>>({})
const createError = ref('')

const lastPage = computed(() => Math.max(1, Math.ceil(total.value / size.value)))

function persistState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ filters: filters.value, page: page.value, size: size.value }))
  } catch {
    // 隐私模式等场景下持久化可能失败，忽略即可，不影响本次查询
  }
}

function restoreState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const saved = JSON.parse(raw) as { filters?: FilterMap; page?: unknown; size?: unknown }
    if (saved.filters && typeof saved.filters === 'object') {
      const restored: FilterMap = {}
      for (const field of filterFields) {
        const value = saved.filters[field.param]
        if (typeof value === 'string' && value.trim()) restored[field.param] = value
      }
      filters.value = restored
    }
    if (typeof saved.page === 'number' && Number.isInteger(saved.page) && saved.page >= 1) {
      page.value = saved.page
    }
    if (typeof saved.size === 'number' && Number.isInteger(saved.size) && saved.size >= 1 && saved.size <= MAX_SIZE) {
      size.value = saved.size
    }
  } catch {
    // 本地缓存损坏时回退默认值
  }
  pageInput.value = String(page.value)
  sizeInput.value = String(size.value)
}

// 页码/每页条数只接受正整数：0、负数、非数字都视为失败，明确提示而不是静默纠正。
function parsePositiveInt(raw: string, label: string): number | null {
  const value = raw.trim()
  if (!/^\d+$/.test(value) || Number(value) < 1) {
    errorMessage.value = `${label}必须是不小于 1 的整数，当前输入「${raw}」无效`
    infoMessage.value = ''
    return null
  }
  return Number(value)
}

function buildQuery(targetPage: number, targetSize: number) {
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = filters.value[field.param]?.trim()
    if (value) params.set(field.param, value)
  }
  params.set('page', String(targetPage))
  params.set('size', String(targetSize))
  return params.toString()
}

async function readError(response: Response, fallback: string) {
  try {
    const payload = (await response.json()) as { detail?: unknown }
    if (typeof payload.detail === 'string') return payload.detail
  } catch {
    // 错误体不是 JSON 时用兜底文案
  }
  return fallback
}

async function reload(targetPage = page.value, targetSize = size.value) {
  errorMessage.value = ''
  infoMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}?${buildQuery(targetPage, targetSize)}`)
    if (!response.ok) {
      // 非法分页参数等 400 错误：表格清空、合计归零，明确提示，三个数不再对不上。
      rows.value = []
      total.value = 0
      throw new Error(await readError(response, '装载单列表读取失败'))
    }
    const payload = (await response.json()) as {
      items?: Row[]
      total?: number
      page?: number
      size?: number
      message?: string | null
    }
    rows.value = payload.items ?? []
    total.value = payload.total ?? 0
    // 页码超出末页时后端会落到最后一页，以返回值为准，页码、行数、合计保持一致。
    page.value = payload.page ?? targetPage
    size.value = payload.size ?? targetSize
    pageInput.value = String(page.value)
    sizeInput.value = String(size.value)
    infoMessage.value = payload.message ?? ''
    persistState()
  } catch (error) {
    // 请求失败：保留当前页码/条数输入并回填到输入框，不悄悄跳到第一页。
    errorMessage.value = error instanceof Error ? error.message : '货邮装载列表读取失败'
    pageInput.value = String(page.value)
    sizeInput.value = String(size.value)
  }
}

function jumpPage() {
  errorMessage.value = ''
  infoMessage.value = ''
  const nextPage = parsePositiveInt(pageInput.value, '页码')
  if (nextPage === null) {
    pageInput.value = String(page.value)
    return
  }
  const nextSize = parsePositiveInt(sizeInput.value, '每页条数')
  if (nextSize === null) {
    sizeInput.value = String(size.value)
    return
  }
  if (nextSize > MAX_SIZE) {
    errorMessage.value = `每页最多 ${MAX_SIZE} 条，请缩小分页范围`
    infoMessage.value = ''
    sizeInput.value = String(size.value)
    return
  }
  // 改每页条数后从第一页开始查；页码越界交给后端收敛到最后一页。
  // 状态由 reload 在请求成功后提交，失败时保留当前页码/条数。
  const targetPage = nextSize !== size.value ? 1 : nextPage
  void reload(targetPage, nextSize)
}

function goPage(target: number) {
  pageInput.value = String(target)
  void reload(target, size.value)
}

function applyFilters() {
  void reload(1, size.value)
}

function resetFilters() {
  filters.value = {}
  void reload(1, 20)
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = Object.fromEntries(createFields.map((field) => [field, '']))
  createError.value = ''
  showCreate.value = true
}

function closeCreate() {
  showCreate.value = false
}

async function submitCreate() {
  createError.value = ''
  const values: Record<string, string> = {}
  const missing: string[] = []
  for (const field of createFields) {
    const value = createForm.value[field]?.trim() ?? ''
    if (!value) missing.push(field)
    values[field] = value
  }
  if (missing.length) {
    createError.value = `缺少必填字段：${missing.join('、')}`
    return
  }
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = (await response.json()) as { ok?: boolean; message?: string }
    if (!response.ok || !payload.ok) {
      createError.value = payload.message || '装载单登记失败，请稍后重试'
      return
    }
    showCreate.value = false
    void reload(1, size.value)
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '装载单登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  infoMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error(await readError(response, '货邮装载动作未生效，请稍后重试'))
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '货邮装载操作失败'
  }
}

restoreState()
onMounted(reload)
</script>

<style scoped>
.pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  font-size: 13px;
  color: var(--muted);
}
.page-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.page-input {
  width: 56px;
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  text-align: center;
}
.size-input {
  width: 64px;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.info-text {
  color: #b54708;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  width: 420px;
  background: #fff;
  border-radius: 10px;
  padding: 20px 24px;
}
.modal h3 {
  margin: 0 0 16px;
}
.modal-item {
  display: block;
  margin-bottom: 12px;
}
.modal-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.modal-item em {
  color: #b42318;
  font-style: normal;
  margin-left: 2px;
}
.modal-item input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
</style>
