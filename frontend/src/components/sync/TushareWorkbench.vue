<script setup lang="ts">
import { computed, onMounted, reactive, ref, watchEffect } from "vue";
import { useRouter } from "vue-router";
import ApiTree from "@/components/sync/ApiTree.vue";
import { tushareCatalog } from "@/data/tushareCatalog";
import { getSourceSettings, type SourceSettings } from "@/services/settings";
import { getTushareSchema, queryTushare, type ApiSchema } from "@/services/tushare";

const activeId = ref("135");
const expanded = reactive<Record<string, boolean>>({ "134": true });
const schema = ref<ApiSchema | null>(null);
const loading = ref(false);
const running = ref(false);
const message = ref("");
const messageOk = ref(false);
const source = ref<"rds" | "promax">("promax");
const sources = ref<SourceSettings | null>(null);
const drafts = reactive<Record<string, string>>({});
const checks = reactive<Record<string, Record<string, boolean>>>({});
const columns = ref<string[]>([]);
const rows = ref<string[][]>([]);
const codeOpen = ref(false);
const codeText = ref("");
const copyHint = ref("");
const allBox = ref<HTMLInputElement | null>(null);
const router = useRouter();

const tokenReady = computed(() => Boolean(sources.value?.[source.value].tokenSet));
const fieldState = computed(() => (schema.value ? checks[schema.value.docId] : undefined));
const selectedFields = computed(() => {
  const state = fieldState.value;
  if (!schema.value || !state) return [];
  return schema.value.fields.filter((field) => state[field.name]).map((field) => field.name);
});
const allChecked = computed(
  () => Boolean(schema.value?.fields.length) && selectedFields.value.length === schema.value?.fields.length,
);
const docHref = computed(() => `https://tushare.pro/document/2?doc_id=${activeId.value}`);
const warehouseRule = computed(() => {
  if (schema.value?.apiName !== "fut_wsr") return "";
  if (source.value === "rds") {
    return "Tushare测试接口下 trade_date 和 symbol 不能都为空，填写其中一个即可；start_date、end_date、exchange 可以为空。";
  }
  return "Tushare接口下 trade_date 不能为空；symbol、start_date、end_date、exchange 可以为空。";
});

watchEffect(() => {
  if (!allBox.value || !schema.value) return;
  allBox.value.indeterminate = selectedFields.value.length > 0 && !allChecked.value;
});

onMounted(async () => {
  void loadSchema("135");
  try {
    sources.value = await getSourceSettings();
  } catch {
    sources.value = null;
  }
});

function toggle(id: string) {
  expanded[id] = !expanded[id];
}

function selectApi(id: string) {
  if (activeId.value === id) return;
  activeId.value = id;
  columns.value = [];
  rows.value = [];
  message.value = "";
  void loadSchema(id);
}

async function loadSchema(id: string) {
  loading.value = true;
  schema.value = null;
  try {
    const data = await getTushareSchema(id);
    if (activeId.value !== id) return;
    schema.value = data;
    if (!checks[id]) {
      checks[id] = Object.fromEntries(data.fields.map((field) => [field.name, field.shown]));
    }
  } catch (error) {
    if (activeId.value !== id) return;
    schema.value = null;
    show(error instanceof Error ? error.message : "读取接口说明失败", false);
  } finally {
    if (activeId.value === id) loading.value = false;
  }
}

function draftKey(name: string) {
  return `${activeId.value}:${name}`;
}

function collectParams() {
  const params: Record<string, string> = {};
  for (const param of schema.value?.params ?? []) {
    params[param.name] = (drafts[draftKey(param.name)] || "").trim();
  }
  return params;
}

function paramValue(name: string) {
  return (drafts[draftKey(name)] || "").trim();
}

