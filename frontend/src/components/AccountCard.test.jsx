// ============================================================
// AccountCard 的元件測試
// ============================================================
// 驗兩個狀態：有帳戶資料時畫四個數字格；還沒載入（account=null）時
// 畫 Skeleton 灰塊佔位（E3），而不是一行「載入中」文字。
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AccountCard from "./AccountCard";

const ACCOUNT = {
  status: "ACTIVE",
  cash: 10000,
  buying_power: 20000,
  portfolio_value: 12345,
};

describe("AccountCard", () => {
  it("有資料時顯示狀態與金額", () => {
    render(<AccountCard account={ACCOUNT} />);
    expect(screen.getByText("帳戶資訊")).toBeInTheDocument();
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
    expect(screen.getByText(/12,345/)).toBeInTheDocument();
  });

  it("account=null 時顯示 Skeleton 載入態", () => {
    render(<AccountCard account={null} />);
    expect(screen.getByLabelText("帳戶資訊載入中")).toBeInTheDocument();
    // 不應出現任何金額
    expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
  });
});
