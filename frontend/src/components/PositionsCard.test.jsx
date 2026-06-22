// ============================================================
// PositionsCard 的元件測試
// ============================================================
// 把 api.getPositions 換成假資料，驗：有持倉時渲染各列 + 損益帶 +/- 號；
// 無持倉時顯示「目前無持倉」。

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import PositionsCard from "./PositionsCard";
import { api } from "../api";

// mock 整個 api 模組（只用到 getPositions）
vi.mock("../api", () => ({
  api: { getPositions: vi.fn() },
}));

describe("PositionsCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("有持倉：渲染代號與帶號損益", async () => {
    api.getPositions.mockResolvedValue([
      {
        symbol: "AAPL",
        qty: 10,
        avg_entry_price: 150,
        current_price: 160.5,
        market_value: 1605,
        unrealized_pl: 105,
        unrealized_plpc: 0.07,
      },
      {
        symbol: "TSLA",
        qty: 5,
        avg_entry_price: 200,
        current_price: 190,
        market_value: 950,
        unrealized_pl: -50,
        unrealized_plpc: -0.05,
      },
    ]);

    render(<PositionsCard />);

    expect(await screen.findByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("TSLA")).toBeInTheDocument();
    // 獲利帶 +，虧損帶 -
    expect(screen.getByText("+$105")).toBeInTheDocument();
    expect(screen.getByText("-$50")).toBeInTheDocument();
  });

  it("無持倉：顯示提示文字", async () => {
    api.getPositions.mockResolvedValue([]);
    render(<PositionsCard />);
    await waitFor(() =>
      expect(screen.getByText("目前無持倉")).toBeInTheDocument()
    );
  });

  it("API 失敗：降級成無持倉、不崩", async () => {
    api.getPositions.mockRejectedValue(new Error("boom"));
    render(<PositionsCard />);
    await waitFor(() =>
      expect(screen.getByText("目前無持倉")).toBeInTheDocument()
    );
  });
});
