export type AssetType = "stock" | "futures";

export type Exchange = "CFFEX" | "SHFE" | "DCE" | "CZCE" | "INE" | "GFEX";

export type AdjustMode = "qfq" | "none";

export type PriceKey = "close" | "settlement";

export type StockRank = "gain" | "loss" | "amount" | "turnover";

export type IndustryRank = "gain" | "loss" | "amount";

export type FuturesRank = "gain" | "oi" | "amount";

export type ChartRange = "1y" | "3y" | "all";

export type MarketStatus = {
  tradeDate: string;
  complete: boolean;
  pendingDate: string | null;
};

export type IndexQuote = {
  code: string;
  name: string;
  close: number;
  change: number;
  changePct: number;
  amount: number;
};

export type Breadth = {
  up: number;
  down: number;
  flat: number;
  limitUp: number;
  limitDown: number;
};

export type IndustryQuote = {
  name: string;
  changePct: number;
  amount: number;
};

export type StockQuote = {
  assetType: "stock";
  code: string;
  name: string;
  industry: string;
  status: string;
  close: number;
  changePct: number;
  amount: number;
  turnover: number;
  marketCap: number;
  pe: number;
  pb: number;
};

export type FuturesQuote = {
  assetType: "futures";
  code: string;
  symbol: string;
  name: string;
  variety: string;
  varietyName: string;
  exchange: Exchange;
  exchangeName: string;
  month: string;
  isMain: boolean;
  isContinuous: boolean;
  close: number;
  settlement: number;
  changePct: number;
  volume: number;
  amount: number;
  openInterest: number;
  openInterestChange: number;
};

export type Instrument = StockQuote | FuturesQuote;

export type Bar = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  settlement?: number;
  openInterest?: number;
  adjFactor: number;
};
