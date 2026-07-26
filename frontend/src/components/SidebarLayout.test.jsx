// SidebarLayout：導覽外殼 + 分組折疊 test（Phase 9 step-01；側邊欄整理）
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import SidebarLayout from "./SidebarLayout";

// 用 MemoryRouter 包起來：index 路由當 Outlet 內容，再補一條 "*" 讓子頁（如 /presets）也能落地，
// 好測「直接走訪收合階段內的頁」。
function renderShell(initial = "/") {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route element={<SidebarLayout status={null} loading={false} />}>
          <Route index element={<div>首頁內容</div>} />
          <Route path="*" element={<div>子頁內容</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("SidebarLayout", () => {
  // 折疊狀態會寫進 localStorage；每個測試前清掉，確保都從各組 defaultOpen 起跑、彼此不汙染。
  beforeEach(() => localStorage.clear());

  it("列出 5 個階段標題，預設展開階段的導覽項可見", () => {
    renderShell();
    // 5 個流程階段標題（① 監控看盤 → ⑤ 部署）
    ["① 監控看盤", "② 找題材", "③ 研究‧驗證", "④ 策展‧演進", "⑤ 部署"].forEach((title) =>
      expect(screen.getByText(title)).toBeInTheDocument()
    );
    // 預設展開階段（①②③）底下的項目看得到
    ["監控中心", "交易紀錄", "決策審計", "市場蒐集員", "AI 探勘", "K 線圖"].forEach((label) =>
      expect(screen.getByText(label)).toBeInTheDocument()
    );
  });

  it("次要階段（④⑤）預設收合，底下的頁先不顯示", () => {
    renderShell();
    expect(screen.queryByText("進化實驗室")).not.toBeInTheDocument(); // ④ 策展‧演進
    expect(screen.queryByText("策略方案")).not.toBeInTheDocument(); // ⑤ 部署
  });

  it("點收合階段的標題可展開、看到底下的頁", () => {
    renderShell();
    expect(screen.queryByText("策略方案")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("⑤ 部署")); // 展開「⑤ 部署」
    expect(screen.getByText("策略方案")).toBeInTheDocument();
  });

  it("直接走訪收合階段內的頁時，該階段自動展開（不會把目前頁的導覽藏起來）", () => {
    renderShell("/presets"); // 「策略方案」在預設收合的「⑤ 部署」
    expect(screen.getByText("策略方案")).toBeInTheDocument();
  });

  it("把 Outlet 內容渲染出來", () => {
    renderShell();
    expect(screen.getByText("首頁內容")).toBeInTheDocument();
  });

  it("實盤雙閘全開時顯示真錢警告", () => {
    render(
      <MemoryRouter>
        <Routes>
          <Route
            element={<SidebarLayout status={{ live_armed: true }} loading={false} />}
          >
            <Route index element={<div />} />
          </Route>
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText(/實盤模式/)).toBeInTheDocument();
  });
});
