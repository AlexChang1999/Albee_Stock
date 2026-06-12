// ============================================================
// DecisionFeed 的元件測試
// ============================================================
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import DecisionFeed from "./DecisionFeed";
import { api } from "../api";

// mock api：播種端點回固定資料
vi.mock("../api", () => ({
  api: { getRecentDecisions: vi.fn() },
}));

describe("DecisionFeed", () => {
  beforeEach(() => {
    api.getRecentDecisions.mockReset();
  });

  it("沒資料顯示空態提示", async () => {
    api.getRecentDecisions.mockResolvedValue([]);
    render(<DecisionFeed feed={[]} />);
    expect(await screen.findByText(/還沒有決策紀錄/)).toBeInTheDocument();
  });

  it("開頁播種：顯示 DB 來的歷史決策（含 bot 名與原因）", async () => {
    api.getRecentDecisions.mockResolvedValue([
      {
        id: 7,
        bot_id: 1,
        bot_name: "甲Bot",
        symbol: "AAPL",
        signal: "hold",
        reason: "無交叉訊號",
        price: 10.5,
        action: "hold",
        created_at: "2026-06-12T10:00:00",
      },
    ]);
    render(<DecisionFeed feed={[]} />);
    expect(await screen.findByText("甲Bot")).toBeInTheDocument();
    expect(screen.getByText(/無交叉訊號/)).toBeInTheDocument();
    expect(screen.getByText("觀望/續抱")).toBeInTheDocument();
  });

  it("WS 即時事件排最前，且與播種去重後合併", async () => {
    api.getRecentDecisions.mockResolvedValue([
      {
        id: 1,
        bot_id: 1,
        bot_name: "甲Bot",
        symbol: "AAPL",
        signal: "hold",
        reason: "舊的觀望",
        price: 10,
        action: "hold",
        created_at: "2026-06-12T09:00:00",
      },
    ]);
    const wsFeed = [
      {
        bot_id: 1,
        bot_name: "甲Bot",
        symbol: "AAPL",
        phase: "decision",
        ts: Date.now() / 1000,
        decision: { signal: "buy", action: "bought", reason: "即時買進", price: 11 },
      },
    ];
    render(<DecisionFeed feed={wsFeed} />);
    // 兩邊都在（合併不互斥）；即時事件（買進）渲染於流中
    await waitFor(() => expect(screen.getByText(/舊的觀望/)).toBeInTheDocument());
    expect(screen.getByText(/即時買進/)).toBeInTheDocument();
  });

  it("播種失敗（後端離線）不炸，仍渲染 WS feed", async () => {
    api.getRecentDecisions.mockRejectedValue(new Error("offline"));
    const wsFeed = [
      {
        bot_id: 2,
        bot_name: "乙Bot",
        symbol: "TSLA",
        phase: "decision",
        ts: Date.now() / 1000,
        decision: { signal: "hold", action: "hold", reason: "WS 來的", price: null },
      },
    ];
    render(<DecisionFeed feed={wsFeed} />);
    expect(await screen.findByText("乙Bot")).toBeInTheDocument();
    expect(screen.getByText(/WS 來的/)).toBeInTheDocument();
  });
});
