// AssistantDrawer：全站助手抽屜 聊天 + 檢討（Phase 9 step-08）
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api", () => ({
  api: {
    sendChat: vi.fn(() => Promise.resolve({ reply: "這是助手回覆" })),
    postmortem: vi.fn(() => Promise.resolve({ postmortem: "檢討結果", references: [] })),
  },
}));

import { api } from "../api";
import AssistantDrawer from "./AssistantDrawer";

describe("AssistantDrawer", () => {
  beforeEach(() => {
    api.sendChat.mockClear();
    api.postmortem.mockClear();
  });

  it("點浮動鈕開抽屜", () => {
    render(<AssistantDrawer />);
    fireEvent.click(screen.getByText("💬"));
    expect(screen.getByText("思考助手")).toBeInTheDocument();
  });

  it("送出聊天呼叫 sendChat 並顯示回覆", async () => {
    render(<AssistantDrawer />);
    fireEvent.click(screen.getByText("💬"));
    fireEvent.change(screen.getByPlaceholderText("輸入訊息…"), {
      target: { value: "你好" },
    });
    fireEvent.click(screen.getByText("送出"));
    expect(await screen.findByText("這是助手回覆")).toBeInTheDocument();
    expect(api.sendChat).toHaveBeenCalled();
  });

  it("填回測 ID 按檢討呼叫 postmortem", async () => {
    render(<AssistantDrawer />);
    fireEvent.click(screen.getByText("💬"));
    fireEvent.change(screen.getByLabelText("回測 ID"), { target: { value: "12" } });
    fireEvent.click(screen.getByText("檢討"));
    await waitFor(() => expect(api.postmortem).toHaveBeenCalledWith(12));
    expect(await screen.findByText("檢討結果")).toBeInTheDocument();
  });
});
