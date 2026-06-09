// CollectorPage：收件匣渲染 + 狀態策展（Phase 10 step-04）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api", () => ({
  api: {
    getCollectorFinds: vi.fn(),
    updateCollectorFind: vi.fn(),
  },
}));

import { api } from "../api";
import CollectorPage from "./CollectorPage";

const ROWS = [
  {
    id: 1, source: "blog.example.com", source_url: "https://blog.example.com/x",
    title: "Mean reversion on SPY", summary: "Buy low RSI", status: "new",
    fetched_at: "2026-06-09T10:00:00",
  },
  {
    id: 2, source: "quant.example.com", source_url: "https://quant.example.com/y",
    title: "Pairs trading", summary: "Cointegration", status: "triaged",
    fetched_at: "2026-06-09T09:00:00",
  },
];

describe("CollectorPage", () => {
  beforeEach(() => {
    api.getCollectorFinds.mockReset();
    api.updateCollectorFind.mockReset();
    api.getCollectorFinds.mockResolvedValue(ROWS);
    api.updateCollectorFind.mockResolvedValue({ id: 1, status: "triaged" });
  });

  it("渲染素材清單 + 狀態中文標籤 + 來源連結", async () => {
    render(<CollectorPage />);
    expect(await screen.findByText("Mean reversion on SPY")).toBeInTheDocument();
    expect(screen.getByText("Pairs trading")).toBeInTheDocument();
    expect(screen.getByText("新收")).toBeInTheDocument(); // status=new
    // 來源連結指到原文
    const link = screen.getByText("Mean reversion on SPY").closest("a");
    expect(link).toHaveAttribute("href", "https://blog.example.com/x");
  });

  it("策展鈕呼叫 updateCollectorFind 並重抓", async () => {
    render(<CollectorPage />);
    await screen.findByText("Mean reversion on SPY");
    // new 狀態的第一個流轉動作是「待試」(triaged)。
    // 用 role=button 選，避開 row2 那個同名的「待試」狀態 Chip（Chip 非 button）。
    fireEvent.click(screen.getByRole("button", { name: "待試" }));
    await waitFor(() =>
      expect(api.updateCollectorFind).toHaveBeenCalledWith(1, "triaged")
    );
    // 重抓清單（load 再被呼叫一次：初次 + 策展後）
    expect(api.getCollectorFinds).toHaveBeenCalledTimes(2);
  });
});
