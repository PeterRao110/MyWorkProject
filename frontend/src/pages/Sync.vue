<script setup lang="ts">
import { ref } from "vue";
import TushareWorkbench from "@/components/sync/TushareWorkbench.vue";

const tab = ref<"tushare" | "akshare">("tushare");
</script>

<template>
  <section>
    <div class="seg">
      <button type="button" :class="{ active: tab === 'tushare' }" @click="tab = 'tushare'">Tushare数据同步</button>
      <button type="button" :class="{ active: tab === 'akshare' }" @click="tab = 'akshare'">AKShare数据同步</button>
    </div>
    <TushareWorkbench v-if="tab === 'tushare'" />
  </section>
</template>
