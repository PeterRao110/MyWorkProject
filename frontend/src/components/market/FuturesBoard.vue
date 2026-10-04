<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { futuresByExchange, rankFutures } from "@/services/market";
import type { FuturesRank } from "@/types/market";
import { formatAmount, formatPct, formatSignedLots, formatVolume, toneOf } from "@/utils/format";

const router = useRouter();
const groups = futuresByExchange();
const rank = ref<FuturesRank>("gain");
const rows = computed(() => rankFutures(rank.value));
const labels: Record<FuturesRank, string> = { gain: "涨跌幅", oi: "持仓增加", amount: "成交额" };

function open(code: string) {
  void router.push(`/instrument/${encodeURIComponent(code)}`);
}
</script>

<template>
  <div class="stack">
    <section v-for="group in groups" :key="group.exchange" class="panel">
      <div class="panel-head">
        <h2>{{ group.name }}</h2>
        <span class="hint">主力合约</span>
      </div>
      <div class="table-wrap">
        <table class="data">
          <thead>
            <tr><th>合约</th><th>最新</th><th>涨跌幅</th><th>成交量</th><th>持仓量</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in group.contracts" :key="item.code" class="clickable" @click="open(item.code)">
              <td>
                <RouterLink :to="`/instrument/${encodeURIComponent(item.code)}`" @click.stop>{{ item.name }}</RouterLink>
                <div class="hint">{{ item.symbol }}</div>
              </td>
              <td>{{ item.close >= 1000 ? item.close.toFixed(item.close >= 10000 ? 0 : 1) : item.close.toFixed(2) }}</td>
              <td :class="toneOf(item.changePct)">{{ formatPct(item.changePct) }}</td>
              <td>{{ formatVolume(item.volume) }}</td>
              <td>{{ formatVolume(item.openInterest) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>品种排行</h2>
        <div class="seg">
          <button v-for="(label, key) in labels" :key="key" type="button" :class="{ active: rank === key }" @click="rank = key">
            {{ label }}
          </button>
        </div>
      </div>
      <div class="table-wrap">
        <table class="data">
          <thead>
            <tr><th>合约</th><th>涨跌幅</th><th>持仓变化</th><th>成交额</th><th>交易所</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in rows" :key="item.code" class="clickable" @click="open(item.code)">
              <td class="left">{{ item.name }}</td>
              <td :class="toneOf(item.changePct)">{{ formatPct(item.changePct) }}</td>
              <td :class="toneOf(item.openInterestChange)">{{ formatSignedLots(item.openInterestChange) }}</td>
              <td>{{ formatAmount(item.amount) }}</td>
              <td>{{ item.exchangeName }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
