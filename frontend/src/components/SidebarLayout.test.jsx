// SidebarLayout：導覽外殼 smoke test（Phase 9 step-01）
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import SidebarLayout from "./SidebarLayout";

// 用 MemoryRouter 包起來，掛一個 index 路由當 Outlet 內容。
function renderShell(initial = "/") {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route element={<SidebarLayout status={null} loading={false} />}>
          <Route index element={<div>首頁內容</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("SidebarLayout", () => {
  it("列出所有導覽項目", () => {
    renderShell();
    expect(screen.getByText("監控中心")).toBeInTheDocument();
    expect(screen.getByText("AI 探勘")).toBeInTheDocument();
    expect(screen.getByText("K 線圖")).toBeInTheDocument();
    expect(screen.getByText("基本面")).toBeInTheDocument();
    expect(screen.getByText("回測 / 交易")).toBeInTheDocument();
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
