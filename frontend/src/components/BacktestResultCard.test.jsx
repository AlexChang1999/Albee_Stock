// ============================================================
// BacktestResultCard 的元件測試
// ============================================================
// 驗三件事：指標 chip 有畫出來（含 VaR/CVaR）、壓力測試按鈕會打 API 並顯示分布、
// API 失敗時顯示錯誤不崩潰。api 模組用 vi.mock 換成假函式，不真的連後端。
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import BacktestResultCard from "./BacktestResultCard";
import { api } from "../api";

vi.mock("../api", () => ({
  api: {
    reportUrl: (id) => `http://test/report/${id}`,
    stressBacktestRun: vi.fn(),
  },
}));

const METRICS = {
  expected_value: 12.3,
  win_rate_pct: 55,
  profit_factor: 1.8,
  total_return_pct: 20,
  max_drawdown_pct: 8,
  num_round_trips: 10,
  extended: { sharpe: 1.2, sortino: 1.5, var_95_pct: 1.1, cvar_95_pct: 1.6 },
};

const STRESS = {
  n_paths: 1000,
  final_equity_p5: 9000,
  final_equity_p50: 11000,
  final_equity_p95: 13000,
  max_drawdown_p50: 10,
  max_drawdown_p95: 25,
  drawdown_threshold_pct: 20,
  prob_drawdown_exceeds_pct: 30,
  ruin_threshold_pct: 50,
  prob_ruin: 0,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("BacktestResultCard", () => {
  it("畫出基本指標與 VaR/CVaR chip", () => {
    render(<BacktestResultCard metrics={METRICS} title="測試卡" />);
    expect(screen.getByText("測試卡")).toBeInTheDocument();
    expect(screen.getByText("勝率 55%")).toBeInTheDocument();
    expect(screen.getByText("VaR95 1.1%")).toBeInTheDocument();
    expect(screen.getByText("CVaR95 1.6%")).toBeInTheDocument();
  });

  it("沒有 runId 時不顯示壓力測試按鈕", () => {
    render(<BacktestResultCard metrics={METRICS} />);
    expect(screen.queryByText(/壓力測試/)).not.toBeInTheDocument();
  });

  it("按壓力測試會打 API 並顯示風險分布", async () => {
    api.stressBacktestRun.mockResolvedValue(STRESS);
    render(<BacktestResultCard metrics={METRICS} runId={7} />);
    fireEvent.click(screen.getByText(/壓力測試/));
    await waitFor(() =>
      expect(screen.getByText("中位 p50 $11000")).toBeInTheDocument()
    );
    expect(api.stressBacktestRun).toHaveBeenCalledWith(7);
    expect(screen.getByText("破產機率 0%")).toBeInTheDocument();
  });

  it("API 失敗時顯示錯誤訊息", async () => {
    api.stressBacktestRun.mockRejectedValue(new Error("後端掛了"));
    render(<BacktestResultCard metrics={METRICS} runId={7} />);
    fireEvent.click(screen.getByText(/壓力測試/));
    await waitFor(() =>
      expect(screen.getByText("後端掛了")).toBeInTheDocument()
    );
  });
});
