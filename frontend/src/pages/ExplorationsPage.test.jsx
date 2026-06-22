// ExplorationsPage：探討頁渲染 + 讀內容（Phase 9 step-05）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("../api", () => ({
  api: {
    getExplorations: vi.fn(),
    getExploration: vi.fn(),
  },
}));

import { api } from "../api";
import ExplorationsPage from "./ExplorationsPage";

const ENTRIES = [
  { run_id: 12, file: "run-0012-williams_r-aapl.md", strategy: "williams_r", symbol: "aapl", summary: "EV 為負" },
  { run_id: 13, file: "run-0013-rsi-tsla.md", strategy: "rsi", symbol: "tsla", summary: "盤整假訊號" },
];

describe("ExplorationsPage", () => {
  beforeEach(() => {
    api.getExplorations.mockReset();
    api.getExplorations.mockResolvedValue(ENTRIES);
    api.getExploration.mockReset();
    api.getExploration.mockResolvedValue({
      name: "run-0012-williams_r-aapl.md",
      content: "# 檢討\n\n建議放寬參數區間。",
    });
  });

  it("列出路標清單", async () => {
    render(<ExplorationsPage />);
    expect(await screen.findByText("run#12 · williams_r / aapl")).toBeInTheDocument();
    expect(screen.getByText("run#13 · rsi / tsla")).toBeInTheDocument();
  });

  it("點一篇讀回內容", async () => {
    render(<ExplorationsPage />);
    fireEvent.click(await screen.findByText("run#12 · williams_r / aapl"));
    expect(await screen.findByText(/建議放寬參數區間/)).toBeInTheDocument();
    expect(api.getExploration).toHaveBeenCalledWith("run-0012-williams_r-aapl.md");
  });
});
