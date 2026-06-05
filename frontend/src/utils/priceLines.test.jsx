// ============================================================
// buildBotPriceLines / findBotForSymbol 單元測試（純函式，不碰畫面）
// ============================================================
import { describe, it, expect } from "vitest";
import {
  buildBotPriceLines,
  findBotForSymbol,
  priceToPct,
} from "../utils/priceLines";

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

describe("buildBotPriceLines 拖曳中繼資料", () => {
  it("止損/追蹤止盈線帶 editable + botId + field + refPrice，進場線不可編輯", () => {
    const lines = buildBotPriceLines({
      id: 7,
      avg_entry_price: 100,
      stop_loss_pct: 0.05,
      peak_price: 110,
      trailing_stop_pct: 0.03,
    });
    const byTitle = Object.fromEntries(lines.map((l) => [l.title, l]));

    // 進場線：真實成交價，不可拖
    expect(byTitle["進場均價"].editable).toBeUndefined();

    // 止損線：可拖，參考價是進場價
    expect(byTitle["止損"].editable).toBe(true);
    expect(byTitle["止損"].botId).toBe(7);
    expect(byTitle["止損"].field).toBe("stop_loss_pct");
    expect(byTitle["止損"].refPrice).toBe(100);

    // 追蹤止盈線：可拖，參考價是持倉最高價
    expect(byTitle["追蹤止盈"].editable).toBe(true);
    expect(byTitle["追蹤止盈"].field).toBe("trailing_stop_pct");
    expect(byTitle["追蹤止盈"].refPrice).toBe(110);
  });
});

describe("priceToPct（拖曳後反推百分比）", () => {
  it("進場價 100、止損線拖到 92 → 0.08", () => {
    expect(priceToPct(100, 92)).toBeCloseTo(0.08);
  });

  it("四捨五入到小數第 4 位（0.01% 精度）", () => {
    expect(priceToPct(150, 142.857)).toBe(0.0476); // 1 − 142.857/150 = 0.04762 → 0.0476
  });

  it("拖到參考價之上（pct ≤ 0）→ null", () => {
    expect(priceToPct(100, 105)).toBe(null);
    expect(priceToPct(100, 100)).toBe(null);
  });

  it("拖到 0 或負（pct ≥ 1）→ null", () => {
    expect(priceToPct(100, 0)).toBe(null);
    expect(priceToPct(100, -5)).toBe(null);
  });

  it("參考價無效 → null", () => {
    expect(priceToPct(0, 50)).toBe(null);
    expect(priceToPct(null, 50)).toBe(null);
    expect(priceToPct(100, null)).toBe(null);
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
