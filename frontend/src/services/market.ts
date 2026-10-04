import { getBars } from "@/mock/bars";
import {
  breadth,
  contracts,
  exchangeOrder,
  featuredCodes,
  findInstrument,
  indices,
  industries,
  marketStatus,
  stocks,
} from "@/mock/universe";
import type {
  FuturesQuote,
  FuturesRank,
  IndustryQuote,
  IndustryRank,
  Instrument,
  StockQuote,
  StockRank,
} from "@/types/market";

export function getMarketStatus() {
  return marketStatus;
}

export function getIndices() {
  return indices;
}

export function getBreadth() {
  return breadth;
}

export function getIndustries() {
  return industries;
}

export function rankIndustries(rank: IndustryRank): IndustryQuote[] {
  const list = [...industries];
  if (rank === "gain") list.sort((a, b) => b.changePct - a.changePct);
  else if (rank === "loss") list.sort((a, b) => a.changePct - b.changePct);
  else list.sort((a, b) => b.amount - a.amount);
  return list.slice(0, 10);
}

export function industryStocks(name: string): StockQuote[] {
  return stocks.filter((item) => item.industry === name).sort((a, b) => b.changePct - a.changePct);
}

export function rankStocks(rank: StockRank): StockQuote[] {
  const list = [...stocks];
  if (rank === "gain") list.sort((a, b) => b.changePct - a.changePct);
  else if (rank === "loss") list.sort((a, b) => a.changePct - b.changePct);
  else if (rank === "turnover") list.sort((a, b) => b.turnover - a.turnover);
  else list.sort((a, b) => b.amount - a.amount);
  return list.slice(0, 50);
}

export function futuresByExchange() {
  return exchangeOrder
    .map((exchange) => ({
      exchange,
      name: contracts.find((item) => item.exchange === exchange)?.exchangeName ?? exchange,
      contracts: contracts.filter((item) => item.exchange === exchange && item.isMain),
    }))
    .filter((group) => group.contracts.length > 0);
}

export function rankFutures(rank: FuturesRank): FuturesQuote[] {
  const list = contracts.filter((item) => item.isMain);
  if (rank === "gain") list.sort((a, b) => b.changePct - a.changePct);
  else if (rank === "oi") list.sort((a, b) => b.openInterestChange - a.openInterestChange);
  else list.sort((a, b) => b.amount - a.amount);
  return list;
}

export function searchInstruments(query: string): Instrument[] {
  const keyword = query.trim().toLowerCase();
  if (!keyword) return [];
  return [...stocks, ...contracts]
    .filter((item) => {
      const extra = item.assetType === "futures" ? `${item.variety} ${item.varietyName} ${item.symbol}` : item.industry;
      return `${item.code} ${item.name} ${extra}`.toLowerCase().includes(keyword);
    })
    .sort((a, b) => score(b, keyword) - score(a, keyword))
    .slice(0, 8);
}

export function getInstrument(code: string): Instrument | null {
  return findInstrument(code) ?? null;
}

export function siblingContracts(code: string): FuturesQuote[] {
  const current = contracts.find((item) => item.code === code);
  if (!current) return [];
  return contracts
    .filter((item) => item.variety === current.variety && item.exchange === current.exchange)
    .sort((a, b) => Number(b.isContinuous) - Number(a.isContinuous) || a.month.localeCompare(b.month));
}

export function getFeatured(): Instrument[] {
  return featuredCodes.flatMap((code) => {
    const item = findInstrument(code);
    return item ? [item] : [];
  });
}

export function getDailyBars(code: string) {
  return getBars(code);
}

function score(item: Instrument, keyword: string): number {
  const code = item.code.toLowerCase();
  const name = item.name.toLowerCase();
  if (code.startsWith(keyword) || name.startsWith(keyword)) return 2;
  return 1;
}
