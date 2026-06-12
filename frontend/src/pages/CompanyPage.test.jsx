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
  discovery_funnel: {
    raw: { new: 3, triaged: 1, built: 2, discarded: 4 },
    knowledge: { candidate: 5, validated: 2, rejected: 6, curated: 1 },
    rejection_rate_pct: 75.0,
  },
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

  it("探勘漏斗卡：計數、待審徽章、淘汰率、連到知識庫策展", async () => {
    renderPage();
    expect(await screen.findByText("探勘漏斗")).toBeInTheDocument();
    // raw 收料合計 = 3+1+2+4 = 10
    expect(screen.getByText("raw 收料").parentElement).toHaveTextContent("10");
    expect(screen.getByText("candidate").parentElement).toHaveTextContent("5");
    expect(screen.getByText("validated").parentElement).toHaveTextContent("2");
    expect(screen.getByText("curated").parentElement).toHaveTextContent("1");
    expect(screen.getByText("待審 2")).toBeInTheDocument(); // validated 待人審徽章
    expect(screen.getByText(/淘汰率 75/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /知識庫策展/ });
    expect(link).toHaveAttribute("href", "/library");
  });

  it("舊版回應沒有 discovery_funnel 時不畫漏斗卡也不崩", async () => {
    api.getCompanyOverview.mockResolvedValue({ ...OVERVIEW, discovery_funnel: undefined });
    renderPage();
    await screen.findByText("Bot 艦隊");
    expect(screen.queryByText("探勘漏斗")).not.toBeInTheDocument();
  });
});
