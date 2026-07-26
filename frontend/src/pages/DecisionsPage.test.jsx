// DecisionsPage：決策審計頁渲染 + 選 Bot（Phase 9 step-06）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route, Outlet } from "react-router-dom";

vi.mock("../api", () => ({
  api: { getBotDecisions: vi.fn(), getBotLessons: vi.fn() },
}));

import { api } from "../api";
import DecisionsPage from "./DecisionsPage";

const BOTS = [
  { id: 10, name: "均線 Bot", symbol: "AAPL" },
  { id: 20, name: "RSI Bot", symbol: "TSLA" },
];
const DECISIONS = [
  { id: 1, symbol: "AAPL", signal: "buy", reason: "黃金交叉", price: 150, volume: 1234567, qty: 5, indicators: { rsi: 28.1 }, action: "bought", created_at: "2026-06-01T10:00:00" },
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
    api.getBotLessons.mockReset();
    api.getBotLessons.mockResolvedValue({ bot_id: 10, lessons: "教訓：少追高", stub: false });
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

  it("顯示 量 欄並可讀教訓（LLM 摘要）", async () => {
    renderPage();
    fireEvent.mouseDown(screen.getByLabelText("選擇 Bot"));
    fireEvent.click(await screen.findByText("均線 Bot（AAPL）"));
    // 量帶千分位
    expect(await screen.findByText("1,234,567")).toBeInTheDocument();
    // 讀教訓 → 顯示 LLM 摘要
    fireEvent.click(screen.getByRole("button", { name: /讀教訓/ }));
    expect(await screen.findByText("教訓：少追高")).toBeInTheDocument();
    expect(api.getBotLessons).toHaveBeenCalledWith(10);
  });
});
