// ============================================================
// buildBotPriceLines / findBotForSymbol 單元測試（純函式，不碰畫面）
// ============================================================
import { describe, it, expect } from "vitest";
import { buildBotPriceLines, findBotForSymbol } from "../utils/priceLines";

describe("buildBotPriceLines", () => {
  it("沒有 bot 時回空陣列", () => {
    expect(buildBotPriceLines(null)).toEqual([]);
  });

  it("空手（avg_entry_price 為 null）只可能畫追蹤止盈線", () => {
    const lines = buildBotPriceLines({
      avg_entry_price: null,
      stop_loss_pct: 0.05,
      peak_price: 120,
      trailing_stop_pct: 0.03,
    });
    // 沒進場價 → 沒進場線、沒止損線；但有 peak + trailing → 有追蹤止盈線
    expect(lines).toHaveLength(1);
    expect(lines[0].title).toBe("追蹤止盈");
    expect(lines[0].price).toBeCloseTo(120 * 0.97);
  });

  it("有持倉時，三條線價格與樣式正確", () => {
    const lines = buildBotPriceLines({
      avg_entry_price: 100,
      stop_loss_pct: 0.05,
      peak_price: 110,
      trailing_stop_pct: 0.03,
    });
    const byTitle = Object.fromEntries(lines.map((l) => [l.title, l]));

    expect(byTitle["進場均價"].price).toBe(100);
    expect(byTitle["進場均價"].dashed).toBe(true); // 進場線是虛線

    expect(byTitle["止損"].price).toBeCloseTo(95); // 100 ×(1−0.05)
    expect(byTitle["止損"].dashed).toBe(false);

    expect(byTitle["追蹤止盈"].price).toBeCloseTo(110 * 0.97); // peak ×(1−0.03)
  });

  it("有進場價但沒設止損 → 不畫止損線", () => {
    const lines = buildBotPriceLines({
      avg_entry_price: 100,
      stop_loss_pct: null,
      peak_price: null,
      trailing_stop_pct: null,
    });
    expect(lines).toHaveLength(1);
    expect(lines[0].title).toBe("進場均價");
  });
});

describe("findBotForSymbol", () => {
  const bots = [
    { id: 1, symbol: "AAPL", is_active: false },
    { id: 2, symbol: "AAPL", is_active: true },
    { id: 3, symbol: "TSLA", is_active: false },
  ];

  it("優先回傳啟用中的同檔 Bot", () => {
    expect(findBotForSymbol(bots, "AAPL").id).toBe(2);
  });

  it("沒有啟用中的就回第一個符合的", () => {
    expect(findBotForSymbol(bots, "TSLA").id).toBe(3);
  });

  it("找不到回 null", () => {
    expect(findBotForSymbol(bots, "NVDA")).toBe(null);
    expect(findBotForSymbol(null, "AAPL")).toBe(null);
  });
});
