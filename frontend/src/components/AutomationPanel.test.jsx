// AutomationPanel：模式 B 自動化規則面板（redesign Phase 4 前端收尾）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api", () => ({
  api: { getAutomation: vi.fn(), runAutomation: vi.fn() },
}));

import { api } from "../api";
import AutomationPanel from "./AutomationPanel";

const RULES = {
  enabled: false,
  ev_threshold: 150,
  winrate_threshold: 0.55,
  max_bots: 5,
  cash_per_bot: 1000,
  scan_hour: 9,
  active_bots: 2,
  slots_left: 3,
};

describe("AutomationPanel", () => {
  beforeEach(() => {
    api.getAutomation.mockReset();
    api.runAutomation.mockReset();
    api.getAutomation.mockResolvedValue(RULES);
  });

  it("掛載後顯示規則門檻與名額", async () => {
    render(<AutomationPanel />);
    expect(await screen.findByText("150")).toBeInTheDocument(); // EV 門檻
    expect(screen.getByText("55%")).toBeInTheDocument(); // 勝率門檻
    expect(screen.getByText("2 / 5")).toBeInTheDocument(); // 名額
    expect(screen.getByText("已關閉")).toBeInTheDocument(); // 總開關狀態
    expect(api.getAutomation).toHaveBeenCalled();
  });

  it("按預覽（dry-run）呼叫 runAutomation 並列出達標清單", async () => {
    api.runAutomation.mockResolvedValue({
      dry_run: true,
      planned: [{ symbol: "AAPL", strategy_key: "rsi" }],
      deployed: [],
    });
    render(<AutomationPanel />);
    await screen.findByText("150");
    fireEvent.click(screen.getByText("預覽（dry-run）"));
    await waitFor(() =>
      expect(api.runAutomation).toHaveBeenCalledWith({ force: true, dry_run: true })
    );
    expect(await screen.findByText(/AAPL（rsi）/)).toBeInTheDocument();
  });

  it("試跑需先確認，確認後實跑並通知 onChanged", async () => {
    api.runAutomation.mockResolvedValue({ dry_run: false, planned: [], deployed: [] });
    const onChanged = vi.fn();
    render(<AutomationPanel onChanged={onChanged} />);
    await screen.findByText("150");
    fireEvent.click(screen.getByText("立即試跑一輪"));
    // 確認視窗出現後按「試跑」
    fireEvent.click(await screen.findByText("試跑"));
    await waitFor(() =>
      expect(api.runAutomation).toHaveBeenCalledWith({ force: true, dry_run: false })
    );
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });
});
