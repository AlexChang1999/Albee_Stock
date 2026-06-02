// ============================================================
// statRows 的單元測試（純函式最好測：給輸入、比對輸出，不碰畫面）
// ============================================================
import { describe, it, expect } from "vitest";
import { statRows } from "../utils/botStats";

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
    expect(rows[1][1]).toBe("12.5%"); // 報酬率值
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
