// AutoBacktestPanel：全自動掃描 — M3.5 timeframe 下拉 + OOS 診斷欄
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api", () => ({
  api: {
    autoBacktest: vi.fn(),
  },
}));

import { api } from "../api";
import AutoBacktestPanel from "./AutoBacktestPanel";

// 最小可渲染結果：冠軍 + 一筆排行榜（含 M3 walk-forward 欄位）
const RESULT = {
  combos_tested: 3,
  strategies_tested: 1,
  data_points: 200,
  best: {
    strategy_key: "rsi",
    params: { period: 14 },
    metrics: {
      expected_value: 5, expectancy_pct: 0.5, total_return_pct: 8,
      buy_and_hold_pct: 6, win_rate_pct: 60, max_drawdown_pct: 4,
      profit_factor: 1.8, num_round_trips: 10,
    },
  },
  leaderboard: [
    {
      strategy_key: "rsi", params: { period: 14 },
      expected_value: 5, expectancy_pct: 0.5, total_return_pct: 8,
      win_rate_pct: 60, max_drawdown_pct: 4, num_round_trips: 10,
      oos_expected_value: 3.2, overfit_gap: 0.66, oos_num_round_trips: 24,
    },
  ],
};

describe("AutoBacktestPanel（M3.5）", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.autoBacktest.mockResolvedValue(RESULT);
  });

  it("掃描帶 timeframe（預設 1Day），排行榜顯示 OOS EV / Gap / OOS 交易", async () => {
    render(<AutoBacktestPanel />);
    fireEvent.click(screen.getByRole("button", { name: /一鍵全自動掃描/ }));

    await waitFor(() => expect(api.autoBacktest).toHaveBeenCalled());
    expect(api.autoBacktest.mock.calls[0][0]).toMatchObject({ timeframe: "1Day" });

    // 排行榜 M3 新欄位（Gap 0.66 > 0.5 那筆會紅色警示，這裡驗值有渲染）
    expect(await screen.findByText("3.2")).toBeInTheDocument();
    expect(screen.getByText("0.66")).toBeInTheDocument();
    expect(screen.getByText("24")).toBeInTheDocument();
  });
});
