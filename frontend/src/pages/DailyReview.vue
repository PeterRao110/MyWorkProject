<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { phaseOf, type DailyPlan, type ExecResult, type PlanItem } from "@/data/dailyReview";
import {
  createDailyPlanItem,
  listDailyPlans,
  moveDailyPlanItem,
  removeDailyPlanItem,
  saveDailyPlanReview,
} from "@/services/dailyReview";
import { getMarketStatus, searchInstruments } from "@/services/market";
import type { Instrument } from "@/types/market";
import { formatPrice } from "@/utils/format";

const tradeDate = getMarketStatus().tradeDate;
const selectedDate = ref(tradeDate);
const view = ref<"list" | "detail">("list");
const varietyFilter = ref("");
const step = ref<"plan" | "review">("plan");
const notice = ref("");
const symbolQuery = ref("");
const symbolOpen = ref(false);
const picked = ref<Instrument | null>(null);

const draft = reactive({
  trend: "",
  operationPlan: "",
  strategy: "",
});

const itemDrafts = reactive<Record<string, { result: ExecResult; resultNote: string; nextPlan: string }>>({});
const plans = ref<DailyPlan[]>([]);

const current = computed<DailyPlan>(() => {
  return plans.value.find((day) => day.date === selectedDate.value) ?? { date: selectedDate.value, items: [] };
});
const days = computed(() => plans.value);
const varieties = computed(() => {
  const names = new Set<string>();
  for (const day of days.value) {
    for (const item of day.items) {
      if (item.symbolName) names.add(item.symbolName);
    }
  }
  return [...names].sort((left, right) => left.localeCompare(right, "zh"));
});
const filteredDays = computed(() => {
  const name = varietyFilter.value;
  if (!name) return days.value;
  return days.value
    .map((day) => ({ ...day, items: day.items.filter((item) => item.symbolName === name) }))
    .filter((day) => day.items.length > 0);
});
const phase = computed(() => phaseOf(current.value));
const symbolResults = computed(() => searchInstruments(symbolQuery.value));
const draftPrice = computed(() => (picked.value ? formatPrice(picked.value.close) : ""));

const phaseText: Record<string, string> = {
  planning: "计划中",
  ready: "待复盘",
  reviewed: "已复盘",
};

const resultText: Record<string, string> = {
  pending: "未执行",
  success: "成功",
  failure: "失败",
};

function draftOf(item: PlanItem) {
  if (!itemDrafts[item.id]) {
    itemDrafts[item.id] = {
      result: item.result,
      resultNote: item.resultNote,
      nextPlan: item.nextPlan,
    };
  }
  return itemDrafts[item.id];
}

function loadReview() {
  for (const item of current.value.items) {
    itemDrafts[item.id] = {
      result: item.result,
      resultNote: item.resultNote,
      nextPlan: item.nextPlan,
    };
  }
  notice.value = "";
  step.value = "plan";
}

onMounted(async () => {
  try {
    plans.value = await listDailyPlans();
  } catch (error) {
    notice.value = error instanceof Error ? error.message : "读取计划失败";
  }
});

function selectDate(date: string) {
  selectedDate.value = date;
  loadReview();
  view.value = "detail";
}

const weekdays = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
const expandedYears = ref<Record<string, boolean>>({});
const expandedMonths = ref<Record<string, boolean>>({});

