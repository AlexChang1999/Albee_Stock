// EvolutionPage：進化實驗室渲染 + 人在迴路晉升/退回（Phase 9 step-07）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api", () => ({
  api: {
    getKnowledge: vi.fn(),
    validateKnowledge: vi.fn(),
    promoteKnowledge: vi.fn(() => Promise.resolve({})),
    rejectKnowledge: vi.fn(() => Promise.resolve({})),
  },
}));

import { api } from "../api";
import EvolutionPage from "./EvolutionPage";

const CANDIDATES = [
  { id: 1, name: "RSI 候選 #1", strategy_key: "rsi", status: "candidate", oos_metrics: {}, params: {} },
];
const VALIDATED = [
  { id: 2, name: "均線 候選", strategy_key: "ma_crossover", status: "validated", oos_metrics: { expected_value: 9.1 }, params: {} },
];

describe("EvolutionPage", () => {
  beforeEach(() => {
    api.getKnowledge.mockReset();
    api.getKnowledge.mockImplementation((status) =>
      Promise.resolve(status === "validated" ? VALIDATED : CANDIDATES)
    );
    api.promoteKnowledge.mockClear();
  });

  it("預設列出候選並可按驗證", async () => {
    render(<EvolutionPage />);
    expect(await screen.findByText("RSI 候選 #1")).toBeInTheDocument();
    expect(screen.getByText("驗證")).toBeInTheDocument();
  });

  it("切到已驗證後按晉升呼叫 promoteKnowledge", async () => {
    render(<EvolutionPage />);
    await screen.findByText("RSI 候選 #1");
    fireEvent.click(screen.getByText("已驗證"));
    fireEvent.click(await screen.findByText("晉升"));
    await waitFor(() => expect(api.promoteKnowledge).toHaveBeenCalledWith(2));
  });
});
