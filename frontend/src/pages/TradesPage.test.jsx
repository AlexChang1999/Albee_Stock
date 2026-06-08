// TradesPage：交易紀錄頁渲染 + 篩選互動（Phase 9 step-02）
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route, Outlet } from "react-router-dom";
import TradesPage from "./TradesPage";

const TRADES = [
  { id: 1, bot_id: 10, symbol: "AAPL", side: "buy", qty: 1, price: 100, reason: "x", created_at: "2026-06-01T10:00:00" },
  { id: 2, bot_id: 20, symbol: "TSLA", side: "sell", qty: 2, price: 200, reason: "y", created_at: "2026-06-05T10:00:00" },
];
const BOTS = [
  { id: 10, name: "Bot-A" },
  { id: 20, name: "Bot-B" },
];

// 用一個 parent 路由提供 Outlet context，模擬 SidebarLayout。
function renderPage() {
  return render(
    <MemoryRouter>
      <Routes>
        <Route element={<Outlet context={{ trades: TRADES, bots: BOTS }} />}>
          <Route index element={<TradesPage />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("TradesPage", () => {
  it("渲染全部交易與計數", () => {
    renderPage();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("TSLA")).toBeInTheDocument();
    expect(screen.getByText("共 2 / 2 筆")).toBeInTheDocument();
  });

  it("依標的篩選會縮減結果", () => {
    renderPage();
    fireEvent.change(screen.getByLabelText("標的"), { target: { value: "aapl" } });
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.queryByText("TSLA")).not.toBeInTheDocument();
    expect(screen.getByText("共 1 / 2 筆")).toBeInTheDocument();
  });

  it("清除篩選回到全部", () => {
    renderPage();
    fireEvent.change(screen.getByLabelText("標的"), { target: { value: "aapl" } });
    fireEvent.click(screen.getByText("清除篩選"));
    expect(screen.getByText("共 2 / 2 筆")).toBeInTheDocument();
  });
});
