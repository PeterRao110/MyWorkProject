<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { getAuthStatus, login, markSignedIn, setupPassword } from "@/services/auth";

const router = useRouter();
const ready = ref(false);
const configured = ref(false);
const password = ref("");
const confirm = ref("");
const notice = ref("");
const busy = ref(false);

onMounted(async () => {
  document.title = "登录 · 数据分析平台";
  try {
    const status = await getAuthStatus();
    if (status.authenticated) {
      markSignedIn();
      await router.replace("/market");
      return;
    }
    configured.value = status.configured;
    ready.value = true;
  } catch {
    notice.value = "后端未连接，暂时无法登录";
    ready.value = true;
  }
});

async function submit() {
  notice.value = "";
  if (password.value.length < 6) {
    notice.value = "密码至少 6 位";
    return;
  }
  if (!configured.value && password.value !== confirm.value) {
    notice.value = "两次输入的密码不一致";
    return;
  }
  busy.value = true;
  try {
    if (configured.value) await login(password.value);
    else await setupPassword(password.value, confirm.value);
    await router.replace("/market");
  } catch (error) {
    notice.value = error instanceof Error ? error.message : "登录失败";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="login-page">
    <form class="login-card" @submit.prevent="submit">
      <div class="mark">研</div>
      <h1>数据分析平台</h1>
      <p v-if="!ready">正在读取登录状态</p>
      <p v-else-if="configured">请输入登录密码</p>
      <p v-else>首次使用请设置登录密码。密码会加密保存，之后无法查看原文。</p>
      <label>
        <span>登录密码</span>
        <input v-model="password" type="password" autocomplete="current-password" :disabled="!ready || busy" />
      </label>
      <label v-if="ready && !configured">
        <span>确认密码</span>
        <input v-model="confirm" type="password" autocomplete="new-password" :disabled="busy" />
      </label>
      <button class="primary-btn" type="submit" :disabled="!ready || busy">
        {{ configured ? "登录" : "设置并登录" }}
      </button>
      <p v-if="notice" class="hint error">{{ notice }}</p>
    </form>
  </section>
</template>
