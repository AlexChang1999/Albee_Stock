// CompanyPage：公司戰情頁渲染（Phase 10 step-01）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// monkeypatch api
vi.mock("../api", () => ({
  api: { getCompanyOverview: vi.fn() },
}));

import { api } from "../api";
import CompanyPage from "./CompanyPage";

const OVERVIEW = {
  account: null, // 離線：帳戶不可得
  bots: {
    total: 2,
    active: 1,
    list: [
      { id: 1, name: "均線 Bot", symbol: "AAPL", strategy: "ma_crossover", is_active: true },
      { id: 2, name: "RSI Bot", symbol: "TSLA", strategy: "rsi", is_active: false },
    ],
  },
  automation: {
    enabled: true,
    ev_threshold: 150,
    winrate_threshold: 55,
    max_bots: 5,
    cash_per_bot: 1000,
    scan_hour: 8,
  },
  circuit_breaker: { tripped: false, equity_now: null, equity_peak: null },
  decisions: [
    { id: 1, bot_id: 1, symbol: "AAPL", signal: "buy", reason: "黃金交叉", price: 190, action: "bought" },
  ],
  opportunities: [
    { id: 1, symbol: "NVDA", strategy_key: "macd", oos_expected_value: 320, oos_win_rate_pct: 62, status: "new" },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter>
      <CompanyPage />
    </MemoryRouter>
  );
}

describe("CompanyPage", () => {
  beforeEach(() => {
    api.getCompanyOverview.mockReset();
    api.getCompanyOverview.mockResolvedValue(OVERVIEW);
  });

  it("渲染各部門卡", async () => {
    renderPage();
    expect(await screen.findByText("Bot 艦隊")).toBeInTheDocument();
    expect(screen.getByText("自動化部署")).toBeInTheDocument();
    expect(screen.getByText("風控熔斷")).toBeInTheDocument();
    expect(screen.getByText("策略主管")).toBeInTheDocument();
    expect(screen.getByText("回測主管")).toBeInTheDocument();
    expect(screen.getByText("決策審計")).toBeInTheDocument();
    expect(screen.getByText("常駐探勘")).toBeInTheDocument();
    expect(screen.getByText(/NVDA · macd/)).toBeInTheDocument(); // 機會清單候選
  });

  it("離線時顯示帳戶不可得提示、自動化顯示開啟", async () => {
    renderPage();
    await screen.findByText("Bot 艦隊");
    expect(screen.getByText(/未連線 Alpaca/)).toBeInTheDocument();
    expect(screen.getByText("自動駕駛中")).toBeInTheDocument();
  });

  it("部門卡帶連到既有頁的連結", async () => {
    renderPage();
    await screen.findByText("Bot 艦隊");
    const evLink = screen.getByRole("link", { name: /EV 榜/ });
    expect(evLink).toHaveAttribute("href", "/backtest-runs");
  });
});