function parseIso(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function toIso(date: Date) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function revealDate(value: string) {
  const [year, month] = value.split("-");
  expandedYears.value[year] = true;
  expandedMonths.value[`${year}-${month}`] = true;
}

watch(selectedDate, revealDate, { immediate: true });

const dateTree = computed(() => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const selected = parseIso(selectedDate.value);
  const end = selected > today ? selected : today;
  let start = new Date(end.getFullYear(), end.getMonth() - 2, 1);
  for (const day of days.value) {
    const date = parseIso(day.date);
    const monthStart = new Date(date.getFullYear(), date.getMonth(), 1);
    if (monthStart < start) start = monthStart;
  }

  const years: { key: string; label: string; months: { key: string; label: string; days: { date: string; label: string }[] }[] }[] = [];
  const cursor = new Date(end.getFullYear(), end.getMonth(), 1);
  while (cursor >= start) {
    const year = cursor.getFullYear();
    const month = cursor.getMonth();
    const lastDay = year === end.getFullYear() && month === end.getMonth() ? end.getDate() : new Date(year, month + 1, 0).getDate();
    const monthDays = [];
    for (let day = lastDay; day >= 1; day -= 1) {
      const date = new Date(year, month, day);
      const iso = toIso(date);
      monthDays.push({ date: iso, label: `${iso} ${weekdays[date.getDay()]}` });
    }
    const yearKey = String(year);
    let yearNode = years.find((item) => item.key === yearKey);
    if (!yearNode) {
      yearNode = { key: yearKey, label: `${year}年`, months: [] };
      years.push(yearNode);
    }
    yearNode.months.push({
      key: `${year}-${String(month + 1).padStart(2, "0")}`,
      label: `${year}年${month + 1}月`,
      days: monthDays,
    });
    cursor.setMonth(cursor.getMonth() - 1);
  }
  return years;
});

function toggleYear(key: string) {
  expandedYears.value[key] = !expandedYears.value[key];
}

function toggleMonth(key: string) {
  expandedMonths.value[key] = !expandedMonths.value[key];
}

function chooseSymbol(item: Instrument) {
  picked.value = item;
  symbolQuery.value = `${item.name} ${item.code}`;
  symbolOpen.value = false;
}

function onSymbolInput() {
  const label = picked.value ? `${picked.value.name} ${picked.value.code}` : "";
  if (symbolQuery.value !== label) picked.value = null;
  symbolOpen.value = symbolQuery.value.trim().length > 0 && !picked.value;
}

function clearSymbol() {
  picked.value = null;
  symbolQuery.value = "";
  symbolOpen.value = false;
}

function applyPlan(plan: DailyPlan) {
  const next = plans.value.filter((day) => day.date !== plan.date);
  if (plan.items.length) next.push(plan);
  next.sort((left, right) => right.date.localeCompare(left.date));
  plans.value = next;
}

async function addItem() {
  notice.value = "";
  if (!picked.value) {
    notice.value = "请选择品种";
    return;
  }
  if (!draft.operationPlan.trim()) {
    notice.value = "请填写操作计划";
    return;
  }
  try {
    const plan = await createDailyPlanItem(selectedDate.value, {
      symbol: picked.value.code,
      symbolName: picked.value.name,
      price: picked.value.close,
      trend: draft.trend,
      operationPlan: draft.operationPlan,
      strategy: draft.strategy,
    });
    applyPlan(plan);
    draft.trend = "";
    draft.operationPlan = "";
    draft.strategy = "";
    clearSymbol();
  } catch (error) {
    notice.value = error instanceof Error ? error.message : "加入计划失败";
  }
}

async function moveItem(item: PlanItem, direction: -1 | 1) {
  notice.value = "";
  try {
    applyPlan(await moveDailyPlanItem(selectedDate.value, item, direction));
  } catch (error) {
    notice.value = error instanceof Error ? error.message : "调整顺序失败";
  }
}

async function removeItem(item: PlanItem) {
  notice.value = "";
  try {
    applyPlan(await removeDailyPlanItem(selectedDate.value, item));
  } catch (error) {
    notice.value = error instanceof Error ? error.message : "删除计划失败";
  }
}

async function saveItem(item: PlanItem) {
  const draft = draftOf(item);
  notice.value = "";
  if (draft.result !== "pending" && !draft.resultNote.trim()) {
    notice.value = "请填写执行结果描述";
    return;
  }
  try {
    applyPlan(await saveDailyPlanReview(selectedDate.value, item, draft));
    notice.value = `${item.symbolName || "该品种"}的复盘已保存`;
  } catch (error) {
    notice.value = error instanceof Error ? error.message : "保存复盘失败";
  }
}
</script>

