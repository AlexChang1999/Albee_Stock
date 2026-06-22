// ============================================================
// BotStrategyChart 的元件測試
// ============================================================
// LightweightChart 本體需要 canvas（jsdom 沒有）→ mock 成 props 記錄器，
// 驗證「API 資料 → 圖表 props」的組裝邏輯（色名映射 / markers 轉換 / 開關）。

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import BotStrategyChart from "./BotStrategyChart";
import { api } from "../api";
import { NEON } from "../theme";

vi.mock("../api", () => ({
  api: { getBotChartData: vi.fn() },
}));

// mock 圖表：把收到的 props 記下來給斷言用
let chartProps = null;
vi.mock("../LightweightChart", () => ({
  default: (props) => {
    chartProps = props;
    return <div data-testid="chart" />;
  },
}));

const bots = [{ id: 1, name: "甲Bot", symbol: "AAPL" }];

const chartData = {
  symbol: "AAPL",
  strategy: "ma_crossover",
  candles: [{ time: "2026-06-01", open: 1, high: 2, low: 1, close: 2, volume: 10 }],
  overlays: [
    { id: "ma_short", title: "MA5", color: "cyan", data: [{ time: "2026-06-01", value: 1.5 }] },
  ],
  pane: null,
  markers: [
    { time: "2026-06-02", kind: "trade", side: "buy", price: 2, text: "買 3 股" },
    { time: "2026-06-01", kind: "decision", action: "hold", reason: "觀望" },
  ],
};

async function selectBot() {
  // MUI select：先開下拉，再點選項
  fireEvent.mouseDown(screen.getByLabelText("選擇 Bot"));
  fireEvent.click(within(screen.getByRole("listbox")).getByText(/甲Bot/));
  await waitFor(() => expect(screen.getByTestId("chart")).toBeInTheDocument());
}

describe("BotStrategyChart", () => {
  beforeEach(() => {
    chartProps = null;
    api.getBotChartData.mockReset();
    api.getBotChartData.mockResolvedValue(chartData);
  });

  it("未選 Bot 顯示引導文字、不渲染圖表", () => {
    render(<BotStrategyChart bots={bots} />);
    expect(screen.getByText(/選一個 Bot/)).toBeInTheDocument();
    expect(screen.queryByTestId("chart")).not.toBeInTheDocument();
  });

  it("選 Bot → 抓 chart-data，色名映射成 NEON、成交標記轉箭頭", async () => {
    render(<BotStrategyChart bots={bots} />);
    await selectBot();

    expect(api.getBotChartData).toHaveBeenCalledWith(1);
    // 色名 "cyan" → NEON.cyan（後端不寫死 hex）
    expect(chartProps.overlays[0].color).toBe(NEON.cyan);
    // 預設不顯示觀望點 → 只剩成交箭頭
    expect(chartProps.markers).toHaveLength(1);
    expect(chartProps.markers[0]).toMatchObject({
      shape: "arrowUp",
      position: "belowBar",
      color: NEON.green,
    });
    // candles 直接餵給圖表（不再自己抓 /bars）
    expect(chartProps.candles).toHaveLength(1);
  });

  it("打開「顯示觀望點」→ markers 多出 circle 且依時間排序", async () => {
    render(<BotStrategyChart bots={bots} />);
    await selectBot();

    fireEvent.click(screen.getByRole("switch"));
    await waitFor(() => expect(chartProps.markers).toHaveLength(2));
    // 觀望點（06-01）在前、成交（06-02）在後：依時間升冪
    expect(chartProps.markers[0].shape).toBe("circle");
    expect(chartProps.markers[1].shape).toBe("arrowUp");
  });

  it("不支援疊圖的策略顯示提示", async () => {
    api.getBotChartData.mockResolvedValue({
      ...chartData,
      strategy: "composite",
      overlays: [],
      pane: null,
    });
    render(<BotStrategyChart bots={bots} />);
    await selectBot();
    expect(screen.getByText(/不支援指標疊圖/)).toBeInTheDocument();
  });
});
