import type {
  Breadth,
  Exchange,
  FuturesQuote,
  IndexQuote,
  IndustryQuote,
  Instrument,
  MarketStatus,
  StockQuote,
} from "@/types/market";

export const TRADE_DATE = "2026-10-02";

export const marketStatus: MarketStatus = {
  tradeDate: TRADE_DATE,
  complete: true,
  pendingDate: null,
};

export const indices: IndexQuote[] = [
  { code: "000001.SH", name: "上证指数", close: 3286.42, change: 18.55, changePct: 0.57, amount: 5.42e11 },
  { code: "399001.SZ", name: "深证成指", close: 10452.18, change: -36.2, changePct: -0.35, amount: 6.18e11 },
  { code: "399006.SZ", name: "创业板指", close: 2184.66, change: 12.4, changePct: 0.57, amount: 2.31e11 },
  { code: "000300.SH", name: "沪深300", close: 4022.15, change: 15.8, changePct: 0.39, amount: 3.05e11 },
  { code: "000905.SH", name: "中证500", close: 5840.22, change: -21.4, changePct: -0.37, amount: 1.62e11 },
  { code: "000852.SH", name: "中证1000", close: 6124.08, change: 8.6, changePct: 0.14, amount: 1.48e11 },
];

export const breadth: Breadth = {
  up: 2816,
  down: 2144,
  flat: 186,
  limitUp: 52,
  limitDown: 9,
};

export const industries: IndustryQuote[] = [
  { name: "有色金属", changePct: 2.64, amount: 680e8 },
  { name: "电力设备", changePct: 1.92, amount: 860e8 },
  { name: "食品饮料", changePct: 1.48, amount: 740e8 },
  { name: "计算机", changePct: 1.21, amount: 180e8 },
  { name: "汽车", changePct: 0.86, amount: 490e8 },
  { name: "电子", changePct: 0.64, amount: 920e8 },
  { name: "医药", changePct: 0.41, amount: 520e8 },
  { name: "通信", changePct: 0.22, amount: 380e8 },
  { name: "家电", changePct: 0.05, amount: 360e8 },
  { name: "非银金融", changePct: -0.08, amount: 430e8 },
  { name: "交通运输", changePct: -0.18, amount: 220e8 },
  { name: "银行", changePct: -0.36, amount: 640e8 },
  { name: "公用事业", changePct: -0.42, amount: 300e8 },
  { name: "基础化工", changePct: -0.55, amount: 240e8 },
  { name: "石油石化", changePct: -0.73, amount: 340e8 },
  { name: "建筑材料", changePct: -0.91, amount: 110e8 },
  { name: "农林牧渔", changePct: -1.12, amount: 140e8 },
  { name: "煤炭", changePct: -1.46, amount: 260e8 },
  { name: "商贸零售", changePct: -1.88, amount: 90e8 },
  { name: "房地产", changePct: -2.35, amount: 160e8 },
];

function stock(
  code: string,
  name: string,
  industry: string,
  close: number,
  changePct: number,
  amountYi: number,
  turnover: number,
  capYi: number,
  pe: number,
  pb: number,
): StockQuote {
  return {
    assetType: "stock",
    code,
    name,
    industry,
    status: "上市",
    close,
    changePct,
    amount: amountYi * 1e8,
    turnover,
    marketCap: capYi * 1e8,
    pe,
    pb,
  };
}

