<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import ApiTree from "@/components/sync/ApiTree.vue";
import { tushareCatalog } from "@/data/tushareCatalog";
import {
  CRON_PRESETS,
  createScheduleJob,
  updateScheduleJob,
  type ScheduleGroup,
  type ScheduleJob,
  type ScheduleJobInput,
} from "@/services/schedule";
import { getTushareSchema, type ApiSchema } from "@/services/tushare";

export type JobPrefill = {
  docId?: string;
  source?: "rds" | "promax";
  params?: Record<string, string>;
  fields?: string[];
};

const props = defineProps<{
  job?: ScheduleJob | null;
  prefill?: JobPrefill | null;
  groups: ScheduleGroup[];
  initialGroupId?: number | null;
}>();

const emit = defineEmits<{
  close: [];
  saved: [];
}>();

const activeId = ref("");
const expanded = reactive<Record<string, boolean>>({ "134": true });
const schema = ref<ApiSchema | null>(null);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const drafts = reactive<Record<string, string>>({});
const checks = reactive<Record<string, boolean>>({});
const form = reactive({
  name: "",
  source: "promax" as "rds" | "promax",
  scheduleMode: "single" as "single" | "group",
  groupId: null as number | null,
  cron: "0 8 * * *",
  targetTable: "",
  primaryKeysText: "",
  retry: 1,
  timeout: 30,
  enabled: true,
});
const cronPreset = ref("0 8 * * *");
const detailTab = ref<"schedule" | "params" | "fields">("schedule");

const selectedFields = computed(() =>
  schema.value ? schema.value.fields.filter((field) => checks[field.name]).map((field) => field.name) : [],
);
const apiLabel = computed(() => {
  if (schema.value) return `${schema.value.title}（${schema.value.apiName}）`;
  if (loading.value) return "正在读取接口说明";
  return props.job?.apiName ?? "";
});
const filledParamCount = computed(
  () => (schema.value?.params ?? []).filter((param) => (drafts[param.name] || "").trim()).length,
);

watch(
  () => form.scheduleMode,
  (mode) => {
    if (mode !== "group") return;
    const known = props.groups.some((group) => group.id === form.groupId);
    if (!known && props.groups[0]) form.groupId = props.groups[0].id;
  },
);

onMounted(() => {
  if (props.initialGroupId) {
    form.scheduleMode = "group";
    form.groupId = props.initialGroupId;
  }
  if (props.job) {
    const job = props.job;
    form.name = job.name;
    form.source = job.source;
    form.cron = job.cron || "0 8 * * *";
    form.scheduleMode = job.groupId ? "group" : "single";
    form.groupId = job.groupId;
    form.targetTable = job.targetTable;
    form.primaryKeysText = job.primaryKeys.join(",");
    form.retry = job.retry;
    form.timeout = job.timeout;
    form.enabled = job.enabled;
    cronPreset.value = CRON_PRESETS.some((item) => item.value === job.cron) ? job.cron : job.cron ? "" : "0 8 * * *";
    activeId.value = job.docId;
    void loadSchema(job.docId, () => {
      Object.assign(drafts, job.params);
      if (job.name === "期货交易日历") drafts.end_date = job.params.end_date || "";
      for (const field of schema.value?.fields ?? []) checks[field.name] = job.fields.includes(field.name);
    });
    return;
  }
  const docId = props.prefill?.docId;
  if (props.prefill && docId) {
    const prefill = props.prefill;
    if (prefill.source) form.source = prefill.source;
    activeId.value = docId;
    void loadSchema(docId, () => {
      Object.assign(drafts, prefill.params ?? {});
      const wanted = new Set(prefill.fields ?? []);
      if (wanted.size) {
        for (const field of schema.value?.fields ?? []) checks[field.name] = wanted.has(field.name);
      }
      if (schema.value) {
        form.name = form.name || schema.value.title;
        form.targetTable = form.targetTable || schema.value.apiName;
      }
    });
  }
});

function toggle(id: string) {
  expanded[id] = !expanded[id];
}

function selectApi(id: string) {
  if (loading.value) return;
  activeId.value = id;
  void loadSchema(id, () => {
    if (!props.job && schema.value) {
      form.name = form.name || schema.value.title;
      form.targetTable = schema.value.apiName;
    }
  });
}

