<script setup lang="ts">
import { ref } from "vue";
import { updateScheduleRunState, type ScheduleRunState } from "@/services/schedule";

const props = defineProps<{ rows: ScheduleRunState[]; runningIds: number[] }>();
const emit = defineEmits<{
  saved: [];
  error: [message: string];
  select: [jobId: number];
  run: [jobId: number];
  detail: [jobId: number];
}>();

type Draft = {
  jobId: number;
  groupName: string;
  jobName: string;
  dateInterval: string;
  nextStart: string;
  nextEnd: string;
  lastStart: string;
  lastEnd: string;
  durationSeconds: string;
  rowCount: string;
  successAt: string;
};

const editing = ref<Draft | null>(null);
const saving = ref(false);
const error = ref("");

function statusText(status: string) {
  return { success: "成功", failed: "失败", running: "运行中" }[status] || "未运行";
}

function isRunning(jobId: number) {
  return props.runningIds.includes(jobId) || props.rows.some((row) => row.jobId === jobId && row.lastStatus === "running");
}

function toInputDate(value: string) {
  return /^\d{8}$/.test(value) ? `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}` : "";
}

function fromInputDate(value: string) {
  return value ? value.replaceAll("-", "") : "";
}

function showDate(value: string) {
  return toInputDate(value) || "—";
}

function toLocalInput(value: string) {
  return value ? value.replace(" ", "T").slice(0, 19) : "";
}

function fromLocalInput(value: string) {
  if (!value) return "";
  const text = value.replace("T", " ");
  return text.length === 16 ? `${text}:00` : text.slice(0, 19);
}

