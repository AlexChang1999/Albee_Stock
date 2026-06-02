// ============================================================
// ConfirmDialog 的元件測試
// ============================================================
// 這裡示範「測元件」三步驟：
//   1. render(...)：把元件畫到模擬的瀏覽器（jsdom）裡
//   2. screen.getByText(...)：找畫面上的元素
//   3. fireEvent.click(...)：模擬使用者點擊，再驗證對應的函式有沒有被呼叫
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ConfirmDialog from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("open=true 時，標題與內文都看得到", () => {
    render(
      <ConfirmDialog
        open
        title="刪除 Bot"
        message="確定要刪除「測試 Bot」嗎？"
        onConfirm={() => {}}
        onClose={() => {}}
      />
    );
    expect(screen.getByText("刪除 Bot")).toBeInTheDocument();
    expect(screen.getByText("確定要刪除「測試 Bot」嗎？")).toBeInTheDocument();
  });

  it("按下確認鈕會呼叫 onConfirm", () => {
    // vi.fn() 建一個「假函式」，用來記錄有沒有被呼叫
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        title="刪除 Bot"
        message="確定？"
        confirmText="刪除"
        onConfirm={onConfirm}
        onClose={() => {}}
      />
    );
    fireEvent.click(screen.getByText("刪除"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("按下取消鈕會呼叫 onClose", () => {
    const onClose = vi.fn();
    render(
      <ConfirmDialog
        open
        title="刪除 Bot"
        message="確定？"
        onConfirm={() => {}}
        onClose={onClose}
      />
    );
    fireEvent.click(screen.getByText("取消"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
