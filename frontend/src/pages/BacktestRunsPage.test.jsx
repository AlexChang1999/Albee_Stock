// BacktestRunsPage：回測歷史頁渲染 + 收藏切換（Phase 9 step-03）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// monkeypatch api
vi.mock("../api", () => ({
  api: {
    getBacktestRuns: vi.fn(),
    getBacktestRun: vi.fn(),
    favoriteBacktestRun: vi.fn(() => Promise.resolve({})),
    reportUrl: (id) => `http://x/${id}/report`,
  },
}));

import { api } from "../api";
import BacktestRunsPage from "./BacktestRunsPage";

const RUNS = [
  {
    id: 1,
    strategy_key: "ma_crossover",
    symbol: "AAPL",
    expected_value: 12.5,
    win_rate_pct: 60,
    total_return_pct: 8,
    max_drawdown_pct: 4,
    has_postmortem: false,
    is_good: false,
    oos_expected_value: 8.1,
    overfit_gap: 0.62,
    oos_num_round_trips: 22,
    timeframe: "5Min",
  },
  {
    id: 2,
    strategy_key: "rsi",
    symbol: "TSLA",
    expected_value: -3.2,
    win_rate_pct: 40,
    total_return_pct: -2,
    max_drawdown_pct: 9,
    has_postmortem: true,
    is_good: true,
  },
];

describe("BacktestRunsPage", () => {
  beforeEach(() => {
    api.getBacktestRuns.mockReset();
    api.getBacktestRuns.mockResolvedValue(RUNS);
    api.favoriteBacktestRun.mockClear();
  });

  it("渲染 EV 榜的每一筆", async () => {
    render(<BacktestRunsPage />);
    expect(await screen.findByText("AAPL", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("12.5")).toBeInTheDocument();
    expect(screen.getByText("-3.2")).toBeInTheDocument();
  });

  it("M3.5：顯示 OOS EV / Gap / timeframe；舊紀錄缺欄位顯示 —", async () => {
    render(<BacktestRunsPage />);
    await screen.findByText("12.5");
    // 第一筆有 walk-forward 欄位
    expect(screen.getByText("8.1")).toBeInTheDocument();
    expect(screen.getByText("0.62")).toBeInTheDocument();
    expect(screen.getByText("5Min")).toBeInTheDocument();
    // 第二筆是舊紀錄（無 OOS 欄位）→ 該列顯示 "—" 不會壞畫面
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("點收藏鈕呼叫 favoriteBacktestRun（反轉 is_good）", async () => {
    render(<BacktestRunsPage />);
    await screen.findByText("12.5");
    // 第一筆 is_good=false → 顯示 ☆，點下去送 true
    fireEvent.click(screen.getAllByText("☆")[0]);
    await waitFor(() =>
      expect(api.favoriteBacktestRun).toHaveBeenCalledWith(1, true)
    );
  });
});
