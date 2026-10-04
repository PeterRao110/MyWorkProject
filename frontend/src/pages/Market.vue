<script setup lang="ts">
import { ref } from "vue";
import FuturesBoard from "@/components/market/FuturesBoard.vue";
import StockBoard from "@/components/market/StockBoard.vue";
import { getMarketStatus } from "@/services/market";

const status = getMarketStatus();
const tab = ref<"stock" | "futures">("stock");
</script>

<template>
  <section>
    <header class="page-head">
      <h1>市场</h1>
      <p v-if="status.complete">示例数据 · 交易日 {{ status.tradeDate }} · 采集完成</p>
      <p v-else>交易日 {{ status.pendingDate }} 采集未完成，当前展示 {{ status.tradeDate }}</p>
    </header>
    <div class="seg">
      <button type="button" :class="{ active: tab === 'stock' }" @click="tab = 'stock'">股票</button>
      <button type="button" :class="{ active: tab === 'futures' }" @click="tab = 'futures'">期货</button>
    </div>
    <p v-if="tab === 'futures'" class="hint">夜盘已计入交易日 {{ status.tradeDate }}，不按自然日切分。</p>
    <div class="board-gap" />
    <StockBoard v-if="tab === 'stock'" />
    <FuturesBoard v-else />
  </section>
</template>