export const stocks: StockQuote[] = [
  stock("600519.SH", "贵州茅台", "食品饮料", 1486.2, 1.24, 68, 0.28, 186800, 22.6, 7.9),
  stock("000858.SZ", "五粮液", "食品饮料", 128.4, -0.62, 32, 0.71, 4980, 16.2, 3.4),
  stock("000568.SZ", "泸州老窖", "食品饮料", 142.6, 0.84, 18, 0.66, 2090, 15.4, 4.1),
  stock("600809.SH", "山西汾酒", "食品饮料", 186.3, 1.52, 22, 0.92, 2270, 18.8, 6.2),
  stock("002304.SZ", "洋河股份", "食品饮料", 78.4, -1.16, 11, 0.54, 1180, 12.6, 2.4),
  stock("600887.SH", "伊利股份", "食品饮料", 28.6, 0.35, 19, 0.48, 1820, 14.1, 3.6),
  stock("300750.SZ", "宁德时代", "电力设备", 248.5, 2.18, 96, 0.88, 10920, 21.5, 4.8),
  stock("300274.SZ", "阳光电源", "电力设备", 98.2, 6.42, 54, 3.26, 2040, 18.4, 4.2),
  stock("601012.SH", "隆基绿能", "电力设备", 16.8, -4.76, 38, 2.14, 1270, 11.2, 1.6),
  stock("002594.SZ", "比亚迪", "汽车", 312.4, 1.08, 72, 0.96, 9080, 24.6, 5.1),
  stock("601633.SH", "长城汽车", "汽车", 26.4, 2.46, 15, 1.22, 2260, 16.8, 2.2),
  stock("600104.SH", "上汽集团", "汽车", 16.2, -2.24, 12, 0.42, 1860, 8.4, 0.7),
  stock("601127.SH", "赛力斯", "汽车", 128.6, 5.36, 41, 4.18, 1940, 32.5, 8.6),
  stock("002475.SZ", "立讯精密", "电子", 42.8, 1.64, 48, 1.36, 3080, 19.2, 4.4),
  stock("688981.SH", "中芯国际", "电子", 86.4, 0.92, 62, 1.84, 6880, 48.6, 3.2),
  stock("002371.SZ", "北方华创", "电子", 412.5, 3.15, 36, 1.58, 2180, 36.4, 8.1),
  stock("603501.SH", "韦尔股份", "电子", 112.3, -0.48, 14, 1.12, 1350, 28.4, 4.6),
  stock("600276.SH", "恒瑞医药", "医药", 48.6, 0.72, 22, 0.58, 3100, 42.8, 6.4),
  stock("300760.SZ", "迈瑞医疗", "医药", 268.2, -0.36, 18, 0.44, 3250, 28.6, 7.2),
  stock("000538.SZ", "云南白药", "医药", 56.8, 0.18, 8, 0.32, 1020, 18.4, 2.8),
  stock("600436.SH", "片仔癀", "医药", 214.6, 1.86, 9, 0.66, 1290, 34.2, 6.8),
  stock("601318.SH", "中国平安", "非银金融", 52.4, -0.22, 46, 0.38, 9560, 9.6, 1.1),
  stock("600036.SH", "招商银行", "银行", 38.6, 0.14, 28, 0.22, 9740, 6.8, 0.9),
  stock("601398.SH", "工商银行", "银行", 6.42, -0.46, 18, 0.08, 22900, 5.4, 0.5),
  stock("600030.SH", "中信证券", "非银金融", 28.4, 0.96, 36, 0.84, 4220, 14.2, 1.4),
  stock("601688.SH", "华泰证券", "非银金融", 18.2, 1.28, 22, 1.06, 1640, 12.6, 1.2),
  stock("600900.SH", "长江电力", "公用事业", 28.1, -0.28, 24, 0.18, 6860, 18.6, 3.1),
  stock("601985.SH", "中国核电", "公用事业", 9.24, -0.64, 11, 0.26, 1760, 16.4, 1.6),
  stock("600028.SH", "中国石化", "石油石化", 6.18, -1.84, 15, 0.16, 7440, 9.2, 0.8),
  stock("601857.SH", "中国石油", "石油石化", 8.46, -2.62, 19, 0.14, 15460, 8.6, 0.9),
  stock("601088.SH", "中国神华", "煤炭", 38.2, -1.12, 16, 0.28, 7600, 11.4, 1.5),
  stock("601225.SH", "陕西煤业", "煤炭", 22.6, -1.74, 12, 0.36, 2190, 8.8, 1.3),
  stock("600309.SH", "万华化学", "基础化工", 72.4, 0.54, 20, 0.48, 2270, 13.6, 2.6),
  stock("002648.SZ", "卫星化学", "基础化工", 18.4, -0.92, 7, 0.62, 620, 10.4, 1.8),
  stock("600585.SH", "海螺水泥", "建筑材料", 24.2, -0.84, 9, 0.34, 1280, 7.6, 0.7),
  stock("000002.SZ", "万科A", "房地产", 6.84, -3.92, 14, 1.46, 760, 12.4, 0.5),
  stock("600048.SH", "保利发展", "房地产", 8.12, -2.18, 8, 0.72, 970, 8.2, 0.6),
  stock("000333.SZ", "美的集团", "家电", 72.8, 0.22, 26, 0.46, 5080, 13.2, 2.8),
  stock("000651.SZ", "格力电器", "家电", 42.6, -0.18, 14, 0.32, 2390, 8.4, 1.8),
  stock("601888.SH", "中国中免", "商贸零售", 68.4, -2.46, 11, 0.88, 1420, 18.6, 3.2),
  stock("002352.SZ", "顺丰控股", "交通运输", 42.2, 0.64, 9, 0.28, 2060, 16.8, 2.4),
  stock("601919.SH", "中远海控", "交通运输", 15.6, -1.08, 13, 0.54, 2420, 7.2, 1.2),
  stock("002714.SZ", "牧原股份", "农林牧渔", 42.8, -1.36, 10, 0.66, 2340, 9.4, 2.6),
  stock("002230.SZ", "科大讯飞", "计算机", 52.4, 3.58, 24, 2.42, 1210, 48.2, 6.4),
  stock("600941.SH", "中国移动", "通信", 108.6, 0.16, 18, 0.12, 23500, 12.4, 1.4),
  stock("000063.SZ", "中兴通讯", "通信", 34.2, 1.42, 22, 1.18, 1630, 15.6, 2.2),
  stock("601899.SH", "紫金矿业", "有色金属", 18.6, 2.84, 48, 1.26, 4880, 14.8, 3.6),
  stock("603993.SH", "洛阳钼业", "有色金属", 8.42, 3.26, 26, 2.08, 1810, 12.2, 2.8),
  stock("002460.SZ", "赣锋锂业", "有色金属", 42.6, 4.18, 32, 3.42, 860, 22.4, 2.2),
  stock("600111.SH", "北方稀土", "有色金属", 24.8, 4.86, 21, 2.96, 890, 28.6, 4.4),
];

