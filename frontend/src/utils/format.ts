export function formatPct(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatPrice(value: number): string {
  if (value >= 10000) return value.toFixed(0);
  if (value >= 1000) return value.toFixed(1);
  return value.toFixed(2);
}

export function formatAmount(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e12) return `${(value / 1e12).toFixed(2)}万亿`;
  if (abs >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
  if (abs >= 1e4) return `${(value / 1e4).toFixed(2)}万`;
  return value.toFixed(0);
}

export function formatVolume(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e8) return `${(value / 1e8).toFixed(2)}亿手`;
  if (abs >= 1e4) return `${(value / 1e4).toFixed(2)}万手`;
  return `${Math.round(value)}手`;
}

export function formatSignedLots(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatVolume(value)}`;
}

export function formatTurnover(value: number): string {
  return `${value.toFixed(2)}%`;
}

export function toneOf(value: number): "up" | "down" | "flat" {
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}
