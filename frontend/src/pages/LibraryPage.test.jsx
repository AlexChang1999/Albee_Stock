// LibraryPage：策略知識庫渲染（Phase 9 step-07）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("../api", () => ({
  api: { getKnowledgeRanking: vi.fn() },
}));

import { api } from "../api";
import LibraryPage from "./LibraryPage";

const CURATED = [
  { id: 1, name: "策展均線", strategy_key: "ma_crossover", status: "curated", theory: "順勢", oos_metrics: { expected_value: 12 }, params: {} },
];
const VALIDATED = [
  { id: 2, name: "驗證 RSI", strategy_key: "rsi", status: "validated", oos_metrics: { expected_value: 5 }, params: {} },
];

describe("LibraryPage", () => {
  beforeEach(() => {
    api.getKnowledgeRanking.mockReset();
    api.getKnowledgeRanking.mockImplementation((status) =>
      Promise.resolve(status === "validated" ? VALIDATED : CURATED)
    );
  });

  it("預設顯示策展庫", async () => {
    render(<LibraryPage />);
    expect(await screen.findByText("策展均線")).toBeInTheDocument();
    expect(api.getKnowledgeRanking).toHaveBeenCalledWith("curated");
  });

  it("切到已驗證會重抓", async () => {
    render(<LibraryPage />);
    await screen.findByText("策展均線");
    fireEvent.click(screen.getByText("已驗證"));
    expect(await screen.findByText("驗證 RSI")).toBeInTheDocument();
  });
});
