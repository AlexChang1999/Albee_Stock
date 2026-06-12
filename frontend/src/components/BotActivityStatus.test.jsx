// ============================================================
// BotActivityStatus 的元件測試（各狀態渲染）
// ============================================================
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import BotActivityStatus from "./BotActivityStatus";

describe("BotActivityStatus", () => {
  it("沒有活動資料（WS 沒連上）→ 渲染 null（優雅降級）", () => {
    const { container } = render(<BotActivityStatus activity={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("進行中階段顯示 detail 文字", () => {
    render(
      <BotActivityStatus
        activity={{ phase: "fetch_data", detail: "抓取 AAPL 最近 31 天 K 線" }}
      />
    );
    expect(screen.getByText("抓取 AAPL 最近 31 天 K 線")).toBeInTheDocument();
  });

  it("決策階段顯示動作 chip + 原因", () => {
    render(
      <BotActivityStatus
        activity={{
          phase: "decision",
          decision: { action: "hold", reason: "無交叉訊號，維持觀望" },
        }}
      />
    );
    expect(screen.getByText("觀望/續抱")).toBeInTheDocument();
    expect(screen.getByText("無交叉訊號，維持觀望")).toBeInTheDocument();
  });

  it("待機顯示最近決策 + 倒數", () => {
    render(
      <BotActivityStatus
        activity={{
          phase: "idle",
          decision: { action: "bought", reason: "黃金交叉" },
          nextRunAt: Date.now() + 42000,
          marketClosed: false,
          stale: false,
        }}
      />
    );
    expect(screen.getByText("買進")).toBeInTheDocument();
    expect(screen.getByText(/下輪 \d+s/)).toBeInTheDocument();
  });

  it("休市待機顯示靜態 chip", () => {
    render(
      <BotActivityStatus
        activity={{ phase: "idle", marketClosed: true, nextRunAt: null, stale: false }}
      />
    );
    expect(screen.getByText("休市待機")).toBeInTheDocument();
  });

  it("失聯（stale）顯示紅色警示——真跑/假跑偵測器", () => {
    render(
      <BotActivityStatus
        activity={{
          phase: "idle",
          stale: true,
          nextRunAt: Date.now() - 60000,
          marketClosed: false,
        }}
      />
    );
    expect(screen.getByText(/排程未回應/)).toBeInTheDocument();
  });
});
