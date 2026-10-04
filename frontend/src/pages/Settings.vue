<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  getDatabaseSettings,
  getSourceSettings,
  saveAkshareSettings,
  saveDatabaseSettings,
  saveTushareSettings,
  testDatabaseSettings,
} from "@/services/settings";

type SectionId = "database" | "akshare" | "tushare";

const sections: { id: SectionId; label: string; desc: string }[] = [
  { id: "database", label: "数据库连接", desc: "保存后写入后端配置文件。密码不会回显，留空表示沿用已保存的密码。" },
  { id: "akshare", label: "AKShare", desc: "保存后写入配置文件。" },
  { id: "tushare", label: "Tushare", desc: "保存后写入配置文件。RDS 和 ProMax 的 Token 不会回显，留空表示沿用已保存的值。" },
];

const active = ref<SectionId>("database");
const current = computed(() => sections.find((item) => item.id === active.value) ?? sections[0]);
const notice = ref("");
const noticeOk = ref(true);
const busy = ref(false);
const passwordSet = ref(false);
const rdsTokenSet = ref(false);
const promaxTokenSet = ref(false);

const db = reactive({
  host: "127.0.0.1",
  port: "3306",
  database: "touyan",
  user: "root",
  password: "",
});

const akshare = reactive({
  enabled: true,
  baseUrl: "https://akshare.akfamily.xyz",
  timeout: "10",
  retry: "3",
});

const rds = reactive({
  token: "",
  baseUrl: "",
  timeout: "10",
  retry: "3",
});

const promax = reactive({
  token: "",
  baseUrl: "",
  timeout: "10",
  retry: "3",
});

onMounted(() => {
  void loadDatabase();
  void loadSources();
});

async function loadDatabase() {
  try {
    const saved = await getDatabaseSettings();
    db.host = saved.host;
    db.port = saved.port;
    db.database = saved.database;
    db.user = saved.user;
    passwordSet.value = saved.passwordSet;
  } catch {
    showNotice("后端未连接，暂时无法读取配置文件", false);
  }
}

function selectSection(id: SectionId) {
  active.value = id;
  notice.value = "";
}

function showNotice(message: string, ok: boolean) {
  notice.value = message;
  noticeOk.value = ok;
}

async function loadSources() {
  try {
    const saved = await getSourceSettings();
    akshare.enabled = saved.akshare.enabled;
    akshare.baseUrl = saved.akshare.baseUrl;
    akshare.timeout = saved.akshare.timeout;
    akshare.retry = saved.akshare.retry;
    rds.baseUrl = saved.rds.baseUrl;
    rds.timeout = saved.rds.timeout;
    rds.retry = saved.rds.retry;
    rdsTokenSet.value = saved.rds.tokenSet;
    promax.baseUrl = saved.promax.baseUrl;
    promax.timeout = saved.promax.timeout;
    promax.retry = saved.promax.retry;
    promaxTokenSet.value = saved.promax.tokenSet;
  } catch {
    showNotice("后端未连接，暂时无法读取配置文件", false);
  }
}

async function save() {
  busy.value = true;
  try {
    if (active.value === "database") {
      if (!validDatabase()) return;
      const result = await saveDatabaseSettings(db);
      passwordSet.value = passwordSet.value || db.password.length > 0;
      db.password = "";
      showNotice(result.message, true);
      return;
    }
    if (active.value === "akshare") {
      if (!validCount(akshare.timeout, akshare.retry)) return;
      const result = await saveAkshareSettings(akshare);
      showNotice(result.message, true);
      return;
    }
    if (!validCount(rds.timeout, rds.retry) || !validCount(promax.timeout, promax.retry)) return;
    const result = await saveTushareSettings({ rds, promax });
    rdsTokenSet.value = rdsTokenSet.value || rds.token.length > 0;
    promaxTokenSet.value = promaxTokenSet.value || promax.token.length > 0;
    rds.token = "";
    promax.token = "";
    showNotice(result.message, true);
  } catch (error) {
    showNotice(error instanceof Error ? error.message : "保存失败", false);
  } finally {
    busy.value = false;
  }
}

async function testConnection() {
  if (!validDatabase()) return;
  busy.value = true;
  try {
    const result = await testDatabaseSettings(db);
    showNotice(result.message, true);
  } catch (error) {
    showNotice(error instanceof Error ? error.message : "连接失败", false);
  } finally {
    busy.value = false;
  }
}

function validCount(timeout: string, retry: string) {
  const timeoutNumber = Number(timeout);
  const retryNumber = Number(retry);
  if (!Number.isInteger(timeoutNumber) || timeoutNumber < 1 || timeoutNumber > 300 || !Number.isInteger(retryNumber) || retryNumber < 0 || retryNumber > 10) {
    showNotice("超时时间为 1 到 300 秒，重试次数为 0 到 10", false);
    return false;
  }
  return true;
}

