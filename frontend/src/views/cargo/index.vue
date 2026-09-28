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

    <form class="filter-bar" @submit.prevent="searchWithFilters">
      <label v-for="field in filterFields" :key="field.key" class="filter-item">
        <span>{{ field.label }}</span>
        <input v-model="filters[field.key]" :placeholder="`按${field.label}检索`" />
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

    <div class="pager-bar">
      <button class="btn" type="button" :disabled="pageNumber <= 1" @click="goPage(pageNumber - 1)">上一页</button>
      <label class="pager-item">
        <span>页码</span>
        <input v-model="pageInput" class="pager-input" type="number" min="1" @change="applyPageInput" />
      </label>
      <span class="pager-hint">/ {{ totalPages }} 页</span>
      <button class="btn" type="button" :disabled="pageNumber >= totalPages" @click="goPage(pageNumber + 1)">下一页</button>
      <label class="pager-item">
        <span>每页条数</span>
        <input v-model="sizeInput" class="pager-input" type="number" min="1" max="200" @change="applySizeInput" />
      </label>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条货邮装载记录，本页 {{ rows.length }} 条，第 {{ pageNumber }} / {{ totalPages }} 页</span>
    </footer>

    <div v-if="creating" class="modal-mask" @click.self="closeCreate">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3>登记装载单</h3>
        <label v-for="field in createFields" :key="field" class="filter-item">
          <span>{{ field }}</span>
          <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
        </label>
        <span v-if="createMessage" class="error-text">{{ createMessage }}</span>
        <div class="modal-actions">
          <button class="btn primary" type="submit">提交登记</button>
          <button class="btn ghost" type="button" @click="closeCreate">取消</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type FilterKey = 'keyword' | 'flight' | 'weight' | 'location'

const ENDPOINT = '/api/cargo'
const STORAGE_KEY = 'cargo:list-state'
const columns = ["装载单号", "关联航班", "货邮重量", "装载位置", "装载车辆", "作业人员", "完成时刻", "装载状态"]
const actions = ["安排装载", "确认完成", "取消装载"]
const statuses = ["待装载", "装载中", "已完成", "已取消"]
const stats = [{"label": "待装载货邮", "value": 0}, {"label": "本月装载重量", "value": 0}, {"label": "超重退运", "value": 0}]
const filterFields: { key: FilterKey; label: string }[] = [
  { key: 'keyword', label: '装载单号' },
  { key: 'flight', label: '关联航班' },
  { key: 'weight', label: '货邮重量' },
  { key: 'location', label: '装载位置' },
]
const createFields = ["装载单号", "关联航班", "货邮重量"]

const rows = ref<Row[]>([])
const total = ref(0)
const pageNumber = ref(1)
const pageInput = ref('1')
const sizeInput = ref('20')
const errorMessage = ref('')
const filters = ref<Record<FilterKey, string>>({ keyword: '', flight: '', weight: '', location: '' })

const creating = ref(false)
const createMessage = ref('')
const createForm = reactive<Record<string, string>>({ 装载单号: '', 关联航班: '', 货邮重量: '' })

const totalPages = computed(() => {
  const size = Number(sizeInput.value)
  if (!Number.isInteger(size) || size < 1) return 1
  return Math.max(Math.ceil(total.value / size), 1)
})

function persistState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      filters: filters.value,
      page: pageInput.value,
      size: sizeInput.value,
    }))
  } catch {
    // 隐私模式等场景下持久化不可用，不影响本次查询
  }
}

function restoreState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const saved = JSON.parse(raw) as { filters?: Partial<Record<FilterKey, string>>; page?: string; size?: string }
    if (saved.filters) {
      for (const field of filterFields) {
        filters.value[field.key] = saved.filters[field.key] ?? ''
      }
    }
    if (saved.page) pageInput.value = saved.page
    if (saved.size) sizeInput.value = saved.size
  } catch {
    // 存档损坏时退回默认状态
  }
}

function validatePositiveInteger(raw: string, label: string): number | null {
  if (raw.trim() === '' || !/^\d+$/.test(raw.trim())) {
    errorMessage.value = `${label}必须是不小于 1 的正整数，请重新输入`
    return null
  }
  const value = Number(raw.trim())
  if (value < 1) {
    errorMessage.value = `${label}必须是不小于 1 的正整数，请重新输入`
    return null
  }
  return value
}

function resetView(matcher: string) {
  // 查询失败时清空表格与合计，避免页码、行数、合计对不上
  rows.value = []
  total.value = 0
  errorMessage.value = matcher
}

async function reload() {
  errorMessage.value = ''
  const page = validatePositiveInteger(pageInput.value, '页码')
  if (page === null) {
    rows.value = []
    total.value = 0
    return
  }
  const size = validatePositiveInteger(sizeInput.value, '每页条数')
  if (size === null) {
    rows.value = []
    total.value = 0
    return
  }
  if (size > 200) {
    resetView('每页最多 200 条，请缩小分页范围')
    return
  }
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = filters.value[field.key]?.trim()
    if (value) params.set(field.key, value)
  }
  params.set('page', String(page))
  params.set('size', String(size))
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null
      throw new Error(payload?.detail || '装载单列表读取失败')
    }
    const payload = (await response.json()) as { items?: Row[]; total?: number; page?: number; size?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    // 服务端把超范围页码落到最后一页时，以服务端返回的页码为准
    const syncedPage = payload.page ?? page
    pageNumber.value = syncedPage
    pageInput.value = String(syncedPage)
    persistState()
  } catch (error) {
    resetView(error instanceof Error ? error.message : '货邮装载列表读取失败')
  }
}

function searchWithFilters() {
  // 重新查询时回到第一页，但保留全部过滤条件
  const size = validatePositiveInteger(sizeInput.value, '每页条数')
  if (size === null) {
    rows.value = []
    total.value = 0
    return
  }
  pageNumber.value = 1
  pageInput.value = '1'
  void reload()
}

function applyPageInput() {
  void reload()
}

function applySizeInput() {
  // 改变每页条数后回到第一页
  pageNumber.value = 1
  pageInput.value = '1'
  void reload()
}

function goPage(target: number) {
  pageInput.value = String(target)
  void reload()
}

function resetFilters() {
  filters.value = { keyword: '', flight: '', weight: '', location: '' }
  pageNumber.value = 1
  pageInput.value = '1'
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createMessage.value = ''
  for (const field of createFields) createForm[field] = ''
  creating.value = true
}

function closeCreate() {
  creating.value = false
}

async function submitCreate() {
  createMessage.value = ''
  const values: Record<string, string> = {}
  for (const field of createFields) values[field] = createForm[field]?.trim() ?? ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = (await response.json()) as { ok?: boolean; message?: string }
    if (!response.ok || !payload.ok) {
      createMessage.value = payload.message || '装载单登记失败，请检查填写内容'
      return
    }
    creating.value = false
    pageNumber.value = 1
    pageInput.value = '1'
    await reload()
  } catch (error) {
    createMessage.value = error instanceof Error ? error.message : '装载单登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('货邮装载动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '货邮装载操作失败'
  }
}

onMounted(() => {
  restoreState()
  void reload()
})
</script>

<style scoped>
.pager-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  font-size: 13px;
}
.pager-item {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
}
.pager-input {
  width: 72px;
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.pager-hint {
  color: var(--muted);
  font-size: 12px;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
.modal-card {
  width: 380px;
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.modal-card h3 {
  margin: 0;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
