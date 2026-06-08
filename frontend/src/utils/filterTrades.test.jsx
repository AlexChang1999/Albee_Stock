// filterTrades 純函式測試（Phase 9 step-02）
import { describe, it, expect } from "vitest";
import { filterTrades } from "./filterTrades";

const TRADES = [
  { id: 1, bot_id: 10, symbol: "AAPL", side: "buy", created_at: "2026-06-01T10:00:00" },
  { id: 2, bot_id: 10, symbol: "AAPL", side: "sell", created_at: "2026-06-03T10:00:00" },
  { id: 3, bot_id: 20, symbol: "TSLA", side: "buy", created_at: "2026-06-05T10:00:00" },
  { id: 4, bot_id: 20, symbol: "NVDA", side: "sell", created_at: "2026-06-07T10:00:00" },
];

describe("filterTrades", () => {
  it("無篩選回傳全部", () => {
    expect(filterTrades(TRADES, {})).toHaveLength(4);
  });

  it("依 Bot 過濾", () => {
    const r = filterTrades(TRADES, { botId: 10 });
    expect(r.map((t) => t.id)).toEqual([1, 2]);
  });

  it("botId 字串也能比對", () => {
    expect(filterTrades(TRADES, { botId: "20" }).map((t) => t.id)).toEqual([3, 4]);
  });

  it("依標的子字串、不分大小寫", () => {
    expect(filterTrades(TRADES, { symbol: "aapl" }).map((t) => t.id)).toEqual([1, 2]);
  });

  it("依買賣別", () => {
    expect(filterTrades(TRADES, { side: "sell" }).map((t) => t.id)).toEqual([2, 4]);
  });

  it("依日期區間（含端點）", () => {
    const r = filterTrades(TRADES, { dateFrom: "2026-06-03", dateTo: "2026-06-05" });
    expect(r.map((t) => t.id)).toEqual([2, 3]);
  });

  it("多條件交集", () => {
    const r = filterTrades(TRADES, { botId: 20, side: "buy" });
    expect(r.map((t) => t.id)).toEqual([3]);
  });

  it("無相符回空陣列", () => {
    expect(filterTrades(TRADES, { symbol: "GOOG" })).toEqual([]);
  });

  it("非陣列輸入回空陣列", () => {
    expect(filterTrades(null, {})).toEqual([]);
  });
});