<template>
  <section class="review-page">
    <div class="review-main">
      <div class="seg" role="tablist" aria-label="每日计划复盘">
        <button type="button" :class="{ active: view === 'list' }" @click="view = 'list'">计划列表</button>
        <button type="button" :class="{ active: view === 'detail' }" @click="view = 'detail'">执行复盘</button>
      </div>

      <div v-if="view === 'list'" class="panel review-list">
        <label class="review-filter">
          <span>品种</span>
          <select v-model="varietyFilter">
            <option value="">全部</option>
            <option v-for="name in varieties" :key="name" :value="name">{{ name }}</option>
          </select>
        </label>
        <div class="table-wrap">
          <table class="review-table">
            <thead>
              <tr>
                <th>日期</th>
                <th>品种</th>
                <th>当前价格</th>
                <th>当前趋势</th>
                <th>操作计划</th>
                <th>操作策略</th>
                <th>执行结果</th>
                <th>执行结果描述</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!filteredDays.length">
                <td colspan="8" class="review-empty-cell">{{ varietyFilter ? "没有符合该品种的计划。" : "还没有每日计划。" }}</td>
              </tr>
              <template v-for="day in filteredDays" :key="day.date">
                <tr
                  v-if="!day.items.length"
                  :class="{ selected: day.date === selectedDate }"
                  @click="selectDate(day.date)"
                >
                  <td>{{ day.date }}</td>
                  <td colspan="7" class="review-empty-cell">这一天还没有计划。</td>
                </tr>
                <tr
                  v-for="item in day.items"
                  :key="item.id"
                  :class="{ selected: day.date === selectedDate }"
                  @click="selectDate(day.date)"
                >
                  <td>{{ day.date }}</td>
                  <td>{{ item.symbolName || "—" }}</td>
                  <td>{{ item.price == null ? "—" : formatPrice(item.price) }}</td>
                  <td class="wrap">{{ item.trend || "—" }}</td>
                  <td class="wrap">{{ item.operationPlan || "—" }}</td>
                  <td class="wrap">{{ item.strategy || "—" }}</td>
                  <td>{{ resultText[item.result] }}</td>
                  <td class="wrap">{{ item.reviewed && item.resultNote.trim() ? item.resultNote : "—" }}</td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>

      <template v-else>
      <div class="review-detail">
      <div class="review-date">
        <div class="date-card">
          <svg class="date-card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <rect x="3" y="5" width="18" height="16" rx="2" />
            <path d="M3 10h18" />
            <path d="M8 3v4" />
            <path d="M16 3v4" />
          </svg>
          <div>
            <span>执行日期</span>
            <strong>{{ selectedDate }}</strong>
          </div>
        </div>
        <span class="chip" :class="phase">{{ phaseText[phase] }}</span>
        <div class="date-tree">
          <div v-for="year in dateTree" :key="year.key">
            <button type="button" class="date-node" @click="toggleYear(year.key)">
              <span class="caret" :class="{ open: expandedYears[year.key] }"></span>
              {{ year.label }}
            </button>
            <div v-if="expandedYears[year.key]" class="date-children">
              <div v-for="month in year.months" :key="month.key">
                <button type="button" class="date-node" @click="toggleMonth(month.key)">
                  <span class="caret" :class="{ open: expandedMonths[month.key] }"></span>
                  {{ month.label }}
                </button>
                <div v-if="expandedMonths[month.key]" class="date-days">
                  <button
                    v-for="day in month.days"
                    :key="day.date"
                    type="button"
                    class="date-day"
                    :class="{ active: day.date === selectedDate }"
                    @click="selectDate(day.date)"
                  >
                    {{ day.label }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="review-detail-main">
      <div class="seg" role="tablist">
        <button type="button" :class="{ active: step === 'plan' }" @click="step = 'plan'">执行计划</button>
        <button type="button" :class="{ active: step === 'review' }" @click="step = 'review'">复盘总结</button>
      </div>

      <div v-if="step === 'plan'" class="stack">
        <div v-if="!current.items.length" class="panel review-empty">这一天还没有计划。</div>

        <article v-for="(item, index) in current.items" :key="item.id" class="panel review-item">
          <header class="review-item-head">
            <div>
              <strong>{{ item.symbolName || item.operationPlan }}</strong>
              <p v-if="item.symbol">{{ item.symbol }}<template v-if="item.price != null"> · 当前价格 {{ formatPrice(item.price) }}</template></p>
              <p v-if="item.trend">当前趋势：{{ item.trend }}</p>
              <p v-if="item.operationPlan">操作计划：{{ item.operationPlan }}</p>
              <p v-if="item.strategy">操作策略：{{ item.strategy }}</p>
            </div>
            <div class="review-item-ops">
              <button type="button" class="secondary-btn" :disabled="index === 0" @click="moveItem(item, -1)">上移</button>
              <button type="button" class="secondary-btn" :disabled="index === current.items.length - 1" @click="moveItem(item, 1)">下移</button>
              <button type="button" class="secondary-btn" @click="removeItem(item)">删除</button>
            </div>
          </header>
        </article>

        <form class="panel review-form" @submit.prevent="addItem">
          <h2>新增计划</h2>
          <div class="review-pair">
            <label class="review-symbol">
              <span>品种</span>
              <input
                v-model="symbolQuery"
                placeholder="搜索品种"
                @focus="onSymbolInput"
                @input="onSymbolInput"
              />
              <div v-if="symbolOpen && symbolResults.length" class="results">
                <button v-for="item in symbolResults" :key="item.code" type="button" @click="chooseSymbol(item)">
                  <span>{{ item.name }}</span>
                  <small>{{ item.code }} · {{ formatPrice(item.close) }}</small>
                </button>
              </div>
            </label>
            <label>
              <span>当前价格</span>
              <input :value="draftPrice" readonly placeholder="选择品种后自动带出" />
            </label>
          </div>
          <label>
            <span>品种当前趋势</span>
            <input v-model="draft.trend" placeholder="例如震荡、偏强、回落" />
          </label>
          <label>
            <span>操作计划</span>
            <textarea v-model="draft.operationPlan" rows="3" placeholder="今天准备怎么操作" />
          </label>
          <label>
            <span>操作策略</span>
            <textarea v-model="draft.strategy" rows="3" placeholder="触发条件、仓位和退出方式" />
          </label>
          <button class="primary-btn" type="submit">加入计划</button>
        </form>
      </div>

      <div v-else class="stack">
        <div v-if="!current.items.length" class="panel review-empty">这一天还没有计划，请先在执行计划中添加。</div>
        <article v-for="item in current.items" :key="item.id" class="panel review-item">
          <header class="review-item-head">
            <div>
              <strong>{{ item.symbolName || item.operationPlan }}</strong>
              <p v-if="item.symbol">{{ item.symbol }}<template v-if="item.price != null"> · 当前价格 {{ formatPrice(item.price) }}</template></p>
              <p v-if="item.trend">当前趋势：{{ item.trend }}</p>
              <p v-if="item.operationPlan">操作计划：{{ item.operationPlan }}</p>
              <p v-if="item.strategy">操作策略：{{ item.strategy }}</p>
            </div>
          </header>
          <div class="seg" role="group" :aria-label="`${item.symbolName}执行结果`">
            <button type="button" :class="{ active: draftOf(item).result === 'pending' }" @click="draftOf(item).result = 'pending'">未执行</button>
            <button type="button" :class="{ active: draftOf(item).result === 'success' }" @click="draftOf(item).result = 'success'">成功</button>
            <button type="button" :class="{ active: draftOf(item).result === 'failure' }" @click="draftOf(item).result = 'failure'">失败</button>
          </div>
          <label>
            <span>执行结果描述</span>
            <textarea v-model="draftOf(item).resultNote" rows="3" placeholder="这次实际发生了什么" />
          </label>
          <label>
            <span>下次计划</span>
            <textarea v-model="draftOf(item).nextPlan" rows="3" placeholder="下次准备怎么做" />
          </label>
          <div class="review-actions">
            <button class="primary-btn" type="button" @click="saveItem(item)">保存</button>
            <span v-if="item.reviewed" class="hint ok">已保存</span>
          </div>
        </article>
      </div>

      <p v-if="notice" class="hint" :class="notice.endsWith('已保存') ? 'ok' : 'error'">{{ notice }}</p>
      </div>
      </div>
      </template>
    </div>
  </section>
</template>
