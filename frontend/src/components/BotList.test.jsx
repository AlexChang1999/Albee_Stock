// ============================================================
// BotList 的元件測試
// ============================================================
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import BotList from "./BotList";

// 測試用的最小 Bot 物件（欄位齊到能渲染即可）
const bot = {
  id: 1,
  name: "測試Bot",
  is_active: false,
  strategy: "ma_crossover",
  symbol: "AAPL",
  trade_amount: 1000,
  peak_price: null,
  last_checked_at: null,
  stats: null,
};

describe("BotList", () => {
  it("空清單顯示提示文字", () => {
    render(<BotList bots={[]} />);
    expect(screen.getByText(/還沒有任何 Bot/)).toBeInTheDocument();
  });

  it("渲染 Bot 名稱", () => {
    render(<BotList bots={[bot]} />);
    expect(screen.getByText("測試Bot")).toBeInTheDocument();
  });

  it("按啟動鈕會以該 Bot 呼叫 onToggle", () => {
    const onToggle = vi.fn();
    render(<BotList bots={[bot]} onToggle={onToggle} />);
    // 圖示鈕用 aria-label 找（無障礙名稱）
    fireEvent.click(screen.getByLabelText("啟動 測試Bot"));
    expect(onToggle).toHaveBeenCalledWith(bot);
  });

  it("按決策軌跡鈕會以該 Bot 呼叫 onShowDecisions", () => {
    const onShowDecisions = vi.fn();
    render(<BotList bots={[bot]} onShowDecisions={onShowDecisions} />);
    fireEvent.click(screen.getByLabelText("查看 測試Bot 的決策軌跡"));
    expect(onShowDecisions).toHaveBeenCalledWith(bot);
  });
});
