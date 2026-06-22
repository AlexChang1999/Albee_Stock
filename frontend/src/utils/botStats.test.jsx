// ============================================================
// statRows 的單元測試（純函式最好測：給輸入、比對輸出，不碰畫面）
// ============================================================
import { describe, it, expect } from "vitest";
import { statRows, formatCheckedAgo, holdingText } from "../utils/botStats";

describe("statRows", () => {
  it("沒有 stats 時，四個欄位都顯示 '-'", () => {
    const rows = statRows(null);
    // 取每一列的「值」（陣列第 2 個元素）出來比對
    const values = rows.map((r) => r[1]);
    expect(values).toEqual(["-", "-", "-", "-"]);
  });

  it("有 stats 但交易次數為 0 時，數字欄顯示 '-'、交易次數顯示 0", () => {
    const rows = statRows({ num_trades: 0 });
    expect(rows[0][1]).toBe("-"); // 勝率
    expect(rows[2][1]).toBe(0); // 交易次數
  });

  it("正報酬時，報酬率那列帶 success 顏色", () => {
    const rows = statRows({
      num_trades: 5,
      win_rate_pct: 60,
      return_pct: 12.5,
      max_drawdown_pct: 3,
    });
    expect(rows[0][1]).toBe("60%"); // 勝率
    expect(rows[1][1]).toBe("+12.5%"); // 報酬率值（正報酬補 + 號，不只靠顏色）
    expect(rows[1][2]).toBe("success.main"); // 報酬率顏色（正 = 綠）
  });

  it("負報酬時，報酬率那列帶 error 顏色", () => {
    const rows = statRows({
      num_trades: 5,
      win_rate_pct: 40,
      return_pct: -8,
      max_drawdown_pct: 10,
    });
    expect(rows[1][2]).toBe("error.main"); // 報酬率顏色（負 = 紅）
  });
});

describe("formatCheckedAgo", () => {
  const now = new Date("2026-06-02T12:00:00Z").getTime();

  it("null / 無效值 → 尚未檢查", () => {
    expect(formatCheckedAgo(null, now)).toBe("尚未檢查");
    expect(formatCheckedAgo("not-a-date", now)).toBe("尚未檢查");
  });

  it("30 秒前 → 秒", () => {
    expect(formatCheckedAgo("2026-06-02T11:59:30Z", now)).toBe("30 秒前檢查");
  });

  it("5 分鐘前 → 分鐘", () => {
    expect(formatCheckedAgo("2026-06-02T11:55:00Z", now)).toBe("5 分鐘前檢查");
  });

  it("3 小時前 → 小時", () => {
    expect(formatCheckedAgo("2026-06-02T09:00:00Z", now)).toBe("3 小時前檢查");
  });
});

describe("holdingText", () => {
  it("null（空手）→ 空手", () => {
    expect(holdingText(null)).toBe("空手");
  });

  it("有最高價 → 持倉中附峰值（兩位小數）", () => {
    expect(holdingText(123.4)).toBe("持倉中 · 峰值 $123.40");
  });
});
