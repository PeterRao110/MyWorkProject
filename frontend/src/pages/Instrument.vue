<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import KlineChart from "@/components/KlineChart.vue";
import { useRecent } from "@/composables/useRecent";
import { getDailyBars, getFeatured, getInstrument, getMarketStatus, siblingContracts } from "@/services/market";
import type { AdjustMode, Bar, ChartRange, FuturesQuote, PriceKey } from "@/types/market";
import { formatAmount, formatPct, formatPrice, formatSignedLots, formatTurnover, formatVolume, toneOf } from "@/utils/format";
import { applyAdjust, rangeCount } from "@/utils/series";

const route = useRoute();
const router = useRouter();
const status = getMarketStatus();
const featured = getFeatured();
const { items, push } = useRecent();

const adjust = ref<AdjustMode>("qfq");
const range = ref<ChartRange>("1y");
const showMa = ref(true);
const priceKey = ref<PriceKey>("close");

const code = computed(() => {
  const raw = route.params.code;
  return typeof raw === "string" ? decodeURIComponent(raw) : "";
});
const quote = computed(() => (code.value ? getInstrument(code.value) : null));
const stock = computed(() => (quote.value?.assetType === "stock" ? quote.value : null));
const futures = computed(() => (quote.value?.assetType === "futures" ? quote.value : null));
const siblings = computed(() => (futures.value ? siblingContracts(futures.value.code) : []));
const recent = computed(() => items.value.flatMap((item) => {
  const found = getInstrument(item);
  return found ? [found] : [];
}));
const bars = computed(() => {
  if (!quote.value) return [];
  const mode = quote.value.assetType === "stock" ? adjust.value : "none";
  return applyAdjust(getDailyBars(quote.value.code), mode);
});
const tableRows = computed(() => buildRows(bars.value, futures.value != null));

watch(
  code,
  (value) => {
    if (!value || !getInstrument(value)) return;
    push(value);
    range.value = "1y";
    showMa.value = true;
    priceKey.value = "close";
    adjust.value = getInstrument(value)?.assetType === "futures" ? "none" : "qfq";
  },
  { immediate: true },
);

watch(
  quote,
  (value) => {
    document.title = value ? `${value.name} · 投研` : "研究 · 投研";
  },
  { immediate: true },
);

function onContract(event: Event) {
  const next = (event.target as HTMLSelectElement).value;
  void router.push(`/instrument/${encodeURIComponent(next)}`);
}

function buildRows(series: Bar[], isFutures: boolean) {
  const window = series.slice(-21);
  return window.slice(1).map((bar, index) => {
    const previous = window[index];
    const previousClose = previous?.close ?? bar.close;
    const changePct = previousClose ? ((bar.close - previousClose) / previousClose) * 100 : 0;
    return { bar, changePct, isFutures };
  }).reverse();
}

function contractLabel(item: FuturesQuote) {
  if (item.isContinuous) return "主力连续";
  return `${item.month}${item.isMain ? " · 主力" : ""}`;
}
</script>