function validate() {
  if (!schema.value?.apiName) {
    show("请选择可调用的数据接口", false);
    return false;
  }
  for (const param of schema.value.params) {
    if (param.required && !drafts[draftKey(param.name)]?.trim()) {
      show(`${param.name} 必填`, false);
      document.getElementById(`param-${param.name}`)?.focus();
      return false;
    }
  }
  if (schema.value.apiName === "fut_wsr") {
    const tradeDate = paramValue("trade_date");
    const symbol = paramValue("symbol");
    if (source.value === "rds" && !tradeDate && !symbol) {
      show("Tushare测试接口下 trade_date 和 symbol 不能都为空，至少填写一个", false);
      document.getElementById("param-trade_date")?.focus();
      return false;
    }
    if (source.value === "promax" && !tradeDate) {
      show("Tushare接口下 trade_date 不能为空", false);
      document.getElementById("param-trade_date")?.focus();
      return false;
    }
  }
  if (!selectedFields.value.length) {
    show("请至少勾选一列", false);
    return false;
  }
  return true;
}

async function runTest() {
  if (!schema.value || running.value || !validate()) return;
  running.value = true;
  message.value = "";
  try {
    const result = await queryTushare({
      source: source.value,
      apiName: schema.value.apiName,
      params: collectParams(),
      fields: selectedFields.value,
    });
    columns.value = result.fields;
    rows.value = result.items.map((item) => item.map((value) => (value == null ? "" : String(value))));
    show(result.message, result.items.length > 0);
  } catch (error) {
    columns.value = [];
    rows.value = [];
    show(error instanceof Error ? error.message : "查询失败", false);
  } finally {
    running.value = false;
  }
}

function generateCode() {
  if (!schema.value?.apiName) return;
  const args = Object.entries(collectParams())
    .filter(([, value]) => value)
    .map(([key, value]) => `${key}=${JSON.stringify(value)}`);
  if (selectedFields.value.length) args.push(`fields=${JSON.stringify(selectedFields.value.join(","))}`);
  codeText.value = [
    "import tushare as ts",
    "",
    'pro = ts.pro_api("你的token")',
    `df = pro.${schema.value.apiName}(${args.join(", ")})`,
    "",
  ].join("\n");
  copyHint.value = "";
  codeOpen.value = true;
}

async function copyCode() {
  try {
    await navigator.clipboard.writeText(codeText.value);
    copyHint.value = "已复制";
  } catch {
    copyHint.value = "复制失败，请手动选择代码";
  }
}

