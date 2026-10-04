import type { AdjustMode, Bar } from "@/types/market";

export function applyAdjust(bars: Bar[], mode: AdjustMode): Bar[] {
  if (mode === "none" || bars.length === 0) return bars;
  const latest = bars[bars.length - 1]?.adjFactor || 1;
  return bars.map((bar) => {
    const ratio = bar.adjFactor / latest;
    return {
      ...bar,
      open: bar.open * ratio,
      high: bar.high * ratio,
      low: bar.low * ratio,
      close: bar.close * ratio,
    };
  });
}

export function movingAverage(values: number[], window: number): Array<number | null> {
  const result: Array<number | null> = [];
  let sum = 0;
  for (let index = 0; index < values.length; index += 1) {
    sum += values[index] ?? 0;
    if (index >= window) sum -= values[index - window] ?? 0;
    result.push(index >= window - 1 ? sum / window : null);
  }
  return result;
}

export function rangeCount(range: "1y" | "3y" | "all"): number | null {
  if (range === "1y") return 245;
  if (range === "3y") return 735;
  return null;
}