function msToSeconds(ms: number | null) {
  if (ms == null) return "";
  const seconds = ms / 1000;
  if (seconds >= 10) return seconds.toFixed(1);
  return seconds.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function showDuration(ms: number | null) {
  const seconds = msToSeconds(ms);
  return seconds ? `${seconds} 秒` : "—";
}

function showCount(count: number | null) {
  return count == null ? "—" : String(count);
}

function showTime(value: string) {
  return value || "—";
}

function addDays(iso: string, days: number) {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCDate(date.getUTCDate() + days);
  const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(date.getUTCDate()).padStart(2, "0");
  return `${date.getUTCFullYear()}-${mm}-${dd}`;
}

function intervalOf(row: Draft) {
  const interval = Number(row.dateInterval);
  return Number.isInteger(interval) && interval >= 1 ? interval : 0;
}

function openEdit(row: ScheduleRunState) {
  error.value = "";
  editing.value = {
    jobId: row.jobId,
    groupName: row.groupName,
    jobName: row.jobName,
    dateInterval: String(row.dateInterval || 1),
    nextStart: toInputDate(row.nextStartDate),
    nextEnd: toInputDate(row.nextEndDate),
    lastStart: toInputDate(row.lastSuccessStart),
    lastEnd: toInputDate(row.lastSuccessEnd),
    durationSeconds: msToSeconds(row.durationMs),
    rowCount: row.lastRowCount == null ? "" : String(row.lastRowCount),
    successAt: toLocalInput(row.lastSuccessAt),
  };
}

function closeEdit() {
  if (saving.value) return;
  editing.value = null;
  error.value = "";
}

function onInterval(event: Event) {
  const row = editing.value;
  if (!row) return;
  const interval = Number((event.target as HTMLInputElement).value);
  if (!row.nextStart || !Number.isInteger(interval) || interval < 1) return;
  row.nextEnd = addDays(row.nextStart, interval - 1);
}

function tradeWindowJob(name: string) {
  return name === "期货日线行情" || name === "期货复权行情" || name === "每日结算参数";
}

function todayInput() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function onNextStart() {
  const row = editing.value;
  if (!row) return;
  if (tradeWindowJob(row.jobName) && row.nextStart && row.nextStart > todayInput()) {
    error.value = "下次开始日期不能超过当天";
    return;
  }
  error.value = "";
  const interval = intervalOf(row);
  if (!row.nextStart || !interval) return;
  row.nextEnd = addDays(row.nextStart, interval - 1);
}

async function save() {
  const row = editing.value;
  if (!row) return;
  error.value = "";
  const interval = intervalOf(row);
  if (!interval || interval > 20000) {
    error.value = "日期间隔需要是 1 到 20000 的整数";
    return;
  }
  const nextStart = fromInputDate(row.nextStart);
  const nextEnd = fromInputDate(row.nextEnd);
  if (tradeWindowJob(row.jobName) && row.nextStart && row.nextStart > todayInput()) {
    error.value = "下次开始日期不能超过当天";
    return;
  }
  const lastStart = fromInputDate(row.lastStart);
  const lastEnd = fromInputDate(row.lastEnd);
  if (nextStart && nextEnd && nextEnd < nextStart) {
    error.value = "下次结束日期不能早于开始日期";
    return;
  }
  if (lastStart && lastEnd && lastEnd < lastStart) {
    error.value = "上次结束日期不能早于上次开始日期";
    return;
  }
  let durationMs: number | null = null;
  if (row.durationSeconds.trim()) {
    const seconds = Number(row.durationSeconds);
    if (!Number.isFinite(seconds) || seconds < 0) {
      error.value = "运行时长需要是大于等于 0 的秒数";
      return;
    }
    durationMs = Math.round(seconds * 1000);
  }
  let lastRowCount: number | null = null;
  if (row.rowCount.trim()) {
    const count = Number(row.rowCount);
    if (!Number.isInteger(count) || count < 0) {
      error.value = "写入行数需要是大于等于 0 的整数";
      return;
    }
    lastRowCount = count;
  }
  saving.value = true;
  try {
    await updateScheduleRunState(row.jobId, {
      dateInterval: interval,
      nextStartDate: nextStart,
      nextEndDate: nextEnd,
      lastSuccessStart: lastStart,
      lastSuccessEnd: lastEnd,
      durationMs,
      lastRowCount,
      lastSuccessAt: fromLocalInput(row.successAt),
    });
    editing.value = null;
    emit("saved");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "保存运行状态失败";
    emit("error", error.value);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="table-wrap runs-wrap state-wrap">
    <table v-if="rows.length" class="data state-table">
      <thead>
        <tr>
          <th>任务组</th>
          <th>任务</th>
          <th>日期间隔</th>
          <th>下次开始日期</th>
          <th>下次结束日期</th>
          <th>上次开始日期</th>
          <th>上次结束日期</th>
          <th>运行时长</th>
          <th>写入行数</th>
          <th>上次运行日期</th>
          <th>状态</th>
          <th class="ops">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.jobId">
          <td>{{ row.groupName || "单任务" }}</td>
          <td>
            <button type="button" class="text-btn" @click="emit('select', row.jobId)">{{ row.jobName }}</button>
          </td>
          <td>{{ row.dateInterval }} 天</td>
          <td>{{ showDate(row.nextStartDate) }}</td>
          <td>{{ showDate(row.nextEndDate) }}</td>
          <td>{{ showDate(row.lastSuccessStart) }}</td>
          <td>{{ showDate(row.lastSuccessEnd) }}</td>
          <td>{{ showDuration(row.durationMs) }}</td>
          <td>{{ showCount(row.lastRowCount) }}</td>
          <td>{{ showTime(row.lastSuccessAt) }}</td>
          <td>
            <span v-if="isRunning(row.jobId)" class="run-spin" role="img" aria-label="运行中" title="运行中">
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <circle cx="8" cy="8" r="6" />
                <path d="M8 2a6 6 0 0 1 6 6" />
              </svg>
            </span>
            <span v-else class="run-status" :class="row.lastStatus">{{ statusText(row.lastStatus) }}</span>
          </td>
          <td class="ops">
            <div class="state-ops">
              <button type="button" class="ghost-btn" @click="openEdit(row)">编辑</button>
              <button type="button" class="ghost-btn" :disabled="isRunning(row.jobId)" @click="emit('run', row.jobId)">运行</button>
              <button type="button" class="ghost-btn" @click="emit('detail', row.jobId)">详情</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="pane-empty">还没有任务。</p>
  </div>

  <div v-if="editing" class="modal-backdrop" @click.self="closeEdit">
    <div class="modal state-edit" role="dialog" aria-modal="true" :aria-label="`编辑 ${editing.jobName} 运行状态`">
      <header>
        <strong>编辑运行状态</strong>
        <button type="button" class="icon-btn" aria-label="关闭" @click="closeEdit">×</button>
      </header>
      <div class="form-grid">
        <label>
          <span>任务组</span>
          <input :value="editing.groupName || '单任务'" readonly />
        </label>
        <label>
          <span>任务</span>
          <input :value="editing.jobName" readonly />
        </label>
        <label>
          <span>日期间隔（天，含首尾）</span>
          <input v-model="editing.dateInterval" type="number" min="1" max="20000" step="1" @input="onInterval" />
        </label>
        <label>
          <span>运行时长</span>
          <input :value="editing.durationSeconds ? `${editing.durationSeconds} 秒` : '—'" readonly />
        </label>
        <label>
          <span>下次开始日期</span>
          <input
            v-model="editing.nextStart"
            type="date"
            :max="tradeWindowJob(editing.jobName) ? todayInput() : undefined"
            @change="onNextStart"
          />
        </label>
        <label>
          <span>下次结束日期</span>
          <input v-model="editing.nextEnd" type="date" />
        </label>
        <label>
          <span>上次开始日期</span>
          <input :value="editing.lastStart || '—'" readonly />
        </label>
        <label>
          <span>上次结束日期</span>
          <input :value="editing.lastEnd || '—'" readonly />
        </label>
        <label>
          <span>写入行数</span>
          <input :value="editing.rowCount || '—'" readonly />
        </label>
        <label>
          <span>上次运行日期</span>
          <input :value="editing.successAt ? editing.successAt.replace('T', ' ') : '—'" readonly />
        </label>
      </div>
      <p v-if="editing.jobName === '期货交易日历' || editing.jobName === '期货合约信息'" class="hint">
        修改下次开始日期或日期间隔时，会按日期间隔自动算出下次结束日期。该任务运行时使用调度配置里保存的入参。
      </p>
      <p v-else-if="tradeWindowJob(editing.jobName)" class="hint">
        修改下次开始日期或日期间隔时，会按日期间隔自动算出下次结束日期。下次开始日期不能超过当天。运行时 trade_date 从下次开始日期逐日执行到下次结束日期，每天间隔 3 秒，全部完成后状态变为成功。
      </p>
      <p v-else class="hint">
        修改下次开始日期或日期间隔时，会按日期间隔自动算出下次结束日期。保存后，入参里的开始日期和结束日期会写成下次窗口；没有这两项时，下次开始日期写入入参中的日期。
      </p>
      <p v-if="error" class="hint error">{{ error }}</p>
      <div class="modal-actions">
        <button type="button" class="run-btn" :disabled="saving" @click="save">{{ saving ? "保存中..." : "保存" }}</button>
        <button type="button" class="ghost-btn" :disabled="saving" @click="closeEdit">取消</button>
      </div>
    </div>
  </div>
</template>
