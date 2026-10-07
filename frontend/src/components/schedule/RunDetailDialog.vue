<script setup lang="ts">
import type { ScheduleGroupRun, ScheduleRun } from "@/services/schedule";

defineProps<{
  title: string;
  summary: ScheduleGroupRun | null;
  calls: ScheduleRun[];
  loading: boolean;
  error: string;
}>();
const emit = defineEmits<{ close: [] }>();

function statusText(status: string) {
  return { success: "成功", failed: "失败", running: "运行中" }[status] || "未运行";
}

function triggerText(trigger: string) {
  return { cron: "定时", manual: "手动", retry: "重跑", group: "任务组", chain: "接续" }[trigger] || trigger;
}

function sourceText(source: string) {
  if (source === "rds") return "Tushare测试接口";
  if (source === "promax") return "Tushare接口";
  return "";
}

function duration(run: { startedAt: string; finishedAt: string }) {
  if (!run.startedAt || !run.finishedAt) return "-";
  const ms = new Date(run.finishedAt.replace(" ", "T")).getTime() - new Date(run.startedAt.replace(" ", "T")).getTime();
  if (Number.isNaN(ms) || ms < 0) return "-";
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function paramEntries(params: Record<string, string>) {
  return Object.entries(params);
}
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal run-detail" role="dialog" aria-modal="true" :aria-label="`${title} 运行详细信息`">
      <header>
        <strong>运行详细信息</strong>
        <button type="button" class="icon-btn" aria-label="关闭" @click="emit('close')">×</button>
      </header>
      <p class="hint">{{ title }}</p>
      <p v-if="loading" class="hint">正在读取本次调用...</p>
      <p v-else-if="error" class="hint error">{{ error }}</p>
      <template v-else>
        <section v-if="summary" class="run-call">
          <h3>运行情况</h3>
          <dl class="job-meta">
            <div>
              <dt>触发</dt>
              <dd>{{ triggerText(summary.triggerType) }}</dd>
            </div>
            <div>
              <dt>状态</dt>
              <dd><span class="run-status" :class="summary.status">{{ statusText(summary.status) }}</span></dd>
            </div>
            <div>
              <dt>开始时间</dt>
              <dd>{{ summary.startedAt || "-" }}</dd>
            </div>
            <div>
              <dt>结束时间</dt>
              <dd>{{ summary.finishedAt || "-" }}</dd>
            </div>
            <div>
              <dt>耗时</dt>
              <dd>{{ duration(summary) }}</dd>
            </div>
            <div class="meta-wide">
              <dt>消息</dt>
              <dd>{{ summary.message || "-" }}</dd>
            </div>
          </dl>
        </section>
        <p v-if="!calls.length && !summary" class="pane-empty">这次运行没有调用记录。</p>
        <p v-else-if="summary && !calls.length" class="hint">这次运行没有调用接口。</p>
        <section v-for="call in calls" :key="call.id" class="run-call">
          <h3>{{ call.jobName || "任务" }}</h3>
          <dl class="job-meta">
            <div>
              <dt>接口</dt>
              <dd>{{ call.apiName || "-" }}<template v-if="sourceText(call.source)">（{{ sourceText(call.source) }}）</template></dd>
            </div>
            <div>
              <dt>返回字段</dt>
              <dd>{{ call.fields.join(", ") || "-" }}</dd>
            </div>
            <div class="meta-wide">
              <dt>实际入参</dt>
              <dd v-if="paramEntries(call.params).length">
                <table class="data param-table">
                  <thead>
                    <tr>
                      <th>参数</th>
                      <th>值</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="[key, value] in paramEntries(call.params)" :key="key">
                      <td>{{ key }}</td>
                      <td>{{ value || "-" }}</td>
                    </tr>
                  </tbody>
                </table>
              </dd>
              <dd v-else>无</dd>
            </div>
            <div>
              <dt>触发</dt>
              <dd>{{ triggerText(call.triggerType) }}</dd>
            </div>
            <div>
              <dt>状态</dt>
              <dd><span class="run-status" :class="call.status">{{ statusText(call.status) }}</span></dd>
            </div>
            <div>
              <dt>开始时间</dt>
              <dd>{{ call.startedAt || "-" }}</dd>
            </div>
            <div>
              <dt>结束时间</dt>
              <dd>{{ call.finishedAt || "-" }}</dd>
            </div>
            <div>
              <dt>耗时</dt>
              <dd>{{ duration(call) }}</dd>
            </div>
            <div>
              <dt>写入行数</dt>
              <dd>{{ call.rowCount }}</dd>
            </div>
            <div class="meta-wide">
              <dt>消息</dt>
              <dd>{{ call.message || "-" }}</dd>
            </div>
          </dl>
        </section>
      </template>
      <div class="modal-actions">
        <button type="button" class="ghost-btn" @click="emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>
