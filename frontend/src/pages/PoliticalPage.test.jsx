// PoliticalPage：政治事件表 + 風險煞車橫幅（Phase 10 step-05）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../api", () => ({
  api: {
    getPoliticalEvents: vi.fn(),
    getPoliticalRisk: vi.fn(),
  },
}));

import { api } from "../api";
import PoliticalPage from "./PoliticalPage";

const EVENTS = [
  {
    id: 1, source: "discord:trump-mirror", author: "realDonaldTrump",
    content_summary: "Massive tariffs incoming", label: "bearish", score: -80,
    reason: "關稅升溫", posted_at: "2026-06-09T11:00:00", posts_last_24h: 5, posts_last_1h: 2,
  },
];

describe("PoliticalPage", () => {
  beforeEach(() => {
    api.getPoliticalEvents.mockReset();
    api.getPoliticalRisk.mockReset();
    api.getPoliticalEvents.mockResolvedValue(EVENTS);
  });

  it("渲染事件 + 偏空判讀標籤 + 頻率", async () => {
    api.getPoliticalRisk.mockResolvedValue({ brake: false, size_factor: 1.0, reason: "政治風險閘未啟用（預設關）" });
    render(<PoliticalPage />);
    expect(await screen.findByText("realDonaldTrump")).toBeInTheDocument();
    expect(screen.getByText("偏空（風險）")).toBeInTheDocument(); // label=bearish
    expect(screen.getByText("5 / 2")).toBeInTheDocument(); // 頻率
  });

  it("旗標關時顯示放行橫幅（不影響下單）", async () => {
    api.getPoliticalRisk.mockResolvedValue({ brake: false, size_factor: 1.0, reason: "政治風險閘未啟用（預設關）" });
    render(<PoliticalPage />);
    expect(await screen.findByText(/放行/)).toBeInTheDocument();
  });

  it("brake 時顯示不開新倉橫幅", async () => {
    api.getPoliticalRisk.mockResolvedValue({ brake: true, size_factor: 0.0, reason: "重大負面情緒/事件" });
    render(<PoliticalPage />);
    expect(await screen.findByText(/不開新倉/)).toBeInTheDocument();
  });
});
