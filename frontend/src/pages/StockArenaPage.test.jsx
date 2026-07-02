// StockArenaPage：個股策略擂台 — 批次「部署前 N 名」+ 去重（Phase 15）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api", () => ({
  api: {
    autoBacktest: vi.fn(),
    getBots: vi.fn(),
    createBot: vi.fn(),
    startBot: vi.fn(),
  },
}));

import { api } from "../api";
import StockArenaPage from "./StockArenaPage";

const RESULT = {
  symbol: "AAPL",
  strategies_tested: 2,
  combos_tested: 5,
  leaderboard: [
    { strategy_key: "rsi", params: { period: 14 }, oos_expected_value: 1.2, oos_win_rate_pct: 55, oos_total_return_pct: 10, num_round_trips: 8, overfit_gap: 0.72, oos_num_round_trips: 21, oos_sharpe: 1.1 },
    { strategy_key: "macd", params: {}, oos_expected_value: 0.5, oos_win_rate_pct: 50, oos_total_return_pct: 4, num_round_trips: 6, overfit_gap: 0.1, oos_num_round_trips: 25, oos_sharpe: 0.8 },
  ],
};

async function scanThenBoard() {
  render(<StockArenaPage />);
  fireEvent.click(screen.getByRole("button", { name: /開跑擂台/ }));
  expect(await screen.findByText(/排行榜/)).toBeInTheDocument();
}

describe("StockArenaPage 批次部署", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.autoBacktest.mockResolvedValue(RESULT);
    api.createBot.mockImplementation(async () => ({ id: Math.random() }));
    api.startBot.mockResolvedValue({});
  });

  it("部署前 N 名：每個策略各建一個 paper bot 並啟動", async () => {
    api.getBots.mockResolvedValue([]); // 無既有 bot
    await scanThenBoard();

    fireEvent.click(screen.getByRole("button", { name: /部署前.*名/ }));

    await waitFor(() => expect(api.createBot).toHaveBeenCalledTimes(2));
    expect(api.startBot).toHaveBeenCalledTimes(2);
    // 帶上自選的輪詢秒數（預設 60）
    expect(api.createBot.mock.calls[0][0]).toMatchObject({
      symbol: "AAPL",
      check_interval_sec: 60,
    });
    expect(await screen.findByText(/已部署 2 個 paper bot/)).toBeInTheDocument();
  });

  it("M3.5：掃描帶 timeframe、排行榜顯示 Gap / OOS 回合", async () => {
    api.getBots.mockResolvedValue([]);
    await scanThenBoard();

    // 預設 timeframe=1Day 隨掃描送出（後端 /auto-backtest 已支援）
    expect(api.autoBacktest.mock.calls[0][0]).toMatchObject({ timeframe: "1Day" });
    // 排行榜顯示 M3 新欄位（Gap 0.72 > 0.5 那筆 + OOS 回合數）
    expect(screen.getByText("0.72")).toBeInTheDocument();
    expect(screen.getByText("21")).toBeInTheDocument();

    // 部署 bot 也帶同一個 timeframe（回測=實盤鐵則）
    fireEvent.click(screen.getByRole("button", { name: /部署前.*名/ }));
    await waitFor(() => expect(api.createBot).toHaveBeenCalled());
    expect(api.createBot.mock.calls[0][0]).toMatchObject({ timeframe: "1Day" });
  });

  it("去重：同股同策略已存在的跳過", async () => {
    api.getBots.mockResolvedValue([{ symbol: "AAPL", strategy: "rsi" }]); // rsi 已存在
    await scanThenBoard();

    fireEvent.click(screen.getByRole("button", { name: /部署前.*名/ }));

    await waitFor(() => expect(api.createBot).toHaveBeenCalledTimes(1)); // 只建 macd
    expect(api.createBot.mock.calls[0][0]).toMatchObject({ strategy: "macd" });
    expect(await screen.findByText(/跳過 1 個已存在/)).toBeInTheDocument();
  });
});
