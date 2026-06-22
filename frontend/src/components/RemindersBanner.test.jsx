// RemindersBanner：主動提醒橫幅（Phase 5 選配）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("../api", () => ({
  api: { getReminders: vi.fn() },
}));

import { api } from "../api";
import RemindersBanner from "./RemindersBanner";

describe("RemindersBanner", () => {
  beforeEach(() => {
    api.getReminders.mockReset();
  });

  it("無提醒時不渲染任何內容", async () => {
    api.getReminders.mockResolvedValue({ reminders: [] });
    const { container } = render(<RemindersBanner />);
    await waitFor(() => expect(api.getReminders).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("有提醒時列出訊息與則數", async () => {
    api.getReminders.mockResolvedValue({
      reminders: [
        { type: "review_negative_ev", run_id: 1, message: "NVDA／rsi 回測 EV 為負且尚未檢討" },
        { type: "deploy_good_strategy", run_id: 2, message: "MSFT／macd 已標為好策略但還沒實跑" },
      ],
    });
    render(<RemindersBanner />);
    expect(await screen.findByText(/有 2 則待辦提醒/)).toBeInTheDocument();
    expect(screen.getByText(/NVDA／rsi 回測 EV 為負/)).toBeInTheDocument();
    expect(screen.getByText(/MSFT／macd 已標為好策略/)).toBeInTheDocument();
  });
});
