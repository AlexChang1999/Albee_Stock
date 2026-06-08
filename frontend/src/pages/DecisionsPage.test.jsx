// DecisionsPage：決策審計頁渲染 + 選 Bot（Phase 9 step-06）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route, Outlet } from "react-router-dom";

vi.mock("../api", () => ({
  api: { getBotDecisions: vi.fn() },
}));

import { api } from "../api";
import DecisionsPage from "./DecisionsPage";

const BOTS = [
  { id: 10, name: "均線 Bot", symbol: "AAPL" },
  { id: 20, name: "RSI Bot", symbol: "TSLA" },
];
const DECISIONS = [
  { id: 1, symbol: "AAPL", signal: "buy", reason: "黃金交叉", price: 150, action: "bought", created_at: "2026-06-01T10:00:00" },
  { id: 2, symbol: "AAPL", signal: "hold", reason: "無訊號", price: 151, action: "hold", created_at: "2026-06-02T10:00:00" },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <Routes>
        <Route element={<Outlet context={{ bots: BOTS }} />}>
          <Route index element={<DecisionsPage />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("DecisionsPage", () => {
  beforeEach(() => {
    api.getBotDecisions.mockReset();
    api.getBotDecisions.mockResolvedValue(DECISIONS);
  });

  it("一開始未選 Bot，不顯示表格", () => {
    renderPage();
    expect(screen.getByText("決策審計")).toBeInTheDocument();
    expect(api.getBotDecisions).not.toHaveBeenCalled();
  });

  it("選 Bot 後抓並列出決策（含配色動作）", async () => {
    renderPage();
    // MUI Select：input 帶 label「選擇 Bot」
    fireEvent.mouseDown(screen.getByLabelText("選擇 Bot"));
    fireEvent.click(await screen.findByText("均線 Bot（AAPL）"));
    expect(await screen.findByText("黃金交叉")).toBeInTheDocument();
    expect(screen.getByText("買進")).toBeInTheDocument();
    expect(screen.getByText("觀望/續抱")).toBeInTheDocument();
    expect(api.getBotDecisions).toHaveBeenCalledWith(10);
  });
});
