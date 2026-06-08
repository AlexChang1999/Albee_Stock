// AutomationPanel：模式 B 自動化規則面板（規則存 DB，可編輯）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api", () => ({
  api: {
    getAutomation: vi.fn(),
    runAutomation: vi.fn(),
    updateAutomation: vi.fn(),
  },
}));

import { api } from "../api";
import AutomationPanel from "./AutomationPanel";

// 注意：winrate_threshold 後端存「百分比」（55 = 55%），前端直接顯示不再 ×100。
const RULES = {
  enabled: false,
  ev_threshold: 150,
  winrate_threshold: 55,
  max_bots: 5,
  cash_per_bot: 1000,
  scan_hour: 9,
  scan_interval_min: 30,
  active_bots: 2,
  slots_left: 3,
};

describe("AutomationPanel", () => {
  beforeEach(() => {
    api.getAutomation.mockReset();
    api.runAutomation.mockReset();
    api.updateAutomation.mockReset();
    api.getAutomation.mockResolvedValue(RULES);
  });

  it("掛載後顯示規則門檻與名額", async () => {
    render(<AutomationPanel />);
    expect(await screen.findByText("150")).toBeInTheDocument(); // EV 門檻
    expect(screen.getByText("55%")).toBeInTheDocument(); // 勝率門檻（不再 ×100）
    expect(screen.getByText("2 / 5")).toBeInTheDocument(); // 名額
    expect(screen.getByText("30 分")).toBeInTheDocument(); // 探勘間隔
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

  it("編輯規則：改 EV 門檻並儲存 → 呼叫 updateAutomation", async () => {
    api.updateAutomation.mockResolvedValue({ ...RULES, ev_threshold: 200 });
    render(<AutomationPanel />);
    await screen.findByText("150");
    fireEvent.click(screen.getByText("編輯規則"));
    const evInput = await screen.findByLabelText("EV 門檻");
    fireEvent.change(evInput, { target: { value: "200" } });
    fireEvent.click(screen.getByText("儲存"));
    await waitFor(() => expect(api.updateAutomation).toHaveBeenCalled());
    // 儲存後回檢視模式、顯示新值
    expect(await screen.findByText("200")).toBeInTheDocument();
  });

  it("開啟總開關需先確認，確認後才 updateAutomation", async () => {
    api.updateAutomation.mockResolvedValue({ ...RULES, enabled: true });
    render(<AutomationPanel />);
    await screen.findByText("150");
    fireEvent.click(screen.getByText("編輯規則"));
    // 打開總開關（用 label 連結定位，避免 MUI Switch role 命名差異）
    const toggle = await screen.findByLabelText(/自動化總開關/);
    fireEvent.click(toggle);
    fireEvent.click(screen.getByText("儲存"));
    // 還沒確認 → 不應呼叫
    expect(api.updateAutomation).not.toHaveBeenCalled();
    // 確認視窗按「開啟並儲存」
    fireEvent.click(await screen.findByText("開啟並儲存"));
    await waitFor(() => expect(api.updateAutomation).toHaveBeenCalled());
  });
});