export const exchangeName: Record<Exchange, string> = {
  CFFEX: "中金所",
  SHFE: "上期所",
  DCE: "大商所",
  CZCE: "郑商所",
  INE: "能源中心",
  GFEX: "广期所",
};

export const exchangeOrder: Exchange[] = ["CFFEX", "SHFE", "DCE", "CZCE", "INE", "GFEX"];

const suffix: Record<Exchange, string> = {
  CFFEX: "CFX",
  SHFE: "SHF",
  DCE: "DCE",
  CZCE: "ZCE",
  INE: "INE",
  GFEX: "GFE",
};

function future(
  symbol: string,
  variety: string,
  varietyName: string,
  exchange: Exchange,
  month: string,
  close: number,
  settlement: number,
  changePct: number,
  volume: number,
  amountYi: number,
  openInterest: number,
  openInterestChange: number,
  flags: { main?: boolean; continuous?: boolean } = {},
): FuturesQuote {
  const continuous = flags.continuous ?? false;
  const main = flags.main ?? false;
  return {
    assetType: "futures",
    code: `${symbol}.${suffix[exchange]}`,
    symbol,
    name: continuous ? `${varietyName}主力连续` : `${varietyName} ${month}`,
    variety,
    varietyName,
    exchange,
    exchangeName: exchangeName[exchange],
    month: continuous ? "连续" : month,
    isMain: main,
    isContinuous: continuous,
    close,
    settlement,
    changePct,
    volume,
    amount: amountYi * 1e8,
    openInterest,
    openInterestChange,
  };
}

