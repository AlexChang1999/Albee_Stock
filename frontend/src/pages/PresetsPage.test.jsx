// PresetsPage：策略方案 CRUD 互動（Phase 9 step-04）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api", () => ({
  api: {
    getPresets: vi.fn(),
    createPreset: vi.fn(() => Promise.resolve({})),
    updatePreset: vi.fn(() => Promise.resolve({})),
    deletePreset: vi.fn(() => Promise.resolve({})),
    backtestPreset: vi.fn(),
    presetToBot: vi.fn(() => Promise.resolve({ id: 9, name: "我的均線", symbol: "AAPL" })),
    getReminders: vi.fn(() => Promise.resolve({ reminders: [] })),
  },
}));

import { api } from "../api";
import PresetsPage from "./PresetsPage";

const PRESETS = [
  { id: 1, name: "我的均線", strategy_key: "ma_crossover", symbol: "AAPL", is_favorite: false, params: {} },
];

describe("PresetsPage", () => {
  beforeEach(() => {
    api.getPresets.mockReset();
    api.getPresets.mockResolvedValue(PRESETS);
    api.createPreset.mockClear();
    api.deletePreset.mockClear();
    api.presetToBot.mockClear();
    api.getReminders.mockClear();
    api.getReminders.mockResolvedValue({ reminders: [] });
  });

  it("渲染既有方案", async () => {
    render(<PresetsPage />);
    expect(await screen.findByText("我的均線")).toBeInTheDocument();
  });

  it("新增方案會呼叫 createPreset", async () => {
    render(<PresetsPage />);
    await screen.findByText("我的均線");
    fireEvent.change(screen.getByLabelText("方案名稱"), { target: { value: "新方案" } });
    fireEvent.change(screen.getByLabelText("股票"), { target: { value: "tsla" } });
    fireEvent.click(screen.getByText("＋ 新增方案"));
    await waitFor(() =>
      expect(api.createPreset).toHaveBeenCalledWith(
        expect.objectContaining({ name: "新方案", symbol: "TSLA" })
      )
    );
  });

  it("刪除走 ConfirmDialog 確認後呼叫 deletePreset", async () => {
    render(<PresetsPage />);
    await screen.findByText("我的均線");
    fireEvent.click(screen.getByText("🗑"));
    // ConfirmDialog 出現，按「刪除」
    fireEvent.click(screen.getByRole("button", { name: "刪除" }));
    await waitFor(() => expect(api.deletePreset).toHaveBeenCalledWith(1));
  });

  it("轉成 Bot 走確認後呼叫 presetToBot 並顯示成功訊息", async () => {
    render(<PresetsPage />);
    await screen.findByText("我的均線");
    fireEvent.click(screen.getByText("🤖 轉成 Bot 實跑"));
    // ConfirmDialog 出現，按「建立 Bot」
    fireEvent.click(screen.getByRole("button", { name: "建立 Bot" }));
    await waitFor(() => expect(api.presetToBot).toHaveBeenCalledWith(1));
    expect(await screen.findByText(/已建立 Bot/)).toBeInTheDocument();
  });
});