function exportCsv() {
  if (!rows.value.length || !columns.value.length) {
    show("请先运行测试", false);
    return;
  }
  const lines = [columns.value, ...rows.value].map((line) => line.map(csvCell).join(","));
  const blob = new Blob([`\uFEFF${lines.join("\n")}`], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${schema.value?.apiName || "tushare"}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function csvCell(value: string) {
  return /[",\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value;
}

function toggleAll(event: Event) {
  const state = fieldState.value;
  if (!schema.value || !state) return;
  const checked = (event.target as HTMLInputElement).checked;
  for (const field of schema.value.fields) state[field.name] = checked;
}

function saveAsJob() {
  if (!schema.value?.apiName) return;
  router.push({
    name: "schedule",
    query: {
      create: "1",
      docId: activeId.value,
      source: source.value,
      params: JSON.stringify(collectParams()),
      fields: selectedFields.value.join(","),
    },
  });
}

function show(text: string, ok: boolean) {
  message.value = text;
  messageOk.value = ok;
}
</script>

<template>
  <div class="ts-tool">
    <aside class="ts-side" aria-label="数据接口">
      <ApiTree
        :nodes="tushareCatalog"
        :depth="0"
        :expanded="expanded"
        :active-id="activeId"
        @toggle="toggle"
        @select="selectApi"
      />
    </aside>

    <div class="ts-main">
      <div class="ts-panes">
        <section class="ts-pane" aria-label="入参">
          <div class="pane-title">
            <strong>入参</strong>
            <span>请输入参数值</span>
          </div>
          <p v-if="loading" class="pane-empty">正在读取接口说明</p>
          <p v-else-if="schema && !schema.params.length" class="pane-empty">这个节点没有入参，可以打开详细文档查看。</p>
          <div v-else-if="schema" class="param-list">
            <p v-if="warehouseRule" class="param-rule">{{ warehouseRule }}</p>
            <div v-for="param in schema.params" :key="param.name" class="param-row">
              <span class="param-name">{{ param.name }}<em v-if="param.required">*</em></span>
              <input :id="`param-${param.name}`" v-model="drafts[draftKey(param.name)]" :aria-label="param.name" />
              <span class="param-desc">{{ param.desc }}</span>
            </div>
          </div>
        </section>

        <section class="ts-pane" aria-label="返回">
          <div class="pane-title">
            <strong>返回</strong>
            <span>请勾选需要显示的列</span>
          </div>
          <table v-if="schema && fieldState" class="field-table">
            <thead>
              <tr>
                <th class="check">
                  <input ref="allBox" type="checkbox" aria-label="全选字段" :checked="allChecked" @change="toggleAll" />
                </th>
                <th>字段</th>
                <th>类型</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="field in schema.fields" :key="field.name">
                <td class="check">
                  <input v-model="fieldState[field.name]" type="checkbox" :aria-label="field.name" />
                </td>
                <td>{{ field.name }}</td>
                <td>{{ field.type }}</td>
                <td>{{ field.desc }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else-if="!loading" class="pane-empty">暂无返回字段</p>
        </section>
      </div>

      <div class="tool-actions">
        <label class="tool-source">
          调用接口
          <select v-model="source" aria-label="调用接口">
            <option value="promax">Tushare接口</option>
            <option value="rds">Tushare测试接口</option>
          </select>
        </label>
        <button type="button" class="run-btn" :disabled="running || !schema?.apiName" @click="runTest">
          {{ running ? "查询中..." : "运行测试" }}
        </button>
        <button type="button" class="ghost-btn" :disabled="!schema?.apiName" @click="generateCode">生成代码</button>
        <button type="button" class="ghost-btn" :disabled="!schema?.apiName" @click="saveAsJob">存为定时任务</button>
        <a class="ghost-btn" :href="docHref" target="_blank" rel="noopener noreferrer">详细文档</a>
      </div>
      <p v-if="sources && schema && !tokenReady" class="tool-msg">当前接口还没有保存 Token，运行测试前请到系统设置填写。</p>
      <p v-if="message" class="tool-msg" :class="{ ok: messageOk, error: !messageOk }">{{ message }}</p>

      <div class="result-head">
        <strong>数据表</strong>
        <span v-if="rows.length">{{ rows.length }} 行</span>
        <button type="button" class="link-btn" @click="exportCsv">导出CSV</button>
      </div>
      <div class="result-wrap">
        <table v-if="rows.length" class="result-table">
          <thead>
            <tr>
              <th v-for="column in columns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in rows" :key="index">
              <td v-for="(value, cell) in row" :key="`${index}-${cell}`">{{ value }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-result">
          <svg viewBox="0 0 48 48" aria-hidden="true">
            <rect x="8" y="14" width="32" height="22" rx="3" />
            <path d="M8 20h32M18 14v-4h12v4" />
          </svg>
          <span>暂无数据</span>
        </div>
      </div>
    </div>

    <div v-if="codeOpen" class="modal-backdrop" @click.self="codeOpen = false">
      <div class="modal" role="dialog" aria-label="生成代码">
        <header>
          <strong>生成代码</strong>
          <button type="button" class="icon-btn" aria-label="关闭" @click="codeOpen = false">×</button>
        </header>
        <pre>{{ codeText }}</pre>
        <div class="modal-actions">
          <button type="button" class="run-btn" @click="copyCode">复制</button>
          <span>{{ copyHint }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
