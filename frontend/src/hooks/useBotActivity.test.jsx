// ============================================================
// useBotActivity 的 Hook 測試（mock WebSocket + 假時鐘）
// ============================================================
// 驗證播放器核心邏輯：
// 1. 密集事件依序播放、每階段至少顯示最少時間（資料真、節奏前端控）
// 2. cycle_end 播完 → 待機 + nextRunAt 倒數
// 3. 倒數歸零 + 寬限過了沒新一輪 → stale（真跑/假跑偵測器）
// 4. 斷線 → connected=false（元件據此優雅降級）
// 5. 決策事件（含觀望）即時進 feed

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useBotActivity, STALE_GRACE_MS } from "./useBotActivity";

// 假 WebSocket：記錄實例，手動觸發 onopen/onmessage/onclose
class MockWebSocket {
  static instances = [];
  constructor(url) {
    this.url = url;
    this.readyState = 1;
    MockWebSocket.instances.push(this);
  }
  send() {}
  close() {
    this.onclose?.();
  }
}

/** 組一則測試事件（ts 用目前假時鐘 → 一定是「新鮮」事件，會播動畫）。 */
function ev(phase, extra = {}) {
  return JSON.stringify({
    type: "bot_activity",
    bot_id: 1,
    bot_name: "測試Bot",
    symbol: "TEST",
    phase,
    detail: `${phase} 中`,
    ts: Date.now() / 1000,
    ...extra,
  });
}

describe("useBotActivity", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  function setup() {
    const hook = renderHook(() => useBotActivity());
    const ws = MockWebSocket.instances.at(-1);
    act(() => ws.onopen());
    return { hook, ws };
  }

  it("連上 → connected=true；斷線 → false", () => {
    const { hook, ws } = setup();
    expect(hook.result.current.connected).toBe(true);
    act(() => ws.onclose());
    expect(hook.result.current.connected).toBe(false);
  });

  it("密集事件依序播放，每階段至少顯示最少時間", () => {
    const { hook, ws } = setup();
    // 一輪 <1 秒的密集事件一次到齊
    act(() => {
      ws.onmessage({ data: ev("cycle_start") });
      ws.onmessage({ data: ev("fetch_data") });
      ws.onmessage({
        data: ev("decision", {
          decision: { signal: "hold", action: "hold", reason: "觀望", price: 50 },
        }),
      });
      ws.onmessage({
        data: ev("cycle_end", { status: "ok", next_run_in_sec: 60, is_active: true }),
      });
    });

    // t=250ms：第一則開播
    act(() => vi.advanceTimersByTime(250));
    expect(hook.result.current.activityByBot["1"].phase).toBe("cycle_start");
    // t=450ms：未滿 600ms 最少顯示時間 → 還是 cycle_start
    act(() => vi.advanceTimersByTime(200));
    expect(hook.result.current.activityByBot["1"].phase).toBe("cycle_start");
    // t=850ms：換 fetch_data
    act(() => vi.advanceTimersByTime(400));
    expect(hook.result.current.activityByBot["1"].phase).toBe("fetch_data");
    // t=1450ms：換 decision（決策停 1800ms）
    act(() => vi.advanceTimersByTime(600));
    expect(hook.result.current.activityByBot["1"].phase).toBe("decision");
    // t=2850ms：決策還沒滿 1800ms → 仍在 decision
    act(() => vi.advanceTimersByTime(1400));
    expect(hook.result.current.activityByBot["1"].phase).toBe("decision");
    // t=3450ms：換 cycle_end
    act(() => vi.advanceTimersByTime(600));
    expect(hook.result.current.activityByBot["1"].phase).toBe("cycle_end");
    // t=4250ms：播完 → 待機 + 倒數
    act(() => vi.advanceTimersByTime(800));
    const idle = hook.result.current.activityByBot["1"];
    expect(idle.phase).toBe("idle");
    expect(idle.nextRunAt).toBeGreaterThan(Date.now());
    expect(idle.stale).toBe(false);
  });

  it("倒數歸零 + 寬限過了沒新一輪 → stale 亮燈", () => {
    const { hook, ws } = setup();
    act(() => {
      ws.onmessage({
        data: ev("cycle_end", { status: "ok", next_run_in_sec: 5, is_active: true }),
      });
    });
    // 播完 cycle_end 進待機
    act(() => vi.advanceTimersByTime(1200));
    expect(hook.result.current.activityByBot["1"].phase).toBe("idle");
    expect(hook.result.current.activityByBot["1"].stale).toBe(false);
    // 過了 next_run（5s）+ 寬限 → stale
    act(() => vi.advanceTimersByTime(5000 + STALE_GRACE_MS + 1000));
    expect(hook.result.current.activityByBot["1"].stale).toBe(true);
  });

  it("決策事件（含觀望）即時進 feed、最新在前", () => {
    const { hook, ws } = setup();
    act(() => {
      ws.onmessage({
        data: ev("decision", {
          decision: { signal: "hold", action: "hold", reason: "第一筆", price: 1 },
        }),
      });
    });
    act(() => vi.advanceTimersByTime(50));
    act(() => {
      ws.onmessage({
        data: ev("decision", {
          decision: { signal: "buy", action: "bought", reason: "第二筆", price: 2 },
        }),
      });
    });
    const feed = hook.result.current.feed;
    expect(feed).toHaveLength(2);
    expect(feed[0].decision.reason).toBe("第二筆"); // 最新在前
  });

  it("休市輪不播動畫：直接進靜態待機（marketClosed）", () => {
    const { hook, ws } = setup();
    act(() => {
      ws.onmessage({
        data: ev("cycle_end", {
          status: "skipped_market_closed",
          next_run_in_sec: 60,
          is_active: true,
        }),
      });
    });
    act(() => vi.advanceTimersByTime(250));
    const st = hook.result.current.activityByBot["1"];
    expect(st.phase).toBe("idle");
    expect(st.marketClosed).toBe(true);
  });
});