<template>
  <section v-if="!code" class="landing">
    <header class="page-head">
      <h1>研究</h1>
      <p>搜索股票、期货合约或品种，查看日线行情。</p>
    </header>
    <div class="landing-grid">
      <div>
        <h2>常用标的</h2>
        <div class="tiles">
          <RouterLink v-for="item in featured" :key="item.code" class="tile" :to="`/instrument/${encodeURIComponent(item.code)}`">
            <span>{{ item.name }}<br /><small>{{ item.code }}</small></span>
            <strong :class="toneOf(item.changePct)">{{ formatPct(item.changePct) }}</strong>
          </RouterLink>
        </div>
      </div>
      <div v-if="recent.length">
        <h2>最近查看</h2>
        <div class="tiles">
          <RouterLink v-for="item in recent" :key="item.code" class="tile" :to="`/instrument/${encodeURIComponent(item.code)}`">
            <span>{{ item.name }}<br /><small>{{ item.code }}</small></span>
            <strong :class="toneOf(item.changePct)">{{ formatPct(item.changePct) }}</strong>
          </RouterLink>
        </div>
      </div>
    </div>
  </section>

  <section v-else-if="!quote" class="card missing">
    <h1>未找到 {{ code }}</h1>
    <p>回到顶部搜索股票代码、名称、期货合约或品种。</p>
  </section>

  <section v-else>
    <article class="card quote">
      <p class="crumb"><RouterLink to="/market">市场</RouterLink> / {{ stock ? "股票" : "期货" }}</p>
      <div class="quote-top">
        <div>
          <h1>{{ quote.name }}</h1>
          <p v-if="stock" class="meta">{{ stock.code }} · {{ stock.industry }} · {{ stock.status }}</p>
          <p v-else-if="futures" class="meta">
            {{ futures.symbol }} · {{ futures.varietyName }} · {{ futures.exchangeName }} · {{ futures.isMain ? "主力" : futures.isContinuous ? "主力连续" : "合约" }}
          </p>
        </div>
        <div>
          <p class="price" :class="toneOf(quote.changePct)">{{ formatPrice(quote.close) }}</p>
          <p :class="toneOf(quote.changePct)">{{ formatPct(quote.changePct) }} · 日线 {{ status.tradeDate }}</p>
        </div>
      </div>
      <div v-if="stock" class="stats">
        <div class="stat"><div class="label">成交额</div><div class="value">{{ formatAmount(stock.amount) }}</div></div>
        <div class="stat"><div class="label">换手率</div><div class="value">{{ formatTurnover(stock.turnover) }}</div></div>
        <div class="stat"><div class="label">总市值</div><div class="value">{{ formatAmount(stock.marketCap) }}</div></div>
        <div class="stat"><div class="label">市盈率</div><div class="value">{{ stock.pe.toFixed(2) }}</div></div>
        <div class="stat"><div class="label">市净率</div><div class="value">{{ stock.pb.toFixed(2) }}</div></div>
      </div>
      <div v-else-if="futures" class="stats">
        <div class="stat"><div class="label">结算价</div><div class="value">{{ formatPrice(futures.settlement) }}</div></div>
        <div class="stat"><div class="label">成交量</div><div class="value">{{ formatVolume(futures.volume) }}</div></div>
        <div class="stat"><div class="label">持仓量</div><div class="value">{{ formatVolume(futures.openInterest) }}</div></div>
        <div class="stat"><div class="label">持仓变化</div><div class="value" :class="toneOf(futures.openInterestChange)">{{ formatSignedLots(futures.openInterestChange) }}</div></div>
      </div>
    </article>

    <section class="card chart-card">
      <div class="controls">
        <div class="seg">
          <button type="button" :class="{ active: range === '1y' }" @click="range = '1y'">近1年</button>
          <button type="button" :class="{ active: range === '3y' }" @click="range = '3y'">近3年</button>
          <button type="button" :class="{ active: range === 'all' }" @click="range = 'all'">{{ stock ? "上市以来" : "全部" }}</button>
        </div>
        <div v-if="stock" class="seg">
          <button type="button" :class="{ active: adjust === 'qfq' }" @click="adjust = 'qfq'">前复权</button>
          <button type="button" :class="{ active: adjust === 'none' }" @click="adjust = 'none'">不复权</button>
        </div>
        <div v-if="futures" class="seg">
          <button type="button" :class="{ active: priceKey === 'close' }" @click="priceKey = 'close'">收盘价</button>
          <button type="button" :class="{ active: priceKey === 'settlement' }" @click="priceKey = 'settlement'">结算价</button>
        </div>
        <div class="seg">
          <button type="button" :class="{ active: showMa }" @click="showMa = !showMa">均线</button>
        </div>
        <label v-if="futures && siblings.length > 1">
          合约
          <select :value="futures.code" @change="onContract">
            <option v-for="item in siblings" :key="item.code" :value="item.code">{{ contractLabel(item) }}</option>
          </select>
        </label>
      </div>
      <KlineChart :bars="bars" :count="rangeCount(range)" :price-key="priceKey" :show-ma="showMa" />
      <p class="hint">红涨绿跌 · {{ stock ? (adjust === "qfq" ? "前复权" : "不复权") : "不复权" }} · 示例日线</p>
    </section>

    <section class="panel" style="margin-top: 16px">
      <div class="panel-head"><h2>近 20 个交易日</h2></div>
      <div class="table-wrap daily-wrap">
        <table class="data">
          <thead>
            <tr>
              <th>日期</th><th>开盘</th><th>最高</th><th>最低</th><th>收盘</th>
              <th v-if="futures">结算</th>
              <th>涨跌幅</th><th>成交量</th>
              <th v-if="stock">成交额</th>
              <th v-if="futures">持仓量</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in tableRows" :key="row.bar.date">
              <td>{{ row.bar.date }}</td>
              <td>{{ formatPrice(row.bar.open) }}</td>
              <td>{{ formatPrice(row.bar.high) }}</td>
              <td>{{ formatPrice(row.bar.low) }}</td>
              <td>{{ formatPrice(row.bar.close) }}</td>
              <td v-if="futures">{{ formatPrice(row.bar.settlement ?? row.bar.close) }}</td>
              <td :class="toneOf(row.changePct)">{{ formatPct(row.changePct) }}</td>
              <td>{{ formatVolume(row.bar.volume) }}</td>
              <td v-if="stock">{{ formatAmount(row.bar.amount) }}</td>
              <td v-if="futures">{{ formatVolume(row.bar.openInterest ?? 0) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
