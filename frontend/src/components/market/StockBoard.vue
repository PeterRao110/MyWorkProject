<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { getBreadth, getIndices, industryStocks, rankIndustries, rankStocks } from "@/services/market";
import type { IndustryRank, StockRank } from "@/types/market";
import { formatAmount, formatPct, formatTurnover, toneOf } from "@/utils/format";

const router = useRouter();
const indices = getIndices();
const breadth = getBreadth();
const industryRank = ref<IndustryRank>("gain");
const stockRank = ref<StockRank>("gain");
const selectedIndustry = ref("");

const industries = computed(() => rankIndustries(industryRank.value));
const stocks = computed(() => rankStocks(stockRank.value));
const members = computed(() => (selectedIndustry.value ? industryStocks(selectedIndustry.value) : []));
const total = breadth.up + breadth.down + breadth.flat;

const industryLabels: Record<IndustryRank, string> = { gain: "涨幅", loss: "跌幅", amount: "成交额" };
const stockLabels: Record<StockRank, string> = { gain: "涨幅", loss: "跌幅", amount: "成交额", turnover: "换手率" };

function open(code: string) {
  void router.push(`/instrument/${encodeURIComponent(code)}`);
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") selectedIndustry.value = "";
}

watch(selectedIndustry, (value) => {
  if (value) window.addEventListener("keydown", onKeydown);
  else window.removeEventListener("keydown", onKeydown);
});

onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>

<template>
  <div>
    <div class="index-row">
      <article v-for="item in indices" :key="item.code" class="card">
        <span class="label">{{ item.name }}</span>
        <strong>{{ item.close.toFixed(2) }}</strong>
        <span class="move" :class="toneOf(item.changePct)">{{ item.change > 0 ? "+" : "" }}{{ item.change.toFixed(2) }} {{ formatPct(item.changePct) }}</span>
        <em>成交额 {{ formatAmount(item.amount) }}</em>
      </article>
    </div>

    <section class="card breadth">
      <div class="breadth-top">
        <h2>涨跌家数</h2>
        <div class="chips">
          <span class="chip up">涨停 {{ breadth.limitUp }}</span>
          <span class="chip down">跌停 {{ breadth.limitDown }}</span>
        </div>
      </div>
      <div class="breadth-bar" aria-hidden="true">
        <span class="up" :style="{ flex: breadth.up }" />
        <span class="flat" :style="{ flex: breadth.flat }" />
        <span class="down" :style="{ flex: breadth.down }" />
      </div>
      <p class="hint">上涨 {{ breadth.up }} · 平盘 {{ breadth.flat }} · 下跌 {{ breadth.down }} · 合计 {{ total }}</p>
    </section>

    <div class="split">
      <section class="panel">
        <div class="panel-head">
          <h2>行业</h2>
          <div class="seg">
            <button v-for="(label, key) in industryLabels" :key="key" type="button" :class="{ active: industryRank === key }" @click="industryRank = key">
              {{ label }}
            </button>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data">
            <thead>
              <tr><th>行业</th><th>涨跌幅</th><th>成交额</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in industries" :key="item.name" class="clickable" :class="{ selected: selectedIndustry === item.name }" @click="selectedIndustry = item.name">
                <td><button type="button" class="text-btn" @click="selectedIndustry = item.name">{{ item.name }}</button></td>
                <td :class="toneOf(item.changePct)">{{ formatPct(item.changePct) }}</td>
                <td>{{ formatAmount(item.amount) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>个股</h2>
          <div class="seg">
            <button v-for="(label, key) in stockLabels" :key="key" type="button" :class="{ active: stockRank === key }" @click="stockRank = key">
              {{ label }}
            </button>
          </div>
        </div>
        <div class="table-wrap">
          <table class="data">
            <thead>
              <tr><th>名称</th><th>涨跌幅</th><th>成交额</th><th>换手率</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in stocks" :key="item.code" class="clickable" @click="open(item.code)">
                <td>
                  <RouterLink :to="`/instrument/${encodeURIComponent(item.code)}`" @click.stop>{{ item.name }}</RouterLink>
                  <div class="hint">{{ item.code }} · {{ item.industry }}</div>
                </td>
                <td :class="toneOf(item.changePct)">{{ formatPct(item.changePct) }}</td>
                <td>{{ formatAmount(item.amount) }}</td>
                <td>{{ formatTurnover(item.turnover) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <div v-if="selectedIndustry" class="drawer-backdrop" @click="selectedIndustry = ''" />
    <aside v-if="selectedIndustry" class="drawer" aria-label="行业成分股">
      <div class="panel-head">
        <h2>{{ selectedIndustry }}</h2>
        <button class="icon-btn" type="button" @click="selectedIndustry = ''">关闭</button>
      </div>
      <p class="hint">示例成分 {{ members.length }} 只</p>
      <table class="data">
        <thead>
          <tr><th>名称</th><th>涨跌幅</th><th>成交额</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in members" :key="item.code" class="clickable" @click="open(item.code)">
            <td class="left">{{ item.name }}</td>
            <td :class="toneOf(item.changePct)">{{ formatPct(item.changePct) }}</td>
            <td>{{ formatAmount(item.amount) }}</td>
          </tr>
        </tbody>
      </table>
    </aside>
  </div>
</template>