function validDatabase() {
  const port = Number(db.port);
  if (!db.host.trim() || !db.database.trim() || !db.user.trim() || !Number.isInteger(port) || port < 1 || port > 65535) {
    showNotice("请填写主机、端口、数据库名和用户名", false);
    return false;
  }
  return true;
}
</script>

<template>
  <section class="settings-layout">
    <aside class="submenu" aria-label="系统设置子菜单">
      <p class="submenu-title">系统设置</p>
      <button
        v-for="item in sections"
        :key="item.id"
        type="button"
        class="submenu-link"
        :class="{ active: active === item.id }"
        @click="selectSection(item.id)"
      >
        <svg v-if="item.id === 'database'" class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <ellipse cx="12" cy="6" rx="7" ry="3" />
          <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
          <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
        </svg>
        <svg v-else-if="item.id === 'akshare'" class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M8 6h11" />
          <path d="M8 12h11" />
          <path d="M8 18h11" />
          <path d="M4 6h.01" />
          <path d="M4 12h.01" />
          <path d="M4 18h.01" />
        </svg>
        <svg v-else class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M12 3v4" />
          <path d="M12 17v4" />
          <path d="M3 12h4" />
          <path d="M17 12h4" />
          <circle cx="12" cy="12" r="3" />
        </svg>
        <span>{{ item.label }}</span>
      </button>
    </aside>

    <article class="settings-panel">
      <header class="page-head">
        <h1>{{ current.label }}</h1>
        <p>{{ current.desc }}</p>
      </header>

      <div v-if="active === 'database'" class="form-grid">
        <label>
          <span>主机</span>
          <input v-model="db.host" placeholder="127.0.0.1" />
        </label>
        <label>
          <span>端口</span>
          <input v-model="db.port" placeholder="3306" />
        </label>
        <label>
          <span>数据库名</span>
          <input v-model="db.database" placeholder="touyan" />
        </label>
        <label>
          <span>用户名</span>
          <input v-model="db.user" placeholder="root" />
        </label>
        <label class="wide">
          <span>密码</span>
          <input
            v-model="db.password"
            type="password"
            :placeholder="passwordSet ? '已保存，留空则不修改' : '请输入密码'"
            autocomplete="off"
          />
        </label>
      </div>

      <div v-else-if="active === 'akshare'" class="form-grid">
        <label class="switch wide">
          <input v-model="akshare.enabled" type="checkbox" />
          <span>启用 AKShare</span>
        </label>
        <label class="wide">
          <span>基础地址</span>
          <input v-model="akshare.baseUrl" placeholder="https://akshare.akfamily.xyz" />
        </label>
        <label>
          <span>超时时间（秒）</span>
          <input v-model="akshare.timeout" placeholder="10" />
        </label>
        <label>
          <span>失败重试次数</span>
          <input v-model="akshare.retry" placeholder="3" />
        </label>
      </div>

      <template v-else>
        <section class="settings-block">
          <h2>RDS 接口</h2>
          <div class="form-grid">
            <label class="wide">
              <span>Token</span>
              <input v-model="rds.token" type="password" :placeholder="rdsTokenSet ? '已保存，留空则不修改' : '输入 RDS token'" autocomplete="off" />
            </label>
            <label class="wide">
              <span>接口地址</span>
              <input v-model="rds.baseUrl" placeholder="RDS 接口地址" />
            </label>
            <label>
              <span>超时时间（秒）</span>
              <input v-model="rds.timeout" placeholder="10" />
            </label>
            <label>
              <span>失败重试次数</span>
              <input v-model="rds.retry" placeholder="3" />
            </label>
          </div>
        </section>

        <section class="settings-block">
          <h2>ProMax 接口</h2>
          <div class="form-grid">
            <label class="wide">
              <span>Token</span>
              <input v-model="promax.token" type="password" :placeholder="promaxTokenSet ? '已保存，留空则不修改' : '输入 ProMax token'" autocomplete="off" />
            </label>
            <label class="wide">
              <span>接口地址</span>
              <input v-model="promax.baseUrl" placeholder="ProMax 接口地址" />
            </label>
            <label>
              <span>超时时间（秒）</span>
              <input v-model="promax.timeout" placeholder="10" />
            </label>
            <label>
              <span>失败重试次数</span>
              <input v-model="promax.retry" placeholder="3" />
            </label>
          </div>
        </section>
      </template>

      <div class="settings-actions">
        <button v-if="active === 'database'" class="secondary-btn" type="button" :disabled="busy" @click="testConnection">
          测试连接
        </button>
        <button class="primary-btn" type="button" :disabled="busy" @click="save">保存配置</button>
        <span v-if="notice" class="hint" :class="noticeOk ? 'ok' : 'error'">{{ notice }}</span>
      </div>
    </article>
  </section>
</template>
