import { TRADE_DATE, findInstrument } from "@/mock/universe";
import type { Bar, Instrument } from "@/types/market";

const cache = new Map<string, Bar[]>();

export function getBars(code: string): Bar[] {
  const cached = cache.get(code);
  if (cached) return cached;
  const quote = findInstrument(code);
  if (!quote) return [];
  const bars = buildBars(quote);
  cache.set(code, bars);
  return bars;
}

function buildBars(quote: Instrument): Bar[] {
  const days = listTradingDays(1100, TRADE_DATE);
  const random = rng(hash(quote.code));
  const last = days.length - 1;
  const closes = new Array<number>(days.length);
  const denominator = 1 + quote.changePct / 100;
  closes[last] = quote.close;
  closes[last - 1] = denominator === 0 ? quote.close : quote.close / denominator;
  for (let index = last - 2; index >= 0; index -= 1) {
    const shock = Math.min(0.035, Math.max(-0.035, (random() - 0.48) * 0.03));
    closes[index] = (closes[index + 1] ?? quote.close) / (1 + shock);
  }

  const openInterest = quote.assetType === "futures" ? buildOpenInterest(quote, days.length, random) : [];
  let factor = 1;
  const bars: Bar[] = [];

  for (let index = 0; index < days.length; index += 1) {
    if (quote.assetType === "stock" && random() < 0.008) factor *= 1.015;
    const close = closes[index] ?? quote.close;
    const prevClose = closes[index - 1] ?? close;
    const open = index === 0 ? close : prevClose * (1 + (random() - 0.5) * 0.01);
    let high = Math.max(open, close) * (1 + random() * 0.008);
    let low = Math.min(open, close) * (1 - random() * 0.008);
    let settlement: number | undefined;
    if (quote.assetType === "futures") {
      settlement = index === last ? quote.settlement : close * (1 + (random() - 0.5) * 0.004);
      high = Math.max(high, settlement, open, close);
      low = Math.min(low, settlement, open, close);
    }
    const roundedOpen = round(open);
    const roundedClose = round(close);
    let roundedHigh = round(high);
    let roundedLow = round(low);
    roundedHigh = Math.max(roundedHigh, roundedOpen, roundedClose);
    roundedLow = Math.min(roundedLow, roundedOpen, roundedClose);
    const amount = index === last ? quote.amount : quote.amount * (0.45 + random() * 0.9);
    const volume =
      quote.assetType === "futures"
        ? Math.round(index === last ? quote.volume : quote.volume * (0.45 + random() * 0.9))
        : Math.round(amount / Math.max(roundedClose, 0.01) / 100);

    bars.push({
      date: days[index] ?? TRADE_DATE,
      open: roundedOpen,
      high: roundedHigh,
      low: roundedLow,
      close: roundedClose,
      volume,
      amount,
      settlement: settlement == null ? undefined : round(settlement),
      openInterest: quote.assetType === "futures" ? Math.round(openInterest[index] ?? 0) : undefined,
      adjFactor: quote.assetType === "futures" ? 1 : Math.round(factor * 10000) / 10000,
    });
  }

  return bars;
}

function buildOpenInterest(quote: Extract<Instrument, { assetType: "futures" }>, length: number, random: () => number) {
  const series = new Array<number>(length);
  const last = length - 1;
  series[last] = quote.openInterest;
  series[last - 1] = Math.max(0, quote.openInterest - quote.openInterestChange);
  for (let index = last - 2; index >= 0; index -= 1) {
    const next = series[index + 1] ?? quote.openInterest;
    series[index] = Math.max(0, next / (1 + (random() - 0.5) * 0.05));
  }
  return series;
}

function listTradingDays(count: number, end: string): string[] {
  const days: string[] = [];
  const cursor = new Date(`${end}T12:00:00`);
  while (days.length < count) {
    const weekday = cursor.getDay();
    if (weekday !== 0 && weekday !== 6) days.push(formatDate(cursor));
    cursor.setDate(cursor.getDate() - 1);
  }
  days.reverse();
  return days;
}

function formatDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function hash(code: string): number {
  let value = 2166136261;
  for (const char of code) value = Math.imul(value ^ char.charCodeAt(0), 16777619);
  return value >>> 0;
}

function rng(seed: number) {
  let state = seed || 1;
  return () => {
    state = (Math.imul(1664525, state) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}
