// PromotionPage：董事會核准頁渲染 + 提議/核准/退回（Phase 10 step-06）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api", () => ({
  api: {
    getPromotions: vi.fn(),
    proposePromotion: vi.fn(() => Promise.resolve({})),
    approvePromotion: vi.fn(() => Promise.resolve({})),
    rejectPromotion: vi.fn(() => Promise.resolve({})),
  },
}));

import { api } from "../api";
import PromotionPage from "./PromotionPage";

const PAPER = [
  {
    bot_id: 7,
    name: "AAPL 達標 Bot",
    symbol: "AAPL",
    strategy_key: "ma_crossover",
    promotion_status: "paper",
    oos_expected_value: 300,
    paper_stats: { win_rate_pct: 80, num_round_trips: 4, return_pct: 12 },
    promotion_reason: null,
  },
];
const PROPOSED = [
  {
    bot_id: 9,
    name: "TSLA 待核 Bot",
    symbol: "TSLA",
    strategy_key: "rsi",
    promotion_status: "proposed_live",
    oos_expected_value: 250,
    paper_stats: { win_rate_pct: 70, num_round_trips: 5, return_pct: 8 },
    promotion_reason: "OOS EV=250；Paper 勝率=70%、完整買賣=5 次、報酬=8%",
  },
];

describe("PromotionPage", () => {
  beforeEach(() => {
    api.getPromotions.mockReset();
    api.getPromotions.mockImplementation((status) =>
      Promise.resolve(status === "proposed_live" ? PROPOSED : status === "paper" ? PAPER : [])
    );
    api.proposePromotion.mockClear();
    api.approvePromotion.mockClear();
  });

  it("預設列出 Paper 候選並可按『提議上真錢』", async () => {
    render(<PromotionPage />);
    expect(await screen.findByText("AAPL 達標 Bot")).toBeInTheDocument();
    fireEvent.click(screen.getByText("提議上真錢"));
    await waitFor(() => expect(api.proposePromotion).toHaveBeenCalledWith(7));
  });

  it("切到待核後按『核准』呼叫 approvePromotion", async () => {
    render(<PromotionPage />);
    await screen.findByText("AAPL 達標 Bot");
    fireEvent.click(screen.getByText("待核"));
    fireEvent.click(await screen.findByText("核准"));
    await waitFor(() => expect(api.approvePromotion).toHaveBeenCalledWith(9));
  });
});
