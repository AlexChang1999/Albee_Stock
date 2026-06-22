// FactorsPage：因子報表渲染 + 匯出鈕（Phase 10 step-03）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api", () => ({
  api: {
    getFactors: vi.fn(),
    factorsCsvUrl: vi.fn((symbol) =>
      `http://x/factors/export.csv${symbol ? `?symbol=${symbol}` : ""}`
    ),
  },
}));

import { api } from "../api";
import FactorsPage from "./FactorsPage";

const ROWS = [
  {
    id: 1, symbol: "AAPL", as_of: "2026-06-08T12:00:00", regime: "trending",
    volume_ratio: 3.2, return_5d: 0.021, return_20d: 0.08, volatility_20d: 0.31,
    trend_strength: 27.5, atr_pct: 0.045, range_position: 0.9,
  },
];

describe("FactorsPage", () => {
  beforeEach(() => {
    api.getFactors.mockReset();
    api.getFactors.mockResolvedValue(ROWS);
  });

  it("渲染因子表格 + regime 中文標籤", async () => {
    render(<FactorsPage />);
    expect(await screen.findByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("趨勢")).toBeInTheDocument(); // regime=trending
    expect(screen.getByText("3.20")).toBeInTheDocument(); // volume_ratio 格式化
  });

  it("匯出鈕連到 CSV 端點", async () => {
    render(<FactorsPage />);
    await screen.findByText("AAPL");
    const link = screen.getByText("匯出 CSV").closest("a");
    expect(link).toHaveAttribute("href", "http://x/factors/export.csv");
  });

  it("查詢鈕用輸入的 symbol 再打 API", async () => {
    render(<FactorsPage />);
    await screen.findByText("AAPL");
    fireEvent.change(screen.getByLabelText(/股票代號/), { target: { value: "tsla" } });
    fireEvent.click(screen.getByText("查詢"));
    await waitFor(() => expect(api.getFactors).toHaveBeenCalledWith({ symbol: "TSLA" }));
  });
});
