// ============================================================
// 數字格式化工具測試
// ============================================================
import { describe, it, expect } from "vitest";
import { formatCompact, formatPercent } from "../utils/number";

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