async function loadSchema(id: string, after?: () => void) {
  loading.value = true;
  schema.value = null;
  error.value = "";
  try {
    const data = await getTushareSchema(id);
    if (activeId.value !== id) return;
    schema.value = data;
    for (const param of data.params) {
      if (!(param.name in drafts)) drafts[param.name] = "";
    }
    for (const field of data.fields) {
      if (!(field.name in checks)) checks[field.name] = field.shown;
    }
    after?.();
  } catch (err) {
    if (activeId.value !== id) return;
    error.value = err instanceof Error ? err.message : "读取接口说明失败";
  } finally {
    if (activeId.value === id) loading.value = false;
  }
}

function collectParams() {
  const params: Record<string, string> = { ...(props.job?.params ?? {}) };
  const known = new Set((schema.value?.params ?? []).map((param) => param.name));
  for (const key of Object.keys(params)) {
    if (known.has(key)) delete params[key];
  }
  for (const param of schema.value?.params ?? []) {
    const value = (drafts[param.name] || "").trim();
    if (value) params[param.name] = value;
  }
  return params;
}

function showRequired(name: string, required: boolean) {
  if (!required) return false;
  return !(props.job?.name === "期货合约信息" && name === "exchange");
}

async function save() {
  error.value = "";
  if (!form.name.trim()) {
    detailTab.value = "schedule";
    error.value = "请填写任务名称";
    return;
  }
  if (!schema.value?.apiName) {
    detailTab.value = "schedule";
    error.value = props.job ? "接口说明尚未载入，请稍后重试" : "请在左侧选择数据接口";
    return;
  }
  const inGroup = form.scheduleMode === "group";
  if (inGroup && !form.groupId) {
    detailTab.value = "schedule";
    error.value = props.groups.length ? "请选择任务组" : "请先新建任务组";
    return;
  }
  const cron = (cronPreset.value || form.cron).trim();
  if (!inGroup && !cron) {
    detailTab.value = "schedule";
    error.value = "请填写 cron 表达式";
    return;
  }
  if (!selectedFields.value.length) {
    detailTab.value = "fields";
    error.value = "请至少勾选一列";
    return;
  }
  const primaryKeys = form.primaryKeysText
    .split(/[,，\s]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  const payload: ScheduleJobInput = {
    name: form.name.trim(),
    docId: activeId.value,
    apiName: schema.value.apiName,
    source: form.source,
    params: collectParams(),
    fields: selectedFields.value,
    cron: inGroup ? form.cron.trim() : cron,
    targetTable: (form.targetTable || schema.value.apiName).trim(),
    primaryKeys,
    retry: Number(form.retry) || 0,
    timeout: Number(form.timeout) || 30,
    groupId: inGroup ? form.groupId : null,
    enabled: form.enabled,
  };
  saving.value = true;
  try {
    if (props.job) {
      await updateScheduleJob(props.job.id, payload);
    } else {
      await createScheduleJob(payload);
    }
    emit("saved");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "保存失败";
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal job-modal" role="dialog" aria-label="定时任务">
      <header>
        <strong>{{ job ? "编辑任务" : "新建任务" }}</strong>
        <button type="button" class="icon-btn" aria-label="关闭" @click="emit('close')">×</button>
      </header>
      <div class="job-modal-body" :class="{ editing: job }">
        <aside v-if="!job" class="job-modal-tree" aria-label="数据接口">
          <ApiTree
            :nodes="tushareCatalog"
            :depth="0"
            :expanded="expanded"
            :active-id="activeId"
            @toggle="toggle"
            @select="selectApi"
          />
        </aside>
        <div class="job-modal-form">
          <div class="job-tabs" role="tablist" aria-label="任务配置">
            <button type="button" role="tab" :class="{ active: detailTab === 'schedule' }" :aria-selected="detailTab === 'schedule'" @click="detailTab = 'schedule'">
              调度配置
            </button>
            <button type="button" role="tab" :class="{ active: detailTab === 'params' }" :aria-selected="detailTab === 'params'" @click="detailTab = 'params'">
              入参
              <em v-if="schema">{{ filledParamCount }}/{{ schema.params.length }}</em>
            </button>
            <button type="button" role="tab" :class="{ active: detailTab === 'fields' }" :aria-selected="detailTab === 'fields'" @click="detailTab = 'fields'">
              返回字段
              <em v-if="schema">{{ selectedFields.length }}/{{ schema.fields.length }}</em>
            </button>
          </div>
          <div class="job-tab-panel" role="tabpanel">
          <div v-show="detailTab === 'schedule'">
          <div class="form-grid">
            <label v-if="job" class="wide">
              <span>数据接口</span>
              <input :value="apiLabel" readonly />
            </label>
            <label>
              <span>任务名称</span>
              <input v-model="form.name" placeholder="例如：A股日线" />
            </label>
            <label>
              <span>调用源</span>
              <select v-model="form.source">
                <option value="promax">Tushare接口</option>
                <option value="rds">Tushare测试接口</option>
              </select>
            </label>
            <div class="wide">
              <span>调度方式</span>
              <div class="schedule-mode">
                <label class="choice">
                  <input v-model="form.scheduleMode" type="radio" value="single" />
                  单独调度
                </label>
                <label class="choice">
                  <input v-model="form.scheduleMode" type="radio" value="group" />
                  加入任务组
                </label>
              </div>
            </div>
            <label v-if="form.scheduleMode === 'group'">
              <span>任务组</span>
              <select v-model.number="form.groupId" :disabled="!groups.length">
                <option v-for="group in groups" :key="group.id" :value="group.id">{{ group.name }}</option>
              </select>
            </label>
            <template v-if="form.scheduleMode === 'single'">
              <label>
                <span>执行频率</span>
                <select v-model="cronPreset">
                  <option v-for="item in CRON_PRESETS" :key="item.value" :value="item.value">{{ item.label }}</option>
                  <option value="">自定义</option>
                </select>
              </label>
              <label v-if="cronPreset === ''">
                <span>cron 表达式（分 时 日 月 星期，0 或 7 表示周日）</span>
                <input v-model="form.cron" placeholder="0 8 * * *" />
              </label>
            </template>
            <label>
              <span>目标表（tusharedata 库）</span>
              <input v-model="form.targetTable" placeholder="默认同接口名" />
            </label>
            <label>
              <span>业务主键（逗号分隔，留空则按调用源全量替换）</span>
              <input v-model="form.primaryKeysText" placeholder="ts_code,trade_date" />
            </label>
            <label>
              <span>失败重试次数</span>
              <input v-model.number="form.retry" type="number" min="0" max="5" />
            </label>
            <label>
              <span>超时秒数</span>
              <input v-model.number="form.timeout" type="number" min="1" max="300" />
            </label>
            <label class="switch">
              <input v-model="form.enabled" type="checkbox" />
              <span>启用</span>
            </label>
          </div>
          <p v-if="form.scheduleMode === 'group'" class="hint">
            加入任务组后按该组的执行频率运行，先后顺序在任务组详情里调整。
          </p>
          <p v-else class="hint">单独调度按上面的 cron 运行，不参与任务组顺序。</p>
          </div>

          <div v-show="detailTab === 'params'">
            <p class="hint">
              入参支持占位符 ${today}、${yesterday}、${trade_date}、${last_trade_date}；值中用逗号分隔多个值会逐个执行后合并写入。
            </p>
            <template v-if="schema">
              <div class="pane-title">
                <strong>{{ schema.title }}</strong>
                <span>{{ schema.apiName }}</span>
              </div>
              <p v-if="!schema.params.length" class="pane-empty">这个接口没有入参。</p>
              <div v-for="param in schema.params" :key="param.name" class="param-row">
                <span class="param-name">{{ param.name }}<em v-if="showRequired(param.name, param.required)">*</em></span>
                <input v-model="drafts[param.name]" :aria-label="param.name" />
                <span class="param-desc">{{ param.desc }}</span>
              </div>
            </template>
            <p v-else-if="loading" class="pane-empty">正在读取接口说明</p>
            <p v-else class="pane-empty">请先在左侧选择数据接口。</p>
          </div>

          <div v-show="detailTab === 'fields'">
            <template v-if="schema">
              <div class="pane-title">
                <strong>返回字段</strong>
                <span>已选 {{ selectedFields.length }} / {{ schema.fields.length }}</span>
              </div>
              <table class="field-table">
                <thead>
                  <tr>
                    <th class="check"></th>
                    <th>字段</th>
                    <th>类型</th>
                    <th>说明</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="field in schema.fields" :key="field.name">
                    <td class="check">
                      <input v-model="checks[field.name]" type="checkbox" :aria-label="field.name" />
                    </td>
                    <td>{{ field.name }}</td>
                    <td>{{ field.type }}</td>
                    <td>{{ field.desc }}</td>
                  </tr>
                </tbody>
              </table>
            </template>
            <p v-else-if="loading" class="pane-empty">正在读取接口说明</p>
            <p v-else class="pane-empty">请先在左侧选择数据接口。</p>
          </div>
          </div>

          <p v-if="error" class="hint error">{{ error }}</p>
          <div class="modal-actions">
            <button type="button" class="run-btn" :disabled="saving" @click="save">
              {{ saving ? "保存中..." : "保存任务" }}
            </button>
            <button type="button" class="ghost-btn" @click="emit('close')">取消</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
