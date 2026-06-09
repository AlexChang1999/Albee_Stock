// ============================================================
// EditBotDialog 的元件測試（聚焦在表單驗證閘）
// ============================================================
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import EditBotDialog from "./EditBotDialog";

const validBot = {
  id: 1,
  name: "測試Bot",
  strategy: "ma_crossover",
  symbol: "AAPL",
  trade_amount: 1000,
  tp: "",
  sl: "",
  trail: "",
  interval: 60,
};

function saveButton() {
  return screen.getByRole("button", { name: "儲存" });
}

describe("EditBotDialog", () => {
  it("名稱空白時，儲存鈕停用", () => {
    render(
      <EditBotDialog
        editBot={{ ...validBot, name: "" }}
        setEditBot={() => {}}
        onSave={() => {}}
      />
    );
    expect(saveButton()).toBeDisabled();
  });

  it("欄位填妥時，儲存鈕可用且點擊呼叫 onSave", () => {
    const onSave = vi.fn();
    render(
      <EditBotDialog editBot={validBot} setEditBot={() => {}} onSave={onSave} />
    );
    expect(saveButton()).toBeEnabled();
    fireEvent.click(saveButton());
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("止盈填超過 100 時，儲存鈕停用", () => {
    render(
      <EditBotDialog
        editBot={{ ...validBot, tp: "150" }}
        setEditBot={() => {}}
        onSave={() => {}}
      />
    );
    expect(saveButton()).toBeDisabled();
  });
});
