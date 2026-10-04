<script setup lang="ts">
import { BarChart, CandlestickChart, LineChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import type { ECharts, EChartsCoreOption } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { Bar, PriceKey } from "@/types/market";
import { formatPrice, formatVolume } from "@/utils/format";
import { movingAverage } from "@/utils/series";

echarts.use([
  CandlestickChart,
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  LegendComponent,
  CanvasRenderer,
]);

const props = defineProps<{
  bars: Bar[];
  count: number | null;
  priceKey: PriceKey;
  showMa: boolean;
}>();

const el = ref<HTMLElement | null>(null);
let chart: ECharts | null = null;
let observer: ResizeObserver | null = null;

const maLines = [
  { name: "MA5", window: 5, color: "#64748b" },
  { name: "MA10", window: 10, color: "#2563eb" },
  { name: "MA20", window: 20, color: "#7c3aed" },
  { name: "MA60", window: 60, color: "#94a3b8" },
];

function priceOf(bar: Bar) {
  return props.priceKey === "settlement" ? (bar.settlement ?? bar.close) : bar.close;
}

function render() {
  if (!chart) return;
  const start = props.count == null ? 0 : Math.max(0, props.bars.length - props.count);
  const view = props.bars.slice(start);
  const prices = props.bars.map(priceOf);
  const dates = view.map((bar) => bar.date);
  const priceName = props.priceKey === "settlement" ? "结算价" : "收盘价";
  const maSeries = props.showMa
    ? maLines.map((line) => ({
        name: line.name,
        type: "line" as const,
        data: movingAverage(prices, line.window)
          .slice(start)
          .map((value) => value ?? "-"),
        showSymbol: false,
        xAxisIndex: 0,
        yAxisIndex: 0,
        lineStyle: { width: 1, color: line.color },
        itemStyle: { color: line.color },
      }))
    : [];

  const option: EChartsCoreOption = {
    animation: false,
    legend: props.showMa
      ? { top: 0, right: 8, data: [priceName, ...maLines.map((line) => line.name)], textStyle: { color: "#64748b" } }
      : undefined,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter: (raw: unknown) => {
        const rows = Array.isArray(raw) ? raw : [raw];
        const first = rows[0] as { axisValue?: string } | undefined;
        const bar = view.find((item) => item.date === first?.axisValue);
        if (!bar) return "";
        return [
          bar.date,
          `开 ${formatPrice(bar.open)}`,
          `高 ${formatPrice(bar.high)}`,
          `低 ${formatPrice(bar.low)}`,
          `收 ${formatPrice(priceOf(bar))}`,
          `量 ${formatVolume(bar.volume)}`,
        ].join("<br/>");
      },
    },
    grid: [
      { left: 72, right: 16, top: 32, height: "56%" },
      { left: 72, right: 16, top: "74%", height: "12%" },
    ],
    xAxis: [
      { type: "category", data: dates, gridIndex: 0, axisLabel: { show: false }, axisTick: { show: false } },
      { type: "category", data: dates, gridIndex: 1, axisLabel: { color: "#64748b", fontSize: 11 } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0, axisLabel: { color: "#64748b" }, splitLine: { lineStyle: { color: "#e2e8f0" } } },
      { gridIndex: 1, min: 0, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1] },
      { type: "slider", xAxisIndex: [0, 1], bottom: 4, height: 16 },
    ],
    series: [
      {
        name: priceName,
        type: "candlestick",
        data: view.map((bar) => [bar.open, priceOf(bar), bar.low, bar.high]),
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: "#dc2626",
          color0: "#15803d",
          borderColor: "#dc2626",
          borderColor0: "#15803d",
        },
      },
      ...maSeries,
      {
        name: "成交量",
        type: "bar",
        data: view.map((bar) => ({
          value: bar.volume,
          itemStyle: { color: priceOf(bar) >= bar.open ? "#dc2626" : "#15803d" },
        })),
        xAxisIndex: 1,
        yAxisIndex: 1,
      },
    ],
  };
  chart.setOption(option, { notMerge: true });
}

onMounted(() => {
  if (!el.value) return;
  chart = echarts.init(el.value);
  render();
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(el.value);
});

onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});

watch(() => [props.bars, props.count, props.priceKey, props.showMa], render);
</script>

<template>
  <div ref="el" class="chart" />
</template>
