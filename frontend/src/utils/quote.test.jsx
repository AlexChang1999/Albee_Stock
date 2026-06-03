// ============================================================
// 報價工具的單元測試（純函式：給輸入、比對輸出）
// ============================================================
import { describe, it, expect } from "vitest";
import { quoteDirection, formatPrice } from "../utils/quote";

describe("quoteDirection", () => {
  it("沒有前一筆價（首次）→ flat", () => {
    expect(quoteDirection(100, null)).toBe("flat");
    expect(quoteDirection(100, undefined)).toBe("flat");
  });

  it("新價 > 前價 → up", () => {
    expect(quoteDirection(101, 100)).toBe("up");
  });

  it("新價 < 前價 → down", () => {
    expect(quoteDirection(99, 100)).toBe("down");
  });

  it("價格沒變 → flat", () => {
    expect(quoteDirection(100, 100)).toBe("flat");
  });
});

describe("formatPrice", () => {
  it("null / NaN → 破折號", () => {
    expect(formatPrice(null)).toBe("—");
    expect(formatPrice(undefined)).toBe("—");
    expect(formatPrice(NaN)).toBe("—");
  });

  it("數字 → 固定兩位小數", () => {
    expect(formatPrice(312.0599)).toBe("312.06");
    expect(formatPrice(10)).toBe("10.00");
  });
});