export const contracts: FuturesQuote[] = [
  future("IF2610", "IF", "沪深300", "CFFEX", "2610", 4022, 4018, 0.42, 98000, 186, 142000, 8600, { main: true }),
  future("IF2612", "IF", "沪深300", "CFFEX", "2612", 4008, 4004, 0.36, 42000, 72, 68000, 2100),
  future("IF9999", "IF", "沪深300", "CFFEX", "连续", 4022, 4018, 0.42, 98000, 186, 142000, 8600, { continuous: true }),
  future("IH2610", "IH", "上证50", "CFFEX", "2610", 2684, 2681, 0.28, 54000, 64, 82000, 1800, { main: true }),
  future("IC2610", "IC", "中证500", "CFFEX", "2610", 5846, 5838, -0.34, 72000, 118, 156000, -4200, { main: true }),
  future("IM2610", "IM", "中证1000", "CFFEX", "2610", 6132, 6124, 0.18, 88000, 142, 198000, 5600, { main: true }),
  future("T2512", "T", "十年国债", "CFFEX", "2512", 108.42, 108.39, 0.06, 64000, 28, 186000, 2400, { main: true }),
  future("rb2601", "rb", "螺纹钢", "SHFE", "2601", 3284, 3288, 1.16, 1820000, 920, 2410000, 32600, { main: true }),
  future("rb2605", "rb", "螺纹钢", "SHFE", "2605", 3246, 3250, 0.92, 640000, 280, 860000, 8400),
  future("rb2610", "rb", "螺纹钢", "SHFE", "2610", 3198, 3202, 0.74, 210000, 86, 320000, 2600),
  future("rb9999", "rb", "螺纹钢", "SHFE", "连续", 3284, 3288, 1.16, 1820000, 920, 2410000, 32600, { continuous: true }),
  future("cu2511", "cu", "沪铜", "SHFE", "2511", 76840, 76720, -0.86, 186000, 640, 248000, -8600, { main: true }),
  future("cu2512", "cu", "沪铜", "SHFE", "2512", 76610, 76520, -0.72, 92000, 280, 126000, -2400),
  future("cu9999", "cu", "沪铜", "SHFE", "连续", 76840, 76720, -0.86, 186000, 640, 248000, -8600, { continuous: true }),
  future("au2512", "au", "沪金", "SHFE", "2512", 612.4, 611.8, 0.64, 168000, 210, 186000, 4200, { main: true }),
  future("ag2512", "ag", "沪银", "SHFE", "2512", 7842, 7826, 1.48, 420000, 360, 286000, 12800, { main: true }),
  future("ni2511", "ni", "沪镍", "SHFE", "2511", 128640, 128420, -1.26, 86000, 148, 72000, -3100, { main: true }),
  future("ru2601", "ru", "橡胶", "SHFE", "2601", 16840, 16890, 0.92, 210000, 96, 164000, 5400, { main: true }),
  future("m2601", "m", "豆粕", "DCE", "2601", 3126, 3132, 0.54, 980000, 420, 1860000, 21400, { main: true }),
  future("m2605", "m", "豆粕", "DCE", "2605", 3084, 3088, 0.38, 360000, 140, 640000, 6200),
  future("m9999", "m", "豆粕", "DCE", "连续", 3126, 3132, 0.54, 980000, 420, 1860000, 21400, { continuous: true }),
  future("i2601", "i", "铁矿石", "DCE", "2601", 762, 766, 1.84, 640000, 280, 820000, 18600, { main: true }),
  future("y2601", "y", "豆油", "DCE", "2601", 8426, 8412, -0.42, 280000, 160, 420000, -3600, { main: true }),
  future("p2601", "p", "棕榈油", "DCE", "2601", 9124, 9108, -0.68, 310000, 190, 380000, -5400, { main: true }),
  future("c2601", "c", "玉米", "DCE", "2601", 2246, 2248, 0.16, 240000, 48, 620000, 1800, { main: true }),
  future("SR601", "SR", "白糖", "CZCE", "601", 5842, 5836, 0.28, 220000, 72, 340000, 2600, { main: true }),
  future("TA601", "TA", "PTA", "CZCE", "601", 5126, 5134, 1.06, 860000, 240, 1240000, 16800, { main: true }),
  future("MA601", "MA", "甲醇", "CZCE", "601", 2486, 2492, 0.74, 720000, 180, 860000, 9200, { main: true }),
  future("FG601", "FG", "玻璃", "CZCE", "601", 1284, 1278, -1.42, 480000, 96, 520000, -12400, { main: true }),
  future("sc2511", "sc", "原油", "INE", "2511", 521.6, 520.4, -0.94, 168000, 86, 64000, -1800, { main: true }),
  future("lc2601", "lc", "碳酸锂", "GFEX", "2601", 76820, 76640, 2.36, 186000, 220, 142000, 8600, { main: true }),
];

export const featuredCodes = [
  "600519.SH",
  "300750.SZ",
  "002594.SZ",
  "rb2601.SHF",
  "cu2511.SHF",
  "IF2610.CFX",
];

export function findInstrument(code: string): Instrument | undefined {
  return stocks.find((item) => item.code === code) ?? contracts.find((item) => item.code === code);
}
