// ============================================================
// 數字格式化工具測試
// ============================================================
import { describe, it, expect } from "vitest";
import { formatCompact, formatPercent, signOf, signedMoney, money } from "../utils/number";

describe("formatCompact", () => {
  it("null / NaN → 破折號", () => {
    expect(formatCompact(null)).toBe("—");
    expect(formatCompact(NaN)).toBe("—");
  });

  it("兆 / 十億 / 百萬 / 千 縮寫", () => {
    expect(formatCompact(3.5e12)).toBe("3.50T");
    expect(formatCompact(1.2e9)).toBe("1.20B");
    expect(formatCompact(4.5e6)).toBe("4.50M");
    expect(formatCompact(2000)).toBe("2.00K");
  });

  it("小數字原樣、負數帶負號", () => {
    expect(formatCompact(500)).toBe("500");
    expect(formatCompact(-1.2e9)).toBe("-1.20B");
  });
});

describe("formatPercent", () => {
  it("比率 → 百分比兩位小數", () => {
    expect(formatPercent(0.0052)).toBe("0.52%");
    expect(formatPercent(0.25)).toBe("25.00%");
  });

  it("null → 破折號", () => {
    expect(formatPercent(null)).toBe("—");
  });
});

describe("signOf", () => {
  it("正數補加號、負數與零不補（負號由數字本身帶）", () => {
    expect(signOf(5.2)).toBe("+");
    expect(signOf(-3)).toBe("");
    expect(signOf(0)).toBe("");
  });

  it("非數字回空字串", () => {
    expect(signOf(null)).toBe("");
    expect(signOf(NaN)).toBe("");
  });
});

describe("signedMoney", () => {
  it("符號在錢號之前", () => {
    expect(signedMoney(12)).toBe("+$12");
    expect(signedMoney(-5)).toBe("-$5");
    expect(signedMoney(0)).toBe("$0");
  });

  it("null / 空 / NaN → 破折號", () => {
    expect(signedMoney(null)).toBe("—");
    expect(signedMoney("")).toBe("—");
    expect(signedMoney(NaN)).toBe("—");
  });
});

describe("money", () => {
  it("千分位金額", () => {
    expect(money(1234)).toBe("$1,234");
    expect(money(0)).toBe("$0");
  });

  it("null / 空 / NaN → 破折號", () => {
    expect(money(null)).toBe("—");
    expect(money("")).toBe("—");
    expect(money(NaN)).toBe("—");
  });
});
